"""Blast-radius scanner — identify results invalidated by a knowledge-doc change.

All functions operate on state dicts (the caller handles persistence).
"""

from __future__ import annotations

from collections import deque

__all__ = [
    "knowledge_invalidation_scan",
    "AssertionCycleError",
    "assertion_invalidation_scan",
    "append_invalidation_event",
    "result_is_suspect",
]

# Module-level scan cache.  Key: (kdoc_id, cache_key int).  No threading lock
# needed — CPython's GIL protects plain dict writes at this scale.
_SCAN_CACHE: dict[tuple[str, int], dict[str, list[str]]] = {}


def _cache_key(state: dict) -> int:
    """Return a cache key that changes when dependency inputs change.

    Includes result dependency edges and kdoc statuses so one scan cannot reuse
    another state object's stale affected-result list.
    """
    result_deps: list[tuple[str, tuple[str, ...]]] = []
    for result in state.get("intermediate_results", []):
        if not isinstance(result, dict):
            continue
        rid = str(result.get("id") or "")
        deps = tuple(str(dep) for dep in result.get("knowledge_deps", []) or [])
        result_deps.append((rid, deps))

    kdocs = state.get("knowledge_docs")
    kdoc_statuses: list[tuple[str, str]] = []
    if isinstance(kdocs, list):
        for kdoc in kdocs:
            if not isinstance(kdoc, dict):
                continue
            kdoc_statuses.append(
                (
                    str(kdoc.get("kdoc_id") or kdoc.get("id") or ""),
                    str(kdoc.get("status", "Draft")),
                )
            )
    return hash((tuple(result_deps), tuple(kdoc_statuses)))


def knowledge_invalidation_scan(state: dict, kdoc_id: str) -> dict[str, list[str]]:
    """Return a map from *kdoc_id* to all result IDs that depend on it.

    Iterates over ``state["intermediate_results"]`` and collects every result
    whose ``knowledge_deps`` field contains *kdoc_id*.

    Args:
        state:    GPD state dict.
        kdoc_id:  The knowledge-doc label to query (e.g. ``"K-001"``).

    Returns:
        ``{kdoc_id: [result_id, ...]}`` — value is an empty list when no
        result depends on *kdoc_id*.  The return value is JSON-serializable.
    """
    key = (kdoc_id, _cache_key(state))
    if key in _SCAN_CACHE:
        return _SCAN_CACHE[key]

    dependent_ids: list[str] = []
    for r in state.get("intermediate_results", []):
        if not isinstance(r, dict):
            continue
        if kdoc_id in r.get("knowledge_deps", []):
            rid = r.get("id")
            if rid:
                dependent_ids.append(rid)

    result = {kdoc_id: dependent_ids}
    _SCAN_CACHE[key] = result
    return result


# ---------------------------------------------------------------------------
# Assertion-DAG invalidation scan
# ---------------------------------------------------------------------------


class AssertionCycleError(Exception):
    """Raised when a cycle is detected in the assertion ``depends_on`` DAG."""


def assertion_invalidation_scan(
    state: dict,
    assertion_id: str,
    assertion_docs: dict[str, dict],
) -> dict[str, list[str]]:
    """Return all result IDs transitively dependent on *assertion_id*.

    Walks the assertion ``depends_on`` DAG (BFS) to collect the transitive
    closure of assertion IDs reachable from *assertion_id*, then scans
    ``state["intermediate_results"]`` for any result whose ``assertion_deps``
    contains one of those assertion IDs.

    Args:
        state:          GPD state dict.  Results are read from
                        ``state["intermediate_results"]`` — a list of dicts
                        each with an ``assertion_deps`` field (list of
                        assertion ID strings).
        assertion_id:   The assertion to query (e.g. ``"A-001"``).
        assertion_docs: Pre-loaded mapping of assertion_id → frontmatter dict.
                        Each dict may contain a ``depends_on`` key (list of
                        assertion ID strings).  Populated by the caller from
                        ``GPD/assertions/``; this function performs no file I/O.

    Returns:
        ``{assertion_id: [result_id, ...]}`` — JSON-serializable.  Value is an
        empty list when *assertion_id* is unknown or no results depend on it.

    Raises:
        AssertionCycleError: If a cycle is detected in the ``depends_on`` DAG.
    """
    if assertion_id not in assertion_docs:
        return {assertion_id: []}

    # BFS transitive closure over depends_on edges.
    # Per the spec: enqueue all children unconditionally; detect cycles at pop
    # time (if popped node is already visited → cycle → raise).
    visited: set[str] = set()
    queue: deque[str] = deque([assertion_id])

    while queue:
        node_id = queue.popleft()
        if node_id in visited:
            raise AssertionCycleError(f"Cycle in assertion DAG at {node_id}")
        visited.add(node_id)

        node_doc = assertion_docs.get(node_id, {})
        for child_id in node_doc.get("depends_on", []):
            queue.append(child_id)

    # Collect results whose assertion_deps intersect the reachable set.
    dependent_ids: list[str] = []
    for r in state.get("intermediate_results", []):
        if not isinstance(r, dict):
            continue
        for dep in r.get("assertion_deps", []):
            if dep in visited:
                rid = r.get("id")
                if rid:
                    dependent_ids.append(rid)
                break  # count each result at most once

    return {assertion_id: dependent_ids}


# ---------------------------------------------------------------------------
# Invalidation-events ledger helpers (brief 002 §8.3 + §8.4; commit 10d)
# ---------------------------------------------------------------------------


def append_invalidation_event(state: dict, event: dict) -> None:
    """Append *event* to the ``invalidation_events`` list in *state*.

    **Caller must hold ``_state_lock()``** before calling this function.
    This function does NOT acquire the lock itself — it is the caller's
    responsibility to ensure atomicity (matches the ``_state_lock`` usage
    pattern throughout ``gpd.core.state``).

    Args:
        state: GPD state dict (mutated in-place).
        event: Dict whose keys conform to the ``InvalidationEvent`` schema
               (``event_id``, ``root_event_id``, ``utc_timestamp``,
               ``source_type``, ``source_id``, ``affected_result_ids``,
               ``status``).
    """
    if "invalidation_events" not in state or not isinstance(state["invalidation_events"], list):
        state["invalidation_events"] = []
    state["invalidation_events"].append(event)


def result_is_suspect(state: dict, result_id: str) -> bool:
    """Return ``True`` if *result_id* is covered by any open invalidation event.

    An event "covers" a result when ``result_id in event["affected_result_ids"]``
    and ``event["status"] == "open"``.  Aborted and resolved events are ignored.

    Deduplication note (brief 002 §8.2): multiple events that share the same
    ``root_event_id`` and all affect *result_id* are logically one suspect entry
    for *reporting* purposes.  For this function's boolean return value, we
    simply return ``True`` if ANY open event covers the result — callers that
    need the deduplicated root list should group by ``root_event_id`` themselves.

    Args:
        state:     GPD state dict.
        result_id: The result identifier to query (e.g. ``"R-001"``).

    Returns:
        ``True`` if at least one open invalidation event covers *result_id*;
        ``False`` otherwise (including when the ledger is absent or empty).
    """
    for ev in state.get("invalidation_events", []):
        if not isinstance(ev, dict):
            continue
        if ev.get("status") != "open":
            continue
        if result_id in ev.get("affected_result_ids", []):
            return True
    return False
