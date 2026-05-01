# Changelog

All notable changes to Get Physics Done are documented here.

## vNEXT

- Add `gpd-finding-adjudicator` agent + adversarial-review loop state machine + `state.json` `adversarial_review_status` block (commit 4b, brief 002 §5.1 (ii)-(iv)). The adjudicator is the third-agent load-bearing-claim tiebreaker per `feedback_adjudicate_load_bearing` (anti-anchoring: form independent position from primary sources before reading either prior report; verdicts SUSTAINED / PARTIALLY-SUSTAINED / REJECTED / INCONCLUSIVE). `core/adversarial_loop.py` gains a `LoopState` enum + `next_loop_state` controller (`IDLE -> IN_PROGRESS -> REVISE | SUCCESS | ESCALATE-UNRESOLVED`: REVISE while any `blocking: true` finding is open, SUCCESS at 0/0/0/0 AND empty blocking list, ESCALATE-UNRESOLVED at iteration cap per `feedback_autonomous_loop`), a `check_merge_allowed` CI merge-hook helper returning `(False, 412, reason)` fail-closed while blocking findings are open, and an `update_blocking_findings` writer that validates finding IDs against `^iter-\d+-[SMWN]\d+$` (or the namespaced `<sub_id>-iter-N-<SMWN>N` per `feedback_simple_finding_ids`) before persisting. `core/state.py` adds a new `AdversarialReviewStatus` pydantic model as a top-level key in `ResearchState` with dual-write discipline: `generate_state_markdown`, `parse_state_md`, `parse_state_to_json`, and `sync_state_json_core` all preserve `adversarial_review_status.blocking_findings_unresolved` through the `state.json <-> STATE.md <-> state.json` cycle.
- Add `/gpd:adversarial-review` primitive (commit 4a, brief 002 §2 component #2): reusable Critic<->Fixer loop skill + workflow + finding-schema template + severity adapter + router. `core/adversarial_loop.py` normalizes the Stable `gpd-adversarial-critic` prompt's native FATAL/SERIOUS/WARNING/MINOR into orchestrator-canonical S/M/W/N with a propagating `blocking: bool` flag (brief §5.1); Critic-vs-Critic merge policy is MAX severity + OR of `blocking`. Router deterministically dispatches assertion docs onto the 5-case table in brief §5.2 (restated-equation, derived-consequence, mixed-kind, compound-derived-consequence, knowledge-doc); recursion depth capped at 3 with schema-validation error on depth-4 nests. Loop state machine + `state.json` dual-write land in commit 4b.
- Split releases into a manual release-PR preparation workflow and a separate publish workflow for PyPI, npm, tags, and GitHub Releases.
- Add gpd-adversarial-critic agent: strategic adversarial critic that challenges research direction through 5 strategic challenges (alternative explanation construction, assumption stress-testing, strategic direction, error blast-radius mapping, robustness assessment). Includes anti-anchoring protocol, iterative refinement with convergence criteria, and structured 7-section verdict format.
### Knowledge Trust & Blast Radius (experimental/knowledge-trust-full)

Six-component feature set for knowledge-doc adversarial digestion, assertion promotion, and error blast-radius tracking. Developed on PSI fork; canary-gated before upstream contribution.

**Components**:
1. **Knowledge-doc artifact type** — `GPD/knowledge/` with Draft→Stable trust lifecycle; `gpd-knowledge-critic` adversarial review
2. **`/gpd:adversarial-review` primitive** — generic Critic↔Fixer loop with S/M/W/N severity adapter; `gpd-finding-adjudicator` tie-breaker
3. **`/gpd:digest-knowledge --adversarial`** — per-paper digest with per-cluster + meta-audit phases; `gpd-cluster-auditor` + `gpd-meta-auditor` + `gpd-eqnref-integrator` agents; `gpd-conventions` MCP auto-fire on 0/0/0/0
4. **Assertion doc lifecycle** — `GPD/assertions/` with `A-NNN` ID scheme; `/gpd:digest-assertion`; `sha256` upstream-ref-hash divergence gate; §5.2 router (5 cases); recursion depth cap 3
5. **Assertion status lock** — `assertion_status_lock()` wrapper over `utils.file_lock`; `write_upstream_divergence_with_cascade` 3-step rollback
6. **Error blast-radius** — `result_downstream()` reverse BFS; `knowledge_invalidation_scan` + `assertion_invalidation_scan` + DAG cycle detection; `invalidation_events` state.json dual-write; reactive triggers on kdoc/assertion status changes
7. **`/gpd:new-project` hooks** — M1.6 knowledge stabilization + M1.7 assertion promotion Y/n prompts; `--no-knowledge-hook` / `--no-assertion-hook` bypass flags
8. **BFSS canary scaffolding** — 16-PDF SHA256 manifest; `run-bfss-canary.py` orchestrator with `BudgetTracker`; six §7 structural criteria

- Add knowledge/assertion schema extensions (default off): `assertion.md` template, `ASSERTION_DIR_NAME` + `ProjectLayout.assertion_dir`, `IntermediateResult.knowledge_deps`/`assertion_deps`, `PlanValidation.requires_knowledge`/`requires_assertion`, `knowledge_gate`/`assertion_gate` enums + config knobs (independent, off|warn|block), `normalize_eqn_body` canonicalizer (brief 002 §3.4.1 pipeline a-e; multi-index symmetry skipped), `planner_artifacts.check_plan_{knowledge,assertion}_prereqs` helpers, meta-audit controlled-vocab template, 21 BFSS lesson files under `references/lessons/`. Adds `pylatexenc>=2.10` dependency.

## v1.1.0

- Public open-source release.
- Multi-runtime support for Claude Code, Gemini CLI, Codex, and OpenCode.
- Structured physics research workflows for planning, execution, verification, and publication support.
