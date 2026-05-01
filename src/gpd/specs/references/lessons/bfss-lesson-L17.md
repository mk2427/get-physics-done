---
lesson_id: L17
title: "MCP OCR Digestion Is Catastrophically Unreliable"
tags: ["papers", "knowledge", "review"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L17: MCP OCR Digestion Is Catastrophically Unreliable [papers, knowledge, review]
**Date**: 2026-04-15
**Trigger**: All 11 knowledge docs reviewed. 30 Fatals, 44 Serious. Every single doc has multiple Fatal errors. Digester agents hallucinated equations from garbled OCR — invented coefficients, fabricated closed-form expressions, reversed metric exponents, inserted spurious factors. Zero docs approved.
**Rule**: NEVER trust knowledge docs built from MCP OCR without adversarial review against the source paper. The review MUST verify every equation numerically, not just visually. Fixer agents MUST read the actual source paper, not just the review report. The pdf_to_md.py pipeline should be used but is plain-text only — equations will still need manual/PDF verification for critical results.
