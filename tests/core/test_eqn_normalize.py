"""Tests for gpd.core.eqn_normalize.

Pipeline stages (a)-(e) coverage plus the multi-index-symmetry skip guard.
Fixture at ``tests/fixtures/eqn_normalize_equivalences.json`` carries >= 10
equivalent pairs and explicit non-equivalent pairs documenting the skipped
canonicalizations (multi-index symmetry; single-letter case preservation).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from gpd.core.eqn_normalize import normalize_eqn_body

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "eqn_normalize_equivalences.json"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestDeterminism:
    def test_idempotent(self) -> None:
        s = r"\dfrac{a + b}{c} \, + \left( d \right)"
        once = normalize_eqn_body(s)
        twice = normalize_eqn_body(once)
        assert once == twice

    def test_non_string_input_raises(self) -> None:
        with pytest.raises(TypeError):
            normalize_eqn_body(42)  # type: ignore[arg-type]

    def test_hashable_output(self) -> None:
        out = normalize_eqn_body(r"a + b")
        # sha256 must accept the output without raising.
        h = hashlib.sha256(out.encode("utf-8")).hexdigest()
        assert len(h) == 64


class TestPipelineStages:
    """Cover every named pipeline stage (a)-(e) from brief 002 §3.4.1."""

    def test_stage_a_whitespace_and_spacing_macros(self) -> None:
        assert normalize_eqn_body(r"a \, + \; b") == normalize_eqn_body("a+b")

    def test_stage_a_unicode_whitespace(self) -> None:
        assert normalize_eqn_body("a\u00a0+\u2009b") == normalize_eqn_body("a+b")

    def test_stage_b_dfrac_and_tfrac(self) -> None:
        assert normalize_eqn_body(r"\dfrac{a}{b}") == normalize_eqn_body(r"\frac{a}{b}")
        assert normalize_eqn_body(r"\tfrac{a}{b}") == normalize_eqn_body(r"\frac{a}{b}")

    def test_stage_b_left_right_paren_strip(self) -> None:
        assert normalize_eqn_body(r"\left( a + b \right)") == normalize_eqn_body("(a+b)")

    def test_stage_b_mathop_rm_to_mathrm(self) -> None:
        assert normalize_eqn_body(r"\mathop{\rm tr}(X)") == normalize_eqn_body(r"\mathrm{tr}(X)")

    def test_stage_c_font_wrapper_lowering_multi_letter(self) -> None:
        assert normalize_eqn_body(r"\mathbf{tr}(X)") == normalize_eqn_body(r"\mathrm{tr}(X)")
        assert normalize_eqn_body(r"\mathit{det}(A)") == normalize_eqn_body(r"\mathrm{det}(A)")
        assert normalize_eqn_body(r"\text{Pf}(M)") == normalize_eqn_body(r"\mathrm{Pf}(M)")

    def test_stage_c_single_letter_wrapper_preserved(self) -> None:
        # Case is semantic on single-letter wrappers (brief §3.4.1 (c) note).
        assert normalize_eqn_body(r"\mathbf{X}") != normalize_eqn_body("X")
        assert normalize_eqn_body(r"\mathrm{A}") != normalize_eqn_body("A")

    def test_stage_d_bare_fraction(self) -> None:
        assert normalize_eqn_body("a/b") == normalize_eqn_body(r"\frac{a}{b}")
        assert normalize_eqn_body(r"\pi/2") == normalize_eqn_body(r"\frac{\pi}{2}")

    def test_stage_e_case_sensitivity_preserved(self) -> None:
        # Stage (e) is a deliberate no-op: case is NOT folded.
        assert normalize_eqn_body("A") != normalize_eqn_body("a")
        assert normalize_eqn_body(r"\mathbf{X}") != normalize_eqn_body(r"\mathbf{x}")


class TestNoMultiIndexSymmetry:
    """Plan 002 §1 item 5 pick: multi-index symmetry is NOT canonicalized."""

    def test_upper_index_pair_not_reordered(self) -> None:
        assert normalize_eqn_body(r"X^{IJ}") != normalize_eqn_body(r"X^{JI}")

    def test_lower_index_pair_not_reordered(self) -> None:
        assert normalize_eqn_body(r"g_{mu nu}") != normalize_eqn_body(r"g_{nu mu}")

    def test_mixed_index_pair_not_reordered(self) -> None:
        assert normalize_eqn_body(r"T^{AB}_{CD}") != normalize_eqn_body(r"T^{BA}_{CD}")


class TestFixtureRoundtrip:
    """Loop the fixture; assert every pair behaves per its ``stage`` annotation."""

    def test_normalize_eqn_body_determinism(self) -> None:
        fixture = _load_fixture()
        failures: list[str] = []
        for pair in fixture["equivalent_pairs"]:
            left = normalize_eqn_body(pair["left"])
            right = normalize_eqn_body(pair["right"])
            if left != right:
                failures.append(
                    f"stage={pair['stage']!r} name={pair['name']!r}: "
                    f"{pair['left']!r} -> {left!r} vs {pair['right']!r} -> {right!r}"
                )
        assert failures == [], "equivalent pairs normalized to distinct strings:\n" + "\n".join(failures)

    def test_non_equivalent_pairs_stay_distinct(self) -> None:
        fixture = _load_fixture()
        failures: list[str] = []
        for pair in fixture["non_equivalent_pairs"]:
            left = normalize_eqn_body(pair["left"])
            right = normalize_eqn_body(pair["right"])
            if left == right:
                failures.append(
                    f"stage={pair['stage']!r} name={pair['name']!r}: "
                    f"both normalized to {left!r}"
                )
        assert failures == [], "non-equivalent pairs collapsed:\n" + "\n".join(failures)

    def test_fixture_has_at_least_ten_equivalent_pairs(self) -> None:
        fixture = _load_fixture()
        assert len(fixture["equivalent_pairs"]) >= 10

    def test_fixture_covers_every_pipeline_stage(self) -> None:
        fixture = _load_fixture()
        covered = set()
        for pair in fixture["equivalent_pairs"]:
            stage = pair["stage"]
            for part in stage.split("+"):
                covered.add(part.strip())
        # Stages (a), (b), (c), (d) MUST appear; (e) is covered by the
        # non-equivalent pairs (case-sensitivity preserved).
        assert {"a", "b", "c", "d"}.issubset(covered), f"missing stages: {covered!r}"
