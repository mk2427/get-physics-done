"""§7 criteria parsers for the BFSS canary (plan-006 C5..C10).

Each criterion ships as a standalone module under this package
(criteria/coverage.py, criteria/consequence_closure.py, etc.) so that
parallel implementation does not collide on a single file. Shared
types (``CriterionResult``, ``CriterionStatus``) live here.

Per plan-006 §Implementation order, all six modules expose a single
top-level ``check(...)`` function with the signature::

    check(
        produced_files: list[Path],   # cost-log-derived ok set
        knowledge_dir: Path,
        assertion_dir: Path,
        truth_table: dict | None = None,  # only criterion 3 uses this
    ) -> CriterionResult

The canary driver loads criteria modules via the ``--criteria-module``
CLI flag (default: this package's project-agnostic six). Per-project
criteria (e.g., BFSS-specific §7.3 typo+axis) live under
``criteria_per_project/`` instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CriterionStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class CriterionResult:
    """Outcome of a single §7 criterion check.

    Fields
    ------
    name:
        Human-readable criterion name (e.g., "Coverage", "Traceability").
    status:
        One of the ``CriterionStatus`` values.
    summary:
        One-line summary suitable for the canary report's status table.
    details:
        Free-form list of diagnostic strings (per-paper failures, etc.).
        Surfaced verbatim in the canary report's per-criterion section.
    payload:
        Optional structured data for downstream tooling (e.g., the list
        of uncovered ``(kdoc_id, eq_id)`` pairs for criterion 1).
    """

    name: str
    status: CriterionStatus
    summary: str
    details: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == CriterionStatus.PASS


__all__ = ["CriterionResult", "CriterionStatus"]
