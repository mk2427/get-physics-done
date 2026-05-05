---
template_version: 1
eqn_ref_schema_version: 1
assertion_schema_version: 1
layout: single
---

# Assertion Document Template

Template for `GPD/assertions/A-NNN-slug.md` — reviewed equation restatements and
derived-consequence claims with a trust lifecycle. Assertion docs mirror the
knowledge-doc lifecycle (Draft → Under Review → Stable → Superseded) but carry
four differential frontmatter fields that pin them to the project's convention
lock (brief 002 §3.4).

**Purpose:** Make load-bearing equations and their derived consequences
reviewable as first-class artifacts. Restated-equation assertions pull from the
EQN-REF catalog (E-entries) or knowledge-doc K-labels and elevate them to
load-bearing status. Derived-consequence assertions capture a new equation or
inequality that follows from one or more restated assertions plus known
conventions.

**Lifecycle:** Draft → Under Review → Stable → Superseded. Only Stable
documents may be cited as dependencies by downstream results and plans.
`load_bearing: true` is **monotonic** — once an assertion reaches Stable with
`load_bearing: true`, it cannot be demoted without explicit supersession.

**Relationship to other files:**

- Knowledge docs (`GPD/knowledge/K-NNN-*.md`) capture domain understanding; they
  are an assertion's upstream source.
- EQN-REF (`GPD/knowledge/013-equation-reference.md` or umbrella parts)
  catalogs equations and their conventions; `upstream_ref_hash` points here.
- Plan frontmatter `requires_assertion: [A-NNN, ...]` gates execution when
  `assertion_gate` is `warn` or `block`.

---

## ID Scheme

**Assertion ID format:** `A-NNN-slug` where NNN is a project-global 3-digit
counter (e.g. `A-007-level-2-virial-bound`). The counter is shared across all
assertions in the project; it does NOT reset per knowledge doc.

**Sub-assertion ID pattern:** `A-NNN.S{k}` where k is 1-indexed within the
doc (e.g. `A-007.S1`, `A-007.S2`). Sub-assertions are in-body only; they do
NOT get their own top-level `A-NNN` ID.

**Regex validation:** `^A-\d{3}(\.S\d+)?$` (without slug suffix for bare IDs)
or `^A-\d{3}-[a-z0-9-]+(\.S\d+)?$` (with slug).

**Finding ID namespace:** `A-NNN-iter-N-S1` (top-level, serious finding 1 at
iteration N) or `A-NNN.S2-iter-3-M1` (sub-assertion 2 of A-NNN, iter-3
moderate finding 1). Pattern: `A-\d{3}(\.S\d+)?-iter-\d+-[SMWN]\d+`.

---

## Four Differential Frontmatter Fields (brief 002 §3.4)

These four fields distinguish assertion docs from knowledge docs:

### `load_bearing`

**Type:** boolean (default `false`)

Whether this assertion is load-bearing for downstream plans. When `true` and
the assertion is Stable, plan frontmatter `requires_assertion: [A-NNN]` gates
plan execution. **Monotonic:** once Stable with `load_bearing: true`, the
assertion cannot be demoted without explicit supersession (opening a
`superseded_by` pointer and a new sibling assertion). Down-gating silently is
the convention-lock drift failure mode L16 was written to prevent.

### `derivation_sketch`

**Type:** string or null

**REQUIRED and non-empty on `kind: derived-consequence`.** The essential
derivation steps from cited upstream sources (K-labels + E-entries) to the
claimed equation. Every step must cite its source. An empty `derivation_sketch`
on a derived-consequence assertion is a **FATAL finding** (S-severity) per the
`gpd-adversarial-critic` charter.

**null on `kind: restated-equation`:** the `upstream_ref_hash` provides the
source pointer; no derivation is needed.

### `upstream_ref_hash`

**Type:** string (sha256 hex digest) or null

**REQUIRED on `kind: restated-equation`.** Computed as:
`sha256(normalize_eqn_body(canonical_latex)).hexdigest()` where `canonical_latex`
is the verbatim `canonical_form` field from the EQN-REF E-entry. Compute via:

```python
from gpd.core.assertion_divergence import compute_upstream_ref_hash
hash_val = compute_upstream_ref_hash(canonical_latex)
```

Empty or stale hashes **BLOCK Stable promotion** — the divergence check
(`assertion_divergence.check_divergence`) must return PASS before
`status: Stable` may be written.

**null on `kind: derived-consequence`:** no EQN-REF E-entry is the single
source of truth; the derivation_sketch carries the provenance instead.

### `upstream_status_mirror`

**Type:** mapping with three sub-fields

Tracks the lifecycle state of the parent knowledge document at the time this
assertion was promoted to Stable. If the parent K-doc transitions from Stable
to Superseded, this assertion auto-transitions Stable → Under Review and fires
an `invalidation_events` entry.

Sub-fields:
- `kdoc_id` — the primary parent K-doc (e.g. `K-007`), or null if no K-doc parent.
- `kdoc_status_at_stable` — the K-doc's `status` field at the time this
  assertion reached Stable (typically `"Stable"`). Used to detect drift.
