<purpose>
Run one round of an adversarial Critic<->Fixer loop against a single artifact and emit three canonical outputs (`REVIEW.md`, `FIX.md`, `LOOP.md`).

This is the generic primitive consumed by every brief 002 component (knowledge docs, assertion docs, cluster/meta-audit, briefs, plans). It owns the severity adapter (brief §5.1) and the router (brief §5.2); the loop state machine (REVISE/APPROVED/ESCALATE) and `state.json` dual-write land in commit 4b.
</purpose>

<core_principle>
An adversarial review is *normalized* Critic output + *independent-assessor* Fixer response. "Normalized" = the Critic's native severity letters map through `core/adversarial_loop.adapt_severity` to canonical S/M/W/N + `blocking: bool` before any count is recorded, so every downstream consumer (canary gate, CI merge hook, `state.json`) sees the same stream. "Independent-assessor" = the Fixer reads source material (paper PDF for physics; artifact body for briefs/plans) and decides per-finding rather than rubber-stamping the Critic (`feedback_adversarial_fixers`).
</core_principle>

<required_reading>
@{GPD_INSTALL_DIR}/templates/adversarial-review-finding-schema.md
</required_reading>

<inputs>

Brief 002 §4.3 + brief 001 §3 schema:

```yaml
target:         <path>                     # artifact under review
charter:        <string | path>            # Critic charter
round:          <int>                       # 1-indexed; default 1
prior_findings: <path | null>               # seed findings for round > 1
autonomy:       strict | semi | full        # default: semi
artifact_kind:  brief | plan | physics | knowledge | assertion
parallel_critics: <bool>                    # speedup B (default: false)
pre_oracle:     <bool>                      # speedup C (default: false); plan 005
```

Per-round outputs (see `<outputs>`): `REVIEW.md`, `FIX.md`, `LOOP.md`.

</inputs>

<process>

<step name="resolve_target">
Resolve `<target-path>` to an absolute path. Default `artifact_kind=knowledge` for paths under `GPD/knowledge/`, `assertion` for `GPD/assertions/`, else require explicit `--artifact-kind`. Derive `<target-slug>` = basename without extension; per-round outputs live under `GPD/reviews/<target-slug>/`.
</step>

<step name="load_charter">
Treat `<charter-or-charter-file>` as a file path if it exists, else a literal string. The charter is the Critic's prompt scaffold (brief 001 §3).

Router dispatch:

- `artifact_kind=assertion` -> delegate to `core/adversarial_loop.route_assertion(frontmatter, sub_assertions, artifact_kind='assertion')` to obtain `[(sub_id, critic)]`. Each sub receives a sub-scoped charter; the top-level covers the doc-level claim.
- `artifact_kind=knowledge` -> single critic `gpd-knowledge-critic`.
- `artifact_kind in {brief, plan, physics}` (non-assertion) -> `gpd-adversarial-critic` with caller-supplied charter.

</step>

<step name="router_validation">
For assertion docs, `route_assertion` validates sub-assertion recursion depth (cap = 3) at router entry. A depth-4 nest raises `ValueError` and the workflow STOPS with a schema-validation error surfaced to the caller. Non-assertion kinds are a no-op here.
</step>

<step name="pre_oracle">
Plan 005 / speedup C: run the SymPy pre-oracle on kdoc equations before
round 1. Fires iff the workflow payload carries `pre_oracle: true` AND
`artifact_kind == "knowledge"` — the oracle only makes sense for
kdocs; any other artifact kind is a no-op.

No mutual-exclusion guard between `pre_oracle` and `parallel_critics`.
The plan 005 c0 dedup-key redesign
(`(kind, location, sha256(normalize(body))[:16])`) makes the two flags
compose safely: the oracle emits `kind: "oracle_falsified"` findings
that never collide with the parallel critics' finding kinds.

Step body:

1. **Preflight**: run `py -c "import sympy"`. On failure, emit a
   single W-level `ORACLE-DISPATCH-FAIL` finding into an otherwise-
   empty `GPD/reviews/<target-slug>/R0-REVIEW.md` (round-0, zero-
   indexed; distinct from the round-1 critic output `R1-REVIEW.md`)
   and skip to `critic_invocation`.

2. **Extract**: call
   `core/sympy_oracle.extract_equations_from_kdoc(<target-path>)` to
   obtain `[(eq_id, latex), ...]`. Zero equations → write an empty
   `R0-REVIEW.md` and skip to `critic_invocation`.

