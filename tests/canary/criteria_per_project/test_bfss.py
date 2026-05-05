"""Tests for the BFSS §7.3 typo+axis recovery parser (plan-006 §C7).

Four tests:

1. PASS fixture — all 16 axes referenced + 10 CONFIRMED typos
   annotated + γ¹⁰ BLOCKING flagged → ``CriterionStatus.PASS``.
2. FAIL on missing CONFIRMED typo — one of T-001..T-016 dropped
   from the produced kdoc → ``FAIL``.
3. FAIL on missing γ¹⁰ BLOCKING — produced kdoc discusses Axis 7
   without the ``BLOCKING:`` token → ``FAIL``.
4. Builder produces correct counts (10 CONFIRMED + 2 INCONCLUSIVE)
   from the live BFSS knowledge directory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure tests/canary is importable as a package root for relative
# imports inside the criteria_per_project module.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.canary.criteria import CriterionStatus  # noqa: E402
from tests.canary.criteria_per_project import Criterion7Inputs  # noqa: E402
from tests.canary.criteria_per_project.bfss import (  # noqa: E402
    BFSSCriterion7,
    _AXIS_PROBES,
)
from tests.canary.criteria_per_project.build_truth_table import (  # noqa: E402
    build_truth_table,
)


_BFSS_KNOWLEDGE_DIR = Path(
    "D:/Data/Dropbox/PSI/projects/bfss-bootstrap/knowledge"
)


# ---------------------------------------------------------------------------
# Helpers — synthesise minimal kdocs that exercise each axis probe + typo.
# ---------------------------------------------------------------------------


def _confirmed_T_ids() -> list[str]:
    """Return the 10 canonical CONFIRMED T-### ids per Part C §3."""
    return [
        "T-001", "T-002", "T-003", "T-004",
        "T-006", "T-009", "T-010",
        "T-013", "T-015", "T-016",
    ]


def _make_pass_kdoc_text() -> str:
    """One kdoc that references every axis probe + every CONFIRMED T-###.

    Includes the γ¹⁰ ``BLOCKING:`` token in proximity to a γ^{10}
    probe so the strict ``_gamma10_aware_blocking`` check passes.
    """
    parts: list[str] = ["---", "kdoc_id: K-999", "status: Stable", "---", ""]
    parts.append("# BFSS Convention Lock — synthesised PASS fixture")
    parts.append("")
    # One paragraph per axis, embedding at least one probe per axis.
    for axis_id, probes in sorted(_AXIS_PROBES.items()):
        probe = probes[0]
        parts.append(f"## Axis {axis_id}")
        parts.append(f"Discusses {probe} per Part A §1 row {axis_id}.")
        if axis_id == 7:
            parts.append("BLOCKING: YES (γ^{10} Euclidean hermiticity).")
        parts.append("")
    # Annotate all 10 CONFIRMED typos.
    parts.append("## Typo annotations")
    for tid in _confirmed_T_ids():
        parts.append(f"- {tid}: CONFIRMED — see Part C §3 for correction.")
    return "\n".join(parts) + "\n"


def _write_kdoc(dirpath: Path, name: str, text: str) -> Path:
    p = dirpath / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture()
def truth_table() -> dict:
    """Truth-table dict synthesised from the live BFSS knowledge dir."""
    if not _BFSS_KNOWLEDGE_DIR.is_dir():
        pytest.skip(f"BFSS knowledge dir not present at {_BFSS_KNOWLEDGE_DIR}")
    return build_truth_table(_BFSS_KNOWLEDGE_DIR)


# ---------------------------------------------------------------------------
# 1. PASS fixture.
# ---------------------------------------------------------------------------


