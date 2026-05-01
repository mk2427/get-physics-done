"""Tests for gpd.core.eqnref_revlog.

Brief 002 §Commit 7 required tests:

1. ``test_append_and_recent`` — append 3 entries; ``eqnref_revlog_recent()``
   returns all 3; filter by ``axis_id`` returns correct subset.
2. ``test_idempotent_rerun`` — re-run with identical ``eqn_ref_content_hash``
   produces a NEW entry (the function is append-only; idempotency is the
   INTEGRATOR's responsibility, not the log's).
3. ``test_axis_id_filter`` — two entries with ``axis_id="trace_norm"``, one
   with ``axis_id="gauge_group"``; filter returns only the right ones.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.eqnref_revlog import (
    EQNREF_REVLOG_RELPATH,
    eqnref_revlog_append,
    eqnref_revlog_path,
    eqnref_revlog_recent,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_entry(
    *,
    run_id: str = "run-aaa",
    utc_timestamp: str = "2026-04-21T00:00:00+00:00",
    axis_id: str = "metric_signature",
    mcp_key: str = "custom:metric-signature",
    prior_value: str | None = None,
    new_value: str = "mostly-plus",
    eqn_ref_content_hash: str = "deadbeef" * 8,
    force_used: bool = False,
) -> dict:
    """Return a minimal valid revlog entry dict."""
    return {
        "run_id": run_id,
        "utc_timestamp": utc_timestamp,
        "axis_id": axis_id,
        "mcp_key": mcp_key,
        "prior_value": prior_value,
        "new_value": new_value,
        "eqn_ref_content_hash": eqn_ref_content_hash,
        "force_used": force_used,
    }


# ─── Test 1: append_and_recent ────────────────────────────────────────────────


class TestAppendAndRecent:
    """Brief 002 §Commit 7 Test 1."""

    def test_append_and_recent_returns_all_entries(self, tmp_path: Path) -> None:
        """Append 3 entries; eqnref_revlog_recent() returns all 3 in order."""
        entries = [
            _make_entry(axis_id="metric_signature", run_id=f"run-{i}")
            for i in range(3)
        ]
        for entry in entries:
            eqnref_revlog_append(tmp_path, entry)

        result = eqnref_revlog_recent(tmp_path)
        assert len(result) == 3
        # Verify chronological order preserved.
        returned_run_ids = [r["run_id"] for r in result]
        assert returned_run_ids == ["run-0", "run-1", "run-2"]

    def test_append_creates_parent_dirs(self, tmp_path: Path) -> None:
        """eqnref_revlog_append creates GPD/knowledge/revlogs/ if absent."""
        project_root = tmp_path / "myproject"
        project_root.mkdir()
        entry = _make_entry()
        eqnref_revlog_append(project_root, entry)
        revlog = eqnref_revlog_path(project_root)
        assert revlog.exists(), "revlog file should have been created"

    def test_revlog_path_uses_expected_relative_path(self, tmp_path: Path) -> None:
        """The revlog file lives at the expected relative path."""
        revlog = eqnref_revlog_path(tmp_path)
        assert revlog == tmp_path / EQNREF_REVLOG_RELPATH

    def test_filter_by_axis_id_returns_correct_subset(self, tmp_path: Path) -> None:
        """Filter by axis_id returns only entries for that axis."""
        eqnref_revlog_append(tmp_path, _make_entry(axis_id="metric_signature", run_id="r1"))
        eqnref_revlog_append(tmp_path, _make_entry(axis_id="gauge_group", run_id="r2"))
        eqnref_revlog_append(tmp_path, _make_entry(axis_id="metric_signature", run_id="r3"))

        metric_entries = eqnref_revlog_recent(tmp_path, axis_id="metric_signature")
        assert len(metric_entries) == 2
        assert all(e["axis_id"] == "metric_signature" for e in metric_entries)

        gauge_entries = eqnref_revlog_recent(tmp_path, axis_id="gauge_group")
        assert len(gauge_entries) == 1
        assert gauge_entries[0]["run_id"] == "r2"

    def test_recent_returns_empty_when_file_absent(self, tmp_path: Path) -> None:
        """eqnref_revlog_recent returns empty list when revlog does not exist."""
        result = eqnref_revlog_recent(tmp_path)
        assert result == []


# ─── Test 2: idempotent_rerun ─────────────────────────────────────────────────


class TestIdempotentRerun:
    """Brief 002 §Commit 7 Test 2.

    The revlog module is append-only — it does NOT enforce idempotency.
    Re-running with an identical ``eqn_ref_content_hash`` produces a NEW
    entry because the log records what happened, not what is current.

    Idempotency is the INTEGRATOR's responsibility: before appending,
    ``gpd-eqnref-integrator`` should check whether the most-recent entry for
    each axis already has the same ``eqn_ref_content_hash`` and ``new_value``,
    and skip the append if so. The revlog module itself MUST NOT do this check
    because it would break the audit trail.
    """

    def test_identical_hash_still_appends_new_entry(self, tmp_path: Path) -> None:
        """Re-run with identical content hash produces a new revlog entry.

        This is the correct, intended behavior: the revlog is a history ledger.
        The integrator layer is responsible for avoiding redundant appends when
        the content hash has not changed; the revlog module never suppresses
        writes.
        """
        shared_hash = "cafebabe" * 8
        entry_a = _make_entry(run_id="run-first", eqn_ref_content_hash=shared_hash)
        entry_b = _make_entry(run_id="run-second", eqn_ref_content_hash=shared_hash)

        eqnref_revlog_append(tmp_path, entry_a)
        eqnref_revlog_append(tmp_path, entry_b)

        result = eqnref_revlog_recent(tmp_path)
        assert len(result) == 2, (
            "eqnref_revlog_append is append-only; identical hash must still produce 2 entries. "
            "Idempotency belongs to the integrator, not the revlog module."
        )
        assert result[0]["run_id"] == "run-first"
        assert result[1]["run_id"] == "run-second"

    def test_missing_required_field_raises_value_error(self, tmp_path: Path) -> None:
        """eqnref_revlog_append raises ValueError for missing required fields."""
        bad_entry = {"run_id": "r1", "axis_id": "x"}  # missing most fields
        with pytest.raises(ValueError, match="missing required fields"):
            eqnref_revlog_append(tmp_path, bad_entry)


# ─── Test 3: axis_id_filter ───────────────────────────────────────────────────


class TestAxisIdFilter:
    """Brief 002 §Commit 7 Test 3."""

    def test_axis_id_filter_separates_trace_norm_from_gauge_group(
        self, tmp_path: Path
    ) -> None:
        """Two entries with axis_id='trace_norm', one with 'gauge_group'.

        eqnref_revlog_recent(axis_id='trace_norm') must return exactly 2;
        eqnref_revlog_recent(axis_id='gauge_group') must return exactly 1.
        """
        eqnref_revlog_append(tmp_path, _make_entry(axis_id="trace_norm", run_id="r1"))
        eqnref_revlog_append(tmp_path, _make_entry(axis_id="gauge_group", run_id="r2"))
        eqnref_revlog_append(tmp_path, _make_entry(axis_id="trace_norm", run_id="r3"))

        trace_entries = eqnref_revlog_recent(tmp_path, axis_id="trace_norm")
        assert len(trace_entries) == 2
        assert {e["run_id"] for e in trace_entries} == {"r1", "r3"}

        gauge_entries = eqnref_revlog_recent(tmp_path, axis_id="gauge_group")
        assert len(gauge_entries) == 1
        assert gauge_entries[0]["run_id"] == "r2"

    def test_limit_truncates_oldest_entries(self, tmp_path: Path) -> None:
        """limit=2 returns only the 2 most recent entries."""
        for i in range(5):
            eqnref_revlog_append(tmp_path, _make_entry(run_id=f"r{i}"))

        result = eqnref_revlog_recent(tmp_path, limit=2)
        assert len(result) == 2
        # Most recent 2 are r3, r4.
        assert [e["run_id"] for e in result] == ["r3", "r4"]

    def test_revlog_file_is_valid_jsonl(self, tmp_path: Path) -> None:
        """Each line in the revlog file is valid JSON."""
        entries = [_make_entry(run_id=f"r{i}") for i in range(3)]
        for e in entries:
            eqnref_revlog_append(tmp_path, e)

        revlog = eqnref_revlog_path(tmp_path)
        lines = revlog.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)  # must not raise
            assert isinstance(parsed, dict)
