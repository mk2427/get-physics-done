---
lesson_id: L21
title: "Revision Logs Live in Sidecar Files, Not Plan Bodies"
tags: ["scaffolding", "workflow"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L21: Revision Logs Live in Sidecar Files, Not Plan Bodies [scaffolding, workflow]
**Date**: 2026-04-17
**Trigger**: Plan 002 accumulated 11 Revision Logs (~50% of 3119 lines), triggering a recursive STABLE-gate lock via self-firing AC-E6. Convergence theater (iter-6 first-pass APPROVED then second-pass REVISE; iter-4 Rule-46 DOUBLE PHANTOM; iter-13 self-falsifying `wc -l = 3016` claim when actual was 3119) identified the root cause: audit trail embedded in live spec creates self-referential review gates.
**Rule**: Every plan file (`agents/plans/NNN-slug.md`) gets a sibling `agents/plans/NNN-slug.revlog.md`. Revision Logs from revision-mode Planners append to the sidecar, NEVER to plan body. Plan body length is not a gated invariant.
