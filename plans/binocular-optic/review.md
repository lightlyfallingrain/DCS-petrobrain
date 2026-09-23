### Review Summary

Reviewed `82b1b29`..`e91b9ee` (Binoculars Stage 1 through Stage 3b) against
`plans/binocular-optic/plan.md`, `plans/binocular-optic/stage3b.md`,
`plans/binocular-optic/implementation.md`, root `CLAUDE.md`, and
`body-layer/CLAUDE.md`. Verified independently rather than taken on the
implementer's report: full checks run fresh (no `.venv` existed in this
worktree — built one matching the main checkout's pinned versions), and
the Stage 3b tripwire (`TestSweepFindsAnOffsetContact`) was empirically
reverted (sweep half-width forced to 0) and re-run — it goes red, confirming
it is a real regression guard, not a decorative assertion.

**Checks (body-layer/ only, the sole subproject touched):**
- `ruff check src tests` — pass
- `mypy --strict src` (`PYTHONPATH=src:../world-model/src`) — pass, 45 source files
- `pytest tests -q` — **1016 passed, 4 xfailed**, matching `implementation.md`'s claim exactly

**The seven specific risk areas hold up, with one exception (item 4 below):**

1. **Purity/replay determinism** — `optic_policy.decide` reads no clock, touches no
   store, mutates nothing; every transition returns a fresh `OpticState` via
   `replace()`/a new constructor call. `logger.ConsolePerceptionRunner.optic_state`
   is reassigned, never mutated in place. Confirmed by reading `decide` end to end,
   not just its docstring.
2. **Layering** — `grep -rnE "^(from|import) belief" body-layer/src/perception/`
   returns nothing; every `belief` mention under `perception/` is a comment/docstring.
   `belief/optic_policy.py` imports from `perception` (the allowed direction).
3. **`phase_started_sim: float | None`** — the `None` guard is centralized: `decide`'s
   first statement checks `state.phase_started_sim is None` and returns early before
   any arithmetic; every other branch (`SEARCHING`, `GLASSING`, the scan-complete
   check) runs only after that guard has passed. `look_is_finished` has its own
   explicit `started_sim is None` check. No bare arithmetic on the field found.
4. **`attempted_at_range_m` unbounded growth** — real, but not a leak in any
   practical sense: it is bounded by the number of distinct contacts one sortie
   produces, the same growth shape `belief.contacts.ContactStore`'s own append-only
   observation log already has by design. Judged **acceptable**, optional note below.
5. **Elevation sign conventions** — traced positive-up through all four sites named
   in the task: `Gaze.center_elevation_deg` (docstring states positive-up explicitly),
   `within_optic_fov`'s `boresight_elevation_deg` (`math.radians` direct, no negation),
   `look_target_for`'s `asin(height_delta / slant_m)` (negative when target is below
   observer), and `search_pattern`'s `elevations = [-(depression...)]` (depression is
   positive by `atan2`, negated to become a negative elevation). All four agree.
   `perception/geometry.py`'s `BodyRelativeDirection.elevation_deg` docstring
   (positive = above boresight) confirms the convention the gate itself tests against.
6. **Sweep envelope vs. per-step aim** — `look_is_finished`/`_target_in_current_look`
   test against `look_envelope_azimuth_deg`/`look_envelope_half_width_deg` (the fixed
   sweep centre/width), falling back to the field of view only when no envelope is
   recorded (a search phase, or a hand-built state in a test) — confirmed this is the
   `N=1` case reproducing prior behaviour exactly, not a silent behaviour change.
   `choose_look` is deliberately left on the field of view (picks where contacts
   cluster), which the code and its comment both state explicitly.
7. **Test quality** — `TestLookSweep`/`TestSweepStepsWithTime`/`TestSweepEnvelope`/
   `TestSweepFindsAnOffsetContact` test behaviour (geometry bounds, step progression,
   the widened stop condition, and the actual real-world defect) rather than echoing
   implementation. The `test_mock_flight_chain` assertion count (36 → 32) is backed by
   a genuine geometric explanation, matching `implementation.md`'s account of the
   search-phase cost rather than the aiming defect. One gap found — see below.

---

### Required Fixes

