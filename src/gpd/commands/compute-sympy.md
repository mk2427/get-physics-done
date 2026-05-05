---
name: gpd:compute-sympy
description: Solve or verify a math/physics problem with SymPy (symbolic + numerical fallback) via the gpd-sympy-calculator agent. Returns verified/falsified/unevaluated + LaTeX result; optionally saves to GPD/knowledge/computed/.
argument-hint: "<problem description or LaTeX equation>"
context_mode: project-aware
agent: gpd-sympy-calculator
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->

<objective>
Solve or verify a single math/physics problem via SymPy (with NumPy/SciPy fallback). Dispatches to the `gpd-sympy-calculator` agent, which writes executable SymPy code, runs it via shell with a 3-attempt retry loop, and returns a structured verdict.

Provide the problem as the command argument — LaTeX, natural language, or a mix. Examples:

```
/gpd:compute-sympy "Verify \int_0^\infty e^{-x^2} dx = \sqrt{\pi}/2."
/gpd:compute-sympy "Solve y' + y = x with y(0) = 1."
/gpd:compute-sympy --numerical "Eigenvalues of [[1, 2], [3, 4]]."
```

Returns `{verdict: verified|falsified|unevaluated, latex_result, code, output, attempts, timeout_hit, note}`.
</objective>

<flags>

- `--save` — force save the result to `GPD/knowledge/computed/` even if it is not obviously relevant to the active research project. Overrides the default relevance heuristic.
- `--no-save` — never save the result; treat the computation as ephemeral. Useful for one-off checks during exploration.
- `--numerical` — skip symbolic evaluation and go straight to NumPy/SciPy numerical computation. Useful when you know symbolic will fail (e.g. large matrices, non-closed-form integrals) or when you only need a numeric answer.
- `--assumptions <yaml>` — inline YAML mapping of symbol assumptions passed through to the agent (e.g. `--assumptions "{x: {real: true}, n: {integer: true}}"`). Optional; the agent infers sensible defaults when omitted.

`--save` and `--no-save` are mutually exclusive.

</flags>

<context>
@GPD/CONVENTIONS.md
@GPD/STATE.md
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compute-sympy.md
</execution_context>

<process>

1. Parse the command argument as the `problem` field and the flags.
2. Read `GPD/CONVENTIONS.md` (when present) to pick up project-wide symbol assumptions (e.g. which symbols are real / positive / dimensionless). Forward these as the `assumptions` dict to the agent.
3. Dispatch to `gpd-sympy-calculator` with:
   ```yaml
   problem:     <argument>
   assumptions: <from CONVENTIONS.md + --assumptions>
   save_result: <true unless --no-save; forced true by --save>
   ```
4. If `--numerical` is set, prepend an instruction to the agent prompt directing it to skip symbolic attempts and jump straight to `sp.lambdify` + NumPy/SciPy.
5. Report the agent's structured return to the user: `verdict`, `latex_result`, and — if `verdict == falsified` — the counterexample and `note`.
6. If the agent saved a `GPD/knowledge/computed/` note, echo the saved path.

</process>

<anti_hallucination>

The command's job is dispatch and presentation. Do NOT re-interpret or re-classify the agent's verdict. If the agent returns `unevaluated`, pass that through verbatim to the user — never upgrade to `verified` based on a plausible-looking output. The agent's LaTeX result is authoritative; do not edit it in post.

</anti_hallucination>