3. **Dispatch + Aggregate** (wrapped in `try / except / finally`):

   ```
   results: dict[str, OracleResult] = {}
   try:
       for eq_id, latex in equations:
           # Per-equation dispatch failure is ISOLATED: OracleDispatchError
           # becomes OracleResult(verdict="unevaluated", ...) and the
           # loop continues. Other exceptions escape and are handled by
           # the outer `except` below.
           result = _run_sympy_check(latex, py)
           result.equation_id = eq_id
           results[eq_id] = result
       safe_write_r0_review(<target-slug>, results,
                            partial=False, dispatch_error=None)
   except Exception as exc:
       safe_write_r0_review(<target-slug>, results,
                            partial=True, dispatch_error=str(exc))
       raise
   finally:
       # The writer is idempotent-by-guard on its first call; the
       # `finally` arm exists only to guarantee an atomic flush even
       # if the `except` arm itself raises.
       ...
   ```

   Per plan 005 §file 3 (iter-2-S1 partial-persist mechanism):
   `safe_write_r0_review(target_slug, results, partial, dispatch_error)`
   atomically writes `GPD/reviews/<target-slug>/R0-REVIEW.md` via
   `tmp.write_text(body); tmp.replace(final)` so no partial file ever
   appears on disk. When `partial=True`, the writer appends a W-level
   `ORACLE-DISPATCH-FAIL` finding with `dispatch_error` in `Problem:`.
   All `verified` / `falsified` results already accumulated in
   `results` are preserved verbatim.

   On workflow-level exception (not a per-equation
   `OracleDispatchError`), the writer flushes the partial results and
   re-raises. The orchestrator's step runner treats the re-raise as
   fail-open: logs the exception and continues to `critic_invocation`
   with the persisted `R0-REVIEW.md` as the round-0 artifact.

4. **Write**: `GPD/reviews/<target-slug>/R0-REVIEW.md` (round-0 review)
   contents follow the finding-schema template, populated per plan
   005 §Q3:
   - N-level informational entry per `verdict: verified` equation
     (`source: sympy_oracle`, `verdict: verified`, `blocking: false`).
   - S-level blocking entry per `verdict: falsified` equation
     (`kind: oracle_falsified`, `source: sympy_oracle`,
     `verdict: falsified`, `blocking: true`, counterexample in
     `Evidence:`).
   - W-level `ORACLE-DISPATCH-FAIL` entry on partial-persist flush.

5. **Hand-off**: `R0-REVIEW.md` is NOT passed via the workflow's
   generic `prior_findings` input — that channel is gated on
   `round > 1` per this spec's `<inputs>` declaration + the
   `critic_invocation` body's conditional on line "prior_findings if
   `round > 1`". Instead, `gpd-knowledge-critic`'s anti-anchoring
   block has a round-1-specific read directive (plan 005 §file 5 edit
   5b) that reads `R0-REVIEW.md` directly when it exists.

Acceptance: `grep -rn "run_pre_oracle\|R0-REVIEW" src/gpd/specs/` now
returns at least one hit inside this workflow spec (plan 005
acceptance criterion 1).
</step>

<step name="critic_invocation">
For each `(sub_id, critic)` row from the router:

1. Invoke the critic agent with the charter, the target (or sub-scoped fragment), and `prior_findings` if `round > 1`.
2. Capture native-letter findings (FATAL/SERIOUS/WARNING/MINOR + extras).
3. Call `adapt_severity` per finding -> canonical S/M/W/N + `blocking` flag.
4. Assign finding IDs matching `^iter-\d+-[SMWN]\d+$`. For compound docs, namespace with the sub-ID (e.g., `sub-2-iter-1-S1`) per `feedback_simple_finding_ids`.
5. If two critics returned findings on the same underlying issue, merge via `core/adversarial_loop.merge_findings` (MAX severity + OR of `blocking`).

Write the merged list to `GPD/reviews/<target-slug>/R{N}-REVIEW.md` following the finding-schema template.
</step>

<step name="parallel_critics">
When the orchestrator passes `parallel_critics: true` (speedup B), the
single critic invocation at `critic_invocation` is replaced by THREE
parallel invocations of the same critic agent, each with a distinct
`focus_area` parameter:

| `focus_area` | Finds | Severity emphasis |
|---|---|---|
| `equations` | Equation errors, wrong derivation steps, OCR hallucinations, wrong limits/asymptotics | S/M |
| `conventions` | Convention clashes, missing/conflicting notation, unit inconsistencies | M/W |
| `completeness` | Missing key results, incomplete derivation sketches, regime gaps, minor imprecision | W/N |

Dispatch rules:

1. Spawn the three critic invocations SIMULTANEOUSLY (orchestrator-side
   parallel sub-agent spawn; the critic agent's `<focus_area>` block
   scopes each instance to its assigned aspect).
2. Each parallel critic returns a list of findings restricted to its
   focus area.
3. Aggregate the three lists via
   `core/adversarial_loop.merge_parallel_findings(findings_a, findings_b, findings_c)`
   BEFORE passing to the Fixer. The merge key is
   `(location, equation_body[:60])`; same-key collisions reduce via
   `merge_findings` (MAX severity + OR of `blocking`); different keys
   UNION.