def test_pass_fixture_returns_pass_status(
    tmp_path: Path,
    truth_table: dict,
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    assertion_dir = tmp_path / "assertions"
    assertion_dir.mkdir()
    kdoc = _write_kdoc(knowledge_dir, "K-999-pass.md", _make_pass_kdoc_text())

    result = BFSSCriterion7().check(
        Criterion7Inputs(
            produced_files=[kdoc],
            knowledge_dir=knowledge_dir,
            assertion_dir=assertion_dir,
            truth_table=truth_table,
        )
    )

    assert result.status == CriterionStatus.PASS, (
        f"Expected PASS; got {result.status}: {result.summary}\n"
        f"details: {result.details}"
    )
    assert result.payload["axes_total"] == 16
    assert result.payload["typos_confirmed_total"] == 10
    assert result.payload["axes_missing"] == []
    assert result.payload["typos_confirmed_missing"] == []
    assert result.payload["typos_not_typo_over_claims"] == []
    assert result.payload["blocking_kdocs"], "expected at least one BLOCKING kdoc"


# ---------------------------------------------------------------------------
# 2. FAIL on missing CONFIRMED typo.
# ---------------------------------------------------------------------------


def test_fails_when_confirmed_typo_missing(
    tmp_path: Path,
    truth_table: dict,
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    assertion_dir = tmp_path / "assertions"
    assertion_dir.mkdir()

    # Drop T-001 from the typo annotations section.
    pass_text = _make_pass_kdoc_text()
    bad_text = pass_text.replace(
        "- T-001: CONFIRMED — see Part C §3 for correction.\n",
        "",
    )
    assert "T-001" not in bad_text, "test setup: T-001 should be removed"
    kdoc = _write_kdoc(knowledge_dir, "K-998-missing-T001.md", bad_text)

    result = BFSSCriterion7().check(
        Criterion7Inputs(
            produced_files=[kdoc],
            knowledge_dir=knowledge_dir,
            assertion_dir=assertion_dir,
            truth_table=truth_table,
        )
    )

    assert result.status == CriterionStatus.FAIL
    missing_ids = {
        e["T_id"] for e in result.payload["typos_confirmed_missing"]
    }
    assert "T-001" in missing_ids, (
        f"Expected T-001 in typos_confirmed_missing; got {missing_ids}"
    )


# ---------------------------------------------------------------------------
# 3. FAIL on missing γ¹⁰ BLOCKING.
# ---------------------------------------------------------------------------


def test_fails_when_gamma10_blocking_absent(
    tmp_path: Path,
    truth_table: dict,
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    assertion_dir = tmp_path / "assertions"
    assertion_dir.mkdir()

    # Strip the BLOCKING token; everything else stays.
    pass_text = _make_pass_kdoc_text()
    bad_text = pass_text.replace("BLOCKING: YES", "blocking flag dropped")
    assert "BLOCKING" not in bad_text.upper().replace("BLOCKING FLAG DROPPED", "")
    kdoc = _write_kdoc(
        knowledge_dir, "K-997-no-blocking.md", bad_text
    )

    result = BFSSCriterion7().check(
        Criterion7Inputs(
            produced_files=[kdoc],
            knowledge_dir=knowledge_dir,
            assertion_dir=assertion_dir,
            truth_table=truth_table,
        )
    )

    assert result.status == CriterionStatus.FAIL
    assert result.payload["blocking_kdocs"] == [], (
        "Expected no BLOCKING kdocs when token is removed"
    )
    assert any(
        "blocking-missing" in d for d in result.details
    ), f"Expected blocking-missing detail; got {result.details}"


# ---------------------------------------------------------------------------
# 4. Builder produces correct counts.
# ---------------------------------------------------------------------------


def test_truth_table_builder_counts() -> None:
    if not _BFSS_KNOWLEDGE_DIR.is_dir():
        pytest.skip(f"BFSS knowledge dir not present at {_BFSS_KNOWLEDGE_DIR}")
    table = build_truth_table(_BFSS_KNOWLEDGE_DIR)

    assert len(table["axes"]) == 16, (
        f"Expected 16 axes; got {len(table['axes'])}"
    )
    assert len(table["typos_confirmed"]) == 10, (
        f"Expected 10 CONFIRMED typos; got {len(table['typos_confirmed'])}"
    )
    assert len(table["typos_inconclusive"]) == 2, (
        f"Expected 2 INCONCLUSIVE typos; got {len(table['typos_inconclusive'])}"
    )

    # γ^{10} Axis 7 must be the lone BLOCKING axis.
    blocking_ids = [a["id"] for a in table["axes"] if a["BLOCKING"]]
    assert blocking_ids == [7], f"Expected BLOCKING==[7]; got {blocking_ids}"

    # Spot-check canonical T-ids.
    confirmed_ids = sorted(e["T_id"] for e in table["typos_confirmed"])
    assert confirmed_ids == sorted(_confirmed_T_ids())
    inconclusive_ids = sorted(e["T_id"] for e in table["typos_inconclusive"])
    assert inconclusive_ids == ["T-005", "T-014"]

    # Round-trip through JSON to ensure the schema is serialisable.
    blob = json.dumps(table)
    assert json.loads(blob) == table
