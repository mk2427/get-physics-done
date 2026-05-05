"""§7.2 Consequence-closure parser (plan-006 §C6).

Per brief 002 §7.2: every derivation stated in the source corpus (e.g.,
``E.45 ∧ E.50 ⇒ ⟨tr X²⟩ ≥ 0.2936``) MUST emerge as a derived-consequence
assertion doc whose ``derivation_sketch`` cites both parent knowledge/
assertion docs via the canonical citation syntax. **Sampling is not
acceptable** — every derivation must close.

Canonical citation syntax (resolves plan-006 iter-1-W3):

* Kdoc equation reference: ``[K-NNN:K.X]``
* EQN-REF entry reference: ``[E.N]``

The parser walks the produced kdoc corpus, scans each kdoc body for
derivation phrasings ("By X", "From X", "Combining X and Y",
"X ∧ Y ⇒ ..."), and for each such match looks up an assertion of
``kind: derived-consequence`` whose ``derivation_sketch`` cites every
parent in the canonical syntax.

Per plan-006 §C6 (post-iter-1-M5 fix): the WARN-fallback that previously
softened misclassifications was DROPPED. Misclassifications are now
either (a) resolved through ``--user-override`` at the CLI level (handled
by ``run_canary.py`` — NOT by this parser) or (b) escalate as
``ESCALATE-UNRESOLVED``, which counts as a hard FAIL for that match.

Empty-corpus edge case: if no kdocs are produced (e.g., dry-run) the
result is ``PASS`` with the summary "no kdocs to scan". This matches
the "vacuously true" interpretation of "every derivation closes" when
there are no derivations to begin with.

Public surface
--------------

``check(produced_files, knowledge_dir, assertion_dir, truth_table=None)``
    Project-agnostic §7 criterion entry point per
    ``criteria/__init__.py``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from . import CriterionResult, CriterionStatus

# ---------------------------------------------------------------------------
# Citation tokens
# ---------------------------------------------------------------------------

# Canonical citation form: ``[K-NNN:K.X]`` (kdoc id + equation label).
_CANONICAL_KDOC_CITE_RE = re.compile(r"\[(K-\d+):(K\.\d+)\]")

# Canonical citation form: ``[E.N]`` (EQN-REF entry).
_CANONICAL_EQN_REF_CITE_RE = re.compile(r"\[(E\.\d+)\]")

# Tolerant fallback for free-text references inside kdoc derivations,
# e.g. ``K.3`` or ``E.45`` appearing bare (not bracketed). The
# consequence-closure parser scans kdoc derivation phrasings — kdoc
# body text frequently uses bare ``K.3`` even when the canonical
# inter-doc citation form is ``[K-NNN:K.X]``. We accept both, then
# normalise to the canonical form for cross-reference matching against
# assertion derivation sketches.
_BARE_LABEL_RE = re.compile(r"\b([KE]\.\d+)\b")

# Derivation phrasings we recognise inside kdoc bodies. The pattern
# tolerates ``By``, ``From``, and ``Combining`` introducers, optional
# parens around the cited labels, the connective tokens
# {``∧``, ``∪``, ``+``, ``,``, ``and``}, and arbitrary trailing prose
# on the same line (the consequence "claim").
_DERIVATION_INTRO = r"(?:By|From|Combining)"
# A single citation token, optionally wrapped in parens:
# - ``[K-NNN:K.X]``      canonical kdoc-eq citation
# - ``[E.N]`` or ``E.N`` EQN-REF entry
# - ``[K.X]`` or ``K.X`` bare kdoc-local label
# - any of the above wrapped in ``(...)``
_LABEL = (
    r"\(?\s*"
    r"(?:\[K-\d+:K\.\d+\]|\[?[KE]\.\d+\]?)"
    r"\s*\)?"
)
_CONNECTIVE = r"(?:\s*(?:∧|∪|\+|,|and)\s*)"
_DERIVATION_RE = re.compile(
    rf"(?:^|\n)\s*"
    rf"(?P<intro>{_DERIVATION_INTRO})\s+"
    rf"(?P<labels>(?:{_LABEL})(?:{_CONNECTIVE}(?:{_LABEL}))*)"
    rf"\s*[,:]?\s*"
    rf"(?P<claim>[^\n]+)",
    re.MULTILINE,
)

# Symbolic-arrow form: ``(K.X) ∧ (K.Y) ⇒ {claim}`` per brief 002 §3.4.
# We accept ⇒, =>, and \Rightarrow. ``_LABEL`` already tolerates parens.
_ARROW_RE = re.compile(
    rf"(?P<labels>(?:{_LABEL})(?:{_CONNECTIVE}(?:{_LABEL}))+)"
    rf"\s*(?:⇒|=>|\\Rightarrow)\s*"
    rf"(?P<claim>[^\n]+)",
    re.MULTILINE,
)

# Frontmatter delimiter.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Tiny YAML reader (frontmatter-only; no PyYAML dependency)
# ---------------------------------------------------------------------------


def _read_frontmatter(text: str) -> dict[str, str]:
    """Parse a top-level YAML block at the head of ``text``.

    Returns a flat ``str -> str`` mapping for scalar fields. List and
    nested fields are returned as raw multi-line strings; this parser
    only needs scalar lookups (``kind``, ``status``, ``kdoc_id``,
    ``assertion_id``).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    out: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        # ``key: value`` at column 0 (no leading whitespace).
        if not raw_line.startswith((" ", "\t")) and ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            out[key] = val
            current_key = key
        else:
            # Continuation line; coarse-append for scalar fields.
            if current_key is not None:
                out[current_key] = (out.get(current_key, "") + "\n" + raw_line).strip()
    return out


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    """Return the body of a doc, stripping any leading YAML frontmatter."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return text
    return text[match.end() :]


def _extract_derivation_sketch(text: str) -> str:
    """Pull the ``## Derivation Sketch`` section body, or empty string."""
    body = _strip_frontmatter(text)
    # Find the section heading; tolerate both `## Derivation Sketch` and
    # `### Derivation Sketch`.
    sec_re = re.compile(r"\n#{2,}\s*Derivation Sketch\s*\n", re.IGNORECASE)
    match = sec_re.search("\n" + body)  # leading \n so heading at top matches
    if not match:
        return ""
    start = match.end() - 1  # because of the prepended \n
    # Stop at the next heading of the same or higher level.
    next_sec = re.search(r"\n#{1,3}\s+\S", body[start:])
    if next_sec:
        return body[start : start + next_sec.start()].strip()
    return body[start:].strip()


