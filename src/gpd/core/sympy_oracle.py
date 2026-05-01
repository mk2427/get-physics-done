"""Pre-oracle SymPy equation check for the adversarial loop.

Runs before round 1 of the Critic-Fixer loop.  For each equation in the
kdoc's ``## Equations`` section, attempts symbolic verification via SymPy.
Returns pre-verified IDs (skip in critic) and pre-falsified findings (seed
as round-0 findings so the fixer gets them immediately).

The real SymPy code generation lives in the ``gpd-sympy-calculator``
agent (`src/gpd/agents/gpd-sympy-calculator.md`); this module owns the
orchestration + result schema + fail-open error handling.

Plan 005 commit c2 replaces the pre-005 ``unevaluated`` stub with a real
dispatch to ``gpd-sympy-calculator`` via ``dispatch_sympy_calculator``.
Following the ``run_parallel_critics`` precedent in
``core/adversarial_loop.py``, the actual agent spawn is
orchestrator-side: ``dispatch_sympy_calculator`` raises
``NotImplementedError`` by default, and tests / production wrappers
monkey-patch the symbol with either a canned payload (tests) or the
Claude Code Task-tool invocation (workflow-step runner). Per plan 005
§Q5, dispatch failures are caught and surface as
``verdict="unevaluated"`` rather than propagating — the pre-oracle is a
speedup, not a gate.
"""

from __future__ import annotations

import re
import subprocess  # noqa: F401  -- reserved for future in-process shell-outs
import sys
import unicodedata  # noqa: F401  -- reserved for future body normalization parity
from dataclasses import dataclass, field  # noqa: F401  -- field reserved for future metadata
from pathlib import Path

__all__ = [
    "OracleResult",
    "OracleDispatchError",
    "extract_equations_from_kdoc",
    "run_pre_oracle",
    "oracle_results_to_findings",
    "dispatch_sympy_calculator",
]


class OracleDispatchError(RuntimeError):
    """Raised by ``dispatch_sympy_calculator`` when the agent spawn
    fails, times out, or returns a malformed payload.

    Plan 005 §Q5: per-equation dispatch failure is ISOLATED — the
    ``_run_sympy_check`` wrapper catches this exception and returns
    ``OracleResult(verdict="unevaluated", output="dispatch_error: ...")``
    so other equations in the batch continue dispatching. Workflow-level
    handling is the caller's responsibility.
    """


@dataclass
class OracleResult:
    """Per-equation result from the SymPy pre-oracle.

    ``verdict`` is one of ``"verified"``, ``"falsified"``, ``"unevaluated"``
    and mirrors the ``gpd-sympy-calculator`` agent's output schema.
    ``attempts`` is capped at 3 per the agent protocol.
    """

    equation_id: str
    verdict: str  # "verified" | "falsified" | "unevaluated"
    latex: str
    sympy_code: str
    output: str
    attempts: int


# Plan 005 §S2: the canonical kdoc template at
# `src/gpd/specs/templates/knowledge.md:66-76` prescribes the `(K.N)`
# parenthesized form. The pre-004c `**E.N**` bold form remains
# supported as a compatibility alias for EQN-REF inputs and pre-004c
# test fixtures.

# All three equation-label patterns are anchored at line start (with
# optional indent) so that in-prose references like ``... using (K.5)
# above`` or ``Trap 8: (K.10) does not couple ...`` cannot trigger a
# spurious match. Without this anchor, ``[^\n]*?\$(.*?)\$`` happily
# walks across same-line prose and captures the next inline ``$...$``
# as a phantom equation body.

# Primary: canonical template form, ``(K.N) $equation$``
# (`knowledge.md:68-76`). Non-greedy ``.*?`` inside ``$`` stops at the
# first closing delimiter.
_EQUATION_PATTERN_KN = re.compile(
    r"(?:^|\n)[ \t]*\((K\.\d+)\)[^\n]*?\$(.*?)\$",
    re.DOTALL,
)

# Compatibility alias: bold-ID prose form used by EQN-REF inputs and
# legacy assertion-doc equations (``**E.N** ... $...$``).
_EQUATION_PATTERN_EN = re.compile(
    r"(?:^|\n)[ \t]*\*\*(E\.\d+)\*\*[^\n]*?\$(.*?)\$",
    re.DOTALL,
)

# Legacy kdoc form: ``**K.N**`` bold label followed (possibly across a
# blank line) by display math ``$$...$$``. Used by pre-template kdocs
# such as K-001 (BFSS Gaussian state chaos). Multi-line prose between
# label and equation is allowed; the first ``$$`` after the label
# bounds the body via non-greedy match.
_EQUATION_PATTERN_KN_LEGACY_DISPLAY = re.compile(
    r"(?:^|\n)[ \t]*\*\*(K\.\d+)\*\*.*?\$\$(.*?)\$\$",
    re.DOTALL,
)

