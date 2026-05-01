#!/usr/bin/env python3
"""Project-agnostic canary driver (plan-006 §C3).

Runs the GPD digester skills against a manifest-defined corpus,
attributes per-paper kdocs/assertions via ``gpd_return.files_written``,
and gates on the six §7 structural criteria.

Per plan-006 §C3 + §Acceptance:

* Every run targets a fresh sandbox at
  ``tests/canary/runs/<timestamp>/{knowledge,assertions,reviews}/``
  (resolves iter-1-M3/M4/M6).
* Run-attribution is via the cost-log's ``files_written`` (not a
  filesystem snapshot diff) — resolves iter-1-S5 + iter-2-M3.
* ``--model`` is a REQUIRED flag; the driver aborts at startup if
  missing (resolves iter-1-M1; "force --model" is the documented
  failure-message keyword).
* Per-paper concurrency uses a ``ThreadPoolExecutor`` (default
  ``--parallel 4``); cost-log + budget-tracker writes serialize through
  a single module-level lock — see ``cost_log._LOCK`` (plan-006 §C4;
  imported lazily here so missing C4 doesn't break import).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone as _tz
from pathlib import Path
from typing import Any, Callable

# Allow direct import of sibling canary modules regardless of cwd.
_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))

# Mount ``src/`` so ``gpd.core.commands`` is importable from the
# canary script invoked outside pytest. The pyproject.toml's
# ``pythonpath = ["src"]`` setting only applies under pytest, and
# dispatch_skill.py imports ``gpd.core.commands`` at module load,
# so this insertion must precede any sibling import that pulls
# dispatch_skill into scope.
_PROJECT_ROOT = _CANARY_DIR.parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from budget_tracker import BudgetExceeded, BudgetTracker  # noqa: E402
from cost_log import (  # noqa: E402
    _LOCK as _COST_LOG_LOCK,
    _append_paper_cost_locked,
    append_paper_cost,
    completed_arxiv_ids,
    read_cost_log,
)

# Import the kdoc equation extractor so the canary driver can enumerate
# equations per kdoc and dispatch the assertion skill 1:N (one call per
# equation). Per plan-006 §C12: the assertion phase is 1:N, not 1:1.
from gpd.core.sympy_oracle import extract_equations_from_kdoc  # noqa: E402

# ``cost_log._LOCK`` is the canonical mutex shared by cost-log appends
# and budget-tracker increments (plan-006 §C3 lines 273-291). The
# unused ``threading`` import remains so callers can introspect the
# lock type via ``run_canary._COST_LOG_LOCK`` without re-importing.


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MANIFEST = _CANARY_DIR / "bfss-corpus-manifest.json"
_DEFAULT_TRUTH_TABLE = _CANARY_DIR / "fixtures" / "bfss-typo-axis-truth.json"
_DEFAULT_CRITERIA_MODULE = "tests.canary.criteria_per_project.bfss"

_DEFAULT_PARALLEL = 4
_DEFAULT_PER_PAPER_TIMEOUT_S = 3600
_DEFAULT_MAX_BUDGET_USD_PER_PAPER = 5.0
_DEFAULT_BUDGET_MULTIPLIER = 3.0

_PER_PAPER_TOKEN_ESTIMATE = 1_200_000  # plan-006 §C11

_HEAVY_RUN_BANNER = (
    "[CANARY] HEAVY RUN BANNER — this canary will dispatch live `claude -p`\n"
    "  subprocesses against the corpus. Expected spend: ~$50-80 (Sonnet 4.6\n"
    "  with prompt caching), worst-case CAP: ~$173. Pass --ack-token-budget\n"
    "  to suppress this banner. See plan-006 §C11 for the cost model.\n"
)


# ---------------------------------------------------------------------------
# Sandbox setup (resolves iter-1-M3/M4/M6)
# ---------------------------------------------------------------------------


def make_sandbox(canary_dir: Path, timestamp: str | None = None) -> dict[str, Path]:
    """Create ``runs/<timestamp>/{knowledge,assertions,reviews}/`` sandbox.

    Every live canary run targets a fresh directory tree so the live
    ``GPD/knowledge/`` is never written to.
    """
    if timestamp is None:
        timestamp = datetime.datetime.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
    root = canary_dir / "runs" / timestamp
    paths = {
        "root": root,
        "knowledge": root / "knowledge",
        "assertions": root / "assertions",
        "reviews": root / "reviews",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


# ---------------------------------------------------------------------------
# kdoc-id parsing + assertion error aggregation (plan-006 §C12)
# ---------------------------------------------------------------------------


_FRONTMATTER_KDOC_ID_RE = __import__("re").compile(
    r"(?m)^\s*kdoc_id\s*:\s*([^\s#]+)\s*$"
)


def _parse_kdoc_id_from_frontmatter(kdoc_path: Path) -> str | None:
    """Extract ``kdoc_id`` from the YAML frontmatter of a kdoc.

    Returns the raw scalar value (e.g.
    ``K-003-kazakov-zheng-lattice-ym-bootstrap``) or ``None`` if the
    frontmatter is missing the field.

    The lookup is intentionally lightweight (a single regex) — pulling
    in PyYAML for one scalar is overkill, and the scalar form per the
    canonical template at ``src/gpd/specs/templates/knowledge.md`` is
    plain ASCII (no quotes, no flow-style).
    """
    try:
        text = kdoc_path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_KDOC_ID_RE.search(text)
    if m is None:
        return None
    return m.group(1).strip()


def _aggregate_error_class(
    k_result: dict[str, Any],
    a_results: list[dict[str, Any]],
) -> str:
    """Aggregate per-paper error class across knowledge + assertion phases.

    Plan-006 §C12 silent-failure fix: the pre-amendment aggregator copied
    only ``k_result["error_class"]``, so a paper whose assertion phase
    errored every single equation would still be logged as ``"ok"`` (cost
    log showed ``error_class: ok, n_assertions: 0``). The fixed rule:

    * If knowledge errored, propagate the knowledge ``error_class``.
    * If knowledge ok and zero assertions were attempted, return ``"ok"``
      (extraction may legitimately find 0 equations; coverage parser
      §7.1 surfaces the structural failure separately).
    * If knowledge ok and any assertion errored, return
      ``"assertion_error"`` — a NEW class enumerable by §7 parsers as a
      hard FAIL signal.
    * Otherwise return ``"ok"``.
    """
    k_class = k_result.get("error_class")
    if k_class != "ok":
        return k_class or "skill_error"
    if not a_results:
        # Knowledge ok but no assertions attempted (e.g. extraction found
        # 0 equations). Coverage parser §7.1 will catch this; aggregate
        # is "ok" to avoid double-reporting.
        return "ok"
    bad = [a for a in a_results if a.get("error_class") != "ok"]
    if bad:
        return "assertion_error"
    return "ok"


def _count_assertion_errors(a_results: list[dict[str, Any]]) -> int:
    """Number of assertion dispatches whose ``error_class != "ok"``."""
    return sum(1 for a in a_results if a.get("error_class") != "ok")


# ---------------------------------------------------------------------------
# Per-paper processor (called from ThreadPoolExecutor)
# ---------------------------------------------------------------------------


def _make_process_one_paper(
    *,
    sources_dir: Path,
    knowledge_dir: Path,
    assertion_dir: Path,
    review_dir: Path,
    canary_run_root: Path,
    max_budget_usd: float,
    timeout_s: int,
    model: str,
    dispatch_knowledge_fn: Callable[..., dict[str, Any]] | None = None,
    dispatch_assertion_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[[dict], dict]:
    """Build a closure suitable for ``executor.submit``.

    The dispatch functions are injected so tests can substitute stubs
    without monkey-patching imports.
    """
    if dispatch_knowledge_fn is None or dispatch_assertion_fn is None:
        from dispatch_skill import (  # noqa: E402
            dispatch_digest_assertion,
            dispatch_digest_knowledge,
        )

        dispatch_knowledge_fn = dispatch_knowledge_fn or dispatch_digest_knowledge
        dispatch_assertion_fn = dispatch_assertion_fn or dispatch_digest_assertion

    def process_one_paper(entry: dict) -> dict:
        arxiv_id = entry["arxiv_id"]
        tex_filename = entry.get("tex_filename") or entry.get("pdf_filename")
        tex_path = Path(sources_dir) / tex_filename if tex_filename else None
        per_paper_timeout = int(entry.get("timeout_hint_s") or timeout_s)

        knowledge_result = dispatch_knowledge_fn(
            tex_path,
            knowledge_dir=knowledge_dir,
            assertion_dir=assertion_dir,
            review_dir=review_dir,
            canary_run_root=canary_run_root,
            sources_dir=sources_dir,
            max_budget_usd=max_budget_usd,
            timeout_s=per_paper_timeout,
            model=model,
        )

        new_kdocs = knowledge_result.get("files_written") or []
        assertion_results: list[dict] = []
        new_assertions: list[str] = []

        # Plan-006 §C12 1:N amendment:
        # Assertion semantics are 1:N (one kdoc → N assertions, one per
        # equation), NOT the 1:1 dispatch the pre-amendment loop did.
        # For each kdoc:
        #   1. Parse the frontmatter to extract ``kdoc_id`` (the skill
        #      expects an ID, not a filesystem path).
        #   2. Use ``extract_equations_from_kdoc`` to enumerate equations.
        #   3. Dispatch ``dispatch_digest_assertion(kdoc_id, eq_id, ...)``
        #      sequentially per kdoc (avoid hammering the API with too
        #      many parallel sub-calls — outer ThreadPool is per-paper).
        if knowledge_result.get("error_class") == "ok":
            for kdoc_rel in new_kdocs:
                kdoc_path = Path(kdoc_rel)
                kdoc_id = _parse_kdoc_id_from_frontmatter(kdoc_path)
                if kdoc_id is None:
                    # Missing/unparseable kdoc_id frontmatter: record a
                    # synthesized assertion result so the aggregator
                    # surfaces it as assertion_error (silent-failure fix).
                    assertion_results.append({
                        "error_class": "skill_error",
                        "status": "skill_error",
                        "files_written": [],
                        "cost_usd": 0.0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "duration_ms": 0,
                        "stderr": (
                            f"kdoc_id frontmatter missing in {kdoc_path}"
                        ),
                    })
                    continue
                try:
                    equations = extract_equations_from_kdoc(kdoc_path)
                except OSError as exc:
                    assertion_results.append({
                        "error_class": "skill_error",
                        "status": "skill_error",
                        "files_written": [],
                        "cost_usd": 0.0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "duration_ms": 0,
                        "stderr": (
                            f"failed to read kdoc {kdoc_path} for equation "
                            f"extraction: {exc}"
                        ),
                    })
                    continue
                # 0 equations is legitimate (some kdocs may be prose-only);
                # aggregator treats this as ok per §7.1 coverage handoff.
                for eq_id, _body in equations:
                    a_result = dispatch_assertion_fn(
                        kdoc_id,
                        eq_id,
                        knowledge_dir=knowledge_dir,
                        assertion_dir=assertion_dir,
                        review_dir=review_dir,
                        canary_run_root=canary_run_root,
                        sources_dir=sources_dir,
                        max_budget_usd=max_budget_usd,
                        timeout_s=per_paper_timeout,
                        model=model,
                    )
                    assertion_results.append(a_result)
                    if a_result.get("error_class") == "ok":
                        new_assertions.extend(
                            a_result.get("files_written") or []
                        )

        return {
            "arxiv_id": arxiv_id,
            "knowledge_result": knowledge_result,
            "assertion_results": assertion_results,
            "new_kdocs": new_kdocs,
            "new_assertions": new_assertions,
        }

    return process_one_paper


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Project-agnostic canary driver: runs GPD digester skills "
            "against a manifest-defined corpus and gates on §7 criteria."
        ),
    )
    p.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    p.add_argument("--knowledge-dir", type=Path, default=None)
    p.add_argument("--assertion-dir", type=Path, default=None)
    p.add_argument("--review-dir", type=Path, default=None)
    p.add_argument("--truth-table", type=Path, default=_DEFAULT_TRUTH_TABLE)
    p.add_argument("--criteria-module", type=str, default=_DEFAULT_CRITERIA_MODULE)
    p.add_argument("--parallel", type=int, default=_DEFAULT_PARALLEL)
    p.add_argument(
        "--per-paper-timeout-s", type=int, default=_DEFAULT_PER_PAPER_TIMEOUT_S
    )
    p.add_argument(
        "--max-budget-usd-per-paper",
        type=float,
        default=_DEFAULT_MAX_BUDGET_USD_PER_PAPER,
    )
    p.add_argument(
        "--budget-multiplier", type=float, default=_DEFAULT_BUDGET_MULTIPLIER
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="REQUIRED: claude model to use (e.g. claude-sonnet-4-6).",
    )
    p.add_argument(
        "--ack-token-budget",
        action="store_true",
        help="Acknowledge heavy-run cost banner; raises cap to math.inf "
        "on budget exceedance.",
    )
    p.add_argument(
        "--resume-from-cost-log",
        type=Path,
        default=None,
        help="Drop arxiv_ids whose latest cost-log entry has "
        "error_class == 'ok' before dispatch.",
    )
    p.add_argument(
        "--cost-log",
        type=Path,
        default=None,
        help="Path for the cost-log JSONL written incrementally by the "
        "driver. Default: <sandbox-root>/cost-log.jsonl (live runs only).",
    )
    p.add_argument(
        "--user-override",
        action="append",
        default=[],
        help="Repeatable: <doc-id>:<reason> for §7.5 ack-and-continue.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--non-interactive", action="store_true")
    return p


def _require_model(args: argparse.Namespace) -> None:
    """Abort if --model is missing (resolves iter-1-M1).

    The error message intentionally contains the literal substring
    ``force --model`` so callers can pattern-match for the guard.
    """
    if args.model is None and not args.dry_run:
        print(
            "[CANARY] --model is REQUIRED for live runs (force --model "
            "<name>); aborting.",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------


def _load_completed_arxiv_ids(cost_log_path: Path | None) -> set[str]:
    """Read the cost log and return arxiv_ids whose latest entry is ok.

    Delegates to :func:`cost_log.completed_arxiv_ids` (plan-006 §C4)
    so the latest-by-completed_at + last-line-tie-breaker rule lives
    in exactly one place. The C3 deviation #2 fallback minimal JSONL
    parse has been removed now that the C4 module is solid.
    """
    if cost_log_path is None:
        return set()
    try:
        return completed_arxiv_ids(read_cost_log(cost_log_path))
    except (OSError, json.JSONDecodeError):
        return set()


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    parser = build_parser()
    args = parser.parse_args(argv)
    _require_model(args)

    # Heavy-run banner unless ack'd.
    if not args.dry_run and not args.ack_token_budget:
        print(_HEAVY_RUN_BANNER, file=sys.stderr)

    # Load manifest.
    if not args.manifest.exists():
        print(f"[CANARY] manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries: list[dict] = manifest.get("entries", [])
    sources_dir = Path(manifest.get("references_dir", _CANARY_DIR))

    # Resume drop.
    completed = _load_completed_arxiv_ids(args.resume_from_cost_log)
    if completed:
        before = len(entries)
        entries = [e for e in entries if e["arxiv_id"] not in completed]
        print(
            f"[CANARY] --resume-from-cost-log dropped "
            f"{before - len(entries)}/{before} already-ok entries.",
            file=sys.stderr,
        )

    if args.dry_run:
        print(
            f"[CANARY] --dry-run: skipping dispatch for "
            f"{len(entries)} entries.",
            file=sys.stderr,
        )
        return 0

    # Sandbox setup (only for live runs).
    sandbox = make_sandbox(_CANARY_DIR)
    knowledge_dir = args.knowledge_dir or sandbox["knowledge"]
    assertion_dir = args.assertion_dir or sandbox["assertions"]
    review_dir = args.review_dir or sandbox["reviews"]
    canary_run_root = sandbox["root"]

    cost_log_path = args.cost_log or (canary_run_root / "cost-log.jsonl")

    print(
        f"[CANARY] sandbox: {canary_run_root}  "
        f"(knowledge={knowledge_dir.name}, "
        f"assertions={assertion_dir.name}, reviews={review_dir.name})"
    )
    print(f"[CANARY] cost-log: {cost_log_path}")

    process_one_paper = _make_process_one_paper(
        sources_dir=sources_dir,
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        review_dir=review_dir,
        canary_run_root=canary_run_root,
        max_budget_usd=args.max_budget_usd_per_paper,
        timeout_s=args.per_paper_timeout_s,
        model=args.model,
    )

    # Budget tracker (token-based, per C11).
    total_estimate = _PER_PAPER_TOKEN_ESTIMATE * max(len(entries), 1)
    tracker = BudgetTracker(
        estimate_tokens=total_estimate, multiplier=args.budget_multiplier
    )

    outcomes: list[dict] = []
    cancel_reason: str | None = None
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futures = {ex.submit(process_one_paper, e): e for e in entries}
        try:
            for fut in as_completed(futures):
                outcome = fut.result()
                outcomes.append(outcome)
                k_result = outcome["knowledge_result"]

                # Defense-in-depth M3 post-condition: ok dispatch with
                # empty files_written ⇒ FAIL with diagnostic.
                if (
                    k_result.get("error_class") == "ok"
                    and not outcome.get("new_kdocs")
                ):
                    print(
                        f"[CANARY] FAIL: dispatcher returned ok with empty "
                        f"files_written for {outcome['arxiv_id']} — likely "
                        "gpd_return-block parse bug (see iter-2-S1), NOT a "
                        "green canary.",
                        file=sys.stderr,
                    )
                    cancel_reason = "empty_files_written_with_ok_dispatch"
                    ex.shutdown(wait=False, cancel_futures=True)
                    return 1

                # Cost-log + budget tracker write under the shared
                # lock (plan-006 §C3 lines 273-291). The append below
                # already takes ``cost_log._LOCK`` internally; we hold
                # it here for the wider critical section so the budget
                # bump and the cost-log line land as one atomic step.
                tokens = (
                    int(k_result.get("input_tokens") or 0)
                    + int(k_result.get("output_tokens") or 0)
                    + sum(
                        int(a.get("input_tokens") or 0)
                        + int(a.get("output_tokens") or 0)
                        for a in outcome.get("assertion_results") or []
                    )
                )
                cost_usd = float(k_result.get("cost_usd") or 0.0) + sum(
                    float(a.get("cost_usd") or 0.0)
                    for a in outcome.get("assertion_results") or []
                )
                duration_ms = int(k_result.get("duration_ms") or 0) + sum(
                    int(a.get("duration_ms") or 0)
                    for a in outcome.get("assertion_results") or []
                )
                completed_at = datetime.datetime.now(_tz.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                # Plan-006 §C12 silent-failure fix: previously the
                # aggregator copied only ``k_result["error_class"]``,
                # masking every per-equation assertion failure as
                # ``"ok"``. ``_aggregate_error_class`` returns
                # ``"assertion_error"`` (a NEW class) when knowledge ok
                # but any assertion errored.
                a_results_list = outcome.get("assertion_results") or []
                agg_error_class = _aggregate_error_class(
                    k_result, a_results_list
                )
                aggregate = {
                    "error_class": agg_error_class,
                    "cost_usd": cost_usd,
                    "input_tokens": int(k_result.get("input_tokens") or 0)
                    + sum(
                        int(a.get("input_tokens") or 0)
                        for a in a_results_list
                    ),
                    "output_tokens": int(k_result.get("output_tokens") or 0)
                    + sum(
                        int(a.get("output_tokens") or 0)
                        for a in a_results_list
                    ),
                    "duration_ms": duration_ms,
                    "completed_at": completed_at,
                    "claude_session_id": k_result.get("session_id"),
                    "n_assertions": len(outcome.get("new_assertions") or []),
                    "n_assertion_errors": _count_assertion_errors(
                        a_results_list
                    ),
                    "assertion_paths": outcome.get("new_assertions") or [],
                }
                with _COST_LOG_LOCK:
                    # Single critical section: cost-log append + budget
                    # bump observed atomically. We call the
                    # ``_locked`` variant here because the public
                    # ``append_paper_cost`` would re-acquire the
                    # non-reentrant ``threading.Lock`` and deadlock.
                    _append_paper_cost_locked(
                        outcome["arxiv_id"],
                        outcome.get("new_kdocs") or [],
                        aggregate,
                        log_path=cost_log_path,
                    )
                    try:
                        tracker.record(tokens or _PER_PAPER_TOKEN_ESTIMATE)
                    except BudgetExceeded as exc:
                        if args.ack_token_budget:
                            tracker.cap = float("inf")
                            print(
                                f"[CANARY] --ack-token-budget: raising cap "
                                f"to math.inf after {exc}",
                                file=sys.stderr,
                            )
                        else:
                            cancel_reason = f"BudgetExceeded: {exc}"
                            ex.shutdown(wait=False, cancel_futures=True)
                            print(
                                f"[CANARY] {cancel_reason}", file=sys.stderr
                            )
                            return 1
        except KeyboardInterrupt:
            ex.shutdown(wait=False, cancel_futures=True)
            print("[CANARY] interrupted by user.", file=sys.stderr)
            return 1

    print(
        f"[CANARY] completed {len(outcomes)} entries; "
        f"sandbox={canary_run_root}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
