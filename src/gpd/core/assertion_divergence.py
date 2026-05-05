"""Assertion divergence checker + critic router (brief 002 §7.3 + §5.2).

This module provides two related public surfaces:

1. **Divergence check** (brief §7.3) — gates Stable promotion for assertion docs
   by comparing `upstream_ref_hash` in the assertion frontmatter against
   `sha256(normalize_eqn_body(canonical_form))` for the referenced EQN-REF
   E-entry.  A PASS clears the gate; a FAIL blocks Stable promotion and surfaces
   the mismatch to the user.

2. **Critic router** (brief §5.2) — maps an assertion_data dict onto the correct
   critic agent(s) for the adversarial-review loop, covering all five cases
   described in the workflow spec.

Public API (all importable from ``gpd.core.assertion_divergence``):

* ``compute_upstream_ref_hash(canonical_latex)`` → str
* ``DivergenceResult`` dataclass
* ``check_divergence(assertion_doc_path, eqn_ref_catalog_path)`` → DivergenceResult
* ``check_divergence_from_dict(assertion_data, eqn_ref_entries)`` → DivergenceResult
* ``AssertionDepthError`` exception
* ``route_assertion_critic(assertion_data)`` → str | list[tuple[str, str]]
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

from gpd.core.eqn_normalize import normalize_eqn_body

__all__ = [
    "AssertionDepthError",
    "DivergenceResult",
    "check_divergence",
    "check_divergence_from_dict",
    "compute_upstream_ref_hash",
    "route_assertion_critic",
]

# ─── Constants ───────────────────────────────────────────────────────────────

_MAX_SUB_ASSERTION_DEPTH = 3  # brief §5.2: depth > 3 → schema validation error

# Critic agent names used by the router (brief §5.2).
_KNOWLEDGE_CRITIC = "gpd-knowledge-critic"
_ADVERSARIAL_CRITIC = "gpd-adversarial-critic"

# Valid assertion kinds (brief §3.4).
_KIND_RESTATEMENT = "restated-equation"
_KIND_DERIVED = "derived-consequence"

# ─── Exceptions ──────────────────────────────────────────────────────────────


class AssertionDepthError(ValueError):
    """Raised when sub-assertion nesting exceeds the depth-3 cap (brief §5.2).

    Depth > 3 is a schema validation error.  The validator raises this *before*
    entering the adversarial loop; the workflow escalates to the user (brief §5.2
    recursion depth cap) rather than dispatching any critic.
    """


# ─── Hash computation ────────────────────────────────────────────────────────


def compute_upstream_ref_hash(canonical_latex: str) -> str:
    """Return ``sha256(normalize_eqn_body(canonical_latex))`` as a hex digest.

    This is the canonical ``upstream_ref_hash`` value for restated-equation
    assertions per brief 002 §3.4.1.  Callers must pass the *canonical form*
    extracted verbatim from the EQN-REF E-entry (not the assertion body itself).

    Args:
        canonical_latex: Raw LaTeX string from the EQN-REF catalog.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    normalized = normalize_eqn_body(canonical_latex)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ─── Divergence result dataclass ─────────────────────────────────────────────


@dataclass
class DivergenceResult:
    """Result of a divergence check between an assertion doc and EQN-REF catalog.

    ``passed=True``  → Stable promotion is unblocked.
    ``passed=False`` → Stable promotion is BLOCKED; inspect ``mismatch_reason``.

    The three mismatch reasons are:
    * ``"hash_mismatch"``     — stored hash != computed hash (source changed).
    * ``"missing_eqn_entry"`` — referenced E-entry not found in catalog.
    * ``"missing_hash_field"``— ``upstream_ref_hash`` absent from assertion YAML.

    For derived-consequence assertions (``upstream_ref_hash: null``), the check
    always passes unconditionally (brief §7.3: no check needed when null).
    """

    passed: bool
    stored_hash: str | None = None
    computed_hash: str | None = None
    mismatch_reason: str | None = None


# ─── Core check logic (dict-based, no file I/O) ──────────────────────────────


