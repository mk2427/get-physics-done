"""§7.6 Traceability parser (plan-006 §C10).

Verifies the canary-produced kdoc + assertion tree forms a non-empty
DAG: every assertion's provenance traces back to a kdoc, and no
back-edges produce reasoning cycles.

The graph build is delegated to :mod:`tests.canary.canary_graph`
(plan-006 §C10 / iter-1-S4); this module is the §7-criterion adapter
that wraps it in a :class:`CriterionResult`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from tests.canary.canary_graph import build_canary_graph, find_cycle
from tests.canary.criteria import CriterionResult, CriterionStatus

_NAME = "Traceability"


def check(
    produced_files: Iterable[Path] | None,
    knowledge_dir: Path,
    assertion_dir: Path,
    truth_table: dict | None = None,  # unused; kept for API symmetry
) -> CriterionResult:
    """Run §7.6 traceability check.

    PASS iff the canary-produced graph is non-empty (>=1 node, >=1
    edge) AND acyclic (DAG). Otherwise FAIL with diagnostics.

    Parameters
    ----------
    produced_files:
        Cost-log-derived list of paths (per the C9 run-attribution
        rule). ``None`` means "walk the full dir" — used only by tests
        that pre-populate a sandbox.
    knowledge_dir, assertion_dir:
        Sandbox directories for this canary run.
    truth_table:
        Unused. Accepted for parity with the project-agnostic ``check``
        signature (plan-006 §Implementation order).
    """
    graph = build_canary_graph(
        knowledge_dir=Path(knowledge_dir),
        assertion_dir=Path(assertion_dir),
        produced_files=list(produced_files) if produced_files is not None else None,
    )

    n_nodes = len(graph)
    n_edges = sum(len(v) for v in graph.values())

    if n_nodes == 0:
        return CriterionResult(
            name=_NAME,
            status=CriterionStatus.FAIL,
            summary="empty graph: no kdocs or assertions found in produced corpus",
            details=[
                f"knowledge_dir={knowledge_dir}",
                f"assertion_dir={assertion_dir}",
                "produced_files filter would have excluded everything",
            ],
            payload={"n_nodes": 0, "n_edges": 0},
        )

    if n_edges == 0:
        return CriterionResult(
            name=_NAME,
            status=CriterionStatus.FAIL,
            summary=f"graph has {n_nodes} node(s) but 0 edges — no provenance recorded",
            details=[
                "Every assertion must cite at least one kdoc via "
                "knowledge_doc_ids; every multi-kdoc corpus must record "
                "cross-references in Connections sections.",
                f"orphaned nodes: {sorted(graph.keys())}",
            ],
            payload={"n_nodes": n_nodes, "n_edges": 0, "nodes": sorted(graph.keys())},
        )

    cycle = find_cycle(graph)
    if cycle is not None:
        return CriterionResult(
            name=_NAME,
            status=CriterionStatus.FAIL,
            summary=f"cycle detected in provenance graph: {' -> '.join(cycle)}",
            details=[
                f"cycle witnesses: {cycle}",
                "Provenance must be acyclic (a DAG); a cycle indicates "
                "circular reasoning between kdocs/assertions.",
            ],
            payload={"n_nodes": n_nodes, "n_edges": n_edges, "cycle": cycle},
        )

    return CriterionResult(
        name=_NAME,
        status=CriterionStatus.PASS,
        summary=f"DAG with {n_nodes} node(s), {n_edges} edge(s)",
        details=[],
        payload={"n_nodes": n_nodes, "n_edges": n_edges},
    )


__all__ = ["check"]
