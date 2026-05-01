---
template_version: 1
template_kind: meta-audit-controlled-vocab
---

# Meta-Audit Controlled-Vocab Template

Seed template for the cross-cluster meta-audit consolidation step (brief 002
§4.1 step 4). A project maintains one canonical controlled-vocab file here
(installed as `references/meta-audit/controlled-vocab.md`) plus a per-project
override where needed. The meta-auditor uses the controlled vocab to group
cluster-report rows by canonical-signature and topic-keyword; anything unmatched
falls through to `candidate-axes.md` per plan §1 item 4.

This file is a SCAFFOLD ONLY. Populate the axis and keyword tables before
running the meta-auditor on a new physics subfield.

---

## Axis Dictionary

Each canonical axis gets exactly one row. The `axis_id` is project-global and
becomes the load-bearing key that EQN-REF axes and `convention_set` MCP calls
reference.

| axis_id | name | canonical_signature | aliases | notes |
|---------|------|---------------------|---------|-------|
| `ax-example-01` | Metric signature | `eta_sign:++--` | `"mostly-plus"`, `"east-coast"` | — |

### Controlled-vocab guidelines

- `canonical_signature` is the load-bearing string used for exact-match grouping
  across cluster reports. Keep it short, deterministic, and convention-lock-ready.
- `aliases` lists strings that ALL map to the same canonical signature (typo
  tolerance; synonym tolerance). The meta-auditor folds aliases into the
  canonical row before applying topic-keyword grouping.
- `notes` captures convention-clash annotations, sign-choice rationale, and any
  HARD punts to the architect.

---

## Topic-Keyword Index

Keyword-match is the second grouping pass. Rows that miss an exact canonical
signature still cluster into an axis if any of the axis's topic keywords appears
in the row's description.

| axis_id | keywords |
|---------|----------|
| `ax-example-01` | `metric`, `signature`, `mostly-plus`, `mostly-minus` |

### Keyword guidelines

- Keep keyword sets small (≤ 8 per axis) and physics-specific. Broad keywords
  (`field`, `coupling`) create false-positive groupings.
- Case-insensitive match at runtime; list all keywords in lowercase here.

---

## Residual-Row Queue

Rows that match neither a canonical signature nor a keyword fall through to the
per-project `candidate-axes.md` queue. The meta-auditor is required to surface
the candidate queue to the user (or to the `/gpd:adversarial-review` loop)
before declaring consolidation done.

Queue contract (columns, JSONL-serializable):

- `row_id`: `"cluster-{K}-row-{N}"` source pointer.
- `description`: verbatim cluster-report description.
- `proposed_axis_id`: optional auto-proposal from the meta-auditor.
- `status`: `"pending" | "accepted" | "rejected" | "escalated"`.
- `reviewer_notes`: free-form.

---

## Per-Project Override Discipline

Projects MAY override this template by creating
`GPD/meta-audit/controlled-vocab.md` with the same schema. The meta-auditor
prefers the project-local file when present; otherwise it falls back to this
installed template. Keep overrides in sync with the installed template's
schema — drift between the two is a `/gpd:adversarial-review` finding.
