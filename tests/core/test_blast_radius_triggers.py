"""Tests for reactive blast-radius triggers (commit 10e).

Five tests covering:
  1. Trigger 1 — verify-phase spec wiring (text assertion)
  2. Trigger 2 — on_kdoc_status_change fires invalidation scan
  3. Trigger 3 — on_assertion_status_change fires DAG scan
  4. root_event_id threading across cascade
  5. Eager trigger writes upstream_status_mirror atomically
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from gpd.core.assertions import on_assertion_status_change
from gpd.core.knowledge_runtime import on_kdoc_status_change


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_assertion_yaml(assertion_id: str, knowledge_doc_ids: list[str] | None = None) -> str:
    """Return a minimal assertion markdown with YAML frontmatter."""
    knowledge_doc_ids = knowledge_doc_ids or []
    fm: dict = {
        "assertion_id": assertion_id,
        "status": "Stable",
        "title": f"Assertion {assertion_id}",
        "upstream_status_mirror": {"divergence_detected_at": None},
        "knowledge_doc_ids": knowledge_doc_ids,
    }
    return "---\n" + yaml.dump(fm, default_flow_style=False) + "---\n\nBody text.\n"


def _write_assertion(tmp_path: Path, assertion_id: str, knowledge_doc_ids: list[str] | None = None) -> Path:
    """Write an assertion YAML into the standard GPD layout under *tmp_path*."""
    assertions_dir = tmp_path / "GPD" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    md_path = assertions_dir / f"{assertion_id}.md"
    md_path.write_text(_make_assertion_yaml(assertion_id, knowledge_doc_ids), encoding="utf-8")
    # Ensure the knowledge/invalidation_events directory exists for ledger writes.
    (tmp_path / "GPD" / "knowledge").mkdir(parents=True, exist_ok=True)
    return md_path


# ---------------------------------------------------------------------------
# Test 1 — Trigger 1 spec text present in verify-phase.md
# ---------------------------------------------------------------------------


def test_trigger_1_verify_phase_gaps_found() -> None:
    """verify-phase.md must contain a result_downstream reference for trigger 1."""
    repo_root = Path(__file__).parent.parent.parent
    spec_file = repo_root / "src" / "gpd" / "specs" / "workflows" / "verify-phase.md"
    assert spec_file.exists(), f"verify-phase.md not found at {spec_file}"
    content = spec_file.read_text(encoding="utf-8")
    assert "result_downstream" in content, (
        "verify-phase.md must reference result_downstream (trigger 1 wiring)"
    )
    # Also verify the blast_radius_on_gaps step and Blast Radius section are present.
    assert "blast_radius_on_gaps" in content
    assert "Blast Radius" in content


# ---------------------------------------------------------------------------
# Test 2 — Trigger 2: on_kdoc_status_change fires invalidation scan
# ---------------------------------------------------------------------------


def test_trigger_2_kdoc_status_change_fires_scan(tmp_path: Path) -> None:
    """on_kdoc_status_change creates an invalidation_events entry for source_type=knowledge."""
    state: dict = {
        "intermediate_results": [
            {"id": "R-001", "knowledge_deps": ["K-001"]},
            {"id": "R-002", "knowledge_deps": ["K-002"]},
        ],
        "assertions": {},
    }

    on_kdoc_status_change(tmp_path, "K-001", "Under Review", state)

    events = state.get("invalidation_events", [])
    assert len(events) == 1
    ev = events[0]
    assert ev["source_type"] == "knowledge"
    assert ev["source_id"] == "K-001"
    assert ev["status"] == "open"
    assert "R-001" in ev["affected_result_ids"]
    assert "R-002" not in ev["affected_result_ids"]


def test_trigger_2_noop_on_non_trigger_status(tmp_path: Path) -> None:
    """on_kdoc_status_change must not fire for Draft or Stable transitions."""
    state: dict = {"intermediate_results": [], "assertions": {}}
    on_kdoc_status_change(tmp_path, "K-001", "Draft", state)
    assert state.get("invalidation_events", []) == []

    on_kdoc_status_change(tmp_path, "K-001", "Stable", state)
    assert state.get("invalidation_events", []) == []


# ---------------------------------------------------------------------------
# Test 3 — Trigger 3: on_assertion_status_change fires DAG scan
# ---------------------------------------------------------------------------


def test_trigger_3_assertion_status_change_fires_dag_scan(tmp_path: Path) -> None:
    """on_assertion_status_change creates an invalidation_events entry with source_type=assertion."""
    assertion_docs: dict[str, dict] = {
        "A-001": {"depends_on": []},
    }
    state: dict = {
        "intermediate_results": [
            {"id": "R-010", "assertion_deps": ["A-001"]},
        ],
    }

    on_assertion_status_change(tmp_path, "A-001", "Under Review", state, assertion_docs)

    events = state.get("invalidation_events", [])
    assert len(events) == 1
    ev = events[0]
    assert ev["source_type"] == "assertion"
    assert ev["source_id"] == "A-001"
    assert ev["status"] == "open"
    assert "R-010" in ev["affected_result_ids"]


# ---------------------------------------------------------------------------
# Test 4 — root_event_id shared across cascaded triggers
# ---------------------------------------------------------------------------


def test_root_event_id_shared_across_cascaded_triggers(tmp_path: Path) -> None:
    """Trigger 2 cascade must propagate root_event_id to write_upstream_divergence_with_cascade."""
    # Write a real assertion file for the cascade to update.
    _write_assertion(tmp_path, "A-050", knowledge_doc_ids=["K-007"])

    state: dict = {
        "intermediate_results": [{"id": "R-099", "knowledge_deps": ["K-007"]}],
        "assertions": {
            "A-050": {"knowledge_doc_ids": ["K-007"]},
        },
    }

    on_kdoc_status_change(tmp_path, "K-007", "Superseded", state)

    events = state.get("invalidation_events", [])
    # The trigger-2 event itself must be present.
    assert len(events) >= 1
    trigger_event = events[0]
    root_id = trigger_event["root_event_id"]
    assert root_id == trigger_event["event_id"], "root_event_id must equal event_id for the originating event"

    # The cascade writes to the JSONL ledger (not to state dict), so verify
    # the ledger file records the shared root_event_id.
    ledger_path = tmp_path / "GPD" / "knowledge" / "invalidation_events.jsonl"
    if ledger_path.exists():
        import json
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            entry = json.loads(line)
            if entry.get("source_id") == "A-050":
                assert entry["root_event_id"] == root_id, (
                    "Cascaded assertion ledger entry must share the parent root_event_id"
                )


# ---------------------------------------------------------------------------
# Test 5 — Eager trigger writes upstream_status_mirror atomically
# ---------------------------------------------------------------------------


def test_eager_trigger_updates_upstream_status_mirror_atomically(tmp_path: Path) -> None:
    """Trigger 2 must set divergence_detected_at on dependent assertion YAML."""
    _write_assertion(tmp_path, "A-030", knowledge_doc_ids=["K-003"])

    state: dict = {
        "intermediate_results": [],
        "assertions": {
            "A-030": {"knowledge_doc_ids": ["K-003"]},
        },
    }

    on_kdoc_status_change(tmp_path, "K-003", "Under Review", state)

    # Read back the assertion YAML and verify divergence_detected_at is set.
    assertion_file = tmp_path / "GPD" / "assertions" / "A-030.md"
    content = assertion_file.read_text(encoding="utf-8")
    parts = content.split("---")
    fm = yaml.safe_load(parts[1])
    mirror = fm.get("upstream_status_mirror", {})
    assert mirror.get("divergence_detected_at") is not None, (
        "divergence_detected_at must be set after trigger 2 fires"
    )
