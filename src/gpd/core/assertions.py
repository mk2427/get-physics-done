"""Lightweight assertion-document loader for GPD/assertions/*.md files.

Provides the ``Assertion`` dataclass and two loader functions that parse YAML
frontmatter from assertion Markdown documents.  No CLI CRUD in this module;
lifecycle management is handled by separate tooling.

Also provides ``on_assertion_status_change`` — the trigger-3 reactive hook
(brief 002 §8.1) that fires when an assertion transitions to Under Review or
Superseded and records an ``InvalidationEvent`` in the state ledger.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gpd.core.blast_radius import (
    AssertionCycleError,  # noqa: F401 — re-exported for callers
    append_invalidation_event,
    assertion_invalidation_scan,
)

__all__ = [
    "Assertion",
    "load_assertion",
    "load_assertions",
    "on_assertion_status_change",
]

logger = logging.getLogger(__name__)


@dataclass
class Assertion:
    """Parsed representation of a ``GPD/assertions/A-NNN-*.md`` document."""

    assertion_id: str
    status: str                                                # Draft | Under Review | Stable | Superseded
    title: str = ""
    depends_on: list[str] = field(default_factory=list)        # A-NNN ids
    knowledge_doc_ids: list[str] = field(default_factory=list)
    eqn_ref_entries: list[str] = field(default_factory=list)
    load_bearing: bool = False
    upstream_ref_hash: str | None = None


def load_assertion(path: Path) -> Assertion:
    """Parse a single assertion ``.md`` file and return an ``Assertion``.

    Extracts the YAML frontmatter block (text between the first ``---`` line
    and the second ``---`` line) and constructs an :class:`Assertion` from it.
    Optional fields that are absent in the frontmatter fall back to the
    dataclass defaults.

    Args:
        path: Absolute or relative path to the ``.md`` assertion file.

    Returns:
        A populated :class:`Assertion` instance.

    Raises:
        ValueError: If the file has no valid YAML frontmatter block, or if the
                    ``assertion_id`` field is absent from the frontmatter.
    """
    content = path.read_text(encoding="utf-8")

    # Split on "---" delimiters.  For a file that starts with "---\n", the
    # result of split("---") is:  ["", " frontmatter ", " body ..."].
    parts = content.split("---")
    if len(parts) < 3:
        raise ValueError(
            f"No valid YAML frontmatter block found in {path}. "
            "Expected content delimited by '---' ... '---'."
        )

    # parts[0] is the text before the first "---" (empty when file starts with it).
    # parts[1] is the frontmatter YAML.
    frontmatter_text = parts[1]
    fm = yaml.safe_load(frontmatter_text)

    if not isinstance(fm, dict):
        raise ValueError(f"Frontmatter in {path} did not parse to a mapping.")

    assertion_id = fm.get("assertion_id")
    if not assertion_id:
        raise ValueError(
            f"Frontmatter in {path} is missing required field 'assertion_id'."
        )

    return Assertion(
        assertion_id=str(assertion_id),
        status=str(fm.get("status", "Draft")),
        title=str(fm.get("title", fm.get("topic", ""))),
        depends_on=list(fm.get("depends_on") or []),
        knowledge_doc_ids=list(fm.get("knowledge_doc_ids") or []),
        eqn_ref_entries=list(fm.get("eqn_ref_entries") or []),
        load_bearing=bool(fm.get("load_bearing", False)),
        upstream_ref_hash=fm.get("upstream_ref_hash") or None,
    )


def load_assertions(assertions_dir: Path) -> dict[str, Assertion]:
    """Load all ``*.md`` assertion files from *assertions_dir*.

    Globs ``*.md`` in the given directory, calls :func:`load_assertion` on
    each, and returns a mapping ``{assertion_id: Assertion}``.  Files that
    raise :exc:`ValueError` (missing frontmatter or missing ``assertion_id``)
    are skipped with a WARNING log.

    Args:
        assertions_dir: Directory to search for assertion documents.

    Returns:
        Dict mapping each successfully loaded assertion's ID to its
        :class:`Assertion` instance.
    """
    result: dict[str, Assertion] = {}
    for md_path in sorted(assertions_dir.glob("*.md")):
        try:
            assertion = load_assertion(md_path)
        except ValueError as exc:
            logger.warning("Skipping %s: %s", md_path.name, exc)
            continue
        result[assertion.assertion_id] = assertion
    return result


# ---------------------------------------------------------------------------
# Reactive trigger 3 — assertion status-change hook (brief 002 §8.1)
# ---------------------------------------------------------------------------

_TRIGGER_STATUSES = {"Under Review", "Superseded"}


def on_assertion_status_change(
    project_root: Path,  # noqa: ARG001 — reserved for future lock-path use
    assertion_id: str,
    new_status: str,
    state: dict,
    assertion_docs: dict[str, dict],
) -> None:
    """React to an assertion status transition (trigger 3).

    Fires when an assertion transitions to ``Under Review`` or ``Superseded``.
    Safe to call for other status values — returns immediately without side
    effects.

    Steps
    -----
    (1) Call ``assertion_invalidation_scan`` to traverse the assertion DAG and
        find all transitively dependent result IDs.
    (2) Build and append an ``InvalidationEvent`` (``source_type="assertion"``)
        to ``state["invalidation_events"]``.

    Args:
        project_root:    Root of the GPD project (reserved; not used currently).
        assertion_id:    Assertion label, e.g. ``"A-001"``.
        new_status:      Destination status string.
        state:           GPD state dict (mutated in-place).
        assertion_docs:  Pre-loaded mapping of assertion_id → frontmatter dict
                         (same format expected by ``assertion_invalidation_scan``).
    """
    if new_status not in _TRIGGER_STATUSES:
        return

    scan_result = assertion_invalidation_scan(state, assertion_id, assertion_docs)
    affected_result_ids: list[str] = scan_result.get(assertion_id, [])

    now_iso = datetime.now(timezone.utc).isoformat()
    event_id = str(uuid.uuid4())
    event: dict = {
        "event_id": event_id,
        "root_event_id": event_id,
        "utc_timestamp": now_iso,
        "source_type": "assertion",
        "source_id": assertion_id,
        "affected_result_ids": affected_result_ids,
        "status": "open",
    }
    append_invalidation_event(state, event)
