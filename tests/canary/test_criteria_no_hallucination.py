"""Tests for the §7.4 no-hallucination parser (plan-006 §C8).

Per the plan §Test deltas, this file ships ≥ 3 tests:

1. ``test_pass_all_hashes_verify`` — produced corpus has one kdoc with
   one equation + one restated-equation assertion whose
   ``upstream_ref_hash`` matches; PASS.
2. ``test_fail_hash_mismatch_is_hallucination`` — produced corpus has a
   kdoc with one equation + an assertion whose ``upstream_ref_hash`` is
   the wrong digest (simulated hallucinated restatement); FAIL with the
   mismatched assertion in details.
3. ``test_fail_dangling_parent_in_derivation_sketch`` — produced corpus
   has a derived-consequence assertion citing ``[K-999:K.1]`` in its
   ``derivation_sketch`` but K-999 is not in the produced kdoc set;
   FAIL with the dangling parent in details.

Plus two robustness tests that fall out of the same fixtures cheaply:

4. ``test_empty_assertion_set_is_vacuous_pass`` — produced corpus has
   kdocs but zero assertions; PASS (vacuous).
5. ``test_dangling_knowledge_doc_id_is_fail`` — assertion frontmatter
   cites a knowledge_doc_id that's missing from the produced corpus.

The fixtures use real ``compute_upstream_ref_hash`` digests so the tests
exercise the canonical 4-stage pipeline (no shortcuts).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))

from criteria import CriterionStatus  # noqa: E402
from criteria.no_hallucination import check  # noqa: E402

from gpd.core.assertion_divergence import compute_upstream_ref_hash  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers.
# ---------------------------------------------------------------------------


def _write_kdoc(
    knowledge_dir: Path,
    kdoc_id: str,
    equations: list[tuple[str, str]],
) -> Path:
    """Write a minimal canonical-template kdoc with the given equations.

    Uses the ``(K.N) $eq$`` template form per knowledge.md so
    ``extract_equations_from_kdoc`` finds them. Frontmatter carries
    ``kdoc_id`` so ``_kdoc_id_from_path`` resolves without falling back
    to the filename heuristic.
    """
    body_lines = [
        "---",
        f"kdoc_id: {kdoc_id}",
        "status: Stable",
        "topic: test fixture",
        "---",
        "",
        f"# {kdoc_id} test kdoc",
        "",
        "## Results",
        "",
    ]
    for eq_id, latex in equations:
        body_lines.append(f"({eq_id}) ${latex}$")
        body_lines.append("")
    path = knowledge_dir / f"{kdoc_id}-test.md"
    path.write_text("\n".join(body_lines), encoding="utf-8")
    return path


def _write_assertion(
    assertion_dir: Path,
    assertion_id: str,
    *,
    kind: str,
    knowledge_doc_ids: list[str] | None = None,
    upstream_ref_hash: str | None = None,
    derivation_sketch: str | None = None,
    upstream_status_mirror_kdoc: str | None = None,
) -> Path:
    """Write a minimal assertion doc with controllable frontmatter."""
    fm: list[str] = ["---", f"assertion_id: {assertion_id}", f"kind: {kind}"]
    if knowledge_doc_ids:
        fm.append("knowledge_doc_ids:")
        for kid in knowledge_doc_ids:
            fm.append(f"  - {kid!r}")
    else:
        fm.append("knowledge_doc_ids: []")
    if upstream_ref_hash is None:
        fm.append("upstream_ref_hash: null")
    else:
        fm.append(f"upstream_ref_hash: {upstream_ref_hash}")
    if derivation_sketch is None:
        fm.append("derivation_sketch: null")
    else:
        # Use a YAML literal block to preserve square brackets verbatim.
        fm.append("derivation_sketch: |")
        for line in derivation_sketch.splitlines() or [""]:
            fm.append(f"  {line}")
    fm.append("upstream_status_mirror:")
    fm.append(
        f"  kdoc_id: {upstream_status_mirror_kdoc or 'null'}"
    )
    fm.append("  kdoc_status_at_stable: null")
    fm.append("  divergence_detected_at: null")
    fm.append("---")
    fm.append("")
    fm.append(f"# Assertion {assertion_id}")
    fm.append("")
    if derivation_sketch:
        fm.append("## Derivation Sketch")
        fm.append("")
        fm.append(derivation_sketch)
    path = assertion_dir / f"{assertion_id}-test.md"
    path.write_text("\n".join(fm), encoding="utf-8")
    return path


@pytest.fixture
def sandbox(tmp_path: Path) -> tuple[Path, Path]:
    knowledge_dir = tmp_path / "knowledge"
    assertion_dir = tmp_path / "assertions"
    knowledge_dir.mkdir()
    assertion_dir.mkdir()
    return knowledge_dir, assertion_dir


# ---------------------------------------------------------------------------
# 1. PASS: all hashes verify.
# ---------------------------------------------------------------------------


def test_pass_all_hashes_verify(sandbox: tuple[Path, Path]) -> None:
    knowledge_dir, assertion_dir = sandbox
    eq_latex = r"E = m c^2"
    kdoc_path = _write_kdoc(knowledge_dir, "K-001", [("K.1", eq_latex)])
    correct_hash = compute_upstream_ref_hash(eq_latex)
    assertion_path = _write_assertion(
        assertion_dir,
        "A-001",
        kind="restated-equation",
        knowledge_doc_ids=["K-001"],
        upstream_ref_hash=correct_hash,
        upstream_status_mirror_kdoc="K-001",
    )

    result = check(
        [kdoc_path, assertion_path],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
    )

    assert result.status == CriterionStatus.PASS, result.details
    assert result.passed is True
    assert result.payload["n_assertions"] == 1
    assert result.payload["n_kdocs"] == 1
    assert result.payload["n_issues"] == 0
    assert result.details == []


def test_pass_with_whitespace_normalization(sandbox: tuple[Path, Path]) -> None:
    """Hash matches even when the kdoc body and the canonical form differ
    only by whitespace -- exercises the canonical 4-stage pipeline.
    """
    knowledge_dir, assertion_dir = sandbox
    kdoc_eq = r"S =  \int  \mathcal{L}\, d^4 x"
    canonical = r"S=\int\mathcal{L}d^4x"  # whitespace-stripped
    # Both forms hash identically through normalize_eqn_body.
    assert compute_upstream_ref_hash(kdoc_eq) == compute_upstream_ref_hash(canonical)
    kdoc_path = _write_kdoc(knowledge_dir, "K-002", [("K.1", kdoc_eq)])
    a_path = _write_assertion(
        assertion_dir,
        "A-002",
        kind="restated-equation",
        knowledge_doc_ids=["K-002"],
        upstream_ref_hash=compute_upstream_ref_hash(canonical),
    )
    result = check([kdoc_path, a_path], knowledge_dir, assertion_dir)
    assert result.status == CriterionStatus.PASS, result.details


# ---------------------------------------------------------------------------
# 2. FAIL: hash mismatch ⇒ hallucination.
# ---------------------------------------------------------------------------


def test_fail_hash_mismatch_is_hallucination(sandbox: tuple[Path, Path]) -> None:
    knowledge_dir, assertion_dir = sandbox
    # Kdoc claims E = m c^2.
    kdoc_path = _write_kdoc(knowledge_dir, "K-001", [("K.1", r"E = m c^2")])
    # Assertion's stored hash is for a *different* equation -- the digester
    # hallucinated a restated form that does not actually appear in any kdoc.
    bogus_hash = compute_upstream_ref_hash(r"F = m a")
    a_path = _write_assertion(
        assertion_dir,
        "A-001",
        kind="restated-equation",
        knowledge_doc_ids=["K-001"],
        upstream_ref_hash=bogus_hash,
    )

    result = check([kdoc_path, a_path], knowledge_dir, assertion_dir)

    assert result.status == CriterionStatus.FAIL
    assert result.passed is False
    assert result.payload["n_issues"] >= 1
    joined = " ".join(result.details)
    assert "A-001" in joined
    assert "hallucinated restatement" in joined
    # The summary names the criterion and counts.
    assert "hallucination" in result.summary.lower() or "ref" in result.summary.lower()


# ---------------------------------------------------------------------------
# 3. FAIL: dangling parent reference in derivation_sketch.
# ---------------------------------------------------------------------------


def test_fail_dangling_parent_in_derivation_sketch(
    sandbox: tuple[Path, Path],
) -> None:
    knowledge_dir, assertion_dir = sandbox
    # Produced corpus has K-001 only -- but the derivation cites K-999.
    kdoc_path = _write_kdoc(knowledge_dir, "K-001", [("K.1", r"E = m c^2")])
    sketch = "By [K-001:K.1] and [K-999:K.1], we derive the consequence."
    a_path = _write_assertion(
        assertion_dir,
        "A-007",
        kind="derived-consequence",
        knowledge_doc_ids=["K-001"],
        upstream_ref_hash=None,
        derivation_sketch=sketch,
    )

    result = check([kdoc_path, a_path], knowledge_dir, assertion_dir)

    assert result.status == CriterionStatus.FAIL
    assert result.passed is False
    joined = " ".join(result.details)
    assert "A-007" in joined
    assert "K-999" in joined
    assert "dangling parent" in joined


# ---------------------------------------------------------------------------
# 4. PASS: empty assertion set (vacuous).
# ---------------------------------------------------------------------------


def test_empty_assertion_set_is_vacuous_pass(sandbox: tuple[Path, Path]) -> None:
    knowledge_dir, assertion_dir = sandbox
    kdoc_path = _write_kdoc(knowledge_dir, "K-001", [("K.1", r"E = m c^2")])
    result = check([kdoc_path], knowledge_dir, assertion_dir)
    assert result.status == CriterionStatus.PASS
    assert result.payload["n_assertions"] == 0
    assert "vacuous" in result.summary.lower() or "0 assertions" in result.summary


# ---------------------------------------------------------------------------
# 5. FAIL: dangling knowledge_doc_id in frontmatter.
# ---------------------------------------------------------------------------


def test_fail_dangling_knowledge_doc_id(sandbox: tuple[Path, Path]) -> None:
    knowledge_dir, assertion_dir = sandbox
    # No kdocs produced at all.
    a_path = _write_assertion(
        assertion_dir,
        "A-042",
        kind="derived-consequence",
        knowledge_doc_ids=["K-404"],
        upstream_ref_hash=None,
        derivation_sketch="A claim that depends on a kdoc not in the corpus.",
    )
    result = check([a_path], knowledge_dir, assertion_dir)
    assert result.status == CriterionStatus.FAIL
    joined = " ".join(result.details)
    assert "A-042" in joined
    assert "K-404" in joined
    assert "dangling parent" in joined
