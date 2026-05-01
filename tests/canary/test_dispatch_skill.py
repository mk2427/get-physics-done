"""Tests for ``tests/canary/dispatch_skill.py`` (plan-006 §C3).

Strategy: stub the ``claude`` CLI via ``monkeypatch`` of
``subprocess.run`` so the tests are platform-portable and never invoke
a real ``claude`` binary.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

# Allow direct sibling imports regardless of cwd.
_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))

import dispatch_skill  # noqa: E402


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a CompletedProcess-like object usable as subprocess.run return."""
    return types.SimpleNamespace(
        stdout=stdout, stderr=stderr, returncode=returncode
    )


def _envelope_with_files(files: list[str], cost_usd: float = 0.42) -> str:
    """A canned envelope JSON with a populated gpd_return YAML block."""
    files_block = "\n".join(f"    - {f}" for f in files) if files else ""
    result_text = (
        "Done.\n\n"
        "```yaml\n"
        "gpd_return:\n"
        "  status: completed\n"
        "  mode: digestion\n"
        "  kdoc_id: K-001-test\n"
        "  files_written:\n"
        f"{files_block}\n"
        "```\n"
    )
    return json.dumps(
        {
            "result": result_text,
            "total_cost_usd": cost_usd,
            "duration_ms": 1234,
            "session_id": "sess-abc",
            "is_error": False,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 200,
                "cache_read_input_tokens": 300,
            },
        }
    )


def _common_kwargs(tmp_path: Path) -> dict:
    return {
        "knowledge_dir": tmp_path / "knowledge",
        "assertion_dir": tmp_path / "assertions",
        "review_dir": tmp_path / "reviews",
        "canary_run_root": tmp_path / "run",
        "sources_dir": tmp_path / "sources",
        "model": "claude-sonnet-4-6",
    }


# ---------------------------------------------------------------------------
# 1. Happy path: gpd_return YAML block parsed correctly.
# ---------------------------------------------------------------------------


def test_happy_path_parses_gpd_return_from_result_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = [
        "GPD/knowledge/K-001-test.md",
        "GPD/knowledge/K-002-other.md",
    ]
    monkeypatch.setattr(
        dispatch_skill.subprocess,
        "run",
        lambda *a, **kw: _make_proc(stdout=_envelope_with_files(files)),
    )

    result = dispatch_skill.dispatch_digest_knowledge(
        Path("sources/foo.tex"), **_common_kwargs(tmp_path)
    )

    assert result["error_class"] == "ok"
    assert result["files_written"] == files
    assert result["cost_usd"] == 0.42
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    assert result["cache_creation_tokens"] == 200
    assert result["cache_read_tokens"] == 300
    assert result["session_id"] == "sess-abc"
    assert result["duration_ms"] == 1234


# ---------------------------------------------------------------------------
# 2. Missing gpd_return block ⇒ skill_error (NOT ok-with-empty-list).
# ---------------------------------------------------------------------------


def test_missing_gpd_return_block_returns_skill_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Resolves iter-2-S1: prose-only result must classify as skill_error."""
    envelope = json.dumps(
        {
            "result": "I finished but forgot to emit the YAML block.",
            "total_cost_usd": 0.10,
            "is_error": False,
            "usage": {},
        }
    )
    monkeypatch.setattr(
        dispatch_skill.subprocess,
        "run",
        lambda *a, **kw: _make_proc(stdout=envelope),
    )

    result = dispatch_skill.dispatch_digest_knowledge(
        Path("sources/foo.tex"), **_common_kwargs(tmp_path)
    )

    assert result["error_class"] == "skill_error"
    assert result["files_written"] == []
    assert "no gpd_return YAML block" in result["stderr"]


# ---------------------------------------------------------------------------
# 3. Subprocess nonzero exit ⇒ subprocess_error.
# ---------------------------------------------------------------------------


def test_subprocess_nonzero_returns_subprocess_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        dispatch_skill.subprocess,
        "run",
        lambda *a, **kw: _make_proc(
            stdout="", stderr="claude: command crashed", returncode=1
        ),
    )

    result = dispatch_skill.dispatch_digest_knowledge(
        Path("sources/foo.tex"), **_common_kwargs(tmp_path)
    )

    assert result["error_class"] == "subprocess_error"
    assert result["returncode"] == 1
    assert "command crashed" in result["stderr"]


# ---------------------------------------------------------------------------
# 4. TimeoutExpired ⇒ timeout class.
# ---------------------------------------------------------------------------


def test_timeout_returns_timeout_class(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["claude"], timeout=1)

    monkeypatch.setattr(dispatch_skill.subprocess, "run", _raise_timeout)

    result = dispatch_skill.dispatch_digest_knowledge(
        Path("sources/foo.tex"),
        timeout_s=1,
        **_common_kwargs(tmp_path),
    )

    assert result["error_class"] == "timeout"
    assert result["status"] == "timeout"


# ---------------------------------------------------------------------------
# 5. --add-dir whitelist must NOT contain project_root (resolves M7).
# ---------------------------------------------------------------------------


def test_add_dir_whitelist_excludes_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Resolves iter-1-M7: only kwargs dirs are whitelisted."""
    captured: dict = {}

    def _capture_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _make_proc(stdout=_envelope_with_files(["a.md"]))

    monkeypatch.setattr(dispatch_skill.subprocess, "run", _capture_run)

    kwargs = _common_kwargs(tmp_path)
    dispatch_skill.dispatch_digest_knowledge(Path("sources/foo.tex"), **kwargs)

    cmd = captured["cmd"]
    add_dir_args: list[str] = []
    for i, tok in enumerate(cmd):
        if tok == "--add-dir":
            add_dir_args.append(cmd[i + 1])

    expected_dirs = {
        str(kwargs["knowledge_dir"]),
        str(kwargs["assertion_dir"]),
        str(kwargs["review_dir"]),
        str(kwargs["canary_run_root"]),
        str(kwargs["sources_dir"]),
    }
    assert set(add_dir_args) == expected_dirs

    # Project root anchor — get-physics-done/ — must NOT appear.
    project_root = Path(__file__).resolve().parents[2]
    assert str(project_root) not in add_dir_args
    # Spot-check: the command does include --model and --no-session-persistence
    assert "--model" in cmd
    assert "--no-session-persistence" in cmd
    assert "--allow-dangerously-skip-permissions" in cmd


