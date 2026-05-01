<purpose>
Create or update a reviewed knowledge document in `GPD/knowledge/`. Light path: research the topic, write a Draft, present for user review, promote to Stable on approval.
</purpose>

<required_reading>
@{GPD_INSTALL_DIR}/templates/knowledge.md
</required_reading>

<process>

<step name="detect_input">
Determine input type from the argument:

- **arXiv ID** (matches `DDDD.DDDDD` or `DDDD.DDDDD` with optional `v\d+` suffix):
  1. First check for a local companion file in the project's `references/` directory
     (look for `references/{arxiv_id}.md`, `references/{arxiv_id}.tex`, and
     `references/{arxiv_id}.txt` in that preference order).
  2. If a local companion exists, read it directly — do **not** fetch from the web.
     This avoids PDF parsing and is faster.
  3. If no local companion is found, fall back to fetching via web_search/web_fetch.
- **File path** (exists on disk): read the file as source material
- **Topic string** (everything else): research the topic via web_search

</step>

<step name="check_existing">
Check if `GPD/knowledge/` exists and scan for existing knowledge docs on this topic:

```bash
find GPD/knowledge -name "*.md" 2>/dev/null || echo "NO_KNOWLEDGE_DIR"
```

If a related doc exists, ask the user: update the existing doc or create a new one?
</step>

<step name="assign_id">
Determine the next sequential ID:

```bash
ls GPD/knowledge/K-*.md 2>/dev/null | sort | tail -1
```

If no docs exist, start with `K-001`. Otherwise increment from the highest existing number.
</step>

<step name="research">
Research the topic thoroughly:

1. If arXiv paper: read the paper, extract key results, equations, conventions
2. If topic: search for authoritative sources (textbooks, review articles, seminal papers)
3. For every method or result cited, read the actual source — do not rely on training knowledge alone
4. Identify convention choices and flag any clashes between sources
5. Note traps and subtleties — what could go wrong if someone uses this knowledge carelessly?

Cross-reference with `GPD/CONVENTIONS.md` to ensure consistency with project conventions.
</step>

<step name="write_draft">
Create `GPD/knowledge/` directory if needed:

```bash
mkdir -p GPD/knowledge
```

Write the knowledge document following the template at `{GPD_INSTALL_DIR}/templates/knowledge.md`.

Set `status: Draft` in the frontmatter. All sections are required — if you don't have content for a section, write "None identified" rather than omitting it.

```bash
gpd commit "docs: add knowledge doc K-{NNN}-{slug} (Draft)" --files "GPD/knowledge/K-{NNN}-{slug}.md"
```
</step>

<step name="present_for_review">
Present the Draft to the user:

1. Summarize what the document covers (2-3 sentences)
2. List the key results found
3. Flag any conventions that required a choice
4. Flag any traps or subtleties discovered
5. Ask: "Review this knowledge document. Should I mark it Stable, revise it, or leave as Draft?"

</step>

<step name="handle_review">
Based on user response:

**"Stable" / approve:**
- Update frontmatter: `status: Stable`, `last_reviewed: [today]`, `review_rounds: 1`
- Commit: `gpd commit "docs: mark K-{NNN}-{slug} Stable" --files "GPD/knowledge/K-{NNN}-{slug}.md"`

**Revise / changes requested:**
- Apply the requested changes
- Re-present for review
- Loop until approved or user says to leave as Draft

**"Leave as Draft":**
- No changes. The document remains Draft for future review.

</step>

</process>

<success_criteria>
- Knowledge document exists in `GPD/knowledge/` with valid frontmatter
- All template sections present (even if "None identified")
- Conventions cross-referenced with CONVENTIONS.md
- Status reflects actual review state (Draft if unreviewed, Stable if user approved)
- Committed to git
</success_criteria>

<adversarial_path>

