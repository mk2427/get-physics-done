<purpose>
Create or review an assertion document in `GPD/assertions/` with a trust lifecycle
(Draft → Under Review → Stable → Superseded). Light path: digester produces Draft →
user reviews → promotes to Stable. Adversarial path: Draft → Critic↔Fixer loop per
`/gpd:adversarial-review` (critic selected by §5.2 router) → 0/0/0/0 APPROVED →
promote to Stable.
</purpose>

<required_reading>
@{GPD_INSTALL_DIR}/templates/assertion.md
</required_reading>

<input_schema>
The orchestrator passes the following fields when invoking this workflow:

```yaml
assertion_id:          "A-NNN"              # optional; assigned if absent
kind:                  "restated-equation | derived-consequence"
source_eqn_ref_entries: ["E.1", "E.2"]      # E-entry IDs from EQN-REF catalog
source_kdoc_ids:        ["K-001", "K-002"]   # K-labels from GPD/knowledge/
equation_id:           "K.5"                 # optional; when present with a single
                                             # kdoc-id input, the digester targets
                                             # this equation specifically (per-eq
                                             # 1:N dispatch path; see C12 amendment)
adversarial:           false                 # true when --adversarial flag set
```

All fields except `adversarial` are optional at invocation time; the workflow
prompts the user for any that are missing.
</input_schema>

<process>

<step name="detect_input">
Determine the assertion kind from the argument:

- **EQN-REF E-entry IDs** (e.g. `E.1`, `E.2`): `kind=restated-equation` path.
- **Knowledge-doc K-labels** (e.g. `K-001`): check whether the K-doc is `status: Stable`.
  If not Stable, surface to the user and halt; do NOT produce an assertion from a
  non-Stable knowledge doc.
- **Knowledge-doc K-label + equation ID** (e.g. `K-001 K.5`, `K-007 E.3`): the
  per-equation 1:N dispatch form used by the canary. Parse the second token as
  `equation_id` (matches `K\.\d+` or `E\.\d+`) and thread it to the digester so it
  targets that equation's body specifically rather than picking the kdoc's lead
  claim. `kind=restated-equation` always — the equation's canonical form is
  hashed verbatim.
- **Mixed**: `kind=derived-consequence` path when the caller provides both E-entries
  (or K-labels for the final equation) plus K-labels for the derivation chain.
- **A-NNN ID alone** (assertion already exists): open the existing assertion for
  re-review; skip to `check_existing`.
</step>

<step name="check_existing">
Check if `GPD/assertions/` exists and scan for an existing assertion for this topic:

```bash
ls GPD/assertions/A-*.md 2>/dev/null | sort
```

If a matching assertion exists, ask the user: update the existing doc or create a sibling?
</step>

<step name="validate_schema">
Before dispatching to any critic (and before spawning the digester on the adversarial
path), validate the assertion's sub-assertion depth using:

```python
from gpd.core.assertion_divergence import route_assertion_critic, AssertionDepthError
try:
    routing = route_assertion_critic(assertion_data)
except AssertionDepthError as exc:
    # Depth > 3 is a schema validation error — escalate to user before any loop.
    surface_to_user(str(exc))
    halt()
```

**Recursion depth cap**: sub-assertions may nest, but depth > 3 MUST escalate to
the user (do not enter the adversarial loop). The validator runs BEFORE dispatching.
</step>

<step name="assign_id">
Determine the next sequential assertion ID:

If the invocation supplies `assertion_id` or `reserved_assertion_id`, use that
numeric A-NNN and skip the filesystem scan for the next ID. This is the canary
mode contract: the orchestrator owns top-level A-NNN allocation. The digester may
append a slug but must not change the numeric prefix.

```bash
ls GPD/assertions/A-*.md 2>/dev/null | sort | tail -1
```

If no docs exist, start with `A-001`. Otherwise increment from the highest existing
NNN. Sub-assertion IDs within a doc follow `A-NNN.S{k}` (k is 1-indexed).

**ID scheme summary:**
- Top-level assertion: `A-NNN-slug` (e.g. `A-007-level-2-virial-bound`)
- Sub-assertion k of A-NNN: `A-NNN.S{k}` (e.g. `A-007.S1`, `A-007.S2`)
- Finding IDs: `A-NNN-iter-N-S1` (top-level) or `A-NNN.S2-iter-3-M1` (sub-assertion)
</step>

<step name="produce_draft">
Spawn `gpd-assertion-digester` to produce `GPD/assertions/A-{NNN}-{slug}.md`.

