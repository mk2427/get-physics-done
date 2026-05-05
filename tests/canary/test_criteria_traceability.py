"""Unit tests for ``tests/canary/criteria/traceability.py`` (plan-006 §C10).

Covers PASS, FAIL on cycle, FAIL on empty graph, and edge cases per
plan §Acceptance criteria 4 (>=3 tests per parser).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.canary.criteria import CriterionStatus
from tests.canary.criteria.traceability import check


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _kdoc(kid: str, *, connections: str = "") -> str:
    return (
        f"---\nkdoc_id: {kid}\nstatus: Stable\n---\n\n# Knowledge: {kid}\n\n"
        f"## Connections\n\n{connections}\n"
    )


def _assertion(
    aid: str,
    *,
    knowledge_doc_ids: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> str:
    kdocs = "\n".join(f"  - {k}" for k in (knowledge_doc_ids or []))
    deps = "\n".join(f"  - {d}" for d in (depends_on or []))
    knowledge_block = (
        f"knowledge_doc_ids:\n{kdocs}\n"
        if (knowledge_doc_ids or [])
        else "knowledge_doc_ids: []\n"
    )
    depends_block = (
        f"depends_on:\n{deps}\n" if (depends_on or []) else "depends_on: []\n"
    )
    return (
        f"---\nassertion_id: {aid}\nkind: restated-equation\nstatus: Stable\n"
        f"{knowledge_block}{depends_block}---\n\n# Assertion: {aid}\n"
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> tuple[Path, Path]:
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()
    return kdir, adir


def test_pass_on_valid_dag(sandbox: tuple[Path, Path]) -> None:
    """A minimal acyclic sandbox yields PASS with non-zero counts."""
    kdir, adir = sandbox
    _write(kdir / "K-001-a.md", _kdoc("K-001"))
    _write(kdir / "K-002-b.md", _kdoc("K-002", connections="- Related to K-001"))
    _write(
        adir / "A-001-x.md",
        _assertion("A-001", knowledge_doc_ids=["K-001"]),
    )
    _write(
        adir / "A-002-y.md",
        _assertion("A-002", knowledge_doc_ids=["K-002"], depends_on=["A-001"]),
    )

    result = check(produced_files=None, knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.PASS
    assert result.payload["n_nodes"] >= 4
    assert result.payload["n_edges"] >= 3


def test_fail_on_empty_corpus(sandbox: tuple[Path, Path]) -> None:
    """No produced files -> FAIL with empty-graph diagnostic."""
    kdir, adir = sandbox
    result = check(produced_files=None, knowledge_dir=kdir, assertion_dir=adir)
    assert result.status == CriterionStatus.FAIL
    assert "empty graph" in result.summary.lower()
    assert result.payload["n_nodes"] == 0


def test_fail_on_cycle(sandbox: tuple[Path, Path]) -> None:
    """A back-edge between kdocs surfaces as FAIL with cycle witnesses."""
    kdir, adir = sandbox
    _write(kdir / "K-001-a.md", _kdoc("K-001", connections="- Related to K-002"))
    _write(kdir / "K-002-b.md", _kdoc("K-002", connections="- Related to K-001"))
    _write(
        adir / "A-001-x.md",
        _assertion("A-001", knowledge_doc_ids=["K-001"]),
    )

    result = check(produced_files=None, knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.FAIL
    assert "cycle" in result.summary.lower()
    cycle = result.payload.get("cycle", [])
    assert set(cycle) >= {"K-001", "K-002"}


def test_fail_on_orphan_nodes_no_edges(sandbox: tuple[Path, Path]) -> None:
    """Nodes without provenance edges fail with no-edges diagnostic."""
    kdir, adir = sandbox
    # Two unconnected kdocs, no Connections block, no assertions
    _write(kdir / "K-001-a.md", _kdoc("K-001"))
    _write(kdir / "K-002-b.md", _kdoc("K-002"))

    result = check(produced_files=None, knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.FAIL
    assert result.payload["n_nodes"] == 2
    assert result.payload["n_edges"] == 0
    assert "0 edges" in result.summary


def test_produced_files_restriction(sandbox: tuple[Path, Path]) -> None:
    """produced_files filter scopes the parser to the run-attribution set."""
    kdir, adir = sandbox
    keep_k = _write(kdir / "K-001-keep.md", _kdoc("K-001"))
    _write(kdir / "K-099-skip.md", _kdoc("K-099", connections="- Related to K-001"))
    keep_a = _write(
        adir / "A-001-keep.md",
        _assertion("A-001", knowledge_doc_ids=["K-001"]),
    )
    # Only the keep set is produced; K-099 file exists but was not produced.
    result = check(
        produced_files=[keep_k, keep_a],
        knowledge_dir=kdir,
        assertion_dir=adir,
    )
    assert result.status == CriterionStatus.PASS
    nodes = set(result.payload.get("nodes", []))
    # nodes payload is only present on the no-edges branch; here PASS path
    # carries n_nodes/n_edges only — so verify counts directly.
    assert result.payload["n_nodes"] == 2
    assert result.payload["n_edges"] >= 1