When the caller passes `--adversarial` to `/gpd:digest-knowledge`, the
light-path present-for-review + handle-review steps are REPLACED by the
per-paper adversarial Critic<->Fixer loop per brief 002 §4.1 step 2. Steps
`detect_input`, `check_existing`, `assign_id`, `research`, and `write_draft`
run unchanged; the Draft kdoc exists on disk before the adversarial loop
starts.

### adversarial_step_a — dispatch gpd-paper-digester

Spawn `gpd-paper-digester` to produce the initial Draft `GPD/knowledge/K-{NNN}-{slug}.md`.
The digester is the independently-addressable agent form of the light-path
`write_draft` step (brief 001 iter-1-W1 resolution): same content discipline
(L9 no-raw-OCR; L17 independent verification against source PDF; L15 no
duplicated derived counts), same template sections, same `status: Draft` at
emit. The digester returns the path in `gpd_return.files_written`.

**Existing-kdoc handling on the adversarial path.** On the light path
the orchestrator can route the digester's `status: blocked`
(pre-existing kdoc) through an `ask_user` prompt. On the adversarial
path there is no user-facing prompt — `--adversarial` on an existing
kdoc means "harden what's there". The orchestrator MUST therefore:

1. Run `check_existing` normally.
2. If an existing kdoc for this paper is found, skip the digester's
   pre-existing-kdoc block and pass `update_in_place: true` +
   `target_kdoc_path: <existing path>` to the digester instead of
   letting it emit `status: blocked`. The digester then uses the
   existing kdoc as the Draft target (updating it in place under the
   same `K-{NNN}` ID) for step (a), and step (b) proceeds with that
   kdoc as the target of the Critic ↔ Fixer loop.
3. If no existing kdoc is found, assign a fresh ID per `assign_id` and
   spawn the digester normally.

### adversarial_step_b — invoke /gpd:adversarial-review

Invoke the primitive with this invocation schema (brief 002 §4.3, §5):

```yaml
target:           GPD/knowledge/K-{NNN}-{slug}.md
charter:          "find equation errors, convention-mismatches, OCR hallucinations, internal contradictions"
artifact_kind:    physics                       # no iteration cap per L20
autonomy:         balanced                      # maps to primitive `semi` mode
artifact_critic:  gpd-knowledge-critic          # brief §5 table per-paper row
```

The router (`core/adversarial_loop.py`) treats `artifact_kind=physics` with
a knowledge-doc path prefix (`GPD/knowledge/`) as the knowledge-doc case
and dispatches `gpd-knowledge-critic` as the single critic (brief §5.2
"Knowledge docs: route to existing `gpd-knowledge-critic` (unchanged)").
The Fixer role is filled by `gpd-paper-digester` operating in
independent-assessor mode per `feedback_adversarial_fixers`: the digester
reads the source PDF for each finding, decides `ACCEPTED | REVISED |
REBUTTED | ESCALATE`, and applies scoped edits to the kdoc in place.

### adversarial_step_c — loop until SUCCESS

The primitive's state machine (commit 4b `LoopState.next_loop_state`) runs
Critic → Fixer → Loop round N, incrementing `review_rounds`, until:

- `LoopState.SUCCESS` — all counts zero (0/0/0/0) AND
  `adversarial_review_status.blocking_findings_unresolved` is empty.
- Every round writes `R{N}-REVIEW.md`, `R{N}-FIX.md`, `R{N}-LOOP.md` under
  `GPD/reviews/K-{NNN}-{slug}/`.

On SUCCESS, transition the kdoc:

```yaml
status: Stable
last_reviewed: <today>
review_rounds: <N>
```

and commit:

```bash
gpd commit "docs: mark K-{NNN}-{slug} Stable (adversarial; N rounds)" \
  --files "GPD/knowledge/K-{NNN}-{slug}.md"
```

`present_for_review` and `handle_review` from the light path are skipped —
the adversarial loop IS the review, and the user sees the LOOP.md trail
rather than an inline Y/n prompt. Per `feedback_autonomous_loop`, once the
brief is APPROVED the loop runs to 0/0/0/0 without per-round user approval.

