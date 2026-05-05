---
name: gpd:digest-knowledge
description: Create or update a reviewed knowledge document from a topic, paper, or existing research; opt-in --adversarial flag routes the Draft through the /gpd:adversarial-review Critic<->Fixer loop before promotion.
argument-hint: "<topic or arXiv-ID> [--adversarial]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
  - web_search
  - web_fetch
  - ask_user
---

<objective>
Create a knowledge document in `GPD/knowledge/` with a trust lifecycle (Draft → Stable).

Knowledge documents capture reviewed domain understanding — key results, equations,
conventions, derivation sketches, and traps. Unlike one-shot RESEARCH.md reports,
knowledge documents are project-scoped and carry an explicit trust status.

Input can be:
- An arXiv ID (e.g., `2301.12345`) — fetch and digest the paper
- A topic (e.g., `"Fuchsian ODE methods"`) — research and synthesize
- A file path to an existing document to digest
</objective>

<flags>

Optional flags:

- `--adversarial` — opt-in. When present, route the Draft through the
  `/gpd:adversarial-review` Critic<->Fixer loop per brief 002 §4.1 step 2 before
  user promotion. The Draft is first produced by `gpd-paper-digester` (same
  content discipline as the light path, L9/L17), then hardened to 0/0/0/0 via
  the `gpd-knowledge-critic` charter ("find equation errors, convention
  mismatches, OCR hallucinations, internal contradictions") per brief 002 §5
  table. When absent, the command follows the light path exactly as before
  (zero behavior change for existing users).

- `--auto-fire-conventions` — after the EQN-REF document is produced at
  phase 5 and the meta-audit reached APPROVED (0/0/0/0 with zero open
  blocking findings), invoke `convention_set` MCP per axis in the EQN-REF
  §1 Convention Lock. No-op if the meta-audit verdict is not APPROVED;
  no-op if `--adversarial` is absent (phase 5 is skipped on the light path).
  Passes `fire_conventions: true` to `gpd-eqnref-integrator`.

- `--dry-run` — produce the EQN-REF artifact without firing any
  `convention_set` MCP calls and without writing revlog entries. Emits a
  preflight estimate summary in the integrator return payload:
  `axes_count`, `estimated_tokens`, `projected_convention_set_calls`, and
  `fire_conventions_would_trigger` (boolean: would the auto-fire guard pass
  if re-run with `--auto-fire-conventions` and without `--dry-run`?).
  Passes `dry_run: true` to `gpd-eqnref-integrator`.

- `--revert` — roll back the last `convention_set` batch by reading the
  most recent `run_id` group from
  `GPD/knowledge/revlogs/eqn-ref-integrator.jsonl` and restoring each
  axis to its `prior_value`. Requires an explicit user confirmation prompt
  before any MCP writes. Axes whose `prior_value` is `null` (first-ever
  lock for that axis) are skipped with a warning. Passes `revert: true`
  to `gpd-eqnref-integrator`.

</flags>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md
</execution_context>

<adversarial_orchestration>

When `--adversarial` is present, dispatch to the adversarial-path step
sequence in the workflow (§adversarial_path). The four-step flow is:

1. `gpd-paper-digester` produces the initial Draft knowledge doc at
   `GPD/knowledge/K-{NNN}-{slug}.md` (light-path content, `status: Draft`).
2. `/gpd:adversarial-review` is invoked with
   `{target: <kdoc path>, charter: "<brief 002 §5 charter>",
     artifact_kind: physics, autonomy: balanced,
     artifact_critic: gpd-knowledge-critic}`. The loop runs
   Critic (`gpd-knowledge-critic`) ↔ Fixer (`gpd-paper-digester` acting as
   independent-assessor fixer per `feedback_adversarial_fixers`) with the
   loop state machine from commit 4b.
3. Loop iterates per the primitive's state machine until SUCCESS
   (0/0/0/0 + zero open `blocking: true`). On SUCCESS the kdoc transitions
   to `status: Stable` (per the light path's promotion rule) and
   `review_rounds: <N>` records the round count.
4. On `ESCALATE-UNRESOLVED` (adjudicator dispatch inconclusive, or genuine
   ambiguity per L20) the kdoc stays at `status: Under Review` and the
   `/gpd:adversarial-review` primitive surfaces the open finding IDs to the
   user for acknowledgment before any further action.

`artifact_kind: physics` inherits the no-iteration-cap policy (L20). The
default `autonomy: balanced` maps to the primitive's `semi` loop-controller
mode (pause on stall; run otherwise).

</adversarial_orchestration>

<context>
@GPD/CONVENTIONS.md
</context>