def check_divergence_from_dict(
    assertion_data: dict,
    eqn_ref_entries: dict[str, str],
) -> DivergenceResult:
    """Check divergence given in-memory assertion data and EQN-REF entries.

    This is the testable, file-I/O-free variant used by the test suite and by
    ``check_divergence`` after it reads the two files from disk.

    Args:
        assertion_data:   Parsed assertion YAML frontmatter as a dict.
                          Expected keys: ``upstream_ref_hash`` (str or None),
                          ``eqn_ref_entries`` (list of str, optional).
        eqn_ref_entries:  Mapping of E-entry ID → canonical LaTeX string.
                          Example: ``{"E.1": r"S = \\int \\mathcal{L}\\, d^4x"}``.

    Returns:
        ``DivergenceResult(passed=True)``   when hash matches or hash is null.
        ``DivergenceResult(passed=False)``  when hash mismatches or E-entry absent.
    """
    stored_hash: str | None = assertion_data.get("upstream_ref_hash")

    # Derived-consequence path: null hash → unconditional PASS (brief §7.3).
    if stored_hash is None:
        return DivergenceResult(passed=True, stored_hash=None, computed_hash=None)

    # Restated-equation path: locate the referenced E-entry.
    entry_ids: list[str] = assertion_data.get("eqn_ref_entries") or []
    if not entry_ids:
        # No E-entry cited but hash present — treat as a structural mismatch.
        return DivergenceResult(
            passed=False,
            stored_hash=stored_hash,
            computed_hash=None,
            mismatch_reason="missing_eqn_entry",
        )

    # Use the *first* cited E-entry as the primary source for the hash check.
    # Per brief §7.3: each assertion that carries an upstream_ref_hash must cite
    # at least one E-entry; the hash is computed over the first entry's canonical
    # form.  If an assertion cites multiple E-entries, downstream review must
    # confirm all of them — but the hash gate uses entry_ids[0].
    primary_entry_id = entry_ids[0]
    canonical_form = eqn_ref_entries.get(primary_entry_id)
    if canonical_form is None:
        return DivergenceResult(
            passed=False,
            stored_hash=stored_hash,
            computed_hash=None,
            mismatch_reason="missing_eqn_entry",
        )

    computed_hash = compute_upstream_ref_hash(canonical_form)
    if stored_hash == computed_hash:
        return DivergenceResult(
            passed=True,
            stored_hash=stored_hash,
            computed_hash=computed_hash,
        )

    return DivergenceResult(
        passed=False,
        stored_hash=stored_hash,
        computed_hash=computed_hash,
        mismatch_reason="hash_mismatch",
    )


# ─── File-based check (used by the workflow) ─────────────────────────────────


def _parse_frontmatter_from_text(text: str) -> dict:
    """Extract and parse the YAML frontmatter block from a markdown file."""
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].strip() == "---":
        return {}
    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    raw = "".join(fm_lines)
    parsed = yaml.safe_load(raw)
    return parsed if isinstance(parsed, dict) else {}


def _parse_eqn_ref_catalog(text: str) -> dict[str, str]:
    """Parse an EQN-REF catalog markdown file into ``{entry_id: canonical_latex}``.

    The catalog format (templates/eqn-reference-schema.md) stores entries as
    YAML code blocks under ``## E.N — Title`` headings.  This parser extracts
    entries using a simple regex over the text.

    Fallback: if the catalog uses a different layout, the parser returns an empty
    dict and the divergence check will surface ``missing_eqn_entry``.
    """
    entries: dict[str, str] = {}
    # Match blocks like:
    #   entry_id: E.1
    #   canonical_form: |
    #     S = \int ...
    # or inline:
    #   canonical_form: "S = \int ..."
    entry_block_re = re.compile(
        r"entry_id:\s*([A-Za-z0-9._-]+).*?canonical_form:\s*[|>-]?\s*\n?(.*?)(?=\nentry_id:|\Z)",
        re.DOTALL,
    )
    for match in entry_block_re.finditer(text):
        entry_id = match.group(1).strip()
        raw_form = match.group(2).strip()
        # Strip surrounding YAML quotes if present.
        if (raw_form.startswith('"') and raw_form.endswith('"')) or (
            raw_form.startswith("'") and raw_form.endswith("'")
        ):
            raw_form = raw_form[1:-1]
        entries[entry_id] = raw_form
    return entries


def check_divergence(
    assertion_doc_path: Path,
    eqn_ref_catalog_path: Path,
) -> DivergenceResult:
    """File-based divergence check; reads both files and delegates to dict variant.

    Called by the ``/gpd:digest-assertion`` workflow before writing
    ``status: Stable`` to the assertion doc.

    Args:
        assertion_doc_path:    Path to the assertion markdown doc.
        eqn_ref_catalog_path:  Path to the EQN-REF catalog markdown file.

    Returns:
        ``DivergenceResult`` (see ``check_divergence_from_dict``).
    """
    assertion_text = assertion_doc_path.read_text(encoding="utf-8")
    assertion_data = _parse_frontmatter_from_text(assertion_text)

    catalog_text = eqn_ref_catalog_path.read_text(encoding="utf-8")
    eqn_ref_entries = _parse_eqn_ref_catalog(catalog_text)

    return check_divergence_from_dict(assertion_data, eqn_ref_entries)


# ─── Critic router ───────────────────────────────────────────────────────────