### adversarial_step_d — escalate on ESCALATE-UNRESOLVED

If any round returns `LoopState.ESCALATE_UNRESOLVED` (adjudicator dispatch
returns `INCONCLUSIVE`, or a Critic<->Fixer disagreement exceeds what
`gpd-finding-adjudicator` can resolve at the dispatched tier, or a genuine
physics-convention / scope / MUST-vs-SHOULD ambiguity surfaces per L20):

1. The kdoc stays at `status: Under Review` (do NOT promote to Stable).
2. Open finding IDs are persisted in
   `state.json::adversarial_review_status.blocking_findings_unresolved`
   per commit 4b dual-write.
3. Surface the LOOP.md, the open finding IDs, and the escalation reason to
   the user; wait for user acknowledgment before any further action.

No iteration cap applies (L20): `artifact_kind=physics` loops forever if
findings keep resolving — escalation fires only on genuine ambiguity, not
on a round count.

### adversarial_phase_3 — cluster audits

Phase 3 runs ONCE every kdoc in the project has transitioned to
`status: Stable` via the per-paper loop above. The workflow partitions the
Stable kdoc set into clusters:

1. **Explicit partition** — if `GPD/meta-audit/clusters.json` exists, use
   its `{cluster_id: [kdoc_id, ...]}` mapping verbatim.
2. **Auto-partition** — else, group by the `cluster:` / `topic_cluster:`
   frontmatter tag on each kdoc. Kdocs without a cluster tag fall into
   a default cluster `unclustered`, which the cluster auditor flags as
   an S-level finding for the user to resolve before meta-audit.

For each cluster, spawn `gpd-cluster-auditor` with this invocation:

```yaml
cluster_id:       <string>
cluster_kdocs:    ["GPD/knowledge/K-{NNN}-{slug}.md", ...]
charter:          "find cross-paper convention drift, restatement disagreements, and typo-verdict contradictions within the cluster"
artifact_kind:    physics
autonomy:         balanced
```

The cluster auditor runs the `/gpd:adversarial-review` primitive
internally on each cross-paper finding batch (Critic↔Fixer loop per
brief 002 §5). On SUCCESS it emits
`GPD/reviews/<cluster>/cluster-audit.md` following the §§1–8 cluster
audit schema (same shape as the meta-audit schema at
`{GPD_INSTALL_DIR}/templates/meta-audit-schema.md` but scoped to one
cluster). Phase 3 blocks on every cluster auditor returning APPROVED.

Phase 3 is SKIPPED on the light path (no `--adversarial` flag). A project
that wants cluster audits without the per-paper adversarial digest may
invoke `gpd-cluster-auditor` directly via `/gpd:adversarial-review`.

### adversarial_phase_4 — cross-cluster meta-audit

Phase 4 runs ONCE every cluster in the project has a committed
`GPD/reviews/<cluster>/cluster-audit.md`. Spawn `gpd-meta-auditor` with:

Resolve the `controlled_vocab` path before spawning: if
`GPD/meta-audit/controlled-vocab.md` exists in the project, pass that
path; otherwise fall back to
`{GPD_INSTALL_DIR}/references/meta-audit/controlled-vocab.md` (the
installed template). The integrator-side schema expects a single
resolved path, not a disjunction.

```yaml
cluster_audit_reports: ["GPD/reviews/<cluster_id>/cluster-audit.md", ...]
controlled_vocab:      "<resolved path per the rule above>"
charter:               "consolidate every cluster-audit row into a project-wide convention-lock proposal set; surface residuals to the adjudication queue; emit meta-audit-report.md per §§1–8 schema"
```

The meta-auditor invokes the grouping helpers in
`gpd.core.meta_audit` via `py -c` shell-outs (subagents cannot import
Python directly; see `agents/gpd-meta-auditor.md` Steps 3–5 for the
exact invocations):

- `canonical_signature(eqn_body)` — sha256 over commit-3-normalized
  equation body (reuses `normalize_eqn_body`); groups equivalent axes.
