### Review Summary

Branch `feature/theatre-from-dcs` (tip `137906bb`, one commit on `main` `cedf604f`), reviewed
against the user's verbatim request and the prior `BL-15`/`plans/bl15-mission-start/plan.md`
Stage 3 design it extends. No separate plan file for this change — correctly scoped as a small,
direct change per the dispatch brief.

**What it does**: `--world-model-dir` alone is now sufficient to start body-layer. No store/theatre
is loaded at startup; `ConsolePerceptionRunner.world_model_store: tuple[str, Path] | None` (new
field, preserved across `reset_for_new_mission`) tracks the live `(theatre, path)` pair behind
`world_model_conn`/`theatre`. `_check_for_new_mission`'s first-poll branch — previously a pure
no-op beyond recording the sequence number — now also calls `_maybe_switch_theatre` with that
first event's theatre, which is how a `--world-model-dir`-alone start gets its first store, and
how an explicit `--theatre`/`--mission-understanding` theatre that DCS disagrees with gets
corrected on the very first poll rather than waiting for a restart. The REPL thread (`_run_crew_
text_repl`) now follows `runner.world_model_store` live instead of a path/theatre pair bound once
at `main()`'s startup, fixing the pre-existing bug where it would keep querying the old theatre
after a live switch.

**Verified by direct trace, not just reading:**

- Every one of the three sites that writes `world_model_conn`/`theatre` (`_enter_refusal_mode`,
  `_maybe_switch_theatre`, the poll loop's own startup branch) also writes `world_model_store` in
  the same block — grepped all three write sites side by side (`grep -n "world_model_conn = \|
  world_model_store = \|\.theatre = "`), no site updates one without the other. This is exactly the
  recurring "co-moving state" defect shape this project's memory flags repeatedly
  (`project_recurring_stale_state_on_transition.md`, five prior occurrences across `BL-14`/
  `BL-B64`/`BL-B80`/`BL-B89`/`BL-B98`) — checked for specifically here and not found.
- `ConsolePerceptionRunner.reset_for_new_mission`'s preserve-set and its completeness test
  (`test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`) both include
  the new `world_model_store` field — it will not silently reset to `None` on a mission restart
  while `world_model_conn`/`theatre` survive, which would otherwise desync the REPL thread's store
  selection from the poll thread's.
- `run_once`'s `self.world_model_conn is not None and self.theatre is not None` guard (line 657)
  already tolerates `theatre is None` without crashing — pre-existing code, unaffected, confirmed
  by reading rather than assumed.
- The explicit `--theatre`/`--world-model-db`-without-`--world-model-dir` refusal-on-first-poll
  behaviour change the dispatch brief flagged is real, intended, and tested
  (`test_check_for_new_mission_first_poll_corrects_a_wrong_initial_theatre` covers the
  theatre-*correction* case; the brief's refusal-on-mismatch-with-no-dir case is the same code
  path as the already-tested `test_maybe_switch_theatre_enters_refusal_mode_when_world_model_
  dir_is_none`). Matches `body-layer/CLAUDE.md`'s own documented posture ("a theatre DCS reports
  that differs from the initial one has nowhere to resolve a store from and enters that same
  refusal mode") and the 2026-10-19 "wrong terrain model is as useless as no terrain model" /
  "on error loud refusal is better" user decision this reuses rather than re-deciding.
- `mark_here_fn`/`mark_target_fn`'s `assert runner.theatre is not None` (unchanged by this diff) is
  still protected the same way it always was: both are reachable only through `handle_command`/
  `handle_line`, both gated by `_refusal_response` at the top, and `crew_console.refused` is set
  `True` synchronously in the same poll-thread code block that used to set `runner.theatre` to a
  non-`None` value unconditionally — the invariant "`refused == False` implies `theatre is not
  None`" still holds by the same mechanism as before, just now spans a potentially unbounded
  waiting period (until DCS names a theatre) instead of a few lines at thread start. No new crash
  path found; see the one observation below.
- Checked for a second new refusal-mode speech leak (the class of bug this project's memory
  records once, `project_degrade_mode_speech_gate_must_be_on_the_speaker_not_the_entry_path.md`):
  `drain_events`/`drain_brain` already gate on `self.refused` as of the prior Stage 3 fix, and this
  diff introduces no new proactive-speech path — not re-broken here.
- Ran `ruff format --check`, `ruff check`, `mypy --strict` (from inside `body-layer`), and the full
  test suite from the worktree's own venv. Format/lint/type-check all clean. 5 pre-existing
  failures (effector-config/switch-reference round-trip tests) reproduced identically against
  `main` at `cedf604f` with the same `-k` selection — confirmed, not introduced by this branch.
  2695 passed, 4 xfailed otherwise.

**One thing that changed character, not correctness**: the first mission-start event's theatre is
now load-bearing for which world-model store loads (previously, with `--mission-understanding`, it
was cosmetic — only a sequence-number bookkeeping read). If the aircraft-layer collector is holding
a stale mission-start event from a mission that has since ended (DCS sitting at the main menu, a
body-layer restart between sorties), that stale theatre gets adopted silently as if it were current
— no reset fires (by the existing, deliberate first-poll design), so there's no visible signal
this happened. This was already an accepted assumption in `plans/bl15-mission-start/plan.md`'s
"Decisions Requiring User Input" ("the first poll as already clean, nothing to reset... regardless
of the sequence number seen") and in this diff's own comment ("the event is the live mission's"),
but that assumption carried negligible cost before (wrong sequence-number bookkeeping, nothing
user-visible) and now carries the cost of loading the wrong theatre's terrain model until the next
genuine mission (re)start corrects it. Not a required fix — it is the plan's own accepted
premise, now exercised in a context where it costs more — but worth a line in `BL-15.md`'s risk
list if it hasn't been flagged already.

### Required Fixes

None.

### Optional Refinements

- Note in `body-layer/ROADMAP/BL-15.md` or `plans/bl15-mission-start/plan.md`'s Risks section that
  a stale cached mission-start event (collector held one from a now-ended mission, body-layer
  started/restarted without a sortie in between) is now load-bearing for initial theatre/store
  selection under `--world-model-dir` alone, not just a bookkeeping read — so a future debugging
  session has this written down rather than re-derived. (Optional: the risk is accepted by the
  plan's existing design, this just makes the cost of that acceptance explicit for the new case.)

### Verdict
APPROVED

### Review Confidence
Full read — plan/roadmap/CLAUDE.md context, the full `body.py` diff, the new/changed test files,
direct tracing of every `world_model_conn`/`theatre`/`world_model_store` write site, and a live run
of format/lint/mypy/pytest from the worktree's own venv.
