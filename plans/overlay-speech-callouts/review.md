### Review Summary

Implementation matches `plans/overlay-speech-callouts/plan.md` (locked at `91f00f2`) closely — no
scope drift, no unrelated refactors. Verified against the working-tree diff (plan.md itself is the
only committed change on the branch; code changes are staged/unstaged in the working tree per
`git status`):

- `overlay_client` is a genuinely separate `CrewConsole` field from `aircraft_client`, with a
  docstring explaining why (BL-6-reserved, no reader today, vs. read every `_print` call). Matches
  the plan's explicit reasoning.
- `_print` is the single funnel point. Confirmed by grep: both call sites of `_print`
  (`crew_console.py:145` in `handle_line`, `:160` in `drain_events`) are the only two, so every
  path that produces spoken text goes through it. No bypass route found.
- `"!! "` prefix is applied only at the `_print` push call, only when `bypass_gate=True`, only to
  the pushed overlay copy — `output`'s printed line is untouched (verified in code and in
  `test_urgent_call_pushes_to_overlay_with_prefix_but_prints_unprefixed`). `bypass_gate` is
  correctly scoped: `handle_line` sets it `False` explicitly for the non-`!inject-urgent` branch,
  `drain_events` always passes `False` (lifecycle `Event`s never set the flag), and
  `_handle_inject_urgent`'s new `tuple[list[str], bool]` return reads `bypass_gate` straight off
  `route_event`'s `OutgoingSpeech` rather than re-deriving it from text — no leak into an unrelated
  path. Cross-checked the "notable discovery" claim that `route_event` always sets
  `bypass_gate=True` for `UrgentCall` — confirmed at `belief/speech.py:254`.
- Failed overlay push degrades correctly: each push in `_print`'s loop is wrapped in its own
  `try/except AircraftLayerError` (log-and-continue), matching `ConsolePerceptionRunner.run_once`'s
  BL-2.5 pattern. `test_failed_overlay_push_degrades_without_raising_and_does_not_block_remaining_lines`
  exercises this with a real failure injected via `FakeOverlayClient(fail_on=...)`, not just an
  assert-no-exception — it confirms the failed line is absent from `pushed` and a later, unrelated
  push in a subsequent call still succeeds.
- `logger.py`: mutual-exclusivity relaxed exactly as planned (`args.crew_text and args.console`
  only). `--crew-text` branch now wires `overlay_client=aircraft_client if args.overlay else None`
  into `CrewConsole(...)`. Confirmed by direct read (`logger.py:623`) that the pre-existing
  `--console` branch's `ConsolePerceptionRunner(overlay_client=aircraft_client if args.overlay else
  None)` wiring (`logger.py:654`) is untouched — same line shape, unaffected by this change. Help
  strings and module docstring updated to describe the new combination.
- Test coverage: 7 new tests (plan/implementation.md both say 7 under "Tests Added"; my review
  brief said 8 — that number came from the task prompt, not from a gap in delivered work). All 7
  assert on `FakeOverlayClient.pushed`'s actual captured content (exact text, prefix present/absent,
  no-op when unset) rather than merely "no exception raised" — meets the checklist bar.
- `belief/speech.py` and `belief/console.py` (`format_event_for_overlay`) are untouched, confirming
  the plan's "no change" list held (`git diff HEAD --stat` on both files is empty).
- `body-layer/CLAUDE.md`'s two updated sections (the `--overlay` running note and the
  `crew_console.py` Structure entry) accurately describe what was built: separate-field reasoning,
  `_print` funnel, prefix scope, and the `--crew-text`/`--overlay` combination — no drift from the
  as-implemented behavior.

Ran body-layer's own commands directly rather than trusting the Implementer's report:
- `ruff format --check src tests` — pass (62 files already formatted)
- `ruff check src tests` — pass
- `cd body-layer && mypy src` — pass, no issues in 29 source files
- `pytest tests -q` — pass, 444 passed

All match the Implementer's reported results exactly.

### Required Fixes

None.

### Optional Refinements

- No test exercises `logger.py`'s `main()` argparse mutual-exclusivity check itself (the
  `parser.error("--crew-text is mutually exclusive with --console")` path) or the `--overlay`
  wiring inside `main()` end-to-end — this is a pre-existing gap (the old mutex code had no direct
  test either, `main()`'s CLI parsing generally isn't unit-tested in this file), not something this
  change introduced or worsened. Worth closing at some point but not blocking, and out of this
  plan's stated scope. (optional)
- New files staged: `git status` shows the code changes as modified/staged (`M`/`A` markers) with
  none left as plain untracked working-tree noise except the implementer's own agent-memory file —
  fine as-is, nothing to add here, just confirming for the record.

### Verdict
APPROVED

### Review Confidence
Full read — read plan.md and implementation.md in full, read the complete diff for all four
changed files (`crew_console.py`, `logger.py`, `test_crew_console.py`, `CLAUDE.md`), grepped for
all `_print` call sites and the `--console` branch's overlay wiring to confirm no regression, cross-
checked the `route_event`/`bypass_gate` claim against `belief/speech.py` source, and ran all four
body-layer verification commands myself rather than trusting the Implementer's report.
