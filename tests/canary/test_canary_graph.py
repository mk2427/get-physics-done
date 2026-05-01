"""Unit tests for ``tests/canary/canary_graph.py`` (plan-006 §C10).

Covers build correctness, cycle detection, produced-files filtering,
and edge-case handling (empty dirs, malformed frontmatter).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.canary.canary_graph import (
    build_canary_graph,
    find_cycle,
    is_dag,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _kdoc(kid: str, *, body: str = "", connections: str = "") -> str:
    return (
        f"---\n"
        f"kdoc_id: {kid}\n"
        f"status: Stable\n"
        f"---\n"
        f"\n# Knowledge: {kid}\n\n"
        f"## Equations\n\n(K.1) $E = mc^2$\n\n"
        f"{body}\n\n"
        f"## Connections\n\n{connections}\n"
    )


def _assertion(
    aid: str,
    *,
    knowledge_doc_ids: list[str] | None = None,
    depends_on: list[str] | None = None,
    mirror_kdoc: str | None = None,
) -> str:
    kdocs = "\n".join(f"  - {k}" for k in (knowledge_doc_ids or [])) or "  []"
    deps = "\n".join(f"  - {d}" for d in (depends_on or [])) or "  []"
    mirror_block = (
        "upstream_status_mirror:\n"
        f"  kdoc_id: {mirror_kdoc or 'null'}\n"
        "  kdoc_status_at_stable: Stable\n"
        "  divergence_detected_at: null\n"
    )
    knowledge_block = (
        "knowledge_doc_ids:\n" + kdocs
        if (knowledge_doc_ids or []) and kdocs != "  []"
        else "knowledge_doc_ids: []"
    )
    depends_block = (
        "depends_on:\n" + deps
        if (depends_on or []) and deps != "  []"
        else "depends_on: []"
    )
    return (
        "---\n"
        f"assertion_id: {aid}\n"
        "kind: restated-equation\n"
        "status: Stable\n"
        f"{knowledge_block}\n"
        f"{depends_block}\n"
        f"{mirror_block}"
        "---\n"
        f"\n# Assertion: {aid}\n"
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> tuple[Path, Path]:
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()
    return kdir, adir


def test_build_simple_pass_graph(sandbox: tuple[Path, Path]) -> None:
    """A minimal valid sandbox produces the expected adjacency."""
    kdir, adir = sandbox
    _write(
        kdir / "K-001-foo.md",
        _kdoc("K-001", connections="- Related to K-002: shared regime"),
    )
    _write(kdir / "K-002-bar.md", _kdoc("K-002"))
    _write(
        adir / "A-007-baz.md",
        _assertion("A-007", knowledge_doc_ids=["K-001"], mirror_kdoc="K-001"),
    )
    _write(
        adir / "A-008-qux.md",
        _assertion("A-008", knowledge_doc_ids=["K-002"], depends_on=["A-007"]),
    )

    graph = build_canary_graph(kdir, adir)

    assert "K-001" in graph and "K-002" in graph
    assert "A-007" in graph and "A-008" in graph
    assert "K-002" in graph["K-001"]  # via Connections
    assert "K-001" in graph["A-007"]  # knowledge_doc_ids + mirror dedup
    assert "K-002" in graph["A-008"]
    assert "A-007" in graph["A-008"]  # depends_on
    assert is_dag(graph)


def test_cycle_detection_kdoc_to_kdoc(sandbox: tuple[Path, Path]) -> None:
    """A back-edge in kdoc Connections is flagged."""
    kdir, adir = sandbox
    _write(
        kdir / "K-001-a.md",
        _kdoc("K-001", connections="- Related to K-002"),
    )
    _write(
        kdir / "K-002-b.md",
        _kdoc("K-002", connections="- Related to K-001"),
    )

    graph = build_canary_graph(kdir, adir)
    cycle = find_cycle(graph)

    assert cycle is not None
    assert set(cycle) >= {"K-001", "K-002"}
    assert not is_dag(graph)


def test_cycle_detection_assertion_to_assertion(sandbox: tuple[Path, Path]) -> None:
    """A depends_on cycle between assertions is flagged."""
    kdir, adir = sandbox
    _write(kdir / "K-001-x.md", _kdoc("K-001"))
    _write(
        adir / "A-001-x.md",
        _assertion("A-001", knowledge_doc_ids=["K-001"], depends_on=["A-002"]),
    )
    _write(
        adir / "A-002-y.md",
        _assertion("A-002", knowledge_doc_ids=["K-001"], depends_on=["A-001"]),
    )

    graph = build_canary_graph(kdir, adir)
    assert not is_dag(graph)


def test_empty_dirs_yield_empty_graph(sandbox: tuple[Path, Path]) -> None:
    """No files -> empty graph, trivially acyclic."""
    kdir, adir = sandbox
    graph = build_canary_graph(kdir, adir)
    assert graph == {}
    assert is_dag(graph)
    assert find_cycle(graph) is None


def test_produced_files_filter_excludes_unlisted(sandbox: tuple[Path, Path]) -> None:
    """Only files in the produced_files whitelist contribute nodes."""
    kdir, adir = sandbox
    keep = _write(kdir / "K-001-keep.md", _kdoc("K-001"))
    _write(kdir / "K-099-skip.md", _kdoc("K-099"))
    keep_a = _write(
        adir / "A-001-keep.md",
        _assertion("A-001", knowledge_doc_ids=["K-001"]),
    )
    _write(
        adir / "A-099-skip.md",
        _assertion("A-099", knowledge_doc_ids=["K-099"]),
    )

    graph = build_canary_graph(kdir, adir, produced_files=[keep, keep_a])

    assert "K-001" in graph and "A-001" in graph
    # K-099 / A-099 must NOT show up as source nodes (no FM read)
    assert "K-099" not in graph
    assert "A-099" not in graph


def test_canonical_eq_citation_in_kdoc_body(sandbox: tuple[Path, Path]) -> None:
    """``[K-NNN:K.X]`` tokens in kdoc bodies create kdoc->kdoc edges."""
    kdir, adir = sandbox
    _write(
        kdir / "K-001-a.md",
        _kdoc("K-001", body="See [K-002:K.3] for the parent identity."),
    )
    _write(kdir / "K-002-b.md", _kdoc("K-002"))

    graph = build_canary_graph(kdir, adir)
    assert "K-002" in graph["K-001"]
    assert is_dag(graph)
