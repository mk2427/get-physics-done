"""Tests for ``gpd.core.sympy_oracle`` (speedup C pre-oracle surface).

Covers the extraction regex for kdoc ``## Equations`` entries (canonical
``(K.N)`` template form per `knowledge.md:66-76` + compatibility alias
``**E.N**`` bold form), the findings-conversion path for falsified
oracle results, and the no-op surface for verified / unevaluated
results.
"""

from __future__ import annotations

import textwrap

from gpd.core import sympy_oracle as oracle_mod
from gpd.core.sympy_oracle import (
    OracleDispatchError,
    OracleResult,
    _run_sympy_check,
    extract_equations_from_kdoc,
    oracle_results_to_findings,
)


def test_extract_equations_template_form(tmp_path):
    """Plan 005 §S2: canonical ``(K.N)`` form matches per
    `knowledge.md:66-76`.
    """
    kdoc = tmp_path / "K-001-test.md"
    kdoc.write_text(
        textwrap.dedent(
            """
            ## Equations

            (K.1) $E = mc^2$
            Context: classical mechanics
            Why/How: rest-frame energy

            (K.2) $F = ma$
            Context: Newton
            Why/How: second law
            """
        )
    )
    eqs = extract_equations_from_kdoc(kdoc)
    assert ("K.1", "E = mc^2") in eqs
    assert ("K.2", "F = ma") in eqs


def test_extract_equations_en_alias(tmp_path):
    """Plan 005 §S2: the legacy ``**E.N**`` bold-ID form still matches."""
    kdoc = tmp_path / "K-002-test.md"
    kdoc.write_text(
        textwrap.dedent(
            """
            ## Equations

            **E.1** The energy relation: $E = mc^2$

            **E.2** Momentum: $p = mv$
            """
        )
    )
    eqs = extract_equations_from_kdoc(kdoc)
    assert ("E.1", "E = mc^2") in eqs
    assert ("E.2", "p = mv") in eqs


def test_extract_equations_en_multi(tmp_path):
    """Plan 005 §S2: guard against DOTALL non-greedy pathology across
    two ``**E.N**`` blocks. Each block must yield its own body.
    """
    kdoc = tmp_path / "K-003-test.md"
    kdoc.write_text(
        "## Equations\n\n"
        "**E.1** First: $a + b = c$\n\n"
        "**E.2** Second: $x * y = z$\n"
    )
    eqs = extract_equations_from_kdoc(kdoc)
    assert ("E.1", "a + b = c") in eqs
    assert ("E.2", "x * y = z") in eqs


def test_extract_equations_mixed(tmp_path):
    """A kdoc with both ``(K.N)`` and ``**E.N**`` blocks returns the
    union. IDs in different namespaces do not collide.
    """
    kdoc = tmp_path / "K-004-test.md"
    kdoc.write_text(
        textwrap.dedent(
            """
            ## Equations

            (K.1) $E = mc^2$

            **E.1** Legacy: $p = mv$
            """
        )
    )
    eqs = extract_equations_from_kdoc(kdoc)
    assert ("K.1", "E = mc^2") in eqs
    assert ("E.1", "p = mv") in eqs


def test_extract_equations_kn_legacy_display_form(tmp_path):
    """Pre-template kdoc form: ``**K.N**`` bold label followed by
    display-math ``$$...$$`` on a separate line, with arbitrary
    multi-line prose in between (including inline ``$...$`` math that
    must NOT terminate the body match).
    """
    kdoc = tmp_path / "K-001-legacy.md"
    kdoc.write_text(
        "## Equations\n\n"
        "**K.1** -- MSS bound (paper eq. (2); $\\hbar = k_B = 1$ throughout):\n\n"
        "$$\\lambda_L \\leq 2\\pi T$$\n\n"
        "---\n\n"
        "**K.2** -- OTOC definition (paper eq. (1)):\n\n"
        "$$C(t) = \\langle [W(t), V(0)]^2 \\rangle$$\n",
        encoding="utf-8",
    )
    eqs = dict(extract_equations_from_kdoc(kdoc))
    assert eqs["K.1"] == "\\lambda_L \\leq 2\\pi T"
    assert eqs["K.2"] == "C(t) = \\langle [W(t), V(0)]^2 \\rangle"


