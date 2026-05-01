"""Tests for ``gpd.core.adversarial_loop`` (commits 4a + 4b; brief 002 §5).

Commit 4a cases:

* ``test_severity_adapter`` -- four-case mapping (brief §5.1 table)
* ``test_blocking_propagation_or_semantics`` -- Critic-vs-Critic OR of
  ``blocking`` (brief §5.1 (i))
* ``test_finding_id_regex`` -- ``^iter-\\d+-[SMWN]\\d+$`` validator
  (brief §5.1 (v) + §7.3)
* ``test_router_compound_derived_consequence`` -- brief §5.2 iter-3-W1
  resolution; 4 partition cases
* ``test_recursion_depth_cap_3`` -- depth-4 nest raises schema error

Commit 4b cases (loop state machine + CI merge hook):

* ``test_loop_stays_in_revise_while_blocking_open`` -- brief §5.1 (ii)
* ``test_ci_merge_hook_returns_412`` -- brief §5.1 (iii)
* ``test_approved_gated_on_empty_blocking_list`` -- brief §5.1 (iv)
* integration smoke: ``artifact_kind=brief`` contrived-findings fixture
  terminates in ≤2 rounds per brief §3 cap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.adversarial_loop import (
    AssertionKind,
    CanonicalSeverity,
    Finding,
    LoopState,
    NativeCriticSeverity,
    adapt_severity,
    check_merge_allowed,
    classify_assertion,
    is_valid_finding_id,
    merge_findings,
    next_loop_state,
    route_assertion,
    update_blocking_findings,
)


def _mkfinding(
    *,
    severity: CanonicalSeverity,
    blocking: bool,
    finding_id: str = "iter-1-S1",
    summary: str = "",
) -> Finding:
    return Finding(finding_id=finding_id, severity=severity, blocking=blocking, summary=summary)


class TestSeverityAdapter:
    """Brief 002 §5.1 table: FATAL->(S,true); SERIOUS->(S,false); WARNING->(W,false); MINOR->(N,false)."""

    @pytest.mark.parametrize(
        ("native", "expected_severity", "expected_blocking"),
        [
            ("FATAL", CanonicalSeverity.SERIOUS, True),
            ("SERIOUS", CanonicalSeverity.SERIOUS, False),
            ("WARNING", CanonicalSeverity.WEAK, False),
            ("MINOR", CanonicalSeverity.NIT, False),
        ],
    )
    def test_four_case_mapping(
        self, native: str, expected_severity: CanonicalSeverity, expected_blocking: bool
    ) -> None:
        severity, blocking = adapt_severity(native)
        assert severity == expected_severity
        assert blocking is expected_blocking

    def test_enum_and_case_insensitive(self) -> None:
        assert adapt_severity(NativeCriticSeverity.FATAL) == (CanonicalSeverity.SERIOUS, True)
        assert adapt_severity("fatal") == (CanonicalSeverity.SERIOUS, True)

    def test_unknown_severity_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown native critic severity"):
            adapt_severity("CATASTROPHIC")

    def test_non_string_non_enum_raises(self) -> None:
        with pytest.raises(TypeError):
            adapt_severity(42)  # type: ignore[arg-type]


class TestBlockingPropagationOrSemantics:
    """Brief 002 §5.1 (i): merge_findings performs OR on the blocking flag."""

    def test_one_true_one_false_merges_to_true(self) -> None:
        a = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=True, summary="A")
        b = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=False, summary="B")
        merged = merge_findings([a, b])
        assert merged.blocking is True
        assert merged.severity == CanonicalSeverity.SERIOUS

    def test_both_false_stays_false(self) -> None:
        a = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=False)
        b = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=False)
        assert merge_findings([a, b]).blocking is False

    def test_both_true_stays_true(self) -> None:
        a = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=True)
        b = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=True)
        assert merge_findings([a, b]).blocking is True

    def test_three_way_merge_true_wins_and_max_severity_enforced(self) -> None:
        a = _mkfinding(severity=CanonicalSeverity.WEAK, blocking=False)
        b = _mkfinding(severity=CanonicalSeverity.WEAK, blocking=False)
        c = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=True)
        merged = merge_findings([a, b, c])
        assert merged.blocking is True
        assert merged.severity == CanonicalSeverity.SERIOUS  # MAX

    def test_max_severity_without_blocking(self) -> None:
        a = _mkfinding(severity=CanonicalSeverity.WEAK, blocking=False)
        b = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=False)
        merged = merge_findings([a, b])
        assert merged.severity == CanonicalSeverity.SERIOUS
        assert merged.blocking is False

    def test_single_finding_passthrough(self) -> None:
        a = _mkfinding(severity=CanonicalSeverity.SERIOUS, blocking=True)
        assert merge_findings([a]) is a

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one Finding"):
            merge_findings([])


class TestFindingIdRegex:
    """Brief 002 §5.1 (v) + §7.3: ``^iter-\\d+-[SMWN]\\d+$``. Letters only; blocking is separate."""

    @pytest.mark.parametrize(
        "valid_id",
        ["iter-1-S1", "iter-2-M3", "iter-10-W12", "iter-100-N99", "iter-1-S0"],
    )
    def test_valid_ids_accepted(self, valid_id: str) -> None:
        assert is_valid_finding_id(valid_id) is True

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "iter-1-F1",           # F outside [SMWN] (native letter does not survive)
            "iter-1-X1",           # unknown letter
            "iter-1-s1",           # lowercase letter
            "ITER-1-S1",           # uppercase prefix
            "iter-S1",             # missing round number
            "iter-1-S",            # missing finding number
            "iter-1S1",            # missing dash
            "iter-1-S1-blocking",  # trailing blocking token (§5.1 (v))
            "",
        ],
    )
    def test_invalid_ids_rejected(self, invalid_id: str) -> None:
        assert is_valid_finding_id(invalid_id) is False

    def test_non_string_raises(self) -> None:
        with pytest.raises(TypeError):
            is_valid_finding_id(42)  # type: ignore[arg-type]


class TestRouterCompoundDerivedConsequence:
    """Brief 002 §5.2 iter-3-W1 resolution.

    Partitions (top-level ``derivation_sketch`` in {empty, non-empty})
    x (in-body sub-assertions in {absent, present}) across 4 cases,
    plus knowledge-doc as a 5th case.
    """

    def test_restated_equation_empty_derivation_no_subs(self) -> None:
        routes = route_assertion({"derivation_sketch": ""}, sub_assertions=None)
        assert len(routes) == 1
        assert routes[0].kind == AssertionKind.RESTATED_EQUATION
        assert routes[0].critic == "gpd-knowledge-critic"

    def test_derived_consequence_nonempty_derivation_no_subs(self) -> None:
        routes = route_assertion({"derivation_sketch": "E.45 and E.50 => claim"}, sub_assertions=None)
        assert len(routes) == 1
        assert routes[0].kind == AssertionKind.DERIVED_CONSEQUENCE
        assert routes[0].critic == "gpd-adversarial-critic"

    def test_mixed_kind_empty_derivation_with_subs(self) -> None:
        sub_assertions = [
            {"id": "sub-a", "derivation_sketch": ""},       # restatement
            {"id": "sub-b", "derivation_sketch": "chain"},   # derivation
        ]
        routes = route_assertion({"derivation_sketch": ""}, sub_assertions=sub_assertions)
        assert len(routes) == 3
        assert routes[0].kind == AssertionKind.MIXED_KIND
        assert routes[0].critic == "gpd-knowledge-critic"
        assert routes[1].sub_id == "sub-a" and routes[1].critic == "gpd-knowledge-critic"
        assert routes[2].sub_id == "sub-b" and routes[2].critic == "gpd-adversarial-critic"

    def test_compound_derived_consequence_nonempty_derivation_with_subs(self) -> None:
        """Brief §5.2 iter-3-W1: the unification-rule case."""
        sub_assertions = [
            {"id": "sub-1", "derivation_sketch": ""},
            {"id": "sub-2", "derivation_sketch": "sub chain"},
        ]
        routes = route_assertion({"derivation_sketch": "top chain"}, sub_assertions=sub_assertions)
        assert len(routes) == 3
        assert routes[0].kind == AssertionKind.COMPOUND_DERIVED_CONSEQUENCE
        assert routes[0].critic == "gpd-adversarial-critic"  # top-level is derivation
        assert routes[1].sub_id == "sub-1" and routes[1].critic == "gpd-knowledge-critic"
        assert routes[2].sub_id == "sub-2" and routes[2].critic == "gpd-adversarial-critic"

    def test_knowledge_doc_routes_to_knowledge_critic(self) -> None:
        routes = route_assertion({}, sub_assertions=None, artifact_kind="knowledge")
        assert routes == [routes[0]]
        assert routes[0].kind == AssertionKind.KNOWLEDGE_DOC
        assert routes[0].critic == "gpd-knowledge-critic"

    def test_classify_assertion_direct(self) -> None:
        """Label each partition cell directly."""
        assert classify_assertion({}, None) == AssertionKind.RESTATED_EQUATION
        assert classify_assertion({"derivation_sketch": "x"}, None) == AssertionKind.DERIVED_CONSEQUENCE
        assert classify_assertion({}, [{"id": "s1"}]) == AssertionKind.MIXED_KIND
        assert (
            classify_assertion({"derivation_sketch": "x"}, [{"id": "s1"}])
            == AssertionKind.COMPOUND_DERIVED_CONSEQUENCE
        )


class TestRecursionDepthCap3:
    """Brief 002 §5.2 'Recursion depth limit': cap at 3; depth-4 nest raises."""

    def test_depth_1_through_3_allowed(self) -> None:
        # Depth model: top-level doc = depth 0, sub = depth 1, sub-of-sub = depth 2,
        # sub-of-sub-of-sub = depth 3 (the cap; MAX_SUB_ASSERTION_DEPTH = 3).
        # Depth 1 (top only; no sub-assertions).
        route_assertion({"derivation_sketch": "x"}, None)
        # Depth 2 (top + one sub at depth 1).
        route_assertion({"derivation_sketch": "x"}, [{"id": "s1", "derivation_sketch": "y"}])
        # Depth 3 (top -> sub (depth 1) -> sub-of-sub (depth 2)), within cap.
        route_assertion(
            {"derivation_sketch": "x"},
            [
                {
                    "id": "s1",
                    "derivation_sketch": "y",
                    "sub_assertions": [{"id": "s1.1", "derivation_sketch": "z"}],
                }
            ],
        )
        # Depth 4 total nesting levels (top -> sub -> sub-of-sub -> sub-of-sub-of-sub),
        # sub-of-sub-of-sub is at depth 3 = MAX_SUB_ASSERTION_DEPTH; still allowed.
        route_assertion(
            {"derivation_sketch": "x"},
            [
                {
                    "id": "s1",
                    "derivation_sketch": "y",
                    "sub_assertions": [
                        {
                            "id": "s1.1",
                            "derivation_sketch": "z",
                            "sub_assertions": [
                                {"id": "s1.1.1", "derivation_sketch": "w"},
                            ],
                        }
                    ],
                }
            ],
        )

    def test_depth_4_raises_schema_validation_error(self) -> None:
        # 5 nesting levels: top (depth 0) -> s1 (depth 1) -> s1.1 (depth 2) ->
        # s1.1.1 (depth 3) -> s1.1.1.1 (depth 4 > MAX_SUB_ASSERTION_DEPTH=3) -> raises.
        with pytest.raises(ValueError, match="Recursion depth"):
            route_assertion(
                {"derivation_sketch": "x"},
                [
                    {
                        "id": "s1",
                        "derivation_sketch": "y",
                        "sub_assertions": [
                            {
                                "id": "s1.1",
                                "derivation_sketch": "z",
                                "sub_assertions": [
                                    {
                                        "id": "s1.1.1",
                                        "derivation_sketch": "w",
                                        "sub_assertions": [
                                            {"id": "s1.1.1.1", "derivation_sketch": "v"},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            )

    def test_empty_sub_assertions_key_at_leaf_allowed(self) -> None:
        """``sub_assertions: []`` at depth-N does not count as depth-(N+1)."""
        route_assertion(
            {"derivation_sketch": "x"},
            [
                {
                    "id": "s1",
                    "derivation_sketch": "y",
                    "sub_assertions": [
                        {"id": "s1.1", "derivation_sketch": "z", "sub_assertions": []},
                    ],
                }
            ],
        )


# ─── Commit 4b: loop state machine + CI merge hook ─────────────────────────────


class TestLoopStaysInRevisWhileBlockingOpen:
    """Brief 002 §5.1 (ii): loop stays in REVISE when any blocking finding is
    open, regardless of overall F/S/W/N zero counts.
    """

    def test_revise_when_zero_counts_but_blocking_open(self) -> None:
        """Zero S/M/W/N counts plus ONE open blocking finding -> REVISE, not
        SUCCESS.  The blocking flag overrides severity convergence.
        """
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=["iter-1-S1"],
            iteration=1,
        )
        assert state == LoopState.REVISE

    def test_revise_persists_across_rounds_with_blocking_open(self) -> None:
        """Multi-round: as long as blocking is open and iter < cap, stays REVISE."""
        for iteration in range(1, 4):
            assert (
                next_loop_state(
                    current_state=LoopState.IN_PROGRESS,
                    severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
                    blocking_findings_unresolved=["iter-1-S1"],
                    iteration=iteration,
                )
                == LoopState.REVISE
            )

    def test_revise_when_counts_nonzero_and_no_blocking(self) -> None:
        """Non-zero S but empty blocking list -> still REVISE (non-blocking
        findings need author response) per brief §5.1 (ii)-(iv).
        """
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 1, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=[],
            iteration=1,
        )
        assert state == LoopState.REVISE

    def test_success_requires_both_zero_counts_and_empty_blocking(self) -> None:
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=[],
            iteration=2,
        )
        assert state == LoopState.SUCCESS

    def test_escalate_unresolved_when_cap_hit_with_blocking_open(self) -> None:
        """Brief §5.1 iteration-cap rule (feedback_autonomous_loop stall)."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=["iter-4-S1"],
            iteration=4,
            max_iterations=4,
        )
        assert state == LoopState.ESCALATE_UNRESOLVED

    def test_idle_transitions_to_in_progress_on_any_input(self) -> None:
        assert (
            next_loop_state(
                current_state=LoopState.IDLE,
                severity_counts=None,
                blocking_findings_unresolved=None,
                iteration=0,
            )
            == LoopState.IN_PROGRESS
        )


