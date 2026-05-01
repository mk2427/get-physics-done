"""§7.5 Adversarial-convergence parser (plan-006 §C9).

Per plan-006 §C9 (post-iter-1-M3 fix), this parser does NOT walk
``knowledge_dir`` or ``assertion_dir`` blindly — that would conflate
this run's output with stale leftovers from prior runs. Instead, the
parser takes ``produced_files`` (the cost-log-derived ``error_class ==
"ok"`` set from C4) as the canonical "this run's docs" set, and
checks that every produced doc carries frontmatter ``status: Stable``.

Defense-in-depth (resolves iter-2-M3): if ``produced_files`` is empty
for a run that dispatched ≥1 paper successfully, FAIL with a
diagnostic citing the iter-2-S1 dispatcher gpd_return-block parse-bug
class. The caller signals "≥1 ok dispatch" via the optional kwarg
``n_ok_dispatches``. This blocks the silent green-stamp regression
where a misconfigured digester returns ``ok`` with empty
``files_written``.

User-override (resolves iter-1-W6): per brief 002 §7 criterion 5,
override is "written justification recorded in the canary report" —
a markdown side-channel, NOT a frontmatter field. The CLI flag
``--user-override <doc-id>:<reason>`` is parsed by ``run_canary.py``
and threaded in here as ``user_overrides: list[str]`` (each entry of
the form ``<doc-id>:<reason>``). Override eligibility is restricted
to ``APPROVED-WITH-DEBT`` per plan-006 §C9 step 5 — ``Draft`` and
``Under Review`` are NOT eligible for override.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from . import CriterionResult, CriterionStatus

# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

# Stand-alone YAML frontmatter ``status:`` extractor. We deliberately
# avoid pulling in ``gpd.registry._parse_frontmatter`` (which depends
# on PyYAML and on the broader registry module) — this parser is
# stdlib-only so the canary criteria pkg has no third-party imports.
# Frontmatter format: ``---\n<key>: <val>\n...\n---\n``. We grab the
# first ``status:`` line in the first frontmatter block.
_FRONTMATTER_DELIM_RE = re.compile(r"^---\s*$")
_STATUS_LINE_RE = re.compile(
    r"^status\s*:\s*(?P<value>[^\r\n#]*?)\s*(?:#.*)?$",
    re.MULTILINE,
)
# kdoc_id / assertion_id frontmatter fields.
_KDOC_ID_LINE_RE = re.compile(
    r"^kdoc_id\s*:\s*(?P<value>[^\r\n#]*?)\s*(?:#.*)?$",
    re.MULTILINE,
)
_ASSERTION_ID_LINE_RE = re.compile(
    r"^assertion_id\s*:\s*(?P<value>[^\r\n#]*?)\s*(?:#.*)?$",
    re.MULTILINE,
)

# Statuses that are eligible for user override under §7.5 step 5.
# Anything else (Draft, Under Review) is NOT override-eligible.
_OVERRIDE_ELIGIBLE_STATUSES: frozenset[str] = frozenset({"APPROVED-WITH-DEBT"})

# The single pass-status. Anything else fails by default.
_PASS_STATUS = "Stable"


def _extract_frontmatter_block(text: str) -> str | None:
    """Return the first YAML frontmatter block (without delimiters)."""
    # Strip BOM if present so the very first character matches ``---``.
    text = text.lstrip("\ufeff")
    lines = text.splitlines(keepends=False)
    if not lines or not _FRONTMATTER_DELIM_RE.match(lines[0]):
        return None
    block: list[str] = []
    for line in lines[1:]:
        if _FRONTMATTER_DELIM_RE.match(line):
            return "\n".join(block)
        block.append(line)
    # No closing delimiter — malformed frontmatter; treat as absent.
    return None


def _strip_yaml_quotes(value: str) -> str:
    """Strip surrounding single/double quotes from a scalar YAML value."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _read_status(path: Path) -> str | None:
    """Return the ``status:`` frontmatter value from a markdown file.

    Returns ``None`` when:
    * the file is missing or unreadable;
    * there is no frontmatter block;
    * the frontmatter block does not declare ``status:``.

    The empty-string status (``status:`` with no value) returns the
    empty string — that is distinguishable from ``None`` so callers
    can render a different diagnostic if desired.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    block = _extract_frontmatter_block(text)
    if block is None:
        return None
    match = _STATUS_LINE_RE.search(block)
    if match is None:
        return None
    return _strip_yaml_quotes(match.group("value"))


def _read_doc_id(path: Path) -> str | None:
    """Return the doc-id (``kdoc_id`` or ``assertion_id``) from frontmatter.

    For knowledge docs the canonical id field is ``kdoc_id``; for
    assertion docs it is ``assertion_id``. We try kdoc_id first, then
    fall back to assertion_id; if neither is present we synthesize an
    id from the file stem so the override map can still address the
    doc by basename.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return path.stem or None
    block = _extract_frontmatter_block(text)
    if block is None:
        return path.stem or None
    for pattern in (_KDOC_ID_LINE_RE, _ASSERTION_ID_LINE_RE):
        match = pattern.search(block)
        if match is not None:
            stripped = _strip_yaml_quotes(match.group("value"))
            if stripped:
                return stripped
    return path.stem or None


