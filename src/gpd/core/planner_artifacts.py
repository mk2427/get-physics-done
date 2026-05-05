"""Planner-artifact prereq helpers for knowledge and assertion gates.

Lightweight, schema-only helpers consumed by the knowledge/assertion gates wired
into ``execute-phase`` in a later commit.  Each helper returns a list of missing
document IDs so that callers can either warn or block depending on the effective
:class:`~gpd.core.config.KnowledgeGateMode` / :class:`~gpd.core.config.AssertionGateMode`.

A knowledge or assertion ID is considered *present* when a markdown file under
``GPD/knowledge/`` (resp. ``GPD/assertions/``) carries that ID in its YAML
frontmatter (``kdoc_id`` / ``assertion_id``) AND its ``status`` is ``stable``.
Any other status (``draft``, ``under_review``, ``superseded``) is treated as
missing so downstream callers can surface a clear error message.

The helpers deliberately perform no I/O side-effects beyond directory reads and
no behavioural coupling to the caller: they simply enumerate + return.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

try:  # pragma: no cover - defensive; pyyaml is a hard dep of gpd
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from gpd.core.constants import ASSERTION_DIR_NAME, KNOWLEDGE_DIR_NAME, PLANNING_DIR_NAME

__all__ = [
    "check_plan_knowledge_prereqs",
    "check_plan_assertion_prereqs",
]


_STABLE_STATUS_VALUES = frozenset({"stable", "Stable", "STABLE"})


def _parse_frontmatter(text: str) -> dict[str, object]:
    """Return parsed YAML frontmatter as a dict (empty dict on any failure)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    raw = text[3:end]
    if yaml is None:
        return {}
    try:
        parsed = yaml.safe_load(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _stable_doc_ids(directory: Path, id_field: str) -> set[str]:
    """Return the set of ``id_field`` values for Stable docs under *directory*."""
    if not directory.is_dir():
        return set()
    found: set[str] = set()
    for md_path in directory.glob("*.md"):
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        frontmatter = _parse_frontmatter(text)
        doc_id = frontmatter.get(id_field)
        status = frontmatter.get("status")
        if isinstance(doc_id, str) and isinstance(status, str) and status in _STABLE_STATUS_VALUES:
            found.add(doc_id)
    return found


def _missing_prereqs(
    required: Iterable[str],
    project_root: Path,
    subdir_name: str,
    id_field: str,
) -> list[str]:
    """Return the subset of *required* IDs that lack a matching Stable doc."""
    needed = [rid for rid in required if isinstance(rid, str) and rid]
    if not needed:
        return []
    directory = project_root / PLANNING_DIR_NAME / subdir_name
    present = _stable_doc_ids(directory, id_field)
    return [rid for rid in needed if rid not in present]


def check_plan_knowledge_prereqs(plan: object, project_root: Path) -> list[str]:
    """Return the knowledge-doc IDs *plan* requires that are NOT Stable on disk.

    The *plan* argument is a duck-typed object (typically a parsed plan
    validation or frontmatter dict) exposing a ``requires_knowledge`` attribute
    or key.  Missing attributes / empty lists produce an empty result.
    """
    required = _plan_field(plan, "requires_knowledge")
    return _missing_prereqs(required, project_root, KNOWLEDGE_DIR_NAME, "kdoc_id")


def check_plan_assertion_prereqs(plan: object, project_root: Path) -> list[str]:
    """Return the assertion-doc IDs *plan* requires that are NOT Stable on disk."""
    required = _plan_field(plan, "requires_assertion")
    return _missing_prereqs(required, project_root, ASSERTION_DIR_NAME, "assertion_id")


def _plan_field(plan: object, name: str) -> list[str]:
    """Read a list-valued field off a pydantic model or dict-ish plan object."""
    if isinstance(plan, dict):
        value = plan.get(name, [])
    else:
        value = getattr(plan, name, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
