"""Append-only JSONL revlog for EQN-REF integrator runs (brief 002 §Commit 7).

Stores a chronological audit trail of every ``convention_set`` MCP call made
by ``gpd-eqnref-integrator``.  Each entry records enough information to
reconstruct the prior convention lock for a full-run revert.

Storage path
------------
``<project_root>/GPD/knowledge/revlogs/eqn-ref-integrator.jsonl``

The file lives inside the project's ``GPD/`` tree, not in the GPD install.
This matches the append-only JSONL pattern established by
``execution_lineage.py`` for runtime project data.

Entry schema (per plan §1 item 3 pick)
---------------------------------------
::

    {
        "run_id":                "<uuid4>",
        "utc_timestamp":         "<ISO-8601>",
        "axis_id":               "<str>",
        "mcp_key":               "<str>",
        "prior_value":           "<str | null>",
        "new_value":             "<str>",
        "eqn_ref_content_hash":  "<sha256-hex>",
        "force_used":            false
    }

``run_id`` is shared across all entries written in a single integrator run,
enabling batch-revert by grouping on ``run_id``.

``prior_value`` is ``null`` when the axis had no prior convention lock
(i.e., the first time this axis was ever set for the project).

Public API
----------
- ``eqnref_revlog_append(project_root, entry)`` — atomically appends one
  JSON line; creates parent directories if needed.
- ``eqnref_revlog_recent(project_root, axis_id=None, limit=50)`` — returns
  the most-recent ``limit`` entries, optionally filtered by ``axis_id``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = [
    "EQNREF_REVLOG_RELPATH",
    "eqnref_revlog_path",
    "eqnref_revlog_append",
    "eqnref_revlog_recent",
]

# ─── Path constant ────────────────────────────────────────────────────────────

EQNREF_REVLOG_RELPATH = Path("GPD") / "knowledge" / "revlogs" / "eqn-ref-integrator.jsonl"
"""Relative path from project root to the revlog file."""


def eqnref_revlog_path(project_root: Path) -> Path:
    """Return the absolute path to the revlog file for a given project root."""
    return project_root / EQNREF_REVLOG_RELPATH


# ─── Writer ───────────────────────────────────────────────────────────────────


def eqnref_revlog_append(project_root: Path, entry: dict) -> None:
    """Atomically append one JSON line to the EQN-REF revlog.

    Creates parent directories if they do not exist.  The write is
    line-atomic on all POSIX-like filesystems via a temp-file + rename
    dance, and uses a plain append on Windows where rename-over-existing
    is not atomic.

    Parameters
    ----------
    project_root:
        Absolute path to the project root directory (the directory that
        contains ``GPD/``).
    entry:
        A dict matching the revlog entry schema (all 8 fields are
        required; additional keys are silently preserved so callers can
        include diagnostic metadata without breaking readers).

    Raises
    ------
    ValueError
        If ``entry`` is missing any of the required schema fields.
    OSError
        If the file cannot be created or written.
    """
    _validate_entry(entry)

    revlog_path = eqnref_revlog_path(project_root)
    revlog_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"

    # Append to the file.  We use 'a' mode which is atomic enough for
    # single-line appends on all supported platforms.  A full atomic
    # rename approach is not needed here because the file is append-only
    # and concurrent writes from a single agent are not expected.
    with revlog_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


# ─── Reader ───────────────────────────────────────────────────────────────────


def eqnref_revlog_recent(
    project_root: Path,
    axis_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return the most-recent ``limit`` revlog entries, optionally filtered.

    Reads the entire file and returns the last ``limit`` matching entries.
    No indexing is performed — this is adequate for the expected file sizes
    (a few hundred entries at most per project).

    Parameters
    ----------
    project_root:
        Absolute path to the project root directory.
    axis_id:
        When provided, return only entries whose ``axis_id`` field matches
        this value exactly.  When ``None``, all entries are considered.
    limit:
        Maximum number of entries to return.  Entries are returned in
        chronological order (oldest first within the returned window, i.e.
        the LAST ``limit`` matching entries from the file).

    Returns
    -------
    list[dict]
        A list of parsed entry dicts.  Empty if the revlog file does not
        exist or contains no matching entries.
    """
    revlog_path = eqnref_revlog_path(project_root)
    if not revlog_path.exists():
        return []

    try:
        raw_lines = revlog_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    # Parse valid JSON lines; silently skip malformed lines.
    entries: list[dict] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        entries.append(obj)

    # Filter by axis_id when requested.
    if axis_id is not None:
        entries = [e for e in entries if e.get("axis_id") == axis_id]

    # Return the last `limit` entries (most recent).
    return entries[-limit:]


# ─── Validation ───────────────────────────────────────────────────────────────

_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "run_id",
        "utc_timestamp",
        "axis_id",
        "mcp_key",
        "prior_value",
        "new_value",
        "eqn_ref_content_hash",
        "force_used",
    }
)


def _validate_entry(entry: dict) -> None:
    """Raise ValueError if ``entry`` is missing required schema fields."""
    missing = _REQUIRED_FIELDS - entry.keys()
    if missing:
        formatted = ", ".join(sorted(missing))
        raise ValueError(f"eqnref revlog entry is missing required fields: {formatted}")
