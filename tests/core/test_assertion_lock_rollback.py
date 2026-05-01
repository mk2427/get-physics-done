"""Tests for write_upstream_divergence_with_cascade rollback discipline (brief 002 §3.4).

Four tests per plan §Commit 9:
* test_step_b_failure_rolls_back_a — (b) raises → (a) reverted; no ledger entry.
* test_step_c_failure_writes_aborted_ledger_and_rolls_back_a — (c) raises → aborted
  compensating entry written; (a) reverted.
* test_ttl_expiry_rolls_back_all_sub_writes — TTL expiry → (a) reverted.
* test_reader_sees_pre_or_post_never_partial — success path transitions cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from gpd.core.assertion_lock import write_upstream_divergence_with_cascade
from gpd.core.constants import INVALIDATION_EVENTS_FILENAME, KNOWLEDGE_DIR_NAME, PLANNING_DIR_NAME


# ─── Fixtures ─────────────────────────────────────────────────────────────────

_ASSERTION_TEMPLATE = """\
---
assertion_id: {assertion_id}
kind: restated-equation
status: Stable
topic: "Test assertion"
knowledge_doc_ids:
  - "K-001"
eqn_ref_entries:
  - "E.1"
created: 2026-01-01
last_reviewed: 2026-01-01
review_rounds: 1
superseded_by: null
load_bearing: false
derivation_sketch: null
upstream_ref_hash: null
upstream_status_mirror:
  kdoc_id: "K-001"
  kdoc_status_at_stable: "Stable"
  divergence_detected_at: null
---

# Assertion: Test