In canary mode, if `canary_dispatch_root`, `canary_output_root`, or
`canary_manifest_path` is supplied, write the assertion under the canary output
root instead of live `GPD/assertions/`, and return the actual path in
`gpd_return.files_written`.

The digester follows the restated-equation or derived-consequence path based on
the input kind:

**Restated-equation:**
- Copies `canonical_form` verbatim from the EQN-REF E-entry.
- Computes `upstream_ref_hash = sha256(normalize_eqn_body(canonical_form))`.
- Sets `derivation_sketch: null`.

**Derived-consequence:**
- Writes `derivation_sketch` with the full derivation chain from cited K-labels
  and E-entries.
- Sets `upstream_ref_hash: null`.

Create `GPD/assertions/` directory if needed:

```bash
mkdir -p GPD/assertions
```

Commit the Draft:

```bash
gpd commit "docs: add assertion A-{NNN}-{slug} (Draft)" \
  --files "GPD/assertions/A-{NNN}-{slug}.md"
```
</step>

<step name="upstream_ref_hash_gate">
Before promoting any assertion to `status: Stable`, run the divergence check:

```python
from gpd.core.assertion_divergence import check_divergence, DivergenceResult
from pathlib import Path

result: DivergenceResult = check_divergence(
    assertion_doc_path=Path("GPD/assertions/A-{NNN}-{slug}.md"),
    eqn_ref_catalog_path=Path("GPD/knowledge/013-equation-reference.md"),
)

if not result.passed:
    surface_to_user(
        f"upstream_ref_hash mismatch ({result.mismatch_reason}): "
        f"stored={result.stored_hash!r} computed={result.computed_hash!r}. "
        "Stable promotion BLOCKED. Correct the hash before re-attempting promotion."
    )
    halt()
```

**PASS** (``result.passed=True``) clears the gate and the workflow continues to
promotion. **FAIL** blocks Stable promotion; the mismatch is surfaced to the user.

For derived-consequence assertions with `upstream_ref_hash: null`, the check always
passes unconditionally (brief §7.3: no check needed when null).
</step>

</process>

<light_path>

## Light Path (no --adversarial flag)

After `produce_draft`:

### present_for_review

Present the Draft to the user:

1. Summarize the assertion (1–2 sentences: kind, equation, regime).
2. List the EQN-REF entries and K-labels cited.
3. Flag `upstream_ref_hash` value (restated-equation) or derivation sketch steps
   (derived-consequence).
4. Flag any traps or subtleties discovered.
5. Ask: "Review this assertion. Should I mark it Stable, revise it, or leave as Draft?"

### handle_review

Based on user response:

**"Stable" / approve:**
- Run `upstream_ref_hash_gate` (above); halt if FAIL.
- Update frontmatter: `status: Stable`, `last_reviewed: <today>`, `review_rounds: 1`.
- Commit: `gpd commit "docs: mark A-{NNN}-{slug} Stable" --files "GPD/assertions/A-{NNN}-{slug}.md"`

**Revise / changes requested:**
- Apply the requested changes.
- Re-present for review.
- Loop until approved or user says to leave as Draft.

**"Leave as Draft":**
- No changes. The document remains Draft for future review.

</light_path>

<adversarial_path>

## Adversarial Path (--adversarial flag)

When `--adversarial` is present, the `present_for_review` + `handle_review` steps
are REPLACED by the assertion adversarial Critic↔Fixer loop per brief 002 §4.1 step 7.
Steps `detect_input`, `check_existing`, `validate_schema`, `assign_id`, and
`produce_draft` run unchanged.

### adversarial_step_a — dispatch gpd-assertion-digester

Spawn `gpd-assertion-digester` to produce the initial Draft per `produce_draft` above.
The digester returns the path in `gpd_return.files_written`.

### adversarial_step_b — critic routing (§5.2 router)

Before dispatching to `/gpd:adversarial-review`, call:

```python
from gpd.core.assertion_divergence import route_assertion_critic
routing = route_assertion_critic(assertion_data)
```

The router implements all 5 cases from brief §5.2:

**Case 1** — `kind=restated-equation`, no sub-assertions:
→ single critic: `gpd-knowledge-critic`
  Charter: "verify equation matches EQN-REF E-entry, check `upstream_ref_hash`
  matches sha256(normalize_eqn_body(canonical_form)), check convention alignment"

**Case 2** — `kind=derived-consequence`, no sub-assertions:
→ single critic: `gpd-adversarial-critic`
  Charter: "verify derivation steps from cited K-labels + E-entries, check regime
  validity, check that `derivation_sketch` is non-empty and complete"