- `topic_keyword_group(rows, vocab)` — keyword match on controlled-vocab
  seed; groups rows without a canonical-signature hit.
- `append_to_candidate_axes(row, path)` — appends ungrouped rows to
  `GPD/meta-audit/candidate-axes.md` for the `/gpd:adversarial-review`
  adjudication pass that closes the brief §1 item 4 W5 pick.

On SUCCESS the meta-auditor emits:

- `GPD/meta-audit/meta-audit-report.md` following the §§1–8 schema at
  `{GPD_INSTALL_DIR}/templates/meta-audit-schema.md`.
- `GPD/meta-audit/candidate-axes.md` (append-only) for every residual
  row surfaced.

Phase 4 is SKIPPED on the light path. It is the single non-optional
prerequisite for emitting a `convention_set` MCP call against the
project's `state.json::convention_lock` axis table; without it, axis
IDs may not align between `GPD/CONVENTIONS.md` and downstream derivation
scaffolding.

Both phases 3 and 4 are gated by the same `--adversarial` flag that
triggered the per-paper loop; the light path's
`present_for_review` + `handle_review` steps remain the default end state
when the flag is absent.

### adversarial_phase_5 — EQN-REF integration

Phase 5 runs ONCE the meta-audit (phase 4) has emitted
`GPD/meta-audit/meta-audit-report.md` with verdict `APPROVED`.

**Phase 5 is SKIPPED on the light path** (no `--adversarial` flag). It is
the final automated step in the adversarial workflow; the user sees the
EQN-REF document and optionally triggers convention lock via
`--auto-fire-conventions`.

#### Phase 5 entry condition

- Phase 4 has completed and `GPD/meta-audit/meta-audit-report.md` exists.
- The meta-audit report's verdict is `APPROVED` (0/0/0/0 AND zero open
  `blocking: true` findings). If the verdict is not APPROVED, phase 5 is
  skipped and the workflow surfaces the unresolved meta-audit findings to
  the user before any further action.

#### Phase 5 invocation

Spawn `gpd-eqnref-integrator` with this invocation schema:

```yaml
meta_audit_report:   "GPD/meta-audit/meta-audit-report.md"
fire_conventions:    <true if --auto-fire-conventions flag set, else false>
dry_run:             <true if --dry-run flag set, else false>
revert:              <true if --revert flag set, else false>
```

The integrator returns `gpd_return.status: completed` on success.

#### Phase 5 outputs

On success, the integrator emits one of:

- `GPD/knowledge/013-equation-reference.md` (single-file layout, ≤ 600
  estimated lines), OR
- `GPD/knowledge/013-equation-reference.md` (umbrella index) +
  `GPD/knowledge/013-part-a-convention-lock.md` +
  `GPD/knowledge/013-part-b-equation-catalog.md` +
  `GPD/knowledge/013-part-c-typos-questions-traps.md` (umbrella layout,
  > 600 estimated lines).

When `--auto-fire-conventions` is set AND the auto-fire guard passes (see
`gpd-eqnref-integrator` `<auto_fire_guard>`), the integrator also writes
one revlog entry per axis to
`GPD/knowledge/revlogs/eqn-ref-integrator.jsonl`.

#### Phase 5 preflight (--dry-run)

When `--dry-run` is set, the integrator emits the EQN-REF document but
makes zero MCP calls and writes zero revlog entries. The preflight summary
(axes count, projected MCP calls, `fire_conventions_would_trigger`) is
returned in `gpd_return.dry_run_preflight` and surfaced to the user so they
can review before a production auto-fire run.

#### Phase 5 revert (--revert)

When `--revert` is set, the integrator skips EQN-REF generation and instead
restores the prior convention lock from the most recent `run_id` group in
`GPD/knowledge/revlogs/eqn-ref-integrator.jsonl`. The user is prompted for
explicit confirmation before any `convention_set` MCP calls are made.

</adversarial_path>