- `divergence_detected_at` — ISO date when a K-doc status change was detected
  that invalidated this assertion, or null if no divergence detected.

---

## Validation Rules

| Field | `restated-equation` | `derived-consequence` |
|---|---|---|
| `upstream_ref_hash` | REQUIRED (sha256 hex string) | MUST be null |
| `derivation_sketch` | null or empty string OK | REQUIRED non-empty string |
| `load_bearing` | any boolean | any boolean |
| `upstream_status_mirror.kdoc_id` | recommended | recommended |

The `check_divergence` gate enforces the `upstream_ref_hash` rule before any
Stable promotion; it is a no-op (unconditional PASS) when `upstream_ref_hash`
is null (derived-consequence path).

---

## File Template

```markdown
---
assertion_id: A-NNN-slug
kind: restated-equation   # or: derived-consequence
status: Draft
topic: "[topic name]"
knowledge_doc_ids:
  - "K-NNN"
eqn_ref_entries:
  - "E.N"
created: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
review_rounds: 0
superseded_by: null

# Differential fields (assertion-specific; see brief 002 §3.4)
# load_bearing: false → not yet cited as a plan dependency
load_bearing: false
# derivation_sketch: REQUIRED non-empty on derived-consequence; null on restated-equation
derivation_sketch: null
# upstream_ref_hash: sha256(normalize_eqn_body(canonical_form)) on restated-equation; null on derived-consequence
upstream_ref_hash: null
# upstream_status_mirror: tracks parent K-doc lifecycle; divergence triggers Under Review
upstream_status_mirror:
  kdoc_id: null
  kdoc_status_at_stable: null
  divergence_detected_at: null
---

# Assertion: [Claim Title]

## Restated Equation or Derived Claim

[The canonical LaTeX form of the equation or inequality being asserted. One
equation per assertion is strongly preferred; compound structures go in
sub-assertions below.]

$[equation]$

## Regime of Validity

[Exact conditions under which the claim holds: N range, temperature, gauge
group, metric signature, coupling regime, etc. See L19: regime-match is
non-negotiable. Every assertion MUST state its regime; omitting it is a FATAL
finding per the adversarial-critic charter.]

## Derivation Sketch

[For derived-consequence assertions: the essential steps from upstream
sources to the claimed equation. Cite every knowledge doc and EQN-REF entry
used. REQUIRED non-empty on kind: derived-consequence.
For restated-equation assertions: this section may be omitted or left empty;
the upstream_ref_hash provides the source pointer.]

## Sub-Assertions

[Optional: in-body sub-assertions per brief 002 §4.1 step 7 body (c).
Recursion depth is capped at 3 per brief §5.2 — depth > 3 is a schema
validation error and escalates to the user before any adversarial loop.
Each sub-assertion is identified as A-NNN.S{k} where k is 1-indexed within
this doc (e.g. A-007.S1, A-007.S2).]

### A-NNN.S1: [sub-claim title]

[Claim, kind (restated-equation or derived-consequence), derivation sketch
if derived, provenance citations.]

## Traps and Subtleties

[Convention clashes, sign conventions, index-ordering subtleties, easy-to-
miss factors. Every assertion has traps; listing none is a review red flag
per L14.]

## Provenance

- **Knowledge docs:** [K-NNN, K-MMM]
- **EQN-REF entries:** [E.P, E.Q]
- **Source papers:** [arXiv IDs, section numbers, equation numbers]
```

---

## Guidelines

- **One claim per document.** "The level-6 BFSS virial bound" is good.
  "All BFSS inequalities at level 6" is too broad — split into sibling
  assertions linked via `depends_on`.
- **`upstream_ref_hash` is mandatory for restated equations.** Compute via
  `sha256(normalize_eqn_body(latex))` per brief 002 §3.4.1. Empty or stale
  hashes BLOCK Stable promotion.
- **`load_bearing: true` is monotonic.** Do not demote a Stable load-bearing
  assertion without opening a supersession. Down-gating silently is the
  convention-lock drift failure mode L16 was written to prevent.
- **`derivation_sketch` is required on derived consequences.** An empty
  sketch on a non-restated assertion is a FATAL finding per brief 002 §5.2
  `gpd-adversarial-critic` charter.
- **Status discipline.** Draft is honest; premature Stable is dangerous —
  especially here, because Stable load-bearing assertions enter the convention
  lock and every downstream plan depends on them.
- **Supersession cascade.** If this assertion's parent knowledge doc
  transitions Stable → Superseded, this assertion auto-transitions Stable →
  Under Review and fires an `invalidation_events` entry. Re-review against
  the superseding knowledge doc before returning to Stable.
- **Sub-assertion depth cap = 3.** The `route_assertion_critic` validator
  raises `AssertionDepthError` before entering any adversarial loop when depth
  exceeds 3. Structure deep compound assertions as sibling top-level assertions
  instead.
