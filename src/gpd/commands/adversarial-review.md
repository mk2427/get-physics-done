---
name: gpd:adversarial-review
description: Run a Critic<->Fixer adversarial review loop against any artifact (brief, plan, knowledge doc, assertion doc) with a caller-supplied charter; normalizes Critic severities and dispatches by artifact kind.
argument-hint: "<target-path> <charter-or-charter-file>"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
---

<objective>
Run one or more rounds of an adversarial Critic<->Fixer loop against a single artifact. Produces three per-round outputs (`REVIEW.md`, `FIX.md`, `LOOP.md`) and normalizes all Critic severities through the read-only adapter at `core/adversarial_loop.py` so downstream counters (canary gate, CI merge hook, `state.json`) see a consistent S/M/W/N + `blocking: bool` stream.

This is the generic primitive under brief 002's umbrella -- consumed by `/gpd:digest-knowledge --adversarial` (per-paper, cluster, meta-audit), `/gpd:digest-assertion` (restatement, derivation, compound), and any future GPD loop (plans, reports, manuscripts).
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/adversarial-review.md
</execution_context>

<inputs>

Required positional arguments:

1. `<target-path>` -- artifact under review (knowledge doc, assertion doc, plan, brief, or any stable-framed text).
2. `<charter-or-charter-file>` -- literal charter string (quoted) OR path to a markdown file whose body is the charter. Per brief 001 §3 the charter is the Critic's prompt scaffold: what to attack, what counts as a finding, what is out-of-scope.

Canonical charter variants (brief 002 §5):

| `artifact_kind` | Charter (abbreviated) |
|---|---|
| `physics` (per-paper knowledge) | "find equation errors, convention-mismatches, OCR hallucinations, internal contradictions" |
| `physics` (cluster/meta-audit) | "find cross-paper convention contradictions, terminology drift, missing axes" |
| `physics` (assertion) | see `core/adversarial_loop.py::route_assertion` for kind-dependent dispatch |
| `brief` / `plan` | Caller-supplied; 2-round cap per `feedback_scaffold_as_we_go` |

Optional flags:

- `--round N` -- resume from round N (default 1). Round N-1 outputs must exist.
- `--prior-findings <path>` -- seed round N with prior findings.
- `--autonomy <mode>` -- `strict` (pause each round), `semi` (default; pause on stall), `full` (run to 0/0/0/0 without pause per `feedback_autonomous_loop`).
- `--artifact-kind <k>` -- one of `brief`, `plan`, `physics`, `knowledge`, `assertion`. Inferred from target path if omitted.
- `--parallel-critics` -- Spawn three parallel critics (equations/conventions/completeness focus) per round instead of one serial critic. Faster for long kdocs; accuracy is preserved since all aspects are covered. Passes `parallel_critics: true` to the workflow.
- `--pre-oracle` -- Run SymPy pre-oracle on kdoc equations before round 1. Pre-verified equations are skipped by the critic. Pre-falsified equations are seeded as round-0 findings. Reduces rounds needed for equation-heavy docs. Implemented by `core/sympy_oracle.run_pre_oracle` + `oracle_results_to_findings` (re-exported from `core/adversarial_loop`). Passes `pre_oracle: true` to the workflow.

</inputs>

<outputs>

Per round N, written under `GPD/reviews/<target-slug>/`:

- `R{N}-REVIEW.md` -- Critic's findings list, adapter-normalized to S/M/W/N with `blocking: bool`.
- `R{N}-FIX.md` -- Fixer's per-finding `ACCEPTED` / `REVISED` / `REBUTTED` / `ESCALATE` verdicts + diffs.
- `R{N}-LOOP.md` -- round summary: counts, delta vs prior round, verdict `REVISE | APPROVED | ESCALATE-UNRESOLVED`.

At convergence the workflow emits `APPROVED.md` pointing at the final round and confirming 0/0/0/0 + zero open blocking findings.

</outputs>

<severity_adapter>

The Stable `gpd-adversarial-critic` prompt at `code/gpd-adversarial-critic-v2.md` emits native FATAL / SERIOUS / WARNING / MINOR. All Critic output flows through `core/adversarial_loop.adapt_severity(...)` before counting. Brief 002 §5.1 mapping:

| Native | Canonical | `blocking` |
|---|---|---|
| FATAL | S | `true` |
| SERIOUS | S | `false` |
| WARNING | W | `false` |
| MINOR | N | `false` |

Revlog finding IDs, canary-gate counts, and the `^iter-\d+-[SMWN]\d+$` regex all key on normalized letters. The Critic prompt is NOT edited -- the adapter is the only normalization surface.

</severity_adapter>

<routing>

For assertion docs, `core/adversarial_loop.route_assertion(...)` partitions inputs along (top-level `derivation_sketch` $\in$ {empty, non-empty}) $\times$ (in-body sub-assertions $\in$ {absent, present}) into four cases, plus knowledge docs as a fifth case. See brief 002 §5.2 + the finding-schema template for the authoritative dispatch table. Recursion depth on nested sub-assertions is capped at 3; depth 4 is a schema-validation error.

</routing>

<loop_control>

Commit 4a surface terminates at "one round produced, findings counted, outputs written" -- a human or wrapping skill decides whether to re-invoke for round N+1. The loop controller (REVISE/APPROVED/ESCALATE state machine + `state.json` `adversarial_review_status` dual-write) lands in commit 4b.

Once 4b lands, convergence is:
- `APPROVED` iff zero S/M/W/N AND zero open `blocking: true`
- `ESCALATE-UNRESOLVED` on Critic<->Fixer disagreement (adjudicator resolves)
- `REVISE` otherwise; re-invoke with `--round N+1`

Iteration caps: `brief` / `plan` -> 2 rounds max (`feedback_scaffold_as_we_go`); `physics` / `knowledge` / `assertion` -> no cap (L20).

</loop_control>

<context>
@{GPD_INSTALL_DIR}/templates/adversarial-review-finding-schema.md
</context>
