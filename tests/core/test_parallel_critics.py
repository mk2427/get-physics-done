"""Tests for parallel multi-aspect critics (speedup B) + plan 005 §S3 dedup-key.

``merge_parallel_findings`` is the pure-functional aggregation step that
combines findings emitted by three parallel focus-area critics
(equations / conventions / completeness) into a single deduped list.

Plan 005 §S3 redesign: the dedup key is
``(kind_slug, location, sha256(normalize(equation_body))[:16])``. The
pre-S3 ``(location, equation_body[:60])`` key silently collapsed every
body-less finding into the ``("", "")`` bucket; the three-tuple key
always distinguishes different-``kind`` findings even at
``location=""``.
"""

from __future__ import annotations

from gpd.core.adversarial_loop import (
    Finding,
    merge_findings,
    merge_parallel_findings,
)


def _f(loc, eq, sev, blocking=False, kind="wrong_equation"):
    return Finding(
        location=loc,
        equation_body=eq,
        severity=sev,
        blocking=blocking,
        kind=kind,
    )


def test_dedup_same_location_keeps_highest_severity():
    a = [_f("eq-3", "E=mc^2", "W", kind="wrong_equation")]
    b = [_f("eq-3", "E=mc^2", "S", blocking=True, kind="wrong_equation")]
    c = []
    merged = merge_parallel_findings(a, b, c)
    assert len(merged) == 1
    assert merged[0].severity == "S"
    assert merged[0].blocking is True


def test_union_different_locations():
    a = [_f("eq-1", "x+y", "S")]
    b = [_f("eq-2", "a*b", "M")]
    c = [_f("eq-3", "f(x)", "W")]
    merged = merge_parallel_findings(a, b, c)
    assert len(merged) == 3


def test_empty_lists():
    merged = merge_parallel_findings([], [], [])
    assert merged == []


# ─── Plan 005 §S3 collision-resistance regression suite ───────────────────────


def test_empty_body_findings_with_different_kind_both_survive():
    """Codex S3 (a): body-less findings with different ``kind`` don't collide.

    Under the pre-S3 ``(location, equation_body[:60])`` key both would
    collapse to ``("", "")`` and only one would survive.
    """
    a = [Finding(location="", equation_body="", severity="M", kind="thin_overview")]
    b = [
        Finding(
            location="",
            equation_body="",
            severity="M",
            kind="missing_physical_picture",
        )
    ]
    c = []
    merged = merge_parallel_findings(a, b, c)
    assert len(merged) == 2
    kinds = {f.kind for f in merged}
    assert kinds == {"thin_overview", "missing_physical_picture"}


def test_same_60char_prefix_different_full_body_both_survive():
    """Codex S3 (b): two findings sharing the same first 60 chars of body.

    sha256 over the full body distinguishes them under the new key.
    """
    common_prefix = "A" * 60
    a = [_f("eq-chain", common_prefix + " tail-A", "S", kind="wrong_equation")]
    b = [_f("eq-chain", common_prefix + " tail-B-different", "S", kind="wrong_equation")]
    merged = merge_parallel_findings(a, b, [])
    assert len(merged) == 2


def test_whitespace_normalization_collapses_trivial_diffs():
    """Plan 005 iter-2-W2: whitespace-only body differences hash identically.

    A non-whitespace character difference (mc^2 vs mc^3) still separates.
    """
    a = [_f("eq-1", "E = mc^2", "S", kind="wrong_equation")]
    b = [_f("eq-1", "E  =  mc^2\n", "S", kind="wrong_equation")]
    merged_same = merge_parallel_findings(a, b, [])
    assert len(merged_same) == 1

    c = [_f("eq-1", "E = mc^3", "S", kind="wrong_equation")]
    merged_diff = merge_parallel_findings(a, b, c)
    assert len(merged_diff) == 2


def test_kindless_finding_passes_merge_helpers():
    """Plan 005 iter-2-M1: non-knowledge-critic findings flow kind=""

    ``merge_findings`` on a single input returns it unchanged;
    ``merge_parallel_findings`` unions distinct-location findings with
    ``kind=""`` without validator rejection (the validator is
    knowledge-critic-scoped).
    """
    f1 = Finding(location="A", equation_body="x+1", severity="S", kind="")
    f2 = Finding(location="B", equation_body="y+2", severity="W", kind="")
    assert merge_findings([f1]) == f1
    merged = merge_parallel_findings([f1], [f2], [])
    assert len(merged) == 2


def test_same_kind_same_location_two_critics_merge_highest_severity():
    """Codex S3 (c): two critics reporting the same issue merge correctly.

    MAX severity + OR of blocking is preserved under the new key.
    """
    a = [_f("K.3", "E = mc^2", "W", blocking=False, kind="wrong_equation")]
    b = [_f("K.3", "E = mc^2", "S", blocking=True, kind="wrong_equation")]
    merged = merge_parallel_findings(a, b, [])
    assert len(merged) == 1
    assert merged[0].severity == "S"
    assert merged[0].blocking is True
    assert merged[0].kind == "wrong_equation"
