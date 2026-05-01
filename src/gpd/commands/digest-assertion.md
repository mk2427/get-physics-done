---
name: gpd:digest-assertion
description: Create or review an assertion document from EQN-REF E-entry IDs or knowledge-doc K-labels; opt-in --adversarial flag routes the Draft through the /gpd:adversarial-review Critic<->Fixer loop (critic selected by §5.2 router) before promotion to Stable.
argument-hint: "<eqn-ref-entry-ids | knowledge-doc K-labels> [--adversarial]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
  - ask_user
---

<objective>
Create an assertion document in `GPD/assertions/` with a trust lifecycle
(Draft → Under Review → Stable → Superseded).

Assertion documents are reviewed equation restatements and derived-consequence
claims. Unlike knowledge docs, they carry four differential frontmatter fields
that pin them to the project's convention lock (brief 002 §3.4):

- `load_bearing` — whether the assertion is a load-bearing dependency for plans.
- `derivation_sketch` — derivation chain (required on derived-consequence; null
  on restated-equation).
- `upstream_ref_hash` — sha256 hash of the canonical equation form (required on
  restated-equation; null on derived-consequence).
- `upstream_status_mirror` — tracks the parent knowledge-doc lifecycle.

Input can be:

- EQN-REF E-entry IDs (e.g. `E.1 E.2`) — produces a restated-equation assertion.
- Knowledge-doc K-labels (e.g. `K-001`) — produces a restated-equation or
  derived-consequence assertion depending on the K-doc content (lead-equation
  fallback).
- Knowledge-doc K-label + equation ID (e.g. `K-001 K.5`) — produces a
  `restated-equation` assertion targeting equation `K.5` specifically inside
  kdoc `K-001`. This is the per-equation form used by the canary 1:N dispatch
  (one assertion per equation).
- A mix of E-entries and K-labels — produces a derived-consequence assertion.
- An existing `A-NNN` ID — opens the assertion for re-review.
</objective>

<flags>

Optional flags:

- `--adversarial` — opt-in. When present, route the Draft through the
  `/gpd:adversarial-review` Critic↔Fixer loop per brief 002 §4.1 step 7 before
  user promotion. The Draft is first produced by `gpd-assertion-digester`, then
  hardened to 0/0/0/0 via the critic selected by the §5.2 router:

  - `restated-equation` → `gpd-knowledge-critic` (verify equation vs EQN-REF
    E-entry + `upstream_ref_hash` + convention alignment).
  - `derived-consequence` → `gpd-adversarial-critic` (verify derivation steps,
    regime validity, non-empty `derivation_sketch`).
  - Compound / mixed-kind with sub-assertions → per-sub routing (restatement →
    knowledge-critic; derivation → adversarial-critic).

  When absent, the command follows the light path (Draft → user review → Stable
  on approval); zero behavior change for existing callers.

</flags>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/digest-assertion.md
</execution_context>

<adversarial_orchestration>

When `--adversarial` is present, dispatch to the adversarial-path step sequence
in the workflow (§adversarial_path). The four-step flow is:

**Argument parsing**: when the input matches `K-NNN K.X` (kdoc-id followed by a
space and an equation ID matching `K\.\d+` or `E\.\d+`), thread `equation_id:
K.X` to the digester agent invocation. When `equation_id` is absent (input is
just `K-NNN` or an `E.N` list), fall back to the lead-equation behavior.

1. `gpd-assertion-digester` produces the initial Draft assertion doc at
   `GPD/assertions/A-{NNN}-{slug}.md` (`status: Draft`). When `equation_id` is
   provided, the digester targets that equation specifically (see workflow
   §step-detect_input and the digester's Step 3) instead of selecting the
   kdoc's lead claim.
2. The §5.2 router (`route_assertion_critic` from `gpd.core.assertion_divergence`)
   selects the correct critic for the assertion kind.
3. `/gpd:adversarial-review` is invoked with:
   ```yaml
   target:           GPD/assertions/A-{NNN}-{slug}.md
   charter:          "<per-case charter from §5.2>"
   artifact_kind:    physics
   autonomy:         balanced
   artifact_critic:  <critic from router>
   ```
   The loop runs Critic↔Fixer (Fixer = `gpd-assertion-digester` in independent-
   assessor mode per `feedback_adversarial_fixers`) until SUCCESS (0/0/0/0 +
   zero open `blocking: true` findings).
4. Before writing `status: Stable`, the `upstream_ref_hash` CI gate runs:
   `assertion_divergence.check_divergence(...)` must return PASS. FAIL blocks
   promotion and surfaces the mismatch to the user.

`artifact_kind: physics` → no iteration cap (L20 + brief §9.2 002-new-M3).
`autonomy: balanced` → primitive `semi` mode (pause on stall; run otherwise).

On `ESCALATE-UNRESOLVED`: the assertion stays at `status: Under Review`; open
finding IDs are surfaced to the user for acknowledgment before any further action.

</adversarial_orchestration>

<context>
@GPD/CONVENTIONS.md
</context>
