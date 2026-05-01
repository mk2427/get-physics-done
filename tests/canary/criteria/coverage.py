"""§7.1 Coverage parser for the BFSS canary (plan-006 §C5).

Implements brief 002 §7.1 load-bearing definition (resolves iter-1-S1):
an equation in the produced corpus is **load-bearing** iff it satisfies
AT LEAST ONE of:

* **(a) Section-anchor rule** — the equation appears under a kdoc body
  section heading whose title matches
  ``^#+\\s*(Results|Theorem|Claim|Key Results)\\b`` (case-insensitive).
  Mechanical.
* **(b) Cross-citation rule** — the equation is cited by ≥ 1 OTHER
  equation across the corpus (any kdoc body or assertion
  ``derivation_sketch``) via the canonical citation syntax. Mechanical.
* **(c) Critic-approved tag** — an assertion doc whose
  ``upstream_ref_hash`` matches the equation has
  ``load_bearing: true`` in its frontmatter.

This parser does **NOT** key off any per-equation ``importance:`` field
— that field does not exist in the canonical kdoc template at
``src/gpd/specs/templates/knowledge.md``. The iter-1-S1 audit confirmed
this. The brief 002 §7.1 rule (a/b/c) is the binding definition.

**Canonical citation syntax (resolves iter-1-W3)** per plan-006 §C5
line 387:

* ``[K-NNN:K.X]`` — kdoc id colon equation label, both bracketed.
* ``[E.N]`` — EQN-REF entry.
* Tolerant fallback: ``K-NNN eq K.X`` (older free-text form) — accepted
  for parsing but flagged for cleanup. Truly missing citations FAIL.

Reuses :func:`gpd.core.sympy_oracle.extract_equations_from_kdoc` for
body-locating only (it parses equation bodies; it does NOT canonicalize
them for hashing — see plan §C5 line 387 and core/sympy_oracle.py
lines 112-147). The hash pipeline goes through
:func:`gpd.core.assertion_divergence.compute_upstream_ref_hash`, which
calls ``eqn_normalize.normalize_eqn_body`` under the hood.

Sampling is **not allowed** (per brief 002 §7.1). The parser is
deterministic and walks the full produced corpus.
"""

from __future__ import annotations

import re
from pathlib import Path

from gpd.core.assertion_divergence import compute_upstream_ref_hash
from gpd.core.frontmatter import extract_frontmatter
from gpd.core.sympy_oracle import extract_equations_from_kdoc
from tests.canary.criteria import CriterionResult, CriterionStatus

# ─── Regex constants ─────────────────────────────────────────────────────────

