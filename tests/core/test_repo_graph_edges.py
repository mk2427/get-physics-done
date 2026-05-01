"""Guardrails for the dependency-graph edge sets in tests/README.md.

Ensures that every registered agent participates in at least one dependency edge
in the README-scoped dependency graph, and that the edge-set membership stays in
lock-step with the live registry inventory.

This catches the FILE-14 manual-edit drift described in brief 002 / v3 plan
(`sync_repo_graph_contract.py` does NOT update edge sets, so they must be
maintained by hand; missing updates are exactly the failure mode this file
guards against).

Two strict edge-set tests are marked `xfail` because of pre-existing drift
documented in v3 plan §5.4 (N1: gpd-explainer missing from shared-protocols
edge set; analogous gap for gpd-verifier in the agent-infrastructure edge set).
Fixing these is explicitly out of scope for the 25th-agent landing commit; the
`xfail` markers flip to `XPASS` once the cleanup commit lands, which will then
promote the expectations into hard assertions.
"""

from __future__ import annotations

import re

import pytest

from gpd import registry
from scripts.repo_graph_contract import REPO_ROOT, iter_graph_edge_specs, read_graph_text

AGENT_EDGE_SOURCE_RE = re.compile(
    r"^src/gpd/agents/(?:\{([^}]+)\}|(gpd-[a-z-]+))\.md$"
)


def _expand_braced(endpoint: str) -> set[str]:
    """Expand `src/gpd/agents/{a,b,c}.md` -> {a, b, c} of agent names."""
    match = AGENT_EDGE_SOURCE_RE.match(endpoint)
    if match is None:
        return set()
    brace_group, single_group = match.groups()
    if single_group is not None:
        return {single_group}
    return {item.strip() for item in brace_group.split(",") if item.strip()}


def _agent_edge_source_map() -> dict[str, set[str]]:
    """Map each agent -> set of edge-target files it appears as source for."""
    graph_text = read_graph_text()
    mapping: dict[str, set[str]] = {}
    for source, target in iter_graph_edge_specs(graph_text):
        agents = _expand_braced(source)
        for agent in agents:
            mapping.setdefault(agent, set()).add(target)
    return mapping


def _live_including(token: str) -> set[str]:
    agents_dir = REPO_ROOT / "src" / "gpd" / "agents"
    return {
        path.stem
        for path in sorted(agents_dir.glob("gpd-*.md"))
        if token in path.read_text(encoding="utf-8")
    }


def _edge_sources_for(target: str) -> set[str]:
    edge_sources: set[str] = set()
    for source, tgt in iter_graph_edge_specs(read_graph_text()):
        if tgt == target:
            edge_sources |= _expand_braced(source)
    return edge_sources


def test_every_registered_agent_has_at_least_one_graph_edge() -> None:
    """Every agent in the registry must appear as the source of at least one
    dependency-graph edge in `tests/README.md`.

    This is the primary regression guard: adding a new agent without touching
    the edge sets will fail this test.
    """
    agent_edges = _agent_edge_source_map()
    registered = set(registry.list_agents())
    missing = sorted(a for a in registered if a not in agent_edges)
    assert not missing, (
        f"Agents with no edge in tests/README.md dependency graph: {missing}. "
        "When adding a new agent, update the edge sets on the lines that "
        "enumerate `src/gpd/agents/{...}.md -> ...` includes."
    )


def test_adversarial_critic_present_in_expected_edge_sets() -> None:
    """The 25th agent (gpd-adversarial-critic) `@include`s both shared-protocols
    and agent-infrastructure; its name must appear in the matching edge sets."""
    shared = _edge_sources_for("src/gpd/specs/references/shared/shared-protocols.md")
    infra = _edge_sources_for("src/gpd/specs/references/orchestration/agent-infrastructure.md")
    assert "gpd-adversarial-critic" in shared, (
        "gpd-adversarial-critic missing from shared-protocols.md edge set "
        "(tests/README.md line ~621)."
    )
    assert "gpd-adversarial-critic" in infra, (
        "gpd-adversarial-critic missing from agent-infrastructure.md edge set "
        "(tests/README.md line ~627)."
    )


def test_edge_set_agent_count_is_within_registry_bound() -> None:
    """Edge-count invariant: the set of agent names referenced as edge sources
    must be a subset of the live registry inventory (no phantom agents in the
    graph)."""
    registered = set(registry.list_agents())
    edge_agents = set(_agent_edge_source_map().keys())
    extras = sorted(edge_agents - registered)
    assert not extras, (
        f"tests/README.md references agent(s) not in the registry: {extras}. "
        "Remove stale entries from the edge sets."
    )


@pytest.mark.xfail(
    reason="N1 from v3 plan §5.4: gpd-explainer pre-existing drift, out of scope for 002",
    strict=False,
)
def test_shared_protocols_edge_set_matches_live_agent_inventory() -> None:
    """STRICT guard (xfailed): every agent that `@include`s shared-protocols
    must appear in the shared-protocols edge set."""
    target = "src/gpd/specs/references/shared/shared-protocols.md"
    live = _live_including("references/shared/shared-protocols.md")
    missing = sorted(live - _edge_sources_for(target))
    assert not missing, (
        f"Agents that include shared-protocols.md but are missing from the "
        f"README edge set: {missing}"
    )


@pytest.mark.xfail(
    reason="Analogous N1 drift: gpd-verifier pre-existing, out of scope for 002",
    strict=False,
)
def test_agent_infrastructure_edge_set_matches_live_agent_inventory() -> None:
    """STRICT guard (xfailed): every agent that `@include`s agent-infrastructure
    must appear in the agent-infrastructure edge set."""
    target = "src/gpd/specs/references/orchestration/agent-infrastructure.md"
    live = _live_including("references/orchestration/agent-infrastructure.md")
    missing = sorted(live - _edge_sources_for(target))
    assert not missing, (
        f"Agents that include agent-infrastructure.md but are missing from the "
        f"README edge set: {missing}"
    )
