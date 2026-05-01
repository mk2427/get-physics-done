"""Tests for ``tests/canary/criteria/coverage.py`` (plan-006 §C5).

Six tests covering the brief 002 §7.1 (a/b/c) load-bearing rule and
plan §C5's canonical citation syntax (``[K-NNN:K.X]`` / ``[E.N]``):

1. Passing case — every load-bearing equation has ≥ 1 covering
   assertion.
2. Failing case — a load-bearing equation under ``## Key Results`` has
   no assertion citing it; coverage FAILs.
3. Edge case — empty corpus (no kdocs, no assertions) → vacuous PASS.
4. Rule (b) — equation cited by another equation across kdocs becomes
   load-bearing and is correctly resolved.
5. Rule (c) — assertion with ``load_bearing: true`` and matching
   ``upstream_ref_hash`` promotes the equation to load-bearing.
6. Tolerant fallback — ``K-NNN eq K.X`` free-text citation is parsed
   and flagged in ``free_text_citations`` payload but does NOT cause
   FAIL on its own.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

from gpd.core.assertion_divergence import compute_upstream_ref_hash
from tests.canary.criteria import CriterionStatus
from tests.canary.criteria.coverage import check

# ─── Fixtures: helpers to write kdoc and assertion files ────────────────────


def _write_kdoc(
    dir_: Path,
    kdoc_id: str,
    body: str,
    slug: str = "topic",
    extra_meta: str = "",
) -> Path:
    """Write a minimally-conforming kdoc to ``dir_/{kdoc_id}-{slug}.md``."""
    p = dir_ / f"{kdoc_id}-{slug}.md"
    frontmatter = textwrap.dedent(
        f"""\
        ---
        kdoc_id: {kdoc_id}-{slug}
        status: Draft
        topic: "test"
        sources: []
        created: 2026-04-26
        last_reviewed: 2026-04-26
        review_rounds: 0
        superseded_by: null
        eqn_ref_schema_version: 1
        assertion_schema_version: 1
        layout: single
        {extra_meta}
        ---

        """
    )
    p.write_text(frontmatter + body, encoding="utf-8")
    return p


def _write_assertion(
    dir_: Path,
    assertion_id: str,
    *,
    upstream_ref_hash: str | None = None,
    derivation_sketch: str | None = None,
    load_bearing: bool = False,
    kind: str = "restated-equation",
) -> Path:
    """Write a minimally-conforming assertion doc.

    Dumps the frontmatter via PyYAML so multi-line / bracket-bearing
    ``derivation_sketch`` strings round-trip cleanly through
    ``extract_frontmatter`` (avoids manual block-scalar indentation
    pitfalls with ``textwrap.dedent`` + f-string substitution).
    """
    p = dir_ / f"{assertion_id}.md"
    meta = {
        "assertion_id": assertion_id,
        "kind": kind,
        "status": "Draft",
        "topic": "test",
        "knowledge_doc_ids": [],
        "eqn_ref_entries": [],
        "created": "2026-04-26",
        "last_reviewed": "2026-04-26",
        "review_rounds": 0,
        "superseded_by": None,
        "load_bearing": load_bearing,
        "derivation_sketch": derivation_sketch,
        "upstream_ref_hash": upstream_ref_hash,
        "upstream_status_mirror": {
            "kdoc_id": None,
            "kdoc_status_at_stable": None,
            "divergence_detected_at": None,
        },
    }
    yaml_str = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False)
    body = textwrap.dedent(
        f"""\

        # Assertion: {assertion_id}

        ## Restated Equation or Derived Claim

        $E = mc^2$
        """
    )
    p.write_text(f"---\n{yaml_str}---\n{body}", encoding="utf-8")
    return p


# ─── 1. Passing case ────────────────────────────────────────────────────────


def test_passing_case_all_load_bearing_covered(tmp_path: Path) -> None:
    """Single kdoc with one load-bearing eq under ``## Key Results``;
    one assertion with matching ``upstream_ref_hash`` covers it.
    """
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()

    eq_body = "E = mc^2"
    body = textwrap.dedent(
        f"""\
        # Knowledge: Test

        ## Overview

        Some prose.

        ## Key Results

        (K.1) ${eq_body}$
        Context: load-bearing under rule (a).
        """
    )
    _write_kdoc(kdir, "K-001", body)

    eq_hash = compute_upstream_ref_hash(eq_body)
    _write_assertion(
        adir,
        "A-001-test",
        upstream_ref_hash=eq_hash,
        kind="restated-equation",
    )

    result = check(produced_files=[], knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.PASS, result.details
    assert result.payload["uncovered"] == []
    assert result.payload["load_bearing"] == [["K-001", "K.1"]]
    assert result.summary.startswith("1/1")


# ─── 2. Failing case ────────────────────────────────────────────────────────


def test_failing_case_uncovered_load_bearing(tmp_path: Path) -> None:
    """Load-bearing eq under ``## Theorem`` has no covering assertion."""
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()

    body = textwrap.dedent(
        """\
        # Knowledge: Test

        ## Theorem

        (K.1) $E = mc^2$
        Context: load-bearing under (a) but uncovered.
        """
    )
    _write_kdoc(kdir, "K-002", body)

    # Assertion that does NOT match the equation hash AND does NOT
    # cite it in derivation_sketch.
    _write_assertion(
        adir,
        "A-002-other",
        upstream_ref_hash=compute_upstream_ref_hash("a + b = c"),
        kind="restated-equation",
    )

    result = check(produced_files=[], knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.FAIL
    assert ["K-002", "K.1"] in result.payload["uncovered"]
    # Ensure diagnostic details mention the uncovered equation.
    assert any("K-002:K.1" in d for d in result.details)


# ─── 3. Edge case: empty corpus ─────────────────────────────────────────────


def test_empty_corpus_vacuously_passes(tmp_path: Path) -> None:
    """Zero kdocs and zero assertions ⇒ 0/0 covered ⇒ PASS."""
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()

    result = check(produced_files=[], knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.PASS
    assert result.payload["uncovered"] == []
    assert result.payload["load_bearing"] == []
    assert "empty" in result.summary.lower() or "0/0" in result.summary


# ─── 4. Rule (b) cross-citation ─────────────────────────────────────────────


def test_rule_b_cross_citation(tmp_path: Path) -> None:
    """Equation cited by another equation across kdocs is load-bearing
    under rule (b); coverage requires an assertion to cite it.
    """
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()

    # K-010: defines (K.1). NOT under a load-bearing heading, so rule
    # (a) does not fire — only rule (b) can promote it.
    body_a = textwrap.dedent(
        """\
        # Knowledge: A

        ## Background

        (K.1) $\\alpha = \\beta$
        Context: not under a load-bearing heading.
        """
    )
    _write_kdoc(kdir, "K-010", body_a, slug="a")

    # K-020: cites K-010:K.1 in its body.
    body_b = textwrap.dedent(
        """\
        # Knowledge: B

        ## Discussion

        (K.1) $\\gamma = [K-010:K.1] \\cdot 2$
        Context: cites K-010:K.1.
        """
    )
    _write_kdoc(kdir, "K-020", body_b, slug="b")

    # Cover K-010:K.1 via assertion citing it canonically in
    # derivation_sketch.
    _write_assertion(
        adir,
        "A-010-cover",
        derivation_sketch="From [K-010:K.1] we get the result.",
        kind="derived-consequence",
    )

    result = check(produced_files=[], knowledge_dir=kdir, assertion_dir=adir)

    # K-010:K.1 is load-bearing via (b). K-020:K.1 is NOT load-bearing
    # (no rule fires for it), so absence of a covering assertion for
    # K-020:K.1 does not cause FAIL.
    lb_set = {tuple(p) for p in result.payload["load_bearing"]}
    assert ("K-010", "K.1") in lb_set
    assert result.status == CriterionStatus.PASS, result.details


# ─── 5. Rule (c) Critic-approved tag ────────────────────────────────────────


def test_rule_c_critic_approved_tag(tmp_path: Path) -> None:
    """Assertion with ``load_bearing: true`` + matching hash promotes
    the equation under rule (c). The same assertion covers it via
    hash.
    """
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()

    eq_body = "S = \\int \\mathcal{L}\\, d^4 x"
    body = textwrap.dedent(
        f"""\
        # Knowledge: Action

        ## Setup

        (K.1) ${eq_body}$
        Context: not under a load-bearing heading; only rule (c) can fire.
        """
    )
    _write_kdoc(kdir, "K-030", body)

    eq_hash = compute_upstream_ref_hash(eq_body)
    _write_assertion(
        adir,
        "A-030-action",
        upstream_ref_hash=eq_hash,
        load_bearing=True,
        kind="restated-equation",
    )

    result = check(produced_files=[], knowledge_dir=kdir, assertion_dir=adir)

    assert result.status == CriterionStatus.PASS
    lb_set = {tuple(p) for p in result.payload["load_bearing"]}
    assert ("K-030", "K.1") in lb_set


# ─── 6. Tolerant fallback citation form ────────────────────────────────────


def test_tolerant_fallback_citation_form(tmp_path: Path) -> None:
    """``K-NNN eq K.X`` free-text citation parses + flags but does
    not block coverage.
    """
    kdir = tmp_path / "knowledge"
    adir = tmp_path / "assertions"
    kdir.mkdir()
    adir.mkdir()

    body = textwrap.dedent(
        """\
        # Knowledge: Tolerant

        ## Background

        (K.1) $f = g$
        Context: cited in older free-text form below.
        """
    )
    _write_kdoc(kdir, "K-040", body)

    # Older free-text form `K-040 eq K.1` in derivation_sketch.
    _write_assertion(
        adir,
        "A-040-tolerant",
        derivation_sketch="From K-040 eq K.1 we obtain the consequence.",
        kind="derived-consequence",
    )

    result = check(produced_files=[], knowledge_dir=kdir, assertion_dir=adir)

    # Free-text form should be flagged in the payload.
    assert ["K-040", "K.1"] in result.payload["free_text_citations"]
    # And K-040:K.1 should be load-bearing under rule (b) (tolerant
    # fallback counts toward citations) AND covered by the assertion.
    lb_set = {tuple(p) for p in result.payload["load_bearing"]}
    assert ("K-040", "K.1") in lb_set
    assert result.status == CriterionStatus.PASS, result.details
    # Diagnostic surfacing: details should mention the W-cleanup.
    assert any("Tolerant-fallback" in d for d in result.details)
