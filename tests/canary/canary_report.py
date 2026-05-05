"""Markdown report writer for schema-v2 canary runs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from criteria import CriterionResult, CriterionStatus


def _status_text(result: CriterionResult) -> str:
    return str(result.status.value if hasattr(result.status, "value") else result.status)


def write_canary_report(
    *,
    report_path: Path,
    criteria_results: Iterable[CriterionResult],
    run_failures: list[dict],
    metadata: dict,
    user_overrides: dict[str, str] | None = None,
) -> Path:
    """Write a concise report and return its path."""
    criteria_results = list(criteria_results)
    lines: list[str] = ["# Canary Report", ""]
    lines.extend(["| Criterion | Status | Summary |", "| --- | --- | --- |"])
    for result in criteria_results:
        summary = result.summary.replace("|", "\\|")
        lines.append(f"| {result.name} | {_status_text(result)} | {summary} |")

    lines.extend(["", "## Run Failures", ""])
    if run_failures:
        for failure in run_failures:
            entry = failure.get("entry", {})
            lines.append(
                f"- {failure.get('reason')}: arxiv_id={entry.get('arxiv_id')} "
                f"error_class={entry.get('error_class')} "
                f"n_assertion_errors={entry.get('n_assertion_errors', 0)}"
            )
            for detail in entry.get("failure_details") or []:
                lines.append(f"  - detail: {str(detail).replace(chr(10), ' ')[:500]}")
    else:
        lines.append("- None")

    lines.extend(["", "## Criteria Details", ""])
    for result in criteria_results:
        lines.append(f"### {result.name}")
        lines.append("")
        lines.append(f"- Status: {_status_text(result)}")
        lines.append(f"- Summary: {result.summary}")
        for detail in result.details:
            lines.append(f"- {detail}")
        lines.append("")

    lines.extend(["## User Overrides", ""])
    if user_overrides:
        for key, value in sorted(user_overrides.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- None")

    lines.extend(["", "## Run Metadata", ""])
    for key, value in sorted(metadata.items()):
        lines.append(f"- {key}: {value}")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def status_from_results(
    criteria_results: Iterable[CriterionResult],
    run_failures: list[dict],
    *,
    allow_subset_partial: bool = True,
) -> int:
    """Return process exit code for criteria + dispatch diagnostics."""
    if any(f.get("reason") == "ok_empty_produced_files" for f in run_failures):
        return 2
    if run_failures:
        return 1
    hard_fail = False
    for result in criteria_results:
        status = result.status
        if status in (CriterionStatus.FAIL, CriterionStatus.ERROR):
            hard_fail = True
        if status == CriterionStatus.PARTIAL and not (
            allow_subset_partial
            and result.name
            in {"Coverage", "Consequence closure", "BFSS Typo+Axis Recovery"}
        ):
            hard_fail = True
    return 1 if hard_fail else 0


__all__ = ["write_canary_report", "status_from_results"]