class TestCiMergeHookReturns412:
    """Brief 002 §5.1 (iii): CI merge hook denies merge (HTTP 412) when
    ``adversarial_review_status.blocking_findings_unresolved`` is non-empty.
    """

    def test_merge_allowed_on_empty_blocking_list(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(
            json.dumps({"adversarial_review_status": {"blocking_findings_unresolved": []}}),
            encoding="utf-8",
        )
        allowed, status, reason = check_merge_allowed("main", path)
        assert allowed is True
        assert status == 200
        assert reason == ""

    def test_merge_denied_with_412_on_open_blocking(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(
            json.dumps(
                {
                    "adversarial_review_status": {
                        "blocking_findings_unresolved": ["iter-1-S1", "iter-2-M2"]
                    }
                }
            ),
            encoding="utf-8",
        )
        allowed, status, reason = check_merge_allowed(
            "experimental/knowledge-trust-full", path
        )
        assert allowed is False
        assert status == 412
        assert "2 blocking finding" in reason
        assert "iter-1-S1" in reason
        assert "experimental/knowledge-trust-full" in reason

    def test_merge_denied_when_state_json_missing_fail_closed(self, tmp_path: Path) -> None:
        """Fail-closed: a branch without state.json is not merge-eligible."""
        allowed, status, reason = check_merge_allowed("feat/foo", tmp_path / "nope.json")
        assert allowed is False
        assert status == 412
        assert "not found" in reason

    def test_merge_allowed_when_status_block_absent(self, tmp_path: Path) -> None:
        """No adversarial_review_status -> no review in flight -> allow merge."""
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"position": {"status": "executing"}}), encoding="utf-8")
        allowed, status, reason = check_merge_allowed("main", path)
        assert allowed is True
        assert status == 200

    def test_update_blocking_findings_writes_and_validates(self, tmp_path: Path) -> None:
        """Writer persists validated finding IDs; merge hook reflects them."""
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"position": {"status": "executing"}}), encoding="utf-8")
        update_blocking_findings(path, ["iter-1-S1", "sub-a-iter-2-W1"])
        allowed, status, reason = check_merge_allowed("feat/foo", path)
        assert allowed is False
        assert status == 412
        # Re-read: block is now persisted in state.json.
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["adversarial_review_status"]["blocking_findings_unresolved"] == [
            "iter-1-S1",
            "sub-a-iter-2-W1",
        ]
        # Clearing unblocks merge.
        update_blocking_findings(path, [])
        allowed, status, _ = check_merge_allowed("feat/foo", path)
        assert allowed is True
        assert status == 200

    def test_update_blocking_findings_rejects_malformed_id(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(json.dumps({}), encoding="utf-8")
        with pytest.raises(ValueError, match="does not match"):
            update_blocking_findings(path, ["iter-1-X1"])  # bad severity letter
        # state.json must NOT have been written on the bad push.
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "adversarial_review_status" not in raw


class TestApprovedGatedOnEmptyBlockingList:
    """Brief 002 §5.1 (iv): APPROVED verdict (SUCCESS) requires
    ``blocking_findings_unresolved`` to be empty.
    """

    def test_zero_counts_with_blocking_does_not_reach_success(self) -> None:
        """Even at 0/0/0/0, SUCCESS is gated on empty blocking list."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=["iter-3-S1"],
            iteration=2,
        )
        assert state == LoopState.REVISE
        assert state != LoopState.SUCCESS

    def test_zero_counts_and_empty_blocking_reaches_success(self) -> None:
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=[],
            iteration=2,
        )
        assert state == LoopState.SUCCESS

    def test_none_severity_counts_treated_as_zero(self) -> None:
        """Empty severity_counts mapping + empty blocking list -> SUCCESS."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts=None,
            blocking_findings_unresolved=[],
            iteration=1,
        )
        assert state == LoopState.SUCCESS

    def test_mixed_severity_counts_and_empty_blocking_wn_fast_exit(self) -> None:
        """W=1 but blocking empty, iteration>=1 -> SUCCESS via W/N fast-exit
        (the fixer already addressed the W/N findings in the current round;
        no need to rerun a full Critic pass for W/N-only residue).
        """
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 1, "N": 0},
            blocking_findings_unresolved=[],
            iteration=1,
        )
        assert state == LoopState.SUCCESS

    def test_mixed_severity_counts_iteration_zero_still_revises(self) -> None:
        """W=1 at iteration=0 -> REVISE (fast-exit requires iteration>=1)."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 1, "N": 0},
            blocking_findings_unresolved=[],
            iteration=0,
        )
        assert state == LoopState.REVISE


class TestIntegrationSmokeBriefArtifactTerminatesInTwoRounds:
    """Brief §3 integration smoke: ``artifact_kind: brief`` fixture with
    contrived findings terminates in ≤ 2 rounds.

    This tests the state machine's termination guarantees (not the actual
    orchestrator; that lands in later commits). We simulate rounds by
    manually driving the state machine with realistic per-round inputs and
    verify SUCCESS is reachable in 2 rounds when blocking findings are
    closed between rounds.
    """

    def test_two_round_termination_blocking_closed(self, tmp_path: Path) -> None:
        """Round 1: 1 blocking finding open -> REVISE.  Round 2: closed -> SUCCESS."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({}), encoding="utf-8")

        # Round 1: Critic emits one FATAL->(S, blocking=True) finding.
        update_blocking_findings(state_path, ["iter-1-S1"])
        round1_state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 1, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=["iter-1-S1"],
            iteration=1,
        )
        assert round1_state == LoopState.REVISE

        # Round 2: Fixer resolves the finding; Critic re-reviews and finds
        # no new issues; orchestrator clears the ledger.
        update_blocking_findings(state_path, [])
        round2_state = next_loop_state(
            current_state=LoopState.REVISE,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=[],
            iteration=2,
        )
        assert round2_state == LoopState.SUCCESS

        # CI merge hook now permits merge.
        allowed, http, _ = check_merge_allowed("feat/brief-fixture", state_path)
        assert allowed is True
        assert http == 200

    def test_escalation_after_two_rounds_with_unresolved_blocking(self, tmp_path: Path) -> None:
        """Brief §3 cap=2 enforced via max_iterations=2; blocking still open
        at round 2 -> ESCALATE_UNRESOLVED.
        """
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({}), encoding="utf-8")
        update_blocking_findings(state_path, ["iter-1-S1"])

        # Round 1: still open -> REVISE
        assert (
            next_loop_state(
                current_state=LoopState.IN_PROGRESS,
                severity_counts={"S": 1, "M": 0, "W": 0, "N": 0},
                blocking_findings_unresolved=["iter-1-S1"],
                iteration=1,
                max_iterations=2,
            )
            == LoopState.REVISE
        )

        # Round 2 hits the cap with blocking still open -> ESCALATE
        assert (
            next_loop_state(
                current_state=LoopState.REVISE,
                severity_counts={"S": 1, "M": 0, "W": 0, "N": 0},
                blocking_findings_unresolved=["iter-1-S1"],
                iteration=2,
                max_iterations=2,
            )
            == LoopState.ESCALATE_UNRESOLVED
        )

        # CI merge hook still denies.
        allowed, http, reason = check_merge_allowed("feat/brief-fixture", state_path)
        assert allowed is False
        assert http == 412


