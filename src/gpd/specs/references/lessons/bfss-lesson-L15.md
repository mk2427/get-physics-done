---
lesson_id: L15
title: "Never Duplicate Derived Counts Across Tracking Docs"
tags: ["tracking"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L15: Never Duplicate Derived Counts Across Tracking Docs [tracking]
**Date**: 2026-04-15
**Trigger**: Tracking doc reviewer found report count, brief count, lesson count, and line counts duplicated across handoff, README, and todo — all stale after every fix round. 5 SERIOUS issues from a single systemic cause.
**Rule**: Designate ONE document (the handoff) as the sole authority for numeric counts. README and todo describe structure and status, not counts. The handoff is updated LAST at session end with verified counts from `wc -l` and `ls`. Other docs MUST NOT claim specific counts — they go stale immediately.
