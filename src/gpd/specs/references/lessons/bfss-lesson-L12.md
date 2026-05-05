---
lesson_id: L12
title: "No Fixed Cap on Parallel Agent Launches"
tags: ["efficiency", "agents"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L12: No Fixed Cap on Parallel Agent Launches [efficiency, agents]
**Date**: 2026-04-15 (revised 2026-04-16)
**Trigger**: Batched critics into groups of 3-4 despite 11 being independent. User corrected twice: first to launch all 11 simultaneously, then (2026-04-16) to remove the 3-4 cap from AGENTS.md §6 Rule 6 entirely.
**Rule**: When N documents/tasks are truly independent, launch N agents in a single parallel wave — not 3, not 4, not 7. Batching independent work wastes wall time without improving per-agent depth. The one-focused-task-per-agent principle (L13, AGENTS.md §1b) bounds per-agent scope; it does NOT bound the count of concurrent agents. Constraints: (a) all agents in a wave must be independent, (b) numbers still pre-allocated per AGENTS.md §10, (c) each agent still gets a single-focus brief.