# ---------------------------------------------------------------------------
# Override parsing
# ---------------------------------------------------------------------------


def _parse_user_overrides(
    user_overrides: Iterable[str] | None,
) -> dict[str, str]:
    """Parse ``--user-override <doc-id>:<reason>`` entries into a dict.

    Splits on the FIRST ``:`` (the reason may itself contain colons,
    e.g., ``K-007:upstream typo: see brief 002 §3.4``). Empty entries
    or entries without a ``:`` separator are silently dropped — the
    CLI parser in ``run_canary.py`` is responsible for shape-checking.
    """
    if not user_overrides:
        return {}
    result: dict[str, str] = {}
    for raw in user_overrides:
        if not isinstance(raw, str) or ":" not in raw:
            continue
        doc_id, _, reason = raw.partition(":")
        doc_id = doc_id.strip()
        reason = reason.strip()
        if not doc_id:
            continue
        result[doc_id] = reason
    return result


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------


def check(
    produced_files: list[Path] | list[str],
    knowledge_dir: Path,
    assertion_dir: Path,
    truth_table: dict | None = None,
    user_overrides: list[str] | None = None,
    *,
    n_ok_dispatches: int = 0,
) -> CriterionResult:
    """§7.5 — every produced doc must be ``status: Stable``.

    Parameters
    ----------
    produced_files:
        The cost-log-derived ``error_class == "ok"`` files set from C4
        (i.e., ``⋃ entry.files_written`` over ok entries). Each entry
        may be a :class:`pathlib.Path` or a path-like string. The
        parser does NOT walk ``knowledge_dir`` / ``assertion_dir``
        blindly — that would conflate this run's output with stale
        leftovers from prior runs (resolves iter-1-M3).
    knowledge_dir, assertion_dir:
        Sandbox directories; used only for partitioning produced
        files into kdoc-vs-assertion buckets in the diagnostic detail
        (the status check itself is path-agnostic).
    truth_table:
        Unused for §7.5; accepted to keep the criteria-module
        signature uniform with §7.1–§7.6.
    user_overrides:
        Optional repeatable ``--user-override <doc-id>:<reason>`` CLI
        entries. Each parsed (doc-id, reason) pair grants PASS to a
        single doc whose frontmatter status is one of the override-
        eligible values (currently only ``APPROVED-WITH-DEBT``).
    n_ok_dispatches:
        Optional count of cost-log entries with ``error_class == "ok"``
        for THIS run, supplied by the caller. Used by the iter-2-M3
        defense-in-depth post-condition: if ``produced_files`` is
        empty AND ``n_ok_dispatches >= 1``, FAIL with the documented
        iter-2-S1 dispatcher-bug diagnostic. Default 0 (i.e., no
        ok-dispatch context known) — empty ``produced_files`` is then
        treated as a vacuous PASS, suitable for unit fixtures that do
        not exercise the dispatcher path.

    Returns
    -------
    :class:`CriterionResult`
        ``PASS`` iff every produced doc has ``status: Stable`` (or is
        ``APPROVED-WITH-DEBT`` covered by an explicit override).
        ``FAIL`` with a per-doc breakdown otherwise. The
        ``payload`` carries structured fields ``honored_overrides``
        and ``override_records`` — the caller writes the latter into
        the canary report's ``## User overrides`` markdown section.
    """
    # Coerce inputs to Path for path-arithmetic; string entries work fine.
    files: list[Path] = [Path(p) for p in (produced_files or [])]
    overrides = _parse_user_overrides(user_overrides)

    # ----- Defense-in-depth (iter-2-M3) -----
    # Empty produced_files + ≥1 ok dispatch ⇒ HARD FAIL. This blocks
    # the silent green-stamp regression where a misconfigured digester
    # returns ok with empty files_written (iter-2-S1 dispatcher bug
    # class).
    if not files and n_ok_dispatches >= 1:
        return CriterionResult(
            name="Adversarial convergence",
            status=CriterionStatus.FAIL,
            summary=(
                "FAIL: dispatcher returned ok with empty files_written "
                f"for {n_ok_dispatches} paper(s) — likely "
                "gpd_return-block parse bug (iter-2-S1), NOT a green "
                "canary."
            ),
            details=[
                f"n_ok_dispatches={n_ok_dispatches} but produced_files=[].",
                "Per plan-006 §C9 iter-2-M3 defense-in-depth: this is a "
                "FAIL, not a vacuous PASS. See dispatcher gpd_return-"
                "block parsing in tests/canary/dispatch_skill.py "
                "(iter-2-S1 fix).",
            ],
            payload={
                "n_ok_dispatches": n_ok_dispatches,
                "produced_files": [],
                "honored_overrides": {},
                "override_records": [],
                "fail_reason": "iter-2-M3-empty-produced-files",
            },
        )

    # ----- Per-doc status walk -----
    knowledge_dir = Path(knowledge_dir)
    assertion_dir = Path(assertion_dir)

    pass_paths: list[Path] = []
    fail_records: list[dict] = []
    honored_overrides: dict[str, dict] = {}
    override_records: list[dict] = []

    for path in files:
        status = _read_status(path)
        doc_id = _read_doc_id(path)

        if status == _PASS_STATUS:
            pass_paths.append(path)
            continue

        # Override eligibility: must be in the override-eligible set
        # AND addressed in user_overrides by either doc_id (preferred)
        # or path stem (fallback for unparseable kdoc_id frontmatter).
        if status in _OVERRIDE_ELIGIBLE_STATUSES:
            override_key = None
            if doc_id is not None and doc_id in overrides:
                override_key = doc_id
            elif path.stem in overrides:
                override_key = path.stem

            if override_key is not None:
                reason = overrides[override_key]
                record = {
                    "doc_id": doc_id or path.stem,
                    "path": path.as_posix(),
                    "status": status,
                    "reason": reason,
                }
                honored_overrides[override_key] = record
                override_records.append(record)
                pass_paths.append(path)
                continue

        # Not Stable, not an honored override — record the failure.
        fail_records.append(
            {
                "doc_id": doc_id or path.stem,
                "path": path.as_posix(),
                "status": status if status is not None else "<missing>",
                "override_eligible": status in _OVERRIDE_ELIGIBLE_STATUSES,
            }
        )

    # ----- Verdict -----
    n_total = len(files)
    n_pass = len(pass_paths)
    n_fail = len(fail_records)
    n_overrides = len(honored_overrides)

    if n_fail == 0:
        # PASS — possibly via override(s).
        summary_bits = [f"PASS: {n_pass}/{n_total} produced docs Stable"]
        if n_overrides:
            summary_bits.append(
                f"({n_overrides} APPROVED-WITH-DEBT override"
                f"{'s' if n_overrides != 1 else ''} honored)"
            )
        return CriterionResult(
            name="Adversarial convergence",
            status=CriterionStatus.PASS,
            summary=" ".join(summary_bits),
            details=[
                f"  - override: {rec['doc_id']} ({rec['status']}) — "
                f"reason: {rec['reason']}"
                for rec in override_records
            ],
            payload={
                "n_total": n_total,
                "n_pass": n_pass,
                "n_overrides_honored": n_overrides,
                "honored_overrides": honored_overrides,
                "override_records": override_records,
                "produced_files": [p.as_posix() for p in files],
            },
        )

    # FAIL — list each non-Stable doc.
    details = [
        f"{n_fail}/{n_total} produced doc(s) not Stable; no override "
        "covers them."
    ]
    for rec in fail_records:
        eligibility = (
            "override-eligible (APPROVED-WITH-DEBT)"
            if rec["override_eligible"]
            else "NOT override-eligible"
        )
        details.append(
            f"  - {rec['doc_id']} (status={rec['status']!r}, "
            f"{eligibility}) at {rec['path']}"
        )
    return CriterionResult(
        name="Adversarial convergence",
        status=CriterionStatus.FAIL,
        summary=(
            f"FAIL: {n_fail}/{n_total} produced doc(s) not Stable "
            f"and not covered by override"
        ),
        details=details,
        payload={
            "n_total": n_total,
            "n_pass": n_pass,
            "n_fail": n_fail,
            "n_overrides_honored": n_overrides,
            "fail_records": fail_records,
            "honored_overrides": honored_overrides,
            "override_records": override_records,
            "produced_files": [p.as_posix() for p in files],
        },
    )


__all__ = ["check"]
