### Review Summary

Reviewed BL-B80 v2 Stages 1–4 (with 3b) on `feature/9k113-sight-pointing`, tip `99eafdf0`
(`git diff 1c433fc6 e16e31e2` is the actual code; `99eafdf0` adds only `implementation.md`'s
record of the early stop). Stage 0 (calibration probe) is known missing, per the plan and
`implementation.md`; not counted against this review. Checked against `plan.md` v2 ("Re-plan,
2026-10-22"), `security-plan-review.md`, `explore-notes.md`, and `implementation.md`'s own account
of the early-stopped session.

All mechanical checks pass, run fresh: aircraft-layer `ruff format --check`/`ruff check`/
`mypy --strict` (27 files) / `pytest` (530 passed, including the luajit-backed
`test_sight_servo_lua.py`/`test_sight_servo_api.py`); body-layer the same (`mypy --strict`, 71
files / `pytest`, 2431 passed, 4 xfailed); `luac5.1 -p` clean on `Export.lua`; the `GETGLOBAL`
mechanical scan lists only genuine DCS/stdlib globals (no own-helper referenced before its `local`).
`test_tuning_defaults_toml.py` passes (the committed `defaults.toml` matches a fresh regeneration).

The frame question this subsystem has broken on four times before (`[[project_recurring_field_
of_regard_enforcement_gap]]`) is **correct here**: both the Python `SightHead._clamp_gimbal` and
the Lua `run_sight_servo` gimbal clamp operate on body-relative az/el computed through the
heading+pitch+bank rotation (`body_relative_direction`/`sight_world_to_body`, the matched
Python/Lua twins) — the airframe-boresight frame the 2026-10-20 sortie correction (F5) requires,
not a ground-anchored one. The removal of v1's position-model pieces (`ShowMenu`, `ai_believed_on`,
874/876-as-position, `GYRO_ALIGNMENT_S`) is complete — grepped clean except one surviving docstring
mention, as `implementation.md` itself states. The `t_sim` security required-change is implemented
correctly at both layers (API `isfinite`+bound+sign check, Lua presence+bound check, whole-command
rejection on failure). `body-layer/CLAUDE.md`'s invariant edit matches the plan's text verbatim.
F2/F3 fences exist and are exercised by real test cases (not just declared).

However, three things need fixing before this goes to DoD: the **rendered** `config/defaults.toml`
carries a severe content-loss corruption and a cosmetic markup corruption for the two new
`sight_head`/`attack_run` tunables (finding 1 — exactly the class of defect this project's own
process note warns a diff-reading reviewer will miss); the F4 differential no-leak test is
narrower than the plan's own spec and narrower than what Security's plan review approval rested on
(finding 2); and the plan's explicitly-named "wiring test + mutation" requirement — called out by
name because this project has three prior leaf-tested/wiring-untested defects on exactly this
shape — was not built for either Stage 3's basic head-cap wiring or Stage 3b's seen-aim wiring
(finding 3).

### Required Fixes