def test_extract_equations_ignores_in_prose_label_references(tmp_path):
    """All three label patterns are anchored at line start (optional
    leading whitespace). Mid-line references like ``... see (K.5) ...
    where $T$ ...`` or ``... formula (K.15) is ... where $\\lambda_L$
    ...`` must NOT bind to the inline math that happens to follow on
    the same line.

    Regression for the bug surfaced by extracting K-001 (BFSS Gaussian
    state chaos): in-prose parenthesized references plus same-line
    inline ``$...$`` produced 4 phantom equations
    (``K.8: X^a_i = \\langle\\hat{X}^a_i\\rangle``,
    ``K.10: \\tau_E``, ``K.15: T``, ``K.18: N_\\mathrm{dof}=1``)
    until each pattern was anchored at line start.
    """
    kdoc = tmp_path / "K-prose.md"
    kdoc.write_text(
        "## Equations\n\n"
        "(K.1) $\\lambda_L \\leq 2\\pi T$\n"
        "Context: real definition.\n\n"
        "## Notes\n\n"
        "Earlier work used (K.5) where $T$ was the temperature; "
        "the formula (K.15) gave $\\lambda_L^0$ at high T; "
        "see also **K.8** in passing where $X^a_i = \\langle X\\rangle$.\n",
        encoding="utf-8",
    )
    eqs = dict(extract_equations_from_kdoc(kdoc))
    assert "K.1" in eqs
    assert eqs["K.1"] == "\\lambda_L \\leq 2\\pi T"
    # No phantom matches from in-prose references.
    assert "K.5" not in eqs
    assert "K.8" not in eqs
    assert "K.15" not in eqs


def test_extract_equations_kn_display_form(tmp_path):
    """Plan-006 C13: ``(K.N) prose ... :\\n\\n$$body$$`` form (used by
    K-003 Kazakov-Zheng lattice YM bootstrap and other pre-template
    kdocs). The label and prose live on one line; the equation body is
    a separate display-math block. Multi-line prose paragraphs after
    the body are not consumed by the body match.
    """
    kdoc = tmp_path / "K-display.md"
    kdoc.write_text(
        "## Equations\n\n"
        "(K.1) Wilson action -- TeX label `eq: action`, section 2:\n"
        "$$S = -\\frac{N_c}{\\lambda} \\sum_{P} \\mathrm{Re}\\,"
        " \\mathrm{tr}\\, U_P$$\n"
        "Context: $U_P$ is the ordered product around plaquette $P$.\n\n"
        "(K.2) Wilson loop averages:\n\n"
        "$$W[C] = \\left\\langle \\frac{\\mathrm{tr}}{N_c}"
        " \\prod_{l \\in C} U_l \\right\\rangle$$\n",
        encoding="utf-8",
    )
    eqs = dict(extract_equations_from_kdoc(kdoc))
    assert "K.1" in eqs
    assert eqs["K.1"] == (
        "S = -\\frac{N_c}{\\lambda} \\sum_{P} \\mathrm{Re}\\,"
        " \\mathrm{tr}\\, U_P"
    )
    assert "K.2" in eqs
    assert eqs["K.2"] == (
        "W[C] = \\left\\langle \\frac{\\mathrm{tr}}{N_c}"
        " \\prod_{l \\in C} U_l \\right\\rangle"
    )


def test_extract_equations_kn_display_dedup_with_canonical(tmp_path):
    """Plan-006 C13: a kdoc that mixes the canonical inline form
    ``(K.1) $body1$`` and the new display form ``(K.2) ... :\\n$$body2$$``
    extracts both with their respective bodies; the display pattern
    must NOT spuriously bind to inline-math fragments inside another
    label's prose section.
    """
    kdoc = tmp_path / "K-mixed-display.md"
    kdoc.write_text(
        "## Equations\n\n"
        "(K.1) $E = mc^2$\n"
        "Context: rest energy.\n\n"
        "(K.2) 3-loop perturbation theory, $N_c = \\infty$:\n"
        "$$u_P = 1 - \\frac{\\lambda}{8} - 0.005107\\,\\lambda^2$$\n"
        "Context: weak-coupling regime.\n",
        encoding="utf-8",
    )
    eqs = dict(extract_equations_from_kdoc(kdoc))
    assert eqs["K.1"] == "E = mc^2"
    assert eqs["K.2"] == (
        "u_P = 1 - \\frac{\\lambda}{8} - 0.005107\\,\\lambda^2"
    )
    # No phantom binding of K.2 to the inline ``$N_c = \\infty$`` in
    # the prose label.
    assert "N_c" not in eqs["K.2"] or "u_P" in eqs["K.2"]
    assert eqs["K.2"].startswith("u_P")


