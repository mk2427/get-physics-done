"""§7.4 No-hallucination parser for the BFSS canary (plan-006 §C8).

Zero-tolerance criterion: every assertion in the produced corpus must
either (a) carry a ``upstream_ref_hash`` that re-verifies against the
canonical hash of the cited kdoc equation, or (b) be a derived-
consequence whose every cited parent (kdoc + upstream-mirror + canonical
[K-NNN:K.X] / [E.N] tokens in the ``derivation_sketch``) actually exists
in the produced corpus. Any mismatch / dangling reference is a FAIL.

Per plan-006 §C8 (post-iter-1-S2 + iter-1-S3 fixes):

* Hashing is delegated to
  :func:`gpd.core.assertion_divergence.compute_upstream_ref_hash`, which
  internally calls :func:`gpd.core.eqn_normalize.normalize_eqn_body` --
  the canonical 4-stage pipeline (whitespace strip → macro
  canonicalization → font-wrapper lowering → fraction canonicalization).
  This is the single source of truth for canonical-equation hashing.

* The parser does NOT call ``core/sympy_oracle._normalize_body`` (no
  such function) or ``core/adversarial_loop._normalize_body`` (weaker
  whitespace+NFC pipeline -- mixing it with the canonical pipeline
  yields mass mismatch on every restated equation).

* Cited-kdoc lookup uses the assertion's frontmatter
  ``knowledge_doc_ids: [K-NNN, ...]`` list (canonical, per
  ``src/gpd/specs/templates/assertion.md``) and, for restated-equation
  assertions, the ``upstream_status_mirror.kdoc_id`` field. The
  assertion frontmatter has NO ``cluster:`` field; that field exists
  only on knowledge docs.

Entry point: :func:`check`. Signature matches the package's
``CriterionResult check(produced_files, knowledge_dir, assertion_dir,
truth_table=None)`` contract; ``truth_table`` is unused here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

import yaml

# Allow ``import criteria`` (package) and ``from gpd.core.assertion_divergence
# import compute_upstream_ref_hash`` to resolve when this module is
# imported either as ``tests.canary.criteria.no_hallucination`` or via the
# canary driver's ``--criteria-module`` plug-in path. The canary tree
# does not import the GPD package by default; the project layout puts
# it under ``src/gpd/`` and the test runner's ``pyproject.toml`` already
# configures ``pythonpath = ["src"]``.
from gpd.core.assertion_divergence import compute_upstream_ref_hash  # noqa: E402
from gpd.core.sympy_oracle import extract_equations_from_kdoc  # noqa: E402

_CANARY_PKG = Path(__file__).resolve().parent.parent
if str(_CANARY_PKG) not in sys.path:
    sys.path.insert(0, str(_CANARY_PKG))

from criteria import CriterionResult, CriterionStatus  # noqa: E402

__all__ = ["check"]


# ---------------------------------------------------------------------------
# Frontmatter + body helpers (shared style with assertion_divergence._parse_*)
# ---------------------------------------------------------------------------

# Matches canonical [K-NNN:K.X] equation citations in the derivation_sketch
# (and anywhere else in the body). Equation-ref entries use the [E.N] form.
_KDOC_EQ_REF_RE = re.compile(r"\[(K-\d+):(K\.\d+)\]")
_EQN_REF_RE = re.compile(r"\[(E\.\d+)\]")


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown file; ``{}`` if absent.

    Mirrors the implementation in ``gpd.core.assertion_divergence`` so the
    parser's frontmatter view stays identical to the divergence-check's.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}
    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    raw = "".join(fm_lines)
    parsed = yaml.safe_load(raw) if raw.strip() else {}
    return parsed if isinstance(parsed, dict) else {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _filter_to_dir(files: Iterable[Path], directory: Path) -> list[Path]:
    """Return the subset of ``files`` that live under ``directory``.

    Both sides are resolved before comparison so symlinks and relative
    inputs land on the same canonical form. A ``ValueError`` from
    ``relative_to`` is silently treated as "outside the directory".
    """
    out: list[Path] = []
    if not directory.exists():
        return out
    dir_resolved = directory.resolve()
    for f in files:
        try:
            rp = f.resolve()
        except OSError:
            continue
        try:
            rp.relative_to(dir_resolved)
        except ValueError:
            continue
        if rp.is_file():
            out.append(rp)
    return out


def _kdoc_id_from_path(path: Path) -> str | None:
    """Best-effort kdoc-id extraction from frontmatter; falls back to filename."""
    try:
        text = _read_text(path)
    except OSError:
        return None
    fm = _parse_frontmatter(text)
    kid = fm.get("kdoc_id") or fm.get("knowledge_doc_id")
    if isinstance(kid, str) and kid:
        return kid
    # Fallback: filename pattern K-NNN-slug.md.
    name = path.name
    m = re.match(r"(K-\d+)\b", name)
    return m.group(1) if m else None


def _build_kdoc_index(
    kdoc_paths: Iterable[Path],
) -> tuple[dict[str, Path], dict[str, dict[str, str]]]:
    """Walk produced kdocs; index by kdoc_id and build an equation map.

    Returns ``(by_id, eq_by_id)`` where:

    * ``by_id[K-NNN] = Path`` (the kdoc on disk).
    * ``eq_by_id[K-NNN][K.X] = canonical_latex`` (the equation body
      verbatim from the kdoc, ready for hashing).
    """
    by_id: dict[str, Path] = {}
    eq_by_id: dict[str, dict[str, str]] = {}
    for path in kdoc_paths:
        kid = _kdoc_id_from_path(path)
        if not kid:
            continue
        by_id[kid] = path
        eq_map: dict[str, str] = {}
        try:
            for eq_id, eq_body in extract_equations_from_kdoc(path):
                # First occurrence wins; matches extract_equations_from_kdoc's
                # own de-duplication contract.
                eq_map.setdefault(eq_id, eq_body)
        except Exception:  # pragma: no cover - defensive on malformed kdocs
            pass
        eq_by_id[kid] = eq_map
    return by_id, eq_by_id


# ---------------------------------------------------------------------------
# Per-assertion check.
# ---------------------------------------------------------------------------


def _cited_kdoc_ids(fm: dict) -> list[str]:
    """Canonical cited-kdoc list per the assertion template.

    Order:
      1. ``knowledge_doc_ids`` (canonical list, per assertion template).
      2. ``upstream_status_mirror.kdoc_id`` (primary parent for restated-
         equation assertions; appended only if not already present).

    The assertion frontmatter has NO ``cluster:`` field (that field is
    on kdocs only); we explicitly do NOT look for it.
    """
    out: list[str] = []
    raw = fm.get("knowledge_doc_ids")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item and item not in out:
                out.append(item)
    mirror = fm.get("upstream_status_mirror")
    if isinstance(mirror, dict):
        primary = mirror.get("kdoc_id")
        if isinstance(primary, str) and primary and primary not in out:
            out.append(primary)
    return out


def _check_one_assertion(
    assertion_path: Path,
    *,
    kdocs_by_id: dict[str, Path],
    eq_by_id: dict[str, dict[str, str]],
) -> list[str]:
    """Return a list of failure messages for ``assertion_path``.

    Empty list ⇒ assertion is hallucination-free.
    """
    errors: list[str] = []
    try:
        text = _read_text(assertion_path)
    except OSError as exc:
        return [f"{assertion_path.name}: cannot read ({exc})"]
    fm = _parse_frontmatter(text)

    aid: str = fm.get("assertion_id") or assertion_path.name
    kind: str = fm.get("kind") or ""
    stored_hash = fm.get("upstream_ref_hash")
    cited_ids = _cited_kdoc_ids(fm)

    # ----- restated-equation hash check ---------------------------------
    if isinstance(stored_hash, str) and stored_hash:
        # Need to find some kdoc/eq pair whose canonical hash matches.
        verified = False
        candidate_kdocs: list[str] = []
        for kid in cited_ids:
            if kid not in kdocs_by_id:
                continue
            candidate_kdocs.append(kid)
            for _eq_id, body in eq_by_id.get(kid, {}).items():
                if compute_upstream_ref_hash(body) == stored_hash:
                    verified = True
                    break
            if verified:
                break
        if not cited_ids:
            errors.append(
                f"{aid}: upstream_ref_hash present but no knowledge_doc_ids cited "
                "(cannot resolve kdoc to recompute hash)"
            )
        elif not candidate_kdocs:
            errors.append(
                f"{aid}: upstream_ref_hash present but cited kdocs "
                f"{cited_ids} not in produced corpus (dangling parent)"
            )
        elif not verified:
            errors.append(
                f"{aid}: upstream_ref_hash {stored_hash[:16]}... does not match "
                f"any equation in cited kdocs {candidate_kdocs} "
                "(hallucinated restatement)"
            )

    # ----- derived-consequence dangling-parent check --------------------
    # Applied to every assertion (a restated-equation may also reference
    # parents in the derivation_sketch; we still want zero dangling
    # references). For the canonical derived-consequence path the
    # derivation_sketch is non-empty; for restated equations it is
    # typically null/empty and the loop below is a no-op.
    sketch = fm.get("derivation_sketch") or ""
    if not isinstance(sketch, str):
        sketch = ""
    # Also scan the body's "## Derivation Sketch" / body-wide canonical
    # citation tokens; the template allows the sketch to live in the
    # body rather than the frontmatter. We scan the entire body to be
    # safe (canonical citations only appear in derivation contexts).
    body_after_fm = text
    if text.startswith("---"):
        # Drop the frontmatter block before scanning body citations so a
        # frontmatter-embedded YAML string with literal "[K-001:K.1]"
        # text can't double-count.
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body_after_fm = parts[2]
    scan_text = sketch + "\n" + body_after_fm

    cited_kdoc_eqs: set[tuple[str, str]] = {
        (m.group(1), m.group(2)) for m in _KDOC_EQ_REF_RE.finditer(scan_text)
    }
    for kid, eq_id in cited_kdoc_eqs:
        if kid not in kdocs_by_id:
            errors.append(
                f"{aid}: derivation_sketch cites [{kid}:{eq_id}] but kdoc "
                f"{kid} not in produced corpus (dangling parent)"
            )
            continue
        if eq_id not in eq_by_id.get(kid, {}):
            errors.append(
                f"{aid}: derivation_sketch cites [{kid}:{eq_id}] but equation "
                f"{eq_id} not found in {kid} (dangling parent)"
            )

    # The assertion's declared kdoc parents must also exist in the
    # produced corpus -- a knowledge_doc_ids entry that points outside
    # the sandbox is a dangling-parent FAIL even if no upstream_ref_hash
    # is set. (Catches the case where the digester invents a K-NNN that
    # was never written.)
    for kid in cited_ids:
        if kid not in kdocs_by_id:
            errors.append(
                f"{aid}: knowledge_doc_ids cites {kid} but kdoc not in "
                "produced corpus (dangling parent)"
            )

    # Sanity: a restated-equation with a missing/empty hash is a template
    # violation and would also be flagged by gpd-knowledge-critic. Surface
    # it here as a hallucination-adjacent issue (no source pointer ⇒
    # cannot rule out hallucination).
    if kind == "restated-equation" and not (
        isinstance(stored_hash, str) and stored_hash
    ):
        errors.append(
            f"{aid}: kind=restated-equation but upstream_ref_hash is empty/null "
            "(no source pointer; cannot verify against any kdoc equation)"
        )

    return errors


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def check(
    produced_files: Iterable[Path],
    knowledge_dir: Path,
    assertion_dir: Path,
    truth_table: dict | None = None,
) -> CriterionResult:
    """§7.4 no-hallucination parser. Zero-tolerance gate.

    Walks every assertion in ``produced_files ∩ assertion_dir``;
    reverifies each ``upstream_ref_hash`` against the canonical hash of
    the cited kdoc equation, and flags any dangling ``[K-NNN:K.X]``
    parent in the derivation sketch / body. Any mismatch ⇒ FAIL.

    Args:
        produced_files: Iterable of file paths produced this canary run
            (cost-log-derived ok set, per the C9 run-attribution rule).
        knowledge_dir:  Sandbox knowledge directory; only kdocs whose
            paths fall under this directory are loaded into the hash
            index.
        assertion_dir:  Sandbox assertion directory; assertions outside
            this directory are ignored (not under our purview).
        truth_table:    Unused for this criterion (passed through by the
            canary driver for uniformity with C7).

    Returns:
        :class:`CriterionResult` with status ``PASS`` (every assertion
        verified, no dangling parents) or ``FAIL`` (one or more
        hallucinations / dangling refs; details listed verbatim).
    """
    del truth_table  # reserved; canary driver passes a uniform signature.

    produced_list = list(produced_files)
    kdoc_paths = _filter_to_dir(produced_list, knowledge_dir)
    assertion_paths = _filter_to_dir(produced_list, assertion_dir)

    kdocs_by_id, eq_by_id = _build_kdoc_index(kdoc_paths)

    if not assertion_paths:
        # Empty assertion set is treated as PASS (vacuously true; the
        # canary's coverage criterion C5 is the gate that fails an
        # empty corpus). The summary makes the no-op explicit.
        return CriterionResult(
            name="No-hallucination",
            status=CriterionStatus.PASS,
            summary="0 assertions in produced corpus (vacuous PASS)",
            details=[],
            payload={"n_assertions": 0, "n_kdocs": len(kdocs_by_id)},
        )

    all_errors: list[str] = []
    n_assertions_checked = 0
    for ap in sorted(assertion_paths):
        n_assertions_checked += 1
        all_errors.extend(
            _check_one_assertion(
                ap,
                kdocs_by_id=kdocs_by_id,
                eq_by_id=eq_by_id,
            )
        )

    if all_errors:
        return CriterionResult(
            name="No-hallucination",
            status=CriterionStatus.FAIL,
            summary=(
                f"{len(all_errors)} hallucination/dangling-ref issue(s) across "
                f"{n_assertions_checked} assertion(s)"
            ),
            details=all_errors,
            payload={
                "n_assertions": n_assertions_checked,
                "n_kdocs": len(kdocs_by_id),
                "n_issues": len(all_errors),
            },
        )

    return CriterionResult(
        name="No-hallucination",
        status=CriterionStatus.PASS,
        summary=(
            f"{n_assertions_checked} assertion(s) verified; "
            f"0 hallucinations, 0 dangling parents"
        ),
        details=[],
        payload={
            "n_assertions": n_assertions_checked,
            "n_kdocs": len(kdocs_by_id),
            "n_issues": 0,
        },
    )
