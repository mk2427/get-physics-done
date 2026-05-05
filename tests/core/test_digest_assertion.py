"""Tests for the /gpd:digest-assertion router + ID scheme + recursion cap.

Four tests per plan §Commit 8:
* test_router_5_cases — all 5 §5.2 router cases produce correct critic selection.
* test_recursion_depth_cap_3_validator — depth-4 raises AssertionDepthError.
* test_a_nnn_id_scheme — assertion IDs match regex ``^A-\\d{3}(\\.S\\d+)?$``.
* test_finding_id_namespace — sample finding IDs match expected pattern.

Plan-006 §C12 amendment additions (skill-input + agent contract):
* TestSkillInputContractC12 — skill markdown documents the new ``K-NNN K.X``
  per-equation form.
* TestAgentEquationIdContractC12 — agent markdown honors equation_id and
  references the canonical extractor.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gpd.core.assertion_divergence import (
    AssertionDepthError,
    route_assertion_critic,
)

# ─── Constants ───────────────────────────────────────────────────────────────

_KNOWLEDGE_CRITIC = "gpd-knowledge-critic"
_ADVERSARIAL_CRITIC = "gpd-adversarial-critic"

# Assertion ID regex: A-NNN (with optional .S{k} sub-assertion suffix)
_ASSERTION_ID_RE = re.compile(r"^A-\d{3}(\.S\d+)?$")

# Finding ID pattern: A-NNN-iter-N-S1 or A-NNN.S2-iter-3-M1
_FINDING_ID_RE = re.compile(r"^A-\d{3}(\.S\d+)?-iter-\d+-[SMWN]\d+$")


# ─── Router case fixtures ────────────────────────────────────────────────────


def _case_1_restated_no_subs() -> dict:
    """Case 1: restated-equation, no sub-assertions → gpd-knowledge-critic."""
    return {
        "assertion_id": "A-001",
        "kind": "restated-equation",
        "sub_assertions": [],
        "derivation_sketch": None,
        "upstream_ref_hash": "abc123",
        "eqn_ref_entries": ["E.1"],
    }


def _case_2_derived_no_subs() -> dict:
    """Case 2: derived-consequence, no sub-assertions → gpd-adversarial-critic."""
    return {
        "assertion_id": "A-002",
        "kind": "derived-consequence",
        "sub_assertions": [],
        "derivation_sketch": "From E.1 with Cauchy-Schwarz: ||A||^2 ≥ 0.",
        "upstream_ref_hash": None,
        "eqn_ref_entries": ["E.1"],
    }


def _case_3_mixed_kind_with_subs() -> dict:
    """Case 3: mixed-kind — empty top-level derivation_sketch + sub-assertions.

    Top-level → gpd-knowledge-critic; each sub routed by sub-kind.
    """
    return {
        "assertion_id": "A-003",
        "kind": "restated-equation",
        "sub_assertions": [
            {
                "assertion_id": "A-003.S1",
                "kind": "restated-equation",
                "sub_assertions": [],
                "derivation_sketch": None,
            },
            {
                "assertion_id": "A-003.S2",
                "kind": "derived-consequence",
                "sub_assertions": [],
                "derivation_sketch": "Derived from E.1 + K-001.",
            },
        ],
        "derivation_sketch": None,  # empty top-level sketch → case 3
        "upstream_ref_hash": "deadbeef",
        "eqn_ref_entries": ["E.2"],
    }


def _case_4_compound_derived_with_subs() -> dict:
    """Case 4: compound derived-consequence — non-empty top-level sketch + sub-assertions.

    Top-level → gpd-adversarial-critic; each sub routed by sub-kind.
    """
    return {
        "assertion_id": "A-004",
        "kind": "derived-consequence",
        "sub_assertions": [
            {
                "assertion_id": "A-004.S1",
                "kind": "restated-equation",
                "sub_assertions": [],
                "derivation_sketch": None,
            },
            {
                "assertion_id": "A-004.S2",
                "kind": "derived-consequence",
                "sub_assertions": [],
                "derivation_sketch": "Step 1: ... Step 2: ...",
            },
        ],
        "derivation_sketch": "Compound derivation: Step A → Step B → conclusion.",  # non-empty
        "upstream_ref_hash": None,
        "eqn_ref_entries": ["E.3"],
    }


def _case_5_kdoc_passthrough() -> dict:
    """Case 5: knowledge-doc input (source_kind='kdoc') → gpd-knowledge-critic."""
    return {
        "assertion_id": "K-007",  # K-doc ID (not an assertion)
        "source_kind": "kdoc",
        "kind": "",
        "sub_assertions": [],
        "derivation_sketch": None,
        "upstream_ref_hash": None,
    }


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestRouter5Cases:
    """Parametrized test over all 5 §5.2 router cases."""

    @pytest.mark.parametrize(
        "fixture_fn, expected_result",
        [
            # Case 1: restated-equation, no subs → single knowledge-critic string
            (_case_1_restated_no_subs, _KNOWLEDGE_CRITIC),
            # Case 2: derived-consequence, no subs → single adversarial-critic string
            (_case_2_derived_no_subs, _ADVERSARIAL_CRITIC),
            # Case 3: mixed-kind with subs → list starting with (top_level, knowledge-critic)
            (_case_3_mixed_kind_with_subs, None),  # see assertions below
            # Case 4: compound derived with subs → list starting with (top_level, adversarial-critic)
            (_case_4_compound_derived_with_subs, None),  # see assertions below
            # Case 5: kdoc passthrough → single knowledge-critic string
            (_case_5_kdoc_passthrough, _KNOWLEDGE_CRITIC),
        ],
    )
    def test_route_returns_correct_critic_or_list(self, fixture_fn, expected_result) -> None:
        fixture = fixture_fn()
        result = route_assertion_critic(fixture)

        if expected_result is not None:
            # Cases 1, 2, 5: expect a single string
            assert isinstance(result, str), f"Expected str, got {type(result).__name__}"
            assert result == expected_result
        else:
            # Cases 3, 4: expect a list of (identifier, critic) tuples
            assert isinstance(result, list), f"Expected list, got {type(result).__name__}"
            assert len(result) > 0

    def test_case_1_restated_no_subs_returns_knowledge_critic(self) -> None:
        """Case 1 (brief §5.2): restated-equation, no sub-assertions → knowledge-critic."""
        result = route_assertion_critic(_case_1_restated_no_subs())

        assert result == _KNOWLEDGE_CRITIC

    def test_case_2_derived_no_subs_returns_adversarial_critic(self) -> None:
        """Case 2 (brief §5.2): derived-consequence, no sub-assertions → adversarial-critic."""
        result = route_assertion_critic(_case_2_derived_no_subs())

        assert result == _ADVERSARIAL_CRITIC

    def test_case_3_mixed_kind_routing(self) -> None:
        """Case 3 (brief §5.2): empty top-level sketch + subs → per-sub routing list."""
        result = route_assertion_critic(_case_3_mixed_kind_with_subs())

        assert isinstance(result, list)
        # First entry is the top-level: must be (top_level, knowledge-critic)
        assert result[0] == ("top_level", _KNOWLEDGE_CRITIC)
        # Sub A-003.S1 is restated-equation → knowledge-critic
        assert ("A-003.S1", _KNOWLEDGE_CRITIC) in result
        # Sub A-003.S2 is derived-consequence → adversarial-critic
        assert ("A-003.S2", _ADVERSARIAL_CRITIC) in result

    def test_case_4_compound_derived_routing(self) -> None:
        """Case 4 (brief §5.2): non-empty top-level sketch + subs → adversarial top + per-sub."""
        result = route_assertion_critic(_case_4_compound_derived_with_subs())

        assert isinstance(result, list)
        # First entry is the top-level: must be (top_level, adversarial-critic)
        assert result[0] == ("top_level", _ADVERSARIAL_CRITIC)
        # Sub A-004.S1 is restated-equation → knowledge-critic
        assert ("A-004.S1", _KNOWLEDGE_CRITIC) in result
        # Sub A-004.S2 is derived-consequence → adversarial-critic
        assert ("A-004.S2", _ADVERSARIAL_CRITIC) in result

    def test_case_5_kdoc_passthrough_returns_knowledge_critic(self) -> None:
        """Case 5 (brief §5.2): source_kind='kdoc' → knowledge-critic passthrough."""
        result = route_assertion_critic(_case_5_kdoc_passthrough())

        assert result == _KNOWLEDGE_CRITIC

    def test_case_3_list_length_matches_subs_plus_top(self) -> None:
        """Case 3: list has (1 top + N subs) entries."""
        fixture = _case_3_mixed_kind_with_subs()
        result = route_assertion_critic(fixture)

        assert isinstance(result, list)
        assert len(result) == 1 + len(fixture["sub_assertions"])

    def test_case_4_list_length_matches_subs_plus_top(self) -> None:
        """Case 4: list has (1 top + N subs) entries."""
        fixture = _case_4_compound_derived_with_subs()
        result = route_assertion_critic(fixture)

        assert isinstance(result, list)
        assert len(result) == 1 + len(fixture["sub_assertions"])


class TestRecursionDepthCapValidator:
    """depth > 3 raises AssertionDepthError before entering the critic loop."""

    def _build_nested_assertion(self, depth: int, base_id: str = "A-099") -> dict:
        """Build an assertion with sub-assertions nested `depth` levels deep."""
        if depth == 0:
            return {
                "assertion_id": f"{base_id}.S1",
                "kind": "restated-equation",
                "sub_assertions": [],
                "derivation_sketch": None,
            }
        return {
            "assertion_id": base_id,
            "kind": "restated-equation",
            "sub_assertions": [
                self._build_nested_assertion(depth - 1, f"{base_id}.S1")
            ],
            "derivation_sketch": None,
        }

    def test_depth_0_no_subs_passes_validator(self) -> None:
        """Top-level assertion with no sub-assertions: depth=0, no error."""
        assertion = _case_1_restated_no_subs()
        # Should not raise
        result = route_assertion_critic(assertion)
        assert result == _KNOWLEDGE_CRITIC

    def test_depth_1_subs_passes_validator(self) -> None:
        """One level of sub-assertions: depth=1, no error."""
        assertion = _case_3_mixed_kind_with_subs()
        # Should not raise
        result = route_assertion_critic(assertion)
        assert isinstance(result, list)

    def test_depth_3_passes_validator(self) -> None:
        """Exactly depth-3 nesting: at the cap, no error."""
        assertion = self._build_nested_assertion(depth=3)
        # Should not raise
        result = route_assertion_critic(assertion)
        assert result is not None

    def test_depth_4_raises_assertion_depth_error(self) -> None:
        """depth=4 (one beyond cap): raises AssertionDepthError."""
        assertion = self._build_nested_assertion(depth=4)

        with pytest.raises(AssertionDepthError):
            route_assertion_critic(assertion)

    def test_depth_5_raises_assertion_depth_error(self) -> None:
        """depth=5 (two beyond cap): also raises AssertionDepthError."""
        assertion = self._build_nested_assertion(depth=5)

        with pytest.raises(AssertionDepthError):
            route_assertion_critic(assertion)

    def test_assertion_depth_error_message_mentions_depth(self) -> None:
        """AssertionDepthError message names the depth and the cap."""
        assertion = self._build_nested_assertion(depth=4)

        with pytest.raises(AssertionDepthError, match=r"(?i)(depth|cap|3|4)"):
            route_assertion_critic(assertion)

    def test_validator_runs_before_critic_dispatch(self) -> None:
        """Depth validation happens regardless of kind (brief §5.2 ordering)."""
        # Use a derived-consequence kind to confirm depth check is kind-agnostic.
        deep_derived = self._build_nested_assertion(depth=4)
        deep_derived["kind"] = "derived-consequence"
        deep_derived["derivation_sketch"] = "Step 1 → ..."

        with pytest.raises(AssertionDepthError):
            route_assertion_critic(deep_derived)


class TestANNNIdScheme:
    r"""Assertion IDs from a fixture set all match ``^A-\d{3}(\.S\d+)?$``."""

    @pytest.mark.parametrize(
        "assertion_id",
        [
            # Top-level assertions
            "A-001",
            "A-007",
            "A-099",
            "A-100",
            "A-999",
            # Sub-assertions
            "A-007.S1",
            "A-007.S2",
            "A-007.S9",
            "A-007.S10",
            "A-099.S1",
        ],
    )
    def test_valid_assertion_id_matches_regex(self, assertion_id: str) -> None:
        """Valid assertion IDs match the canonical regex."""
        assert _ASSERTION_ID_RE.match(assertion_id), (
            f"{assertion_id!r} should match ^A-\\d{{3}}(\\.S\\d+)?$"
        )

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "A-1",        # too few digits
            "A-01",       # too few digits
            "A-1000",     # too many digits
            "B-007",      # wrong prefix
            "a-007",      # lowercase
            "A-007.1",    # missing S prefix
            "A-007.s1",   # lowercase s
            "A-007.S",    # no digit after S
            "A007",       # missing dash
            "",           # empty
        ],
    )
    def test_invalid_assertion_id_rejected(self, invalid_id: str) -> None:
        """Invalid IDs do not match the canonical regex."""
        assert not _ASSERTION_ID_RE.match(invalid_id), (
            f"{invalid_id!r} should NOT match the assertion ID regex"
        )

    def test_fixture_assertion_ids_all_valid(self) -> None:
        r"""IDs from the 5 router fixtures all match ``^A-\d{3}(\\.S\d+)?$``."""
        fixtures = [
            _case_1_restated_no_subs(),
            _case_2_derived_no_subs(),
            _case_3_mixed_kind_with_subs(),
            _case_4_compound_derived_with_subs(),
        ]

        def _collect_ids(d: dict) -> list[str]:
            """Recursively collect all assertion_id values."""
            ids = []
            if "assertion_id" in d and d["assertion_id"].startswith("A-"):
                ids.append(d["assertion_id"])
            for sub in d.get("sub_assertions") or []:
                ids.extend(_collect_ids(sub))
            return ids

        for fixture in fixtures:
            for aid in _collect_ids(fixture):
                assert _ASSERTION_ID_RE.match(aid), (
                    f"Fixture assertion_id {aid!r} does not match canonical regex"
                )

    def test_sub_assertion_ids_are_suffixed_correctly(self) -> None:
        """A-NNN.S1, A-NNN.S2 notation per brief §9.2 commit 8 resolution."""
        sub_ids = ["A-007.S1", "A-007.S2", "A-007.S3"]
        for sid in sub_ids:
            assert _ASSERTION_ID_RE.match(sid)
        # Verify the sub-assertion suffix is correctly extracted.
        m = _ASSERTION_ID_RE.match("A-007.S3")
        assert m is not None
        assert m.group(1) == ".S3"


class TestFindingIdNamespace:
    r"""Sample finding IDs from the router output match ``A-\d{3}(\.S\d+)?-iter-\d+-[SMWN]\d+``."""

    @pytest.mark.parametrize(
        "finding_id",
        [
            # Top-level finding IDs (brief §5.2 iter-3-W1 format)
            "A-001-iter-1-S1",   # serious finding 1 at iter 1
            "A-007-iter-3-M1",   # moderate finding 1 at iter 3
            "A-007-iter-3-W2",   # weak finding 2 at iter 3
            "A-007-iter-3-N1",   # note finding 1 at iter 3
            "A-099-iter-10-S2",  # two-digit iter, S-severity
            # Sub-assertion finding IDs (brief §5.2 iter-3-W1 for sub)
            "A-007.S1-iter-1-S1",
            "A-007.S2-iter-3-M1",  # brief §5.2 canonical example
            "A-007.S2-iter-3-W1",
            "A-099.S1-iter-2-N1",
        ],
    )
    def test_valid_finding_id_matches_pattern(self, finding_id: str) -> None:
        """Valid finding IDs match the canonical namespace pattern."""
        assert _FINDING_ID_RE.match(finding_id), (
            f"{finding_id!r} should match A-\\d{{3}}(\\.S\\d+)?-iter-\\d+-[SMWN]\\d+"
        )

    @pytest.mark.parametrize(
        "invalid_finding_id",
        [
            "A-007-1-S1",          # missing 'iter-' prefix
            "A-007-iter-3-X1",     # X is not a valid severity letter
            "A-7-iter-3-S1",       # too few digits in A-NNN
            "K-007-iter-3-S1",     # wrong prefix (K- not A-)
            "A-007.S2-3-M1",       # missing 'iter-' between sub-id and round
            "A-007-iter-S1",       # missing round number
        ],
    )
    def test_invalid_finding_id_rejected(self, invalid_finding_id: str) -> None:
        """Invalid finding IDs do not match the pattern."""
        assert not _FINDING_ID_RE.match(invalid_finding_id), (
            f"{invalid_finding_id!r} should NOT match the finding ID pattern"
        )

    def test_finding_ids_from_case3_routing_are_namespaced_correctly(self) -> None:
        """Sub-assertion IDs from case-3 routing can be composed into valid finding IDs."""
        fixture = _case_3_mixed_kind_with_subs()
        routing = route_assertion_critic(fixture)
        assert isinstance(routing, list)

        for identifier, _critic in routing:
            # Construct sample finding IDs using the identifier from router output.
            if identifier == "top_level":
                # Top-level: use the assertion's own A-NNN ID.
                base = fixture["assertion_id"]
            else:
                base = identifier

            for severity in ("S", "M", "W", "N"):
                finding_id = f"{base}-iter-1-{severity}1"
                assert _FINDING_ID_RE.match(finding_id), (
                    f"Composed finding ID {finding_id!r} does not match pattern "
                    f"(base={base!r}, severity={severity!r})"
                )


# ─── Plan-006 §C12 amendment: skill input + agent equation_id contract ───────


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_DOC = _REPO_ROOT / "src" / "gpd" / "commands" / "digest-assertion.md"
_AGENT_DOC = _REPO_ROOT / "src" / "gpd" / "agents" / "gpd-assertion-digester.md"
_WORKFLOW_DOC = _REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "digest-assertion.md"


class TestSkillInputContractC12:
    """C12 amendment: ``/gpd:digest-assertion`` skill accepts ``K-NNN K.X``."""

    def test_skill_doc_documents_k_nnn_k_x_form(self) -> None:
        """The skill doc's <objective> block lists the new
        ``K-001 K.5`` per-equation input form."""
        text = _SKILL_DOC.read_text(encoding="utf-8")
        assert "K-001 K.5" in text or "K-NNN K.X" in text, (
            "skill doc must document the new K-NNN K.X form (C12 amendment)"
        )
        # Must explicitly say it produces a restated-equation assertion
        # targeting the equation specifically. DOTALL because the
        # markdown bullet wraps across lines.
        assert re.search(
            r"restated-equation.*?equation\s+`?K\.5`?|K\.5.*?restated",
            text,
            re.IGNORECASE | re.DOTALL,
        ), "skill doc must say K-NNN K.X targets the equation specifically"

    def test_skill_doc_threads_equation_id_through_orchestration(self) -> None:
        """The skill's <adversarial_orchestration> block mentions threading
        equation_id through to the digester."""
        text = _SKILL_DOC.read_text(encoding="utf-8")
        # The C12 amendment threads equation_id; doc must reference it
        # somewhere in the orchestration block.
        assert "equation_id" in text, (
            "skill doc must reference equation_id parameter (C12 amendment)"
        )

    def test_workflow_input_schema_has_equation_id_field(self) -> None:
        """Workflow input_schema documents the new equation_id field."""
        text = _WORKFLOW_DOC.read_text(encoding="utf-8")
        assert "equation_id" in text, (
            "workflow doc must list equation_id in <input_schema>"
        )
        # The detect_input step references the new K-NNN + equation_id form.
        assert (
            "K-001 K.5" in text
            or "K.X" in text
            or "K-007 E.3" in text
        ), "workflow detect_input step must describe the new form"

    def test_skill_input_form_regex_matches(self) -> None:
        """The K-NNN + (K.X|E.X) form is parseable by a deterministic regex.

        The dispatcher and the skill prompt construction both need to
        agree on a regex that recognizes this input form. We pin it
        here so future drift is caught.
        """
        # Pattern: K-{3-digit-NNN}[-slug] then whitespace then K.\d+ or E.\d+.
        pattern = re.compile(
            r"^(K-\d{3}(?:-[a-z0-9-]+)?)\s+((?:K|E)\.\d+)\s*$"
        )
        good = [
            "K-001 K.5",
            "K-003-kazakov-zheng-lattice-ym-bootstrap K.7",
            "K-042 E.3",
        ]
        bad = [
            "K-1 K.5",         # too few digits
            "K-001 X.5",       # bad equation prefix
            "K-001",           # missing equation
            "E.1 E.2",         # not a K-NNN form
        ]
        for ok in good:
            assert pattern.match(ok), f"expected {ok!r} to parse"
        for bad_in in bad:
            assert not pattern.match(bad_in), f"expected {bad_in!r} to reject"


class TestAgentEquationIdContractC12:
    """C12 amendment: gpd-assertion-digester honors equation_id parameter."""

    def test_agent_doc_describes_equation_id_path(self) -> None:
        """Agent's digestion protocol documents the K-NNN + equation_id path."""
        text = _AGENT_DOC.read_text(encoding="utf-8")
        assert "equation_id" in text, (
            "agent doc must describe equation_id handling (C12 amendment)"
        )
        # Must reference the canonical extractor so the agent uses the
        # same equation-form parser as the canary driver.
        assert "extract_equations_from_kdoc" in text, (
            "agent doc must point to gpd.core.sympy_oracle.extract_equations_from_kdoc"
        )

    def test_agent_doc_specifies_per_equation_slug_and_kind(self) -> None:
        """Agent doc says: slug from equation summary, kind=restated-equation."""
        text = _AGENT_DOC.read_text(encoding="utf-8")
        # The equation-slug rule: don't slug from the kdoc lead claim.
        assert "equation-slug" in text or "equation slug" in text.lower()
        # The kind must always be restated-equation on this path.
        # (Search after the equation_id mention to scope the match.)
        eq_section = text[text.index("equation_id input"):]
        assert "restated-equation" in eq_section, (
            "agent doc must declare kind: restated-equation on per-eq path"
        )

    def test_agent_doc_falls_back_when_equation_id_absent(self) -> None:
        """Agent doc explicitly handles the equation_id-absent fallback."""
        text = _AGENT_DOC.read_text(encoding="utf-8")
        assert (
            "equation_id` is absent" in text
            or "equation_id is absent" in text
            or "lead-equation fallback" in text
        ), "agent doc must describe equation_id-absent fallback behavior"


