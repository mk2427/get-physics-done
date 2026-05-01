"""Tests for gpd-eqnref-integrator behavior (brief 002 §Commit 7).

These tests exercise the integrator's core logic — auto-fire guard,
dry-run suppression, and revert — by importing the revlog module and
applying the same guard conditions the agent is specified to implement.
The MCP ``convention_set`` call is mocked via ``unittest.mock.patch``
to avoid real network / file-lock side effects.

Brief 002 §Commit 7 required tests:

1. ``test_auto_fire_on_0000_stable`` — fixture meta-audit marked APPROVED
   (0/0/0/0); with ``fire_conventions=True``, the integrator emits
   ``convention_set`` calls (mock the MCP call). Verify call count =
   number of axes in fixture.
2. ``test_no_fire_on_non_approved`` — fixture meta-audit with 2 open
   findings; even with ``fire_conventions=True``, NO ``convention_set``
   calls emitted.
3. ``test_dry_run_zero_writes`` — ``dry_run=True`` even with APPROVED
   meta-audit; zero MCP calls AND zero writes to
   ``eqn-ref-integrator.jsonl``.
4. ``test_revert_restores_prior_lock`` — seed ``eqn-ref-integrator.jsonl``
   with 2 entries for the same axis (prior/new); ``--revert`` mode calls
   ``convention_set`` with ``prior_value``; verify the correct prior value
   is used.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from gpd.core.eqnref_revlog import eqnref_revlog_append, eqnref_revlog_recent, eqnref_revlog_path

# ─── Helpers — integrator logic under test ────────────────────────────────────
#
# The integrator is a *agent* (gpd-eqnref-integrator.md), not a Python module.
# The tests below therefore implement the integrator's specification as a thin
# Python function ``_run_integrator`` that mirrors the exact guard conditions
# documented in the agent spec. This function IS the unit-under-test: if the
# agent's markdown spec ever gets a Python backing module, these tests will
# serve as the acceptance contract.
#
# ``_run_integrator`` calls ``mock_convention_set`` (a callable injected by
# the test) instead of the real MCP tool so tests are deterministic.
#

_FAKE_CONTENT_HASH = hashlib.sha256(b"canonical_body").hexdigest()
_FAKE_AXIS_A = {
    "axis_id": "metric_signature",
    "mcp_key": "custom:metric-signature",
    "canonical_phase_0F": "mostly-plus",
}
_FAKE_AXIS_B = {
    "axis_id": "trace_normalization",
    "mcp_key": "custom:trace-normalization",
    "canonical_phase_0F": "1/N",
}


def _make_meta_audit_report(
    *,
    verdict: str = "APPROVED",
    severity_s: int = 0,
    severity_m: int = 0,
    severity_w: int = 0,
    severity_n: int = 0,
    open_blocking_findings: list[str] | None = None,
    axes: list[dict] | None = None,
) -> dict:
    """Return a minimal parsed meta-audit report dict for test fixtures."""
    if open_blocking_findings is None:
        open_blocking_findings = []
    if axes is None:
        axes = [_FAKE_AXIS_A, _FAKE_AXIS_B]
    return {
        "verdict": verdict,
        "severity_counts": {
            "S": severity_s,
            "M": severity_m,
            "W": severity_w,
            "N": severity_n,
        },
        "open_blocking_findings": open_blocking_findings,
        "convention_lock_proposals": axes,
    }


def _auto_fire_guard_passes(report: dict, *, fire_conventions: bool, dry_run: bool) -> bool:
    """Return True iff the integrator's auto-fire guard would allow MCP calls.

    Implements the exact conditions from gpd-eqnref-integrator.md
    <auto_fire_guard> section:
    1. fire_conventions is True
    2. dry_run is False
    3. verdict == "APPROVED"
    4. severity_counts all zero
    5. zero open blocking findings
    """
    if not fire_conventions:
        return False
    if dry_run:
        return False
    if report.get("verdict") != "APPROVED":
        return False
    counts = report.get("severity_counts", {})
    if any(counts.get(k, 0) != 0 for k in ("S", "M", "W", "N")):
        return False
    if report.get("open_blocking_findings"):
        return False
    return True


def _run_integrator(
    project_root: Path,
    report: dict,
    *,
    fire_conventions: bool = False,
    dry_run: bool = False,
    revert: bool = False,
    mock_convention_set: Any = None,
) -> dict:
    """Thin Python implementation of gpd-eqnref-integrator spec for testing.

    This function encodes the integrator's core contract:
    - Auto-fire guard (exact 5-condition check)
    - Dry-run suppression (zero MCP calls, zero revlog writes)
    - Revert (reads prior_value from most-recent revlog batch, calls
      convention_set with prior_value)
    - Revlog append (one entry per axis after successful convention_set)

    Returns a result dict analogous to gpd_return.
    """
    if mock_convention_set is None:
        mock_convention_set = MagicMock()

    convention_set_calls_made = 0
    revert_applied = False
    revlog_entries_written = 0
    fire_skipped_reason: str | None = None

    if revert:
        # Revert mode: restore prior convention lock from revlog.
        recent = eqnref_revlog_recent(project_root)
        if not recent:
            return {
                "status": "failed",
                "revert_applied": False,
                "error": "no revlog entries found",
            }
        # Group by the most-recent run_id (last entry's run_id).
        most_recent_run_id = recent[-1]["run_id"]
        batch = [e for e in recent if e["run_id"] == most_recent_run_id]
        for entry in batch:
            prior_value = entry.get("prior_value")
            if prior_value is None:
                continue  # skip axes with no prior value
            mock_convention_set(
                key=entry["mcp_key"],
                value=prior_value,
                force=True,
            )
            convention_set_calls_made += 1
        revert_applied = True
        return {
            "status": "completed",
            "revert_applied": revert_applied,
            "convention_set_calls_made": convention_set_calls_made,
        }

    # Normal EQN-REF generation path.
    axes = report.get("convention_lock_proposals", [])

    if _auto_fire_guard_passes(report, fire_conventions=fire_conventions, dry_run=dry_run):
        run_id = str(uuid.uuid4())
        for axis in axes:
            mock_convention_set(
                key=axis["mcp_key"],
                value=axis["canonical_phase_0F"],
                force=False,
            )
            convention_set_calls_made += 1
            # Append revlog entry (not suppressed in normal mode).
            entry = {
                "run_id": run_id,
                "utc_timestamp": datetime.now(timezone.utc).isoformat(),
                "axis_id": axis["axis_id"],
                "mcp_key": axis["mcp_key"],
                "prior_value": None,
                "new_value": axis["canonical_phase_0F"],
                "eqn_ref_content_hash": _FAKE_CONTENT_HASH,
                "force_used": False,
            }
            eqnref_revlog_append(project_root, entry)
            revlog_entries_written += 1
    else:
        # Determine skip reason for return payload.
        if dry_run:
            fire_skipped_reason = "dry_run"
        elif not fire_conventions:
            fire_skipped_reason = "fire_conventions_not_set"
        elif report.get("verdict") != "APPROVED":
            fire_skipped_reason = "meta_audit_not_approved"
        elif report.get("open_blocking_findings"):
            fire_skipped_reason = "open_blocking_findings"
        else:
            fire_skipped_reason = "severity_counts_nonzero"

    return {
        "status": "completed",
        "convention_set_calls_made": convention_set_calls_made,
        "revlog_entries_written": revlog_entries_written,
        "fire_conventions_skipped_reason": fire_skipped_reason,
        "revert_applied": revert_applied,
        "dry_run_preflight": (
            {
                "axes_count": len(axes),
                "projected_convention_set_calls": len(axes),
                "fire_conventions_would_trigger": _auto_fire_guard_passes(
                    report, fire_conventions=True, dry_run=False
                ),
            }
            if dry_run
            else None
        ),
    }


# ─── Test 1: auto_fire_on_0000_stable ─────────────────────────────────────────


class TestAutoFireOn0000Stable:
    """Brief 002 §Commit 7 Test 1.

    Fixture meta-audit APPROVED (0/0/0/0); fire_conventions=True.
    Verify convention_set is called once per axis.
    """

    def test_fires_convention_set_for_each_axis(self, tmp_path: Path) -> None:
        """APPROVED meta-audit + fire_conventions=True → one call per axis."""
        report = _make_meta_audit_report()  # APPROVED, 2 axes
        mock_cs = MagicMock()

        result = _run_integrator(
            tmp_path, report, fire_conventions=True, mock_convention_set=mock_cs
        )

        assert result["convention_set_calls_made"] == 2
        assert result["fire_conventions_skipped_reason"] is None
        assert mock_cs.call_count == 2

    def test_call_keys_and_values_are_correct(self, tmp_path: Path) -> None:
        """convention_set is called with the correct key + canonical_phase_0F."""
        report = _make_meta_audit_report(axes=[_FAKE_AXIS_A])
        mock_cs = MagicMock()

        _run_integrator(tmp_path, report, fire_conventions=True, mock_convention_set=mock_cs)

        mock_cs.assert_called_once_with(
            key="custom:metric-signature",
            value="mostly-plus",
            force=False,
        )

    def test_revlog_entries_written_after_fire(self, tmp_path: Path) -> None:
        """One revlog entry per axis is written after successful convention_set calls."""
        report = _make_meta_audit_report()  # 2 axes
        result = _run_integrator(tmp_path, report, fire_conventions=True)

        assert result["revlog_entries_written"] == 2
        recent = eqnref_revlog_recent(tmp_path)
        assert len(recent) == 2


# ─── Test 2: no_fire_on_non_approved ──────────────────────────────────────────


class TestNoFireOnNonApproved:
    """Brief 002 §Commit 7 Test 2.

    Meta-audit with 2 open findings; fire_conventions=True.
    Verify NO convention_set calls are made.
    """

    def test_non_approved_verdict_suppresses_all_calls(self, tmp_path: Path) -> None:
        """REVISE verdict → zero convention_set calls regardless of fire_conventions."""
        report = _make_meta_audit_report(
            verdict="REVISE",
            severity_s=1,
            severity_m=1,
            open_blocking_findings=["iter-1-S1", "iter-1-M2"],
        )
        mock_cs = MagicMock()

        result = _run_integrator(
            tmp_path, report, fire_conventions=True, mock_convention_set=mock_cs
        )

        assert result["convention_set_calls_made"] == 0
        assert mock_cs.call_count == 0
        assert result["fire_conventions_skipped_reason"] == "meta_audit_not_approved"

    def test_open_blocking_findings_suppresses_calls(self, tmp_path: Path) -> None:
        """APPROVED verdict but open blocking findings → zero convention_set calls."""
        report = _make_meta_audit_report(
            verdict="APPROVED",  # verdict field says APPROVED but has blocking
            severity_s=0,
            severity_m=0,
            open_blocking_findings=["iter-2-S1"],
        )
        mock_cs = MagicMock()

        result = _run_integrator(
            tmp_path, report, fire_conventions=True, mock_convention_set=mock_cs
        )

        assert result["convention_set_calls_made"] == 0
        assert mock_cs.call_count == 0
        assert result["fire_conventions_skipped_reason"] == "open_blocking_findings"

    def test_nonzero_severity_suppresses_calls(self, tmp_path: Path) -> None:
        """Non-zero severity counts (even W-level) suppress convention_set calls."""
        report = _make_meta_audit_report(
            verdict="APPROVED",
            severity_w=1,  # W-level finding present
        )
        mock_cs = MagicMock()

        result = _run_integrator(
            tmp_path, report, fire_conventions=True, mock_convention_set=mock_cs
        )

        assert result["convention_set_calls_made"] == 0
        assert mock_cs.call_count == 0


# ─── Test 3: dry_run_zero_writes ──────────────────────────────────────────────


class TestDryRunZeroWrites:
    """Brief 002 §Commit 7 Test 3.

    dry_run=True even with APPROVED meta-audit; zero MCP calls AND zero
    writes to eqn-ref-integrator.jsonl.
    """

    def test_dry_run_makes_no_mcp_calls(self, tmp_path: Path) -> None:
        """dry_run=True → zero convention_set calls even on APPROVED meta-audit."""
        report = _make_meta_audit_report()  # APPROVED
        mock_cs = MagicMock()

        result = _run_integrator(
            tmp_path,
            report,
            fire_conventions=True,
            dry_run=True,
            mock_convention_set=mock_cs,
        )

        assert result["convention_set_calls_made"] == 0
        assert mock_cs.call_count == 0
        assert result["fire_conventions_skipped_reason"] == "dry_run"

    def test_dry_run_writes_no_revlog_entries(self, tmp_path: Path) -> None:
        """dry_run=True → zero entries written to eqn-ref-integrator.jsonl."""
        report = _make_meta_audit_report()  # APPROVED
        _run_integrator(tmp_path, report, fire_conventions=True, dry_run=True)

        revlog = eqnref_revlog_path(tmp_path)
        assert not revlog.exists(), "revlog must not be created in dry-run mode"

    def test_dry_run_preflight_summary_in_result(self, tmp_path: Path) -> None:
        """dry_run=True → preflight summary present in result."""
        report = _make_meta_audit_report()  # 2 axes, APPROVED
        result = _run_integrator(tmp_path, report, dry_run=True)

        preflight = result.get("dry_run_preflight")
        assert preflight is not None
        assert preflight["axes_count"] == 2
        assert preflight["projected_convention_set_calls"] == 2

    def test_dry_run_preflight_fire_would_trigger_true_on_approved(
        self, tmp_path: Path
    ) -> None:
        """fire_conventions_would_trigger=True when meta-audit is APPROVED."""
        report = _make_meta_audit_report()  # APPROVED
        result = _run_integrator(tmp_path, report, dry_run=True, fire_conventions=True)

        preflight = result["dry_run_preflight"]
        assert preflight["fire_conventions_would_trigger"] is True

    def test_dry_run_preflight_fire_would_trigger_false_on_non_approved(
        self, tmp_path: Path
    ) -> None:
        """fire_conventions_would_trigger=False when meta-audit is not APPROVED."""
        report = _make_meta_audit_report(verdict="REVISE", severity_s=1)
        result = _run_integrator(tmp_path, report, dry_run=True, fire_conventions=True)

        preflight = result["dry_run_preflight"]
        assert preflight["fire_conventions_would_trigger"] is False


# ─── Test 4: revert_restores_prior_lock ───────────────────────────────────────


class TestRevertRestoresPriorLock:
    """Brief 002 §Commit 7 Test 4.

    Seed eqn-ref-integrator.jsonl with 2 entries for the same axis
    (old run = prior_value; new run = new_value). revert mode calls
    convention_set with prior_value; verify the correct prior value is used.
    """

    def _seed_revlog(self, project_root: Path) -> None:
        """Write two revlog entries for axis 'metric_signature' from the same run."""
        run_id = "run-original-abc"
        entries = [
            {
                "run_id": run_id,
                "utc_timestamp": "2026-04-21T10:00:00+00:00",
                "axis_id": "metric_signature",
                "mcp_key": "custom:metric-signature",
                "prior_value": "all-plus",   # this is the value to restore
                "new_value": "mostly-plus",  # this is what was set
                "eqn_ref_content_hash": _FAKE_CONTENT_HASH,
                "force_used": False,
            },
            {
                "run_id": run_id,
                "utc_timestamp": "2026-04-21T10:00:01+00:00",
                "axis_id": "trace_normalization",
                "mcp_key": "custom:trace-normalization",
                "prior_value": None,  # was the first-ever set; no prior
                "new_value": "1/N",
                "eqn_ref_content_hash": _FAKE_CONTENT_HASH,
                "force_used": False,
            },
        ]
        for e in entries:
            eqnref_revlog_append(project_root, e)

    def test_revert_calls_convention_set_with_prior_value(
        self, tmp_path: Path
    ) -> None:
        """--revert reads prior_value and calls convention_set with it."""
        self._seed_revlog(tmp_path)
        mock_cs = MagicMock()

        # We pass an empty report because revert mode doesn't use the report.
        result = _run_integrator(
            tmp_path,
            {},
            revert=True,
            mock_convention_set=mock_cs,
        )

        assert result["revert_applied"] is True
        # Only 1 call made: the axis with prior_value=None is skipped.
        assert result["convention_set_calls_made"] == 1
        mock_cs.assert_called_once_with(
            key="custom:metric-signature",
            value="all-plus",  # prior_value field
            force=True,
        )

    def test_revert_skips_null_prior_value(self, tmp_path: Path) -> None:
        """Axes with prior_value=null are skipped in revert mode."""
        self._seed_revlog(tmp_path)
        mock_cs = MagicMock()

        _run_integrator(tmp_path, {}, revert=True, mock_convention_set=mock_cs)

        # Verify that 'custom:trace-normalization' (prior_value=None) was NOT called.
        called_keys = [c.kwargs.get("key") or c.args[0] for c in mock_cs.call_args_list]
        assert "custom:trace-normalization" not in called_keys

    def test_revert_uses_most_recent_run_id_batch(self, tmp_path: Path) -> None:
        """revert targets the most recent run_id batch, not an older run."""
        # Seed an older run first.
        old_entry = {
            "run_id": "run-old",
            "utc_timestamp": "2026-04-20T00:00:00+00:00",
            "axis_id": "metric_signature",
            "mcp_key": "custom:metric-signature",
            "prior_value": "very-old-value",
            "new_value": "intermediate-value",
            "eqn_ref_content_hash": _FAKE_CONTENT_HASH,
            "force_used": False,
        }
        eqnref_revlog_append(tmp_path, old_entry)

        # Seed the newer run.
        self._seed_revlog(tmp_path)
        mock_cs = MagicMock()

        _run_integrator(tmp_path, {}, revert=True, mock_convention_set=mock_cs)

        # Should restore "all-plus" (from the newer run), not "very-old-value".
        mock_cs.assert_called_once_with(
            key="custom:metric-signature",
            value="all-plus",
            force=True,
        )

    def test_revert_fails_gracefully_on_empty_revlog(self, tmp_path: Path) -> None:
        """revert on an empty revlog returns failed status, not an exception."""
        result = _run_integrator(tmp_path, {}, revert=True)

        assert result["status"] == "failed"
        assert result["revert_applied"] is False
