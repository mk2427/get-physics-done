---
lesson_id: L9
title: "MCP OCR Output Is Not Trustworthy for Equations"
tags: ["papers", "equations"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L9: MCP OCR Output Is Not Trustworthy for Equations [papers, equations]
**Date**: 2026-04-15
**Trigger**: All 11 knowledge docs were built from arXiv MCP output, which garbles equations via OCR. Agent 005 critic found that (7-4sqrt(3))/256 was evaluated as ~0.06546 when the actual value is ~0.000280 — likely an OCR transcription error.
**Rule**: Never use raw MCP output as ground truth for equations. Always verify against the original PDF. Mark unverified equations as [EXTRACTED - VERIFY AGAINST PDF].