class TestAgentStrictRestatementContractC13:
    """Plan-006 §C13: gpd-assertion-digester enforces literal restatement
    on the K-NNN + equation_id path.

    The C12 smoke surfaced an agent that produced the BFSS virial-form
    expansion (`-2<K> + 4<V> + <F> = 0`) when invoked with `K-001 K.5`
    instead of the literal `<[H, Tr X P]> = 0` constraint. Both forms
    are mathematically equivalent, but `compute_upstream_ref_hash` (the
    no-hallucination criterion in `tests/canary/criteria/no_hallucination.py`)
    matches TEXTUALLY, so an expanded form fails §7.4 against the
    kdoc's stored hash. C13 tightens the digester prompt to forbid
    silent expansion / derivation on this path.
    """

    def test_agent_doc_forbids_derivation_on_per_equation_path(self) -> None:
        """The strict-restatement directive must be present verbatim.

        These specific strings are load-bearing; an accidental edit
        that drops them silently regresses the digester to substantive
        (rather than literal) restatement and breaks §7.4 hash match.
        """
        text = _AGENT_DOC.read_text(encoding="utf-8")
        # Load-bearing verbatim strings from the C13 directive.
        assert "DO NOT derive" in text, (
            "agent doc must contain literal 'DO NOT derive' directive"
            " (C13 strict-restatement contract)"
        )
        assert "literal kdoc equation body" in text, (
            "agent doc must reference 'literal kdoc equation body'"
            " (C13 strict-restatement contract)"
        )

    def test_agent_doc_warns_against_commutator_unfolding(self) -> None:
        """The directive cites the BFSS commutator example (the actual
        C12 smoke regression) so future readers understand why."""
        text = _AGENT_DOC.read_text(encoding="utf-8")
        # The BFSS K-001 K.5 case unfolded `[H, Tr X P]` into a virial
        # form. The directive must call this out as a textual mismatch.
        assert "commutator" in text.lower() or "Tr" in text, (
            "agent doc should cite the commutator example so the rule"
            " is concrete (C13)"
        )
        # And explain the textual-match consequence so the agent can't
        # rationalize "but it's mathematically equivalent".
        assert "TEXTUAL" in text or "textual" in text.lower(), (
            "agent doc should explain that §7.4 matches textually"
            " (C13)"
        )

    def test_agent_doc_tells_agent_to_block_when_derivation_required(
        self,
    ) -> None:
        """Escape hatch: when a derivation IS needed, the agent must
        return ``status: blocked`` rather than silently produce an
        equivalent form. The mixed-input derived-consequence path is
        the right route for derivations."""
        text = _AGENT_DOC.read_text(encoding="utf-8")
        # Pull the strict-restatement section to scope the search.
        idx = text.index("Strict literal restatement")
        section = text[idx : idx + 3000]
        assert "blocked" in section, (
            "agent doc must instruct: return status: blocked when"
            " derivation is required (C13)"
        )
        assert "derived-consequence" in section, (
            "agent doc must point to derived-consequence path as the"
            " correct route for derivations (C13)"
        )

    def test_agent_doc_lists_four_extraction_forms(self) -> None:
        """Plan-006 C13 added a 4th extraction form (display-math
        ``(K.N) ... :\\n$$body$$`` used by K-003). The agent doc must
        document all four so the operator knows which forms are
        recognized.
        """
        text = _AGENT_DOC.read_text(encoding="utf-8")
        # Pull the equation_id section.
        idx = text.index("equation_id input")
        section = text[idx : idx + 2000]
        # Canonical inline:
        assert "canonical inline" in section.lower()
        # New display-math kdoc form (K-003):
        assert "display-math kdoc" in section.lower() or "K-003" in section
        # Legacy display:
        assert "legacy display" in section.lower()
        # EQN-REF compatibility alias:
        assert "EQN-REF" in section or "compatibility alias" in section.lower()
