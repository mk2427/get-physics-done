"""`claude -p` subprocess bridge for canary skill dispatch.

Per plan-006 §C3, this module exposes ``dispatch_digest_knowledge`` and
``dispatch_digest_assertion`` — thin wrappers around the headless
``claude -p`` CLI that run the GPD digester skills against a single paper
or kdoc and return a normalized result dict.

Key invariants (all per plan-006 §C3):

* The ``--add-dir`` whitelist is **explicit** — only the kwargs dirs are
  granted; the project root is NEVER added (resolves iter-1-M7).
* The return shape is uniform across the four ``error_class`` values
  ``{ok, skill_error, subprocess_error, timeout}`` with explicit-zero
  defaults for missing numeric fields (resolves iter-1-W1).
* ``files_written`` is parsed from the ``gpd_return`` YAML block embedded
  inside ``payload['result']`` text, NOT from a top-level envelope field
  (resolves iter-2-S1). The canonical block regex and field parser are
  imported from ``gpd.core.commands`` to ensure parity with
  ``/gpd:validate-return``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

# Reuse the canonical YAML-block parsers from gpd.core.commands so the
# dispatcher and `gpd:validate-return` agree on what counts as a valid
# `gpd_return` block (resolves iter-2-S1). Verified at:
#   src/gpd/core/commands.py:788  -> _GPD_RETURN_BLOCK_RE
#   src/gpd/core/commands.py:816  -> _parse_gpd_return_fields
from gpd.core.commands import _GPD_RETURN_BLOCK_RE, _parse_gpd_return_fields

def _resolve_claude_cli() -> str:
    """Locate the ``claude`` CLI executable, with Windows shim support.

    On Windows the npm-installed ``claude`` package ships three shims
    in ``%APPDATA%\\npm\\``: ``claude`` (Bash), ``claude.cmd`` (cmd),
    and ``claude.ps1`` (PowerShell). Python's ``subprocess.run`` on
    Windows uses ``CreateProcess`` which does NOT search ``PATHEXT``
    when given a bare name like ``claude``; it can only execute the
    ``.cmd`` / ``.exe`` shims. ``shutil.which`` performs the right
    lookup (honors ``PATHEXT`` on Windows; returns the bare path on
    POSIX) so we use it here.
    """
    found = shutil.which("claude")
    if found is None:
        raise RuntimeError(
            "`claude` CLI not found on PATH; install Claude Code or "
            "add the npm bin dir to PATH"
        )
    return found


CLAUDE_CLI = _resolve_claude_cli()


def _base_return() -> dict[str, Any]:
    """Normalized return shape (resolves iter-1-W1).

    Every dispatch path returns the same key set, with explicit zero
    defaults for missing numeric fields and an explicit ``error_class``.
    """
    return {
        "error_class": None,
        "status": None,
        "result_text": "",
        "cost_usd": 0.0,
        "duration_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "session_id": None,
        "files_written": [],
        "returncode": None,
        "stderr": "",
    }


def _build_cmd(
    prompt: str,
    *,
    write_dirs: list[Path],
    read_dirs: list[Path],
    extra_allowed_dirs: list[Path] | None,
    max_budget_usd: float,
    model: str,
) -> list[str]:
    """Build the ``claude -p`` argv with an explicit (no-project-root)
    ``--add-dir`` whitelist.

    Per plan-006 §C3 (iter-1-M7): the whitelist is the set of
    sandbox/source dirs the kwargs explicitly grant — NOT project_root.
    Adding project_root would expose ``.git/``, ``src/``, ``tests/``
    trees that the canary skill has no business writing to.
    """
    cmd = [
        CLAUDE_CLI,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--allow-dangerously-skip-permissions",
        "--max-budget-usd",
        str(max_budget_usd),
        "--model",
        model,
    ]
    for d in (*write_dirs, *read_dirs, *(extra_allowed_dirs or [])):
        cmd.extend(["--add-dir", str(d)])
    return cmd


def _harvest_new_files(write_dirs: list[Path], since: float) -> list[str]:
    """Enumerate ``K-*.md`` / ``A-*.md`` files under ``write_dirs`` whose
    mtime is newer than ``since`` (a Unix timestamp from ``time.time()``).

    Used as fallback when the slash-skill's terminal ``payload['result']``
    doesn't carry the agent's ``gpd_return.files_written`` YAML block
    (which is the common case under ``claude -p --output-format json``:
    only the FINAL response is captured, so any ``gpd_return`` emitted
    by the digester DURING its turn is lost). The agent's actual writes
    persist to disk regardless, so an mtime-after-start scan reliably
    recovers ``files_written`` for a single-paper or sequential dispatch.

    Concurrency note (iter-1-S5 carry-over): with ``--parallel N > 1``
    this scan can attribute thread B's writes to thread A if their
    dispatch windows overlap. Acceptable for digest-knowledge because
    each paper produces a unique K-NNN slug (collision-free); the
    canary-driver-level cost-log de-duplicates by arxiv_id afterwards.
    For digest-assertion, A-NNN slugs are also paper-scoped so the same
    holds.
    """
    new_files: list[str] = []
    for d in write_dirs:
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            name = p.name
            if not (name.endswith(".md")):
                continue
            if not (name.startswith("K-") or name.startswith("A-")):
                continue
            try:
                if p.stat().st_mtime > since:
                    new_files.append(str(p))
            except OSError:
                continue
    new_files.sort()
    return new_files


def _parse_files_written(result_text: str) -> list[str] | None:
    """Extract ``files_written`` from the ``gpd_return`` YAML block.

    Returns ``None`` if no block is found (caller must classify as
    skill_error per iter-2-S1). Returns a (possibly empty) list of
    strings if a block exists but ``files_written`` is missing or empty.
    """
    block_match = _GPD_RETURN_BLOCK_RE.search(result_text)
    if block_match is None:
        return None
    fields = _parse_gpd_return_fields(block_match.group(1))
    raw = fields.get("files_written") or []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def _dispatch(
    prompt: str,
    *,
    write_dirs: list[Path],
    read_dirs: list[Path],
    extra_allowed_dirs: list[Path] | None,
    max_budget_usd: float,
    timeout_s: int,
    model: str,
) -> dict[str, Any]:
    """Shared dispatcher used by both digest-knowledge and digest-assertion.

    Always returns a dict matching ``_base_return()``'s key set with
    ``error_class`` set to one of ``{ok, skill_error, subprocess_error,
    timeout}``.
    """
    base = _base_return()
    cmd = _build_cmd(
        prompt,
        write_dirs=write_dirs,
        read_dirs=read_dirs,
        extra_allowed_dirs=extra_allowed_dirs,
        max_budget_usd=max_budget_usd,
        model=model,
    )
    dispatch_start = time.time()
    try:
        # encoding="utf-8" + errors="replace" overrides Windows' default
        # cp1252 codec which crashes on Greek/math symbols emitted by the
        # agent (UnicodeDecodeError in subprocess._readerthread). errors=
        # "replace" preserves the rest of the stream when one byte is
        # un-decodable.
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        return {
            **base,
            "error_class": "timeout",
            "status": "timeout",
            "stderr": str(e)[-2000:],
        }
    if proc.returncode != 0:
        return {
            **base,
            "error_class": "subprocess_error",
            "status": "subprocess_error",
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-2000:],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {
            **base,
            "error_class": "subprocess_error",
            "status": "subprocess_error",
            "returncode": proc.returncode,
            "stderr": f"could not parse claude stdout as JSON: {e}",
        }

    usage = payload.get("usage") or {}
    result_text = payload.get("result", "") or ""
    cost_usd = payload.get("total_cost_usd") or 0.0

    files_written = _parse_files_written(result_text)
    if files_written is None:
        # No gpd_return block in payload['result'] — common under
        # `claude -p --output-format json` because only the FINAL skill
        # response is captured, and the digester's gpd_return YAML block
        # is emitted DURING its turn (mid-skill), not at the terminal.
        # Fall back to mtime-based harvest of write_dirs to recover
        # files_written. Agent's writes persist to disk regardless of
        # whether the YAML block survives the JSON envelope round-trip.
        harvested = _harvest_new_files(list(write_dirs), since=dispatch_start)
        if not harvested:
            # Both gpd_return AND mtime-harvest empty: no files detected.
            # This IS a real skill_error — agent didn't produce anything.
            return {
                **base,
                "error_class": "skill_error",
                "status": "skill_error",
                "result_text": result_text,
                "cost_usd": cost_usd,
                "stderr": (
                    "no gpd_return YAML block in payload['result'] AND "
                    "no new K-*.md / A-*.md files in write_dirs since "
                    f"dispatch_start={dispatch_start:.0f}"
                ),
            }
        # mtime-harvest recovered files; treat as ok with a synthesized
        # files_written list.
        files_written = harvested

    if payload.get("is_error"):
        return {
            **base,
            "error_class": "skill_error",
            "status": "skill_error",
            "result_text": result_text,
            "cost_usd": cost_usd,
            "files_written": files_written,
        }

    return {
        **base,
        "error_class": "ok",
        "status": "ok",
        "result_text": result_text,
        "cost_usd": cost_usd,
        "duration_ms": payload.get("duration_ms") or 0,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "session_id": payload.get("session_id"),
        "files_written": files_written,
        "returncode": proc.returncode,
    }


def dispatch_digest_knowledge(
    tex_path: Path,
    *,
    knowledge_dir: Path,
    assertion_dir: Path,
    review_dir: Path,
    canary_run_root: Path,
    sources_dir: Path,
    max_budget_usd: float = 5.0,
    timeout_s: int = 3600,
    model: str,
    extra_allowed_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Invoke ``/gpd:digest-knowledge --adversarial`` via headless ``claude``.

    Returns a dict with ``error_class ∈ {ok, skill_error,
    subprocess_error, timeout}`` and the normalized return shape from
    plan-006 §C3.
    """
    prompt = f"/gpd:digest-knowledge --adversarial {tex_path}"
    write_dirs = [knowledge_dir, assertion_dir, review_dir, canary_run_root]
    read_dirs = [sources_dir]
    return _dispatch(
        prompt,
        write_dirs=write_dirs,
        read_dirs=read_dirs,
        extra_allowed_dirs=extra_allowed_dirs,
        max_budget_usd=max_budget_usd,
        timeout_s=timeout_s,
        model=model,
    )


