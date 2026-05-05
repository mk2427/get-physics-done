<purpose>
Solve or verify a math/physics problem with SymPy (symbolic + numerical fallback) via the `gpd-sympy-calculator` agent. Handles the full dispatch surface: parse the problem, forward symbol assumptions from project conventions, drive the 3-attempt retry loop inside the agent, and surface a structured verdict (`verified` / `falsified` / `unevaluated`) plus LaTeX result to the caller.

This workflow is the thin orchestration layer under `gpd:compute-sympy`. Actual SymPy code generation and execution happen inside the agent; the workflow's job is input validation, flag plumbing, and presentation.
</purpose>

<core_principle>
Correctness first. Never upgrade an `unevaluated` verdict to `verified` based on a plausible-looking output; never claim `falsified` without a concrete counterexample. The agent's verdict is authoritative and passes through unchanged.
</core_principle>

<process>

<step name="parse_argument">
**Step 1: Parse the command argument.**

- The argument is a single string containing a LaTeX equation, natural-language problem description, or both.
- If the argument is empty, ask the user what to compute before proceeding.
- If the argument contains obvious runtime artifacts (unclosed `$`, literal `\n`, mismatched braces), surface a parse warning to the user but continue — let the agent decide whether it is tractable.

</step>

<step name="resolve_flags">
**Step 2: Resolve the flags.**

- `--save` and `--no-save` are mutually exclusive. If both are present, error out.
- `--numerical` is optional; when set, forward an instruction to the agent to skip symbolic attempts and jump straight to `sp.lambdify` + NumPy/SciPy.
- `--assumptions <yaml>` is optional; when present, merge with the project-conventions assumptions loaded in step 3 (command-line wins on conflict).

</step>

<step name="load_conventions">
**Step 3: Load project conventions for symbol assumptions.**

- Read `GPD/CONVENTIONS.md` when present and extract per-symbol assumption hints (e.g. "all Greek indices are real", "n is always a positive integer").
- Merge the extracted assumptions with any `--assumptions` overrides from step 2.
- If no conventions file is available (e.g. projectless invocation), pass an empty assumptions dict; the agent infers sensible defaults per SymPy's default symbol semantics.

</step>

<step name="dispatch_agent">
**Step 4: Dispatch to `gpd-sympy-calculator`.**

Payload:

```yaml
problem:     <command argument>
assumptions: <merged per step 3>
save_result: <true by default; forced true by --save; forced false by --no-save>
numerical:   <true iff --numerical>
```

The agent follows its own `<execution_protocol>`: parse the problem, emit SymPy code, run via shell, retry up to 3 attempts with progressive debugging, classify the verdict, and (when save_result is true) persist a `GPD/knowledge/computed/<slug>-<timestamp>.md` note.
</step>

<step name="present_result">
**Step 5: Present the agent's structured return to the user.**

Report:

- `verdict` (verified | falsified | unevaluated)
- `latex_result` (or the counterexample if falsified)
- `attempts` used
- If the agent saved a `GPD/knowledge/computed/` note, echo the saved path
- If `verdict == falsified`, surface the agent's `note` verbatim
- If `verdict == unevaluated`, explain that SymPy could not resolve the problem in 3 attempts and suggest either reformulating with more explicit assumptions or rerunning with `--numerical`

Do NOT re-interpret or re-classify the agent's verdict. Do NOT edit the returned LaTeX.
</step>

</process>

<anti_hallucination>

- The command is dispatch + presentation. All computation happens inside the agent, driven by real SymPy running under `py`.
- `unevaluated` is a first-class outcome; never silently promote it.
- Counterexamples for `falsified` verdicts come from the agent only; never synthesize one in post.
- LaTeX preservation: copy `latex_result` through verbatim; Markdown-escaping is the caller's responsibility, not this workflow's.

</anti_hallucination>
