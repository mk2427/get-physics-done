# EQN-REF Document Schema — Canonical Template

This file is the canonical 8-field schema template for EQN-REF documents
produced by `gpd-eqnref-integrator`. Every EQN-REF document emitted by the
integrator MUST conform to this template's six-section structure and 8-field
per-equation catalog format.

---

## Document Layout

### Single-file vs umbrella split

- **Single file** — emit `013-equation-reference.md` when the estimated
  total line count is ≤ 600 lines.
- **Umbrella + parts split** — emit when estimated total line count exceeds
  600 lines:
  - `013-equation-reference.md` — umbrella index (§§1–6 section headers +
    links only; no duplicated content)
  - `013-part-a-convention-lock.md` — §1 Convention Lock + §E.0 Translation
    Formulas
  - `013-part-b-equation-catalog.md` — §2 Equation Catalog (8-field)
  - `013-part-c-typos-questions-traps.md` — §3 Typo Annotations + §4 K↔E
    Map + §5 Open Questions + §6 Traps

---

## Six-Section Structure (required for all EQN-REF documents)

Every EQN-REF document MUST contain all six sections even when a section has
no content (write "None identified" rather than omitting the section).

### §1 Convention Lock

Tabular listing of all convention axes locked for this project. Each row
carries:

| Axis ID | Canonical Phase 0F choice | Source cluster-audit row | `convention_set` key |
|---------|--------------------------|--------------------------|----------------------|

Axes are sorted by `axis_id`. The `convention_set` key is the MCP key used
when `--auto-fire-conventions` is active: canonical axes use their
short-form key; non-canonical axes use `custom:<slug>`.

The Convention Lock section is the authoritative source for `gpd-conventions`
MCP state. It supersedes any manually-edited `GPD/CONVENTIONS.md` entries for
the axes listed.

### §E.0 Translation Formulas

For every axis where the meta-audit identified a non-canonical variant (i.e.,
the "Alternative conventions" cell in a §2 catalog entry is non-empty),
document the translation formula:

```
[Axis: <axis_id>] Canonical ↔ Alternative
  canonical:    <canonical form>
  alternative:  <alternative form>
  translation:  <LaTeX formula relating the two>
  direction:    bidirectional | canonical→alternative | alternative→canonical
```

Emit "None identified" when every axis has a unique canonical choice with no
variants.

### §2 Equation Catalog (8-field)

One entry per equation. Each entry MUST carry all 8 fields (see §2 Field
Definitions below). Entries are numbered sequentially as `E.1`, `E.2`, etc.
The numbering is stable across runs once assigned (do NOT re-number on
incremental updates).

#### §2 Field Definitions

1. **E.N** — Equation identifier. Sequential integer label using the `E.N`
   scheme (e.g., `E.1`, `E.2`). Assigned once and never reused.

2. **Name** — Human-readable equation name (e.g., "BFSS Hamiltonian",
   "Gauge-fixing condition"). Concise noun phrase; avoid generic labels like
   "main equation".

3. **Canonical form** — LaTeX equation body rendered in the project's
   canonical conventions as established in §1. MUST be the post-normalization
   form as produced by `normalize_eqn_body` (commit 3). Wrap in fenced code
   block:
   ```latex
   <LaTeX body>
   ```

4. **Source** — arXiv ID + paper equation number + `.tex` line-cite.
   Format: `arXiv:<NNNN.NNNNN> Eq. <label>; references/<id>.tex line <N>`.
   For non-paper-native equations (convention-lock identities, definitions),
   cite the K-label that introduced the equation instead of an arXiv source:
   `K-label: <knowledge/NNN K.N>`.

5. **K-label origin** — Comma-separated list of knowledge-doc K-labels that
   this equation entry consolidates (e.g., `K-001 K.3, K-004 K.7`). A single
   equation restated across multiple kdocs will list all origin K-labels here.
   Emit `—` when the equation originates only from a paper source with no
   kdoc restatement.

