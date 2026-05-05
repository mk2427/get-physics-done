---
lesson_id: L19
title: "Regime Matching in Monte Carlo Comparisons"
tags: ["comparison", "verification", "mc-benchmark"]
source: "bfss-bootstrap/tasks/lessons.md (verbatim per brief 002 §11 and brief 001 §9)"
---

### L19: Regime Matching in Monte Carlo Comparisons [comparison, verification, mc-benchmark]
**Date**: 2026-04-16
**Trigger**: Scaffolding iter-3 scenario walkthrough revealed knowledge doc 006 compares T=0 bootstrap against T=0.4, mu=0.5 Monte Carlo without prominent warning. CLAUDE.md Rule 43 requires regime matching but is buried deep in the rules list; without a tagged lesson, the injection mechanism (Rule 3) cannot deliver the requirement to verification agents.
**Rule**: Before comparing bootstrap bounds against Monte Carlo or other numerical results, explicitly verify ALL of: (a) gauge group match (SU(N) vs U(N)), (b) N value (infinite vs finite), (c) temperature (T=0 ground state vs finite T thermal), (d) BMN mass mu if applicable, (e) observable normalization (tr vs Tr, factors of N, energy vs length units). Any comparison that does not verify all five is SUSPECT and must be flagged. Knowledge doc values are often at finite T and BMN mass — not ground state. See CLAUDE.md Rule 43.
