"""Minimal in-process harness for the adversarial-review workflow pre-oracle step.

Plan 005 commit c3 / iter-1-M2 fixer: the end-to-end tests MUST drive
the workflow `<step name="pre_oracle">` primitive — not a direct call
to `run_pre_oracle` — so a future developer deleting the workflow
step causes a test failure rather than an untested regression.

Strategy:

1. **Spec presence guard**. Every harness invocation re-reads
   `src/gpd/specs/workflows/adversarial-review.md` and asserts the
   `<step name="pre_oracle">` block is present and mentions the
   load-bearing contract lines (gate on `pre_oracle: true` AND
   `artifact_kind == "knowledge"`, `R0-REVIEW.md` output, fail-open
   `ORACLE-DISPATCH-FAIL` W-finding). If the block disappears from
   the spec the harness raises `WorkflowSpecDrift`.

2. **Prose-derived executor**. `run_pre_oracle_workflow_step` is a
   Python translation of the spec's step body prose (preflight →
   extract → try/dispatch/aggregate/except/finally → write). It is
   the SAME control flow the spec prescribes; the spec guard above
   ensures the prose stays authoritative.

3. **Mock dispatch surface**. Tests monkey-patch
   `gpd.core.sympy_oracle.dispatch_sympy_calculator` directly (the
   step body calls it transitively via `_run_sympy_check`).
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

from gpd.core import sympy_oracle as oracle_mod
from gpd.core.sympy_oracle import (
    OracleResult,
    _run_sympy_check,
    extract_equations_from_kdoc,
)

_WORKFLOW_SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "gpd"
    / "specs"
    / "workflows"
    / "adversarial-review.md"
)

_REQUIRED_SPEC_TOKENS = (
    '<step name="pre_oracle">',
    "pre_oracle: true",
    'artifact_kind == "knowledge"',
    "R0-REVIEW.md",
    "ORACLE-DISPATCH-FAIL",
    "safe_write_r0_review",
)


class WorkflowSpecDrift(AssertionError):
    """Raised when the workflow spec's pre_oracle step body loses a
    load-bearing token; blocks the harness so a silent spec deletion
    does not cause tests to green-wash.
    """


def _assert_workflow_spec_has_pre_oracle_step() -> None:
    """Re-read the workflow spec and guard the pre_oracle step body
    against accidental deletion / substantive edits.
    """

    if not _WORKFLOW_SPEC_PATH.exists():
        raise WorkflowSpecDrift(
            f"Workflow spec missing at {_WORKFLOW_SPEC_PATH}; "
            "plan 005 c3 regressed."
        )
    text = _WORKFLOW_SPEC_PATH.read_text(encoding="utf-8")
    missing = [tok for tok in _REQUIRED_SPEC_TOKENS if tok not in text]
    if missing:
        raise WorkflowSpecDrift(
            "Workflow spec's pre_oracle step is missing required "
            f"load-bearing tokens: {missing!r}. Plan 005 c3 has "
            "regressed — restore the <step name=\"pre_oracle\"> block."
        )


def _render_r0_review(
    target_slug: str,
    results: dict[str, OracleResult],
    *,
    partial: bool,
    dispatch_error: str | None,
) -> str:
    """Render the round-0 review markdown per plan 005 §Q3/§file 3."""

    lines: list[str] = []
    lines.append(f"# R0-REVIEW — {target_slug}")
    lines.append("")
    lines.append("Round-0 SymPy pre-oracle results.")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    for eq_id, r in results.items():
        if r.verdict == "verified":
            lines.append(f"### [N] ORACLE-VERIFIED-{eq_id}")
            lines.append(f"- source: sympy_oracle")
            lines.append(f"- verdict: verified")
            lines.append(f"- blocking: false")
            lines.append(f"- location: {eq_id}")
            lines.append(f"- equation_body: {r.latex}")
            lines.append(f"- output: {r.output}")
            lines.append("")
        elif r.verdict == "falsified":
            lines.append(f"### [S] ORACLE-FALSIFIED-{eq_id}")
            lines.append(f"- source: sympy_oracle")
            lines.append(f"- verdict: falsified")
            lines.append(f"- blocking: true")
            lines.append(f"- kind: oracle_falsified")
            lines.append(f"- location: {eq_id}")
            lines.append(f"- equation_body: {r.latex}")
            lines.append(f"- Evidence: {r.output}")
            lines.append("")
        else:  # unevaluated — informational only, no finding emitted
            lines.append(f"<!-- unevaluated: {eq_id}: {r.output} -->")
    if partial:
        lines.append("### [W] ORACLE-DISPATCH-FAIL")
        lines.append("- source: sympy_oracle")
        lines.append(f"- kind: oracle_dispatch_fail")
        lines.append(f"- blocking: false")
        lines.append(f"- Problem: {dispatch_error or 'dispatch failed'}")
        lines.append("")
    return "\n".join(lines) + "\n"


def safe_write_r0_review(
    review_dir: Path,
    target_slug: str,
    results: dict[str, OracleResult],
    *,
    partial: bool,
    dispatch_error: str | None,
) -> Path:
    """Atomically write `R0-REVIEW.md` per plan 005 §file 3 iter-2-S1.

    `tmp.write_text(body); tmp.replace(final)` — no partial file ever
    appears on disk. Idempotent-by-guard: re-invocations overwrite the
    same final path atomically, so the try/except/finally pattern in
    the workflow step body never produces a double-flush race.
    """

    review_dir.mkdir(parents=True, exist_ok=True)
    final_path = review_dir / "R0-REVIEW.md"
    tmp_path = review_dir / "R0-REVIEW.md.tmp"
    body = _render_r0_review(
        target_slug, results, partial=partial, dispatch_error=dispatch_error
    )
    tmp_path.write_text(body, encoding="utf-8")
    tmp_path.replace(final_path)
    return final_path


def _preflight_sympy_import() -> bool:
    """Plan 005 §file 3 preflight: `py -c "import sympy"` success."""
    try:
        import sympy  # noqa: F401
    except ImportError:
        return False
    return True


def run_pre_oracle_workflow_step(
    target_path: Path,
    target_slug: str,
    review_dir: Path,
    *,
    pre_oracle: bool,
    artifact_kind: str,
    python_path: str | None = None,
) -> dict[str, OracleResult] | None:
    """Execute the `<step name="pre_oracle">` workflow step in-process.

    Returns the accumulated `results` dict so tests can assert on the
    in-memory state AND on the disk artifact. Returns `None` when the
    step is a no-op (precondition gate false).

    Raises the captured workflow-level exception after flushing the
    partial `R0-REVIEW.md` (fail-open is an orchestrator-level
    policy; the harness preserves exception fidelity so tests can
    assert on the re-raise).
    """

    _assert_workflow_spec_has_pre_oracle_step()

    # Precondition gate per step body clause 1.
    if not pre_oracle or artifact_kind != "knowledge":
        return None

    # Preflight per step body clause 1.
    if not _preflight_sympy_import():
        safe_write_r0_review(
            review_dir,
            target_slug,
            {},
            partial=True,
            dispatch_error="preflight failed: sympy not importable",
        )
        return {}

    # Extract per step body clause 2.
    equations = extract_equations_from_kdoc(target_path)
    if not equations:
        safe_write_r0_review(
            review_dir, target_slug, {}, partial=False, dispatch_error=None
        )
        return {}

    # Dispatch + Aggregate + Write per step body clause 3.
    results: dict[str, OracleResult] = {}
    py = python_path or sys.executable
    try:
        for eq_id, latex in equations:
            result = _run_sympy_check(latex, py)
            result.equation_id = eq_id
            results[eq_id] = result
        safe_write_r0_review(
            review_dir, target_slug, results, partial=False, dispatch_error=None
        )
    except Exception as exc:
        # Partial-persist then re-raise per iter-2-S1.
        try:
            safe_write_r0_review(
                review_dir, target_slug, results, partial=True, dispatch_error=str(exc)
            )
        finally:
            # Re-raise the ORIGINAL workflow-level exception.
            raise
    return results
