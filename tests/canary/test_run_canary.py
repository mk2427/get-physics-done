"""Tests for ``tests/canary/run_canary.py`` (plan-006 §C3).

Covers:

1. Missing ``--model`` aborts with documented message (iter-2-M1).
2. ``--dry-run`` short-circuits before any dispatch.
3. Legacy ``run-bfss-canary.py --dry-run`` wrapper still exits 0.
4. ``--resume-from-cost-log`` drops already-completed arxiv_ids.
5. ``error_class==ok`` with empty ``files_written`` ⇒ FAIL with
   diagnostic (defense-in-depth iter-2-M3).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import hashlib
from pathlib import Path

import pytest

_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))


def _import_run_canary():
    """Fresh import each test (sys.argv parsing is process-local)."""
    if "run_canary" in sys.modules:
        del sys.modules["run_canary"]
    return importlib.import_module("run_canary")


def _write_minimal_manifest(tmp_path: Path, arxiv_ids: list[str]) -> Path:
    manifest_path = tmp_path / "manifest.json"
    entries = [
        {
            "arxiv_id": aid,
            "tex_filename": f"sources/{aid}.tex",
            "pdf_filename": f"{aid}.pdf",
            "sha256": "0" * 64,
        }
        for aid in arxiv_ids
    ]
    manifest_path.write_text(
        json.dumps(
            {"references_dir": str(tmp_path / "refs"), "entries": entries}
        )
    )
    return manifest_path


# ---------------------------------------------------------------------------
# 1. Missing --model on a live (non-dry-run) invocation aborts.
# ---------------------------------------------------------------------------


def test_missing_model_flag_aborts(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Resolves iter-2-M1: live runs require --model; abort message says
    "force --model"."""
    rc = _import_run_canary()
    manifest = _write_minimal_manifest(tmp_path, ["1810.03378"])
    with pytest.raises(SystemExit) as exc_info:
        rc.main(["--manifest", str(manifest), "--non-interactive"])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "force --model" in err


# ---------------------------------------------------------------------------
# 2. --dry-run skips dispatch entirely.
# ---------------------------------------------------------------------------


def test_dry_run_does_not_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rc = _import_run_canary()
    manifest = _write_minimal_manifest(tmp_path, ["1810.03378", "2511.01209"])

    call_count = {"k": 0, "a": 0}

    def _fake_k(*args, **kwargs):  # pragma: no cover -- must NOT run
        call_count["k"] += 1
        return {"error_class": "ok", "files_written": []}

    def _fake_a(*args, **kwargs):  # pragma: no cover -- must NOT run
        call_count["a"] += 1
        return {"error_class": "ok", "files_written": []}

    monkeypatch.setattr(
        "dispatch_skill.dispatch_digest_knowledge", _fake_k, raising=False
    )
    monkeypatch.setattr(
        "dispatch_skill.dispatch_digest_assertion", _fake_a, raising=False
    )

    rc_code = rc.main(
        ["--manifest", str(manifest), "--dry-run", "--non-interactive"]
    )
    assert rc_code == 0
    assert call_count == {"k": 0, "a": 0}


