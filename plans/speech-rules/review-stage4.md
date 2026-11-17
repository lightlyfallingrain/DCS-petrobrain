### Review Summary

Reviewed four commits on `feature/speech-rules-matching` (tip `3c516667`, fast-forwarded from
this worktree's prior `fc282270` — HEAD was a strict ancestor, tree clean, merge was `--ff-only`):

- `04217983` — Stage 4: flight-control port (19 rules in `config/rules/flight.lua`).
- `6a6ce8e7` — main-loop reconciliation of Stage 4's actions with Stage 3d's widened `Action`
  signature (`_int_arg`).
- `d3ec510b` — Stage 4 follow-ups: collision-check recalibration (D9) + U22 (`note_urgent`).
- `38dcd6a1` — Stage 3d re-review Fix 4 round 2: buffer-then-commit effector writes.

Scope matches `plans/speech-rules/plan.md` Revision 2's Stage 4 section (D16/D18), D9's dated
"Recalibrated 2026-11-17" note, D19/U22, and `review-stage3b.md`'s Required Fix 1 and optional
refinement. Not re-reviewed: Stage 3d Fixes 1–3 and Fix 4 round 1 (already closed in
`review-stage3d.md`), and anything in `850b4b8a..3c516667` outside the four commits named above.

**Two mid-review directions from the coordinator, applied below, not treated as open questions:**
1. `straight`'s collision with `hvrt_translate_right` is being resolved on the branch separately
   (dropping the `straight` rule, which also un-disables `hvrt_translate_right`) — not raised as a
   required fix here, and the collision-check *mechanism* that found it is reviewed on its own
   merits, independent of that one rule's fate.
2. No further required fixes on rollback/recovery from a broken rule. `38dcd6a1`'s buffer-then-
   commit stays exactly as built. The bar for a broken rule is: the failure is clear (stderr names
   the file/rule; "Action file error." is spoken) and body-layer does not crash — reviewed against
   that bar only, below.

### What was verified, and how

**1. Differential equivalence of every ported command.** `turn_heading` (absolute), `level_flight`,
`set_speed`/`set_speed_max`, `speed_step`, `set_altitude`, `altitude_step`, `hold_altitude`,
`level_off`/`straight`, the four HVRT translate directions, `hvrt_hold`, `hvrt_step_up`/`_down`,
and "you/i have controls" are each extracted into a `CrewConsole` action method whose own docstring
names the deleted pre-rules handler it replaces, and `test_rules_flight_actions.py` pins every
branch those deleted handlers' own tests covered against the **real**, shipped `flight.lua`
(`_dispatching_console` goes through `handle_command` → the real gate → `_dispatch_rule` → the real
`run_rule`, not a direct action call) — read the pre-image of each deleted test class via `git show`
on the commit that removed `test_crew_console_ai_pilot_wheel.py`'s `TestLevelFlight`/
`TestTurnHeading`/`TestSetSpeed`/`TestSpeedStep`/`TestSetAltitude`/`TestAltitudeStep`/
`TestHoldAltitude`/`TestLevelOff`/`TestHvrtTranslate`/`TestHvrtHold`/`TestHvrtStep` and compared by
hand against the new classes with the same names in `test_rules_flight_actions.py`: the 0/360 wrap
(pre-existing from Stage 2, unchanged), the speed-max sentinel, the 700 m radar-cap reference
resolution (both directions — "radar" requested and achieved, "radar" requested but capped to
barometric, no reference spoken keeping the current one), and the HVRT hover precondition
(dispatches from `HVR`/`HVRT`, refuses from `FLT`/before any mode is known, "not flying" takes
priority over "not ready" even with a stale `ai_mode="HVR"` already set) are all present and
correct. The one deliberate, flagged exception: the legacy compass-point form ("heading north") is
dropped — `turn_heading`'s own `heading` slot type is three digits only (D7/D14's correction), with
no compass-word alternative, and `set_heading`'s own docstring plus `implementation.md` both say so
as a user-visible narrowing, not a silent one. I grepped for `SECTOR_WORD_DEGREES` across both
subprojects after the deletion — no remaining reference anywhere, confirming it was dead weight
once `parse_heading_deg` went, not a load-bearing table shared with scan/report's own compass
handling (that uses a different mechanism, `belief.attention.Sector`, untouched). I did not find
anything else dropped silently.

