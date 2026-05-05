"""Round-trip tests for ``state.json <-> STATE.md <-> state.json`` (commit 4b).

Brief 002 §5.1 (iv) added ``adversarial_review_status.blocking_findings_unresolved``
as a new top-level key in ``state.json``.  This test file exercises the
full dual-write discipline per ``error-blast-radius-scope.md`` §state-management:

* JSON payload round-trips losslessly through ``generate_state_markdown``
  + ``parse_state_to_json`` (STATE.md is the markdown projection; state.json
  is authoritative).
* ``sync_state_json_core`` preserves the status block across a STATE.md
  rewrite.
"""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.constants import ProjectLayout
from gpd.core.state import (
    InvalidationEvent,
    ResearchState,
    default_state_dict,
    generate_state_markdown,
    parse_state_md,
    parse_state_to_json,
    save_state_json,
    save_state_markdown,
    sync_state_json,
)


def _setup_project(tmp_path: Path) -> ProjectLayout:
    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)
    (layout.gpd / "phases").mkdir(exist_ok=True)
    (layout.gpd / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (layout.gpd / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    return layout


class TestAdversarialReviewStatusRoundTrip:
    """Brief 002 §5.1 (iv): ``adversarial_review_status.blocking_findings_unresolved``
    survives the full state.json <-> STATE.md <-> state.json cycle.
    """

    def test_default_empty_list_roundtrips(self) -> None:
        """Default state has empty blocking list; round-trip preserves it."""
        state = default_state_dict()
        assert state["adversarial_review_status"] == {
            "blocking_findings_unresolved": []
        }
        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert parsed["adversarial_review_status"] == {
            "blocking_findings_unresolved": []
        }

    def test_populated_list_roundtrips_through_markdown(self) -> None:
        """Non-empty blocking list is preserved through generate + parse."""
        state = default_state_dict()
        state["adversarial_review_status"] = {
            "blocking_findings_unresolved": [
                "iter-1-S1",
                "iter-2-M3",
                "sub-a-iter-2-W1",  # namespaced per feedback_simple_finding_ids
            ]
        }
        md = generate_state_markdown(state)
        assert "## Adversarial Review Status" in md
        assert "iter-1-S1" in md
        assert "sub-a-iter-2-W1" in md

        parsed_md = parse_state_md(md)
        assert parsed_md["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == ["iter-1-S1", "iter-2-M3", "sub-a-iter-2-W1"]

        parsed_json = parse_state_to_json(md)
        assert parsed_json["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == ["iter-1-S1", "iter-2-M3", "sub-a-iter-2-W1"]

    def test_full_state_json_to_md_to_state_json_roundtrip(self, tmp_path: Path) -> None:
        """Full round-trip through the dual-write engine: write state.json,
        regenerate STATE.md, re-parse STATE.md back into state.json.
        """
        layout = _setup_project(tmp_path)
        state = default_state_dict()
        state["adversarial_review_status"] = {
            "blocking_findings_unresolved": ["iter-1-S1", "iter-3-M2"]
        }
        state["position"] = {
            **state["position"],
            "current_phase": "02",
            "status": "in_progress",
            "current_plan": "1",
            "total_plans_in_phase": 2,
        }

        # Step 1: write authoritative state.json + STATE.md.
        save_state_json(tmp_path, state)
        md = generate_state_markdown(state)
        save_state_markdown(tmp_path, md)

        # Step 2: parse STATE.md back and sync into state.json.
        resynced = sync_state_json(tmp_path, md)
        assert resynced["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == ["iter-1-S1", "iter-3-M2"]

        # Step 3: verify the on-disk state.json carries the block.
        raw_json = json.loads(layout.state_json.read_text(encoding="utf-8"))
        assert raw_json["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == ["iter-1-S1", "iter-3-M2"]

    def test_empty_status_block_is_emitted_and_parsed(self, tmp_path: Path) -> None:
        """An empty blocking list still emits the status section with
        a ``- None`` placeholder; parse recovers the empty list.
        """
        state = default_state_dict()
        md = generate_state_markdown(state)
        assert "## Adversarial Review Status" in md
        assert "**Blocking findings unresolved:**" in md
        parsed = parse_state_md(md)
        assert parsed["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == []

    def test_status_block_survives_add_blocking_then_clear(self, tmp_path: Path) -> None:
        """Simulates a full loop: start empty, add blocking IDs, clear, verify
        each round-trip preserves the intermediate ledger state."""
        _setup_project(tmp_path)
        state = default_state_dict()

        # Round 1: add blocking IDs and round-trip through MD.
        state["adversarial_review_status"] = {
            "blocking_findings_unresolved": ["iter-1-S1"]
        }
        md1 = generate_state_markdown(state)
        parsed1 = parse_state_to_json(md1)
        assert parsed1["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == ["iter-1-S1"]

        # Round 2: clear, round-trip, verify empty.
        parsed1["adversarial_review_status"] = {"blocking_findings_unresolved": []}
        md2 = generate_state_markdown(parsed1)
        parsed2 = parse_state_to_json(md2)
        assert parsed2["adversarial_review_status"][
            "blocking_findings_unresolved"
        ] == []


class TestInvalidationEventsRoundTrip:
    """Brief 002 §8.3 + §8.4 (commit 10d): ``invalidation_events`` ledger
    survives the full state.json <-> STATE.md <-> state.json cycle.
    """

    def test_invalidation_events_roundtrip(self) -> None:
        """Two InvalidationEvent entries round-trip through generate + parse,
        with all fields preserved field-by-field (not just string equality).
        """
        state = default_state_dict()
        events = [
            {
                "event_id": "evt-0001-aaaa-bbbb-cccc-dddddddddddd",
                "root_event_id": "evt-0001-aaaa-bbbb-cccc-dddddddddddd",
                "utc_timestamp": "2026-04-21T10:00:00+00:00",
                "source_type": "knowledge",
                "source_id": "K-001",
                "affected_result_ids": ["R-03-07", "R-03-08"],
                "status": "open",
            },
            {
                "event_id": "evt-0002-aaaa-bbbb-cccc-dddddddddddd",
                "root_event_id": "evt-0001-aaaa-bbbb-cccc-dddddddddddd",
                "utc_timestamp": "2026-04-21T10:01:00+00:00",
                "source_type": "assertion",
                "source_id": "A-001",
                "affected_result_ids": ["R-04-02"],
                "status": "resolved",
            },
        ]
        state["invalidation_events"] = events

        # Generate markdown and parse back.
        md = generate_state_markdown(state)

        # Verify the HTML comment tags are present in the markdown.
        assert "<!--invalidation_events-->" in md
        assert "<!--/invalidation_events-->" in md
        assert "## Invalidation Events" in md

        parsed_md = parse_state_md(md)
        recovered = parsed_md["invalidation_events"]

        assert len(recovered) == 2, f"Expected 2 events, got {len(recovered)}: {recovered}"

        # First event — all fields.
        ev0 = recovered[0]
        assert ev0["event_id"] == events[0]["event_id"]
        assert ev0["root_event_id"] == events[0]["root_event_id"]
        assert ev0["utc_timestamp"] == events[0]["utc_timestamp"]
        assert ev0["source_type"] == events[0]["source_type"]
        assert ev0["source_id"] == events[0]["source_id"]
        assert ev0["affected_result_ids"] == events[0]["affected_result_ids"]
        assert ev0["status"] == events[0]["status"]

        # Second event — spot-check key discriminants.
        ev1 = recovered[1]
        assert ev1["event_id"] == events[1]["event_id"]
        assert ev1["source_type"] == events[1]["source_type"]
        assert ev1["status"] == events[1]["status"]
        assert ev1["affected_result_ids"] == events[1]["affected_result_ids"]

    def test_invalidation_events_schema_extra_allow(self) -> None:
        """ResearchState validates with the new invalidation_events field.

        Proves that ``model_config = {"extra": "allow"}`` (or the explicit
        field declaration) handles the key without raising a ValidationError.
        """
        events = [
            {
                "event_id": "evt-schema-test-0001",
                "root_event_id": "evt-schema-test-0001",
                "utc_timestamp": "2026-04-21T12:00:00+00:00",
                "source_type": "result",
                "source_id": "R-001",
                "affected_result_ids": [],
                "status": "open",
            }
        ]
        state_dict = default_state_dict()
        state_dict["invalidation_events"] = events

        # Must not raise.
        validated = ResearchState.model_validate(state_dict)
        dumped = validated.model_dump()

        assert "invalidation_events" in dumped
        assert len(dumped["invalidation_events"]) == 1
        ev = dumped["invalidation_events"][0]
        # Either the field is stored as an InvalidationEvent model (model_dump
        # returns a dict) or passed through directly.
        if isinstance(ev, dict):
            assert ev["event_id"] == "evt-schema-test-0001"
            assert ev["status"] == "open"
        else:
            assert ev.event_id == "evt-schema-test-0001"
            assert ev.status == "open"