# Section-anchor rule (a). Case-insensitive; matches one or more `#`
# followed by whitespace and one of the load-bearing section titles.
# `\b` anchors the right boundary so "Results" matches but "Resultset"
# does not.
_LOAD_BEARING_HEADING_RE = re.compile(
    r"^#+\s*(Results|Theorem|Claim|Key Results)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Any markdown ATX heading line (`# ...`, `## ...`, etc.) at line start.
_ANY_HEADING_RE = re.compile(r"^#+\s+.*$", re.MULTILINE)

# Canonical kdoc-equation citation: `[K-NNN:K.X]`. NNN is one or more
# digits; X is one or more digits.
_CITATION_KDOC_RE = re.compile(r"\[(K-\d+):(K\.\d+)\]")

# Canonical EQN-REF citation: `[E.N]` where N is one or more digits.
_CITATION_EQNREF_RE = re.compile(r"\[(E\.\d+)\]")

# Tolerant fallback: `K-NNN eq K.X` free-text form (pre-W3 fix).
# Accepted for parsing; flagged for cleanup.
_CITATION_KDOC_FREE_RE = re.compile(r"\b(K-\d+)\s+eq\s+(K\.\d+)\b")


# ─── Helpers ────────────────────────────────────────────────────────────────


def _kdoc_id_from_meta(meta: dict[str, object], kdoc_path: Path) -> str:
    """Return the canonical ``K-NNN`` form of the kdoc id.

    Prefers frontmatter ``kdoc_id`` (canonical form is ``K-NNN-slug`` —
    we strip the ``-slug`` suffix to get the bare ``K-NNN`` token used
    in citations). Falls back to extracting ``K-NNN`` from the file
    stem when the frontmatter is missing or malformed.
    """
    raw = meta.get("kdoc_id")
    if isinstance(raw, str) and raw:
        # Canonical form is `K-NNN-slug`; citations use bare `K-NNN`.
        m = re.match(r"(K-\d+)", raw)
        if m:
            return m.group(1)
        return raw
    # Fallback: filename pattern like `K-001-foo.md`.
    m = re.match(r"(K-\d+)", kdoc_path.stem)
    if m:
        return m.group(1)
    return kdoc_path.stem


def _heading_for_position(body: str, pos: int) -> str | None:
    """Return the most recent ATX heading line above ``pos`` in ``body``.

    Walks all heading matches and returns the last one whose end <=
    ``pos``. Returns ``None`` if no heading precedes the position
    (equation appears before any heading, e.g. in the file preamble).
    """
    last: str | None = None
    for m in _ANY_HEADING_RE.finditer(body):
        if m.end() <= pos:
            last = m.group(0)
        else:
            break
    return last


def _equation_position_in_body(body: str, eq_id: str) -> int | None:
    """Return the start position of ``eq_id``'s label in ``body``, or None.

    Tries the three label forms recognized by
    ``extract_equations_from_kdoc`` (canonical ``(K.N)`` or ``(E.N)``,
    bold ``**E.N**``, legacy ``**K.N**``). Returns the first match.
    """
    for pattern in (
        rf"\({re.escape(eq_id)}\)",
        rf"\*\*{re.escape(eq_id)}\*\*",
    ):
        m = re.search(pattern, body)
        if m:
            return m.start()
    return None


def _is_under_load_bearing_heading(body: str, eq_id: str) -> bool:
    """Rule (a): is ``eq_id`` under a load-bearing section heading?"""
    pos = _equation_position_in_body(body, eq_id)
    if pos is None:
        return False
    heading = _heading_for_position(body, pos)
    if heading is None:
        return False
    return bool(_LOAD_BEARING_HEADING_RE.match(heading))


def _extract_citations(
    text: str,
) -> tuple[set[tuple[str, str]], set[str], set[tuple[str, str]]]:
    """Extract canonical and tolerant-fallback citations from ``text``.

    Returns ``(kdoc_citations, eqnref_citations, free_text_citations)``:

    * ``kdoc_citations`` — set of ``(kdoc_id, eq_id)`` pairs from
      ``[K-NNN:K.X]`` matches.
    * ``eqnref_citations`` — set of ``E.N`` strings from ``[E.N]``
      matches.
    * ``free_text_citations`` — set of ``(kdoc_id, eq_id)`` pairs from
      the tolerant ``K-NNN eq K.X`` fallback. These are accepted but
      flagged in the caller for cleanup.
    """
    if not text:
        return set(), set(), set()
    kdoc_cites = {(m.group(1), m.group(2)) for m in _CITATION_KDOC_RE.finditer(text)}
    eqnref_cites = {m.group(1) for m in _CITATION_EQNREF_RE.finditer(text)}
    free_cites = {
        (m.group(1), m.group(2)) for m in _CITATION_KDOC_FREE_RE.finditer(text)
    }
    return kdoc_cites, eqnref_cites, free_cites


def _filter_to_produced(
    candidates: list[Path], produced_files: list[Path] | None
) -> list[Path]:
    """If ``produced_files`` is provided and non-empty, intersect with it.

    Path comparison is by resolved-absolute form to avoid CWD-relative
    vs. sandbox-relative mismatches between the cost-log strings and
    on-disk discovery.
    """
    if not produced_files:
        return candidates
    produced_set = {Path(p).resolve() for p in produced_files}
    return [p for p in candidates if p.resolve() in produced_set]


# ─── Main entry point ────────────────────────────────────────────────────────


def check(
    produced_files: list[Path],
    knowledge_dir: Path,
    assertion_dir: Path,
    truth_table: dict | None = None,  # unused for §7.1
) -> CriterionResult:
    """Run the §7.1 coverage check.

    See module docstring for the load-bearing definition. Returns a
    ``CriterionResult`` with:

    * ``status = PASS`` iff every load-bearing ``(kdoc_id, eq_id)`` is
      covered by ≥ 1 assertion (via hash match OR canonical citation in
      that assertion's ``derivation_sketch``).
    * ``status = FAIL`` otherwise; ``payload['uncovered']`` lists the
      ``(kdoc_id, eq_id)`` pairs and ``details`` carries human-readable
      diagnostics.

    Walks ``knowledge_dir`` and ``assertion_dir`` recursively.  When
    ``produced_files`` is non-empty, the walk is intersected with that
    set so cost-log-failed papers do not contribute (this matches the
    canary driver's run-attribution discipline; iter-1-S5 + iter-2-M3).
    """
    knowledge_dir = Path(knowledge_dir)
    assertion_dir = Path(assertion_dir)

    # ── 1. Discover kdoc and assertion files ────────────────────────
    kdoc_paths = (
        sorted(knowledge_dir.rglob("*.md")) if knowledge_dir.exists() else []
    )
    assertion_paths = (
        sorted(assertion_dir.rglob("*.md")) if assertion_dir.exists() else []
    )
    kdoc_paths = _filter_to_produced(kdoc_paths, produced_files)
    assertion_paths = _filter_to_produced(assertion_paths, produced_files)

    # Empty corpus: vacuously PASS (zero load-bearing equations means
    # 100% coverage). The canary driver decides separately whether the
    # cost-log emptiness itself is a failure.
    if not kdoc_paths and not assertion_paths:
        return CriterionResult(
            name="Coverage",
            status=CriterionStatus.PASS,
            summary="0/0 load-bearing equations covered (empty corpus).",
            details=["Empty produced corpus: no kdocs and no assertions."],
            payload={"uncovered": [], "load_bearing": [], "free_text_citations": []},
        )

    # ── 2. Parse all kdocs: equations + per-equation rule-(a) tag ────
    # eq_index: list of dicts, one per (kdoc_id, eq_id):
    #   {"kdoc_id", "eq_id", "body": latex, "rule_a": bool, "hash": str}
    eq_index: list[dict[str, object]] = []
    # hash_to_eqs: sha256 -> list of (kdoc_id, eq_id)
    hash_to_eqs: dict[str, list[tuple[str, str]]] = {}
    # All kdoc body text for citation scanning.
    kdoc_body_texts: list[str] = []
    parse_errors: list[str] = []

    for kdoc_path in kdoc_paths:
        try:
            text = kdoc_path.read_text(encoding="utf-8")
        except OSError as exc:
            parse_errors.append(f"Could not read {kdoc_path}: {exc}")
            continue
        try:
            meta, body = extract_frontmatter(text)
        except Exception as exc:  # noqa: BLE001 — frontmatter errors are diagnostic-only
            parse_errors.append(f"Frontmatter parse error in {kdoc_path}: {exc}")
            meta, body = {}, text
        kdoc_id = _kdoc_id_from_meta(meta, kdoc_path)
        kdoc_body_texts.append(body)

        equations = extract_equations_from_kdoc(kdoc_path)
        for eq_id, eq_body in equations:
            rule_a = _is_under_load_bearing_heading(body, eq_id)
            try:
                eq_hash = compute_upstream_ref_hash(eq_body)
            except Exception as exc:  # noqa: BLE001 — defensive
                parse_errors.append(
                    f"Hash computation failed for {kdoc_id}:{eq_id}: {exc}"
                )
                eq_hash = ""
            entry = {
                "kdoc_id": kdoc_id,
                "eq_id": eq_id,
                "body": eq_body,
                "rule_a": rule_a,
                "hash": eq_hash,
            }
            eq_index.append(entry)
            if eq_hash:
                hash_to_eqs.setdefault(eq_hash, []).append((kdoc_id, eq_id))

    # ── 3. Parse all assertions ─────────────────────────────────────
    # assertion_records: list of dicts with frontmatter fields + body.
    assertion_records: list[dict[str, object]] = []
    for a_path in assertion_paths:
        try:
            text = a_path.read_text(encoding="utf-8")
        except OSError as exc:
            parse_errors.append(f"Could not read {a_path}: {exc}")
            continue
        try:
            meta, body = extract_frontmatter(text)
        except Exception as exc:  # noqa: BLE001
            parse_errors.append(f"Frontmatter parse error in {a_path}: {exc}")
            meta, body = {}, text
        derivation_sketch = meta.get("derivation_sketch")
        if not isinstance(derivation_sketch, str):
            derivation_sketch = ""
        load_bearing_flag = bool(meta.get("load_bearing"))
        upstream_hash = meta.get("upstream_ref_hash")
        if not isinstance(upstream_hash, str):
            upstream_hash = ""
        assertion_records.append(
            {
                "path": a_path,
                "assertion_id": meta.get("assertion_id") or a_path.stem,
                "derivation_sketch": derivation_sketch,
                "load_bearing": load_bearing_flag,
                "upstream_ref_hash": upstream_hash,
            }
        )

    # ── 4. Compute citation set (rule b) and free-text findings ─────
    cited_kdoc_eqs: set[tuple[str, str]] = set()
    free_text_citations: set[tuple[str, str]] = set()
    # cited_eqnref_ids: set[str] = set()  # noqa — not used for kdoc-eq coverage
    for body in kdoc_body_texts:
        kc, _ec, fc = _extract_citations(body)
        cited_kdoc_eqs |= kc
        free_text_citations |= fc
    for rec in assertion_records:
        kc, _ec, fc = _extract_citations(rec["derivation_sketch"])
        cited_kdoc_eqs |= kc
        free_text_citations |= fc
    # Tolerant fallback: count free-text citations as rule (b) hits as
    # well (parser is tolerant; the Critic flags them as W-findings for
    # cleanup, but coverage is not blocked by free-text form).
    cited_kdoc_eqs |= free_text_citations

    # ── 5. Compute rule-(c) set ─────────────────────────────────────
    rule_c_eqs: set[tuple[str, str]] = set()
    for rec in assertion_records:
        if rec["load_bearing"] and rec["upstream_ref_hash"]:
            for eq_pair in hash_to_eqs.get(rec["upstream_ref_hash"], []):
                rule_c_eqs.add(eq_pair)

    # ── 6. Determine load-bearing set = (a) ∪ (b) ∪ (c) ─────────────
    load_bearing: list[tuple[str, str]] = []
    load_bearing_index: list[dict[str, object]] = []
    for entry in eq_index:
        pair = (entry["kdoc_id"], entry["eq_id"])
        rule_b = pair in cited_kdoc_eqs
        rule_c = pair in rule_c_eqs
        if entry["rule_a"] or rule_b or rule_c:
            load_bearing.append(pair)
            load_bearing_index.append(
                {
                    **entry,
                    "rule_b": rule_b,
                    "rule_c": rule_c,
                }
            )

    # ── 7. Coverage check: each load-bearing eq must be covered by ≥ 1
    # assertion via hash match OR canonical citation in derivation_sketch.
    # Build the assertion-cited set: (kdoc_id, eq_id) tuples that appear
    # in any assertion's derivation_sketch via canonical or fallback form.
    assertion_cited: set[tuple[str, str]] = set()
    for rec in assertion_records:
        kc, _ec, fc = _extract_citations(rec["derivation_sketch"])
        assertion_cited |= kc
        assertion_cited |= fc
    # Hash-covered set: pairs whose hash matches any assertion's
    # upstream_ref_hash.
    assertion_hashes = {
        rec["upstream_ref_hash"]
        for rec in assertion_records
        if rec["upstream_ref_hash"]
    }
    hash_covered: set[tuple[str, str]] = set()
    for h in assertion_hashes:
        for pair in hash_to_eqs.get(h, []):
            hash_covered.add(pair)

    uncovered: list[tuple[str, str]] = []
    for entry in load_bearing_index:
        pair = (entry["kdoc_id"], entry["eq_id"])
        if pair in hash_covered or pair in assertion_cited:
            continue
        uncovered.append(pair)

    # ── 8. Build CriterionResult ───────────────────────────────────
    n_lb = len(load_bearing)
    n_covered = n_lb - len(uncovered)
    summary = f"{n_covered}/{n_lb} load-bearing equations covered."

    details: list[str] = []
    if parse_errors:
        details.extend(parse_errors)
    if free_text_citations:
        details.append(
            "Tolerant-fallback `K-NNN eq K.X` citations detected (W-cleanup): "
            + ", ".join(f"{k} eq {e}" for k, e in sorted(free_text_citations))
        )
    if uncovered:
        details.append("Uncovered load-bearing equations:")
        for kdoc_id, eq_id in sorted(uncovered):
            details.append(f"  - {kdoc_id}:{eq_id}")

    status = CriterionStatus.PASS if not uncovered else CriterionStatus.FAIL

    return CriterionResult(
        name="Coverage",
        status=status,
        summary=summary,
        details=details,
        payload={
            "uncovered": [list(p) for p in uncovered],
            "load_bearing": [list(p) for p in load_bearing],
            "free_text_citations": [list(p) for p in sorted(free_text_citations)],
            "n_kdocs": len(kdoc_paths),
            "n_assertions": len(assertion_paths),
        },
    )


__all__ = ["check"]
