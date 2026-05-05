---
template_version: 1
type: adversarial-review-finding-schema
---

# Adversarial-Review Finding Schema

Canonical shape of a single `/gpd:adversarial-review` finding entry.

Findings are emitted by the Critic (per brief 002 §5.1, after the severity adapter runs), consumed by the Fixer (per brief 002 §4.3), merged by the Critic-vs-Critic policy (MAX severity + OR of `blocking`; brief §5.1 (i)), and counted against the 0/0/0/0 convergence gate.

Use this template whenever you author, revise, or validate a finding. Do not invent ad-hoc keys or omit the `blocking` flag on severity-S findings.

---

## Required Fields

| Field | Type | Notes |
|---|---|---|
| `finding_id` | string | MUST match `^iter-\d+-[SMWN]\d+$` (brief 002 §7.3; `feedback_simple_finding_ids`). Letters-only; `blocking` is a separate field. |
| `severity` | enum | One of `S` / `M` / `W` / `N` (orchestrator-canonical; brief 002 §5.1 legend). |
| `blocking` | bool | `true` iff the underlying native Critic severity was FATAL (brief 002 §5.1 adapter table). SERIOUS / WARNING / MINOR map to `false`. An open `blocking: true` finding forces REVISE regardless of zero-counts (brief §5.1 (ii)). |
| `summary` | string | One-line human description. |
| `target` | string | Path or artifact ID the finding applies to (e.g., knowledge doc ID, assertion sub-ID, line range). |
| `charter_line` | string | The Critic-charter line this finding operationalizes; used so the Fixer can cross-check charter coverage. |

## Optional Fields

| Field | Type | Notes |
|---|---|---|
| `root_event_id` | string \| null | Reserved for commit 10d `invalidation_events` ledger linkage. Null on 4a; populated post-10d when a finding was triggered by a reactive invalidation event. |
| `evidence` | list[string] | Citations, log excerpts, numeric comparisons the Critic invoked. |
| `proposed_fix` | string | Fixer-consumable hint; NOT a contract — the Fixer still independently assesses per `feedback_adversarial_fixers`. |
| `duplicates_of` | list[string] | Finding IDs this one duplicates (post-merge bookkeeping). |

---

## Severity Legend

Source of truth: brief 002 §5.1.

| Native Critic severity | Canonical | `blocking` |
|---|---|---|
| `FATAL` | `S` | `true` |
| `SERIOUS` | `S` | `false` |
| `WARNING` | `W` | `false` |
| `MINOR` | `N` | `false` |

`M` (Moderate) is reserved for orchestrator-synthesised findings that do not originate from the native Critic prompt (e.g., policy checks, CI). On 4a the adapter never emits `M` directly.

---

## JSON Example

```json
{
  "finding_id": "iter-2-S1",
  "severity": "S",
  "blocking": true,
  "target": "GPD/knowledge/K-007-ward-identity.md#eq-3.14",
  "charter_line": "find equation errors",
  "summary": "Restated \\Gamma^{\\mu\\nu}_{\\rho} uses opposite sign from the source paper.",
  "evidence": [
    "Paper arXiv:2410.14647 eq. (3.14)",
    "Local restatement uses +, source uses -"
  ],
  "proposed_fix": "Replace + with - in the restated equation body; re-run upstream_ref_hash.",
  "root_event_id": null,
  "duplicates_of": []
}
```

---

## Merge Rules (Critic-vs-Critic)

Two findings from different critics on the *same underlying issue* merge as:

- `severity` -> MAX of the inputs (S > M > W > N)
- `blocking` -> OR of the inputs (one `true` wins)
- `finding_id` -> the first input's ID; no renumbering
- `summary` -> the most-severe input's summary; ties break first-seen
- `root_event_id` -> first non-null across inputs

The Adjudicator (commit 4b) inherits the OR on `blocking` unchanged (brief §5.1 (i)).

---

## Router Interaction

Findings always carry a `target` that resolves inside the artifact being reviewed. For compound assertion docs (brief 002 §5.2 mixed-kind and compound-derived-consequence), the router emits per-sub-claim reviews; the `finding_id` is namespaced with the sub-ID per `feedback_simple_finding_ids`, for example:

```
sub-2-iter-1-S1
```

Recursion depth is capped at 3 (top-level -> sub -> sub-of-sub); deeper nests are a schema-validation error.

---

## Version History

| template_version | Date | Change |
|---|---|---|
| 1 | 2026-04-20 | Initial landing (commit 4a). |
