"""Knowledge-doc runtime hooks (brief 002 §8.1 trigger 2).

Provides reactive triggers that fire when a knowledge document transitions to
``Under Review`` or ``Superseded`` status.  The hook:

1. Scans for all result IDs that depend on the changed knowledge doc.
2. Records an ``InvalidationEvent`` in the state ledger.
3. Cascades the status change to dependent assertions via
   ``write_upstream_divergence_with_cascade`` inside an exclusive lock.

Public API
----------
* ``on_kdoc_status_change(project_root, kdoc_id, new_status, state)``
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from gpd.core.blast_radius import (
    append_invalidation_event,
    knowledge_invalidation_scan,
)
from gpd.core.assertion_lock import assertion_status_lock, write_upstream_divergence_with_cascade

__all__ = ["on_kdoc_status_change"]

_TRIGGER_STATUSES = {"Under Review", "Superseded"}


def on_kdoc_status_change(
    project_root: Path,
    kdoc_id: str,
    new_status: str,
    state: dict,
) -> None:
    """React to a knowledge-doc status transition (trigger 2).

    Called when a knowledge document transitions to ``Under Review`` or
    ``Superseded``.  Safe to call for other status values — returns immediately
    without side effects.

    Steps
    -----
    (1) Run ``knowledge_invalidation_scan`` to find affected result IDs.
    (2) Build and append an ``InvalidationEvent`` to ``state["invalidation_events"]``.
    (3) For every dependent assertion (assertions whose ``knowledge_doc_ids``
        contains *kdoc_id*), call ``write_upstream_divergence_with_cascade``
        inside an ``assertion_status_lock`` context, passing ``root_event_id``
        so the cascade shares the parent event's identity.

    Args:
        project_root: Root of the GPD project (used for the assertion lock path).
        kdoc_id:      Knowledge-doc label, e.g. ``"K-001"``.
        new_status:   Destination status string.  Hook fires only for
                      ``"Under Review"`` and ``"Superseded"``.
        state:        GPD state dict (mutated in-place to record the event).
    """
    if new_status not in _TRIGGER_STATUSES:
        return

    # (1) Scan for affected result IDs.
    scan_result = knowledge_invalidation_scan(state, kdoc_id)
    affected_result_ids: list[str] = scan_result.get(kdoc_id, [])

    # (2) Build and append the InvalidationEvent.
    now_iso = datetime.now(timezone.utc).isoformat()
    root_event_id = str(uuid.uuid4())
    event: dict = {
        "event_id": root_event_id,
        "root_event_id": root_event_id,
        "utc_timestamp": now_iso,
        "source_type": "knowledge",
        "source_id": kdoc_id,
        "affected_result_ids": affected_result_ids,
        "status": "open",
    }
    append_invalidation_event(state, event)

    # (3) Cascade to dependent assertions.
    dependent_assertions = [
        a_id
        for a_id, a_data in state.get("assertions", {}).items()
        if isinstance(a_data, dict) and kdoc_id in a_data.get("knowledge_doc_ids", [])
    ]

    if not dependent_assertions:
        return

    with assertion_status_lock(project_root):
        for assertion_id in dependent_assertions:
            write_upstream_divergence_with_cascade(
                project_root,
                assertion_id,
                kind="knowledge_invalidation",
                at_timestamp=now_iso,
                root_event_id=root_event_id,
                state=state,
            )