**Case 3** — Mixed-kind (empty top-level `derivation_sketch` + sub-assertions):
→ `route_assertion_critic` returns list of `(identifier, critic)` pairs.
  Top-level dispatched to `gpd-knowledge-critic`; each `A-NNN.S{k}` dispatched
  by sub-kind (restatement → knowledge-critic; derivation → adversarial-critic).

**Case 4** — Compound derived-consequence (non-empty `derivation_sketch` + sub-assertions):
→ Top-level to `gpd-adversarial-critic`; each sub routed by sub-kind (same
  recursion as case 3).

**Case 5** — Knowledge doc input (`source_kind="kdoc"`):
→ `gpd-knowledge-critic` (passthrough; knowledge docs may be cross-checked here).

### adversarial_step_c — invoke /gpd:adversarial-review

For each critic returned by the router, invoke the primitive:

```yaml
target:           GPD/assertions/A-{NNN}-{slug}.md
charter:          "<per-case charter string from §5.2 above>"
artifact_kind:    physics        # no iteration cap per L20 + brief §9.2 002-new-M3
autonomy:         balanced       # maps to primitive `semi` mode
artifact_critic:  <critic from router>
```

When the router returns a list (cases 3 and 4), each sub-assertion is dispatched to
its critic in the order returned by `route_assertion_critic`. Finding IDs use the
`A-NNN-iter-N-S1` / `A-NNN.S2-iter-3-M1` namespace per brief §5.2 iter-3-W1.

Review artifacts are written to `GPD/reviews/A-{NNN}-{slug}/R{N}-REVIEW.md`,
`R{N}-FIX.md`, `R{N}-LOOP.md`.

### adversarial_step_d — loop until SUCCESS

The primitive's state machine runs Critic → Fixer → Loop round N, incrementing
`review_rounds`, until `LoopState.SUCCESS` (all counts 0/0/0/0 AND zero open
`blocking: true` findings).

On SUCCESS:

1. Run `upstream_ref_hash_gate` (section above); halt on FAIL.
2. Transition assertion:
   ```yaml
   status: Stable
   last_reviewed: <today>
   review_rounds: <N>
   ```
3. Commit:
   ```bash
   gpd commit "docs: mark A-{NNN}-{slug} Stable (adversarial; N rounds)" \
     --files "GPD/assertions/A-{NNN}-{slug}.md"
   ```

Per `feedback_autonomous_loop`: run to 0/0/0/0 without per-round user approval;
surface only on convergence, stall, or genuine domain question (L20).

`artifact_kind: physics` → no iteration cap (L20 + brief §9.2 002-new-M3 resolution).

### adversarial_step_e — escalate on ESCALATE-UNRESOLVED

If any round returns `LoopState.ESCALATE_UNRESOLVED`:

1. Assert stays at `status: Under Review` (do NOT promote to Stable).
2. Open finding IDs persisted in `state.json::adversarial_review_status.blocking_findings_unresolved`.
3. Surface LOOP.md, open finding IDs, and escalation reason to user; wait for
   acknowledgment before any further action.

</adversarial_path>

<success_criteria>
- Assertion document exists in `GPD/assertions/` with valid frontmatter
- All four differential fields present: `load_bearing`, `derivation_sketch`,
  `upstream_ref_hash`, `upstream_status_mirror`
- `upstream_ref_hash` matches `sha256(normalize_eqn_body(canonical_form))` for
  restated-equation assertions, or is null for derived-consequence assertions
- Assertion ID matches `A-NNN-slug` format; sub-assertion IDs follow `A-NNN.S{k}`
- Status reflects actual review state
- Committed to git
</success_criteria>

<artifact_policy>
- **Artifact kind**: `physics` — no iteration cap per L20 + brief §9.2 002-new-M3.
- **Autonomy**: `balanced` — consistent with `/gpd:digest-knowledge --adversarial`.
- **Finding ID namespace**: `A-NNN-iter-N-S1` (top-level) or `A-NNN.S2-iter-3-M1`
  (sub-assertion 2 of A-NNN, iter-3 moderate finding 1) per `feedback_simple_finding_ids`.
- Only `Stable` assertions may be cited as dependencies in downstream plans
  (plan frontmatter `requires_assertion: [A-NNN, ...]`).
- `load_bearing: true` is monotonic — once Stable with `load_bearing: true`, the
  assertion cannot be demoted without explicit supersession.
</artifact_policy>
