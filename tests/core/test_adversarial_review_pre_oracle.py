"""End-to-end tests for plan 005 `--pre-oracle` workflow wiring.

Plan 005 commit c3 / iter-1-M2 fixer: tests drive the workflow
`<step name="pre_oracle">` primitive via
`tests/core/workflow_harness.run_pre_oracle_workflow_step`, not a
direct call to `run_pre_oracle`. The harness asserts the workflow spec
still carries the load-bearing step block so a silent deletion causes
test failure.

Coverage:

* Primary end-to-end: fixture kdoc with one verifiable + one falsifiable
  equation; monkey-patched dispatch returns canned verdicts; assert
  `R0-REVIEW.md` contains the expected N-level verified entry + S-level
  blocking falsified entry with counterexample.
* Preflight: import-sympy failure emits exactly one
  `ORACLE-DISPATCH-FAIL` W-finding.
* Round-1 critic handshake: the round-0 file is on disk at the path
  `gpd-knowledge-critic` reads in its anti-anchoring round-0 pre-read
  directive.
* Partial-persist: workflow-level exception mid-batch flushes already-
  collected findings AND the `ORACLE-DISPATCH-FAIL` W-finding, then
  re-raises.
* Finally-exactly-once: spy on the writer to confirm idempotent flush.
* Negative: `--pre-oracle` absent → no `R0-REVIEW.md` written.
* Compose: `pre_oracle: true` and `parallel_critics: true` together
  (no collision under plan 005 c0 dedup key).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gpd.core import sympy_oracle as oracle_mod
from gpd.core.adversarial_loop import Finding, merge_parallel_findings
from gpd.core.sympy_oracle import OracleDispatchError, oracle_results_to_findings

from tests.core import workflow_harness


# ─── Fixture builders ─────────────────────────────────────────────────────────


def _write_fixture_kdoc(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            ---
            kind: knowledge
            ---

            # Test Kdoc

            ## Overview

            Overview paragraphs for the fixture kdoc.

            ## Equations

            (K.1) $2 + 2 = 4$
            Context: arithmetic ground truth.
            Why/How: verified by SymPy.

            (K.2) $2 + 2 = 5$
            Context: intentional arithmetic error.
            Why/How: should trigger a falsified verdict.
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _canned_dispatch(latex, python_path, *, assumptions=None, timeout_s=60.0):
    """Dispatch that returns `verified` for the valid eq and `falsified`
    for the intentionally-wrong one.
    """
    body = latex.strip()
    if "= 5" in body:
        return {
            "verdict": "falsified",
            "latex_result": body,
            "code": "sp.Eq(2 + 2, 5)",
            "output": "counterexample: 2+2 = 4, not 5",
            "attempts": 1,
            "timeout_hit": False,
            "note": "",
        }
    return {
        "verdict": "verified",
        "latex_result": body,
        "code": "sp.Eq(2 + 2, 4)",
        "output": "True",
        "attempts": 1,
        "timeout_hit": False,
        "note": "",
    }


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_pre_oracle_end_to_end_writes_r0_review(tmp_path, monkeypatch):
    """Primary end-to-end: canned dispatch → R0-REVIEW.md bytes contain
    both the N-level verified entry and the S-level falsified entry.
    """
    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", _canned_dispatch)

    kdoc = tmp_path / "K-999-test.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "K-999-test"

    results = workflow_harness.run_pre_oracle_workflow_step(
        kdoc, "K-999-test", review_dir, pre_oracle=True, artifact_kind="knowledge"
    )
    assert results is not None
    assert results["K.1"].verdict == "verified"
    assert results["K.2"].verdict == "falsified"

    body = (review_dir / "R0-REVIEW.md").read_text(encoding="utf-8")
    assert "ORACLE-VERIFIED-K.1" in body
    assert "ORACLE-FALSIFIED-K.2" in body
    assert "blocking: true" in body  # from the falsified entry
    assert "blocking: false" in body  # from the verified entry
    assert "counterexample: 2+2 = 4, not 5" in body
    assert "source: sympy_oracle" in body
    assert "kind: oracle_falsified" in body


def test_pre_oracle_preflight_fails_on_missing_sympy(tmp_path, monkeypatch):
    """iter-1-M2: ImportError in preflight → exactly one
    ORACLE-DISPATCH-FAIL W-finding in R0-REVIEW.md.
    """
    monkeypatch.setattr(
        workflow_harness, "_preflight_sympy_import", lambda: False
    )

    kdoc = tmp_path / "K-998-test.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "K-998-test"

    results = workflow_harness.run_pre_oracle_workflow_step(
        kdoc, "K-998-test", review_dir, pre_oracle=True, artifact_kind="knowledge"
    )
    assert results == {}
    body = (review_dir / "R0-REVIEW.md").read_text(encoding="utf-8")
    assert body.count("ORACLE-DISPATCH-FAIL") == 1
    assert "preflight failed" in body


def test_pre_oracle_skipped_when_flag_absent(tmp_path, monkeypatch):
    """Negative: --pre-oracle absent → no R0-REVIEW.md written."""
    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", _canned_dispatch)

    kdoc = tmp_path / "K-997-test.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "K-997-test"

    results = workflow_harness.run_pre_oracle_workflow_step(
        kdoc, "K-997-test", review_dir, pre_oracle=False, artifact_kind="knowledge"
    )
    assert results is None
    assert not (review_dir / "R0-REVIEW.md").exists()


def test_pre_oracle_skipped_on_non_knowledge_artifact(tmp_path, monkeypatch):
    """Precondition gate: artifact_kind != "knowledge" → no-op."""
    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", _canned_dispatch)

    kdoc = tmp_path / "brief.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "brief"

    results = workflow_harness.run_pre_oracle_workflow_step(
        kdoc, "brief", review_dir, pre_oracle=True, artifact_kind="brief"
    )
    assert results is None
    assert not (review_dir / "R0-REVIEW.md").exists()


def test_round_1_critic_reads_round_0_oracle_findings(tmp_path, monkeypatch):
    """iter-1-M2 + S1: the round-0 artifact is on the disk path the
    critic reads via its anti-anchoring directive. The critic contract
    change is tested here as a path + contents check (the agent itself
    is LLM-driven and not exercised in unit tests).
    """
    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", _canned_dispatch)

    kdoc = tmp_path / "K-996-test.md"
    _write_fixture_kdoc(kdoc)
    target_slug = "K-996-test"
    review_dir = tmp_path / "GPD" / "reviews" / target_slug

    workflow_harness.run_pre_oracle_workflow_step(
        kdoc, target_slug, review_dir, pre_oracle=True, artifact_kind="knowledge"
    )

    # The critic's anti-anchoring round-0 pre-read directive reads
    # `GPD/reviews/<target-slug>/R0-REVIEW.md`.
    r0 = review_dir / "R0-REVIEW.md"
    assert r0.exists()
    body = r0.read_text(encoding="utf-8")
    # Critic-consumable structure: source + verdict fields present so
    # the agent can classify verified (de-prioritize) vs falsified
    # (pre-seed) per the §1 focus-area rules.
    assert "source: sympy_oracle" in body
    assert "verdict: verified" in body
    assert "verdict: falsified" in body


def test_pre_oracle_preserves_partials_on_workflow_failure(tmp_path, monkeypatch):
    """iter-1-S2 + iter-2-S1: workflow-level exception mid-batch →
    R0-REVIEW.md exists AFTER re-raise and contains both the completed
    K.1 finding AND the ORACLE-DISPATCH-FAIL W-finding.
    """
    # K.1 falsified, K.2 raises a non-per-equation exception during
    # dispatch (simulates an orchestrator-layer crash: e.g., Task tool
    # subsystem crash that is NOT an OracleDispatchError).
    call_count = {"n": 0}

    def erratic_dispatch(latex, python_path, *, assumptions=None, timeout_s=60.0):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # K.1 → falsified with counterexample
            return {
                "verdict": "falsified",
                "latex_result": latex,
                "code": "",
                "output": "counterexample: K.1-specific",
                "attempts": 1,
                "timeout_hit": False,
                "note": "",
            }
        raise OSError("subsystem crash (not an OracleDispatchError)")

    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", erratic_dispatch)

    kdoc = tmp_path / "K-995-test.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "K-995-test"

    with pytest.raises(OSError, match="subsystem crash"):
        workflow_harness.run_pre_oracle_workflow_step(
            kdoc, "K-995-test", review_dir, pre_oracle=True, artifact_kind="knowledge"
        )

    # File EXISTS after re-raise (guaranteed by try/except/finally).
    r0 = review_dir / "R0-REVIEW.md"
    assert r0.exists(), "R0-REVIEW.md must exist after re-raise (partial-persist)"
    body = r0.read_text(encoding="utf-8")
    # K.1 falsified finding preserved.
    assert "ORACLE-FALSIFIED-K.1" in body
    assert "counterexample: K.1-specific" in body
    # ORACLE-DISPATCH-FAIL W-finding documents the shortfall.
    assert "ORACLE-DISPATCH-FAIL" in body
    assert "subsystem crash" in body


def test_pre_oracle_finally_runs_exactly_once(tmp_path, monkeypatch):
    """iter-2-S1: spy on safe_write_r0_review to confirm exactly one
    invocation (with partial=True) on workflow-level failure.
    Guards against accidental double-flush.
    """
    calls: list[dict] = []
    original = workflow_harness.safe_write_r0_review

    def spy(review_dir, target_slug, results, *, partial, dispatch_error):
        calls.append(
            {"partial": partial, "dispatch_error": dispatch_error, "n_results": len(results)}
        )
        return original(
            review_dir, target_slug, results,
            partial=partial, dispatch_error=dispatch_error,
        )

    monkeypatch.setattr(workflow_harness, "safe_write_r0_review", spy)

    def erratic_dispatch(latex, python_path, *, assumptions=None, timeout_s=60.0):
        raise OSError("boom")

    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", erratic_dispatch)

    kdoc = tmp_path / "K-994-test.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "K-994-test"

    with pytest.raises(OSError):
        workflow_harness.run_pre_oracle_workflow_step(
            kdoc, "K-994-test", review_dir, pre_oracle=True, artifact_kind="knowledge"
        )

    # Exactly one invocation, and it was the partial-persist flush.
    assert len(calls) == 1
    assert calls[0]["partial"] is True


def test_pre_oracle_compose_with_parallel_critics_no_collision(tmp_path, monkeypatch):
    """iter-1-M1 Option 2 compose test: `pre_oracle: true` produces a
    `kind: oracle_falsified` finding; parallel critics produce other
    kinds; merged list has all of them (no collision) under the new
    `(kind, location, body_hash)` dedup key.

    Emulates merged-finding aggregation at the workflow boundary after
    both steps have run.
    """
    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", _canned_dispatch)

    kdoc = tmp_path / "K-993-test.md"
    _write_fixture_kdoc(kdoc)
    review_dir = tmp_path / "reviews" / "K-993-test"
    results = workflow_harness.run_pre_oracle_workflow_step(
        kdoc, "K-993-test", review_dir, pre_oracle=True, artifact_kind="knowledge"
    )
    oracle_finding_dicts = oracle_results_to_findings(results)
    assert len(oracle_finding_dicts) == 1  # only K.2 falsified
    oracle_findings = [
        Finding(
            finding_id=d["finding_id"],
            severity="S",
            blocking=True,
            summary=d["summary"],
            location=d["location"],
            equation_body=d["equation_body"],
            kind=d["kind"],
        )
        for d in oracle_finding_dicts
    ]

    # Parallel-critic findings: a doc-level completeness finding, plus
    # a SAME-K.2-location but DIFFERENT-kind equation-critic finding.
    parallel_findings = [
        Finding(
            location="",
            equation_body="",
            severity="M",
            kind="thin_overview",
            summary="Overview is thin",
        ),
        Finding(
            location="K.2",
            equation_body="2 + 2 = 5",
            severity="S",
            blocking=True,
            kind="wrong_equation",
            summary="K.2 wrong coefficient on RHS",
        ),
    ]

    merged = merge_parallel_findings(oracle_findings, parallel_findings, [])

    # All three survive; the same-location K.2 findings do NOT collide
    # because their `kind` slugs differ.
    assert len(merged) == 3
    kinds = {f.kind for f in merged}
    assert kinds == {"oracle_falsified", "thin_overview", "wrong_equation"}

    # No duplicate dedup keys.
    from gpd.core.adversarial_loop import _finding_dedup_key

    keys = [_finding_dedup_key(f) for f in merged]
    assert len(set(keys)) == len(keys)