# ---------------------------------------------------------------------------
# Bonus: dispatch_digest_assertion mirrors the same shape (post-C12: takes
# ``kdoc_id`` + ``equation_id`` as positional args).
# ---------------------------------------------------------------------------


def test_dispatch_digest_assertion_mirrors_knowledge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        dispatch_skill.subprocess,
        "run",
        lambda *a, **kw: _make_proc(
            stdout=_envelope_with_files(["GPD/assertions/A-001.md"])
        ),
    )

    result = dispatch_skill.dispatch_digest_assertion(
        "K-001-test", "K.1", **_common_kwargs(tmp_path)
    )
    assert result["error_class"] == "ok"
    assert result["files_written"] == ["GPD/assertions/A-001.md"]


# ---------------------------------------------------------------------------
# Plan-006 §C12: dispatch_digest_assertion takes (kdoc_id, equation_id) and
# builds a per-equation prompt with --adversarial.
# ---------------------------------------------------------------------------


def test_dispatch_digest_assertion_prompt_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C12 amendment: prompt must be ``/gpd:digest-assertion {kdoc_id} {eq_id}
    --adversarial`` (NOT a filesystem path)."""
    captured: dict = {}

    def _capture_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _make_proc(stdout=_envelope_with_files(["GPD/assertions/A-1.md"]))

    monkeypatch.setattr(dispatch_skill.subprocess, "run", _capture_run)

    dispatch_skill.dispatch_digest_assertion(
        "K-003-kazakov-zheng-lattice-ym-bootstrap",
        "K.5",
        **_common_kwargs(tmp_path),
    )

    cmd = captured["cmd"]
    # Locate the -p prompt argument (the slot right after "-p").
    p_idx = cmd.index("-p")
    prompt = cmd[p_idx + 1]

    assert prompt.startswith("/gpd:digest-assertion ")
    assert "K-003-kazakov-zheng-lattice-ym-bootstrap" in prompt
    assert "K.5" in prompt
    assert "--adversarial" in prompt
    # No filesystem path leakage: must not mention .md or sandbox dirs.
    assert ".md" not in prompt
    assert str(tmp_path) not in prompt


def test_dispatch_digest_assertion_default_budget_is_8usd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C12 amendment: per-call default ``max_budget_usd`` raised from 5.0 to
    8.0 (adversarial loop on per-equation assertions hits ~$4-7)."""
    captured: dict = {}

    def _capture_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _make_proc(stdout=_envelope_with_files(["A-1.md"]))

    monkeypatch.setattr(dispatch_skill.subprocess, "run", _capture_run)

    # Pass NO max_budget_usd kwarg → must default to 8.0.
    dispatch_skill.dispatch_digest_assertion(
        "K-001-test", "K.1", **_common_kwargs(tmp_path)
    )

    cmd = captured["cmd"]
    budget_idx = cmd.index("--max-budget-usd")
    budget_value = cmd[budget_idx + 1]
    assert budget_value == "8.0", (
        f"Expected default budget 8.0, got {budget_value!r}"
    )


def test_dispatch_digest_assertion_signature_takes_kdoc_id_and_equation_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C12 amendment: signature is ``(kdoc_id: str, equation_id: str, *,
    ...)``. Passing a Path as first arg is a TypeError-equivalent via the
    str-only signature; we verify the function accepts the new form
    cleanly and the kdoc_id appears verbatim in the prompt."""
    captured: dict = {}

    def _capture_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _make_proc(stdout=_envelope_with_files(["A-1.md"]))

    monkeypatch.setattr(dispatch_skill.subprocess, "run", _capture_run)

    result = dispatch_skill.dispatch_digest_assertion(
        "K-042-some-paper",
        "E.7",
        **_common_kwargs(tmp_path),
    )

    assert result["error_class"] == "ok"
    p_idx = captured["cmd"].index("-p")
    prompt = captured["cmd"][p_idx + 1]
    # Order: kdoc_id then equation_id.
    assert prompt.index("K-042-some-paper") < prompt.index("E.7")