**2. Per-parameter readiness gates.** `review-stage3b.md`'s Required Fix 1 (the single `settling`
proxy was correct only for `turn_heading_relative`, wrong for five of the other six commands) is
resolved exactly as that review suggested as one option: `CrewState` now carries the three raw
`held_*` values (not one derived bool), and `rules/gates.py` declares one base gate
(`_flight_control`, has-controls only) plus three per-parameter variants
(`_flight_control_heading`/`_speed`/`_altitude`/`_any`), each holding on exactly the field its own
rule family needs (`_flight_control_any` correctly reproduces `level_flight`'s own "any one of
three is enough" rule, promoted from the deleted handler). `flight.lua`'s 19 `when.speech` calls are
each tagged with the category that matches their own extracted action's own old precondition check
(cross-checked rule-by-rule against the table in `review-stage3b.md`'s own finding). Every
extracted action that had an old `is None -> NOT_READY` branch now `assert`s the gate's guarantee
instead (`step_speed`, `step_altitude`, `hold_altitude`, `level_off`'s `speak_level_off`) — no
`None` reaches arithmetic, and a would-be violation degrades safely rather than crashing (see
`run_rule`'s hardening, below) rather than silently passing. `GATE_REGISTRY` is closed and
validated at rule-load time (`rules/engine.py`'s loader checks a declared category against it
before accepting the rule), so an unregistered category can only ever be reached defensively
(`check_gate`'s own `UNABLE("NO_SUCH_COMMAND")` fallback), never silently `PASS`. `test_rule_gates.py`
exercises all four `flight_control*` gates plus the registry-closure test directly.

**3. Collision recalibration.** `d3ec510b`'s `_is_genuine_collision` replaces D9's original "any
hit at all" criterion with the three-way split the task asked me to check: an exact tie
(`own_ratio == other_ratio == 1.0`, both disabled — the literal "same wording" U10 names), the other
side confidently beating the sample's own rule by `>= SEPARATION_MIN` (confident-wrong, disabled),
and a fuzzy near-tie under that gap with neither side at `1.0` (logged at `INFO`, left to the
runtime confirm band, not disabled). The measured table in `implementation.md` matches what the
code does: `set_speed`/`altitude_step` and `level_off` are rescued (own `1.0` clearly beats a fuzzy
competing resolution), and `straight`/`hvrt_translate_right` were the one surviving pair — `straight`'s
own perturbed sample ("right") hits `hvrt_translate_right` at an exact `1.0`, clear of `straight`'s
own `0.769` self-match by `0.231`, a genuine confident-wrong collision, not a near-tie; the
previously-reported "straight vs sight" framing was the *un-recalibrated* check's own false
positive, correctly superseded in the writeup. Per the coordinator's direction above, this one
rule's fate is being resolved separately (dropping `straight`), so I am not requiring anything
about it here — the mechanism that found and correctly classified it is what I reviewed, and it is
sound. Tests (`TestCompileRules` in `test_rule_patterns.py`) cover both the near-tie-is-not-a-
collision case and the counterfactual (a confident beat is still rejected even on a perturbed
sample), in both the rule×rule and rule×legacy directions.

**4. U22 scoping.** `d3ec510b` routes a flight-category rule's own readback through
`CalloutScheduler.note_urgent` (via `_print`'s existing `bypass_gate` parameter) in both
`handle_command`'s immediate dispatch and `drain_pending_rule_dispatch`'s hold-and-retry path.
Scoping is `category.startswith("flight_control") and self.current_crew_state().has_controls` —
checked at the point of speaking, not at match time, so it can never influence *which* rule matched
or resolve a near-tie toward a flight command: D17's own "never a tie-break toward flight" rule
(`SEPARATION_MIN`'s disposition) is untouched by this commit, and I confirmed `bypass_gate` is
computed from the matched rule's *already-decided* category and current `has_controls`, after
dispatch, nowhere near `_match_rules`/`match_transcript`. The `has_controls` check also correctly
keeps an `UNABLE("NOT_FLYING")`/held-timeout line (spoken when he does *not* have controls) off the
urgent path. `category="always"` ("you/i have controls") is excluded by the `startswith` check, as
intended (Q7's silent no-op was never a candidate for urgency anyway, since it says nothing).

**5. The three infrastructure fixes in `04217983`.**
- **Union-slot wire fix**: `MatchResult.slots`/`_match_rules`'s typed-slot filter widened from
  `isinstance(value, (int, str))` to `(int, str, dict)`, with a new `SlotValue = int | str |
  dict[str, object]` alias threaded through `command_matcher.py` and `transcript_queue.py`. Before
  this, `speed_target`'s own `{"kind": ..., ...}` union value was silently dropped at the wire
  boundary — the differential test for `set_speed`/`speed_target` is what caught it, and
  `TestSetSpeed`'s two tests (numeric and literal-max) now exercise the fixed path end to end.
- **HVRT self-collision fix**: `_collides_with_legacy` now requires the legacy probe's token to
  differ from the rule's own id before counting a hit. Without this, every HVRT bare-word rule
  "collided with itself," since `command_matcher`'s own pre-rule `_HVRT_BARE_WORD_TOKENS` shortcut
  always resolves a bare "left"/"hold"/etc. to that same token regardless of whether any rule is
  pushed — correctly identified as the opposite of a collision (the legacy pipeline and the rule
  agree on what the command is).
- **`run_rule` hardening**: a bare `except Exception` added alongside the existing
  `(RuleRuntimeError, RuleBudgetExceeded)` catch, degrading to D6's "Action file error." instead of
  letting a Python exception (e.g. a future assert violation) escape and crash the poll loop — this
  closes `review-stage3b.md`'s own optional refinement, and directly satisfies the coordinator's
  "failure is clear, body-layer does not crash" bar for a broken rule: the log line names the rule
  id, its file, and the exception type (`"rule %r (%s) dispatch error (unhandled %s): %s"`), and the
  one line spoken is the same `ACTION_FILE_ERROR_LINE` every other dispatch-time failure uses.

**6. Buffer-then-commit (`38dcd6a1`), reviewed only against "failure is clear, no crash."**
`_dispatch_rule` opens a thread-local buffer before calling `rule_runner`; `queue_effector_write`
appends to that buffer when one is open (straight to the shared `pending_effector_writes`
otherwise, unchanged); on success the buffer is `list.extend`-ed onto the shared list in one call,
on error it is discarded. I re-read `review-stage3d.md`'s "Re-review (Fix 4)" finding this closes
(the poll thread's own unconditional per-poll drain could win a race against Fix 4 round 1's
token-filter rollback, taking an entry before the rollback ran) and confirmed the new shape removes
the race structurally rather than winning it: nothing partial is ever visible to the drain, so there
is nothing left to race. `test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_
it` reproduces the exact interleaving the prior review demonstrated with a probe and asserts the
stronger claim (`engine_state.ad_hoc_runs == {}` before the dispatch even errors, not just "ends up
empty") — this is precisely the test `review-stage3d.md` asked for. `test_queue_effector_write_
buffers_inside_a_dispatch_and_appends_directly_outside_one` covers "a write outside any dispatch
still works" (the module-level comment and test both correctly identify this as the path the
existing `test_effector_write_queued_from_background_thread_is_applied_on_next_poll_drain` test
exercises). `test_concurrent_dispatches_do_not_lose_each_others_queued_writes` (two independent
`LuaRuntime`s feeding one `CrewConsole`) covers concurrency in both directions — A's write staying
invisible while open, B's write surviving A's later discard. `test_a_successful_dispatchs_write_
commits_to_the_shared_list` pins the success path unchanged. Per the coordinator's direction, I am
not asking for anything further on this line (no second-order race, no additional rollback
refinement) — what the direction asks me to check is present: a Lua error during dispatch degrades
to "Action file error." (spoken) with the error and traceback logged (D6, unchanged by this
commit), and `run_rule`'s hardening above means even a bare Python exception inside the handler
cannot crash the poll loop. `dispatch_token`/`current_dispatch_token` are correctly removed as
dead code now that nothing filters by identity any more.

**7. Dropped "heading north."** Covered under (1) above — flagged in both the action's own
docstring and `implementation.md`, consistent with D14's "heading is always three digits"
correction. I did not find anything else silently dropped: the deleted `vocabulary.py`/
`command_matcher.py` branches (the eight slotted verbs/parsers for `turn_heading`/`set_speed`/
`speed_step`/`set_altitude`/`altitude_step`) are all accounted for by the rule engine's own
pattern grammar, and `_HVRT_BARE_WORD_TOKENS`'s pre-rule exact-match shortcut (unaffected by this
port) still carries the seven HVRT bare words.

### Checks

Fresh `.venv`s built from `/opt/homebrew/bin/python3.14` (none existed in this worktree;
body-layer: `lupa==2.8` from `pyproject.toml`, editable install pulling in `../world-model`).

- **body-layer**: `ruff format --check src tests` — pass (223 files). `ruff check src tests` —
  pass. `cd body-layer && .venv/bin/mypy src` — pass, 91 source files, 0 issues.
  `.claude/scripts/fast-tests.sh body-layer` — 2678 passed, 1 failed, 4 xfailed. The one failure is
  the named pre-existing, unrelated `test_shipped_effector_config_loads_without_errors` (an empty
  row in `config/sequences/mi-24p/seat-copilot.md`), exactly as the task brief predicted.
- **audio-adapter**: `ruff format --check src tests` — pass (36 files). `ruff check src tests` —
  pass. `.venv/bin/mypy src` — pass, 17 source files, 0 issues. `.claude/scripts/fast-tests.sh
  audio-adapter` — 472 passed, 2 skipped.
- `git status --porcelain` clean before and after (venvs gitignored).

### Required Fixes

None.

### Optional Refinements

- **`accepted-items-ledger.sh plans/speech-rules` only scrapes the original "### Decisions
  Requiring User Input" heading** (U1–U18) — Revision 2's own "### Revision 2's own open decisions
  (U19–U24)" section uses a different heading, so the script silently finds nothing for U19–U24 and
  reports no gap for that range at all (not "all accounted for" — it never looked). I read that
  section by hand instead: U19 (built, `config/rules/flight.lua`'s required third argument),
  U20 (`RULE_GATE_HOLD_TIMEOUT_S`, already shipped Stage 3b), U21 (latest-wins, already shipped
  Stage 3b), U22 (`implementation.md` correctly records it first as "not built in this stage" then,
  later in this same stage's own follow-up section, as built by `d3ec510b`), U23 (named in
  `plan.md` as Stage 3c's own ship gate, not yet reached — consistent, nothing to build here), U24
  (named as "no change for now, revisit at Stage 5" — consistent, nothing to build here). All six
  are accounted for; the gap is only in the mechanical script's own section-heading match, not in
  the plan or the implementation record. Worth renaming the Revision 2 heading to literally
  "Decisions Requiring User Input" (or widening the script's `awk` pattern) so a future reviewer
  does not have to notice this by hand — cheap, not blocking (not a code change in body-layer/
  audio-adapter, so not something to fold into this stage's own commits).
- **`config/rules/README.md`'s category table** could note inline that `"flight_control"` (the
  coarse variant) is also the category HVRT uses — currently true by reading `flight.lua` directly,
  but a reader of the README's own category table alone might expect every flight command to use
  one of the four more specific names. Not required — the README already says the finer precondition
  stays in the action for HVRT; this would only save a cross-reference.

### Verdict
APPROVED

### Review Confidence
Full read. Every changed file in all four commits was read in diff form against `plan.md`
Revision 2 (D9/D13/D14/D16/D18/D19/D20, U19–U24), `review-stage3b.md`'s Required Fix 1 and optional
refinement, `review-stage3d.md`'s re-review finding, and `body-layer/ROADMAP/BL-17.md`'s verbatim
user decisions (Q7/Q9–Q12, "Category gates, before any rule runs," "Settled after the goal check").
Pre-image of every deleted test class was read via `git show` on the commits that removed them and
compared by hand against the new differential tests, not taken on the implementation log's word.
All four checks (format/lint/type/test) run directly in this session for both subprojects, from
fresh venvs. I did not independently re-run the mutation-style probes `review-stage3d.md` used to
verify the prior round's tests — `38dcd6a1`'s new test
(`test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_it`) reproduces that
review's own probe almost verbatim (same drain line, same interleaving), so I read it line-by-line
against that probe's transcript instead of re-running it myself; this is a lighter check than a
fresh mutation and is the one place in this review where I am relying partly on a documented prior
measurement rather than a new one of my own.
