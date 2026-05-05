---
template_version: 1
template_kind: meta-audit-schema
---

# Meta-Audit Schema

Canonical output shape for the cross-cluster meta-auditor report
(`GPD/meta-audit/meta-audit-report.md`) emitted by `gpd-meta-auditor` at the
end of the brief 002 §4.1 step 4 consolidation pass.

The section ordering below is LOAD-BEARING: it matches the BFSS-bootstrap
hand-built fixture at
`agents/reports/cross-cluster-meta-audit.md` §§1–8 that motivated the
schema. A test in `tests/core/test_meta_audit.py` validates the installed
template against that fixture — drift here will flip the test red.

Use this template when authoring or validating a meta-audit report. Do NOT
invent ad-hoc top-level sections; if a section has no content for a given
project, emit "None identified" so the §§1–8 contract stays intact.

---

## 1. Consistency Summary

Top-line verdict (PASS / PASS-with-caveat / FAIL) plus the cross-cluster
checks table. One row per check:

| Check | Clusters | Status | Pass rate |
|---|---|---|---|
| <check name> | <e.g., C1 vs C2> | PASS / INCONCLUSIVE / FAIL | N / M |

Follow with a ≤5-sentence journal-style summary stating whether any
cross-cluster PHYSICAL contradictions fired and whether all regime-matches
resolve transparently via §3. Residual INCONCLUSIVE items are listed here
and cross-linked into §2.

---

## 2. Inter-Cluster Contradictions Flagged

Header row MUST state the contradiction count explicitly, e.g.
`Count: 0 physical contradictions. 3 items carried forward as bookkeeping`.

For each flagged item emit a subsection `### I{n}. <short title>`:

- **Observation**: verbatim cross-paper disagreement, with paper + line cites.
- **Status**: whether the disagreement is a physical contradiction, a
  convention-only choice, or a bookkeeping ambiguity.
- **Action**: what the Phase 0F (or downstream) author MUST do.
- **Flag severity**: LOW / MEDIUM / HIGH.

Items that do not rise to "contradiction" after regime match are still
logged here; the top-line count MUST match the §1 summary.

---

## 3. Master Convention Reconciliation Table

For every canonical axis identified by the meta-auditor emit a subsection
`### 3{letter}. <axis title>` with:

1. A table of per-paper local conventions (`# | Paper | Local convention`).
2. A `**Reconciliation**` paragraph summarising the family structure.
3. A `**Canonical Phase 0F**` paragraph with the project-wide choice.

Close §3 with a one-line tally: the number of raw convention rows
consolidated and the number of orthogonal canonical axes produced. The
axis IDs MUST line up with the controlled-vocab `axis_id` column
(`references/meta-audit/controlled-vocab.md`) so downstream
`convention_set` MCP calls can reference them by key.

---

## 4. Aggregate Typo List

Single wide table combining every confirmed / rejected / inconclusive typo
from every cluster audit and adjudication report. Columns:

| # | Paper | Line(s) | Typo description | Status | Confidence | Source |
|---|---|---|---|---|---|---|

Status enum: `CONFIRMED (Adjudicated)` / `CONFIRMED (cluster)` /
`NOT-TYPO (Adjudicated)` / `NOT-TYPO (cluster)` / `INCONCLUSIVE`.

Close §4 with a summary paragraph tallying CONFIRMED / NOT-TYPO /
INCONCLUSIVE counts and a cross-cluster consistency line stating that no
typo verdict contradicts between clusters.

---

## 5. Open Questions for Downstream / Phase 0F Authors

Numbered `### O{n}. <short title> (<priority> priority)` subsections. Each
open question MUST carry:

- A plain-language statement of the unresolved question.
- Why it matters (which load-bearing downstream result depends on it).
- **Suggested action**: concrete next step (fetch paper X, run
  adjudication Y, contact author Z).

Close with a one-line tally `Total open questions: N` broken down by
HIGH / MEDIUM / LOW priority.

---

## 6. Cross-Cluster Consistency Audit Detail

Per-pair audit subsections `### 6{letter}. Cluster X vs Cluster Y — <scope>`
each containing the numerical / analytic checks that produced the §1 status
rows. This is the evidence section that §1 summarises.

An optional `### 6{letter}. Numerical cross-check consolidation` table MAY
list the load-bearing values compared across clusters with source and
cross-verification paper references plus agreement bounds. The row schema
is:

| # | Quantity | Source value + paper | Cross-verified value + paper | Agreement |

---

## 7. Compliance Checklist

Checklist of meta-audit preconditions (all boxes MUST be checked at emit):

- [ ] Read every cluster audit report in full.
- [ ] Read every adjudication report in full.
- [ ] §1 consistency summary has an explicit pass count.
- [ ] §2 contradictions section lists zero physical contradictions (or
      justifies each non-zero one).
- [ ] §3 master convention table carries a canonical Phase 0F choice for
      every axis.
- [ ] §4 aggregate typo list has confidence + source citation for every row.
- [ ] §5 open questions are tagged with HIGH / MEDIUM / LOW priority.
- [ ] Did NOT touch `GPD/knowledge/`, runtime instruction files,
      `lessons.md`, other reports, `handoff-*.md`, `references/`,
      or runtime settings files.
- [ ] Did NOT use `gpd-*` subagents (meta-auditor is the top-level agent).

---

## 8. Journal Entry

Append a dated entry to `agents/journal.md` (or the project-equivalent
location) with the schema:

```
### cross-cluster-meta-audit (Role: Cross-cluster meta-auditor) — <date>

<1-2 paragraph summary covering: inputs consumed, consistency verdict,
 canonical-axis count, aggregate typo counts, open-question priorities,
 artifacts emitted, paths NOT touched.>
```

The journal entry is the stable reference future agents use to locate the
meta-audit report without re-scanning the project.

---

## Residual-Row Queue Cross-Reference

Rows that matched neither a canonical signature nor a topic keyword SHALL
be appended to `GPD/meta-audit/candidate-axes.md` via
`gpd.core.meta_audit.append_to_candidate_axes`. The meta-audit report MUST
surface that queue explicitly in §2 (under the bookkeeping items) so the
`/gpd:adversarial-review` adjudication pass can pick them up.
