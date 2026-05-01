"""Regression checks for planner workflow prompt deduplication."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_planner_workflows_reference_shared_templates_instead_of_repeating_policy_blocks() -> None:
    plan_phase = _read("plan-phase.md")
    quick = _read("quick.md")
    verify_work = _read("verify-work.md")

    for text in (plan_phase, quick, verify_work):
        assert "templates/plan-contract-schema.md" in text

    assert "templates/planner-subagent-prompt.md" in plan_phase
    assert "templates/phase-prompt.md" in plan_phase
    assert "templates/planner-subagent-prompt.md" in quick
    assert "templates/phase-prompt.md" in quick
    assert "shared planner template, phase template, and `templates/plan-contract-schema.md`" in plan_phase
    assert "Before planning, load the shared planner template, phase template, and canonical contract schema." in quick
    assert (
        "Use the shared planner template, phase template, and `templates/plan-contract-schema.md` "
        "before drafting the fix plan."
    ) in verify_work
    assert (
        "Use the shared planner template, phase template, and `templates/plan-contract-schema.md` "
        "before rewriting the fix plan."
    ) in verify_work


def test_planner_workflows_do_not_embed_the_removed_long_policy_blocks() -> None:
    plan_phase = _read("plan-phase.md")
    verify_work = _read("verify-work.md")

    for legacy_phrase in (
        "Each plan has a complete contract block (claims, deliverables, acceptance tests, forbidden proxies, uncertainty markers, and `references[]` whenever grounding is not already explicit elsewhere in the contract)",
        "Non-scoping plans keep `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` non-empty.",
        "Include `references[]` only when the plan relies on external grounding",
        "Keep the full canonical frontmatter, including `wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, and `contract`.",
        "If the downstream fix plan will need specialized tooling or any other machine-checkable hard validation requirement, surface it in PLAN frontmatter `tool_requirements` before drafting task prose.",
        "If the revised fix plan still needs specialized tooling or any other machine-checkable hard validation requirement, keep it in PLAN frontmatter `tool_requirements` before rewriting task prose.",
        ):
        assert legacy_phrase not in plan_phase
        assert legacy_phrase not in verify_work


def test_planner_workflows_keep_tangent_policy_single_sourced() -> None:
    plan_phase = _read("plan-phase.md")

    assert plan_phase.count("Required 4-way tangent decision model:") == 1
    assert plan_phase.count("Branch as alternative hypothesis") == 1
