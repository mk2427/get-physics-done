"""Per-project §7 criteria implementations (plan-006 §C7).

Each project (BFSS, future projects) ships its own §7.3 typo+axis
recovery parser under this package. The abstract ``Criterion7`` base
class below pins the contract; concrete implementations subclass and
provide the project-specific ``check()``.

The canary driver loads the per-project module via
``--criteria-module tests.canary.criteria_per_project.<project>``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from tests.canary.criteria import CriterionResult


@dataclass
class Criterion7Inputs:
    """Inputs to the per-project §7.3 criterion.

    Fields
    ------
    produced_files:
        Cost-log-derived list of kdoc paths produced by the canary run
        (only those with ``error_class == "ok"``).
    knowledge_dir:
        Sandbox knowledge directory for this run.
    assertion_dir:
        Sandbox assertion directory.
    truth_table:
        Already-parsed dict of project ground-truth data (axes, typos,
        BLOCKING flags, etc.). Per-project schema; the abstract base
        does not validate it.
    """

    produced_files: list[Path]
    knowledge_dir: Path
    assertion_dir: Path
    truth_table: dict


class Criterion7(ABC):
    """Abstract base class for §7.3 typo+axis recovery parsers.

    Subclasses implement ``check(inputs) -> CriterionResult`` per the
    project's truth-table schema. The canary driver calls
    ``cls().check(inputs)``; subclasses should not require constructor
    args (truth-table loading happens before instantiation).
    """

    name: str = "Typo+Axis Recovery"

    @abstractmethod
    def check(self, inputs: Criterion7Inputs) -> CriterionResult:
        """Run the §7.3 check against the produced corpus.

        Returns
        -------
        CriterionResult
            ``status`` is ``PASS`` only if every required item in the
            truth table is recovered in the produced corpus AND no
            project-specific BLOCKING flag is unflagged. Otherwise
            ``FAIL`` with per-item diagnostics in ``details``.
        """


__all__ = ["Criterion7", "Criterion7Inputs"]
