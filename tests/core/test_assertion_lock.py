"""Tests for gpd.core.assertion_lock — wrapper acquire/release, TTL, cross-process.

Three tests per plan §Commit 9:
* test_wrapper_acquires_via_utils_file_lock — confirms delegation to utils.file_lock.
* test_wrapper_timeout_30s_overrides_default — confirms timeout=30.0, not 5.0.
* test_cross_process_mutual_exclusion — subprocess holds lock; main process times out.

iter-1-M3 regression (dual-write discipline):
* test_dual_write_populates_state_when_provided — write_upstream_divergence_with_cascade
  must also call append_invalidation_event(state, event) when state kwarg is passed.
"""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import json

import yaml

from gpd.core.assertion_lock import assertion_status_lock, write_upstream_divergence_with_cascade
from gpd.core.constants import ProjectLayout


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _hold_lock_for(project_root: Path, hold_seconds: float, ready_event_path: Path) -> None:
    """Subprocess target: acquire the lock and hold it, signalling readiness via a file."""
    from gpd.core.assertion_lock import assertion_status_lock  # noqa: PLC0415

    with assertion_status_lock(project_root, timeout=30.0):
        ready_event_path.touch()
        time.sleep(hold_seconds)


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestWrapperAcquiresViaUtilsFileLock:
    """Wrapper delegates to utils.file_lock with the correct lock stem path."""

    def test_wrapper_acquires_via_utils_file_lock(self, tmp_path: Path) -> None:
        """Mock-spy on utils.file_lock; assert called with correct path and timeout."""
        captured: list[tuple] = []

        from gpd.core import utils as core_utils
        real_file_lock = core_utils.file_lock

        def spy_file_lock(path: Path, timeout: float = 5.0):
            captured.append((path, timeout))
            return real_file_lock(path, timeout=timeout)

        with patch("gpd.core.utils.file_lock", side_effect=spy_file_lock):
            with assertion_status_lock(tmp_path):
                pass

        assert len(captured) == 1
        called_path, called_timeout = captured[0]
        expected_stem = ProjectLayout(tmp_path).assertion_status_lock
        assert called_path == expected_stem
        assert called_timeout == 30.0


class TestWrapperTimeout30sOverridesDefault:
    """assertion_status_lock passes timeout=30.0, overriding utils.file_lock's 5 s default."""

    def test_wrapper_timeout_30s_overrides_default(self, tmp_path: Path) -> None:
        """Capture the timeout kwarg forwarded to utils.file_lock; assert it is 30.0."""
        captured_timeout: list[float] = []

        from gpd.core import utils as core_utils
        real_file_lock = core_utils.file_lock

        def spy_file_lock(path: Path, timeout: float = 5.0):
            captured_timeout.append(timeout)
            return real_file_lock(path, timeout=timeout)

        with patch("gpd.core.utils.file_lock", side_effect=spy_file_lock):
            with assertion_status_lock(tmp_path):
                pass

        assert captured_timeout == [30.0]

    def test_custom_timeout_forwarded(self, tmp_path: Path) -> None:
        """Custom timeout value is forwarded unchanged to utils.file_lock."""
        captured_timeout: list[float] = []

        from gpd.core import utils as core_utils
        real_file_lock = core_utils.file_lock

        def spy_file_lock(path: Path, timeout: float = 5.0):
            captured_timeout.append(timeout)
            return real_file_lock(path, timeout=timeout)

        with patch("gpd.core.utils.file_lock", side_effect=spy_file_lock):
            with assertion_status_lock(tmp_path, timeout=10.0):
                pass

        assert captured_timeout == [10.0]


class TestCrossProcessMutualExclusion:
    """Subprocess holds the lock; concurrent acquire from main process raises TimeoutError."""

    def test_cross_process_mutual_exclusion(self, tmp_path: Path) -> None:
        """Hold lock in subprocess; assert concurrent acquire times out."""
        ready_flag = tmp_path / ".lock_ready"

        proc = multiprocessing.Process(
            target=_hold_lock_for,
            args=(tmp_path, 5.0, ready_flag),
        )
        proc.start()

        # Wait until the subprocess has acquired the lock (up to 5 s).
        deadline = time.monotonic() + 5.0
        while not ready_flag.exists():
            if time.monotonic() > deadline:
                proc.terminate()
                proc.join()
                pytest.fail("Subprocess did not acquire lock within 5 s")
            time.sleep(0.05)

        try:
            with pytest.raises(TimeoutError):
                with assertion_status_lock(tmp_path, timeout=0.1):
                    pass  # should not reach here
        finally:
            proc.terminate()
            proc.join(timeout=6.0)


# ─── iter-1-M3 regression: dual-write ────────────────────────────────────────


def _make_assertion_file(tmp_path: Path, assertion_id: str) -> None:
    """Write a minimal Stable assertion file under the standard GPD layout."""
    assertions_dir = tmp_path / "GPD" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "assertion_id": assertion_id,
        "status": "Stable",
        "title": f"Test {assertion_id}",
        "upstream_status_mirror": {"divergence_detected_at": None},
    }
    md_path = assertions_dir / f"{assertion_id}.md"
    md_path.write_text("---\n" + yaml.dump(fm, default_flow_style=False) + "---\n\nBody.\n", encoding="utf-8")
    (tmp_path / "GPD" / "knowledge").mkdir(parents=True, exist_ok=True)


class TestDualWritePopulatesState:
    """iter-1-M3 regression: write_upstream_divergence_with_cascade with state kwarg
    must also call append_invalidation_event so state['invalidation_events'] is updated.
    """

    def test_dual_write_populates_state_when_provided(self, tmp_path: Path) -> None:
        """When state dict is passed, the JSONL write AND the state list write both happen."""
        _make_assertion_file(tmp_path, "A-DW-001")
        state: dict = {}

        with assertion_status_lock(tmp_path):
            write_upstream_divergence_with_cascade(
                tmp_path,
                "A-DW-001",
                kind="test_kind",
                at_timestamp="2026-04-21T00:00:00+00:00",
                state=state,
            )

        # State dict must now have the event.
        events = state.get("invalidation_events", [])
        assert len(events) == 1, "state['invalidation_events'] must contain the cascade event"
        ev = events[0]
        assert ev["source_id"] == "A-DW-001"
        assert ev["status"] == "open"
        assert ev["source_type"] == "assertion"

        # JSONL ledger must also have the event (the original durable write).
        ledger = tmp_path / "GPD" / "knowledge" / "invalidation_events.jsonl"
        assert ledger.exists()
        lines = ledger.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 1
        ledger_ev = json.loads(lines[0])
        assert ledger_ev["event_id"] == ev["event_id"], "JSONL event_id must match state event_id"

    def test_no_state_kwarg_does_not_update_state(self, tmp_path: Path) -> None:
        """Without state kwarg, state dict is not modified (backward compat)."""
        _make_assertion_file(tmp_path, "A-DW-002")
        state: dict = {}

        with assertion_status_lock(tmp_path):
            write_upstream_divergence_with_cascade(
                tmp_path,
                "A-DW-002",
                kind="test_kind",
                at_timestamp="2026-04-21T00:00:00+00:00",
                # no state kwarg
            )

        # State dict must be untouched.
        assert "invalidation_events" not in state
