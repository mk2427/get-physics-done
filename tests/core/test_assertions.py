"""Tests for gpd.core.assertions — assertion-document loader."""

from __future__ import annotations

import textwrap

import pytest

from gpd.core.assertions import Assertion, load_assertion, load_assertions


# ---------------------------------------------------------------------------
# Test 1 — depends_on field is correctly parsed from frontmatter
# ---------------------------------------------------------------------------


def test_assertion_depends_on_loader(tmp_path):
    """load_assertion parses depends_on, assertion_id, and status correctly."""
    md_content = textwrap.dedent("""\
        ---
        assertion_id: A-007
        status: Stable
        title: "Level-2 virial bound"
        depends_on:
          - A-001
          - A-003
        load_bearing: true
        ---

        # Assertion: Level-2 virial bound

        Body content here.
    """)
    assertion_file = tmp_path / "A-007-level-2-virial-bound.md"
    assertion_file.write_text(md_content, encoding="utf-8")

    assertion = load_assertion(assertion_file)

    assert isinstance(assertion, Assertion)
    assert assertion.assertion_id == "A-007"
    assert assertion.status == "Stable"
    assert assertion.depends_on == ["A-001", "A-003"]
    assert assertion.load_bearing is True


# ---------------------------------------------------------------------------
# Test 2 — load_assertions globs a directory and returns both assertions
# ---------------------------------------------------------------------------


def test_load_assertions_globs_directory(tmp_path):
    """load_assertions returns a dict with all valid assertion files in a dir."""
    file_a = tmp_path / "A-001-foo.md"
    file_a.write_text(
        textwrap.dedent("""\
            ---
            assertion_id: A-001
            status: Draft
            depends_on: []
            ---
            Body A.
        """),
        encoding="utf-8",
    )

    file_b = tmp_path / "A-002-bar.md"
    file_b.write_text(
        textwrap.dedent("""\
            ---
            assertion_id: A-002
            status: Under Review
            depends_on:
              - A-001
            ---
            Body B.
        """),
        encoding="utf-8",
    )

    result = load_assertions(tmp_path)

    assert isinstance(result, dict)
    assert "A-001" in result
    assert "A-002" in result
    assert result["A-001"].status == "Draft"
    assert result["A-002"].depends_on == ["A-001"]


# ---------------------------------------------------------------------------
# Test 3 — file with no frontmatter raises ValueError
# ---------------------------------------------------------------------------


def test_load_assertion_missing_frontmatter_raises(tmp_path):
    """A Markdown file with no --- delimiters raises ValueError."""
    bad_file = tmp_path / "A-999-no-frontmatter.md"
    bad_file.write_text(
        "# No frontmatter here\n\nJust a bare body with no YAML block.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_assertion(bad_file)
