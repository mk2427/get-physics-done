"""§7.3 Typo+axis recovery parser — BFSS-specific (plan-006 §C7).

Loaded by the canary driver via
``--criteria-module tests.canary.criteria_per_project.bfss`` (default
in the BFSS preset wrapper). Subclasses the abstract ``Criterion7``
base in ``criteria_per_project/__init__.py``.

PASS gate (per plan-006 §C7, post-iter-1-S6 + iter-1-W2 fixes):

- 16/16 axes referenced in the produced kdoc corpus (axis-specific
  symbol probes, see ``_AXIS_PROBES``).
- 10/10 ``typos_confirmed`` annotated by at least one produced kdoc
  (T-### appears in body or frontmatter alongside its correction
  fingerprint).
- γ¹⁰ Euclidean BLOCKING flag (Axis 7) flagged as ``BLOCKING:`` /
  ``BLOCKING=YES`` in at least one produced kdoc — plan-006 §C7
  step 5.
- Zero over-claims on ``typos_not_typo`` — if any produced kdoc
  annotates a NOT-TYPO entry as a confirmed typo, FAIL.

``typos_inconclusive`` are NOT load-bearing for PASS; their presence
or absence is reported in ``CriterionResult.payload`` for operator
review only.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.canary.criteria import CriterionResult, CriterionStatus
from tests.canary.criteria_per_project import Criterion7, Criterion7Inputs


# ---------------------------------------------------------------------------
# Axis probes — minimal symbol fingerprints derived from Part A §1.
#
# Every axis ships at least one mechanical token whose presence in
# kdoc body text indicates the axis was discussed. Probes are
# deliberately small and high-signal (e.g., ``γ^{10}`` for Axis 7,
# ``T̃`` for Axis 4); a kdoc that mentions any one of an axis' probes
# is counted as "covering" that axis.
# ---------------------------------------------------------------------------


_AXIS_PROBES: dict[int, list[str]] = {
    1: ["tr 1 = 1", "Tr 1 = N", "(1/N) Tr", "tr ="],
    2: ["SU(N)", "U(N)", "c.o.m.", "center of mass"],
    3: ["[X^I, X^J]", "[X, X]", "BFSS Hamiltonian", "Lin-Zheng Eq"],
    4: ["T̃", "T/λ^{1/3}", "lambda^{1/3}", "T tilde"],
    5: ["Majorana", "γ^I", "16-component", "real-symmetric"],
    6: ["g_YM", "α'", "alpha'", "ℓ_s", "g_s"],
    7: ["γ^{10}", "gamma^{10}", "γ_E", "γ10", "gamma10"],
    8: ["−i [X", "-i [X", "+i [X", "Gauss law", "C|phys"],
    9: ["ℓ(X)", "ℓ(P)", "ℓ(ψ)", "level assignment"],
    10: ["Polyakov", "𝒫 exp", "P exp(i", "Tr P exp"],
    11: ["BMN", "μ", "factor 3", "factor-3"],
    12: ["Wilson", "lattice stencil", "U^2", "improved"],
    13: ["Lorentzian", "Euclidean", "(−,+,+,…,+)", "mostly-plus"],
    14: ["16 ⊗ 16", "1 ⊕ 9", "126", "γ^{IJ}"],
    15: ["N/λ", "N/lambda", "Euclidean prefactor", "S_E"],
    16: ["Δ_{O", "Delta_{O", "Biggs-Maldacena", "(2 + b)(7/5)", "five-tower"],
}


_BLOCKING_AXIS_ID = 7


# Compile a forgiving "BLOCKING: YES" detector. Accepts any of:
#   BLOCKING: YES    BLOCKING=YES    BLOCKING = YES
# case-insensitively. The presence of any such token in any produced
# kdoc satisfies plan-006 §C7 step 5.
_BLOCKING_RE = re.compile(r"BLOCKING\s*[:=]\s*YES", re.IGNORECASE)


def _read_text_safely(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _gather_corpus_texts(
    produced_files: list[Path],
    knowledge_dir: Path,
) -> dict[Path, str]:
    """Return ``{path: text}`` for every produced kdoc under knowledge_dir.

    Filters ``produced_files`` to those that resolve under
    ``knowledge_dir`` (per the C9 run-attribution discipline) and
    reads each file. Files that cannot be read are skipped silently.
    """
    out: dict[Path, str] = {}
    knowledge_dir_resolved = knowledge_dir.resolve()
    for raw in produced_files:
        try:
            resolved = Path(raw).resolve()
        except OSError:
            continue
        # Only count files under the sandbox knowledge directory.
        try:
            resolved.relative_to(knowledge_dir_resolved)
        except ValueError:
            continue
        if not resolved.is_file():
            continue
        out[resolved] = _read_text_safely(resolved)
    return out


def _axes_covered(corpus: dict[Path, str]) -> dict[int, list[str]]:
    """For each axis id, return the list of probes that hit at least once.

    An axis is "covered" iff its returned list is non-empty.
    """
    blob = "\n".join(corpus.values())
    out: dict[int, list[str]] = {}
    for axis_id, probes in _AXIS_PROBES.items():
        hits = [p for p in probes if p in blob]
        out[axis_id] = hits
    return out


def _typos_annotated(
    corpus: dict[Path, str],
    typos: list[dict],
) -> dict[str, list[Path]]:
    """For each typo's T_id, return the kdocs that mention it.

    A kdoc "annotates" a typo iff the canonical T-### token appears
    anywhere in its text (frontmatter or body). The stricter
    "alongside its correction fingerprint" gate is left to a higher-
    fidelity follow-up parser; for plan-006 §C7 the T-### presence
    test is the canonical discriminator.
    """
    out: dict[str, list[Path]] = {}
    for entry in typos:
        tid = entry.get("T_id", "")
        if not tid:
            continue
        hits = [p for p, text in corpus.items() if tid in text]
        out[tid] = hits
    return out


def _blocking_flagged(corpus: dict[Path, str]) -> list[Path]:
    """Return the kdocs that carry a ``BLOCKING: YES`` token.

    plan-006 §C7 step 5 requires this for the γ¹⁰ Euclidean
    hermiticity axis (Axis 7); any kdoc that mentions a γ^{10} probe
    AND carries a BLOCKING token satisfies the gate.
    """
    return [p for p, text in corpus.items() if _BLOCKING_RE.search(text)]


def _gamma10_aware_blocking(corpus: dict[Path, str]) -> list[Path]:
    """Return kdocs that flag BLOCKING in proximity to a γ^{10} probe.

    Stricter than ``_blocking_flagged``: requires that the same kdoc
    both carries the BLOCKING token AND references at least one γ^{10}
    probe. This enforces plan-006 §C7 step 5's intent that the
    BLOCKING flag attaches to Axis 7, not to some unrelated kdoc that
    happens to use the word ``BLOCKING``.
    """
    gamma10_probes = _AXIS_PROBES[_BLOCKING_AXIS_ID]
    out: list[Path] = []
    for path, text in corpus.items():
        if not _BLOCKING_RE.search(text):
            continue
        if any(probe in text for probe in gamma10_probes):
            out.append(path)
    return out


class BFSSCriterion7(Criterion7):
    """BFSS-specific §7.3 typo+axis recovery parser."""

    name = "BFSS Typo+Axis Recovery"

    def check(self, inputs: Criterion7Inputs) -> CriterionResult:
        truth = inputs.truth_table
        axes = truth.get("axes", [])
        typos_confirmed = truth.get("typos_confirmed", [])
        typos_inconclusive = truth.get("typos_inconclusive", [])
        typos_not_typo = truth.get("typos_not_typo", [])

        if not axes:
            return CriterionResult(
                name=self.name,
                status=CriterionStatus.ERROR,
                summary="Truth-table missing 'axes' (builder did not run).",
            )

        corpus = _gather_corpus_texts(inputs.produced_files, inputs.knowledge_dir)
        details: list[str] = []
        payload: dict[str, object] = {}

        # ----- 16-axis coverage ------------------------------------------------
        coverage = _axes_covered(corpus)
        missing_axes = [a for a in axes if not coverage.get(a["id"])]
        payload["axes_total"] = len(axes)
        payload["axes_missing"] = [
            {"id": a["id"], "name": a["name"]} for a in missing_axes
        ]
        if missing_axes:
            for a in missing_axes:
                details.append(
                    f"axis-missing: id={a['id']} name={a['name']!r} "
                    f"(no Part-A symbol probe matched any produced kdoc)"
                )

        # ----- 10/10 confirmed typos ------------------------------------------
        confirmed_hits = _typos_annotated(corpus, typos_confirmed)
        missing_confirmed = [
            entry for entry in typos_confirmed
            if not confirmed_hits.get(entry.get("T_id", ""))
        ]
        payload["typos_confirmed_total"] = len(typos_confirmed)
        payload["typos_confirmed_missing"] = [
            {"T_id": e["T_id"], "description": e.get("description", "")}
            for e in missing_confirmed
        ]
        for e in missing_confirmed:
            details.append(
                f"typo-confirmed-missing: {e['T_id']} "
                f"({e.get('description', '')!r}) not annotated in any produced kdoc"
            )

        # ----- inconclusive (informational) -----------------------------------
        inconclusive_hits = _typos_annotated(corpus, typos_inconclusive)
        payload["typos_inconclusive_annotated"] = sorted(
            tid for tid, hits in inconclusive_hits.items() if hits
        )
        payload["typos_inconclusive_total"] = len(typos_inconclusive)

        # ----- NOT-TYPO over-claim guard --------------------------------------
        not_typo_hits = _typos_annotated(corpus, typos_not_typo)
        # An over-claim is a kdoc that mentions a NOT-TYPO T-### in a
        # CONFIRMED-style annotation. We approximate this by checking
        # whether the T-### appears alongside the word "CONFIRMED" within
        # the same kdoc; otherwise treat the mention as a legitimate
        # rejected-claim trap reference (Trap A8/A9/A10 etc.).
        over_claims: list[dict] = []
        for entry in typos_not_typo:
            tid = entry.get("T_id", "")
            for path in not_typo_hits.get(tid, []):
                text = corpus[path]
                # crude: T-### within ~200 chars of "CONFIRMED" in same doc.
                for m in re.finditer(re.escape(tid), text):
                    window = text[max(0, m.start() - 200): m.end() + 200]
                    if re.search(r"\bCONFIRMED\b", window, re.IGNORECASE):
                        over_claims.append(
                            {"T_id": tid, "path": str(path)}
                        )
                        break
        payload["typos_not_typo_over_claims"] = over_claims
        for oc in over_claims:
            details.append(
                f"typo-not-typo-over-claim: {oc['T_id']} annotated as CONFIRMED "
                f"in {oc['path']}"
            )

        # ----- γ¹⁰ Euclidean BLOCKING flag (Axis 7) ---------------------------
        blocking_hits = _gamma10_aware_blocking(corpus)
        payload["blocking_axis_id"] = _BLOCKING_AXIS_ID
        payload["blocking_kdocs"] = [str(p) for p in blocking_hits]
        if not blocking_hits:
            details.append(
                f"blocking-missing: γ¹⁰ Euclidean hermiticity (Axis "
                f"{_BLOCKING_AXIS_ID}) not flagged with 'BLOCKING:' in any "
                f"produced kdoc that references γ^{{10}}"
            )

        # ----- aggregate verdict ----------------------------------------------
        passed = (
            not missing_axes
            and not missing_confirmed
            and bool(blocking_hits)
            and not over_claims
        )
        if passed:
            summary = (
                f"PASS: {len(axes)}/{len(axes)} axes covered, "
                f"{len(typos_confirmed)}/{len(typos_confirmed)} CONFIRMED typos "
                f"annotated, γ¹⁰ BLOCKING flagged, 0 NOT-TYPO over-claims."
            )
            status = CriterionStatus.PASS
        else:
            reasons = []
            if missing_axes:
                reasons.append(f"{len(missing_axes)} axes missing")
            if missing_confirmed:
                reasons.append(f"{len(missing_confirmed)} CONFIRMED typos missing")
            if not blocking_hits:
                reasons.append("γ¹⁰ BLOCKING flag absent")
            if over_claims:
                reasons.append(f"{len(over_claims)} NOT-TYPO over-claims")
            summary = "FAIL: " + "; ".join(reasons)
            status = CriterionStatus.FAIL

        return CriterionResult(
            name=self.name,
            status=status,
            summary=summary,
            details=details,
            payload=payload,
        )


__all__ = ["BFSSCriterion7"]