def _assertion_depth(assertion_data: dict, current_depth: int = 0) -> int:
    """Compute the maximum nesting depth of sub-assertions recursively.

    Top-level assertion = depth 0.  Sub-assertions under it = depth 1.  Sub-
    assertions of sub-assertions = depth 2.  Etc.

    Args:
        assertion_data: Assertion dict (may have a ``sub_assertions`` list).
        current_depth:  Recursion depth counter (callers pass 0).

    Returns:
        Maximum depth found in the tree.
    """
    sub_assertions: list[dict] = assertion_data.get("sub_assertions") or []
    if not sub_assertions:
        return current_depth
    child_depths = [_assertion_depth(sub, current_depth + 1) for sub in sub_assertions]
    return max(child_depths)


def _validate_depth(assertion_data: dict) -> None:
    """Raise ``AssertionDepthError`` if sub-assertion nesting exceeds depth 3.

    Called by ``route_assertion_critic`` BEFORE any critic is dispatched.  The
    workflow spec mandates that depth > 3 escalates to the user rather than
    entering the adversarial loop.
    """
    max_depth = _assertion_depth(assertion_data)
    if max_depth > _MAX_SUB_ASSERTION_DEPTH:
        raise AssertionDepthError(
            f"Sub-assertion nesting depth {max_depth} exceeds the cap of "
            f"{_MAX_SUB_ASSERTION_DEPTH} (brief §5.2). Escalate to user before "
            "entering the adversarial loop."
        )


def _critic_for_kind(kind: str) -> str:
    """Map an assertion kind string to the canonical critic name."""
    if kind == _KIND_RESTATEMENT:
        return _KNOWLEDGE_CRITIC
    # derived-consequence + anything unknown defaults to adversarial critic.
    return _ADVERSARIAL_CRITIC


def route_assertion_critic(
    assertion_data: dict,
) -> Union[str, list[tuple[str, str]]]:
    """Select the correct critic(s) for an assertion per brief §5.2 (5 cases).

    This function is the single authoritative implementation of the critic router.
    It is called by the ``/gpd:digest-assertion`` workflow and tested directly by
    ``tests/core/test_digest_assertion.py``.

    The five cases (brief §5.2):

    1. ``kind=restated-equation``, no sub-assertions → ``gpd-knowledge-critic``.
    2. ``kind=derived-consequence``, no sub-assertions → ``gpd-adversarial-critic``.
    3. Mixed-kind: empty top-level ``derivation_sketch`` + sub-assertions present
       → top-level to ``gpd-knowledge-critic``; each sub routed by its own kind.
       Emits list of ``(sub_id, critic)`` pairs with ``("top_level", critic)`` first.
    4. Compound derived-consequence: non-empty top-level ``derivation_sketch`` +
       sub-assertions present → top-level to ``gpd-adversarial-critic``; each sub
       routed by its own kind. Same list format.
    5. Knowledge doc input (``source_kind="kdoc"`` or ``kind`` absent) →
       ``gpd-knowledge-critic`` (passthrough).

    Validates recursion depth first; raises ``AssertionDepthError`` if > 3.

    Args:
        assertion_data: Dict representing the assertion.  Expected keys:
            ``kind`` (str), ``sub_assertions`` (list, optional),
            ``derivation_sketch`` (str or None, optional),
            ``assertion_id`` (str, optional),
            ``source_kind`` (str, optional — "kdoc" for case 5).

    Returns:
        A single critic name (str) for cases 1, 2, 5, or a list of
        ``(identifier, critic)`` tuples for cases 3 and 4.

    Raises:
        AssertionDepthError: If sub-assertion nesting depth > 3.
    """
    _validate_depth(assertion_data)

    kind: str = assertion_data.get("kind", "")
    source_kind: str = assertion_data.get("source_kind", "")
    sub_assertions: list[dict] = assertion_data.get("sub_assertions") or []
    derivation_sketch: str | None = assertion_data.get("derivation_sketch")
    assertion_id: str = assertion_data.get("assertion_id", "top_level")

    # Case 5: knowledge doc passthrough.
    if source_kind == "kdoc" or (not kind and not sub_assertions):
        return _KNOWLEDGE_CRITIC

    has_subs = bool(sub_assertions)

    # Cases 1 and 2: no sub-assertions.
    if not has_subs:
        return _critic_for_kind(kind)

    # Cases 3 and 4: sub-assertions present.
    # Determine top-level critic by derivation_sketch content.
    sketch_non_empty = bool(derivation_sketch and derivation_sketch.strip())
    if sketch_non_empty:
        # Case 4: compound derived-consequence (non-empty sketch + sub-assertions).
        top_critic = _ADVERSARIAL_CRITIC
    else:
        # Case 3: mixed-kind (empty top-level sketch + sub-assertions).
        top_critic = _critic_for_kind(kind) if kind else _KNOWLEDGE_CRITIC

    routing: list[tuple[str, str]] = [("top_level", top_critic)]
    for sub in sub_assertions:
        sub_id: str = sub.get("assertion_id", "unknown")
        sub_kind: str = sub.get("kind", "")
        routing.append((sub_id, _critic_for_kind(sub_kind)))

    return routing