4. The merged list is then written to
   `GPD/reviews/<target-slug>/R{N}-REVIEW.md` exactly as in the
   serial-critic case — downstream consumers (Fixer, loop state
   machine, `state.json` writer) see an identical schema.

When `parallel_critics: false` (default) the workflow runs the
single-critic path at `critic_invocation` unchanged. The flag is a
performance toggle; correctness is preserved because the three focus
areas partition the review charter.
</step>

<step name="fixer_invocation">
Invoke the role-appropriate Fixer agent (paper-digester / knowledge-fixer / orchestrator-default).

The Fixer MUST:
- Read the source material (paper PDF for physics charter; artifact body for brief/plan) per L17.
- Independently assess each finding: `ACCEPTED`, `REVISED`, `REBUTTED`, or `ESCALATE` (`feedback_adversarial_fixers`).
- For `ACCEPTED` / `REVISED`, apply the fix (scoped_write) or queue for orchestrator if outside the Fixer's write scope.
- For `REBUTTED`, cite evidence; orchestrator adjudicates via `gpd-finding-adjudicator` (commit 4b).
- For `ESCALATE`, write an ESCALATE-UNRESOLVED line to `LOOP.md` and surface to user per `feedback_autonomous_loop`.

Write per-finding verdicts + applied diffs to `GPD/reviews/<target-slug>/R{N}-FIX.md`.
</step>

<step name="loop_summary">
Emit `GPD/reviews/<target-slug>/R{N}-LOOP.md`:

```yaml
round: <N>
artifact_kind: <kind>
counts: { S: <int>, M: <int>, W: <int>, N: <int>, open_blocking: <int> }
delta_vs_prior_round: { S: <int>, M: <int>, W: <int>, N: <int> }  # signed
verdict: REVISE | APPROVED | ESCALATE-UNRESOLVED
next_action: <string>
```

Verdict rules (authoritative in 4b; stubbed for 4a surface):

- `APPROVED` iff all counts zero AND `open_blocking == 0`
- `ESCALATE-UNRESOLVED` iff any `ESCALATE` in `FIX.md`
- `REVISE` otherwise

Iteration caps (enforced in 4b):

- `brief` / `plan`: round 2 that returns REVISE auto-escalates (`feedback_scaffold_as_we_go`)
- `physics` / `knowledge` / `assertion`: no cap (L20)

</step>

<step name="persist_outputs">
Do NOT write to `state.json` in commit 4a -- `adversarial_review_status` ships in 4b. The 4a surface stops at three markdown outputs per round.

Commit atomically:

```bash
gpd commit "review: R{N} on <target-slug> (<kind>; S=<s> M=<m> W=<w> N=<n>; verdict=<v>)" \
  --files "GPD/reviews/<target-slug>/R{N}-REVIEW.md" \
  --files "GPD/reviews/<target-slug>/R{N}-FIX.md" \
  --files "GPD/reviews/<target-slug>/R{N}-LOOP.md"
```

</step>

</process>

<success_criteria>
- Three markdown outputs exist at `GPD/reviews/<target-slug>/R{N}-{REVIEW,FIX,LOOP}.md`.
- Every finding in `REVIEW.md` has a canonical severity letter (S/M/W/N) + explicit `blocking` field.
- Every finding ID matches `^iter-\d+-[SMWN]\d+$` (sub-ID-namespaced for compound assertion docs).
- `LOOP.md` carries deterministic verdict `REVISE | APPROVED | ESCALATE-UNRESOLVED`.
- Recursion-depth cap of 3 is honored (depth 4 raises schema error before any critic is invoked).
</success_criteria>

<forbidden>
- DO NOT edit `code/gpd-adversarial-critic-v2.md`. The Stable Critic prompt is shared across callers; the adapter at `core/adversarial_loop.py` is the only permitted normalization surface (brief 002 §5.1).
- DO NOT treat the router as an LLM call. Selection is deterministic on frontmatter + sub-assertion presence (brief §5.2).
- DO NOT write to `state.json` in commit 4a. The `adversarial_review_status` dual-write lands in 4b.
- DO NOT rubber-stamp Critic findings in the Fixer step (`feedback_adversarial_fixers`).
- DO NOT drop the `blocking` flag when merging. OR of inputs is the policy (brief §5.1 (i)).
</forbidden>

<references>
- Brief 002 §4.3 (loop control), §5.1 (severity adapter), §5.2 (router), §7.3 (finding-ID regex)
- Brief 001 §3 (generic Critic<->Fixer loop primitive)
- `feedback_adversarial_critics`, `feedback_adversarial_fixers`, `feedback_autonomous_loop`, `feedback_simple_finding_ids`, `feedback_scaffold_as_we_go`, L17, L20
</references>