def test_extract_equations_k003_excerpt(tmp_path):
    """Plan-006 C13 regression: K-003 (Kazakov-Zheng) Makeenko-Migdal
    loop equations entry exercises the display-math kdoc form with a
    multi-line ``$$...$$`` body. Mirrors the actual kdoc fragment.
    """
    kdoc = tmp_path / "K-003-excerpt.md"
    kdoc.write_text(
        "## Equations\n\n"
        "(K.3) Makeenko-Migdal loop equations -- TeX label `MMLE`,"
        " section 2:\n"
        "$$\\sum_{\\nu \\perp \\mu} \\left( W[C_{l_\\mu} \\cdot"
        " \\overrightarrow{\\delta C^\\nu_{l_\\mu}}] - W[C_{l_\\mu}"
        " \\cdot \\overleftarrow{\\delta C^\\nu_{l_\\mu}}] \\right)"
        " = \\lambda \\sum_{\\substack{l' \\in C \\\\ l' \\sim l}}"
        " \\epsilon_{ll'}\\, W[C_{ll'}]\\, W[C_{l'l}]$$\n"
        "Context: Schwinger-Dyson equations for WAs.\n",
        encoding="utf-8",
    )
    eqs = dict(extract_equations_from_kdoc(kdoc))
    assert "K.3" in eqs
    body = eqs["K.3"]
    # Body starts with the LHS sum and contains the RHS factorized
    # product of Wilson averages.
    assert body.startswith("\\sum_{\\nu \\perp \\mu}")
    assert "W[C_{ll'}]\\, W[C_{l'l}]" in body
    # Body does NOT include the prose context line.
    assert "Schwinger-Dyson" not in body


def test_extract_equations_kn_canonical_wins_over_legacy(tmp_path):
    """When both canonical ``(K.N) $body$`` and legacy ``**K.N**``
    + ``$$body$$`` appear for the same id, dedup keeps the canonical
    body (canonical pattern iterates first).
    """
    kdoc = tmp_path / "K-mixed.md"
    kdoc.write_text(
        "## Equations\n\n"
        "(K.1) $E = mc^2$\n\n"
        "**K.1** legacy alias: $$E = m c^{2}$$\n",
        encoding="utf-8",
    )
    eqs = dict(extract_equations_from_kdoc(kdoc))
    assert eqs["K.1"] == "E = mc^2"


def test_oracle_results_to_findings_empty():
    results = {"E.1": OracleResult("E.1", "verified", "E=mc^2", "", "", 1)}
    assert oracle_results_to_findings(results) == []


def test_oracle_results_to_findings_falsified():
    results = {
        "E.1": OracleResult("E.1", "falsified", "E=mc^2", "code", "expected 2, got 3", 2)
    }
    findings = oracle_results_to_findings(results)
    assert len(findings) == 1
    assert findings[0]["severity"] == "S"
    assert findings[0]["blocking"] is True


def test_oracle_results_to_findings_includes_summary_equation_body_and_kind():
    """Plan 005 §Q4 refinement + §S3: oracle-seeded dicts carry the
    fields required by the redesigned ``Finding`` schema +
    ``merge_parallel_findings`` dedup key.
    """
    results = {
        "K.2": OracleResult(
            "K.2", "falsified", "2 + 2 = 5", "code", "counterexample: 4 != 5", 2
        )
    }
    findings = oracle_results_to_findings(results)
    assert len(findings) == 1
    f = findings[0]
    assert f["kind"] == "oracle_falsified"
    assert f["location"] == "K.2"
    assert f["equation_body"] == "2 + 2 = 5"
    assert f["summary"]  # populated, non-empty
    assert f["summary"] == f["problem"]  # mirrors legacy field
    assert f["source"] == "sympy_oracle"


