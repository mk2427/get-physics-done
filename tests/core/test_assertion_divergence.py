"""Tests for gpd.core.assertion_divergence — divergence check (brief 002 §7.3).

Four tests per plan §Commit 8:
* test_restatement_hash_matches_source — correctly computed hash → PASS.
* test_divergence_blocks_stable — stored hash differs from computed → FAIL.
* test_derived_consequence_null_hash — upstream_ref_hash=null → PASS unconditionally.
* test_normalize_eqn_body_integration — compute_upstream_ref_hash produces
  consistent results across whitespace variants (regression guard on eqn_normalize).
"""

from __future__ import annotations

import hashlib

import pytest

from gpd.core.assertion_divergence import (
    DivergenceResult,
    check_divergence_from_dict,
    compute_upstream_ref_hash,
)
from gpd.core.eqn_normalize import normalize_eqn_body


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_restatement_assertion(
    canonical_latex: str,
    entry_id: str = "E.1",
    stored_hash: str | None = None,
) -> tuple[dict, dict[str, str]]:
    """Return (assertion_data, eqn_ref_entries) fixture for a restated-equation path."""
    if stored_hash is None:
        stored_hash = compute_upstream_ref_hash(canonical_latex)
    assertion_data = {
        "kind": "restated-equation",
        "assertion_id": "A-001-test-eq",
        "upstream_ref_hash": stored_hash,
        "eqn_ref_entries": [entry_id],
        "derivation_sketch": None,
    }
    eqn_ref_entries = {entry_id: canonical_latex}
    return assertion_data, eqn_ref_entries


def _make_derived_assertion() -> tuple[dict, dict[str, str]]:
    """Return (assertion_data, eqn_ref_entries) fixture for a derived-consequence path."""
    assertion_data = {
        "kind": "derived-consequence",
        "assertion_id": "A-002-derived",
        "upstream_ref_hash": None,  # derived → no hash
        "eqn_ref_entries": ["E.2"],
        "derivation_sketch": "From E.2 with Cauchy-Schwarz: ||A||^2 ≥ 0.",
    }
    eqn_ref_entries = {
        "E.2": r"S = \int \mathcal{L}\, d^4x",
    }
    return assertion_data, eqn_ref_entries


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestRestatementHashMatchesSource:
    """Correctly computed hash → PASS (canonical path)."""

    def test_basic_equation(self) -> None:
        """Simple equation: stored hash == sha256(normalize(canonical)) → PASS."""
        canonical = r"E = mc^2"
        assertion_data, eqn_ref_entries = _make_restatement_assertion(canonical)

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert isinstance(result, DivergenceResult)
        assert result.passed is True
        assert result.stored_hash == result.computed_hash
        assert result.mismatch_reason is None

    def test_complex_equation(self) -> None:
        """LaTeX with fracs and macros: hash still matches after normalization."""
        canonical = r"\frac{d}{dt} \int \rho \, dV = - \oint \mathbf{J} \cdot d\mathbf{A}"
        assertion_data, eqn_ref_entries = _make_restatement_assertion(canonical, entry_id="E.5")

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is True
        assert result.stored_hash is not None
        assert len(result.stored_hash) == 64  # sha256 hex

    def test_pass_result_fields_populated(self) -> None:
        """On PASS, both stored_hash and computed_hash are populated."""
        canonical = r"\hat{H} \psi = E \psi"
        assertion_data, eqn_ref_entries = _make_restatement_assertion(canonical)

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is True
        assert result.stored_hash is not None
        assert result.computed_hash is not None
        assert result.stored_hash == result.computed_hash


class TestDivergenceBlocksStable:
    """Stored hash differs from computed → FAIL (blocks Stable promotion)."""

    def test_tampered_hash_fails(self) -> None:
        """Storing a wrong hash returns passed=False with hash_mismatch reason."""
        canonical = r"F = ma"
        wrong_hash = "a" * 64  # not the real hash
        assertion_data, eqn_ref_entries = _make_restatement_assertion(
            canonical, stored_hash=wrong_hash
        )

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is False
        assert result.mismatch_reason == "hash_mismatch"
        assert result.stored_hash == wrong_hash
        assert result.computed_hash != wrong_hash
        assert result.computed_hash is not None

    def test_fail_result_has_non_null_mismatch_reason(self) -> None:
        """Brief §7.3: FAIL result must have a non-null mismatch_reason."""
        canonical = r"\nabla \cdot \mathbf{E} = \frac{\rho}{\epsilon_0}"
        bad_hash = hashlib.sha256(b"wrong input").hexdigest()
        assertion_data, eqn_ref_entries = _make_restatement_assertion(
            canonical, stored_hash=bad_hash
        )

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is False
        assert result.mismatch_reason is not None
        assert len(result.mismatch_reason) > 0

    def test_missing_eqn_entry_fails(self) -> None:
        """Assertion references E.99 which is absent from catalog → FAIL."""
        canonical = r"p = mv"
        stored_hash = compute_upstream_ref_hash(canonical)
        assertion_data = {
            "kind": "restated-equation",
            "upstream_ref_hash": stored_hash,
            "eqn_ref_entries": ["E.99"],  # not in catalog
        }
        eqn_ref_entries = {"E.1": canonical}  # E.99 absent

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is False
        assert result.mismatch_reason == "missing_eqn_entry"

    def test_source_equation_changed_fails(self) -> None:
        """Hash correct at write time, but source equation changed → FAIL."""
        original_canonical = r"S = \int \mathcal{L}\, d^4x"
        updated_canonical = r"S = \int \mathcal{L}[\phi]\, d^4x"  # source changed
        stored_hash = compute_upstream_ref_hash(original_canonical)

        assertion_data = {
            "kind": "restated-equation",
            "upstream_ref_hash": stored_hash,
            "eqn_ref_entries": ["E.3"],
        }
        eqn_ref_entries = {"E.3": updated_canonical}  # catalog now has updated form

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is False
        assert result.mismatch_reason == "hash_mismatch"


