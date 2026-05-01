"""Adversarial-review loop primitive -- severity adapter + router (brief 002 §5).

Stateless primitives landed in commit 4a:

* Severity adapter (brief §5.1 table).
* Critic-vs-Critic merge (MAX severity + OR of ``blocking``).
* Finding-ID validator (``^iter-\\d+-[SMWN]\\d+$``; brief §7.3).
* 5-case assertion router (brief §5.2) with recursion depth capped at 3.

Commit 4b adds (still pure-functional except for the JSON writer):

* ``LoopState`` enum + ``next_loop_state`` state-machine transition
  (``IDLE -> IN_PROGRESS -> REVISE | SUCCESS | ESCALATE-UNRESOLVED``).
* ``check_merge_allowed`` CI merge-hook helper (brief §5.1 (iii)):
  returns ``(False, 412, reason)`` iff any blocking finding is open on
  the branch's ``adversarial_review_status`` block.
* ``update_blocking_findings`` writer: persists
  ``adversarial_review_status.blocking_findings_unresolved: list[str]``
  to ``state.json`` (brief §5.1 (iv); co-located with §8.4
  ``invalidation_events`` ledger).

Plan 005 commit c0 (S3 dedup-key redesign):

* ``Finding`` dataclass gains a ``kind: str = ""`` slug field.
* ``_CANONICAL_FINDING_KINDS`` registry (append-only) enumerates the
  canonical slugs produced by ``gpd-knowledge-critic`` plus the
  ``oracle_falsified`` slug emitted by the SymPy pre-oracle.
* ``merge_parallel_findings`` dedup key becomes
  ``(kind_slug, location, sha256(normalize(equation_body))[:16])`` via
  ``_finding_dedup_key``; whitespace-normalized sha256 over the FULL
  body supersedes the pre-S3 ``(location, equation_body[:60])`` key
  that collapsed every body-less finding into a single
  ``("", "")`` bucket (Codex r1 S3).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from gpd.core.sympy_oracle import (
    OracleDispatchError,
    dispatch_sympy_calculator,
    oracle_results_to_findings,
    run_pre_oracle,
)

__all__ = [
    "CanonicalSeverity",
    "NativeCriticSeverity",
    "Finding",
    "AssertionKind",
    "RouteEntry",
    "LoopState",
    "FINDING_ID_RE",
    "MAX_SUB_ASSERTION_DEPTH",
    "DEFAULT_MAX_ITERATIONS",
    "adapt_severity",
    "merge_findings",
    "merge_parallel_findings",
    "run_parallel_critics",
    "is_valid_finding_id",
    "classify_assertion",
    "route_assertion",
    "next_loop_state",
    "check_merge_allowed",
    "update_blocking_findings",
    "run_pre_oracle",
    "oracle_results_to_findings",
    "dispatch_sympy_calculator",
    "OracleDispatchError",
    "_CANONICAL_FINDING_KINDS",
]


class CanonicalSeverity(StrEnum):
    """Orchestrator-canonical severity letters (brief §5.1 legend).

    ``MODERATE`` ("M") is reserved for manually-authored findings (e.g. audit
    reports, orchestrator-level briefs) that are written by humans, not by the
    Critic adapter.  The adapter (``adapt_severity``) never produces M — its
    table maps FATAL/SERIOUS → S, WARNING → W, MINOR → N.  Finding IDs of the
    form ``iter-N-M<n>`` are valid per ``FINDING_ID_RE`` and accepted by
    ``update_blocking_findings``; they must be injected directly as
    ``Finding(severity=CanonicalSeverity.MODERATE, ...)`` rather than via
    ``adapt_severity``.
    """

    SERIOUS = "S"
    MODERATE = "M"  # reserved: manually-authored only; not producible by adapt_severity
    WEAK = "W"
    NIT = "N"


class NativeCriticSeverity(StrEnum):
    """Native four-letter severities emitted by ``gpd-adversarial-critic``."""

    FATAL = "FATAL"
    SERIOUS = "SERIOUS"
    WARNING = "WARNING"
    MINOR = "MINOR"


# Brief §5.1 table (source of truth for ``test_severity_adapter``).
_NATIVE_TO_CANONICAL: dict[NativeCriticSeverity, tuple[CanonicalSeverity, bool]] = {
    NativeCriticSeverity.FATAL: (CanonicalSeverity.SERIOUS, True),
    NativeCriticSeverity.SERIOUS: (CanonicalSeverity.SERIOUS, False),
    NativeCriticSeverity.WARNING: (CanonicalSeverity.WEAK, False),
    NativeCriticSeverity.MINOR: (CanonicalSeverity.NIT, False),
}

# Rank for Critic-vs-Critic MAX merge (lower = more severe).
_CANONICAL_RANK: dict[CanonicalSeverity, int] = {
    CanonicalSeverity.SERIOUS: 0,
    CanonicalSeverity.MODERATE: 1,
    CanonicalSeverity.WEAK: 2,
    CanonicalSeverity.NIT: 3,
}


# Plan 005 §S3: append-only registry of canonical finding-kind slugs
# produced by ``gpd-knowledge-critic`` across its four focus areas +
# the per-invocation completeness filter, plus the ``oracle_falsified``
# slug emitted by ``sympy_oracle.oracle_results_to_findings``. Slugs
# feed the ``(kind, location, body_hash)`` dedup key redesigned in
# ``merge_parallel_findings`` to eliminate the pre-S3 ``("", "")``
# collision that silently collapsed distinct body-less findings.
#
# This registry is knowledge-critic-scoped; findings produced by
# ``gpd-adversarial-critic`` for ``artifact_kind in {brief, plan,
# physics}`` retain ``kind=""`` and are NOT validated against this set
# (iter-2-M1 decision).
_CANONICAL_FINDING_KINDS: frozenset[str] = frozenset(
    {
        # <focus_areas> §1 Equation errors
        "wrong_equation",
        "wrong_sign",
        "wrong_coefficient",
        "ocr_hallucination",
        "dimensional_error",
        # <focus_areas> §2 Convention mismatches
        "missing_convention",
        "convention_clash",
        "convention_lock_divergence",
        "cross_kdoc_contradiction",
        # <focus_areas> §4 Internal contradictions (specialization slugs +
        # umbrella for back-compat with the critic's existing prose)
        "traps_vs_equation_contradiction",
        "derivation_contradiction",
        "results_derivation_mismatch",
        "frontmatter_artifact_mismatch",
        "simultaneous_equation_violation",
        "internal_contradiction",
        # <focus_area> singular per-invocation completeness filter
        "thin_overview",
        "missing_physical_picture",
        "missing_why_how",
        "missing_result",
        "missing_regime",
        # Plan 005 pre-oracle (source: sympy_oracle)
        "oracle_falsified",
    }
)


def _normalize_body(body: str) -> str:
    """Collapse whitespace + NFC-normalize a finding's equation body.

    Two critics extracting the same equation body with trivial
    whitespace differences (``\\n`` vs space in LaTeX source, trailing
    whitespace, tab-vs-space, combining-accent decomposition) hash
    identically under ``_body_hash``. Non-whitespace character
    differences survive untouched so ``wrong_equation`` findings on
    genuinely different equations never collide (Plan 005 iter-2-W2).
    """

    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", body).strip())


def _body_hash(body: str | None) -> str:
    """sha256 hex digest (truncated to 16 chars) of the normalized body.

    Empty/None input returns ``""`` so cross-cutting findings (doc-level
    ``thin_overview`` etc.) remain distinguishable by ``kind`` alone in
    the three-tuple dedup key.
    """

    if not body:
        return ""
    return hashlib.sha256(_normalize_body(body).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Finding:
    """A single Critic finding after severity normalization.

    ``finding_id`` matches ``^iter-\\d+-[SMWN]\\d+$`` (brief §7.3).
    ``blocking`` is the FATAL-vs-SERIOUS propagation flag (brief §5.1 (ii)-(iv));
    any open ``blocking=True`` forces REVISE at the 4b loop controller.
    ``root_event_id`` is reserved for commit 10d ``invalidation_events`` linkage.
    ``location`` and ``equation_body`` are optional metadata used by the
    parallel-critic merge path (speedup B).
    ``kind`` is a canonical slug from ``_CANONICAL_FINDING_KINDS`` (plan
    005 §S3) identifying the issue family. Required for findings
    produced on the knowledge-critic path; defaulted to ``""`` so
    brief/plan/physics critics and legacy callers continue to compile.
    The ``merge_parallel_findings`` dedup key is
    ``(kind, location, sha256(normalize(equation_body))[:16])``; the
    three-tuple distinguishes body-less doc-level findings
    (``thin_overview`` vs ``missing_physical_picture``) that the pre-S3
    ``(location, equation_body[:60])`` key silently collapsed.
    ``finding_id`` defaults to empty so constructors built purely from a
    parallel-critic payload need not mint a canonical ID up front; the
    orchestrator assigns a valid ID before the finding enters the
    canonical ledger.
    """

    finding_id: str = ""
    severity: CanonicalSeverity = CanonicalSeverity.NIT
    blocking: bool = False
    summary: str = ""
    root_event_id: str | None = None
    location: str | None = None
    equation_body: str | None = None
    kind: str = ""


FINDING_ID_RE: re.Pattern[str] = re.compile(r"^iter-\d+-[SMWN]\d+$")


def is_valid_finding_id(finding_id: str) -> bool:
    """Return True iff *finding_id* matches ``^iter-\\d+-[SMWN]\\d+$``.

    Letters-only validation: the ``blocking`` flag is a separate JSON field,
    not part of the ID string (brief §5.1 (v)).
    """

    if not isinstance(finding_id, str):
        raise TypeError(f"finding_id must be str, got {type(finding_id).__name__}")
    return bool(FINDING_ID_RE.match(finding_id))


def adapt_severity(native: str | NativeCriticSeverity) -> tuple[CanonicalSeverity, bool]:
    """Normalize a native Critic severity to canonical S/M/W/N + ``blocking``.

    Brief §5.1 table: FATAL->(S,True); SERIOUS->(S,False); WARNING->(W,False);
    MINOR->(N,False).  The Stable Critic prompt MUST NOT be edited; this
    adapter is the only normalization surface.
    """

    if isinstance(native, NativeCriticSeverity):
        key = native
    elif isinstance(native, str):
        try:
            key = NativeCriticSeverity(native.strip().upper())
        except ValueError as exc:
            raise ValueError(
                f"Unknown native critic severity {native!r}; "
                f"expected one of {[s.value for s in NativeCriticSeverity]}"
            ) from exc
    else:
        raise TypeError(
            f"native severity must be str or NativeCriticSeverity, got {type(native).__name__}"
        )
    return _NATIVE_TO_CANONICAL[key]


def merge_findings(findings: Iterable[Finding]) -> Finding:
    """Merge same-issue Critic findings (brief §5.1 (i)).

    * ``severity`` = MAX across inputs (S > M > W > N); ties break first-seen.
    * ``blocking`` = logical OR across inputs.
    * ``finding_id`` = first input's ID (caller owns canonical ordering).
    * ``summary`` = most-severe input's summary; ties break first-seen.
    * ``root_event_id`` = first non-None across inputs.
    """

    items = list(findings)
    if not items:
        raise ValueError("merge_findings requires at least one Finding")
    if len(items) == 1:
        return items[0]

    sorted_by_rank = sorted(
        enumerate(items),
        key=lambda pair: (_CANONICAL_RANK[pair[1].severity], pair[0]),
    )
    _, most_severe = sorted_by_rank[0]
    blocking_or = any(f.blocking for f in items)
    root_event = next((f.root_event_id for f in items if f.root_event_id is not None), None)

    return Finding(
        finding_id=items[0].finding_id,
        severity=most_severe.severity,
        blocking=blocking_or,
        summary=most_severe.summary,
        root_event_id=root_event,
        location=items[0].location,
        equation_body=items[0].equation_body,
        kind=items[0].kind,
    )


class AssertionKind(StrEnum):
    """Brief §5.2 partition of assertion docs.

    (top-level ``derivation_sketch`` in {empty, non-empty}) x
    (in-body sub-assertions in {absent, present}):

    * RESTATED_EQUATION            = (empty, absent)
    * DERIVED_CONSEQUENCE          = (non-empty, absent)
    * MIXED_KIND                   = (empty, present)     [iter-2-W1]
    * COMPOUND_DERIVED_CONSEQUENCE = (non-empty, present) [iter-3-W1]
    * KNOWLEDGE_DOC                = knowledge-doc artifact_kind
    """

    RESTATED_EQUATION = "restated-equation"
    DERIVED_CONSEQUENCE = "derived-consequence"
    MIXED_KIND = "mixed-kind"
    COMPOUND_DERIVED_CONSEQUENCE = "compound-derived-consequence"
    KNOWLEDGE_DOC = "knowledge-doc"


# Recursion cap (brief §5.2 "Recursion depth limit").  Depth is a chain
# length: top-level=1, sub=2, sub-of-sub=3, depth 4 is the first illegal level.
MAX_SUB_ASSERTION_DEPTH: int = 3


@dataclass(frozen=True, slots=True)
class RouteEntry:
    """Router output row: a claim node -> critic agent.

    ``sub_id`` is ``"top-level"`` for the doc-level claim, else the
    in-body sub-assertion ID (namespaced per ``feedback_simple_finding_ids``).
    """

    sub_id: str
    critic: str
    kind: AssertionKind


# Canonical critic agents (brief 002 §5.2 + brief 001 §2).  The Knowledge
# critic lands with the knowledge pipeline in later commits; the workflow
# tolerates it being absent at 4a time.
_CRITIC_ADVERSARIAL = "gpd-adversarial-critic"
_CRITIC_KNOWLEDGE = "gpd-knowledge-critic"


def _has_derivation_sketch(frontmatter: Mapping[str, object] | None) -> bool:
    if not frontmatter:
        return False
    raw = frontmatter.get("derivation_sketch")
    if raw is None:
        return False
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, (list, tuple, dict)):
        return bool(raw)
    return bool(raw)


def _validate_recursion_depth(
    sub_assertions: Sequence[Mapping[str, object]],
    *,
    current_depth: int,
) -> None:
    """Raise if nested sub-assertions exceed ``MAX_SUB_ASSERTION_DEPTH``.

    Depth model (aligned with ``assertion_divergence._assertion_depth``):
    * depth 0 = top-level assertion doc (the document root; NOT passed here).
    * depth 1 = direct sub-assertions (top-level call passes ``current_depth=1``).
    * depth 2 = sub-of-sub.
    * depth 3 = sub-of-sub-of-sub (cap; ``MAX_SUB_ASSERTION_DEPTH = 3``).
    * depth 4+ = illegal; raises ``ValueError``.

    Top-level callers MUST pass ``current_depth=1`` (children of the depth-0 doc).
    """

    if current_depth > MAX_SUB_ASSERTION_DEPTH:
        raise ValueError(
            f"Sub-assertion recursion depth {current_depth} exceeds cap "
            f"MAX_SUB_ASSERTION_DEPTH={MAX_SUB_ASSERTION_DEPTH} "
            f"(brief 002 §5.2 'Recursion depth limit'); schema validation error"
        )
    for sub in sub_assertions:
        if not isinstance(sub, Mapping):
            raise TypeError(
                f"sub-assertion entries must be mappings with frontmatter-like keys; "
                f"got {type(sub).__name__}"
            )
        nested = sub.get("sub_assertions") or []
        if not isinstance(nested, Sequence) or isinstance(nested, (str, bytes)):
            raise TypeError(f"sub_assertions must be a sequence, got {type(nested).__name__}")
        if nested:
            _validate_recursion_depth(nested, current_depth=current_depth + 1)


def classify_assertion(
    frontmatter: Mapping[str, object] | None,
    sub_assertions: Sequence[Mapping[str, object]] | None = None,
    *,
    artifact_kind: str = "assertion",
) -> AssertionKind:
    """Label an assertion doc onto the §5.2 partition.  Pure-functional; no LLM call."""

    if artifact_kind == "knowledge":
        return AssertionKind.KNOWLEDGE_DOC
    has_derivation = _has_derivation_sketch(frontmatter)
    has_subs = bool(sub_assertions)
    if has_derivation and has_subs:
        return AssertionKind.COMPOUND_DERIVED_CONSEQUENCE
    if has_derivation:
        return AssertionKind.DERIVED_CONSEQUENCE
    if has_subs:
        return AssertionKind.MIXED_KIND
    return AssertionKind.RESTATED_EQUATION


def _critic_for_sub(sub: Mapping[str, object]) -> tuple[str, AssertionKind]:
    """Pick the critic for a leaf sub-assertion by recursive §5.2 rule."""

    nested_subs = sub.get("sub_assertions") or []
    kind = classify_assertion(sub, nested_subs if nested_subs else None, artifact_kind="assertion")
    if kind == AssertionKind.RESTATED_EQUATION:
        return _CRITIC_KNOWLEDGE, kind
    return _CRITIC_ADVERSARIAL, kind


def route_assertion(
    frontmatter: Mapping[str, object] | None,
    sub_assertions: Sequence[Mapping[str, object]] | None = None,
    *,
    artifact_kind: str = "assertion",
    top_level_id: str = "top-level",
) -> list[RouteEntry]:
    """Deterministic 5-case dispatch of an assertion doc onto critics.

    * No sub-assertions: exactly ONE ``RouteEntry`` for the top-level.
    * With sub-assertions: one entry per claim (top-level + each sub),
      recursing through nested subs (depth capped at
      ``MAX_SUB_ASSERTION_DEPTH``).
    * Knowledge docs route to ``gpd-knowledge-critic`` (5th case).
    * Depth > 3 raises ValueError AT router entry (before any critic).

    Selection is deterministic on frontmatter + presence of in-body
    sub-assertions (brief §5.2).
    """

    subs = list(sub_assertions) if sub_assertions else []
    # Validate the full nest BEFORE emitting any routes (router-entry check).
    # current_depth=1: these are depth-1 children of the depth-0 top-level doc.
    if subs:
        _validate_recursion_depth(subs, current_depth=1)

    kind = classify_assertion(frontmatter, subs if subs else None, artifact_kind=artifact_kind)

    if kind == AssertionKind.KNOWLEDGE_DOC:
        return [RouteEntry(sub_id=top_level_id, critic=_CRITIC_KNOWLEDGE, kind=kind)]
    if kind == AssertionKind.RESTATED_EQUATION:
        return [RouteEntry(sub_id=top_level_id, critic=_CRITIC_KNOWLEDGE, kind=kind)]
    if kind == AssertionKind.DERIVED_CONSEQUENCE:
        return [RouteEntry(sub_id=top_level_id, critic=_CRITIC_ADVERSARIAL, kind=kind)]

    # Mixed-kind and compound-derived-consequence both fan out per-sub.
    top_critic = _CRITIC_KNOWLEDGE if kind == AssertionKind.MIXED_KIND else _CRITIC_ADVERSARIAL
    entries: list[RouteEntry] = [RouteEntry(sub_id=top_level_id, critic=top_critic, kind=kind)]
    for index, sub in enumerate(subs):
        sub_id = str(sub.get("id") or f"sub-{index + 1}")
        nested = sub.get("sub_assertions") or []
        if nested:
            # Recurse with namespaced ID (feedback_simple_finding_ids).
            entries.extend(
                route_assertion(
                    sub,
                    nested,
                    artifact_kind="assertion",
                    top_level_id=sub_id,
                )
            )
        else:
            critic, sub_kind = _critic_for_sub(sub)
            entries.append(RouteEntry(sub_id=sub_id, critic=critic, kind=sub_kind))
    return entries


# ─── Loop state machine (commit 4b) ───────────────────────────────────────────


class LoopState(StrEnum):
    """Adversarial-review loop controller states (brief §5.1 + §6.1).

    ``IDLE``            — no loop in flight; the primitive has not been
                          dispatched on the current artifact.
    ``IN_PROGRESS``     — the orchestrator has dispatched Critics and is
                          awaiting verdicts; severity counts are not yet
                          final.
    ``REVISE``          — at least one open finding carries
                          ``blocking: True`` OR severity counts are non-zero.
                          Loop stays in REVISE across iterations until every
                          blocking finding is closed (brief §5.1 (ii)).
                          Exception: for ``artifact_kind in ("brief", "plan")``,
                          SUCCESS fires at iteration ≥ 2 when no blocking
                          (S/M) findings remain, even if W/N findings are open
                          (``feedback_scaffold_as_we_go`` 2-round cap).
    ``SUCCESS``         — One of (a) 0/0/0/0 severity counts AND
                          ``blocking_findings_unresolved`` is empty
                          (brief §5.1 (iv)); (b) ``artifact_kind`` is
                          ``"brief"``/``"plan"`` AND iteration ≥ 2 AND no
                          blocking (S/M) findings remain; or (c) W/N
                          fast-exit: ``artifact_kind`` is not
                          ``"brief"``/``"plan"``, iteration ≥ 1, S=M=0, and
                          only W/N findings remain — the fixer has already
                          handled them so a fresh Critic pass is wasted.
    ``ESCALATE_UNRESOLVED`` — iteration cap reached while blocking findings
                             remain open (`feedback_autonomous_loop` stall
                             rule).
    """

    IDLE = "IDLE"
    IN_PROGRESS = "IN_PROGRESS"
    REVISE = "REVISE"
    SUCCESS = "SUCCESS"
    ESCALATE_UNRESOLVED = "ESCALATE-UNRESOLVED"


# Default iteration cap for the loop controller. Callers may pass a lower
# cap per brief §3 ("≤2 rounds" integration smoke) or per tier; the ceiling
# is set wide enough to cover the `gpd-adversarial-critic`'s 4-round
# mandatory escalation per its own prompt.
DEFAULT_MAX_ITERATIONS: int = 4


def _severity_counts_all_zero(severity_counts: Mapping[str, int] | None) -> bool:
    """Return True iff every S/M/W/N count in the mapping is zero.

    Missing keys are treated as zero. Non-integer values raise TypeError.
    """

    if severity_counts is None:
        return True
    for key in ("S", "M", "W", "N"):
        raw = severity_counts.get(key, 0)
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise TypeError(
                f"severity_counts[{key!r}] must be int, got {type(raw).__name__}"
            )
        if raw != 0:
            return False
    return True


def _sm_counts_zero(severity_counts: Mapping[str, int] | None) -> bool:
    """Return True when S and M counts are both zero (W/N may be non-zero)."""
    if not severity_counts:
        return True
    return severity_counts.get("S", 0) == 0 and severity_counts.get("M", 0) == 0


def next_loop_state(
    *,
    current_state: LoopState,
    severity_counts: Mapping[str, int] | None,
    blocking_findings_unresolved: Sequence[str] | None,
    iteration: int,
    max_iterations: int | None = DEFAULT_MAX_ITERATIONS,
    artifact_kind: str = "assertion",
) -> LoopState:
    """Compute the next loop state per brief §5.1 (ii)–(iv).

    Transition rules (pure function of its inputs):

    * ``IDLE -> IN_PROGRESS``: any call with ``current_state == IDLE``
      advances to IN_PROGRESS; severity counts are ignored (the orchestrator
      has not yet collected Critic verdicts).
    * If ``blocking_findings_unresolved`` is non-empty:
        * ``max_iterations`` is not None and ``iteration >= max_iterations``
          -> ``ESCALATE_UNRESOLVED`` (cap hit with blockers open;
          `feedback_autonomous_loop` stall rule).
        * otherwise -> ``REVISE`` regardless of S/M/W/N counts
          (brief §5.1 (ii)).
    * If ``blocking_findings_unresolved`` is empty:
        * ``artifact_kind in ("brief", "plan")`` and ``iteration >= 2``
          -> ``SUCCESS`` (brief §3 / ``feedback_scaffold_as_we_go`` 2-round
          cap for scaffold artifacts; non-blocking W/N nits do not block
          completion).
        * W/N fast-exit: ``artifact_kind`` is NOT ``"brief"``/``"plan"``,
          ``iteration >= 1``, S and M counts are both zero, and at least
          one W/N finding remains -> ``SUCCESS``. The fixer already
          addressed these in the current round; rerunning the full Critic
          pass for W/N-only residue is wasted work.
        * severity counts all zero -> ``SUCCESS`` (brief §5.1 (iv)
          convergence gate).
        * otherwise -> ``REVISE`` (non-blocking findings still need
          author response).

    ``max_iterations=None`` means no iteration cap (L20 physics/knowledge/
    assertion artifact rule).  Pass ``DEFAULT_MAX_ITERATIONS`` (4) for
    standard artifacts; physics/knowledge/assertion artifacts MUST pass
    ``None`` to honour L20.

    Callers own authoring ``blocking_findings_unresolved`` from the merged
    finding set via ``merge_findings`` + collecting those with
    ``blocking=True``; this function does not inspect ``Finding`` objects.
    """

    if current_state == LoopState.IDLE:
        return LoopState.IN_PROGRESS

    if not isinstance(iteration, int) or isinstance(iteration, bool):
        raise TypeError(f"iteration must be int, got {type(iteration).__name__}")
    if max_iterations is not None:
        if not isinstance(max_iterations, int) or isinstance(max_iterations, bool):
            raise TypeError(
                f"max_iterations must be int or None, got {type(max_iterations).__name__}"
            )
        if max_iterations < 1:
            raise ValueError(
                f"max_iterations must be >=1 when set; got {max_iterations=}"
            )
    if iteration < 0:
        raise ValueError(f"iteration must be >=0; got {iteration=}")

    blocking_open = list(blocking_findings_unresolved or [])
    if blocking_open:
        if max_iterations is not None and iteration >= max_iterations:
            return LoopState.ESCALATE_UNRESOLVED
        return LoopState.REVISE

    # No blocking findings remain open.
    # brief/plan artifacts: enforce 2-round cap (feedback_scaffold_as_we_go).
    if artifact_kind in ("brief", "plan") and iteration >= 2:
        return LoopState.SUCCESS

    # W/N fast-exit: if no S or M remain and we have completed at least one
    # fixer round, exit rather than running another full Critic pass.
    if (
        iteration >= 1
        and artifact_kind not in ("brief", "plan")  # brief/plan already have their own cap
        and _sm_counts_zero(severity_counts)
        and not _severity_counts_all_zero(severity_counts)  # there are W/N but no S/M
    ):
        return LoopState.SUCCESS

    if _severity_counts_all_zero(severity_counts):
        return LoopState.SUCCESS
    return LoopState.REVISE


# ─── CI merge-hook helper (brief §5.1 (iii)) ──────────────────────────────────


def check_merge_allowed(
    branch_name: str,
    state_json_path: str | Path,
) -> tuple[bool, int, str]:
    """CI merge-hook gate: deny merge while blocking findings remain open.

    Reads ``adversarial_review_status.blocking_findings_unresolved`` from
    the ``state.json`` at *state_json_path*.

    Returns:
        * ``(True, 200, "")`` if the list is empty or the block is absent.
        * ``(False, 412, reason)`` if at least one blocking finding is open.
        * ``(False, 412, reason)`` if ``state.json`` is unreadable / malformed
          (fail-closed: a broken state file on a branch under adversarial
          review is not merge-eligible).

    *branch_name* is echoed in the ``reason`` string so CI operators can
    grep across multiple PRs; it is not otherwise used for dispatch.
    """

    if not isinstance(branch_name, str) or not branch_name:
        raise ValueError("branch_name must be a non-empty str")

    path = Path(state_json_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            False,
            412,
            f"state.json not found at {path} for branch {branch_name}; "
            f"adversarial-review status cannot be verified (fail-closed)",
        )
    except OSError as exc:
        return (
            False,
            412,
            f"state.json unreadable at {path} for branch {branch_name}: {exc} "
            f"(fail-closed)",
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return (
            False,
            412,
            f"state.json malformed at {path} for branch {branch_name}: {exc} "
            f"(fail-closed)",
        )

    if not isinstance(parsed, dict):
        return (
            False,
            412,
            f"state.json root must be an object at {path} for branch {branch_name}; "
            f"got {type(parsed).__name__} (fail-closed)",
        )

    status_block = parsed.get("adversarial_review_status")
    if status_block is None:
        # No status block means no adversarial review in flight on this branch;
        # merge is permitted (brief §5.1 (iii) gates only when a block exists).
        return (True, 200, "")
    if not isinstance(status_block, dict):
        return (
            False,
            412,
            f"adversarial_review_status must be an object, got "
            f"{type(status_block).__name__} for branch {branch_name}",
        )

    unresolved = status_block.get("blocking_findings_unresolved") or []
    if not isinstance(unresolved, list):
        return (
            False,
            412,
            f"adversarial_review_status.blocking_findings_unresolved must be a list, "
            f"got {type(unresolved).__name__} for branch {branch_name}",
        )
    open_ids = [item for item in unresolved if isinstance(item, str) and item.strip()]
    if open_ids:
        return (
            False,
            412,
            f"branch {branch_name} has {len(open_ids)} blocking finding(s) "
            f"unresolved: {open_ids}",
        )

    return (True, 200, "")


# ─── blocking_findings_unresolved writer (brief §5.1 (iv)) ────────────────────


def update_blocking_findings(
    state_json_path: str | Path,
    finding_ids: list[str],
) -> None:
    """Overwrite ``adversarial_review_status.blocking_findings_unresolved``.

    The input list is validated (each ID must satisfy ``FINDING_ID_RE`` or be
    a namespaced ``<sub_id>-iter-N-<SMWN>N`` form per
    ``feedback_simple_finding_ids``). Unknown or malformed IDs raise
    ``ValueError`` BEFORE any write occurs, so a bad ledger push never
    corrupts ``state.json``.

    Atomicity: the writer reads the full JSON, updates the block, and
    writes via ``pathlib.Path.write_text`` with the ``state.json`` locked
    at a higher level (the caller — typically
    ``gpd.core.state.sync_state_json`` — owns the file lock; brief §state-
    management "dual-write discipline"). This helper does NOT acquire the
    lock itself; it is a pure JSON rewrite over an already-held handle.
    """

    if not isinstance(finding_ids, list):
        raise TypeError(f"finding_ids must be a list, got {type(finding_ids).__name__}")
    validated: list[str] = []
    for item in finding_ids:
        if not isinstance(item, str):
            raise TypeError(
                f"finding_id entries must be str, got {type(item).__name__} for {item!r}"
            )
        stripped = item.strip()
        if not stripped:
            raise ValueError("finding_id entries must be non-empty strings")
        # Accept either the bare `iter-N-<SMWN>N` form OR the namespaced
        # `<sub_id>-iter-N-<SMWN>N` form (feedback_simple_finding_ids).
        # Namespaced form: everything before the last '-iter-' is the sub_id.
        bare_match = FINDING_ID_RE.match(stripped)
        namespaced_match = re.match(r"^.+?-(iter-\d+-[SMWN]\d+)$", stripped)
        if not (bare_match or namespaced_match):
            raise ValueError(
                f"finding_id {stripped!r} does not match "
                f"'^iter-\\d+-[SMWN]\\d+$' or namespaced "
                f"'<sub_id>-iter-N-<SMWN>N' (brief §7.3)"
            )
        validated.append(stripped)

    path = Path(state_json_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        parsed: dict[str, object] = {}
    else:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"state.json at {path} is malformed; refusing to overwrite "
                f"blocking_findings_unresolved: {exc}"
            ) from exc
        if not isinstance(loaded, dict):
            raise ValueError(
                f"state.json root must be an object at {path}; "
                f"got {type(loaded).__name__}"
            )
        parsed = loaded

    status_block = parsed.get("adversarial_review_status")
    if not isinstance(status_block, dict):
        status_block = {}
    status_block["blocking_findings_unresolved"] = validated
    parsed["adversarial_review_status"] = status_block

    path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")


# ─── Parallel multi-aspect critics (speedup B) ────────────────────────────────


def run_parallel_critics(
    kdoc_path: str,
    critic_agent: str,
    source_ref: str | None = None,
) -> list[Finding]:
    """Run equations/conventions/completeness critics in parallel and merge.

    Returns the merged, deduped finding list identical in schema to a single
    critic run so callers need no changes.
    """

    focus_areas = ["equations", "conventions", "completeness"]  # noqa: F841
    # Record the three parallel invocations in the loop state — actual
    # parallelism is handled by the orchestrator (Claude Code spawns sub-agents).
    # This function returns the merged schema so next_loop_state is unchanged.
    # NOTE: real parallel dispatch happens at orchestrator level; this function
    # documents the intended invocation contract and performs the merge.
    raise NotImplementedError(
        "Parallel dispatch is orchestrator-side; this stub documents the contract. "
        "See adversarial_loop_parallel_critics() for the full merge logic."
    )


def _finding_dedup_key(f: Finding) -> tuple[str, str, str]:
    """Compute the ``(kind, location, body_hash)`` three-tuple dedup key.

    Plan 005 §S3: sha256 over the whitespace-normalized FULL
    ``equation_body`` (truncated to 16 hex chars) replaces the pre-S3
    ``equation_body[:60]`` prefix. Empty body → empty hash, which is
    still distinguished from other empty-body findings by ``kind``.
    Pure function; no I/O.
    """

    return (f.kind or "", f.location or "", _body_hash(f.equation_body))


def merge_parallel_findings(
    *finding_lists: list[Finding],
) -> list[Finding]:
    """Merge findings from parallel critics; dedup by ``(kind, location, body_hash)``.

    Plan 005 §S3 redesign. The three-tuple dedup key is
    ``(kind_slug, location, sha256(normalize(equation_body))[:16])``.
    When two findings collide on the same key, ``merge_findings`` runs
    (MAX severity + OR of ``blocking``) so the higher-severity finding
    wins. Findings with different keys are UNIONed.

    The pre-S3 ``(location, equation_body[:60])`` key silently collapsed
    distinct body-less findings into the ``("", "")`` bucket
    (``thin_overview`` + ``missing_physical_picture`` + ``missing_convention``
    all at the doc level). The three-tuple key above always distinguishes
    them because ``kind_slug`` is required for knowledge-critic findings
    (Codex r1 S3).

    Pure function: no I/O, no side effects. Safe to call from any context.
    """

    seen: dict[tuple[str, str, str], Finding] = {}
    for findings in finding_lists:
        for f in findings:
            key = _finding_dedup_key(f)
            if key not in seen:
                seen[key] = f
            else:
                existing = seen[key]
                # Keep highest severity (and OR the blocking flag).
                seen[key] = merge_findings([existing, f])
    return list(seen.values())