# ---------------------------------------------------------------------------
# Citation normalisation
# ---------------------------------------------------------------------------


def _normalise_label(token: str, *, kdoc_id: str | None) -> str:
    """Collapse a raw cited-label token to canonical form.

    The kdoc body may write ``K.3`` (bare), ``[K.3]`` (bracketed local),
    ``[K-007:K.3]`` (canonical), or ``E.45`` / ``[E.45]``. For matching
    against assertion derivation sketches we always normalise to the
    canonical bracketed form.

    For bare ``K.X`` references found inside a kdoc body, we resolve to
    that kdoc's id (``K-NNN``) so the resulting canonical token matches
    what a downstream assertion would cite.
    """
    raw = token.strip().strip("()[]").strip()
    # Already canonical kdoc cite ``K-NNN:K.X``.
    m = re.fullmatch(r"K-\d+:K\.\d+", raw)
    if m:
        return f"[{raw}]"
    # Bare K.X — pin to the host kdoc id when known.
    m = re.fullmatch(r"K\.\d+", raw)
    if m:
        if kdoc_id:
            return f"[{kdoc_id}:{raw}]"
        return f"[{raw}]"
    # E.N entry.
    m = re.fullmatch(r"E\.\d+", raw)
    if m:
        return f"[{raw}]"
    return f"[{raw}]"


