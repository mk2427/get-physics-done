"""Per-paper cost-log helper for the BFSS canary (plan-006 §C4).

Atomic JSONL append + read + manifest verification + resume support.
Stdlib only; no GPD core imports — this module is standalone.

Public surface:

* ``_LOCK`` — module-level :class:`threading.Lock`. Serializes both
  cost-log appends here AND ``BudgetTracker.record`` calls in
  ``run_canary.py`` so the two writes are observed as a single atomic
  step (plan-006 §C3 lines 273-291).
* :func:`append_paper_cost` — atomic JSONL append with the canonical
  per-paper schema (plan-006 §C3 lines 244-258).
* :func:`read_cost_log` — read all entries as ``list[dict]`` in file
  order; returns ``[]`` if the file does not exist.
* :func:`verify_log_against_manifest` — diff log vs manifest; returns
  ``{missing, extra, duplicates}``.
* :func:`completed_arxiv_ids` — set of arxiv_ids whose **latest** entry
  has ``error_class == "ok"``. Latest = max(``completed_at``); on tie,
  last-line-wins (resolves iter-2-W2).

Atomic-write strategy: ``tmp.write_text(...); tmp.replace(log_path)``.
The replace is the atomic step on POSIX and on Windows (``os.replace``
is documented atomic since CPython 3.3).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

# Module-level lock. Imported by run_canary.py to serialize cost-log
# appends with BudgetTracker.record (plan-006 §C3 lines 273-291).
_LOCK: threading.Lock = threading.Lock()


# Fields that must be present in a cost-log entry. Defined here (not in
# dispatch_skill) because the cost-log schema is the durable on-disk
# contract; the dispatch return shape is the in-memory supplier.
_SCHEMA_FIELDS: tuple[str, ...] = (
    "arxiv_id",
    "kdoc_paths",
    "n_assertions",
    "assertion_paths",
    "kdoc_statuses",
    "cost_usd",
    "token_cost",
    "wall_clock_seconds",
    "completed_at",
    "claude_session_id",
    "error_class",
)


def _build_entry(
    arxiv_id: str,
    kdoc_paths: list[Path],
    dispatch_result: dict[str, Any],
) -> dict[str, Any]:
    """Project a dispatch result into the canonical cost-log schema.

    Missing numeric fields default to 0 / 0.0 (matches
    ``dispatch_skill._base_return``). ``completed_at`` and
    ``claude_session_id`` may be ``None`` if the caller has not supplied
    them — both are accepted by the schema.
    """
    input_tokens = int(dispatch_result.get("input_tokens") or 0)
    output_tokens = int(dispatch_result.get("output_tokens") or 0)
    token_cost = (
        dispatch_result.get("token_cost")
        if dispatch_result.get("token_cost") is not None
        else input_tokens + output_tokens
    )
    def _to_posix(p: Any) -> str:
        # Normalize to POSIX form so the on-disk cost log is portable
        # across Windows / POSIX (canonical citation paths in kdocs use
        # forward slashes; mixing in `\` would break downstream parsers).
        if isinstance(p, Path):
            return p.as_posix()
        return str(p).replace("\\", "/")

    return {
        "arxiv_id": arxiv_id,
        "kdoc_paths": [_to_posix(p) for p in (kdoc_paths or [])],
        "n_assertions": int(dispatch_result.get("n_assertions") or 0),
        "assertion_paths": [
            _to_posix(p) for p in (dispatch_result.get("assertion_paths") or [])
        ],
        "kdoc_statuses": dict(dispatch_result.get("kdoc_statuses") or {}),
        "cost_usd": float(dispatch_result.get("cost_usd") or 0.0),
        "token_cost": int(token_cost or 0),
        "wall_clock_seconds": float(
            dispatch_result.get("wall_clock_seconds")
            or (
                (dispatch_result.get("duration_ms") or 0) / 1000.0
                if dispatch_result.get("duration_ms")
                else 0.0
            )
        ),
        "completed_at": dispatch_result.get("completed_at"),
        "claude_session_id": dispatch_result.get(
            "claude_session_id", dispatch_result.get("session_id")
        ),
        "error_class": dispatch_result.get("error_class"),
    }


def _append_paper_cost_locked(
    arxiv_id: str,
    kdoc_paths: list[Path],
    dispatch_result: dict[str, Any],
    *,
    log_path: Path,
) -> None:
    """Append-under-caller-held-lock variant of :func:`append_paper_cost`.

    Used by ``run_canary.py``'s budget-tracker critical section, which
    holds :data:`_LOCK` across both the append AND the budget bump.
    ``threading.Lock`` is non-reentrant, so the public
    :func:`append_paper_cost` must NOT be called while the caller holds
    :data:`_LOCK` — call this function instead.
    """
    log_path = Path(log_path)
    entry = _build_entry(arxiv_id, kdoc_paths, dispatch_result)
    new_line = json.dumps(entry, sort_keys=True) + "\n"

    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
    else:
        existing = ""
        log_path.parent.mkdir(parents=True, exist_ok=True)
    contents = existing + new_line

    # Use a NamedTemporaryFile in the same directory so os.replace
    # stays on the same filesystem (a cross-fs replace would not be
    # atomic). delete=False because we replace the file ourselves.
    tmp_dir = log_path.parent
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(tmp_dir),
        prefix=log_path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as fh:
        tmp_path = Path(fh.name)
        fh.write(contents)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        tmp_path.replace(log_path)
    except OSError:
        # On replace failure, leave log_path untouched. Best-effort
        # cleanup of the orphan tmp; ignore if it's already gone.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def append_paper_cost(
    arxiv_id: str,
    kdoc_paths: list[Path],
    dispatch_result: dict[str, Any],
    *,
    log_path: Path,
) -> None:
    """Atomically append one paper's cost entry to ``log_path`` (JSONL).

    Strategy: under :data:`_LOCK`, read the current file (or empty
    string), concatenate the new line, write to a sibling ``.tmp`` file,
    then ``os.replace`` it onto ``log_path``. The replace is atomic on
    POSIX and Windows; readers will never see a torn line.

    Notes
    -----
    * Writing the WHOLE file each call (not just the new line) is
      deliberate — JSONL append-via-replace requires re-materializing
      prior content because ``os.replace`` is atomic at the file level,
      not at the byte-range level. The cost log is small (≤ corpus
      size, ~16 entries for BFSS) so this is a non-issue.
    * If ``tmp.replace`` fails after ``tmp.write_text`` has succeeded,
      ``log_path`` is unchanged and the partial ``.tmp`` file is left on
      disk for forensics (and removed on retry).
    * Callers that need to hold :data:`_LOCK` for a wider critical
      section (e.g. budget-tracker increment) must use
      :func:`_append_paper_cost_locked` directly to avoid the
      non-reentrant ``threading.Lock`` deadlock.
    """
    with _LOCK:
        _append_paper_cost_locked(
            arxiv_id, kdoc_paths, dispatch_result, log_path=log_path
        )


def read_cost_log(log_path: Path) -> list[dict]:
    """Return all entries from ``log_path`` in file order.

    Returns ``[]`` if the file does not exist (canary's first-run case).
    Skips blank lines but raises on malformed JSON — silent corruption
    in the cost log would defeat the resume-safety guarantee.
    """
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    entries: list[dict] = []
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


def verify_log_against_manifest(
    log: list[dict], manifest: dict
) -> dict[str, list[str]]:
    """Diff ``log`` against ``manifest['entries']``.

    Returns
    -------
    dict
        ``{"missing": [...], "extra": [...], "duplicates": [...]}``

        * **missing**: arxiv_ids in the manifest with no log entry
          (preserves manifest order).
        * **extra**: arxiv_ids in the log with no manifest entry
          (preserves log order; deduped).
        * **duplicates**: arxiv_ids appearing more than once in the log
          (preserves log order of first occurrence; deduped).
    """
    manifest_ids = [e["arxiv_id"] for e in (manifest.get("entries") or [])]
    manifest_set = set(manifest_ids)

    log_ids = [e["arxiv_id"] for e in log]
    log_set = set(log_ids)

    missing = [aid for aid in manifest_ids if aid not in log_set]

    extra_seen: set[str] = set()
    extra: list[str] = []
    for aid in log_ids:
        if aid not in manifest_set and aid not in extra_seen:
            extra.append(aid)
            extra_seen.add(aid)

    counts: dict[str, int] = {}
    for aid in log_ids:
        counts[aid] = counts.get(aid, 0) + 1
    dup_seen: set[str] = set()
    duplicates: list[str] = []
    for aid in log_ids:
        if counts[aid] > 1 and aid not in dup_seen:
            duplicates.append(aid)
            dup_seen.add(aid)

    return {"missing": missing, "extra": extra, "duplicates": duplicates}


def completed_arxiv_ids(log: list[dict]) -> set[str]:
    """Return arxiv_ids whose **latest** entry has ``error_class == 'ok'``.

    Tie-breaker (resolves iter-2-W2): for entries sharing the same
    ``completed_at`` timestamp, the entry that appears LAST in file
    order wins. The cost log is append-only, so file order is the
    canonical secondary sort key.

    Implementation: walk ``log`` in order; for each arxiv_id keep the
    entry whose ``completed_at`` is ≥ the current best (``≥`` — not
    ``>`` — gives last-line-wins on tie). Then filter to
    ``error_class == 'ok'``.

    A missing or ``None`` ``completed_at`` is treated as the empty
    string for ordering purposes; this is consistent because ISO-8601
    timestamps are lexicographically ordered, and the empty string is
    less than any real timestamp.
    """
    latest: dict[str, dict] = {}
    for entry in log:
        aid = entry.get("arxiv_id")
        if aid is None:
            continue
        ts = entry.get("completed_at") or ""
        prev = latest.get(aid)
        if prev is None:
            latest[aid] = entry
            continue
        prev_ts = prev.get("completed_at") or ""
        # >= so a later file-order entry with equal ts wins (last-line).
        if ts >= prev_ts:
            latest[aid] = entry
    return {aid for aid, entry in latest.items() if entry.get("error_class") == "ok"}
