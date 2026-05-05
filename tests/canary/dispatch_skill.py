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
import os
import re
import signal
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

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
    if os.name == "nt":
        shim = Path(found)
        if shim.suffix.lower() in {".cmd", ".bat", ".ps1"}:
            exe = (
                shim.parent
                / "node_modules"
                / "@anthropic-ai"
                / "claude-code"
                / "bin"
                / "claude.exe"
            )
            if exe.is_file():
                return str(exe)
    return found


CLAUDE_CLI = _resolve_claude_cli()
DispatchPhase = Literal["knowledge", "assertion"]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LIVE_KNOWLEDGE_DIR = _PROJECT_ROOT / "GPD" / "knowledge"
_LIVE_ASSERTION_DIR = _PROJECT_ROOT / "GPD" / "assertions"
_LIVE_REVIEW_DIR = _PROJECT_ROOT / "GPD" / "reviews"


def _base_return() -> dict[str, Any]:
    """Normalized return shape (resolves iter-1-W1).

    Every dispatch path returns the same key set, with explicit zero
    defaults for missing numeric fields and an explicit ``error_class``.
    """
    return {
        "schema_version": 2,
        "dispatch_id": None,
        "phase": None,
        "arxiv_id": None,
        "error_class": None,
        "status": None,
        "kdoc_paths": [],
        "assertion_paths": [],
        "review_paths": [],
        "manifest_path": None,
        "raw_files_written": [],
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


def make_dispatch_id(
    phase: DispatchPhase, arxiv_id: str | None, eq_id: str | None = None
) -> str:
    """Create a filesystem-safe per-dispatch ID."""
    bits = [phase, arxiv_id or "unknown"]
    if eq_id:
        bits.append(eq_id)
    bits.append(str(int(time.time() * 1000)))
    raw = "-".join(bits)
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-")


def dispatch_root_for(canary_run_root: Path, dispatch_id: str) -> Path:
    return Path(canary_run_root) / "dispatch" / dispatch_id


def _ensure_dispatch_dirs(dispatch_root: Path) -> None:
    for rel in (
        "knowledge",
        "assertions",
        "reviews",
        "GPD/knowledge",
        "GPD/assertions",
        "GPD/reviews",
    ):
        (dispatch_root / rel).mkdir(parents=True, exist_ok=True)


def _ensure_dispatch_command_surface(dispatch_root: Path) -> Path:
    """Stage a local Claude Code command surface for this isolated dispatch.

    Headless ``claude -p`` resolves ``/gpd:*`` commands from the current
    project's Claude config. Canary dispatches intentionally run from a fresh
    sandbox, so they must carry their own ephemeral command/workflow surface
    instead of relying on the user's global install or the repo root.
    """
    target_dir = dispatch_root / ".claude"
    marker = target_dir / "commands" / "gpd" / "digest-knowledge.md"
    if marker.is_file():
        return target_dir

    from gpd.adapters.claude_code import ClaudeCodeAdapter

    ClaudeCodeAdapter().install(
        _PROJECT_ROOT / "src" / "gpd",
        target_dir,
        is_global=False,
        explicit_target=True,
    )
    return target_dir


def _phase_roots(dispatch_root: Path, phase: DispatchPhase) -> list[Path]:
    if phase == "knowledge":
        return [dispatch_root / "knowledge", dispatch_root / "GPD" / "knowledge"]
    return [dispatch_root / "assertions", dispatch_root / "GPD" / "assertions"]


def _review_roots(dispatch_root: Path) -> list[Path]:
    return [dispatch_root / "reviews", dispatch_root / "GPD" / "reviews"]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _resolve_returned_path(raw: str, cwd: Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (cwd / p).resolve()


def _snapshot_live_roots() -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for root in (_LIVE_KNOWLEDGE_DIR, _LIVE_ASSERTION_DIR, _LIVE_REVIEW_DIR):
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path.resolve())] = (int(stat.st_mtime_ns), stat.st_size)
    return snapshot


def _live_roots_changed(before: dict[str, tuple[int, int]]) -> list[str]:
    after = _snapshot_live_roots()
    changed = sorted(
        path for path, state in after.items() if before.get(path) != state
    )
    removed = sorted(path for path in before if path not in after)
    return changed + removed