def _split_labels(label_blob: str, *, kdoc_id: str | None) -> list[str]:
    """Split a captured labels group into normalised canonical tokens."""
    # Tokenise on connectives ∧, ∪, +, comma, and the word "and".
    parts = re.split(r"(?:\s*(?:∧|∪|\+|,|and)\s*)", label_blob)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(_normalise_label(p, kdoc_id=kdoc_id))
    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for tok in out:
        if tok not in seen:
            seen.add(tok)
            deduped.append(tok)
    return deduped


# ---------------------------------------------------------------------------
# Kdoc derivation-statement scan
# ---------------------------------------------------------------------------


def _scan_kdoc_derivations(
    kdoc_path: Path, body: str, *, kdoc_id: str | None
) -> list[dict]:
    """Return derivation matches found in a kdoc body."""
    found: list[dict] = []
    seen_keys: set[tuple[str, ...]] = set()

    def _record(labels: list[str], claim: str, span: tuple[int, int], form: str) -> None:
        if not labels:
            return
        key = (form, *labels, claim.strip()[:80])
        if key in seen_keys:
            return
        seen_keys.add(key)
        found.append(
            {
                "kdoc_path": str(kdoc_path),
                "kdoc_id": kdoc_id,
                "form": form,
                "parents": labels,
                "claim": claim.strip(),
                "span": span,
            }
        )

    for m in _DERIVATION_RE.finditer(body):
        labels = _split_labels(m.group("labels"), kdoc_id=kdoc_id)
        _record(labels, m.group("claim"), m.span(), form=m.group("intro").lower())

    for m in _ARROW_RE.finditer(body):
        labels = _split_labels(m.group("labels"), kdoc_id=kdoc_id)
        _record(labels, m.group("claim"), m.span(), form="arrow")

    return found


# ---------------------------------------------------------------------------
# Assertion index
# ---------------------------------------------------------------------------


