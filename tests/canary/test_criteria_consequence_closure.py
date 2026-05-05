"""Tests for ``tests/canary/criteria/consequence_closure.py`` (plan-006 §C6).

Coverage
--------

Per plan-006 §Test deltas (C6 +3 consequence-closure tests) and §C6 +
brief 002 §7.2:

1. **Closed derivation → PASS.** A kdoc states ``Combining (K.1) and
   (K.2), {claim}``; the assertion sandbox carries a
   ``kind: derived-consequence`` doc whose ``derivation_sketch`` cites
   both parents in canonical ``[K-NNN:K.X]`` form.
2. **Open derivation → FAIL.** A kdoc states a derivation but the
   assertion sandbox has no ``derived-consequence`` assertion that
   cites both parents (the WARN-fallback was DROPPED per iter-1-M5;
   misclassifications surface as hard FAIL).
3. **Empty corpus → PASS.** A run with no produced kdocs (e.g., a
   dry-run) closes vacuously per the plan §C6 wording — "every
   derivation closes" is true when there are no derivations to scan.

Plus a few targeted tests for the regex tolerance described in §C6
(``By X``, ``From X``, ``Combining X and Y``, and the symbolic
``X ∧ Y ⇒`` form) so future regex tightening on real corpora has a
fixture-level safety net.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make ``tests.canary.criteria.consequence_closure`` importable in both
# the canonical ``tests.canary.*`` package layout and a flat ad-hoc
# layout (some CI invocations chdir into ``tests/canary/`` before
# collecting). Mirrors the pattern in ``test_dispatch_skill.py``.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.canary.criteria import CriterionStatus  # noqa: E402
from tests.canary.criteria.consequence_closure import check  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_kdoc(
    knowledge_dir: Path,
    kdoc_id: str,
    *,
    body: str,
    status: str = "Stable",
) -> Path:
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{kdoc_id}-fixture.md"
    path.write_text(
        f"""---
kdoc_id: {kdoc_id}
status: {status}
topic: "fixture"
---

{body}
""",
        encoding="utf-8",
    )
    return path


def _write_assertion(
    assertion_dir: Path,
    assertion_id: str,
    *,
    cited_parents: list[str],
    kind: str = "derived-consequence",
    status: str = "Stable",
) -> Path:
    assertion_dir.mkdir(parents=True, exist_ok=True)
    cite_block = " ".join(cited_parents)
    sketch = (
        f"Combining {cite_block}, the consequence follows by direct\n"
        f"substitution into the convention-locked frame.\n"
    )
    path = assertion_dir / f"{assertion_id}-fixture.md"
    path.write_text(
        f"""---
assertion_id: {assertion_id}
kind: {kind}
status: {status}
topic: "fixture"
---

# Assertion: fixture

## Restated Equation or Derived Claim

$X = 0$

## Regime of Validity

Test fixture only.

## Derivation Sketch

