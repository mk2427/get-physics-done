"""Tests for ``tests/canary/cost_log.py`` (plan-006 §C4).

Six tests cover:

1. Append round-trips (order + content preserved).
2. Atomic-write under simulated ``tmp.replace`` failure (log_path
   unchanged).
3. Concurrent append from 4 threads × 25 entries (final log has 100
   entries with no torn writes).
4. ``completed_arxiv_ids`` filters to latest-error_class=='ok'.
5. ``completed_arxiv_ids`` tie-breaker: identical ``completed_at`` ⇒
   last-line wins (resolves iter-2-W2).
6. ``verify_log_against_manifest`` detects missing / extra / duplicates.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))

import cost_log  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Append round-trips.
# ---------------------------------------------------------------------------


def test_append_round_trips(tmp_path: Path) -> None:
    log_path = tmp_path / "cost.jsonl"
    cost_log.append_paper_cost(
        "1810.03378",
        [Path("GPD/knowledge/K-001-foo.md")],
        {
            "error_class": "ok",
            "cost_usd": 4.21,
            "input_tokens": 100,
            "output_tokens": 50,
            "session_id": "sess-A",
            "completed_at": "2026-04-26T18:43:00Z",
            "duration_ms": 720_000,
            "n_assertions": 12,
            "assertion_paths": ["GPD/assertions/A-007-bar.md"],
            "kdoc_statuses": {"K-001": "Stable"},
        },
        log_path=log_path,
    )
    cost_log.append_paper_cost(
        "2511.01209",
        [Path("GPD/knowledge/K-002-baz.md")],
        {
            "error_class": "timeout",
            "cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "completed_at": "2026-04-26T19:00:00Z",
        },
        log_path=log_path,
    )

    log = cost_log.read_cost_log(log_path)
    assert len(log) == 2
    assert [e["arxiv_id"] for e in log] == ["1810.03378", "2511.01209"]
    assert log[0]["error_class"] == "ok"
    assert log[0]["cost_usd"] == pytest.approx(4.21)
    assert log[0]["token_cost"] == 150
    assert log[0]["n_assertions"] == 12
    assert log[0]["kdoc_paths"] == ["GPD/knowledge/K-001-foo.md"]
    assert log[0]["claude_session_id"] == "sess-A"
    assert log[0]["wall_clock_seconds"] == pytest.approx(720.0)
    assert log[1]["error_class"] == "timeout"


# ---------------------------------------------------------------------------
# 2. Atomic write: replace fails ⇒ log_path is unchanged.
# ---------------------------------------------------------------------------


def test_atomic_write_under_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_path = tmp_path / "cost.jsonl"

    # Pre-populate with one good entry.
    cost_log.append_paper_cost(
        "PRE",
        [],
        {"error_class": "ok"},
        log_path=log_path,
    )
    pre_bytes = log_path.read_bytes()
    assert pre_bytes  # sanity

    # Patch Path.replace to raise on any call. cost_log calls
    # ``tmp_path.replace(log_path)`` after the tmp file has been written
    # and fsync'd, so this exercises the post-write / pre-replace
    # failure path.
    real_replace = Path.replace

    def boom(self: Path, target: object) -> Path:
        # Only blow up replaces that would clobber log_path; leave any
        # internal pytest-tmp_path replaces (none expected) alone.
        if Path(target) == log_path:
            raise OSError("simulated replace failure")
        return real_replace(self, target)  # pragma: no cover

    monkeypatch.setattr(Path, "replace", boom)

    with pytest.raises(OSError, match="simulated replace failure"):
        cost_log.append_paper_cost(
            "WOULD-FAIL",
            [],
            {"error_class": "ok"},
            log_path=log_path,
        )

    # log_path must be byte-identical to the pre-failure state.
    assert log_path.read_bytes() == pre_bytes
    log = cost_log.read_cost_log(log_path)
    assert len(log) == 1
    assert log[0]["arxiv_id"] == "PRE"


# ---------------------------------------------------------------------------
# 3. Concurrent append: 4 threads × 25 entries ⇒ exactly 100 valid lines.
# ---------------------------------------------------------------------------


def test_concurrent_append_serializes(tmp_path: Path) -> None:
    log_path = tmp_path / "cost.jsonl"
    n_threads = 4
    per_thread = 25

    def worker(tid: int) -> None:
        for i in range(per_thread):
            cost_log.append_paper_cost(
                f"T{tid}-E{i:02d}",
                [Path(f"GPD/knowledge/K-{tid}-{i}.md")],
                {
                    "error_class": "ok",
                    "cost_usd": 0.01 * i,
                    "input_tokens": tid * 1000 + i,
                    "output_tokens": i,
                },
                log_path=log_path,
            )

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    raw = log_path.read_text(encoding="utf-8")
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    assert len(lines) == n_threads * per_thread, (
        f"expected {n_threads * per_thread} lines, got {len(lines)}"
    )
    # Every line must be parseable JSON with the required schema fields.
    arxiv_ids: set[str] = set()
    for ln in lines:
        entry = json.loads(ln)
        assert entry["error_class"] == "ok"
        assert "arxiv_id" in entry
        arxiv_ids.add(entry["arxiv_id"])
    assert len(arxiv_ids) == n_threads * per_thread, "no duplicates expected"


# ---------------------------------------------------------------------------
# 4. completed_arxiv_ids: latest-entry filter (error, error, ok ⇒ {X}).
# ---------------------------------------------------------------------------


def test_completed_arxiv_ids_filters_to_ok_latest() -> None:
    log = [
        {
            "arxiv_id": "X",
            "error_class": "subprocess_error",
            "completed_at": "2026-04-26T10:00:00Z",
        },
        {
            "arxiv_id": "X",
            "error_class": "timeout",
            "completed_at": "2026-04-26T11:00:00Z",
        },
        {
            "arxiv_id": "X",
            "error_class": "ok",
            "completed_at": "2026-04-26T12:00:00Z",
        },
        {
            "arxiv_id": "Y",
            "error_class": "ok",
            "completed_at": "2026-04-26T09:00:00Z",
        },
        {
            "arxiv_id": "Y",
            "error_class": "skill_error",
            "completed_at": "2026-04-26T13:00:00Z",
        },
    ]
    # X: latest is ok ⇒ included. Y: latest is skill_error ⇒ excluded.
    assert cost_log.completed_arxiv_ids(log) == {"X"}


# ---------------------------------------------------------------------------
# 5. completed_arxiv_ids tie-breaker: identical ts ⇒ last-line wins (W2).
# ---------------------------------------------------------------------------


def test_completed_arxiv_ids_latest_by_completed_at_tie_breaks_last_line() -> None:
    same_ts = "2026-04-26T18:00:00Z"
    # Case A: ok then error at same ts ⇒ error wins (last line) ⇒ Y NOT in set.
    log_a = [
        {"arxiv_id": "Y", "error_class": "ok", "completed_at": same_ts},
        {"arxiv_id": "Y", "error_class": "skill_error", "completed_at": same_ts},
    ]
    assert cost_log.completed_arxiv_ids(log_a) == set()

    # Case B: error then ok at same ts ⇒ ok wins (last line) ⇒ Y IN set.
    log_b = [
        {"arxiv_id": "Y", "error_class": "skill_error", "completed_at": same_ts},
        {"arxiv_id": "Y", "error_class": "ok", "completed_at": same_ts},
    ]
    assert cost_log.completed_arxiv_ids(log_b) == {"Y"}


# ---------------------------------------------------------------------------
# 6. verify_log_against_manifest: missing + extra + duplicates.
# ---------------------------------------------------------------------------


def test_verify_log_against_manifest_detects_missing_extra_duplicates() -> None:
    manifest = {
        "entries": [
            {"arxiv_id": "A"},
            {"arxiv_id": "B"},
            {"arxiv_id": "C"},  # missing in log
        ]
    }
    log = [
        {"arxiv_id": "A", "error_class": "ok"},
        {"arxiv_id": "B", "error_class": "ok"},
        {"arxiv_id": "B", "error_class": "ok"},  # duplicate
        {"arxiv_id": "Z", "error_class": "ok"},  # extra
        {"arxiv_id": "Z", "error_class": "ok"},  # extra + duplicate
    ]
    diff = cost_log.verify_log_against_manifest(log, manifest)
    assert diff["missing"] == ["C"]
    assert diff["extra"] == ["Z"]
    assert set(diff["duplicates"]) == {"B", "Z"}
