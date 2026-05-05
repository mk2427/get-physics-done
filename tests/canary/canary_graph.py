"""Canary traceability graph builder (plan-006 §C10).

Walks a sandbox kdoc + assertion tree and emits a directed graph of
provenance edges for §7.6 traceability checks. Stdlib-only — networkx
is NOT a project dependency.

Edge semantics (per plan-006 §C10):

- ``kdoc -> kdoc`` for each ``[K-NNN:K.X]`` citation in the body or
  prose ``Related to K-NNN`` line in the kdoc's ``## Connections``.
- ``assertion -> kdoc`` for each ``K-NNN`` listed under
  ``knowledge_doc_ids:`` frontmatter, plus ``upstream_status_mirror.kdoc_id``.
- ``assertion -> assertion`` for each ``A-NNN`` listed under
  ``depends_on:`` frontmatter.

Cycle detection uses :class:`graphlib.TopologicalSorter` (stdlib).

The existing ``gpd.core.blast_radius`` is NOT a directory walker — it
operates on pre-built ``state`` dicts. This module is the file-I/O
surface for §7.6 (resolves iter-1-S4).
"""
from __future__ import annotations

import re
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Iterable

import yaml

# K-NNN reference (in body or frontmatter scalars)
_K_REF_RE = re.compile(r"\bK-(\d{3,})\b")
# A-NNN reference (in body or frontmatter scalars)
_A_REF_RE = re.compile(r"\bA-(\d{3,})\b")
# Canonical equation citation tokens [K-NNN:K.X]
_K_EQ_CITE_RE = re.compile(r"\[K-(\d{3,}):K\.\d+\]")
# Frontmatter delimiter
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_frontmatter_and_body(path: Path) -> tuple[dict, str]:
    """Return ``(frontmatter_dict, body_text)``; empty dict if no FM."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    return fm, text[m.end():]


def _normalize_kdoc_id(raw: str | int | None) -> str | None:
    """Coerce a kdoc id to canonical ``K-NNN`` form."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = _K_REF_RE.search(s)
    if m:
        return f"K-{int(m.group(1)):03d}"
    return None


def _normalize_assertion_id(raw: str | int | None) -> str | None:
    """Coerce an assertion id to canonical ``A-NNN`` form."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = _A_REF_RE.search(s)
    if m:
        return f"A-{int(m.group(1)):03d}"
    return None


def _id_from_filename(path: Path, prefix: str) -> str | None:
    """Extract canonical ``K-NNN`` / ``A-NNN`` from a filename."""
    stem = path.stem
    m = re.match(rf"^{prefix}-(\d{{3,}})", stem)
    if m:
        return f"{prefix}-{int(m.group(1)):03d}"
    return None


def build_canary_graph(
    knowledge_dir: Path,
    assertion_dir: Path,
    produced_files: Iterable[Path] | None = None,
) -> dict[str, list[str]]:
    """Build a provenance graph as ``dict[node_id, list[successor_id]]``.

    Parameters
    ----------
    knowledge_dir:
        Directory holding ``K-NNN-*.md`` kdocs.
    assertion_dir:
        Directory holding ``A-NNN-*.md`` assertion docs.
    produced_files:
        Optional whitelist of Path objects to restrict the walk to (per
        the C9 run-attribution rule). If ``None``, walk the full dirs.

    Returns
    -------
    dict[str, list[str]]
        Adjacency map. Every referenced node appears as a key (sources
        with no outgoing edges have an empty list). Edge direction is
        ``source -> target`` per the C10 contract.
    """
    knowledge_dir = Path(knowledge_dir)
    assertion_dir = Path(assertion_dir)
    whitelist: set[Path] | None = None
    if produced_files is not None:
        whitelist = {Path(p).resolve() for p in produced_files}

    def _included(p: Path) -> bool:
        if whitelist is None:
            return True
        return p.resolve() in whitelist

    graph: dict[str, set[str]] = {}

    def _add_node(node: str) -> None:
        graph.setdefault(node, set())

    def _add_edge(src: str, tgt: str) -> None:
        if src == tgt:
            return
        graph.setdefault(src, set()).add(tgt)
        graph.setdefault(tgt, set())

    # Walk kdocs
    if knowledge_dir.is_dir():
        for path in sorted(knowledge_dir.glob("K-*.md")):
            if not _included(path):
                continue
            fm, body = _read_frontmatter_and_body(path)
            kid = _normalize_kdoc_id(fm.get("kdoc_id")) or _id_from_filename(path, "K")
            if kid is None:
                continue
            _add_node(kid)
            # kdoc -> kdoc edges from body citations and Connections lines
            for m in _K_EQ_CITE_RE.finditer(body):
                target = f"K-{int(m.group(1)):03d}"
                _add_edge(kid, target)
            # Loose prose mentions inside the Connections section
            conn_match = re.search(
                r"^##\s*Connections\s*\n(.*?)(?=^##\s|\Z)",
                body,
                re.DOTALL | re.MULTILINE,
            )
            if conn_match:
                for m in _K_REF_RE.finditer(conn_match.group(1)):
                    target = f"K-{int(m.group(1)):03d}"
                    _add_edge(kid, target)

    # Walk assertions
    if assertion_dir.is_dir():
        for path in sorted(assertion_dir.glob("A-*.md")):
            if not _included(path):
                continue
            fm, _body = _read_frontmatter_and_body(path)
            aid = _normalize_assertion_id(fm.get("assertion_id")) or _id_from_filename(
                path, "A"
            )
            if aid is None:
                continue
            _add_node(aid)
            # assertion -> kdoc via knowledge_doc_ids
            for raw in fm.get("knowledge_doc_ids") or []:
                target = _normalize_kdoc_id(raw)
                if target:
                    _add_edge(aid, target)
            mirror = fm.get("upstream_status_mirror") or {}
            if isinstance(mirror, dict):
                target = _normalize_kdoc_id(mirror.get("kdoc_id"))
                if target:
                    _add_edge(aid, target)
            # assertion -> assertion via depends_on
            for raw in fm.get("depends_on") or []:
                target = _normalize_assertion_id(raw)
                if target:
                    _add_edge(aid, target)

    return {node: sorted(targets) for node, targets in graph.items()}


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return a list of node ids forming a cycle, or None if acyclic.

    Uses :class:`graphlib.TopologicalSorter` for the acyclicity test;
    on cycle, walks back through the sorter's reported edge to surface
    a witness (best-effort — full cycle reconstruction is not required
    by the §7.6 contract, only that ONE witness is named).
    """
    # graphlib's TopologicalSorter expects predecessors; invert.
    predecessors: dict[str, set[str]] = {n: set() for n in graph}
    for src, tgts in graph.items():
        for tgt in tgts:
            predecessors.setdefault(tgt, set()).add(src)
            predecessors.setdefault(src, predecessors.get(src, set()))
    ts = TopologicalSorter(predecessors)
    try:
        ts.prepare()
    except CycleError as exc:
        # exc.args[1] is a list of nodes forming the cycle
        cycle = exc.args[1] if len(exc.args) > 1 else []
        return list(cycle)
    return None


def is_dag(graph: dict[str, list[str]]) -> bool:
    """True iff the graph has no cycles."""
    return find_cycle(graph) is None


__all__ = ["build_canary_graph", "find_cycle", "is_dag"]