class TestPhysicsArtifactNoIterationCap:
    """iter-1-S2: physics/knowledge/assertion artifacts accept max_iterations=None
    (no cap) so they never escalate on blocking findings due to round count alone.
    """

    def test_none_max_iterations_accepted(self) -> None:
        """max_iterations=None does not raise TypeError."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 1, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=["iter-1-S1"],
            iteration=100,
            max_iterations=None,
        )
        assert state == LoopState.REVISE

    def test_physics_artifact_never_escalates_on_count_alone(self) -> None:
        """With max_iterations=None a physics artifact stays REVISE indefinitely
        while blocking findings are open (L20 no-cap rule).
        """
        for high_iteration in (4, 10, 50, 999):
            state = next_loop_state(
                current_state=LoopState.IN_PROGRESS,
                severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
                blocking_findings_unresolved=["iter-1-S1"],
                iteration=high_iteration,
                max_iterations=None,
                artifact_kind="physics",
            )
            assert state == LoopState.REVISE, (
                f"Expected REVISE at iteration={high_iteration} with max_iterations=None"
            )

    def test_physics_artifact_succeeds_when_all_clear(self) -> None:
        """With max_iterations=None and no blocking/non-zero findings -> SUCCESS."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=[],
            iteration=50,
            max_iterations=None,
            artifact_kind="physics",
        )
        assert state == LoopState.SUCCESS

    def test_non_none_max_iterations_still_enforced(self) -> None:
        """max_iterations=4 (default) still escalates at cap when blocking."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 0},
            blocking_findings_unresolved=["iter-4-S1"],
            iteration=4,
            max_iterations=4,
        )
        assert state == LoopState.ESCALATE_UNRESOLVED

    def test_float_inf_still_raises(self) -> None:
        """Callers who mistakenly pass float('inf') get a TypeError (use None)."""
        with pytest.raises(TypeError):
            next_loop_state(
                current_state=LoopState.IN_PROGRESS,
                severity_counts=None,
                blocking_findings_unresolved=["iter-1-S1"],
                iteration=1,
                max_iterations=float("inf"),  # type: ignore[arg-type]
            )


class TestBriefPlanTwoRoundCapNonBlocking:
    """iter-1-W3: brief/plan artifacts auto-escalate (SUCCESS) at round >= 2
    even when non-blocking W/N findings remain, per feedback_scaffold_as_we_go.
    """

    def test_brief_artifact_exits_at_round_2_with_w_findings(self) -> None:
        """round=2, artifact_kind='brief', no blocking, W=1 -> SUCCESS (2-round cap)."""
        state = next_loop_state(
            current_state=LoopState.REVISE,
            severity_counts={"S": 0, "M": 0, "W": 1, "N": 0},
            blocking_findings_unresolved=[],
            iteration=2,
            artifact_kind="brief",
        )
        assert state == LoopState.SUCCESS

    def test_plan_artifact_exits_at_round_2_with_n_findings(self) -> None:
        """round=2, artifact_kind='plan', no blocking, N=3 -> SUCCESS."""
        state = next_loop_state(
            current_state=LoopState.REVISE,
            severity_counts={"S": 0, "M": 0, "W": 0, "N": 3},
            blocking_findings_unresolved=[],
            iteration=2,
            artifact_kind="plan",
        )
        assert state == LoopState.SUCCESS

    def test_brief_still_revises_at_round_1_with_w_findings(self) -> None:
        """round=1, artifact_kind='brief', no blocking, W=1 -> REVISE (cap not yet hit)."""
        state = next_loop_state(
            current_state=LoopState.IN_PROGRESS,
            severity_counts={"S": 0, "M": 0, "W": 1, "N": 0},
            blocking_findings_unresolved=[],
            iteration=1,
            artifact_kind="brief",
        )
        assert state == LoopState.REVISE

    def test_brief_with_blocking_still_revises_at_round_2(self) -> None:
        """Brief 2-round cap only fires when NO blocking findings remain."""
        state = next_loop_state(
            current_state=LoopState.REVISE,
            severity_counts={"S": 0, "M": 0, "W": 1, "N": 0},
            blocking_findings_unresolved=["iter-2-S1"],
            iteration=2,
            artifact_kind="brief",
        )
        assert state == LoopState.REVISE

    def test_non_brief_plan_artifact_wn_fast_exits_after_one_round(self) -> None:
        """Non-brief/plan artifact_kind (assertion) with W-only findings and
        iteration>=1 SUCCESS-exits via the W/N fast-exit rule (the
        brief/plan 2-round cap is still respected for those kinds; non-
        scaffold artifacts get a one-round fast-exit on W/N-only residue).
        """
        state = next_loop_state(
            current_state=LoopState.REVISE,
            severity_counts={"S": 0, "M": 0, "W": 1, "N": 0},
            blocking_findings_unresolved=[],
            iteration=2,
            artifact_kind="assertion",
        )
        assert state == LoopState.SUCCESS


def test_wn_fast_exit_after_one_round():
    """W/N-only findings with iteration>=1 and no blocking → SUCCESS."""
    state = next_loop_state(
        current_state=LoopState.IN_PROGRESS,
        severity_counts={"S": 0, "M": 0, "W": 2, "N": 1},
        blocking_findings_unresolved=[],
        iteration=1,
        max_iterations=None,
        artifact_kind="physics",
    )
    assert state == LoopState.SUCCESS


def test_wn_fast_exit_not_on_iteration_zero():
    """W/N fast-exit must not fire on iteration 0 (fixer hasn't run yet)."""
    state = next_loop_state(
        current_state=LoopState.IN_PROGRESS,
        severity_counts={"S": 0, "M": 0, "W": 2, "N": 0},
        blocking_findings_unresolved=[],
        iteration=0,
        max_iterations=None,
        artifact_kind="physics",
    )
    assert state == LoopState.REVISE


def test_wn_fast_exit_blocked_by_M():
    """W/N fast-exit must not fire when M > 0."""
    state = next_loop_state(
        current_state=LoopState.IN_PROGRESS,
        severity_counts={"S": 0, "M": 1, "W": 2, "N": 0},
        blocking_findings_unresolved=[],
        iteration=2,
        max_iterations=None,
        artifact_kind="physics",
    )
    assert state == LoopState.REVISE