6. **Regime** — Applicability conditions. Specify at least one of: `N`
   (large-N expansion order), `T` (temperature regime), `coupling` (weak /
   strong / arbitrary), `model` (BFSS / BFSS-SU(N) / etc.). Emit `—` if the
   equation holds universally within the project scope.

7. **Typo note** — Short annotation referencing §3 (e.g., "See §3 T.2 —
   confirmed sign error in arXiv v1"). Emit `—` if no typo annotation applies
   to this equation.

8. **Alternative conventions** — Non-canonical variants and translation
   pointer. Format: `<description> → see §E.0 <axis_id>`. Emit `—` if no
   alternative conventions apply.

#### §2 Entry Format

```markdown
#### E.N — <Name>

- **E.N**: E.N
- **Name**: <equation name>
- **Canonical form**:
  ```latex
  <LaTeX body>
  ```
- **Source**: <arXiv-ID> Eq. <label>; `references/<id>.tex` line <N>
- **K-label origin**: <knowledge/NNN K.N> | **Regime**: <conditions>
- **Typo note**: <annotation or —> | **Alternative conventions**: <variants or —>
```

### §3 Typo Annotations

One entry per confirmed, not-a-typo, or inconclusive typo verdict from the
cluster and meta-audit phases. Entries use the `T.N` numbering scheme where N
is sequential within this document.

| T.N | Equation | Paper cite | Verdict | Note |
|-----|----------|------------|---------|------|

Verdicts: `confirmed-typo` / `not-a-typo` / `inconclusive`.

Emit "None identified" when no typo annotations exist.

### §4 K↔E Map

Bidirectional index linking knowledge-doc K-labels to EQN-REF E.N labels.

```
K-001 K.3  →  E.2, E.7
K-004 K.7  →  E.2
E.2        →  K-001 K.3, K-004 K.7
```

Emit "None identified" when the project has no kdocs (EQN-REF was produced
without `--adversarial`).

### §5 Open Questions (with BLOCKING flags)

Unresolved questions from the meta-audit phase that affect convention-lock or
equation-catalog completeness. Each entry carries a BLOCKING flag.

| OQ.N | Question | BLOCKING | Source finding ID | Opened |
|------|----------|----------|-------------------|--------|

- `BLOCKING: true` — the convention lock or equation catalog MUST NOT be
  treated as final until this question is resolved.
- `BLOCKING: false` — informational; does not gate downstream use.

Emit "None identified" when no open questions remain. A clean §5 is a
prerequisite for `--auto-fire-conventions` without `--force`.

### §6 Traps

Known pitfalls for downstream agents and users. Format:

```
**Trap T.N** — <title>
Context: <when this trap is relevant>
Risk: <what goes wrong>
Mitigation: <how to avoid>
```

Emit "None identified" when no traps are documented.

---

## EQN-REF Content Hash

The EQN-REF document's `eqn_ref_content_hash` (used in the revlog) is
computed as the SHA-256 of the UTF-8-encoded canonical-form bodies of all
§2 entries, joined by newlines, after passing each body through
`normalize_eqn_body` (commit 3 pipeline). This makes the hash stable under
whitespace and formatting changes to the document prose while sensitive to
actual equation-body changes.

---

## Frontmatter (EQN-REF documents)

All EQN-REF documents carry the following YAML frontmatter:

```yaml
---
kind: eqn-reference
project: <project slug>
generated_by: gpd-eqnref-integrator
meta_audit_report: GPD/meta-audit/meta-audit-report.md
meta_audit_verdict: APPROVED        # must be APPROVED for convention_set to fire
eqn_ref_content_hash: <sha256-hex>  # hash of all §2 canonical-form bodies
convention_lock_axes: <N>           # count of axes in §1
equation_count: <N>                 # count of entries in §2
created: <ISO-8601 date>
last_updated: <ISO-8601 date>
---
```
