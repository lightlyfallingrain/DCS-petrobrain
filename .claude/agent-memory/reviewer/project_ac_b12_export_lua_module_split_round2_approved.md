---
name: ac-b12-export-lua-module-split-round2-approved
description: AC-B12/AC-B13 re-review after the required fix (commands.lua dispatch-table guard) -- APPROVED. Confirms how a cheap counterfactual test was verified as genuine without re-running the whole feature review.
metadata:
  type: project
---

Re-reviewed `feature/ac-b12-export-modules` at `c304dcc5` (fix commit) against
`plans/ac-b12-export-modules/review.md`'s one required fix. Verdict: APPROVED. Full account in
that file's "Re-review" section.

**The required fix was the obvious shape** (guard each `commands.lua` dispatch-table entry on its
owning module being non-`nil`, mirroring the loader's own `call_if`) -- the useful check in a
re-review of a one-line-conceptually fix is not re-deriving the fix, it's verifying the
*counterfactual test* that proves it. `test_commands_lua.py`'s
`test_mutation_unguarded_table_build_crashes_instead` claims the pre-fix shape crashes; rather than
trusting that claim, ran the literal pre-fix table construction through `luajit` directly
(`local handlers = { cockpit_switch = effectors.handle_cockpit_switch_command }` with `effectors`
undefined) and got the exact error the test asserts on (`attempt to index global 'effectors' (a nil
value)`, non-zero exit). Cheap (one `Write` + one `Bash` call) and it is the only way to know the
counterfactual is genuine rather than a test that would pass regardless of which shape it's pointed
at -- consistent with `.claude/agents/reviewer.md`'s "Verify by mutation" section and this
project's own `feedback_lua_named_mutations_are_cheap_to_reproduce_directly.md`.

**Also worth noting for future re-reviews of a fix commit that bundles a "main-loop decision" with
the required fix:** the task explicitly separated "required fix" from "main-loop decision, not a
reviewer requirement" (the `EXPORT_SCRIPT_VERSION` bump) up front. Re-reviewing both anyway (not
skipping the non-required one) caught that the bump was done consistently on both sides
(`Export.lua` + `collector/server.py`) with the parity test still passing -- a decision correctly
exempted from being a *requirement* is not exempt from being *checked*, since the main loop still
needs to know it landed cleanly.

See `project_ac_b12_export_lua_module_split_review.md` (the first-round review and its one
finding) for the full context on what this fix corrects.