class TestDerivedConsequenceNullHash:
    """upstream_ref_hash=null → PASS unconditionally (no check needed)."""

    def test_null_hash_passes(self) -> None:
        """Derived-consequence with null hash always passes regardless of entries."""
        assertion_data, eqn_ref_entries = _make_derived_assertion()

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is True
        assert result.stored_hash is None
        assert result.computed_hash is None
        assert result.mismatch_reason is None

    def test_null_hash_passes_even_with_empty_catalog(self) -> None:
        """Derived-consequence: no catalog entries needed when hash is null."""
        assertion_data = {
            "kind": "derived-consequence",
            "upstream_ref_hash": None,
            "eqn_ref_entries": [],
            "derivation_sketch": "Step 1: ...",
        }
        eqn_ref_entries: dict[str, str] = {}

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is True

    def test_null_hash_passes_even_with_mismatched_entries(self) -> None:
        """Even if the catalog has contradictory data, null hash → PASS."""
        assertion_data = {
            "kind": "derived-consequence",
            "upstream_ref_hash": None,
            "eqn_ref_entries": ["E.1"],
        }
        # Catalog has E.1 but we don't check it for derived-consequence.
        eqn_ref_entries = {"E.1": r"X = Y + Z"}

        result = check_divergence_from_dict(assertion_data, eqn_ref_entries)

        assert result.passed is True


class TestNormalizeEqnBodyIntegration:
    """compute_upstream_ref_hash produces consistent results across whitespace variants."""

    def test_whitespace_variants_produce_same_hash(self) -> None:
        """Leading/trailing/internal whitespace stripped before hashing."""
        eq_compact = r"E=mc^2"
        eq_spaced = r"E = mc^2"
        eq_padded = r"  E = mc^2  "
        eq_tabbed = r"E\t=\tmc^2"  # note: \t is literal in raw string → two chars

        hash_compact = compute_upstream_ref_hash(eq_compact)
        hash_spaced = compute_upstream_ref_hash(eq_spaced)
        hash_padded = compute_upstream_ref_hash(eq_padded)

        # All three reduce to the same normalized form (spaces stripped).
        assert hash_compact == hash_spaced
        assert hash_compact == hash_padded

    def test_dfrac_tfrac_canonical_to_frac(self) -> None:
        r"""\\dfrac and \\tfrac both normalize to \\frac before hashing."""
        eq_dfrac = r"\dfrac{a}{b} = c"
        eq_tfrac = r"\tfrac{a}{b} = c"
        eq_frac = r"\frac{a}{b} = c"

        hash_dfrac = compute_upstream_ref_hash(eq_dfrac)
        hash_tfrac = compute_upstream_ref_hash(eq_tfrac)
        hash_frac = compute_upstream_ref_hash(eq_frac)

        assert hash_dfrac == hash_frac
        assert hash_tfrac == hash_frac

    def test_hash_length_is_64_chars(self) -> None:
        """SHA-256 hex digest is always 64 characters."""
        for eq in [r"a = b", r"E = mc^2", r"\int f(x)\,dx = F(x) + C"]:
            assert len(compute_upstream_ref_hash(eq)) == 64

    def test_different_equations_produce_different_hashes(self) -> None:
        """Distinct equations should not collide (regression guard)."""
        eq1 = r"E = mc^2"
        eq2 = r"F = ma"
        eq3 = r"\nabla^2 \phi = 0"

        hashes = {compute_upstream_ref_hash(eq) for eq in [eq1, eq2, eq3]}
        assert len(hashes) == 3  # all distinct

    def test_normalize_eqn_body_integration_round_trip(self) -> None:
        """compute_upstream_ref_hash is sha256 of normalize_eqn_body output."""
        canonical = r"\frac{1}{2} m v^2 + mgh = E"
        expected = hashlib.sha256(normalize_eqn_body(canonical).encode("utf-8")).hexdigest()
        actual = compute_upstream_ref_hash(canonical)
        assert actual == expected

    def test_spacing_macro_variants_produce_same_hash(self) -> None:
        r"""Spacing macros \\, \\! etc. stripped before hashing."""
        eq_with_spacing = r"f\,g"
        eq_without_spacing = r"fg"

        hash_with = compute_upstream_ref_hash(eq_with_spacing)
        hash_without = compute_upstream_ref_hash(eq_without_spacing)

        assert hash_with == hash_without
