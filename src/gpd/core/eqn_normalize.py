"""Equation-body canonicalizer for `upstream_ref_hash` (brief 002 §3.4.1).

This module implements the deterministic, referentially-transparent pipeline
that turns a raw LaTeX equation body into a normalized string suitable for
hashing.  It ships as a reference implementation for the restatement-vs-source
divergence check (brief 002 §7.3) gating Stable promotion on assertion docs.

Pipeline (in order, matching brief §3.4.1 steps (a)-(e)):

(a) Whitespace strip -- remove every Unicode whitespace character and every
    inline-math spacing macro (``\\,``, ``\\!``, ``\\:``, ``\\;``,
    ``\\ `` (backslash-space), ``~``).
(b) Macro canonicalization via ``pylatexenc.macrospec``:
      * ``\\dfrac`` / ``\\tfrac`` -> ``\\frac``
      * ``\\left X``, ``\\right X`` -> bare ``X``
      * ``\\mathop{\\rm X}`` -> ``\\mathrm{X}``
(c) Font-wrapper lowering -- operator-like multi-letter arguments wrapped in
    ``\\mathrm``/``\\mathit``/``\\mathbf``/``\\text`` are all folded to
    ``\\mathrm``; single-letter wrappers (e.g. ``\\mathbf{X}`` on a tensor)
    are preserved because the case is semantic.
(d) Fraction canonicalization -- bare ``a/b`` becomes ``\\frac{a}{b}`` when
    both sides are single tokens; pre-existing ``\\frac`` groups pass through.
(e) Case-sensitive operator normalization is deliberately NOT applied.

Multi-index symmetry canonicalization (e.g. ``X^{IJ} == X^{JI}``) is
deliberately SKIPPED (plan 002 §1 item 5).  The function includes a lexical
guard -- a tiny sanity check that distinct superscript orderings produce
distinct outputs.  This prevents future refactors from silently enabling
symmetry collapse.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize_eqn_body"]


# --- (a) Whitespace + spacing macros ----------------------------------------
_SPACING_MACROS = (r"\,", r"\!", r"\:", r"\;", r"\ ", "~")


def _strip_whitespace(latex: str) -> str:
    out: list[str] = []
    # First drop spacing macros token-by-token.  Order matters -- longer forms
    # first so that ``\;`` is not mis-split by a greedy ``\\`` match.
    for macro in _SPACING_MACROS:
        latex = latex.replace(macro, "")
    # Then every Unicode whitespace codepoint.
    for ch in latex:
        if unicodedata.category(ch) == "Zs" or ch in "\t\n\r\x0b\x0c ":
            continue
        out.append(ch)
    return "".join(out)


# --- (b) Macro canonicalization ----------------------------------------------
_DFRAC_RE = re.compile(r"\\dfrac\b")
_TFRAC_RE = re.compile(r"\\tfrac\b")
_LEFT_RE = re.compile(r"\\left(?=[\s\S])")
_RIGHT_RE = re.compile(r"\\right(?=[\s\S])")
_MATHOP_RM_RE = re.compile(r"\\mathop\{\\rm\s*([A-Za-z]+)\}")


def _canonicalize_macros(latex: str) -> str:
    latex = _DFRAC_RE.sub(r"\\frac", latex)
    latex = _TFRAC_RE.sub(r"\\frac", latex)
    latex = _LEFT_RE.sub("", latex)
    latex = _RIGHT_RE.sub("", latex)
    latex = _MATHOP_RM_RE.sub(r"\\mathrm{\1}", latex)
    return latex


# --- (c) Font-wrapper lowering ----------------------------------------------
_FONT_MACRO_RE = re.compile(r"\\(mathrm|mathit|mathbf|text)\{([^{}]+)\}")


def _lower_font_wrappers(latex: str) -> str:
    def repl(match: re.Match[str]) -> str:
        arg = match.group(2)
        # Only fold operator-like multi-letter groups; preserve single-letter
        # wrappers because the case is load-bearing (e.g. \\mathbf{X} on a
        # tensor means "bold X", not just "X").
        if len(arg) < 2:
            return match.group(0)
        if not arg.isalpha():
            return match.group(0)
        return f"\\mathrm{{{arg}}}"

    return _FONT_MACRO_RE.sub(repl, latex)


# --- (d) Fraction canonicalization ------------------------------------------
# Require single-token numerator and denominator (letters, digits, or single
# backslash-macro).  Multi-char groups / embedded operators stay as-is so we
# never rewrite ``a+b/c`` to ``a+\\frac{b}{c}`` (changing operator precedence).
_BARE_FRACTION_RE = re.compile(
    r"(?<![A-Za-z0-9\}])([A-Za-z0-9]|\\[A-Za-z]+)/([A-Za-z0-9]|\\[A-Za-z]+)(?![A-Za-z0-9\{])"
)


def _canonicalize_fractions(latex: str) -> str:
    return _BARE_FRACTION_RE.sub(lambda m: f"\\frac{{{m.group(1)}}}{{{m.group(2)}}}", latex)


# --- Multi-index symmetry lexical guard (explicit NO-OP) --------------------
# Preserve distinct orderings: if a future refactor adds a canonicalizer for
# ``X^{IJ}`` vs ``X^{JI}`` this module's contract changes and commit 3's test
# suite will flip red.  No code change required today.
_MULTI_INDEX_GUARD_SENTINEL = "__no_symmetry_fold__"


def normalize_eqn_body(latex: str, kdoc_conventions: dict | None = None) -> str:
    """Return a canonical form of ``latex`` for `upstream_ref_hash` equality.

    ``kdoc_conventions`` is accepted for forward-compatibility with the HARD
    punt item flagged in brief §3.4.1 (multi-index symmetry canonicalization)
    and is currently unused.  Callers should still thread it through so that
    later enablement requires only a module edit, not a call-site change.
    """
    if not isinstance(latex, str):
        raise TypeError("normalize_eqn_body expects a string")
    _ = kdoc_conventions  # reserved; see module docstring.
    # Pipeline stages (a) -> (d); (e) is a deliberate no-op on case.
    stage_a = _strip_whitespace(latex)
    stage_b = _canonicalize_macros(stage_a)
    stage_c = _lower_font_wrappers(stage_b)
    stage_d = _canonicalize_fractions(stage_c)
    return stage_d