def dispatch_digest_assertion(
    kdoc_id: str,
    equation_id: str,
    *,
    knowledge_dir: Path,
    assertion_dir: Path,
    review_dir: Path,
    canary_run_root: Path,
    sources_dir: Path,
    max_budget_usd: float = 8.0,
    timeout_s: int = 3600,
    model: str,
    extra_allowed_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Invoke ``/gpd:digest-assertion`` via headless ``claude`` for ONE
    (kdoc, equation) pair (plan-006 §C12 1:N amendment).

    Per the C12 amendment, assertion semantics are 1:N (one kdoc → N
    assertions, one per equation), not 1:1 like knowledge digestion. The
    skill input contract therefore takes:

    * ``kdoc_id``     — the K-NNN-slug identifier of the parent kdoc
                        (e.g. ``K-003-kazakov-zheng-lattice-ym-bootstrap``),
                        NOT a filesystem path. Pre-amendment dispatchers
                        passed the path; the skill expected an ID.
    * ``equation_id`` — the equation ID inside the kdoc (e.g. ``K.5``);
                        produces a ``kind: restated-equation`` assertion
                        targeting that equation specifically.

    The skill prompt always includes ``--adversarial`` so the Draft is
    hardened to Stable through the Critic↔Fixer loop. The default
    ``max_budget_usd`` is bumped from 5.0 to 8.0 because the adversarial
    loop on per-equation assertions hits ~$4-7 in practice (the smoke
    run hit $4 on a partial Draft-only run).
    """
    prompt = f"/gpd:digest-assertion {kdoc_id} {equation_id} --adversarial"
    write_dirs = [knowledge_dir, assertion_dir, review_dir, canary_run_root]
    read_dirs = [sources_dir]
    return _dispatch(
        prompt,
        write_dirs=write_dirs,
        read_dirs=read_dirs,
        extra_allowed_dirs=extra_allowed_dirs,
        max_budget_usd=max_budget_usd,
        timeout_s=timeout_s,
        model=model,
    )