def _index_assertions(
    assertion_dir: Path, produced: set[Path]
) -> list[dict]:
    """Return one record per produced derived-consequence assertion."""
    out: list[dict] = []
    if not assertion_dir.exists():
        return out
    for path in sorted(assertion_dir.rglob("*.md")):
        if produced and path.resolve() not in produced:
            continue
        text = path.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        kind = fm.get("kind", "").strip()
        if kind != "derived-consequence":
            continue
        sketch_field = fm.get("derivation_sketch", "")
        sketch_section = _extract_derivation_sketch(text)
        sketch = "\n".join(s for s in (sketch_field, sketch_section) if s)
        cited: set[str] = set()
        for m in _CANONICAL_KDOC_CITE_RE.finditer(sketch):
            cited.add(f"[{m.group(1)}:{m.group(2)}]")
        for m in _CANONICAL_EQN_REF_CITE_RE.finditer(sketch):
            cited.add(f"[{m.group(1)}]")
        # Tolerant: also accept bare ``K.X eq`` or free-text fallback per
        # plan-006 §C5 cleanup-flag rule. We keep the bracketed form
        # only — bare forms are not tolerated for kdoc cites because we
        # cannot disambiguate which kdoc they refer to from an
        # assertion's sketch alone (the assertion may cite multiple
        # parents). Bare ``E.N`` is ambiguous-free and is accepted.
        for m in _BARE_LABEL_RE.finditer(sketch):
            tok = m.group(1)
            if tok.startswith("E."):
                cited.add(f"[{tok}]")
        out.append(
            {
                "assertion_path": str(path),
                "assertion_id": fm.get("assertion_id", path.stem),
                "status": fm.get("status", ""),
                "cited_parents": cited,
                "sketch_excerpt": sketch[:400],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------


def _produced_set(produced_files: Iterable[Path] | None) -> set[Path]:
    if not produced_files:
        return set()
    return {Path(p).resolve() for p in produced_files}


def check(
    produced_files: list[Path] | None,
    knowledge_dir: Path,
    assertion_dir: Path,
    truth_table: dict | None = None,
) -> CriterionResult:
    """Run the §7.2 consequence-closure check.

    Per plan-006 §C6 + brief 002 §7.2 — every kdoc derivation must close
    via a ``derived-consequence`` assertion that cites every parent in
    canonical form. Sampling is NOT permitted.

    Parameters
    ----------
    produced_files:
        Cost-log-derived list of paths produced by the canary run (only
        those with ``error_class == "ok"``). When ``None`` or empty the
        parser walks the full ``knowledge_dir`` / ``assertion_dir`` —
        useful for unit tests that operate on a fixture directory
        without a cost log.
    knowledge_dir:
        Sandbox knowledge directory for the run.
    assertion_dir:
        Sandbox assertion directory.
    truth_table:
        Unused by this criterion; accepted to match the project-agnostic
        signature in ``criteria/__init__.py``.
    """
    name = "Consequence Closure"
    knowledge_dir = Path(knowledge_dir)
    assertion_dir = Path(assertion_dir)
    produced = _produced_set(produced_files)

    if not knowledge_dir.exists():
        return CriterionResult(
            name=name,
            status=CriterionStatus.PASS,
            summary="no kdocs to scan (knowledge_dir absent)",
            details=[],
            payload={"derivations_found": 0, "closed": 0},
        )

    # Collect kdoc paths to scan.
    kdoc_paths: list[Path] = []
    for path in sorted(knowledge_dir.rglob("*.md")):
        if produced and path.resolve() not in produced:
            continue
        kdoc_paths.append(path)

    if not kdoc_paths:
        return CriterionResult(
            name=name,
            status=CriterionStatus.PASS,
            summary="no kdocs to scan (empty corpus)",
            details=[],
            payload={"derivations_found": 0, "closed": 0},
        )

    # Scan kdoc bodies for derivation statements.
    derivations: list[dict] = []
    for path in kdoc_paths:
        text = path.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        kdoc_id = fm.get("kdoc_id", "").strip()
        # Strip the frontmatter so derivation regexes never match the
        # YAML block itself (e.g., a string value containing "By X").
        body = _strip_frontmatter(text)
        derivations.extend(
            _scan_kdoc_derivations(path, body, kdoc_id=kdoc_id or None)
        )

    if not derivations:
        return CriterionResult(
            name=name,
            status=CriterionStatus.PASS,
            summary="no derivations stated in produced corpus (vacuous closure)",
            details=[],
            payload={"derivations_found": 0, "closed": 0},
        )

    # Index produced derived-consequence assertions.
    assertion_records = _index_assertions(assertion_dir, produced)

    closed_count = 0
    failures: list[str] = []
    closure_payload: list[dict] = []
    for d in derivations:
        parents = set(d["parents"])
        match = None
        for rec in assertion_records:
            if parents.issubset(rec["cited_parents"]):
                match = rec
                break
        closure_payload.append(
            {
                "kdoc_path": d["kdoc_path"],
                "form": d["form"],
                "parents": sorted(parents),
                "claim": d["claim"],
                "matched_assertion": match["assertion_id"] if match else None,
            }
        )
        if match is None:
            failures.append(
                f"{Path(d['kdoc_path']).name}: derivation "
                f"({d['form']} {', '.join(sorted(parents))}) ⇒ "
                f"\"{d['claim'][:80]}\" — no derived-consequence assertion "
                f"cites all parents {sorted(parents)}"
            )
        else:
            closed_count += 1

    if failures:
        return CriterionResult(
            name=name,
            status=CriterionStatus.FAIL,
            summary=(
                f"{len(failures)}/{len(derivations)} derivations not closed "
                f"(brief 002 §7.2: sampling is not acceptable)"
            ),
            details=failures,
            payload={
                "derivations_found": len(derivations),
                "closed": closed_count,
                "closures": closure_payload,
            },
        )

    return CriterionResult(
        name=name,
        status=CriterionStatus.PASS,
        summary=f"{closed_count}/{len(derivations)} derivations closed",
        details=[],
        payload={
            "derivations_found": len(derivations),
            "closed": closed_count,
            "closures": closure_payload,
        },
    )


__all__ = ["check"]
