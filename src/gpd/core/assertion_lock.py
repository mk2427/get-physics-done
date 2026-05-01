"""Assertion-status exclusive lock wrapper + rollback helper (brief 002 §3.4 iter-3-W2).

Public API:

* ``assertion_status_lock(project_root, timeout=30.0)`` — context manager; thin
  pass-through to ``utils.file_lock`` with a 30 s TTL that overrides the 5 s default.
* ``write_upstream_divergence_with_cascade(project_root, assertion_id, kind,
  at_timestamp)`` — three-step write sequence with rollback discipline; MUST be
  called inside an ``assertion_status_lock`` context.

Rollback contract:
  (a) Write ``divergence_detected_at`` into the assertion YAML ``upstream_status_mirror``.
  (b) Append the full ``InvalidationEvent`` schema entry (``status: "open"``) to
      ``GPD/knowledge/invalidation_events.jsonl``; also writes to
      ``state["invalidation_events"]`` when *state* is provided (dual-write).
  (c) Write ``status: Under Review`` into the assertion YAML.

  Failure in (b) → restore pre-write YAML snapshot (undo a); re-raise.
  Failure in (c) → write compensating ``status: aborted`` ledger entry; undo (a); re-raise.
  TTL expiry (TimeoutError from file_lock) → caller's context aborts before any sub-writes.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml

from gpd.core import utils
from gpd.core.assertion_divergence import DivergenceResult  # noqa: F401 — imported for CI gate callers
from gpd.core.blast_radius import append_invalidation_event
from gpd.core.constants import (
    ASSERTION_DIR_NAME,
    INVALIDATION_EVENTS_FILENAME,
    KNOWLEDGE_DIR_NAME,
    PLANNING_DIR_NAME,
    ProjectLayout,
)

__all__ = [
    "assertion_status_lock",
    "write_upstream_divergence_with_cascade",
]


# ─── Lock wrapper ─────────────────────────────────────────────────────────────


@contextmanager
def assertion_status_lock(project_root: Path, timeout: float = 30.0) -> Iterator[None]:
    """Exclusive lock for assertion-status mutations; delegates to utils.file_lock.

    The lock file is ``<project_root>/GPD/locks/assertion_status.lock``.
    ``utils.file_lock`` appends ``.lock`` to the path suffix, so we pass the
    stem path (without ``.lock``) constructed via ``ProjectLayout``.

    Args:
        project_root: Root of the GPD project.
        timeout:      Seconds to wait before raising ``TimeoutError``.  Overrides
                      ``utils.file_lock``'s 5 s default with a 30 s TTL.
    """
    lock_stem = ProjectLayout(project_root).assertion_status_lock
    with utils.file_lock(lock_stem, timeout=timeout):
        yield


# ─── Rollback helper ──────────────────────────────────────────────────────────


def _find_assertion_file(project_root: Path, assertion_id: str) -> Path:
    """Locate an assertion markdown file by scanning the assertions directory."""
    assertions_dir = project_root / PLANNING_DIR_NAME / ASSERTION_DIR_NAME
    for md_file in sorted(assertions_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        if fm.get("assertion_id") == assertion_id:
            return md_file
    raise FileNotFoundError(
        f"No assertion file found for assertion_id={assertion_id!r} in {assertions_dir}"
    )


def _parse_frontmatter(text: str) -> dict:
    """Extract and parse YAML frontmatter from a markdown document."""
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


def _write_frontmatter_field(
    md_path: Path,
    *,
    nested_key: tuple[str, ...] | None = None,
    top_key: str | None = None,
    value: object,
) -> None:
    """Overwrite a single frontmatter field in a markdown document.

    Supports setting a top-level key or a two-level nested key (e.g.
    ``upstream_status_mirror.divergence_detected_at``).
    """
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    # Locate the frontmatter block.
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"No YAML frontmatter found in {md_path}")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError(f"Frontmatter closing '---' not found in {md_path}")

    fm_text = "".join(lines[1:end_idx])
    data = yaml.safe_load(fm_text)
    if not isinstance(data, dict):
        data = {}

    if nested_key is not None and len(nested_key) == 2:
        parent, child = nested_key
        if not isinstance(data.get(parent), dict):
            data[parent] = {}
        data[parent][child] = value
    elif top_key is not None:
        data[top_key] = value
    else:
        raise ValueError("Must provide nested_key or top_key")

    new_fm = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_text = "---\n" + new_fm + "---\n" + "".join(lines[end_idx + 1 :])
    md_path.write_text(new_text, encoding="utf-8")


def write_upstream_divergence_with_cascade(
    project_root: Path,
    assertion_id: str,
    kind: str,
    at_timestamp: str,
    root_event_id: str | None = None,
    state: dict | None = None,
) -> None:
    """Three-step write with rollback discipline (brief 002 §3.4 iter-3-W2).

    Must be called INSIDE an ``assertion_status_lock(project_root)`` context.
    Also callable from the §7.3 CI divergence gate: when ``check_divergence``
    returns FAIL on a Stable assertion, the CI workflow calls this function to
    record the divergence atomically (per ``DivergenceResult`` from
    ``gpd.core.assertion_divergence``).

    Steps:
        (a) Set ``upstream_status_mirror.divergence_detected_at = at_timestamp``.
        (b) Append the full ``InvalidationEvent`` schema entry (``status: "open"``,
            all 7 fields) to ``GPD/knowledge/invalidation_events.jsonl``.  When
            *root_event_id* is supplied (cascade from trigger 2), the ledger entry
            records the parent's ``root_event_id`` instead of this event's own
            ``event_id``, so the full cascade shares one root identity.  When
            *state* is supplied, also calls ``append_invalidation_event(state,
            event)`` so ``state["invalidation_events"]`` stays in sync with the
            durable JSONL ledger (brief 002 §8.4 dual-write discipline).
        (c) Set ``status = "Under Review"`` on the assertion YAML.

    Rollback:
        (b) raises  → restore pre-(a) YAML snapshot; re-raise.
        (c) raises  → append compensating ``{"status": "aborted"}`` entry; restore
                      pre-(a) YAML snapshot; re-raise.

    Args:
        project_root:   Root of the GPD project.
        assertion_id:   Assertion to update (e.g. ``"A-001"``).
        kind:           Divergence kind label (e.g. ``"knowledge_invalidation"``).
        at_timestamp:   ISO-8601 UTC timestamp string for ``divergence_detected_at``.
        root_event_id:  Optional parent root event ID for cascade writes.  When
                        ``None``, the generated ``event_id`` IS the root.
        state:          Optional GPD state dict.  When provided, the
                        ``InvalidationEvent`` written to the JSONL ledger is
                        also appended to ``state["invalidation_events"]`` so
                        that ``result_is_suspect`` can see cascade-triggered
                        events without reading the JSONL file.  Caller must hold
                        ``_state_lock()`` before passing *state*.
    """
    assertion_file = _find_assertion_file(project_root, assertion_id)
    pre_write_snapshot = assertion_file.read_text(encoding="utf-8")

    ledger_path = project_root / PLANNING_DIR_NAME / KNOWLEDGE_DIR_NAME / INVALIDATION_EVENTS_FILENAME
    event_id = str(uuid.uuid4())
    effective_root_event_id = root_event_id if root_event_id is not None else event_id

    # ── Step (a): write divergence_detected_at ────────────────────────────────
    _write_frontmatter_field(
        assertion_file,
        nested_key=("upstream_status_mirror", "divergence_detected_at"),
        value=at_timestamp,
    )

    # ── Step (b): append InvalidationEvent-schema entry to invalidation ledger ──
    # The entry uses the full InvalidationEvent schema (brief 002 §8.3; commit 10d).
    # ``status`` is "open".  When *state* is provided, the same event is also
    # written to ``state["invalidation_events"]`` (brief 002 §8.4 dual-write
    # discipline) so that ``result_is_suspect`` can observe cascade events without
    # reading the JSONL file.
    event_dict = {
        "event_id": event_id,
        "root_event_id": effective_root_event_id,
        "utc_timestamp": at_timestamp,
        "source_type": "assertion",
        "source_id": assertion_id,
        "affected_result_ids": [],
        "status": "open",
    }
    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event_dict) + "\n")
        # Dual-write: keep in-memory state in sync with the durable JSONL ledger.
        if state is not None:
            append_invalidation_event(state, event_dict)
    except Exception:
        # Rollback (a): restore pre-write snapshot.
        assertion_file.write_text(pre_write_snapshot, encoding="utf-8")
        raise

    # ── Step (c): set status = Under Review ───────────────────────────────────
    try:
        _write_frontmatter_field(assertion_file, top_key="status", value="Under Review")
    except Exception:
        # Compensating ledger entry for the already-appended stub.
        try:
            aborted_entry = json.dumps({"event_id": event_id, "status": "aborted"})
            with ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(aborted_entry + "\n")
        except Exception:
            pass  # best-effort; re-raise original below
        # Rollback (a): restore pre-write snapshot.
        assertion_file.write_text(pre_write_snapshot, encoding="utf-8")
        raise
