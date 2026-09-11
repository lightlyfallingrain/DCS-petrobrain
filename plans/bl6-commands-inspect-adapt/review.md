### Review Summary

Reviewed the BL-6 implementation (branch `feature/bl6-commands-inspect-adapt`, commits
`2c98ff9`..`1f93e3b`) against the locked, revised plan
(`plans/bl6-commands-inspect-adapt/plan.md`, commit `2c98ff9`) and the Implementer's own
`implementation.md`. Scope matches the plan closely: `PendingIntent`/`TaskStore` (`tasks.py`,
pure, no DCS I/O), `scan_area`/`get_task_status`/`cancel_task` (`tools.py`, also pure), the live
trigger wired one layer up in `console.py`'s `scan-area` handler exactly as the plan specified,
and the matching aircraft-layer effector (`Export.lua` wheel press/long-hold, `command_sender.py`,
the two new endpoints). The one documented deviation (`scan_area` gaining an explicit `now_sim`
parameter the plan's prose omitted) is correctly reasoned and consistent with every other
`belief.*` sim-time convention — not a real deviation.

Both hard design constraints hold up under direct inspection, not just docstring assertion:

- **Observation/engagement separation.** The only wheel buttons ever pressed anywhere in this
  change are `3001` (menu-open) and `3015` (centre/search) — `Export.lua`'s
  `handle_petrovich_search_command` never references `3020` (`DesignateAttackPoint`), `3009`
  (`SelectTarget`), or `3010` (`UnselectTarget`). `mode` is validated server-side against exactly
  `{"forward", "boresight"}` in three independent places (`api/server.py`'s
  `_VALID_SEARCH_MODES`, `command_sender.py`'s `SearchMode` Literal, `Export.lua`'s own
  `mode ~= "forward" and mode ~= "boresight"` guard) — there is no code path from this milestone's
  new surface that can reach a selection/engagement command. `test_petrovich_search_api.py`
  exercises the 400-on-invalid-mode case directly.
- **`cancel_task` removes the `AttentionArea`.** `tools.cancel_task` reads `task.area.id` and
  calls `store.remove_area` before returning; `test_cancel_task_command_cancels_and_removes_the_area`
  asserts `console.store.areas == []` afterward, not just the task's own status field.
- **Purity boundary.** `tasks.py`/`tools.py` import nothing DCS-facing; the live trigger and the
  wheel-state diagnostic read both live in `console.py`'s handlers, matching the plan's explicit
  "wire the live effect one layer up" instruction and BL-2.5's precedent.
- **`aircraft_client=None` as the safe default.** Every new console/tool test exercises the
  no-client path as the default case; a `_RecordingAircraftClient` double covers both the
  live-trigger-success and live-trigger-failure-degrades-gracefully paths without any test
  requiring a live DCS session.

Ran `body-layer`'s and `aircraft-layer`'s own format/lint/type/test commands directly (not just
trusting the Implementer's report): `ruff format --check`, `ruff check`, `mypy --strict`, and
`pytest -q` are all green in both subprojects (437 passed / 90 passed), matching
`implementation.md`'s numbers exactly.

### Required Fixes

- **The Mi-24P RU manual PDF (16.25 MB, `docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf`,
  added in `663c7f3`) is committed in the wrong module and probably shouldn't be committed as a
  binary at all.** `docs/concept/` is this project's architecture/design-reference location
  (`PETROBRAIN_SYSTEM.md`, `WORLD_MODEL_BUILDER.md`, etc.) — a third-party copyrighted flight-manual
  scan doesn't belong there, and if it belongs anywhere it's alongside the research notes that
  cite it (`aircraft-layer/research/2026-09-11-quickstart-ru-9k113-manual.md`,
  `reference_mi24p_quickstart_ru_manual.md`), which already extract everything the investigation
  actually used. Two separate problems: (1) module placement — this is implementation-adjacent
  research material sitting in the architecture-docs directory; (2) committing a 16 MB third-party
  copyrighted PDF into git history at all is a real, hard-to-undo cost (git history bloat that
  persists even after a later removal, plus a redistribution question this project has not had to
  face before since every other research artifact has been project-authored notes/logs). Recommend
  removing the binary from the branch before merge and keeping only the already-written extraction
  notes; if the raw manual is needed for reference, keep it outside version control (e.g. a path
  noted in the research doc, not a tracked blob).
- **`tool_api.py`'s updated freeze-point docstring cites the wrong document.** Lines 15-17 now say
  "`TOOL_SET` is now the frozen surface `docs/concept/PETROBRAIN_RUNTIME.md` §3.3 names in full,"
  but §3.3 (the tool list with `scan_area`/`get_task_status`/`cancel_task`) lives in
  `plans/body-layer/plan.md`, not `docs/concept/PETROBRAIN_RUNTIME.md` — confirmed by grep,
  `PETROBRAIN_RUNTIME.md` doesn't mention `scan_area` anywhere, and the same docstring's own line
  19 (unchanged) correctly cites `plans/body-layer/plan.md` §3.3 two lines later. This is a
  one-line factual fix, but it's exactly the kind of misdirection a future reader hunting for "the
  frozen tool contract" would hit.

### Optional Refinements

- `body-layer/ROADMAP.md` line 158 ("The tool-set freeze point is the end of BL-7, not BL-5") and
  `plans/body-layer/plan.md` line 898 (same claim) are now stale given this plan's revision moved
  the freeze point to BL-6 — worth a one-line fix at milestone close, alongside the plan's own
  flagged stale-Security-gating-wording note. Not blocking; this is exactly the kind of
  housekeeping the project's "Milestone Completion" checkpoint is for, not a Reviewer gate. (optional)
- `crew_console.py`'s new `aircraft_client` field has no reader this milestone (documented as
  reserved in both the field's own docstring and `implementation.md`). This is a reasonable,
  clearly-labeled wiring-parity choice rather than silent dead code, but worth a second look at
  DoD/next-milestone time if it's still unread after BL-6's player-facing follow-on lands — a
  reserved field with no consumer for two milestones running is worth questioning. (optional)

### Verdict

APPROVED WITH MINOR FIXES

Both required fixes are small and mechanical (move/drop one binary file, fix one doc-reference
typo) — neither touches design, tests, or the two hard constraints, which are all correctly
implemented and exercised. No re-review needed once these are applied; the Implementer can make
both fixes and proceed straight to DoD.

### Review Confidence

Full read — read the plan, implementation summary, `tasks.py`/`tools.py` in full, the
`console.py`/`aircraft_client.py`/`tool_api.py`/`crew_console.py`/`logger.py` diffs in full, the
`api/server.py`/`command_sender.py` diff in full, `Export.lua`'s new command-handling code in
full, `test_tasks.py` and the `test_console.py`/`test_petrovich_search_api.py` additions in full,
and ran all four format/lint/type/test commands directly in both touched subprojects rather than
trusting the Implementer's report.
