---
lesson_id: L18
title: "Briefs Go in Files, Not Inline"
tags: ["context"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L18: Briefs Go in Files, Not Inline [context]
**Date**: 2026-04-15
**Trigger**: All critic prompts were written inline in main context, wasting tokens. CSFT Rule 26 says "Agent Prompts Go in Briefing Files, Not Main Context."
**Rule**: Write agent prompts to `agents/briefs/NNN-slug.md`. Launch agents with a 1-2 sentence reference. Main context is for orchestration only.
