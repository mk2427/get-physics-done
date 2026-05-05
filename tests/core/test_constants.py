"""Tests for gpd.core.constants (ASSERTION_DIR_NAME + ProjectLayout.assertion_dir)."""

from __future__ import annotations

from pathlib import Path

from gpd.core.constants import (
    ASSERTION_DIR_NAME,
    KNOWLEDGE_DIR_NAME,
    PLANNING_DIR_NAME,
    ProjectLayout,
)


class TestAssertionDirName:
    def test_value(self) -> None:
        assert ASSERTION_DIR_NAME == "assertions"

    def test_is_distinct_from_knowledge_dir(self) -> None:
        assert ASSERTION_DIR_NAME != KNOWLEDGE_DIR_NAME


class TestProjectLayoutAssertionDir:
    def test_assertion_dir_is_sibling_of_knowledge_dir(self, tmp_path: Path) -> None:
        layout = ProjectLayout(tmp_path)
        assert layout.assertion_dir == tmp_path / PLANNING_DIR_NAME / "assertions"
        assert layout.knowledge_dir.parent == layout.assertion_dir.parent

    def test_assertion_dir_type(self, tmp_path: Path) -> None:
        layout = ProjectLayout(tmp_path)
        assert isinstance(layout.assertion_dir, Path)