- **D4 ("a player command lowers the binoculars, unconditionally... not a special
  case per command") is only wired for one of the two live command paths.**
  `CrewConsole._note_player_command()` — which is what `logger.py`'s
  `_run_crew_text_poll_loop` reads via `commands_handled` to call
  `lower_binoculars` — is called **only** inside `handle_f10_command`
  (`src/belief/crew_console.py:448`). Free-form utterances dispatched through
  `_act` (`set_attention`/`describe_contact`, reachable both from typed
  `handle_line` in `--crew-text` mode *and* from voice's `"fallthrough"`
  disposition, which itself calls `handle_line` — `crew_console.py:902`) never
  call it. So asking Petrovich to "watch that contact" or "what is that" by typed
  or free-form-voice input does **not** lower the binoculars, while the same
  request phrased as a legacy F10-vocabulary token does. This directly contradicts
  the plan's own stated rule that the interrupt is unconditional across command
  surfaces. `test_a_player_command_lowers_the_binoculars`
  (`tests/test_logger.py`) does not catch this — it tests `handle_f10_command`
  incrementing the counter and `lower_binoculars` acting on a hand-built state as
  two separate facts, never the actual poll-loop wiring end to end, so the gap has
  no test coverage in either direction. Fix: call `_note_player_command()` (or
  equivalent) from `_act`'s handled branch as well, or move the call to a point
  both paths pass through.

- **`plans/binocular-optic/plan.md`'s own Stage 3b entry is stale.** It still reads
  *"Stage 3b — a look is a sweep, not a stare. NOT BUILT; this is the next piece of
  work"* even though Stage 3b is built, tested, and merged (`e91b9ee`). A plan file
  that says "not built" about code that is built will mislead the next person who
  reads it before reading the diff — mark it done, with the merge reference.

- **`body-layer/ROADMAP.md` has no entry for this milestone at all.** Stages 1
  through 3b (the whole binocular-optic feature) do not appear anywhere in the
  roadmap. `ROADMAP.md`'s own header instructs updating it "whenever a body-layer
  branch merges," and root `CLAUDE.md`'s "Milestone Completion" section requires
  recording whether the milestone changes what's next (Stage 4's sortie is the
  obvious next step and is not currently pointed to from anywhere in the roadmap).

---

### Optional Refinements

- `attempted_at_range_m`'s unbounded per-sortie growth (item 4) is acceptable as
  designed — bounded by distinct-contact count, same shape as `ContactStore`'s own
  append-only log — but a one-line comment on `OpticState.attempted_at_range_m`
  noting *why* this is fine (rather than just that contacts are "never removed")
  would save a future reader from re-deriving the bound (optional).
- `_SEARCH_BAND_M` in `logger.py` is a fixed constant (2333–5647 m) rather than
  derived per-contact-type the way `improvement_window_m` is for looks — reasonable,
  since a search has no contact yet to size a band from, and the plan explicitly
  calls this out as "stated as a constant... because a search has no contact yet."
  Not a defect, just worth remembering it will need revisiting once Stage 4's sortie
  judges the search band against real vehicle sizes (optional, already flagged in
  the plan's own risks).

---

### Verdict

APPROVED WITH MINOR FIXES

The core Stage 2/3b mechanism (purity, layering, the `None`-guarded sim clock, sign
conventions, the envelope/step split) is solid and independently verified, including
by empirically reverting and re-running the tripwire test. The three required fixes
are a real behavioural gap in the interrupt rule (D4) and two stale/missing
documentation updates — none require touching the core `optic_policy.py` decision
logic.

### Review Confidence

Full read of `optic_policy.py`, `gaze.py`, `visibility.py`/`optics.py`'s diffs,
`logger.py`'s wiring diff, `crew_console.py`'s diff, and the plan/stage3b/
implementation docs. Test files read in full for `test_optic_policy.py`'s new
classes and `test_logger.py`'s new tests; `test_crew_console.py`'s new tests
(speech-log, a side feature bundled in this diff) spot-checked as clearly in scope
and correct, not read line-by-line against every existing test in that large file.
Checks (ruff/mypy/pytest) run directly in this worktree, not taken from the
implementer's report.
