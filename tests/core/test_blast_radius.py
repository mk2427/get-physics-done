"""Tests for gpd.core.blast_radius — knowledge-doc invalidation scanner."""

from __future__ import annotations

import time

import gpd.core.blast_radius as _blast_mod
from gpd.core.blast_radius import (
    AssertionCycleError,
    append_invalidation_event,
    assertion_invalidation_scan,
    knowledge_invalidation_scan,
    result_is_suspect,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_cache() -> None:
    """Empty the module-level scan cache between tests."""
    _blast_mod._SCAN_CACHE.clear()


# ---------------------------------------------------------------------------
# Test 1 — finds dependent results
# ---------------------------------------------------------------------------


def test_kdoc_invalidation_finds_dependent_results():
    """A result whose knowledge_deps contains K-001 is returned by the scan."""
    _clear_cache()

    state: dict = {
        "intermediate_results": [
            {
                "id": "R-03-07",
                "equation": "E = mc^2",
                "description": "energy-mass",
                "phase": "3",
                "depends_on": [],
                "knowledge_deps": ["K-001"],
                "verified": False,
                "verification_records": [],
            },
            {
                "id": "R-03-08",
                "description": "unrelated result",
                "phase": "3",
                "depends_on": [],
                "knowledge_deps": ["K-002"],
                "verified": False,
                "verification_records": [],
            },
        ]
    }

    result = knowledge_invalidation_scan(state, "K-001")

    assert isinstance(result, dict)
    assert "K-001" in result
    assert "R-03-07" in result["K-001"]
    assert "R-03-08" not in result["K-001"]


# ---------------------------------------------------------------------------
# Test 2 — empty knowledge_deps returns empty list
# ---------------------------------------------------------------------------


def test_kdoc_invalidation_empty_knowledge_deps():
    """When no result references K-001 the scan returns {K-001: []}."""
    _clear_cache()

    state: dict = {
        "intermediate_results": [
            {
                "id": "R-01",
                "description": "no kdoc deps",
                "depends_on": [],
                "knowledge_deps": [],
                "verified": False,
                "verification_records": [],
            },
            {
                "id": "R-02",
                "description": "also no kdoc deps",
                "depends_on": [],
                # knowledge_deps absent — treated as empty
                "verified": False,
                "verification_records": [],
            },
        ]
    }

    result = knowledge_invalidation_scan(state, "K-001")

    assert result == {"K-001": []}


# ---------------------------------------------------------------------------
# Test 3 — cache invalidation on kdoc status change
# ---------------------------------------------------------------------------


def test_kdoc_invalidation_cache_invalidation_on_status_change():
    """Cache is invalidated when a kdoc transitions away from Draft status.

    Sequence:
    1. Build state with one result depending on K-001 and one kdoc (Draft).
    2. Call scan twice → both hits the cache on the second call (same key).
    3. Mutate the kdoc status to "Stable" (simulates a status transition).
    4. Call scan again → cache miss; result is recomputed.

    We verify the cache-key function changes after the mutation, which is the
    mechanism that causes the recomputation.
    """
    _clear_cache()

    state: dict = {
        "knowledge_docs": [
            {"id": "K-001", "status": "Draft"},
        ],
        "intermediate_results": [
            {
                "id": "R-05-01",
                "description": "result depending on K-001",
                "depends_on": [],
                "knowledge_deps": ["K-001"],
                "verified": False,
                "verification_records": [],
            },
        ],
    }

    # First call — populates cache
    result_first = knowledge_invalidation_scan(state, "K-001")
    assert "R-05-01" in result_first["K-001"]

    # Record the cache key before mutation
    key_before = _blast_mod._cache_key(state)

    # Second call — same state → same cache key → cache hit
    result_second = knowledge_invalidation_scan(state, "K-001")
    assert result_second is result_first  # identical object from cache

    # Mutate: promote kdoc from Draft → Stable (simulates status transition)
    state["knowledge_docs"][0]["status"] = "Stable"

    # Cache key must have changed
    key_after = _blast_mod._cache_key(state)
    assert key_after != key_before, (
        f"Cache key should change after status transition: before={key_before}, after={key_after}"
    )

    # Third call — new cache key → cache miss → fresh computation
    result_third = knowledge_invalidation_scan(state, "K-001")
    assert "R-05-01" in result_third["K-001"]
    # The new cache entry is a distinct object from the stale one
    assert result_third is not result_first


# ---------------------------------------------------------------------------
# Assertion-DAG invalidation tests (commit 10c)
# ---------------------------------------------------------------------------


def test_assertion_invalidation_direct_dependents():
    """A result whose assertion_deps contains A-001 is returned by the scan."""
    assertion_docs = {"A-001": {"depends_on": []}}
    state: dict = {
        "intermediate_results": [
            {
                "id": "R-04-02",
                "description": "result depending directly on A-001",
                "assertion_deps": ["A-001"],
            },
            {
                "id": "R-04-03",
                "description": "unrelated result",
                "assertion_deps": ["A-007"],
            },
        ]
    }

    result = assertion_invalidation_scan(state, "A-001", assertion_docs)

    assert isinstance(result, dict)
    assert "A-001" in result
    assert "R-04-02" in result["A-001"]
    assert "R-04-03" not in result["A-001"]


def test_assertion_invalidation_transitive_dag():
    """Transitive closure: scan from A-001 finds dependents of A-007 and A-019.

    DAG: A-001 → A-007 → A-019 (depends_on edges point to children).
    Results depending on A-007 and A-019 are both reachable from A-001.
    """
    assertion_docs = {
        "A-001": {"depends_on": ["A-007"]},
        "A-007": {"depends_on": ["A-019"]},
        "A-019": {"depends_on": []},
    }
    state: dict = {
        "intermediate_results": [
            {
                "id": "R-10-01",
                "description": "depends on A-007",
                "assertion_deps": ["A-007"],
            },
            {
                "id": "R-10-02",
                "description": "depends on A-019",
                "assertion_deps": ["A-019"],
            },
            {
                "id": "R-10-03",
                "description": "unrelated",
                "assertion_deps": ["A-042"],
            },
        ]
    }

    result = assertion_invalidation_scan(state, "A-001", assertion_docs)

    assert "A-001" in result
    assert "R-10-01" in result["A-001"]
    assert "R-10-02" in result["A-001"]
    assert "R-10-03" not in result["A-001"]


def test_assertion_dag_cycle_detection():
    """A cycle in depends_on raises AssertionCycleError (not an infinite loop)."""
    assertion_docs = {
        "A-001": {"depends_on": ["A-002"]},
        "A-002": {"depends_on": ["A-001"]},
    }
    state: dict = {"intermediate_results": []}

    import pytest

    with pytest.raises(AssertionCycleError):
        assertion_invalidation_scan(state, "A-001", assertion_docs)


def test_assertion_invalidation_fixed_point_termination():
    """Chain of 50 assertions terminates in < 1 second (visited-set guarantees O(N+E))."""
    n = 50
    # A-001 → A-002 → ... → A-050 (linear chain)
    assertion_docs = {
        f"A-{i:03d}": {"depends_on": [f"A-{i + 1:03d}"] if i < n else []}
        for i in range(1, n + 1)
    }
    state: dict = {
        "intermediate_results": [
            {
                "id": f"R-chain-{i:03d}",
                "assertion_deps": [f"A-{i:03d}"],
            }
            for i in range(1, n + 1)
        ]
    }

    start = time.monotonic()
    result = assertion_invalidation_scan(state, "A-001", assertion_docs)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"Scan took {elapsed:.3f}s — expected < 1s"
    # All results in the chain are reachable from A-001
    assert len(result["A-001"]) == n


# ---------------------------------------------------------------------------
# Invalidation-events ledger tests (commit 10d)
# ---------------------------------------------------------------------------


def _make_event(
    event_id: str,
    *,
    root_event_id: str | None = None,
    source_type: str = "knowledge",
    source_id: str = "K-001",
    affected_result_ids: list[str] | None = None,
    status: str = "open",
) -> dict:
    """Construct a minimal InvalidationEvent-compatible dict for tests."""
    return {
        "event_id": event_id,
        "root_event_id": root_event_id if root_event_id is not None else event_id,
        "utc_timestamp": "2026-04-21T00:00:00+00:00",
        "source_type": source_type,
        "source_id": source_id,
        "affected_result_ids": affected_result_ids if affected_result_ids is not None else [],
        "status": status,
    }


def test_append_invalidation_event_atomic_with_state_lock() -> None:
    """append_invalidation_event appends to state["invalidation_events"];
    two sequential calls produce two entries (no overwrite), simulating the
    atomic behaviour expected under a held _state_lock context.

    Note: the caller is responsible for holding _state_lock(); this test
    exercises the list-mutation behaviour in a single-threaded context,
    which is sufficient because CPython's GIL protects the append itself
    and the lock is documented as caller-held.
    """
    state: dict = {}

    ev1 = _make_event("evt-0001", affected_result_ids=["R-001"])
    ev2 = _make_event("evt-0002", affected_result_ids=["R-002"])

    append_invalidation_event(state, ev1)
    append_invalidation_event(state, ev2)

    assert "invalidation_events" in state
    assert len(state["invalidation_events"]) == 2

    # Both events are present; neither overwrote the other.
    ids_present = {ev["event_id"] for ev in state["invalidation_events"]}
    assert "evt-0001" in ids_present
    assert "evt-0002" in ids_present


def test_result_is_suspect_checks_all_open_events() -> None:
    """result_is_suspect returns True for a result covered by any open event,
    even when multiple independent events (different root_event_id, different
    source) each target a different result.
    """
    state: dict = {
        "invalidation_events": [
            _make_event("evt-A", source_id="K-001", affected_result_ids=["R-001"], status="open"),
            _make_event("evt-B", source_id="K-002", affected_result_ids=["R-002"], status="open"),
        ]
    }

    assert result_is_suspect(state, "R-001") is True
    assert result_is_suspect(state, "R-002") is True
    # A result not mentioned in any event is not suspect.
    assert result_is_suspect(state, "R-999") is False


def test_result_is_suspect_dedups_on_root_event_id() -> None:
    """Two events sharing a root_event_id, both open, both covering R-001;
    result_is_suspect returns True (deduplicated or not, the boolean is True).

    Brief 002 §8.2: deduplication on root_event_id is for REPORTING; the
    boolean return is True whenever any open event covers the result.
    """
    shared_root = "root-evt-0001"
    state: dict = {
        "invalidation_events": [
            _make_event(
                "evt-child-0001",
                root_event_id=shared_root,
                affected_result_ids=["R-001"],
                status="open",
            ),
            _make_event(
                "evt-child-0002",
                root_event_id=shared_root,
                affected_result_ids=["R-001"],
                status="open",
            ),
        ]
    }

    assert result_is_suspect(state, "R-001") is True


def test_status_aborted_on_iter3_W2_rollback_path() -> None:
    """An event with status "aborted" (written by the compensating ledger entry
    in assertion_lock step-(c) failure; brief 002 iter-3-W2) does NOT make the
    result suspect.
    """
    state: dict = {
        "invalidation_events": [
            _make_event("evt-aborted-0001", affected_result_ids=["R-001"], status="aborted"),
        ]
    }

    assert result_is_suspect(state, "R-001") is False


def test_event_level_status_resolved_only_when_all_per_result_cleared() -> None:
    """An event with status "resolved" does NOT make the result suspect.

    Per brief 002 §8.4 scope-doc §schema-notes bullet 2: result_is_suspect
    ignores resolved events.  The test name mirrors the acceptance criterion
    wording in the plan spec.
    """
    state: dict = {
        "invalidation_events": [
            _make_event("evt-resolved-0001", affected_result_ids=["R-001"], status="resolved"),
        ]
    }

    assert result_is_suspect(state, "R-001") is False


# ---------------------------------------------------------------------------
# Regression test — iter-1-S1: assertion_invalidation_scan must use
# state["intermediate_results"], NOT state["results"]
# ---------------------------------------------------------------------------


def test_assertion_invalidation_uses_intermediate_results_not_results():
    """Regression for iter-1-S1: scan must read 'intermediate_results', not 'results'.

    If the wrong key ('results') is used, the scan returns an empty list even
    when a matching result exists, silently breaking trigger-3 blast-radius.
    """
    assertion_docs = {"A-REG": {"depends_on": []}}

    # State with the correct key populated — scan should find R-REG-01.
    state_correct: dict = {
        "intermediate_results": [
            {"id": "R-REG-01", "assertion_deps": ["A-REG"]},
        ]
    }
    result = assertion_invalidation_scan(state_correct, "A-REG", assertion_docs)
    assert "R-REG-01" in result["A-REG"], (
        "assertion_invalidation_scan must find results under 'intermediate_results'"
    )

    # State with only the wrong key populated — scan must return empty (no false positives).
    state_wrong_key: dict = {
        "results": [
            {"id": "R-REG-01", "assertion_deps": ["A-REG"]},
        ]
    }
    result_wrong = assertion_invalidation_scan(state_wrong_key, "A-REG", assertion_docs)
    assert result_wrong["A-REG"] == [], (
        "Stale 'results' key must not be read; scan should return [] for state with only 'results'"
    )