def _harvest_phase_files(
    dispatch_root: Path, phase: DispatchPhase, since: float
) -> list[str]:
    """Fallback scan scoped to one dispatch root and one phase."""
    expected_prefix = "K-" if phase == "knowledge" else "A-"
    new_files: list[str] = []
    for root in _phase_roots(dispatch_root, phase):
        if not root.is_dir():
            continue
        for p in root.iterdir():
            if not p.is_file() or not p.name.endswith(".md"):
                continue
            if not p.name.startswith(expected_prefix):
                continue
            try:
                if p.stat().st_mtime > since:
                    new_files.append(str(p.resolve()))
            except OSError:
                continue
    new_files.sort()
    return new_files


def _normalize_artifacts(
    raw_files: list[str],
    *,
    phase: DispatchPhase,
    dispatch_root: Path,
    cwd: Path,
    assertion_id: str | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    artifacts = {"kdoc_paths": [], "assertion_paths": [], "review_paths": []}
    errors: list[str] = []
    phase_roots = _phase_roots(dispatch_root, phase)
    review_roots = _review_roots(dispatch_root)
    for raw in raw_files:
        path = _resolve_returned_path(raw, cwd)
        if (
            _is_relative_to(path, _LIVE_KNOWLEDGE_DIR)
            or _is_relative_to(path, _LIVE_ASSERTION_DIR)
            or _is_relative_to(path, _LIVE_REVIEW_DIR)
        ):
            errors.append(f"live GPD artifact returned in canary mode: {path}")
            continue
        if any(_is_relative_to(path, root) for root in review_roots):
            artifacts["review_paths"].append(str(path))
            continue
        if not any(_is_relative_to(path, root) for root in phase_roots):
            errors.append(f"returned path escapes dispatch {phase} roots: {path}")
            continue
        name = path.name
        if name.startswith("K-") and name.endswith(".md"):
            if phase != "knowledge":
                errors.append(f"assertion dispatch returned K artifact: {path}")
            else:
                artifacts["kdoc_paths"].append(str(path))
            continue
        if name.startswith("A-") and name.endswith(".md"):
            if phase != "assertion":
                errors.append(f"knowledge dispatch returned A artifact: {path}")
            elif assertion_id and not name.startswith(assertion_id):
                errors.append(
                    f"assertion ID mismatch: reserved {assertion_id}, got {path.name}"
                )
            else:
                artifacts["assertion_paths"].append(str(path))
            continue
        errors.append(f"returned path has unknown artifact shape: {path}")
    return artifacts, errors


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


def _subprocess_failure_detail(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stderr = (proc.stderr or "").strip()
    detail_bits: list[str] = []
    payload: dict[str, Any] = {}
    if proc.stdout:
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            detail_bits.append(f"stdout: {proc.stdout[-1200:]}")
        else:
            if isinstance(parsed, dict):
                payload = parsed
                subtype = payload.get("subtype")
                if subtype:
                    detail_bits.append(f"subtype={subtype}")
                for err in payload.get("errors") or []:
                    detail_bits.append(str(err))
                if payload.get("is_error") and not detail_bits:
                    detail_bits.append("claude returned is_error=true")
    if stderr:
        detail_bits.append(stderr[-1200:])
    return {
        "detail": " | ".join(detail_bits)[-2000:],
        "payload": payload,
    }


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    """Best-effort termination of the Claude subprocess tree."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        proc.kill()


def _run_claude_process(
    cmd: list[str],
    *,
    timeout_s: int,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Run Claude in a killable process group and return a CompletedProcess."""
    # Existing unit tests monkeypatch subprocess.run with canned envelopes.
    # Preserve that seam while real live canaries use Popen so timeout can kill
    # the whole process tree instead of only the direct child.
    if getattr(subprocess.run, "__module__", "subprocess") != "subprocess":
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
        )

    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        start_new_session = True
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd),
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=timeout_s,
            output=stdout or exc.output,
            stderr=stderr or exc.stderr,
        ) from exc
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def _dispatch(
    prompt: str,
    *,
    phase: DispatchPhase,
    dispatch_id: str,
    arxiv_id: str | None,
    dispatch_root: Path,
    assertion_id: str | None = None,
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
    dispatch_root = Path(dispatch_root).resolve()
    _ensure_dispatch_dirs(dispatch_root)
    manifest_path = dispatch_root / "manifest.json"
    base = {
        **_base_return(),
        "dispatch_id": dispatch_id,
        "phase": phase,
        "arxiv_id": arxiv_id,
        "manifest_path": str(manifest_path),
    }
    try:
        claude_surface_dir = _ensure_dispatch_command_surface(dispatch_root)
    except Exception as exc:
        return {
            **base,
            "error_class": "subprocess_error",
            "status": "subprocess_error",
            "stderr": f"failed to stage Claude command surface: {exc}",
        }
    effective_extra_allowed_dirs = [
        *(extra_allowed_dirs or []),
        claude_surface_dir,
    ]
    cmd = _build_cmd(
        prompt,
        write_dirs=write_dirs,
        read_dirs=read_dirs,
        extra_allowed_dirs=effective_extra_allowed_dirs,
        max_budget_usd=max_budget_usd,
        model=model,
    )
    dispatch_start = time.time()
    live_before = _snapshot_live_roots()
    try:
        # encoding="utf-8" + errors="replace" overrides Windows' default
        # cp1252 codec which crashes on Greek/math symbols emitted by the
        # agent (UnicodeDecodeError in subprocess._readerthread). errors=
        # "replace" preserves the rest of the stream when one byte is
        # un-decodable.
        proc = _run_claude_process(cmd, timeout_s=timeout_s, cwd=dispatch_root)
    except subprocess.TimeoutExpired as e:
        elapsed_s = max(time.time() - dispatch_start, float(e.timeout or timeout_s))
        detail = str(e)
        stdout = getattr(e, "stdout", None)
        stderr = getattr(e, "stderr", None)
        if stdout:
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            detail += f"; stdout_tail={str(stdout)[-800:]!r}"
        if stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            detail += f"; stderr_tail={str(stderr)[-800:]!r}"
        return {
            **base,
            "error_class": "timeout",
            "status": "timeout",
            "stderr": detail[-2000:],
            "duration_ms": int(elapsed_s * 1000),
            "wall_clock_seconds": elapsed_s,
        }
    if proc.returncode != 0:
        failure = _subprocess_failure_detail(proc)
        payload = failure["payload"]
        usage = payload.get("usage") or {}
        return {
            **base,
            "error_class": "subprocess_error",
            "status": "subprocess_error",
            "returncode": proc.returncode,
            "stderr": failure["detail"] or (proc.stderr or "")[-2000:],
            "result_text": payload.get("result", "") or "",
            "cost_usd": payload.get("total_cost_usd") or 0.0,
            "duration_ms": payload.get("duration_ms") or 0,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "session_id": payload.get("session_id"),
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        stdout_tail = (proc.stdout or "<empty stdout>")[-1200:]
        stderr_tail = (proc.stderr or "").strip()[-1200:]
        detail = f"could not parse claude stdout as JSON: {e}; stdout={stdout_tail!r}"
        if stderr_tail:
            detail += f"; stderr={stderr_tail!r}"
        return {
            **base,
            "error_class": "subprocess_error",
            "status": "subprocess_error",
            "returncode": proc.returncode,
            "stderr": detail[-2000:],
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
        harvested = _harvest_phase_files(
            dispatch_root, phase, since=dispatch_start
        )
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
                    f"no new {phase} artifact in dispatch root since "
                    f"dispatch_start={dispatch_start:.0f}"
                ),
            }
        # mtime-harvest recovered files; treat as ok with a synthesized
        # files_written list.
        files_written = harvested

    raw_files = [str(x) for x in files_written]
    artifacts, artifact_errors = _normalize_artifacts(
        raw_files,
        phase=phase,
        dispatch_root=dispatch_root,
        cwd=dispatch_root,
        assertion_id=assertion_id,
    )
    live_changes = _live_roots_changed(live_before)
    if live_changes:
        artifact_errors.extend(
            f"live GPD artifact changed during canary dispatch: {p}"
            for p in live_changes
        )
    if artifact_errors:
        return {
            **base,
            "error_class": "skill_error",
            "status": "skill_error",
            "result_text": result_text,
            "cost_usd": cost_usd,
            "raw_files_written": raw_files,
            "files_written": raw_files,
            **artifacts,
            "stderr": "; ".join(artifact_errors),
        }

    if payload.get("is_error"):
        error_bits = [str(item) for item in (payload.get("errors") or [])]
        if payload.get("subtype"):
            error_bits.insert(0, f"subtype={payload.get('subtype')}")
        return {
            **base,
            "error_class": "skill_error",
            "status": "skill_error",
            "result_text": result_text,
            "cost_usd": cost_usd,
            "duration_ms": payload.get("duration_ms") or 0,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "session_id": payload.get("session_id"),
            "raw_files_written": raw_files,
            "files_written": raw_files,
            **artifacts,
            "stderr": " | ".join(error_bits)[-2000:],
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
        "raw_files_written": raw_files,
        "files_written": raw_files,
        **artifacts,
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
    dispatch_id: str | None = None,
    arxiv_id: str | None = None,
    source_filename: str | None = None,
    source_path_sha256: str | None = None,
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
    dispatch_id = dispatch_id or make_dispatch_id("knowledge", arxiv_id)
    dispatch_root = dispatch_root_for(canary_run_root, dispatch_id)
    manifest_path = dispatch_root / "manifest.json"
    source_filename = source_filename or Path(tex_path).name
    prompt = (
        f"/gpd:digest-knowledge --adversarial {tex_path}\n\n"
        f"canary_dispatch_root: {dispatch_root}\n"
        f"canary_manifest_path: {manifest_path}\n"
        f"source_arxiv_id: {arxiv_id or ''}\n"
        f"source_filename: {source_filename}\n"
        f"source_path_sha256: {source_path_sha256 or ''}\n"
        "\nCANARY HARD REQUIREMENTS:\n"
        "- Write canary artifacts only under the canary dispatch root.\n"
        "- Do not write live GPD/knowledge, GPD/assertions, or GPD/reviews.\n"
        "- Copy the exact scalar values above into the kdoc YAML "
        "frontmatter as source_arxiv_id, source_filename, and "
        "source_path_sha256.\n"
        "- Do not shorten source_filename to a basename; keep any "
        "manifest subdirectory prefix exactly as supplied.\n"
        "- Do not emit source_path_sha256 as null, empty, or a PDF hash when "
        "a source_path_sha256 value is supplied.\n"
        "- If you cannot emit those exact ownership scalars, return "
        "gpd_return.status: blocked and do not write a kdoc.\n"
        "- gpd_return.files_written must list the actual emitted paths under "
        "the canary dispatch root."
    )
    write_dirs = [dispatch_root]
    read_dirs = [sources_dir]
    return _dispatch(
        prompt,
        phase="knowledge",
        dispatch_id=dispatch_id,
        arxiv_id=arxiv_id,
        dispatch_root=dispatch_root,
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
    assertion_id: str | None = None,
    dispatch_id: str | None = None,
    arxiv_id: str | None = None,
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
    dispatch_id = dispatch_id or make_dispatch_id(
        "assertion", arxiv_id, equation_id
    )
    dispatch_root = dispatch_root_for(canary_run_root, dispatch_id)
    manifest_path = dispatch_root / "manifest.json"
    assertion_part = f" --assertion-id {assertion_id}" if assertion_id else ""
    prompt = (
        f"/gpd:digest-assertion {kdoc_id} {equation_id} --adversarial"
        f"{assertion_part}\n\n"
        f"canary_dispatch_root: {dispatch_root}\n"
        f"canary_manifest_path: {manifest_path}\n"
        f"reserved_assertion_id: {assertion_id or ''}\n"
        "Write canary artifacts only under the canary dispatch root. "
        "Do not scan live GPD/assertions when reserved_assertion_id is supplied."
    )
    write_dirs = [dispatch_root]
    read_dirs = [sources_dir, knowledge_dir]
    return _dispatch(
        prompt,
        phase="assertion",
        dispatch_id=dispatch_id,
        arxiv_id=arxiv_id,
        dispatch_root=dispatch_root,
        assertion_id=assertion_id,
        write_dirs=write_dirs,
        read_dirs=read_dirs,
        extra_allowed_dirs=extra_allowed_dirs,
        max_budget_usd=max_budget_usd,
        timeout_s=timeout_s,
        model=model,
    )