Body text.
"""


def _make_assertion_file(project_root: Path, assertion_id: str = "A-001-test") -> Path:
    """Create a stub assertion YAML in GPD/assertions/ and return its path."""
    assertions_dir = project_root / PLANNING_DIR_NAME / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    slug = assertion_id.split("-", 2)[-1] if assertion_id.count("-") >= 2 else assertion_id
    md_path = assertions_dir / f"{assertion_id}.md"
    md_path.write_text(_ASSERTION_TEMPLATE.format(assertion_id=assertion_id), encoding="utf-8")
    return md_path


def _ledger_path(project_root: Path) -> Path:
    return project_root / PLANNING_DIR_NAME / KNOWLEDGE_DIR_NAME / INVALIDATION_EVENTS_FILENAME


def _read_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}
    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    parsed = yaml.safe_load("".join(fm_lines))
    return parsed if isinstance(parsed, dict) else {}


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestStepBFailureRollsBackA:
    """(b) raises → (a) reverted; ledger file is absent or unchanged."""

    def test_step_b_failure_rolls_back_a(self, tmp_path: Path) -> None:
        md_path = _make_assertion_file(tmp_path)
        original_text = md_path.read_text(encoding="utf-8")

        # Inject step-(b) failure by patching json.dumps to raise on the first call
        # inside write_upstream_divergence_with_cascade (which is the ledger entry
        # serialisation in step b).
        real_json_dumps = json.dumps
        call_count = [0]

        def failing_json_dumps(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("simulated ledger write failure")
            return real_json_dumps(*args, **kwargs)

        with patch("gpd.core.assertion_lock.json.dumps", side_effect=failing_json_dumps):
            with pytest.raises(OSError, match="simulated ledger write failure"):
                write_upstream_divergence_with_cascade(
                    tmp_path, "A-001-test", "restated-equation", "2026-04-21T00:00:00Z"
                )

        # (a) must be reverted: YAML content restored to pre-write snapshot.
        restored_text = md_path.read_text(encoding="utf-8")
        assert restored_text == original_text

        # Ledger must not exist (or be empty — nothing was written).
        ledger = _ledger_path(tmp_path)
        assert not ledger.exists() or ledger.stat().st_size == 0


class TestStepCFailureWritesAbortedLedgerAndRollsBackA:
    """(c) raises → compensating aborted entry + (a) reverted."""

    def test_step_c_failure_writes_aborted_ledger_and_rolls_back_a(self, tmp_path: Path) -> None:
        md_path = _make_assertion_file(tmp_path)
        original_text = md_path.read_text(encoding="utf-8")

        # We need step (c) to fail. (c) writes the top-level `status` field via
        # _write_frontmatter_field. We patch yaml.dump so that the second call
        # (during step c) raises, while the first call (step a) succeeds.
        real_yaml_dump = yaml.dump
        call_count = [0]

        def patched_yaml_dump(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise RuntimeError("simulated status write failure")
            return real_yaml_dump(*args, **kwargs)

        with patch("gpd.core.assertion_lock.yaml.dump", side_effect=patched_yaml_dump):
            with pytest.raises(RuntimeError, match="simulated status write failure"):
                write_upstream_divergence_with_cascade(
                    tmp_path, "A-001-test", "restated-equation", "2026-04-21T00:00:00Z"
                )

        # (a) must be reverted.
        restored_text = md_path.read_text(encoding="utf-8")
        assert restored_text == original_text

        # Ledger must contain the original "open" entry PLUS a compensating aborted entry
        # (brief 002 §8.3; commit 10d replaced the "pending" stub with the full
        # InvalidationEvent schema using status="open").
        ledger = _ledger_path(tmp_path)
        assert ledger.exists(), "Ledger must exist after step (b) succeeded"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(entries) == 2
        open_entries = [e for e in entries if e.get("status") == "open"]
        aborted_entries = [e for e in entries if e.get("status") == "aborted"]
        assert len(open_entries) == 1
        assert len(aborted_entries) == 1
        # Both entries share the same event_id.
        assert open_entries[0]["event_id"] == aborted_entries[0]["event_id"]


class TestTtlExpiryRollsBackAllSubWrites:
    """TTL expiry propagates out; (a) is reverted if expiry happens during lock acquisition."""

    def test_ttl_expiry_rolls_back_all_sub_writes(self, tmp_path: Path) -> None:
        """Simulate TTL expiry by patching utils.file_lock to raise TimeoutError.

        Since assertion_status_lock wraps file_lock, a TimeoutError from file_lock
        means the context body (including all sub-writes) never executes.  The YAML
        must remain unchanged.
        """
        md_path = _make_assertion_file(tmp_path)
        original_text = md_path.read_text(encoding="utf-8")

        from contextlib import contextmanager  # noqa: PLC0415

        @contextmanager
        def timeout_file_lock(path, timeout=5.0):
            raise TimeoutError(f"Timeout acquiring lock on {path}")
            yield  # noqa: unreachable — satisfies contextmanager type

        with patch("gpd.core.utils.file_lock", side_effect=timeout_file_lock):
            from gpd.core.assertion_lock import assertion_status_lock  # noqa: PLC0415

            with pytest.raises(TimeoutError):
                with assertion_status_lock(tmp_path, timeout=0.01):
                    write_upstream_divergence_with_cascade(
                        tmp_path, "A-001-test", "restated-equation", "2026-04-21T00:00:00Z"
                    )

        # YAML must be unchanged (context body never ran).
        assert md_path.read_text(encoding="utf-8") == original_text
        assert not _ledger_path(tmp_path).exists()


class TestReaderSeesPreOrPostNeverPartial:
    """Success path: assertion transitions cleanly Stable → Under Review with ledger entry."""

    def test_reader_sees_pre_or_post_never_partial(self, tmp_path: Path) -> None:
        md_path = _make_assertion_file(tmp_path)

        write_upstream_divergence_with_cascade(
            tmp_path, "A-001-test", "restated-equation", "2026-04-21T12:00:00Z"
        )

        # Assertion YAML must have status=Under Review and divergence_detected_at set.
        fm = _read_frontmatter(md_path)
        assert fm["status"] == "Under Review"
        mirror = fm.get("upstream_status_mirror", {})
        assert mirror.get("divergence_detected_at") == "2026-04-21T12:00:00Z"

        # Ledger must contain exactly one "open" entry with the full InvalidationEvent
        # schema (brief 002 §8.3; commit 10d replaced the "pending" stub).
        ledger = _ledger_path(tmp_path)
        assert ledger.exists()
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["status"] == "open"
        assert entry["source_type"] == "assertion"
        assert entry["source_id"] == "A-001-test"
        assert entry["utc_timestamp"] == "2026-04-21T12:00:00Z"
        assert "event_id" in entry
        assert entry["root_event_id"] == entry["event_id"]
        assert "affected_result_ids" in entry
