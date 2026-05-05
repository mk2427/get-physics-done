#!/usr/bin/env python3
"""Project-agnostic canary driver (plan-006 §C3).

Runs the GPD digester skills against a manifest-defined corpus,
attributes per-paper kdocs/assertions via schema-v2 cost-log entries,
and gates on the six §7 structural criteria.

Per plan-006 §C3 + §Acceptance:

* Every run targets a fresh sandbox at
  ``tests/canary/runs/<timestamp>/{knowledge,assertions,reviews}/``
  (resolves iter-1-M3/M4/M6).
* Run-attribution is via the cost-log's typed output fields (not a
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
import hashlib
import importlib
import json
import os
import re
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
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_SRC_DIR = _PROJECT_ROOT / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from budget_tracker import BudgetExceeded, BudgetTracker  # noqa: E402
from assertion_id_pool import AssertionIdPool  # noqa: E402
from canary_report import status_from_results, write_canary_report  # noqa: E402
from cost_log import (  # noqa: E402
    _LOCK as _COST_LOG_LOCK,
    _append_paper_cost_locked,
    append_paper_cost,
    completed_arxiv_ids,
    produced_files_from_entries,
    read_cost_log,
    read_entries,
    run_failures_from_entries,
)
from criteria import CriterionResult, CriterionStatus  # noqa: E402
from criteria_per_project import Criterion7Inputs  # noqa: E402

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
_REFERENCES_DIR_ENV = "GPD_BFSS_REFERENCES_DIR"

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
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
_FRONTMATTER_SCALAR_RE = re.compile(r"(?m)^\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$")


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


def _parse_frontmatter_scalars(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    match = _FRONTMATTER_RE.search(text)
    if match is None:
        return {}
    out: dict[str, str] = {}
    for key, value in _FRONTMATTER_SCALAR_RE.findall(match.group(1)):
        value = value.strip().strip('"').strip("'")
        if value and not value.startswith("[") and not value.startswith("{"):
            out[key] = value
    return out


def _sha256_file(path: Path | None, *, canonical_text: bool = False) -> str | None:
    if path is None or not path.is_file():
        return None
    data = path.read_bytes()
    if canonical_text:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _expected_source_hash(entry: dict[str, Any]) -> str | None:
    source_hash = entry.get("source_path_sha256")
    if isinstance(source_hash, str) and source_hash:
        return source_hash
    tex_hash = entry.get("tex_sha256")
    if isinstance(tex_hash, str) and tex_hash:
        return tex_hash
    pdf_hash = entry.get("sha256")
    if isinstance(pdf_hash, str) and pdf_hash:
        return pdf_hash
    return None


def _resolve_sources_dir(manifest: dict[str, Any]) -> Path:
    override = os.environ.get(_REFERENCES_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path(manifest.get("references_dir", _CANARY_DIR))


def _validate_kdoc_ownership(kdoc_path: Path, entry: dict) -> str | None:
    meta = _parse_frontmatter_scalars(kdoc_path)
    expected_arxiv = str(entry.get("arxiv_id") or "")
    source_arxiv = meta.get("source_arxiv_id")
    if not source_arxiv:
        return f"source_arxiv_id frontmatter missing in {kdoc_path}"
    if expected_arxiv and source_arxiv != expected_arxiv:
        return (
            f"source_arxiv_id mismatch in {kdoc_path}: "
            f"expected {expected_arxiv}, got {source_arxiv}"
        )
    expected_filename = entry.get("tex_filename") or entry.get("pdf_filename")
    source_filename = meta.get("source_filename")
    if expected_filename:
        if not source_filename:
            return f"source_filename frontmatter missing in {kdoc_path}"
        expected_filename_norm = str(expected_filename).replace("\\", "/")
        source_filename_norm = str(source_filename).replace("\\", "/")
        if source_filename_norm != expected_filename_norm:
            return (
                f"source_filename mismatch in {kdoc_path}: "
                f"expected {expected_filename_norm}, got {source_filename_norm}"
            )
    expected_hash = _expected_source_hash(entry)
    source_hash = meta.get("source_path_sha256")
    if expected_hash and not source_hash:
        return f"source_path_sha256 frontmatter missing in {kdoc_path}"
    if source_hash and expected_hash and source_hash != expected_hash:
        return (
            f"source_path_sha256 mismatch in {kdoc_path}: "
            f"expected {expected_hash}, got {source_hash}"
        )
    return None


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
    assertion_id_pool: AssertionIdPool | None = None,
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
        manifest_source_hash = _expected_source_hash(entry)
        actual_source_hash = _sha256_file(
            tex_path,
            canonical_text=bool(tex_path and tex_path.suffix.lower() == ".tex"),
        )
        if (
            manifest_source_hash
            and actual_source_hash
            and manifest_source_hash != actual_source_hash
        ):
            return {
                "arxiv_id": arxiv_id,
                "knowledge_result": {
                    "error_class": "skill_error",
                    "status": "skill_error",
                    "stderr": (
                        "source hash mismatch before dispatch: "
                        f"manifest expected {manifest_source_hash}, "
                        f"actual LF-normalized source is {actual_source_hash}"
                    ),
                    "kdoc_paths": [],
                    "assertion_paths": [],
                    "review_paths": [],
                },
                "assertion_results": [],
                "new_kdocs": [],
                "new_assertions": [],
                "review_paths": [],
            }
        source_hash = actual_source_hash or manifest_source_hash
        ownership_entry = dict(entry)
        if source_hash:
            ownership_entry["source_path_sha256"] = source_hash

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
            arxiv_id=arxiv_id,
            source_filename=tex_filename,
            source_path_sha256=source_hash,
        )

        new_kdocs = knowledge_result.get("kdoc_paths") or []
        assertion_results: list[dict] = []
        new_assertions: list[str] = []
        review_paths: list[str] = list(knowledge_result.get("review_paths") or [])

        if knowledge_result.get("assertion_paths"):
            assertion_results.append({
                "error_class": "skill_error",
                "status": "skill_error",
                "assertion_paths": [],
                "stderr": "knowledge dispatch returned assertion_paths",
            })

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
                ownership_error = _validate_kdoc_ownership(kdoc_path, ownership_entry)
                if ownership_error:
                    assertion_results.append({
                        "error_class": "skill_error",
                        "status": "skill_error",
                        "assertion_paths": [],
                        "stderr": ownership_error,
                    })
                    continue
                kdoc_id = _parse_kdoc_id_from_frontmatter(kdoc_path)
                if kdoc_id is None:
                    # Missing/unparseable kdoc_id frontmatter: record a
                    # synthesized assertion result so the aggregator
                    # surfaces it as assertion_error (silent-failure fix).
                    assertion_results.append({
                        "error_class": "skill_error",
                        "status": "skill_error",
                        "assertion_paths": [],
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
                        "assertion_paths": [],
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
                    dispatch_id = None
                    assertion_id = None
                    if assertion_id_pool is not None:
                        dispatch_id = (
                            f"assertion-{arxiv_id}-{eq_id}".replace("/", "-")
                        )
                        reservation = assertion_id_pool.reserve(
                            dispatch_id=dispatch_id,
                            output_assertion_dir=assertion_dir,
                        )
                        assertion_id = reservation.reserved_id
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
                        assertion_id=assertion_id,
                        dispatch_id=dispatch_id,
                        arxiv_id=arxiv_id,
                    )
                    assertion_results.append(a_result)
                    review_paths.extend(a_result.get("review_paths") or [])
                    if a_result.get("error_class") == "ok":
                        new_assertions.extend(
                            a_result.get("assertion_paths") or []
                        )

        return {
            "arxiv_id": arxiv_id,
            "knowledge_result": knowledge_result,
            "assertion_results": assertion_results,
            "new_kdocs": new_kdocs,
            "new_assertions": new_assertions,
            "review_paths": review_paths,
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


def _parse_user_overrides(raw: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw or []:
        if ":" in item:
            key, value = item.split(":", 1)
            out[key.strip()] = value.strip()
        else:
            out[item.strip()] = ""
    return out


def _blocked_result(name: str, reason: str) -> CriterionResult:
    return CriterionResult(
        name=name,
        status=CriterionStatus.ERROR,
        summary=f"BLOCKED: {reason}",
        details=[reason],
    )


def run_criteria(
    *,
    produced_files: list[Path],
    knowledge_dir: Path,
    assertion_dir: Path,
    truth_table_path: Path,
    criteria_module: str,
    user_overrides: list[str] | None,
    n_ok_dispatches: int,
    blocked: bool = False,
) -> list[CriterionResult]:
    """Invoke all six criteria once, or mark them blocked after dispatch failure."""
    names = [
        "Coverage",
        "Consequence closure",
        "BFSS Typo+Axis Recovery",
        "No-hallucination",
        "Adversarial convergence",
        "Traceability",
    ]
    if blocked:
        return [_blocked_result(name, "no produced files due to dispatch failure") for name in names]

    truth_table = None
    if truth_table_path and Path(truth_table_path).exists():
        truth_table = json.loads(Path(truth_table_path).read_text(encoding="utf-8"))

    from criteria import coverage, consequence_closure, no_hallucination, traceability
    from criteria import adversarial_convergence

    results = [
        coverage.check(produced_files, knowledge_dir, assertion_dir, truth_table),
        consequence_closure.check(produced_files, knowledge_dir, assertion_dir, truth_table),
    ]

    project_module = importlib.import_module(criteria_module)
    criterion_cls = getattr(project_module, "BFSSCriterion7")
    results.append(
        criterion_cls().check(
            Criterion7Inputs(
                produced_files=produced_files,
                knowledge_dir=knowledge_dir,
                assertion_dir=assertion_dir,
                truth_table=truth_table or {},
            )
        )
    )
    results.extend([
        no_hallucination.check(produced_files, knowledge_dir, assertion_dir, truth_table),
        adversarial_convergence.check(
            produced_files,
            knowledge_dir,
            assertion_dir,
            truth_table,
            user_overrides=user_overrides,
            n_ok_dispatches=n_ok_dispatches,
        ),
        traceability.check(produced_files, knowledge_dir, assertion_dir, truth_table),
    ])
    return results


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
    sources_dir = _resolve_sources_dir(manifest)

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
        assertion_id_pool=AssertionIdPool(_PROJECT_ROOT / "GPD" / "assertions"),
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
                entry = futures[fut]
                try:
                    outcome = fut.result()
                except Exception as exc:
                    arxiv_id = str(entry.get("arxiv_id") or "unknown")
                    outcome = {
                        "arxiv_id": arxiv_id,
                        "knowledge_result": {
                            "error_class": "subprocess_error",
                            "status": "subprocess_error",
                            "stderr": f"worker exception for {arxiv_id}: {exc}",
                            "kdoc_paths": [],
                            "assertion_paths": [],
                            "review_paths": [],
                        },
                        "assertion_results": [],
                        "new_kdocs": [],
                        "new_assertions": [],
                        "review_paths": [],
                    }
                outcomes.append(outcome)
                k_result = outcome["knowledge_result"]

                # Defense-in-depth M3 post-condition: ok dispatch with
                # empty produced files => FAIL with diagnostic.
                if (
                    k_result.get("error_class") == "ok"
                    and not outcome.get("new_kdocs")
                ):
                    print(
                        f"[CANARY] FAIL: dispatcher returned ok with empty "
                        f"produced files for {outcome['arxiv_id']} — likely "
                        "gpd_return-block parse bug (see iter-2-S1), NOT a "
                        "green canary.",
                        file=sys.stderr,
                    )
                    cancel_reason = "empty_produced_files_with_ok_dispatch"
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
                failure_details = []
                if k_result.get("error_class") != "ok" and k_result.get("stderr"):
                    failure_details.append(str(k_result.get("stderr"))[-2000:])
                for a_result in a_results_list:
                    if (
                        a_result.get("error_class") != "ok"
                        and a_result.get("stderr")
                    ):
                        failure_details.append(str(a_result.get("stderr"))[-2000:])
                kdoc_statuses = {}
                for raw_path in outcome.get("new_kdocs") or []:
                    kdoc_path = Path(raw_path)
                    meta = _parse_frontmatter_scalars(kdoc_path)
                    kdoc_statuses[
                        meta.get("kdoc_id") or kdoc_path.stem
                    ] = meta.get("status") or "unknown"
                aggregate = {
                    "error_class": agg_error_class,
                    "dispatch_ids": [
                        x
                        for x in [
                            k_result.get("dispatch_id"),
                            *[
                                a.get("dispatch_id")
                                for a in a_results_list
                                if a.get("dispatch_id")
                            ],
                        ]
                        if x
                    ],
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
                    "review_paths": outcome.get("review_paths") or [],
                    "kdoc_statuses": kdoc_statuses,
                    "failure_details": failure_details,
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
                        knowledge_root=knowledge_dir,
                        assertion_root=assertion_dir,
                        review_root=review_dir,
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
    entries_v2 = read_entries(cost_log_path)
    produced_files = produced_files_from_entries(entries_v2, ok_only=True)
    run_failures = run_failures_from_entries(entries_v2)
    criteria_results = run_criteria(
        produced_files=produced_files,
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        truth_table_path=args.truth_table,
        criteria_module=args.criteria_module,
        user_overrides=args.user_override,
        n_ok_dispatches=sum(1 for e in entries_v2 if e.get("error_class") == "ok"),
        blocked=not produced_files and bool(run_failures),
    )
    exit_code = status_from_results(criteria_results, run_failures)
    write_canary_report(
        report_path=canary_run_root / "canary-report.md",
        criteria_results=criteria_results,
        run_failures=run_failures,
        metadata={
            "run_root": str(canary_run_root),
            "cost_log": str(cost_log_path),
            "produced_files": len(produced_files),
            "exit_code": exit_code,
        },
        user_overrides=_parse_user_overrides(args.user_override),
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