def test_run_canary_script_dry_run_imports_when_executed_as_file(
    tmp_path: Path,
) -> None:
    manifest = _write_minimal_manifest(tmp_path, ["1810.03378"])

    result = subprocess.run(
        [
            sys.executable,
            str(_CANARY_DIR / "run_canary.py"),
            "--manifest",
            str(manifest),
            "--dry-run",
            "--non-interactive",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--dry-run" in result.stderr


# ---------------------------------------------------------------------------
# 3. Legacy wrapper (--dry-run --non-interactive) still exits 0.
# ---------------------------------------------------------------------------


def test_legacy_wrapper_dry_run_exits_zero(
    capsys: pytest.CaptureFixture,
) -> None:
    """The legacy ``run-bfss-canary.py`` entry point must still produce
    exit-0 on ``--dry-run --non-interactive``.
    """
    script_path = _CANARY_DIR / "run-bfss-canary.py"
    spec = importlib.util.spec_from_file_location(
        "run_bfss_canary_legacy", script_path
    )
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)  # type: ignore[union-attr]

    with pytest.raises(SystemExit) as exc_info:
        legacy.main(["--dry-run", "--non-interactive"])
    # Legacy main() ends with sys.exit(0 if pass/dry_run else 1).
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# 4. --resume-from-cost-log drops completed arxiv_ids.
# ---------------------------------------------------------------------------


def test_resume_skips_already_completed_arxiv_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    rc = _import_run_canary()
    manifest = _write_minimal_manifest(
        tmp_path, ["A", "B", "C", "D"]
    )

    cost_log = tmp_path / "cost.jsonl"
    cost_log.write_text(
        json.dumps({"arxiv_id": "A", "error_class": "ok"})
        + "\n"
        + json.dumps({"arxiv_id": "B", "error_class": "ok"})
        + "\n",
        encoding="utf-8",
    )

    rc_code = rc.main(
        [
            "--manifest", str(manifest),
            "--resume-from-cost-log", str(cost_log),
            "--dry-run",
            "--non-interactive",
        ]
    )
    assert rc_code == 0
    err = capsys.readouterr().err
    # Banner says "dropped 2/4".
    assert "dropped 2/4" in err


# ---------------------------------------------------------------------------
# 5. Defense-in-depth M3: ok dispatch + empty files_written ⇒ FAIL.
# ---------------------------------------------------------------------------


def test_empty_files_written_with_ok_dispatch_fails_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    rc = _import_run_canary()
    manifest = _write_minimal_manifest(tmp_path, ["1810.03378"])

    # Stub the dispatcher to return ok-with-empty-files.
    def _stub_k(*args, **kwargs):
        return {
            "error_class": "ok",
            "status": "ok",
            "files_written": [],
            "cost_usd": 0.0,
            "input_tokens": 100,
            "output_tokens": 50,
        }

    def _stub_a(*args, **kwargs):  # not reached
        return {"error_class": "ok", "files_written": []}

    import dispatch_skill  # noqa: E402
    monkeypatch.setattr(
        dispatch_skill, "dispatch_digest_knowledge", _stub_k
    )
    monkeypatch.setattr(
        dispatch_skill, "dispatch_digest_assertion", _stub_a
    )

    rc_code = rc.main(
        [
            "--manifest", str(manifest),
            "--model", "claude-sonnet-4-6",
            "--ack-token-budget",
            "--non-interactive",
            "--parallel", "1",
        ]
    )
    assert rc_code == 1
    err = capsys.readouterr().err
    assert "empty" in err.lower()
    assert "iter-2-S1" in err or "files_written" in err


# ---------------------------------------------------------------------------
# 6. Bonus: end-to-end ok-dispatch with non-empty files_written passes.
# ---------------------------------------------------------------------------


def test_ok_dispatch_with_files_written_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rc = _import_run_canary()
    manifest = _write_minimal_manifest(tmp_path, ["1810.03378"])

    def _stub_k(*args, **kwargs):
        kdoc_path = kwargs["knowledge_dir"] / "K-001-foo.md"
        kdoc_path.write_text(
            "---\nkdoc_id: K-001-foo\nstatus: Stable\n"
            "source_arxiv_id: 1810.03378\n"
            "source_filename: sources/1810.03378.tex\n"
            f"source_path_sha256: {'0' * 64}\n"
            "---\n\n"
            "(K.1) $E = mc^2$\n"
            "(K.2) $F = ma$\n",
            encoding="utf-8",
        )
        return {
            "error_class": "ok",
            "status": "ok",
            "kdoc_paths": [str(kdoc_path)],
            "assertion_paths": [],
            "cost_usd": 0.5,
            "input_tokens": 100,
            "output_tokens": 50,
        }

    def _stub_a(kdoc_id, equation_id, **kwargs):
        return {
            "error_class": "ok",
            "status": "ok",
            "assertion_paths": [
                f"GPD/assertions/A-{equation_id.replace('.', '-')}.md"
            ],
            "cost_usd": 0.2,
            "input_tokens": 30,
            "output_tokens": 20,
        }

    import dispatch_skill  # noqa: E402
    monkeypatch.setattr(dispatch_skill, "dispatch_digest_knowledge", _stub_k)
    monkeypatch.setattr(dispatch_skill, "dispatch_digest_assertion", _stub_a)
    monkeypatch.setattr(rc, "run_criteria", lambda **kwargs: [])

    rc_code = rc.main(
        [
            "--manifest", str(manifest),
            "--model", "claude-sonnet-4-6",
            "--ack-token-budget",
            "--non-interactive",
            "--parallel", "1",
        ]
    )
    assert rc_code == 0


def test_process_one_paper_uses_manifest_tex_sha256_for_source_identity(
    tmp_path: Path,
) -> None:
    rc = _import_run_canary()
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    tex_path = sources_dir / "paper.tex"
    tex_path.write_bytes(b"line one\r\nline two\r\n")
    expected_tex_hash = hashlib.sha256(b"line one\nline two\n").hexdigest()
    captured: dict[str, str | None] = {}

    def _stub_k(*args, **kwargs):
        captured["source_path_sha256"] = kwargs["source_path_sha256"]
        kwargs["knowledge_dir"].mkdir(parents=True, exist_ok=True)
        kdoc_path = kwargs["knowledge_dir"] / "K-001-source.md"
        kdoc_path.write_text(
            "---\nkdoc_id: K-001-source\nstatus: Stable\n"
            "source_arxiv_id: X\n"
            "source_filename: paper.tex\n"
            f"source_path_sha256: {expected_tex_hash}\n"
            "---\n\nNo displayed equations.\n",
            encoding="utf-8",
        )
        return {
            "error_class": "ok",
            "kdoc_paths": [str(kdoc_path)],
            "assertion_paths": [],
        }

    def _stub_a(*args, **kwargs):  # pragma: no cover - no equations extracted
        raise AssertionError("unexpected assertion dispatch")

    proc = rc._make_process_one_paper(
        sources_dir=sources_dir,
        knowledge_dir=tmp_path / "k",
        assertion_dir=tmp_path / "a",
        review_dir=tmp_path / "r",
        canary_run_root=tmp_path / "root",
        max_budget_usd=8.0,
        timeout_s=10,
        model="m",
        dispatch_knowledge_fn=_stub_k,
        dispatch_assertion_fn=_stub_a,
    )
    outcome = proc(
        {
            "arxiv_id": "X",
            "tex_filename": "paper.tex",
            "tex_sha256": expected_tex_hash,
            "sha256": "0" * 64,
        }
    )

    assert captured["source_path_sha256"] == expected_tex_hash
    assert outcome["assertion_results"] == []


def test_process_one_paper_rejects_stale_manifest_source_hash(
    tmp_path: Path,
) -> None:
    rc = _import_run_canary()
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    tex_path = sources_dir / "paper.tex"
    tex_path.write_bytes(b"fresh line\r\n")
    stale_hash = "b" * 64

    def _stub_k(*args, **kwargs):  # pragma: no cover - must not dispatch
        raise AssertionError("stale manifest hash should fail before dispatch")

    def _stub_a(*args, **kwargs):  # pragma: no cover - must not dispatch
        raise AssertionError("unexpected assertion dispatch")

    proc = rc._make_process_one_paper(
        sources_dir=sources_dir,
        knowledge_dir=tmp_path / "k",
        assertion_dir=tmp_path / "a",
        review_dir=tmp_path / "r",
        canary_run_root=tmp_path / "root",
        max_budget_usd=8.0,
        timeout_s=10,
        model="m",
        dispatch_knowledge_fn=_stub_k,
        dispatch_assertion_fn=_stub_a,
    )
    outcome = proc(
        {
            "arxiv_id": "X",
            "tex_filename": "paper.tex",
            "tex_sha256": stale_hash,
        }
    )

    assert outcome["knowledge_result"]["error_class"] == "skill_error"
    assert "source hash mismatch before dispatch" in outcome["knowledge_result"]["stderr"]
    assert stale_hash in outcome["knowledge_result"]["stderr"]


def test_run_canary_honors_references_dir_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rc = _import_run_canary()
    override = tmp_path / "local-refs"
    monkeypatch.setenv("GPD_BFSS_REFERENCES_DIR", str(override))

    assert rc._resolve_sources_dir({"references_dir": "D:/stale/path"}) == override


def test_kdoc_ownership_requires_exact_source_filename_and_hash(
    tmp_path: Path,
) -> None:
    rc = _import_run_canary()
    expected_hash = "a" * 64
    entry = {
        "arxiv_id": "2302.04416",
        "tex_filename": "sources/2302.04416.tex",
        "tex_sha256": expected_hash,
    }

    missing_hash = tmp_path / "missing-hash.md"
    missing_hash.write_text(
        "---\n"
        "source_arxiv_id: 2302.04416\n"
        "source_filename: sources/2302.04416.tex\n"
        "---\n",
        encoding="utf-8",
    )
    assert "source_path_sha256 frontmatter missing" in (
        rc._validate_kdoc_ownership(missing_hash, entry) or ""
    )

    legacy_arxiv_only = tmp_path / "legacy-arxiv-only.md"
    legacy_arxiv_only.write_text(
        "---\n"
        "arxiv_id: 2302.04416\n"
        "source_filename: sources/2302.04416.tex\n"
        f"source_path_sha256: {expected_hash}\n"
        "---\n",
        encoding="utf-8",
    )
    assert "source_arxiv_id frontmatter missing" in (
        rc._validate_kdoc_ownership(legacy_arxiv_only, entry) or ""
    )

    basename_only = tmp_path / "basename-only.md"
    basename_only.write_text(
        "---\n"
        "source_arxiv_id: 2302.04416\n"
        "source_filename: 2302.04416.tex\n"
        f"source_path_sha256: {expected_hash}\n"
        "---\n",
        encoding="utf-8",
    )
    assert "source_filename mismatch" in (
        rc._validate_kdoc_ownership(basename_only, entry) or ""
    )

    exact = tmp_path / "exact.md"
    exact.write_text(
        "---\n"
        "source_arxiv_id: 2302.04416\n"
        "source_filename: sources/2302.04416.tex\n"
        f"source_path_sha256: {expected_hash}\n"
        "---\n",
        encoding="utf-8",
    )
    assert rc._validate_kdoc_ownership(exact, entry) is None


# ---------------------------------------------------------------------------
# Plan-006 §C12: per-equation 1:N dispatch + silent-failure aggregation.
# ---------------------------------------------------------------------------


def test_aggregate_error_class_propagates_assertion_error(tmp_path: Path) -> None:
    """C12: when knowledge ok but ANY assertion errored, aggregate is
    ``"assertion_error"`` (NOT silently ``"ok"`` like the pre-amendment bug)."""
    rc = _import_run_canary()
    k_ok = {"error_class": "ok"}
    a_results = [
        {"error_class": "ok"},
        {"error_class": "skill_error", "stderr": "claude crashed"},
    ]
    assert rc._aggregate_error_class(k_ok, a_results) == "assertion_error"


def test_aggregate_error_class_all_ok_returns_ok(tmp_path: Path) -> None:
    """C12: when knowledge ok and all assertions ok → aggregate is ``"ok"``."""
    rc = _import_run_canary()
    k_ok = {"error_class": "ok"}
    a_results = [{"error_class": "ok"}, {"error_class": "ok"}]
    assert rc._aggregate_error_class(k_ok, a_results) == "ok"


def test_aggregate_error_class_zero_assertions_returns_ok(tmp_path: Path) -> None:
    """C12: knowledge ok + zero assertions attempted (extraction found 0
    equations) is OK at the aggregator; coverage parser §7.1 catches it."""
    rc = _import_run_canary()
    k_ok = {"error_class": "ok"}
    assert rc._aggregate_error_class(k_ok, []) == "ok"


def test_aggregate_error_class_propagates_knowledge_error(tmp_path: Path) -> None:
    """C12: knowledge errored → propagate the knowledge error class."""
    rc = _import_run_canary()
    k_bad = {"error_class": "skill_error"}
    a_results = [{"error_class": "ok"}]
    assert rc._aggregate_error_class(k_bad, a_results) == "skill_error"


def test_per_equation_dispatch_loops_over_extracted_equations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C12 1:N: process_one_paper calls dispatch_digest_assertion ONCE per
    equation in the kdoc, with (kdoc_id, equation_id) positional args."""
    rc = _import_run_canary()
    manifest = _write_minimal_manifest(tmp_path, ["X"])

    kdoc_path = tmp_path / "K-007-three-eqs.md"
    kdoc_path.write_text(
        "---\nkdoc_id: K-007-three-eqs\nsource_arxiv_id: X\n"
        "source_filename: x.tex\n---\n\n"
        "(K.1) $a = b$\n"
        "(K.2) $c = d$\n"
        "(K.3) $e = f$\n",
        encoding="utf-8",
    )

    calls: list[tuple[str, str]] = []

    def _stub_k(*args, **kwargs):
        return {
            "error_class": "ok",
            "kdoc_paths": [str(kdoc_path)],
            "assertion_paths": [],
            "cost_usd": 0.0,
        }

    def _stub_a(kdoc_id, equation_id, **kwargs):
        calls.append((kdoc_id, equation_id))
        return {
            "error_class": "ok",
            "assertion_paths": [f"A-{len(calls):03d}.md"],
            "cost_usd": 0.1,
        }

    proc = rc._make_process_one_paper(
        sources_dir=tmp_path,
        knowledge_dir=tmp_path / "k",
        assertion_dir=tmp_path / "a",
        review_dir=tmp_path / "r",
        canary_run_root=tmp_path / "root",
        max_budget_usd=8.0,
        timeout_s=10,
        model="m",
        dispatch_knowledge_fn=_stub_k,
        dispatch_assertion_fn=_stub_a,
    )
    outcome = proc({"arxiv_id": "X", "tex_filename": "x.tex"})

    assert calls == [
        ("K-007-three-eqs", "K.1"),
        ("K-007-three-eqs", "K.2"),
        ("K-007-three-eqs", "K.3"),
    ]
    assert len(outcome["assertion_results"]) == 3
    assert len(outcome["new_assertions"]) == 3


def test_per_equation_dispatch_zero_equations_no_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C12: kdoc with no extractable equations → 0 assertion calls; result
    is still ok at the aggregator (coverage parser handles structural)."""
    rc = _import_run_canary()
    kdoc_path = tmp_path / "K-008-prose-only.md"
    kdoc_path.write_text(
        "---\nkdoc_id: K-008-prose-only\nsource_arxiv_id: X\n"
        "source_filename: x.tex\n---\n\n"
        "Just prose, no equations.\n",
        encoding="utf-8",
    )

    calls: list = []

    def _stub_k(*args, **kwargs):
        return {
            "error_class": "ok",
            "kdoc_paths": [str(kdoc_path)],
            "assertion_paths": [],
        }

    def _stub_a(*args, **kwargs):
        calls.append(args)
        return {"error_class": "ok", "assertion_paths": []}

    proc = rc._make_process_one_paper(
        sources_dir=tmp_path,
        knowledge_dir=tmp_path / "k",
        assertion_dir=tmp_path / "a",
        review_dir=tmp_path / "r",
        canary_run_root=tmp_path / "root",
        max_budget_usd=8.0,
        timeout_s=10,
        model="m",
        dispatch_knowledge_fn=_stub_k,
        dispatch_assertion_fn=_stub_a,
    )
    outcome = proc({"arxiv_id": "X", "tex_filename": "x.tex"})

    assert calls == []
    assert outcome["assertion_results"] == []


def test_per_equation_dispatch_missing_kdoc_id_records_skill_error(
    tmp_path: Path,
) -> None:
    """C12: a kdoc without ``kdoc_id`` frontmatter records a synthesized
    skill_error so the silent-failure aggregator surfaces it."""
    rc = _import_run_canary()
    kdoc_path = tmp_path / "K-bad-no-frontmatter.md"
    kdoc_path.write_text(
        "---\nsource_arxiv_id: X\nsource_filename: x.tex\n---\n\n"
        "No kdoc_id.\n\n(K.1) $x = y$\n",
        encoding="utf-8",
    )

    def _stub_k(*args, **kwargs):
        return {
            "error_class": "ok",
            "kdoc_paths": [str(kdoc_path)],
            "assertion_paths": [],
        }

    def _stub_a(*args, **kwargs):  # must NOT be called
        raise AssertionError("dispatch_digest_assertion called with bad kdoc")

    proc = rc._make_process_one_paper(
        sources_dir=tmp_path,
        knowledge_dir=tmp_path / "k",
        assertion_dir=tmp_path / "a",
        review_dir=tmp_path / "r",
        canary_run_root=tmp_path / "root",
        max_budget_usd=8.0,
        timeout_s=10,
        model="m",
        dispatch_knowledge_fn=_stub_k,
        dispatch_assertion_fn=_stub_a,
    )
    outcome = proc({"arxiv_id": "X", "tex_filename": "x.tex"})

    assert len(outcome["assertion_results"]) == 1
    assert outcome["assertion_results"][0]["error_class"] == "skill_error"
    assert "kdoc_id frontmatter missing" in (
        outcome["assertion_results"][0]["stderr"]
    )
    # Aggregate must surface this as assertion_error (silent-failure fix).
    assert (
        rc._aggregate_error_class(
            outcome["knowledge_result"], outcome["assertion_results"]
        )
        == "assertion_error"
    )


def test_count_assertion_errors_helper(tmp_path: Path) -> None:
    """C12: ``_count_assertion_errors`` counts entries with error_class != ok."""
    rc = _import_run_canary()
    a_results = [
        {"error_class": "ok"},
        {"error_class": "skill_error"},
        {"error_class": "ok"},
        {"error_class": "timeout"},
    ]
    assert rc._count_assertion_errors(a_results) == 2
    assert rc._count_assertion_errors([]) == 0


def test_parse_kdoc_id_from_frontmatter_happy_path(tmp_path: Path) -> None:
    """C12: ``_parse_kdoc_id_from_frontmatter`` extracts the scalar value."""
    rc = _import_run_canary()
    p = tmp_path / "K-099-foo.md"
    p.write_text(
        "---\nkdoc_id: K-099-foo-bar\nstatus: Stable\n---\n\nbody\n",
        encoding="utf-8",
    )
    assert rc._parse_kdoc_id_from_frontmatter(p) == "K-099-foo-bar"


def test_parse_kdoc_id_from_frontmatter_missing_returns_none(tmp_path: Path) -> None:
    """C12: missing kdoc_id field → returns None (caller surfaces error)."""
    rc = _import_run_canary()
    p = tmp_path / "no-frontmatter.md"
    p.write_text("just body, no frontmatter\n", encoding="utf-8")
    assert rc._parse_kdoc_id_from_frontmatter(p) is None
