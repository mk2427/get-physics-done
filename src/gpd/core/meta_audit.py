"""Cross-cluster meta-audit grouping + residual-row queue writer.

Brief 002 §4.1 step 4 consolidation helpers used by `gpd-meta-auditor` to
reduce per-cluster audit reports into a single project-wide convention-lock
proposal set. Two grouping passes are implemented:

1. **Canonical-signature grouping** — equations equivalent under
   :func:`gpd.core.eqn_normalize.normalize_eqn_body` hash to the same sha256
   digest. This is the load-bearing primary match used for the Master
   Convention Table §2 of the meta-audit schema. Reuses the pipeline shipped
   in commit 3 (brief 002 §3.4.1) for referential transparency with
   `upstream_ref_hash`.

2. **Topic-keyword grouping** — rows whose description matches any controlled
   vocabulary term fall into the corresponding axis bucket. Seeds the §3
   topic-keyword groups in the meta-audit report, and serves as fallback for
   rows that do not carry a canonical equation body.

Rows that match neither pass are appended to the per-project
`GPD/meta-audit/candidate-axes.md` residual queue via
:func:`append_to_candidate_axes`; the queue is the input to the
`/gpd:adversarial-review` adjudication loop that resolves the §1 item 4 W5
workflow pick.

All three helpers are pure / deterministic and intentionally free of file IO
beyond the explicit `candidate_axes_path` writer. They are callable from the
`gpd-meta-auditor` agent prompt directly or from downstream tests with
synthetic cluster-report fixtures.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from gpd.core.eqn_normalize import normalize_eqn_body

__all__ = [
    "CANDIDATE_AXES_HEADER",
    "append_to_candidate_axes",
    "canonical_signature",
    "topic_keyword_group",
]


# --- (1) Canonical-signature grouping ---------------------------------------


def canonical_signature(
    eqn_body: str,
    normalize_fn: Callable[[str], str] = normalize_eqn_body,
) -> str:
    """Return the canonical sha256 signature of an equation body.

    The input is first normalized via ``normalize_fn`` (default:
    :func:`gpd.core.eqn_normalize.normalize_eqn_body` from commit 3), then
    UTF-8 encoded and sha256-digested. Equivalent equations (same
    ``normalize_fn`` output) MUST produce identical signatures; this is the
    primary grouping key for the meta-audit Master Convention Table.

    Only the normalized equation body contributes to the digest: kdoc ID,
    equation number, paper, and surrounding prose are intentionally excluded
    so that two papers quoting the SAME equation under the SAME canonical
    form always collide regardless of bookkeeping metadata. The grouping
    consumer is responsible for carrying that metadata alongside the
    signature (see :func:`topic_keyword_group`'s ``rows`` schema).

    Parameters
    ----------
    eqn_body:
        Raw LaTeX equation body, as extracted from a cluster-audit report or
        kdoc ``equations[].body`` field.
    normalize_fn:
        Pluggable canonicalizer. Tests can inject an identity function to
        validate grouping over an already-normalized fixture; production
        always uses the commit-3 pipeline.

    Returns
    -------
    str
        Hex-encoded sha256 digest, 64 characters long.
    """

    if not isinstance(eqn_body, str):
        raise TypeError("canonical_signature expects eqn_body to be a string")
    normalized = normalize_fn(eqn_body)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest


# --- (2) Topic-keyword grouping ---------------------------------------------


def topic_keyword_group(
    rows: list[dict],
    vocab: list[str],
) -> dict[str, list[dict]]:
    """Bucket cluster-report rows by controlled-vocab keyword match.

    Each row is a dict with at minimum a ``description`` string field; rows
    MAY also carry ``row_id``, ``cluster``, ``axis_id``, and other metadata
    which is passed through unchanged.

    A row is assigned to every keyword whose lowercase form appears as a
    substring of the row's lowercase ``description``. This is intentionally
    permissive on the grouping side — a row that mentions multiple topics
    surfaces in every relevant bucket so the meta-auditor can audit the
    intersection. Rows that match no keyword are absent from the returned
    mapping and should be appended to the residual queue via
    :func:`append_to_candidate_axes`.

    Parameters
    ----------
    rows:
        List of cluster-report row dicts. Each must have a string
        ``description`` field. Missing / non-string descriptions are skipped
        silently (treated as unmatched) so a malformed upstream cluster
        report never crashes the grouping pass.
    vocab:
        Controlled-vocabulary keyword list, typically sourced from the
        ``Topic-Keyword Index`` section of
        ``references/meta-audit/controlled-vocab.md`` (commit 3 template) or
        the per-project override ``GPD/meta-audit/controlled-vocab.md``.

    Returns
    -------
    dict[str, list[dict]]
        Keyword (lowercased) -> list of matching rows, in original order.
        Keywords that matched zero rows are present with an empty list iff
        the keyword appeared in ``vocab``; this keeps the output shape
        stable for downstream report emitters.
    """

    if not isinstance(rows, list):
        raise TypeError("topic_keyword_group expects rows to be a list of dicts")
    if not isinstance(vocab, list):
        raise TypeError("topic_keyword_group expects vocab to be a list of strings")

    # Normalize vocab: lowercase, strip, drop empties, de-dup preserving order.
    seen: set[str] = set()
    normalized_vocab: list[str] = []
    for term in vocab:
        if not isinstance(term, str):
            raise TypeError("topic_keyword_group vocab entries must be strings")
        key = term.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized_vocab.append(key)

    buckets: dict[str, list[dict]] = {term: [] for term in normalized_vocab}

    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("topic_keyword_group rows must be dicts")
        description = row.get("description")
        if not isinstance(description, str):
            continue
        haystack = description.lower()
        for term in normalized_vocab:
            if term in haystack:
                buckets[term].append(row)

    return buckets


# --- (3) Residual-row queue writer ------------------------------------------


CANDIDATE_AXES_HEADER = (
    "# Candidate Axes Queue\n"
    "\n"
    "Residual rows from the cross-cluster meta-audit that matched neither a\n"
    "canonical-signature group nor a topic-keyword bucket. Each entry awaits\n"
    "`/gpd:adversarial-review` adjudication per brief 002 §1 item 4 (W5\n"
    "workflow pick). Append-only ledger; do not rewrite prior rows.\n"
    "\n"
    "Columns:\n"
    "- `row_id`: `cluster-{K}-row-{N}` source pointer.\n"
    "- `description`: verbatim cluster-report description.\n"
    "- `proposed_axis_id`: optional auto-proposal from the meta-auditor.\n"
    "- `status`: `pending` | `accepted` | `rejected` | `escalated`.\n"
    "- `reviewer_notes`: free-form.\n"
    "\n"
    "| row_id | description | proposed_axis_id | status | reviewer_notes |\n"
    "|---|---|---|---|---|\n"
)


def append_to_candidate_axes(
    residual_row: dict,
    candidate_axes_path: Path,
) -> None:
    """Append a residual cluster-report row to the candidate-axes queue.

    Creates the file with :data:`CANDIDATE_AXES_HEADER` if it does not yet
    exist; otherwise appends a single markdown table row. The queue contract
    matches the ``Residual-Row Queue`` section of
    ``references/meta-audit/controlled-vocab.md`` (commit 3) so a meta-auditor
    writing to either the installed template path or the per-project override
    produces a consistent on-disk shape.

    Row fields (all optional; missing fields become ``""``):
        - ``row_id``
        - ``description``
        - ``proposed_axis_id``
        - ``status`` (defaults to ``"pending"``)
        - ``reviewer_notes``

    Any embedded ``|``, ``\\n``, or ``\\r`` in string fields is escaped or
    stripped so a single logical row stays on a single markdown line. This
    keeps the table parseable by downstream `/gpd:adversarial-review` tooling.

    Parameters
    ----------
    residual_row:
        Dict with the fields above. Unknown keys are ignored (forward-compat).
    candidate_axes_path:
        Target ``GPD/meta-audit/candidate-axes.md`` (or the installed
        template path in test harnesses). Parent directory is created if
        absent.
    """

    if not isinstance(residual_row, dict):
        raise TypeError("append_to_candidate_axes expects residual_row dict")
    candidate_axes_path = Path(candidate_axes_path)
    candidate_axes_path.parent.mkdir(parents=True, exist_ok=True)

    def _cell(value: object) -> str:
        text = "" if value is None else str(value)
        # Keep the row on one markdown line; escape pipes so they do not split columns.
        text = text.replace("\r", " ").replace("\n", " ")
        text = text.replace("|", r"\|")
        return text.strip()

    row_id = _cell(residual_row.get("row_id", ""))
    description = _cell(residual_row.get("description", ""))
    proposed_axis_id = _cell(residual_row.get("proposed_axis_id", ""))
    status = _cell(residual_row.get("status", "pending")) or "pending"
    reviewer_notes = _cell(residual_row.get("reviewer_notes", ""))

    line = f"| {row_id} | {description} | {proposed_axis_id} | {status} | {reviewer_notes} |\n"

    if not candidate_axes_path.exists():
        candidate_axes_path.write_text(CANDIDATE_AXES_HEADER + line, encoding="utf-8")
        return

    # Preserve existing header + prior appended rows; append new row at end.
    existing = candidate_axes_path.read_text(encoding="utf-8")
    if not existing.endswith("\n"):
        existing = existing + "\n"
    candidate_axes_path.write_text(existing + line, encoding="utf-8")