# Display-math kdoc form: ``(K.N)`` parenthesized label, with same-line
# prose (label, TeX-name, section reference, ending in ``:``), followed
# by a ``$$...$$`` display-math block on a subsequent line. Used by
# pre-template kdocs such as K-003 (Kazakov-Zheng lattice YM
# bootstrap), where each equation entry reads:
#
#     (K.N) prose ... :
#     $$body$$
#
# The prefix ``[^\n]*\n+`` restricts the prose between the label and
# the ``$$`` to the same line as the label plus blank/whitespace
# lines. We deliberately do NOT allow arbitrary multi-line prose
# (which would let the pattern walk past the next ``(K.M)`` label and
# bind the wrong body); paragraph breaks containing additional prose
# are out of scope for this pattern. Dedup in
# ``extract_equations_from_kdoc`` runs this pattern BEFORE the
# canonical inline form so that an entry like
# ``(K.7) ... $\\inline\\math$:\\n$$body$$`` binds to the display body
# rather than the inline-math fragment in the prose label.
_EQUATION_PATTERN_KN_DISPLAY = re.compile(
    r"(?:^|\n)[ \t]*\((K\.\d+)\)[^\n]*\n+[ \t]*\$\$(.*?)\$\$",
    re.DOTALL,
)


def extract_equations_from_kdoc(kdoc_path: Path) -> list[tuple[str, str]]:
    """Return list of ``(equation_id, latex_body)`` from a kdoc's equations.

    Matches four forms, de-duplicated by ``equation_id`` (first
    occurrence wins):

    * **Canonical template form** per `knowledge.md:66-76`:
      ``(K.1) $equation$`` (parenthesized numeric label, inline math).
    * **Display-math kdoc form** for pre-template kdocs (e.g., K-003
      Kazakov-Zheng): ``(K.1) prose ... :\n\n$$equation$$`` —
      parenthesized label with the equation body in a separate
      display-math block. Multi-line prose between the label and the
      ``$$`` block is allowed.
    * **Compatibility alias** for EQN-REF and pre-004c fixtures:
      ``**E.1** prose: $equation$`` (bold-ID prose form).
    * **Legacy kdoc form** for pre-template kdocs (e.g., K-001 BFSS):
      ``**K.1** prose ... $$equation$$`` with the display-math block
      typically on a separate line. Multi-line prose between the label
      and the equation is allowed.

    The DOTALL flag lets the prose / context span line breaks; the
    non-greedy ``.*?`` inside ``$...$`` / ``$$...$$`` stops at the
    first closing delimiter. Pattern order matters for dedup: the
    display-math kdoc form runs BEFORE the canonical inline form so
    that an entry like ``(K.7) prose with $\\inline$ math:\\n$$body$$``
    binds to the display body rather than the inline-math fragment in
    the prose label. The legacy ``**K.N**`` and EQN-REF ``**E.N**``
    patterns target distinct label syntaxes and don't compete for the
    same id.
    """

    text = kdoc_path.read_text(encoding="utf-8")
    matches: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for pattern in (
        _EQUATION_PATTERN_KN_DISPLAY,
        _EQUATION_PATTERN_KN,
        _EQUATION_PATTERN_EN,
        _EQUATION_PATTERN_KN_LEGACY_DISPLAY,
    ):
        for m in pattern.finditer(text):
            eq_id = m.group(1)
            if eq_id in seen_ids:
                continue
            seen_ids.add(eq_id)
            matches.append((eq_id, m.group(2).strip()))
    return matches


def dispatch_sympy_calculator(
    latex: str,
    python_path: str,
    *,
    assumptions: dict | None = None,
    timeout_s: float = 60.0,
) -> dict:
    """Dispatch ``gpd-sympy-calculator``; returns the agent's output_schema dict.

    Orchestrator-owned: Claude Code's Task tool invokes this function's
    payload against the agent spec at
    ``src/gpd/agents/gpd-sympy-calculator.md``. The expected return
    shape is::

        {
            "verdict": "verified" | "falsified" | "unevaluated",
            "latex_result": str,
            "code": str,
            "output": str,
            "attempts": int,      # 1..3
            "timeout_hit": bool,
            "note": str,
        }

    In the pure-Python module layer this function raises
    ``NotImplementedError`` so tests MUST monkey-patch it (and the
    workflow-step runner MUST substitute the real Task-tool dispatch).
    Raises ``OracleDispatchError`` on agent-spawn failure, timeout, or
    malformed return from any wrapping caller (including
    ``_run_sympy_check`` fail-open handling).

    Subprocess (direct ``py -c``) dispatch was considered and rejected
    per plan 005 §Q1: the agent's ``<execution_protocol>`` requires a
    manual LaTeX→SymPy translation discipline that a deterministic
    translator cannot satisfy.
    """

    del latex, python_path, assumptions, timeout_s  # consumed by the monkey-patched dispatch
    raise NotImplementedError(
        "dispatch_sympy_calculator is orchestrator-side; tests monkey-patch this symbol "
        "and the workflow-step runner substitutes the Task-tool dispatch. "
        "See plan 005 §Q1 for the design rationale."
    )