{sketch}
""",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_closed_derivation_passes(tmp_path: Path) -> None:
    """A kdoc derivation cited in a derived-consequence assertion → PASS."""
    knowledge_dir = tmp_path / "knowledge"
    assertion_dir = tmp_path / "assertions"

    _write_kdoc(
        knowledge_dir,
        "K-001",
        body=(
            "## Key Results\n\n"
            "Combining (K.1) and (K.2), the bound ⟨tr X²⟩ ≥ 0.2936 follows.\n"
        ),
    )
    _write_assertion(
        assertion_dir,
        "A-001",
        cited_parents=["[K-001:K.1]", "[K-001:K.2]"],
    )

    result = check(None, knowledge_dir, assertion_dir)

    assert result.status == CriterionStatus.PASS, result.details
    assert result.payload["derivations_found"] >= 1
    assert result.payload["closed"] == result.payload["derivations_found"]


def test_open_derivation_fails(tmp_path: Path) -> None:
    """Derivation with no matching consequence assertion → FAIL.

    Per plan-006 §C6 (post-iter-1-M5 fix): no WARN-downgrade fallback.
    Misclassifications either resolve via ``--user-override`` (out of
    scope for this parser) or escalate as ESCALATE-UNRESOLVED — both
    paths surface as a hard FAIL here.
    """
    knowledge_dir = tmp_path / "knowledge"
    assertion_dir = tmp_path / "assertions"

    _write_kdoc(
        knowledge_dir,
        "K-007",
        body=(
            "## Derivation Sketches\n\n"
            "By (K.3), the level-2 virial bound emerges directly.\n"
        ),
    )
    # Intentionally NO derived-consequence assertion is written.
    assertion_dir.mkdir(parents=True, exist_ok=True)

    result = check(None, knowledge_dir, assertion_dir)

    assert result.status == CriterionStatus.FAIL
    # Per brief 002 §7.2, summary must reference the no-sampling rule.
    assert "sampling is not acceptable" in result.summary.lower()
    assert result.details, "FAIL must surface per-derivation diagnostics"
    assert any("K-007" in d for d in result.details)


def test_empty_corpus_passes(tmp_path: Path) -> None:
    """Empty kdoc dir → PASS (vacuous closure per plan §C6 wording)."""
    knowledge_dir = tmp_path / "knowledge"
    assertion_dir = tmp_path / "assertions"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    assertion_dir.mkdir(parents=True, exist_ok=True)

    result = check(None, knowledge_dir, assertion_dir)

    assert result.status == CriterionStatus.PASS
    assert result.payload["derivations_found"] == 0
    assert result.payload["closed"] == 0


# ---------------------------------------------------------------------------
# Regex tolerance — exercised for plan-006 §C6 ``By/From/Combining`` +
# the symbolic-arrow form. Each fixture writes a closed derivation so a
# regex regression that fails to match the phrasing surfaces as a PASS
# with ``derivations_found == 0`` (caught by the assertion below).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrasing",
    [
        "By (K.1), the claim follows.",
        "From [K-002:K.4], the claim follows.",
        "Combining (K.1) and (K.2), the claim follows.",
        "(K.1) ∧ (K.2) ⇒ the claim",
        "(K.1) and (K.2) => the claim",
    ],
)
def test_regex_tolerance(tmp_path: Path, phrasing: str) -> None:
    """Each derivation phrasing matches and closes against an assertion."""
    knowledge_dir = tmp_path / "knowledge"
    assertion_dir = tmp_path / "assertions"

    _write_kdoc(
        knowledge_dir,
        "K-001",
        body=f"## Derivation Sketches\n\n{phrasing}\n",
    )
    # The derivation might cite K-001 (bare K.1/K.2 rebound to K-001),
    # K-002, or both. Cite the union of canonical forms so the test
    # passes regardless of whether the host kdoc is K-001 or K-002.
    _write_assertion(
        assertion_dir,
        "A-001",
        cited_parents=[
            "[K-001:K.1]",
            "[K-001:K.2]",
            "[K-001:K.4]",
            "[K-002:K.4]",
        ],
    )

    result = check(None, knowledge_dir, assertion_dir)

    assert result.payload["derivations_found"] >= 1, (
        f"phrasing not recognised: {phrasing!r}"
    )
    assert result.status == CriterionStatus.PASS, result.details


def test_definition_phrasing_does_not_falsely_match(tmp_path: Path) -> None:
    """Plain prose without an introducer must not trip the derivation regex.

    Per brief 002 §7.2, a definition is not a derivation; the regex
    must not match a paragraph that lacks a ``By/From/Combining/⇒``
    introducer even when it mentions ``K.1`` and ``K.2`` in passing.
    """
    knowledge_dir = tmp_path / "knowledge"
    assertion_dir = tmp_path / "assertions"
    assertion_dir.mkdir(parents=True, exist_ok=True)

    _write_kdoc(
        knowledge_dir,
        "K-005",
        body=(
            "## Equations\n\n"
            "Equations (K.1) and (K.2) are the BFSS Hamiltonian and the\n"
            "fermion bilinear, respectively.\n"
        ),
    )

    result = check(None, knowledge_dir, assertion_dir)

    # No derivation introducer → vacuous PASS, NOT FAIL.
    assert result.status == CriterionStatus.PASS
    assert result.payload["derivations_found"] == 0