def test_oracle_results_to_findings_summary_is_one_line():
    """Cosmetic fix: ``summary`` is a one-liner (no embedded newlines),
    bounded length, so consumers that render it next to a separate
    ``Evidence:`` block (the OracleResult.output dump) don't print the
    full output twice. The full output is preserved on the ``OracleResult``;
    R0-REVIEW.md writers pull it from there for the Evidence block.
    """
    multi_line_output = (
        "lhs = oo\n"
        "rhs = pi**2/6\n"
        "lhs is finite? False\n"
        "H_1000 = 7.485470860550345\n"
        "rhs numeric = 1.6449340668482264\n"
    )
    results = {
        "K.3": OracleResult(
            "K.3",
            "falsified",
            r"\sum 1/n = \pi^2/6",
            "code",
            multi_line_output,
            1,
        )
    }
    findings = oracle_results_to_findings(results)
    assert len(findings) == 1
    summary = findings[0]["summary"]
    assert "\n" not in summary
    assert len(summary) <= 200
    assert "K.3" in summary
    # First non-empty line of the output is what gets surfaced.
    assert "lhs = oo" in summary


def test_oracle_results_to_findings_summary_handles_empty_output():
    """No output lines → summary still well-formed (no trailing colon)."""
    results = {
        "K.4": OracleResult("K.4", "falsified", r"x = y", "code", "   \n\n", 1)
    }
    findings = oracle_results_to_findings(results)
    summary = findings[0]["summary"]
    assert "\n" not in summary
    assert summary.endswith("K.4")  # no trailing ": " when output is blank


def test_run_sympy_check_dispatches_agent(monkeypatch):
    """Plan 005 §S4: `_run_sympy_check` routes through
    `dispatch_sympy_calculator` and maps the agent's output_schema to
    an `OracleResult`.
    """
    captured: dict = {}

    def fake_dispatch(latex, python_path, *, assumptions=None, timeout_s=60.0):
        captured["latex"] = latex
        return {
            "verdict": "verified",
            "latex_result": "E = mc^2",
            "code": "sp.simplify(E - m*c**2)",
            "output": "0",
            "attempts": 1,
            "timeout_hit": False,
            "note": "",
        }

    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", fake_dispatch)
    result = _run_sympy_check("E = mc^2", "/usr/bin/py")
    assert captured["latex"] == "E = mc^2"
    assert result.verdict == "verified"
    assert result.latex == "E = mc^2"
    assert result.sympy_code == "sp.simplify(E - m*c**2)"
    assert result.attempts == 1


def test_run_sympy_check_fails_open(monkeypatch):
    """Plan 005 §Q5: `OracleDispatchError` surfaces as
    `verdict="unevaluated"` with a `dispatch_error: ...` trace —
    per-equation failure never propagates.
    """

    def fake_dispatch(latex, python_path, *, assumptions=None, timeout_s=60.0):
        raise OracleDispatchError("agent spawn timed out")

    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", fake_dispatch)
    result = _run_sympy_check("x + y = z", "/usr/bin/py")
    assert result.verdict == "unevaluated"
    assert "dispatch_error" in result.output
    assert "agent spawn timed out" in result.output


def test_run_sympy_check_malformed_verdict_fails_open(monkeypatch):
    """A malformed-but-non-exceptional payload (unknown verdict)
    collapses to `unevaluated` with a `dispatch_error: malformed
    verdict ...` trace. Guards against partial-contract regressions.
    """

    def fake_dispatch(latex, python_path, *, assumptions=None, timeout_s=60.0):
        return {"verdict": "bogus"}

    monkeypatch.setattr(oracle_mod, "dispatch_sympy_calculator", fake_dispatch)
    result = _run_sympy_check("a = b", "/usr/bin/py")
    assert result.verdict == "unevaluated"
    assert "malformed verdict" in result.output