- **Finding 1 — the rendered `config/defaults.toml` is corrupted for both new tunables in this
  diff, not just the source comment.** Per this project's own standing instruction ("check the
  rendered file, not the `#:` comment"), I read `config/defaults.toml` itself, not
  `sight_head.py`'s source:

  - `body-layer/config/defaults.toml:28` (`SEEN_AIM_HEIGHT_OFFSET_M`) renders as:
    > `seen_world_direction`'s own aim-point correction (`[[BL-B80]]`, plan Decision 6, pilot
    > 2026-10-22, verbatim: *"no idea.`

    The actual source comment (`body-layer/src/belief/attack_run.py:143-146`) reads *"no idea.
    let's assume on ground"*) — the pilot's own quoted answer, which is the entire rationale this
    comment exists to record. The rendered line cuts off mid-quote, drops the closing `*"` and the
    rest of the sentence, and also drops the comment's *opening* backtick (the line should start
    `` `seen_world_direction`'s ``, not `seen_world_direction`'s`). Root cause:
    `tools/generate_defaults.py`'s `_SENTENCE_SPLIT` regex splits on the first unescaped `.` not
    adjacent to a digit — including the period *inside* the pilot's quoted sentence ("no idea.")
    — so the "first sentence" extractor treats an embedded quotation's own full stop as the
    comment's sentence boundary. This is a real instance of exactly the bug class
    `docs/AGENT_ROLES.md`/this project's tuning notes warn about: a rendered description reaching
    nobody, except here it's not a second sentence being dropped, it's the pilot's own stated
    reason for the value being truncated into nonsense.
  - `body-layer/config/defaults.toml:140` (`SLEW_EL_DPS`) renders as:
    > Elevation's own slew rate -- same source as `` `SLEW_AZ_DPS. ``

    (confirmed byte-for-byte with `od -c` — the closing backtick after `SLEW_AZ_DPS` is genuinely
    absent, not a terminal-rendering artifact). Source
    (`body-layer/src/belief/sight_head.py:51`) correctly reads `` same source as `SLEW_AZ_DPS`. ``
    — closing backtick, then the full stop. Root cause: `_first_sentence`'s
    `parts[0].strip().strip("*\`")` unconditionally strips trailing backticks/asterisks from the
    extracted sentence, intended to remove markup the split's own optional
    `(?:\*\*|`)?` group consumed *after* the period — but here the backtick is the correct,
    legitimate close of an inline-code span sitting *before* the period (the normal, correct
    Markdown form), and the blanket `.strip("*\`")` eats it regardless of which case produced it.

  Both are new to this diff (`git diff 1c433fc6 e16e31e2 -- body-layer/config/defaults.toml`
  confirms both added lines) and both are a generator defect exposed by, not independent of, this
  diff's two new comments — the regex/strip bug in `tools/generate_defaults.py` is generic and
  will recur on the next tunable whose first sentence contains an embedded quoted period or ends
  with a legitimately-closed inline-code span. `test_tuning_defaults_toml.py`'s staleness check
  passes on both corrupted lines, because it only proves the committed file matches a fresh
  regeneration — it cannot catch a bug baked into the generator itself, per this project's own
  "would it fail if someone edited one side only" caveat. **Fix, both parts**: (a) rewrite
  `SEEN_AIM_HEIGHT_OFFSET_M`'s comment so its first sentence does not contain an embedded
  sentence-ending period inside the pilot's quote (e.g. move the quote to a later sentence, or
  rephrase it without an internal full stop), since this is the more urgent, content-losing half;
  (b) fix `tools/generate_defaults.py`'s `_first_sentence` so it does not strip a backtick that
  closes an inline-code span immediately before the sentence-ending period (the strip should only
  remove markup the split's own trailing-markup group actually matched, not blindly strip the
  sentence's last character class) — this is a latent bug independent of this feature and will
  keep corrupting future tunables' rendered descriptions until fixed. Regenerate and re-read the
  rendered file, not just the diff, after either fix.

- **Finding 2 — F4's differential no-leak test is scoped to `ContactStore` positions only, not the
  plan's own F4 spec.** Plan (`plan.md` lines 338, 451) specifies: *"`ContactStore` position
  estimates, `MissionMemory` appends, every utterance and every `TOOL_SET` result must be
  identical; only the head direction and the wire goal may differ"*, and Security's plan review
  explicitly endorsed F4 as *"the strongest fence in the set... a behavioral proof... rather than
  only a static grep"* precisely because it independently verifies the no-leak claim for every
  consumer, not just the one a reader happens to check. The implemented test
  (`body-layer/tests/test_logger.py:3243-3279`, `TestF4DifferentialNoLeak`) asserts only
  `{c.id: c.position for c in runner.store.contacts}` is identical with/without the seen-aim
  channel; its own docstring states the rest ("`MissionMemory`/`TOOL_SET`/utterance identity")
  rests on "the structural fact that `seen_world_direction`'s only consumer is `sight_head.py`" —
  i.e. it falls back to the same grep-based (F2/F3) argument Security's review explicitly said a
  behavioral test was needed *in addition to*, not instead of. A grep proves nobody imports the
  function; it does not prove the function's *value* cannot reach those sinks through some other
  path (e.g. a future caller threading the head's `aim_source` or `goal_world_*` fields into a
  callout or a `MissionMemory` entry — exactly the leak class F4 was designed to catch
  independently of whether anyone remembered to grep). **Fix**: extend the two-poll
  `_f4_scenario` (or add a longer one) so it also asserts identical `MissionMemory` entries (e.g.
  via `runner.store`'s mission-memory sink if wired in the test harness, or a minimal
  `MissionMemory` instance passed to the runner) and identical spoken output
  (`crew_console.output`/drained events) between the two runs — matching the plan's stated scope,
  not a narrower one the test's own docstring talks its way around.

- **Finding 3 — the plan's explicitly-named "wiring test + mutation" requirement was not built**,
  for either Stage 3 or Stage 3b. Plan Stage 3 (`plan.md` line 441-442) calls for *"a wiring test
  through `run_once` (the recurring leaf-tested/wiring-untested defect, three prior instances) and
  a mutation of that wiring to show the test catches it"*; Stage 3b (line 452-453) calls for the
  analogous *"a `run_once` wiring test that a seen look moves the next poll's wire goal onto the
  true direction while the contact's believed position is unchanged, plus a mutation (goal from
  belief) the test catches."* Both are named explicitly because this project has three prior
  instances of exactly this failure shape (a test exercises the leaf function correctly but never
  proves the runner actually wires it in) — the plan is quoting its own prior incident, not
  adding boilerplate. Grepped `test_logger.py`/`test_sight_head.py` for `mutation`: the only two
  hits (lines 4756, 4854) are about the guidance-unit power-up sequencer and the "ready" speech
  latch, unrelated to `sight_head`/`select_sight_goal` wiring. `test_run_once_caps_a_sight_tier_
  optic_until_the_head_is_free` (test_logger.py:3108) and
  `test_advance_sight_head_seen_goal_feeds_through_to_world_goal` (test_sight_head.py:393) are real
  wiring/unit tests that currently pass, but neither is accompanied by a demonstrated mutation
  showing the test would fail if the wiring broke — the exact gap the plan is naming. **Fix**: add
  at least one mutation per stage (e.g. for Stage 3, temporarily bypass the `optic_decision.optic`
  → `is_sight_tier` gating at the `_apply_active_gaze` call site and confirm the existing test
  fails; for Stage 3b, force `select_sight_goal` to always return the `belief` row and confirm the
  seen-goal wiring test fails), demonstrate the red, then restore — matching this project's "show
  the red" convention for a test asserting a positive wiring claim.

### Optional Refinements

- `tools/generate_defaults.py`'s `_SENTENCE_SPLIT` regex has no special handling for a quoted
  pilot verbatim containing its own full stop, which is now a second occurrence in this codebase's
  tunable comments (any future `verbatim: "..."` quote with internal punctuation will hit the same
  bug) — worth a project-wide grep for other tunables whose comment contains an embedded quote with
  a period, once finding 1 is fixed, to confirm this is the only other instance (optional, since
  finding 1's fix for this specific comment is required regardless).
- `implementation.md`'s own "Deviations" section already documents the single-commit/no-per-stage-
  notes/Stage-0-not-built deviations honestly; no additional note needed there.

### Verdict

NEEDS REVISION

The core mechanism — frame correctness on the gimbal clamp (this subsystem's own four-time-recurring
defect class), the `t_sim` security fix, the removal of v1's position-model pieces, the Lua/Python
rate-limit and world↔body rotation twins, and the overall Stage 1–4/3b scope — is built correctly
and matches the plan. All three required fixes are narrower in scope than finding 1's severity
might suggest: finding 1 is a two-line comment fix (plus a small, separable generator bug) with no
runtime-behaviour implication; findings 2 and 3 are both "extend an existing, correctly-targeted
test" rather than "the mechanism is wrong." None of the three touches `Export.lua`'s per-frame
servo logic, the part of this change with no automated coverage at all, which I read in full and
found correct against the plan's own step-by-step spec (closed/open-loop switch, mark-validity
gate, clip-edge re-anchor, stall detection, the shared dither/flicker parity flag). Recommend:
Implementer fixes the three items above (finding 1 first, since it is the one a live sortie's
pilot could actually open `defaults.toml` and read), Reviewer re-checks the diff, then proceed to
DoD. Flight B (Stage 4's live sortie) should not be flown to validate anything finding 2/3 would
have caught — this is a documentation/test-coverage gate, not a live-behaviour risk, so it does not
block a flight test of the loop itself if the user wants one before the re-review lands.

### Review Confidence

Full read of every changed body-layer/aircraft-layer source file in the diff: `Export.lua`'s
`run_sight_servo` and its helper functions end to end; `sight_head.py` end to end; `geometry.py`'s
new/changed functions; `attack_run.py`'s refactor and `seen_world_direction`; `optic_policy.py`'s
changed sections; `logger.py`'s changed call sites (gyro-alignment cap, `last_sight_look_sim`
stamping, `write_sight_target` wiring); `sight_effector.py`'s lamp readback changes;
`sight_trace_writer.py`; `aircraft_client.py`; `command_sender.py`; `api/server.py`'s new handler,
read in full including the `t_sim` bound; `schema/sight_servo.py`. `body-layer/CLAUDE.md`'s diff
checked word-for-word against the plan's specified text. `config/defaults.toml` read as the
rendered file (confirmed byte-for-byte with `od -c` on the corrupted line), not inferred from the
source comment. Test files read for coverage-gap verification (F2/F3/F4, the wiring tests, the
mutation grep) rather than for their own correctness. All mechanical checks (`ruff format --check`,
`ruff check`, `mypy --strict`, `pytest`, `luac5.1 -p`, the `GETGLOBAL` scan,
`test_tuning_defaults_toml.py`) run fresh, not taken from `implementation.md`. Not independently
re-derived: the mark-scale/boresight calibration constants and the Kp/FF_GAIN tuning numbers,
which the plan itself states are Stage 0/Flight A placeholders, not yet calibrated — nothing to
verify there beyond confirming they are labelled as such (they are).

---

### v2 re-review (fixes)

Reviewed the three v2 required fixes against the fix commits (`28d45a09`, `ebd48c41`, `fdfe3948`)
and `implementation.md`'s "Review fixes (v2 review, 2026-10-22)" section, plus a light read of the
Stage 0 probe/card the main loop added (`0c542d5f`). Branch fast-forwarded cleanly from `49fa122b`
to the named tip `816250c8` (strict ancestor, clean tree).

**Finding 1 — `defaults.toml` generator.** Read every rendered entry the fix claims to repair, not
just the two the original finding named: `SEEN_AIM_HEIGHT_OFFSET_M`, `SLEW_EL_DPS`, and all 7
"already on the branch" repairs (`ATTACK_RUN_ELEVATION_GATE_DEG`,
`ATTACK_RUN_LINED_UP_AZIMUTH_DEG`, `BUILT_UP_VILLAGE_MAX_AREA_M2`, `ATTACK_TARGET_LOS_MAX_AGE_S`,
`FIRING_MAX_AGE_S`, `IDENTITY_HALF_LIFE_S`, `MEDRES_ANGULAR_RADIUS_RAD`). All 9 render correctly
against their source comments (traced the `_SENTENCE_SPLIT`/`_first_sentence`/`_join_comment_lines`
logic by hand for each, including the hand-wrapped-backtick join case on
`ATTACK_RUN_LINED_UP_AZIMUTH_DEG` and the nested-quote-inside-backtick case on
`BUILT_UP_VILLAGE_MAX_AREA_M2`/`ATTACK_TARGET_LOS_MAX_AGE_S`) — none of the 9 lost or gained markup,
and no sentence boundary moved incorrectly. `test_generate_defaults_first_sentence.py` (7 tests)
passes. **Verified by mutation, not just by reading the diff**: reverted `_SENTENCE_SPLIT` to its
pre-fix form (no quote-balance lookahead) — `test_period_inside_a_quoted_verbatim_does_not_end_the_
sentence` failed exactly as expected. Restored (confirmed by `shasum` matching pre-mutation), then
separately reverted `_first_sentence`'s closing-markup handling to a blanket
`sentence.strip("*\`") + "."` — three tests failed exactly as expected
(`test_closing_backtick_before_the_period_is_kept`,
`test_opening_backtick_at_the_start_is_kept`,
`test_bold_closing_after_the_period_mid_sentence_is_put_back`). Restored, `shasum` matched again.
Both halves of the fix are load-bearing, independently.

**Finding 2 — F4 widened.** Read `_f4_poll`/`_f4_scenario`/`_f4_tool_results` and the four test
methods in `TestF4DifferentialNoLeak` in full: the scenario now drives `run_once`, the attack-run
drain, the real `_mission_memory_step`, and the event/positional-reply drains for four polls, with
`select_target`/`mark_target`/`engage` commands, and compares `ContactStore` positions,
`MissionMemory` entries, every utterance, and every `TOOL_SET` result (checked against `TOOL_SET`
itself so a new tool can't escape the fence) — matching the plan's own F4 spec, not the narrower
`ContactStore`-only scope the original finding caught. Ran the suite green at baseline, then
**independently constructed a new mutation** (not one of the three implementation.md already
reports) to confirm the widened assertions are load-bearing rather than coincidentally passing:
edited `logger._mark_target_fn`'s `mark_target` to add `+0.5` to `now_sim` whenever
`runner.sight_head.aim_source == "seen"` — a direct simulation of the leak class F4 exists to
catch (a seen-aim artifact reaching a `MissionMemory` entry's `t_sim`).
`test_mission_memory_is_identical_with_and_without_the_seen_aim` and
`test_tool_set_results_are_identical_with_and_without_the_seen_aim` both failed red exactly as
expected (the latter via `get_contact_history`'s folded mark entry); the position and utterance
tests correctly stayed green, since this particular mutation doesn't touch either path — consistent
with the fence being scoped per-sink rather than one undifferentiated assertion. Reverted via
`git checkout --`, confirmed a clean diff. (A first attempt at this mutation, multiplying by the
seen goal's azimuth value, passed by accident because the scenario's seen azimuth happens to be
exactly 0° — a reminder that a mutation's own correctness has to be checked, not just whether the
test went green or red.)

**Finding 3 — wiring tests.** Read both new tests
(`test_run_once_perceives_through_the_world_stabilised_head_not_the_desired_aim`,
`test_run_once_seen_look_moves_the_next_goal_onto_the_true_direction`) in full; both match the
plan's Stage 3/3b wording. Ran green at baseline, then independently reproduced both of
`implementation.md`'s named mutations rather than taking them on account: (a) in
`_apply_active_gaze`'s sight-tier branch, fed `decision.look_azimuth_deg` instead of
`sight_head_body_az_deg` into `actual_aim_azimuth_deg` — the Stage 3 test failed red
(`[50.0, 50.0, 50.0]` instead of `[0.0, 20.0, 10.0]`); (b) in `run_once`, forced
`advance_sight_head`'s `look_contact` argument to always be `None` — the Stage 3b test failed red
(`aim_source` stayed `"belief"`, never reached `"seen"`). Both reverted via `git checkout --`,
confirmed clean.

**Stage 0 (`0c542d5f`).** Light read of `Export.probe-9k113-calibration.lua` (`luac5.1 -p` clean)
and `docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md`: the card's block table (settle / A / E1-E2 /
E3 / B / D / F / end) and "Measures" list map directly onto the plan's "Flight A" spec (mark scale
both axes, az/el boresight from 962's edges, 555's clip edges and elevation closed-loop
feasibility, azimuth steady error vs. run 10, AI-rate frame in a turn) plus the separate cold-start
READY-lamp check from Part 2. Branch and run command are named for the pilot per this project's
"naming the branch is the only channel" rule. Not independently re-derived against the probe
script's own per-block timing logic (Stage 0 is outside the reviewed batch per the plan's own
"Stage 0 is a probe, outside the batch"); this is a scope-fit check only, not a probe-logic review.

**Checks, run fresh:**
- body-layer: `ruff format --check` (pass, 170 files), `ruff check` (pass, `src tests tools`),
  `mypy src` (pass, 71 files), `pytest` (2443 passed, 4 xfailed — matches `implementation.md`'s
  own count), `test_tuning_defaults_toml.py` (pass, in isolation).
- aircraft-layer: `ruff format --check` (pass, 75 files), `ruff check` (pass), `mypy src` (pass, 27
  files), `pytest` (533 passed — 3 more than `implementation.md`'s last-recorded 530 for this
  subproject; this fix diff is body-layer-only per `implementation.md` and the file list below, so
  the discrepancy predates this fix and is not attributable to it; not a regression since 0
  failures either time), the luajit-backed `test_sight_servo_lua.py`/`test_sight_servo_api.py`/
  `test_sight_target.py`/`test_exponent_float_fix.py` run by name (52 passed), `luac5.1 -p` clean
  on both `Export.lua` and `Export.probe-9k113-calibration.lua`, the `GETGLOBAL` scan (clean — only
  genuine DCS/stdlib globals and the file's own pre-existing `DUMPED_*` debug-dump flags, no
  own-helper referenced before its `local`).
- `git status --porcelain` clean throughout; no leftover debug/TODO code in the three fix commits
  (`git diff` grepped for `TODO`/`FIXME`/`XXX`/`print(`, no hits).

**Memory.** `.claude/agent-memory/reviewer/feedback_generator_strips_legitimate_closing_backtick.md`
and `.claude/agent-memory/reviewer/project_bl_b80_v2_f4_scope_and_missing_mutation_tests.md` (my own
v2-review memories) updated to record both fixes as closed, keeping the transferable lesson in each.

### v2 Re-review Verdict

APPROVED

All three required fixes are correct, complete, and independently verified by mutation (not taken
on `implementation.md`'s account) — including one mutation of my own construction beyond the three
the implementer already reports for Finding 2. No new required fixes. Proceed to DoD.

### v2 Re-review Confidence

Full read of the fix diff (`defaults.toml`'s rendered form for all 9 repaired entries, not just the
two the original finding named; `tools/generate_defaults.py`'s rewritten functions end to end;
`test_generate_defaults_first_sentence.py`; the widened `TestF4DifferentialNoLeak` and its
scenario helpers in full; both new `run_once` wiring tests). Independent mutation of all three
fixes (five mutations total: two for Finding 1's two sub-bugs, one newly constructed for Finding 2
beyond the implementer's own three, two reproducing Finding 3's named mutations), each confirmed
red then cleanly restored (`git checkout --`/`shasum`). All four subprojects' mechanical checks run
fresh. The Stage 0 probe/card read for scope-fit only, not for probe-logic correctness, consistent
with it being outside the reviewed batch.

---

## v1 (superseded)

### Review Summary

Reviewed BL-B80 Stages 1–3 (`feature/9k113-sight-pointing`, `edc8dd73..4c887644`) against
`plans/9k113-sight-pointing/plan.md` (including the 2026-10-22 coordinator amendments),
`explore-notes.md`, `implementation.md`, and `security-plan-review.md`.

All mechanical checks pass: `ruff format --check`, `ruff check`, `mypy --strict` (26 source files
aircraft-layer / 70 body-layer), `pytest` (459 passed aircraft-layer; 2417 passed, 4 xfailed
body-layer), `luac5.1 -p` on `Export.lua`, and the `GETGLOBAL` mechanical scan for a local used
before its own declaration (clean — only stdlib/DCS globals appear). `EXPORT_SCRIPT_VERSION`
(`"2026-10-22"`) matches collector `EXPECTED_EXPORT_VERSION`. The elevation command/readback-domain
split (`sight_elevation_raw_to_deg` vs `sight_elevation_deg_to_raw`) is arithmetically correct
against the probe findings, well-tested, and the implementer's own mid-implementation self-catch
of the first (wrong) version is a good sign of care. `home_phase` correctly now follows the
observed arg-886 edge, re-derived fresh every poll in `run_once`, with the command-driven path
removed from the `observ_transition` drain block. `defaults.toml`'s rendered `GYRO_ALIGNMENT_S`
entry is correct and regenerates clean. Security's own plan-review findings (bound clamp,
loopback-only, `AC-B11`) are all implemented as recommended.

However, `Export.lua`'s per-frame sight owner — the one part of this change no automated test can
reach — has a defect that defeats its own central mechanism (finding 1), and a second, broader
defect in body-layer couples sight-head readback into generic gaze perception regardless of which
optic is actually in use (finding 2), which is exactly the kind of co-moving-field/no-omniscience
coupling this plan's own table is meant to guard against. Both were found only by reading the code
rather than the diff summary, and neither is caught by the existing (otherwise thorough) test
suite.

### Required Fixes

- **`Export.lua:1215-1239` — the AI-off detector's `ai_off_since` accumulator is reset to `t` every
  frame regardless of whether a press fired, so it can never accumulate past one frame's `dt`.**
  The "Reset either way" line (1233-1236) sits inside the outer
  `if commanded_nontrivial and not readback_responding then` block, at the same indentation as the
  two inner `if`s, so it runs unconditionally every frame this branch is taken — not only when the
  inner `if (t - ai_off_since) >= AI_OFF_DETECT_TIMEOUT_S ...` actually fires. Concretely: frame N
  sets `ai_off_since = t_N` (first time, `ai_off_since` was `nil`); frame N+1 finds
  `ai_off_since ~= nil`, checks `(t_{N+1} - t_N) >= 0.5s` (false at any normal frame rate, ~0.0167s
  at 60 fps), then unconditionally overwrites `ai_off_since = t_{N+1}` — so the *next* frame's
  check is against a interval that is again only one frame wide. `(t - ai_off_since)` can never
  reach `AI_OFF_DETECT_TIMEOUT_S` (0.5 s) except across a genuine ≥0.5 s frame stall. This defeats
  the entire reactive `ShowMenu` mechanism the coordinator amendments (2 and 3) require — "met
  within one timeout of the sight becoming usable" never actually happens under normal frame
  timing, and `ai_believed_on` can then never recover once DCS's own AI is genuinely off (no press
  ever fires to turn it back on). No automated test reaches this file, so nothing caught it; a
  manual trace of the control flow does. **Fix**: only set `ai_off_since = t` when the press
  actually fires (move the reset inside the inner `if (t - ai_off_since) >= AI_OFF_DETECT_TIMEOUT_S
  ...` block, immediately after `ai_believed_on = false`), and drop the unconditional line 1236
  reset entirely — `ai_off_since` should hold its original stuck-since timestamp until either the
  readback responds again (handled by the `else` branch, line 1238) or a press fires and restarts
  the window.

- **`body-layer/src/logger.py:792-793` — `sight_az_raw`/`sight_elev_raw` are passed into
  `_apply_active_gaze`/`advance_sight_aim` unconditionally, regardless of which optic is actually
  resolved this poll**, and `GuidanceUnitState.sight_az_raw`/`sight_elev_raw` stay non-`None` for
  the rest of the mission once any sight readback sample has ever arrived (`refresh_readback` only
  updates them on a numeric sample; it never clears them back to `None`). The result:
  `OpticState.actual_aim_azimuth_deg`/`actual_aim_elevation_deg` — consumed generically by
  `perception/naked_eye_source.py` to build the gaze cone for *naked-eye and binocular* perception,
  not only sight perception — gets anchored to the literal 9K113 head position whenever a readback
  exists, even while `optic_decision.optic` is `UNAIDED_OPTIC` or `BINOCULAR_OPTIC`. This is most
  visibly wrong during the gyro-alignment window itself: the optic is deliberately capped to
  `BINOCULAR_OPTIC` there (plan Stage 1, `logger.py:768-772`) *specifically so perception does not
  come from the sight*, but the very next lines (782-793) feed the sight's own raw readback into
  the field that binocular/naked-eye perception reads its look direction from — defeating the
  purpose of the cap, and doing so for the rest of the mission after the sight's first use, not
  only during the alignment window. No test combines a non-sight optic with a set
  `sight_az_raw`/`sight_elev_raw` (`test_logger.py`/`test_optic_policy.py` grepped — none found),
  so this gap is real, not just unexercised. **Fix**: gate passing `sight_az_raw`/`sight_elev_raw`
  at the `_apply_active_gaze` call site on `optic_decision.optic` (the post-cap value) being
  `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`; pass `None, None` otherwise so `advance_sight_aim` falls
  through to its pass-through model for every other optic, as the model's own docstring already
  describes it should.

- **Missing `run_once`-level integration test for the gyro-alignment optic cap**, explicitly
  specified by the plan's own Stage 1 test list: *"a `run_once`-level test that an OBSERV-on edge
  followed immediately by a poll inside the window never yields `SIGHT_WIDE_OPTIC`/
  `SIGHT_NARROW_OPTIC`"*. Only pure-function `in_gyro_alignment` unit tests exist
  (`test_sight_effector.py:371-384`); nothing exercises the actual wiring at `logger.py:768-772`
  through `run_once`/`ConsolePerceptionRunner`. `implementation.md`'s "Test-impact check" states
  "No test named in the plan turned out to be missing... the plan's own 'Tests:' bullets per stage
  matched the actual suite" — this is not accurate for this one bullet. Add the integration test;
  it would also have been the natural place to catch the second required fix above (asserting the
  gaze direction used for perception during the window is not anchored to a stale sight readback).

- **`Export.lua:1076` — `sight_point_quiet`'s `local dev = GetDevice(DEV_I9K113)` is the one
  unguarded `GetDevice` call in the entire file.** Every other call site
  (`push_cockpit_switch_state`, `handle_cockpit_switch_command`, `run_sight_pointing`'s own OBSERV
  read and AI-on/off readback reads, the `ShowMenu` presses, etc.) wraps `GetDevice` inside
  `safe_call`/`pcall`, consistent with this file's own stated posture ("DCS internals here are
  heavily unverified ... every failure so far ... has been from an unguarded call", top-of-file
  comment). `run_sight_pointing` itself runs unwrapped from `LuaExportAfterNextFrame` (same as its
  per-frame siblings `push_ptt_state`/`push_spu8_state`/`push_cockpit_switch_state`), so an
  exception from this one unguarded line would propagate out of the frame callback uncaught — a
  risk this environment has no console to diagnose. **Fix**: wrap it the same way, e.g.
  `local dev = safe_call(function() return GetDevice(DEV_I9K113) end)`.

- **`test_logger.py:2980` (`test_observ_off_command_stops_the_sight_through_the_real_poll_loop`) —
  stale docstring now gives false assurance**, confirmed per the implementer's own flag in
  `implementation.md`. The docstring claims the test "Reproduces the exact
  `observ_transition == 'off'` drain block `logger.py`'s poll loop runs," but that drain block no
  longer sets `home_phase` there (`[[BL-B80]]` moved that derivation into `run_once`, reading the
  observed arg-886 edge) — the test's own local snippet (lines 3015-3020) still sets `home_phase`
  directly from the command, which is no longer what production code does. A future reader could
  mistake this test as current coverage for OBSERV-off → `home_phase` behaviour, when it tests a
  path that no longer exists. **Fix**: correct the docstring to state it covers only the
  hands-busy-suppression/cockpit-write half of the old drain block (still accurate), not the
  `home_phase` transition, and/or rename the test to make that scope explicit.

### Optional Refinements

- `run_sight_pointing`'s elevation rate selection (`Export.lua`, the `elev_rate` branch) reads the
  *current* `commanded_elev_cmd`'s sign rather than the target's, so a single step crossing zero
  uses the wrong-side rate for that one step. Cosmetic — the plan's own Risks section already
  accepts the derived-formula/rate-mimic risk as cosmetic, and this is a sub-case of that. Not
  blocking.
- The cross-domain coupling the implementer flagged (`sight_elevation_deg_to_raw`/
  `sight_elevation_raw_to_deg` sharing bare `float` with nothing in the type system distinguishing
  "command value" from "readback argument") is real but both current call sites use the correct
  function for their domain and are tested. A `NewType` per domain would close this structurally;
  worth doing if a third call site is ever added, not required now.
- `security-plan-review.md`'s housekeeping note (update `AC-B11.md`'s endpoint count to reflect the
  sixth endpoint sharing the unbounded-`Content-Length` shape) is still open — not a gate, but easy
  to fold into this change's own commit rather than a future one.

### Verdict

NEEDS REVISION

Two required fixes are correctness defects in the exact area the plan itself flagged as having no
automated test coverage (`Export.lua`) and in the no-omniscience/co-moving-fields boundary this
project treats as structural (`logger.py`'s gaze/optic coupling) — both are real, not stylistic,
and the second is broader than the gyro-alignment window the plan named: it affects naked-eye and
binocular perception for the remainder of any mission once the sight has been used once. The
missing integration test and the stale test docstring are smaller but both erode exactly the
safety net this feature most needs, given it has no live-DCS automated coverage at all. The
`GetDevice` guard is a consistency/robustness fix, not a demonstrated live failure, but costs
nothing to fix alongside the others.

None of this reflects on the elevation-conversion derivation, the tuning entry, the security
posture, or the mechanical checks — all of those are clean. Recommend: Implementer fixes the five
items above, Reviewer re-checks the diff (the `Export.lua` detector fix and the `logger.py` gating
fix in particular, since both are exactly the kind of thing a second skim could again miss), then
proceed to DoD. The live sortie (Stage 4) should not be flown against the current tip — the AI-off
detector not firing would be indistinguishable, from the cockpit, from "DCS's AI just happens to
stay on all flight," which is a dangerous thing to let an acceptance test quietly pass on.

### Review Confidence

Full read of every changed body-layer/aircraft-layer source file in the diff (`Export.lua` end to
end, including constants and both new functions; `sight_effector.py`, `optic_policy.py`'s changed
sections, `logger.py`'s changed call sites, `aircraft_client.py`, `command_sender.py`,
`api/server.py`'s new handler, `sight_trace_writer.py`). Test files read for coverage-gap
verification (grepped and spot-read, not read line-by-line in full) rather than for their own
correctness — all currently pass and are not themselves in question. Plan/explore-notes/
implementation/security-review docs read in full.

---

### Re-review (fixes)

Reviewed the fix diff (`385c3b34..157b78b1`) against the five required fixes above, per
`implementation.md`'s "Review fixes" section. Branch fast-forwarded cleanly from `9284cd34` to the
named tip `157b78b1` (strict ancestor, clean tree).

**Fix 1 — `Export.lua`'s `ai_off_since` accumulator (the one requiring most scrutiny, no automated
test reaches this file).** Hand-traced the corrected control flow frame by frame:

- Frame where the branch is first entered (`ai_off_since == nil`): sets `ai_off_since = t`, then
  the inner timeout check is false (0 s elapsed) — correctly does not fire or reset.
- Subsequent frames while still stuck: `ai_off_since` is left untouched (the unconditional "reset
  either way" line is gone), so `(t - ai_off_since)` now genuinely grows frame over frame until it
  crosses `AI_OFF_DETECT_TIMEOUT_S` (0.5 s) — this is the fix, confirmed by reading the diff and
  the surrounding function (`Export.lua:1209-1241`).
- Timeout fires: press issued, `ai_believed_on = false`, `ai_off_since` reset to `t` *inside* the
  same inner `if`, immediately after the press — this restarts the window rather than leaving it
  stuck at the original timestamp, which is what lets the re-press interval
  (`AI_OFF_REPRESS_INTERVAL_S`, 2.5 s) work: the next timeout accumulates fresh from the press time,
  and the repress gate (`last_showmenu_press_t`) independently prevents a second press before 2.5 s
  regardless of the timeout's own state.
- Recovery path (readback starts responding again): the `else` branch (`ai_off_since = nil`) is
  unchanged and still correct — confirmed this branch was not touched by the fix and did not need
  to be.
- OBSERV falling-edge / mission-stop interplay: both reset blocks (`Export.lua:1148-1151`,
  `1312-1315`) independently zero `ai_off_since`/`last_showmenu_press_t`/`ai_believed_on` to `nil`/
  `false`, and `run_sight_pointing` is itself gated on OBSERV being on (`observ_on_since ~= nil`
  before reaching the detector block) — the fix does not interact with either reset path, and
  re-reading them confirms no stale `ai_off_since` can survive an OBSERV-off/mission-stop into the
  next OBSERV-on. The `GYRO_ALIGNMENT_S` gate (`(t - observ_on_since) >= GYRO_ALIGNMENT_S`) around
  the whole detector block is also untouched and still correctly prevents the detector from even
  starting to accumulate during the gyro-alignment window — no interplay bug introduced.
- Mechanically confirmed the fix introduces no new unresolved global: `luac5.1 -l -p` + the
  `GETGLOBAL` scan on the post-fix `Export.lua` lists only genuine DCS/stdlib names (`GetDevice`,
  `LoGet*`, `pcall`, `math`, etc.) — no own-helper (e.g. `safe_call`) appears, which would indicate
  a local-before-declaration mistake introduced by the edit's reindentation.

This fix is correct and complete. The implementer's own manual-trace verification in
`implementation.md` matches independent re-derivation here.

**Fix 2 — `logger.py`'s readback gating on the post-cap optic.** Confirmed `is_sight_tier` is
computed from `optic_decision.optic` *after* the gyro-alignment cap (`replace(optic_decision,
optic=BINOCULAR_OPTIC)`) has already run and been assigned back to `optic_decision` — the gating
reads the same post-cap value `self.optic` is set from, not the pre-cap `decide_optic` output, so
the cap and the gate cannot disagree. `sight_az_raw`/`sight_elev_raw` are passed as `None, None`
whenever `optic_decision.optic` is not `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`, matching
`advance_sight_aim`'s own documented pass-through fallback.

**Verified by mutation, not just by reading the diff** (reviewer protocol): reverted the gating
(restored the unconditional `sight_az_raw=self.guidance_unit_state.sight_az_raw` /
`sight_elev_raw=self.guidance_unit_state.sight_elev_raw` call), reran
`test_run_once_caps_a_sight_tier_optic_during_gyro_alignment` in isolation — it failed exactly as
expected (`actual_aim_azimuth_deg == 68.18181818181819`, not `12.0`). Restored the fix, reran — the
test passes clean. The guard is load-bearing, not a comment.

**Fixes 3-5.** The new `run_once`-level integration test
(`test_run_once_caps_a_sight_tier_optic_during_gyro_alignment`) matches the plan's Stage 1 test
list wording exactly, exercises both the window-held and window-lifted cases, and — per the
mutation check above — doubles correctly as fix 2's test. `Export.lua:1076`'s `GetDevice` call is
now wrapped in `safe_call`, consistent with every other call site in the file. The stale docstring
on `test_observ_off_command_stops_the_sight_through_the_real_poll_loop` is corrected to state its
actual (narrower) scope accurately.

**Checks (run independently, not taken from `implementation.md`):**
- aircraft-layer: `ruff format --check` (pass, 71 files), `ruff check` (pass), `cd aircraft-layer
  && .venv/bin/mypy src` (pass, 26 source files), `pytest` (459 passed, including
  `test_dcs_export_lua_local_order.py` and `test_dcs_export_lua_syntax.py`), `luac5.1 -p
  Export.lua` (pass), `GETGLOBAL` scan (clean).
- body-layer: `ruff format --check` (pass, 160 files), `ruff check` (pass), `cd body-layer &&
  .venv/bin/mypy src` (pass, 70 source files), `pytest` (2418 passed, 4 xfailed).

**No new scope, no leftover debug/TODO code** in the fix diff (`Export.lua`, `logger.py`,
`test_logger.py`, `implementation.md` — the only four files touched between the two tips).

### Re-review Verdict

APPROVED

All five required fixes are correct, complete, and verified independently (including by mutation
on the one fix a test now covers). The elevation-conversion derivation, tuning entry, security
posture, and mechanical checks remain clean from the original review and were unaffected by this
diff. Proceed to DoD. The live sortie (Stage 4) can now be flown against this tip — the AI-off
detector's reactive `ShowMenu` press should actually fire within ~0.5 s of a genuine AI-off
condition persisting past the gyro-alignment window, which was not true at the previously reviewed
tip.

### Re-review Confidence

Full read of the fix diff (`Export.lua`, `logger.py`, `test_logger.py`,
`implementation.md`). Independent hand-trace of the `Export.lua` detector's frame-by-frame
behaviour (no automated coverage exists for that file). Independent mutation test of the
`logger.py` gating fix. All four subprojects' mechanical checks (`ruff format --check`, `ruff
check`, `mypy --strict`, `pytest`) run fresh rather than taken on faith from `implementation.md`.

---

## Review (exponent-float fix)

Scope: the one-off fix described in `implementation.md`'s "Exponent-float fix" section
(`5a8a4672..1277c9df`), landed after the Stage 1-3 batch's own Security/Performance/Reviewer
passes (`a7ff14d3` perf, `fcbce9f2` security, `5a8a4672` re-review) had already approved and
proceeded toward DoD. Diff is exactly the six files `implementation.md` claims: `Export.lua`,
`command_sender.py`, `server.py` (one-line version bump), the new
`tests/test_exponent_float_fix.py`, `implementation.md` itself, and the rewritten
`.claude/agent-memory/security/project_export_lua_json_extractor_cannot_yield_nonfinite.md`.

### The bug, confirmed

`CommandSender.send_sight_target`/`send_cockpit_switch` built their UDP datagram with
`json.dumps`, which emits exponent notation for `|value| < 1e-4`
(`json.dumps({"x": 1e-05})` -> `'{"x": 1e-05}'`). `Export.lua`'s old
`extract_json_number_field` pattern (`"field"%s*:%s*(-?%d+%.?%d*)`) has no `e`/`E` in its
character class, so it did not reject that text -- Lua patterns aren't anchored at the end -- it
matched the *leading* digits only and stopped: `"1e-05"` -> captured `"1"` -> `tonumber("1")` ->
`1`, a finite, in-range-looking, completely wrong number (a ~60 deg sight command from a
near-zero intent). No `nil`/NaN/huge check downstream could ever see this, because `1` is none of
those. The corrected agent-memory file states this accurately, including the generalizable lesson
("a parser can't produce X" is a claim about its full accepted grammar, not about inputs anyone
tried) -- no discrepancy between the memory file and what the diff actually does.

### New extractor pattern -- traced and independently executed

`[eE]?[%-%+]?%d*` appended to the old pattern. Traced by hand and then verified by actually
running the live function (extracted into a standalone script, not a copy) against `luajit`
(5.1-semantics-compatible for `string.match`/`tonumber`/`math.huge` -- this function has no
DCS-API dependency, so interpreter choice doesn't matter here) for every case the task asked to
think through, plus a few the test suite doesn't cover:

| input | result | correct? |
|---|---|---|
| `1e-05` | `1e-05` | yes (the bug case) |
| `-3.3e-07` | `-3.3e-07` | yes |
| `1E+3` | `1000` | yes (uppercase E) |
| `0.25` / `-0.5` | `0.25` / `-0.5` | yes, unaffected by the added optional group |
| `-0` | `-0` | yes (Lua has no separate int/float subtype; stays finite) |
| `1e999` | `nil` | yes -- overflows to `math.huge`, rejected by the new finite check |
| `1e` (malformed, no exponent digits) | `nil` | yes -- `tonumber("1e")` is itself `nil` in Lua, caught by the existing `value == nil` branch |
| value immediately followed by `,` or `}` | unaffected | yes -- confirmed with `1e-05` both mid-object and at the end; Lua pattern matching isn't end-anchored, so the trailing delimiter was never part of the risk |

All eight matched the expected finite/non-finite/malformed outcome. `test_exponent_float_fix.py`
covers four of these end-to-end through a real interpreter (`1e-05`, `-3.3e-07`, `0.25`, `-0.5`,
`1e999`) plus the Python-side never-emits-exponent half; it does not cover `1E+3` (uppercase) or
the bare malformed `1e` case. Both pass by my own run above, so this is a coverage gap, not a
defect -- noted as optional below.

### Range check, non-finite rejection, cockpit_switch unaffected

- `SIGHT_TARGET_CMD_BOUND = 1.5` added and correctly mirrors `api.server`'s
  `_SIGHT_TARGET_CMD_BOUND` (grepped both files, same value, same comment cross-reference).
  Without it, a finite-but-huge exponent value (`"1e10"`) would now pass the extractor's new
  finite check and reach `handle_sight_target_command` as a nonsense command -- the fix adds this
  specifically because accepting exponents reopened that door.
- `handle_cockpit_switch_command`'s own pre-existing `value ~= value or value == math.huge or
  value == -math.huge` re-check is untouched and now genuinely redundant (the extractor already
  guarantees finite) rather than falsely redundant as the pre-fix memory claimed -- correctly left
  in place rather than removed, since removing genuinely-redundant defense-in-depth for a LAN
  write surface would be the wrong kind of cleanup here.
- `cockpit_switch`'s `device`/`cmd` fields are unaffected: `command_sender.py` splices them as
  plain Python ints directly into the hand-built JSON string, never through `_format_fixed_point`
  or `json.dumps`, so their wire representation is unchanged by this fix.

### `_format_fixed_point` -- no exponent, adequate precision, existing values unaffected

Traced `_format_fixed_point` against the pre-fix `json.dumps` behaviour for ordinary
already-working values (`0.5`, `-1.0`, `3.0`, `0.0`, `-0.0`) -- all produce the identical
fixed-point string either way, so no behavioural change for any value `cockpit_switch`/
`sight_target` callers were already sending correctly. `-0.0` renders as `"-0.0"` (valid JSON, not
`"-0."`), matching the docstring's stated reason for the trim-then-restore-one-digit logic. Ints
stay ints: `device`/`cmd` are never routed through this helper (see above).

One edge case worth naming, not blocking: at 9 decimal places, a magnitude below ~`5e-10` renders
as `"0.0"`/`"-0.0"` -- a second, much smaller truncation than the one this fix removes. For
`sight_target` (bounded +/-1.5, body-layer arithmetic near sight centre producing values down to
`~1e-4`) this is immaterial. For `cockpit_switch`'s "any value for any switch" channel (BL-B66,
no bound by design) it's a real precision ceiling if a future caller ever needs sub-nanometer-
scale switch values -- vanishingly unlikely for a clickable-action argument, so optional rather
than required.

### Version bump and test extraction method

`EXPORT_SCRIPT_VERSION` (`"2026-10-22b"`) matches `collector.server.EXPECTED_EXPORT_VERSION`
exactly (grepped both). `test_exponent_float_fix.py`'s `_extract_lua_function` slices the function
by balanced `function`/`if`/`end` counting straight out of the live `dcs-export/Export.lua` file
on disk -- confirmed by reading the extraction code, not just the docstring's claim -- so this is
the real, currently-deployed function under test, not a hand-copied duplicate that could silently
drift from it.

### Mutation check -- not run by me, taken on the implementer's own account

`implementation.md` states the implementer reverted the extractor to the old digits-only pattern,
confirmed the new test class failed exactly as predicted (`"1e-05"` -> `1`, `"1e999"` -> `1`
instead of `nil`), then restored the fix and verified an exact `shasum` match. I attempted to
repeat this independently and the harness's auto-mode classifier refused the revert as "security
test removal" (reverting a security-relevant parser, even temporarily, inside the diff under
review). I did not work around this. In its place I ran the extractor's live source directly
against `luajit` for the eight cases in the table above (a forward confirmation of current
behaviour, not a reversion) and separately hand-traced why the old pattern must fail those same
cases (no `e`/`E`/exponent-sign/second-digit-run in its character class, so the match necessarily
stops at the first non-digit, non-`.` character it meets). Both lines of evidence agree with the
implementer's account; I did not independently reproduce the counterfactual run and am saying so
rather than presenting the implementer's account as my own finding.

### Checks (run independently)

aircraft-layer: `ruff format --check` (pass, 72 files), `ruff check` (all checks passed),
`cd aircraft-layer && .venv/bin/mypy src` (pass, 26 source files), `pytest aircraft-layer/tests -q`
(469 passed, up from the prior batch's 459 -- the 10 new tests), `test_exponent_float_fix.py` and
`test_dcs_export_lua_local_order.py` run by name (both pass; `luajit` was on `PATH` so the
Lua-interpreter-dependent test class actually ran rather than skipping). body-layer untouched by
this diff (confirmed via the file list above), so not re-run.

### Required Fixes

None.

### Optional Refinements

- Add `1E+3` (uppercase exponent) and a bare malformed `1e` case to
  `test_exponent_float_fix.py`'s Lua-side test class -- both pass today (confirmed above by
  independent execution) but aren't in the automated suite, so a future regression on either
  wouldn't be caught mechanically.
- Note the ~`5e-10` precision ceiling in `_format_fixed_point`'s docstring for the benefit of a
  future `cockpit_switch` caller on the unbounded channel, even though no current caller is
  affected.

### Process note, not a required fix

This fix touches the inbound command parser on a LAN-reachable (loopback-bound, but a write
surface nonetheless) path, and landed **after** the Stage 1-3 batch's own Security deep analysis
(`fcbce9f2`) had already run and approved. Per `AGENTS.md`'s role sequencing ("Bug fix: Debugger
-> Reviewer -> Security (deep analysis) -> DoD" and "A change request ... re-enters the loop"),
this diff has not yet had its own Security pass -- `security-review.md`'s existing content
predates it and still states the old, now-superseded "digits-only, cannot match non-finite"
characterization of the extractor (correct as a description of the pre-fix code at the time it
was written, not a staleness defect in that document, but not evidence this new diff has been
security-reviewed either). Recommend one short Security pass on this diff specifically before
DoD, consistent with how the rest of the batch was gated -- this fix is small and self-contained
enough that it should be quick.

### Verdict

APPROVED WITH MINOR FIXES

The fix is correct, complete, and matches `implementation.md`'s own account in every detail I
could independently check (extractor pattern, range check, sender formatting, version bump, test
extraction method). No required fixes. Two optional test/documentation refinements. One process
item: a Security deep-analysis pass on this specific diff has not yet happened and should run
before DoD, per the standard bug-fix role sequence -- not a defect in the fix itself.

### Review Confidence

Full read of every changed file (`Export.lua`'s two changed functions in full,
`command_sender.py`'s `_format_fixed_point` and both callers in full, `server.py`'s one-line
version bump, `test_exponent_float_fix.py` in full, the rewritten agent-memory file,
`implementation.md`'s "Exponent-float fix" section). Independently executed the live extractor
against `luajit` for eight hand-chosen edge cases beyond the test suite's own four. Mechanical
checks (`ruff format --check`, `ruff check`, `mypy --strict`, `pytest`) run fresh. The one gap:
the implementer's digits-only-pattern counterfactual run was not independently repeated (harness
refused the revert as a security-test-removal action) -- taken on the implementer's documented
account plus my own independent forward-direction confirmation and hand-trace, not re-verified by
mutation myself.