def _run_sympy_check(latex: str, python_path: str) -> OracleResult:
    """Verify a single LaTeX equation via ``gpd-sympy-calculator``. Max 3 attempts.

    Plan 005 commit c2: dispatches the real agent via
    ``dispatch_sympy_calculator`` and maps the agent's output_schema
    onto ``OracleResult``. Per plan 005 §Q5 fail-open:
    ``OracleDispatchError`` is caught and surfaces as
    ``verdict="unevaluated"`` with ``output="dispatch_error: ..."`` so
    the pre-oracle stays a speedup rather than a gate. Any other
    unexpected exception propagates — the workflow-step wrapper's
    try/except/finally (plan 005 §file 3) handles those at the outer
    scope and preserves already-collected results.
    """

    try:
        payload = dispatch_sympy_calculator(latex, python_path)
    except OracleDispatchError as exc:
        return OracleResult(
            equation_id="",
            verdict="unevaluated",
            latex=latex,
            sympy_code="",
            output=f"dispatch_error: {exc}",
            attempts=1,
        )

    # Map the agent's output_schema onto OracleResult. Unknown verdicts
    # collapse to "unevaluated" so a malformed-but-non-exceptional
    # return still fails open.
    verdict = payload.get("verdict")
    if verdict not in {"verified", "falsified", "unevaluated"}:
        return OracleResult(
            equation_id="",
            verdict="unevaluated",
            latex=latex,
            sympy_code=str(payload.get("code", "")),
            output=f"dispatch_error: malformed verdict {verdict!r}",
            attempts=int(payload.get("attempts", 1) or 1),
        )

    return OracleResult(
        equation_id="",
        verdict=verdict,
        latex=latex,
        sympy_code=str(payload.get("code", "")),
        output=str(payload.get("output", "")),
        attempts=int(payload.get("attempts", 1) or 1),
    )


def run_pre_oracle(
    kdoc_path: Path,
    python_path: str | None = None,
) -> dict[str, OracleResult]:
    """Run the SymPy pre-oracle on all equations in a kdoc.

    Returns a dict keyed by ``equation_id`` (``"K.1"``, ``"K.2"``, ...).  The
    caller uses this in two ways:

    * Pre-verified equation IDs (``verdict == "verified"``) are marked so
      the Critic skips them in round 1.
    * Pre-falsified equations (``verdict == "falsified"``) are converted via
      :func:`oracle_results_to_findings` into seed findings handed to the
      Fixer in round 0.
    """

    py = python_path or sys.executable
    equations = extract_equations_from_kdoc(kdoc_path)
    results: dict[str, OracleResult] = {}
    for eq_id, latex in equations:
        result = _run_sympy_check(latex, py)
        result.equation_id = eq_id
        results[eq_id] = result
    return results


def oracle_results_to_findings(
    results: dict[str, OracleResult],
) -> list[dict]:
    """Convert falsified oracle results to pre-seeded Finding dicts.

    Each falsified result becomes a dict with the canonical keys used by
    the adversarial loop's round-0 seed-findings slot:

    * ``id`` / ``finding_id``: ``ORACLE-<eq_id>``
    * ``severity``: ``"S"`` (SymPy-confirmed contradiction is serious)
    * ``blocking``: ``True``
    * ``location``: the equation ID
    * ``problem`` (legacy) + ``summary``: human-readable description
    * ``equation_body``: the LaTeX body (plan 005 §Q4 refinement)
    * ``kind``: ``"oracle_falsified"`` (plan 005 §S3; required for the
      redesigned ``merge_parallel_findings`` dedup key
      ``(kind, location, sha256(normalize(body))[:16])``)
    * ``source``: ``"sympy_oracle"``

    The ``summary`` / ``equation_body`` / ``kind`` additions let this
    dict lift cleanly into an ``adversarial_loop.Finding`` for the
    parallel-critics merge path (plan 005 §S3 schema contract).
    """

    findings: list[dict] = []
    for eq_id, r in results.items():
        if r.verdict == "falsified":
            first = next((ln.strip() for ln in r.output.splitlines() if ln.strip()), "")
            if len(first) > 120:
                first = first[:117] + "..."
            summary = (
                f"SymPy oracle falsified equation {eq_id}: {first}"
                if first
                else f"SymPy oracle falsified equation {eq_id}"
            )
            findings.append(
                {
                    "id": f"ORACLE-{eq_id}",
                    "finding_id": f"ORACLE-{eq_id}",
                    "severity": "S",
                    "blocking": True,
                    "location": eq_id,
                    "problem": summary,
                    "summary": summary,
                    "equation_body": r.latex,
                    "kind": "oracle_falsified",
                    "source": "sympy_oracle",
                }
            )
    return findings
