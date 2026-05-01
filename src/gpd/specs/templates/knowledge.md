---
template_version: 1
eqn_ref_schema_version: 1
assertion_schema_version: 1
layout: single
---

# Knowledge Document Template

Template for `GPD/knowledge/NNN-slug.md` — reviewed domain knowledge with a trust lifecycle.

**Purpose:** Capture domain understanding in a reviewable form before computation depends on it. Unlike RESEARCH.md (one-shot, phase-scoped), knowledge documents are project-scoped, reviewed, and carry an explicit trust status.

**Lifecycle:** Draft → Under Review → Stable → Superseded. Only Stable documents should be cited as dependencies by downstream results and plans.

**Relationship to other files:**

- `RESEARCH.md` is a phase-scoped exploration report — consumed by the planner, then largely forgotten
- `INSIGHTS.md` is an append-only pattern ledger — records what went wrong, not what is known
- `CONVENTIONS.md` is the prescriptive convention catalog — governs signs, normalizations, units
- Knowledge documents capture *domain understanding* — what the key results are, how they connect, where the traps lie

---

## File Template

```markdown
---
kdoc_id: K-NNN-slug
status: Draft
topic: "[topic name]"
cluster: ""  # optional: group this kdoc into a named cluster for phase-3 auto-partition; leave blank to fall into "unclustered"
sources:
  - "[arXiv:XXXX.XXXXX or DOI or textbook reference]"
created: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
review_rounds: 0
superseded_by: null
eqn_ref_schema_version: 1
assertion_schema_version: 1
layout: single  # single | umbrella-plus-parts
---

# Knowledge: [Topic Title]

## Overview

[3-5 substantive paragraphs. Cover: (1) what physical question the paper/topic addresses and why it matters; (2) the key physical content — what mechanism, result, or structure the paper establishes; (3) main quantitative results and their significance; (4) consequences for the broader project. This is NOT a one-sentence abstract. A thin overview that just lists topics is a failure mode.]

## Physical Picture

[The conceptual core of this topic — written for a physicist who knows the field but hasn't read this paper.
Cover:
- **Motivation**: why does this topic exist? What physical question does it answer?
- **Key intuition**: what is the mental model? What should a reader visualize or remember?
- **Logical flow**: how do the main ideas chain together? (not equations — the reasoning)
- **Regime**: when does this description apply, and when does it break down?

Minimum 2 substantive paragraphs. Do NOT reduce this to equation labels.]

## Key Results

1. [Result statement with equation reference, e.g., "The 4-point KZ connection matrix is given by eq. (K.3)"]
2. [...]

## Equations

[Key equations, each with context. Use LaTeX. Number as (K.1), (K.2), etc.]

(K.1) $equation$
Context: [where this comes from, when it applies]
Why/How: [physical reason this relation holds; how the coefficient or structure arises; what breaks down if you ignore it]

(K.2) $equation$
Context: [...]
Why/How: [...]

## Conventions

[All conventions used in this document. Cross-reference with CONVENTIONS.md where applicable.]

- Metric signature: [...]
- Normalization: [...]
- Index ranges: [...]

## Derivation Sketches

[For each key result: the essential derivation steps, or a pointer to a full derivation elsewhere.]

## Connections

[How this topic connects to other knowledge documents or project artifacts.]

- Related to K-NNN: [...]
- Used by Phase X: [...]

## Open Questions

[What is NOT known or NOT settled.]

- [...]

## Traps and Subtleties

[Common mistakes, easy-to-miss sign errors, convention clashes between papers.]

- [...]
```

---

## Guidelines

- **One topic per document.** "Metric conventions in curved-space QFT" is good. "Everything about QFT" is too broad.
- **Cite specific equations.** "Peskin-Schroeder eq. (7.84)" not "standard result."
- **Flag convention clashes.** If Paper A uses (+−−−) and Paper B uses (−+++), say so explicitly.
- **Traps section is mandatory.** Every topic has subtleties. If you can't think of any, you haven't understood the topic well enough.
- **Status discipline.** Don't mark Stable until a human has reviewed. Draft is honest; premature Stable is dangerous.
