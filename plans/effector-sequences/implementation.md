### Implementation Summary

Fix pass on `feature/switch-reference-values`, closing the real-Windows-run findings
(arithmetic parameters, NULL class slots, silent unknowns, float noise, `radio_wheel_1`'s real
shape) plus the Reviewer's two required fixes and all three optional refinements
(`plans/effector-sequences/review-switch-values.md`).

### Files Changed

- `body-layer/tools/generate_effector_registry.py` —
  - Added a safe constant-arithmetic evaluator (`_eval_constant_arithmetic`/`_lua_arithmetic`),
    an `ast.parse(mode="eval")` whitelist walk over numeric literals, unary minus, and
    `+ - * /` only — never `eval`. Wired into `_lua_scalar`, so `multiposition_switch`'s
    `delta_` and `default_axis`/`default_axis_limited`'s `gain_` now resolve expressions like
    `1/9`, `-2/3`, `0.2 * 5 / 6` instead of falling to `_UNRESOLVED`/`"unknown"`.
  - Added `ValueKind.NONE = "none"` and `_none_value()` for a raw-literal NULL-class
    (`class_type.NULL`, bare `0`) action — a placeholder with no settable value, not a parser
    failure. `_value_ranges_for_raw_literal` now special-cases `kind == "NULL"` before the
    generic `unhandled raw-literal class` fallback.
  - `radio_wheel_1` is now emitted as a discrete, step-size-derived range with a new
    `ValueRange.relative` field set, not `_continuous` — it is TUMB/relative per the research
    note, not a continuous axis.
  - Added `_round_value`/`_VALUE_ROUND_NDIGITS` (6 decimal places) and applied it in `_discrete`
    (every value) and `_continuous` (`min`/`max`/`gain`) — fixes the `0.30000000000000004`-style
    float noise at the point values are computed, once, rather than re-emitting it from every
    downstream reader forever.
  - **Required fix**: `default_1_position_tumb`'s default `arg_lim_` fallback is now
    `(0.0, arg_val_ if arg_val_ is not None else 1.0)`, not the shared `(0.0, 1.0)` the other two
    helpers in its group use — reads `arg_val_` (one offset before `arg_lim_`) when `arg_lim_`
    itself is absent, per the research note's documented default (row 36).
  - Added `_toml_value_range` support for `kind == "none"` (no extra fields) and
    `relative = true` on a discrete entry; added a run-report/header accounting of value-range
    unknowns (`_unknown_value_ranges`, printed per-element-per-action plus a count in both the
    stdout summary line and the TOML header's `# Elements:` comment) — previously silent: an
    element could be fully "handled" while its value range was `"unknown"`, discoverable only by
    grepping the rendered TOML by hand.
  - Pruned/amended the module's own "value ranges" section comment and the
    `_Unresolved`/`_lua_scalar` docstring comments to describe arithmetic resolution instead of
    claiming every such expression is unresolved (comment was standing next to code I changed).
- `body-layer/tools/render_switch_reference.py` — `_format_value_range`: `"to"` replaces `"-"`
  as the discrete-step-count and continuous range separator (optional fix — a negative lower
  bound like `-1-1 continuous` read ambiguously); added `relative`/`"none"` (→ `—`) rendering;
  fixed the stale `config/effectors-raw.toml` path in the rendered header to
  `config/effectors-raw/mi-24p.toml` (optional fix); updated the Values-column legend to
  document `relative` and `—`.
- `body-layer/src/belief/effector_sequences.py` — reworded `TRIGGER_INFO[TAKEOFF]`'s
  description: the skip on an already-satisfied repeat is the *engine's* implicit self-check
  (a row does not write if its switch already reads the target value), not "a sequence file's
  own row conditions" — that sentence named the wrong mechanism.
- `aircraft-layer/research/2026-10-23-mi24p-clickable-value-ranges.md` — corrected the
  `multiposition_switch` Helpers-table row's wrong "every real call uses d = 0.1" claim (several
  real calls use fractional deltas), and appended a dated "Amendment, first real Windows run"
  section recording the three findings above with their verified element names.
- `plans/effector-sequences/implementation.md` — trimmed the stray orphaned line at the end
  (optional fix).
- `body-layer/config/sequences/mi-24p/switch-reference.md`, `body-layer/config/sequences/triggers.md`
  — regenerated (`--write`) against the current (still pre-Windows-rerun) committed
  `config/effectors-raw/mi-24p.toml` and the `TRIGGER_INFO` wording fix. The render mechanism
  works correctly with the new separator/relative/none formatting; the *values* in the real dump
  (the float-noise examples, `radio_wheel_1`'s continuous shape, the NULL-class "unhandled"
  reason text) will only change once the generator is rerun on the Windows DCS machine — see
  "Notable Discoveries" below for exactly which rows are still stale and why.
- `body-layer/tests/test_generate_effector_registry.py` — see "Tests Added".
- `body-layer/tests/test_render_switch_reference_values.py` — updated `test_long_discrete_list_
  is_shown_as_a_step_count`, `test_continuous_with_gain`, `test_continuous_without_gain`, and
  `test_values_cell_multi_action_is_labelled_per_action` to the new `"to"` separator (deliberate
  behaviour change per the task, not a scope-creep edit); added `test_relative_discrete_list_
  is_marked` and `test_none_kind_renders_as_an_em_dash`.

### Tests Added

- `test_multiposition_switch_fractional_delta_is_evaluated` / `test_multiposition_switch_
  unresolvable_delta_expression_is_unknown` — arithmetic `delta_` resolves; a real identifier
  (`anim_speed_default / 5`) still does not.
- `test_default_axis_arithmetic_gain_is_evaluated_and_rounded` / `test_default_axis_
  unresolvable_gain_identifier_is_unknown` — same pair for `default_axis`'s `gain_`, plus the
  rounding is checked directly (`vr.gain == round(vr.gain, 6)`).
- `test_default_1_position_tumb_default_arg_lim_is_0_to_1` / `..._uses_custom_arg_val` /
  `..._unresolvable_arg_val_is_unknown` — the Required Fix: no-`arg_val_` default stays `(0,1)`,
  a custom `arg_val_` with no `arg_lim_` changes the upper bound to it, an unresolvable `arg_val_`
  is unknown rather than silently falling back.
- `test_radio_wheel_1_is_relative_discrete_not_continuous` / `..._default_step_and_limit` —
  `radio_wheel_1`'s new discrete/stepped/`relative` shape, both with an explicit step/limit and
  with everything defaulted.
- `test_raw_table_literal_null_class_action_is_none_not_unknown` (renamed/rewritten from
  `..._is_unknown`) — NULL class now renders `"none"`, not `"unknown"`.
- `test_value_range_for_every_helper_signature_minimal_call` — the Required Fix for the
  mutation-coverage gap: one table-driven test iterating every one of the 22
  `_HELPER_SIGNATURES` entries with a minimal (all-nil) call, asserting the expected
  `ValueRange` shape transcribed independently from the research note. Verified by mutation:
  removing `"default_blue_cover"` from its group now fails this test (confirmed live, restored
  by checksum — see below); previously it left the whole suite green exactly as the review
  described.
- `test_relative_discrete_list_is_marked`, `test_none_kind_renders_as_an_em_dash` (render test
  file) — the new Values-column markers.

### Checks

(body-layer only — the only subproject touched)

- `ruff format --check src tests tools`: pass (one file needed `ruff format` after adding the
  new table-driven test — applied, then re-checked clean)
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (74 files)
- `cd body-layer && .venv/bin/mypy tools`: pass (10 files)
- `pytest -q`: pass — 2596 passed, 4 xfailed

### Mutation verification performed (counterfactuals actually run, not theorised)

1. Removed `"default_blue_cover"` from its `_value_range_for_helper` group → the new
   `test_value_range_for_every_helper_signature_minimal_call` failed with exactly the
   `discrete` → `unknown` downgrade the review predicted. Restored; `shasum` of the file
   matched its pre-mutation value exactly.
2. Disabled the `default_1_position_tumb` special-case branch (`elif helper ==
   "default_1_position_tumb"` → `elif False`) → both of that helper's new custom-`arg_val_`
   tests failed as expected (`discrete` with the wrong upper bound / not falling to `unknown`
   for an unresolvable `arg_val_`). Restored; `shasum` matched.

### Notable Discoveries

- **The committed `config/effectors-raw/mi-24p.toml` cannot be hand-edited** (project rule) —
  so every "unknown"/float-noise/continuous-`radio_wheel_1` row the task asked me to list is
  still exactly what it was before this pass, because the dump itself was generated by the old
  code. The rows that will change on the next Windows rerun: every `multiposition_switch`/
  `default_axis`/`default_axis_limited` element whose `helper_args` contains a `/` or `*`
  (currently rendered `unknown: ...delta_/gain_ is not a literal number` — ~25 elements, grep
  `helper_args.*[/*]` in the raw dump for the exact list), the five `radio_wheel_1` JADRO-1I
  elements (currently rendered `continuous (gain 0.1)`, will become `0 to 1 (11 steps)
  relative`), and `ILS-ADJUST-HANDLE-PTR`/`BRAKE-LEVEL-OP-PTR`'s NULL-class actions (currently
  `unknown: unhandled raw-literal class 'NULL'`, will become `—`). The render mechanism itself
  (separator, `relative`, `none`) is verified correct against synthetic fixtures and the unit
  tests, independent of the stale dump.
- `default_1_position_tumb` is confirmed never called in the real module (per the research
  note), so the Required Fix, while now covered and correct, is still dormant in the committed
  dump exactly as the review described — the regenerated dump after the Windows rerun will not
  exercise it either, since no real call overrides `arg_val_` without `arg_lim_`. The fix guards
  against a future DCS patch that does, and against the generator's own documented rule
  ("never guessed") silently drifting from the helper's real default.
- `multiposition_switch`'s real `delta_` values are now confirmed to span at least
  `1/9, 1/10, 1/17, 1/20, 1/3, 1/5, 1/6, 0.1, 0.115` across the real dump's `helper_args` — the
  research note's "every real call uses d = 0.1" was wrong for roughly half the calls that pass
  a `delta_` at all (counted by grepping `helper_args` entries containing a `/` against the ones
  that don't, in the committed real dump — not a guess).

---

## Mission-start triggers (2026-10-23, follow-on)

Adds the two triggers from `explore-notes.md`'s "Two new triggers: mission start"
(user, verbatim): *"Add trigger for mission-start that fires once at every mission start and
separate for mission-start-in-air that fires once at mission start only if airborne (AGL >
10 m)"*. Plan R14 (added this pass) and `body-layer/CLAUDE.md`'s BL-B90 entry record the
design; no sequence file ships for either trigger (the user writes those).

### Files Changed

- `body-layer/src/belief/effector_sequences.py` — two new `EffectorTrigger` members
  (`MISSION_START`, `MISSION_START_IN_AIR`), both `cardinality="once"`, with `TRIGGER_INFO`
  entries. Pruned the `cardinality` field's docstring claim that "no shipped trigger is `once`
  yet" (now false).
- `body-layer/config/sequences/triggers.md` — regenerated (`tools/render_triggers.py --write`).
- `body-layer/src/logger.py`:
  - `ConsolePerceptionRunner` gains three fields: `pending_mission_start_fire`,
    `pending_mission_start_in_air_check` (both `bool`, default `False`), and
    `mission_start_fresh_sample_baseline_t_sim` (`float | None`). All three reset to their
    declared defaults on `reset_for_new_mission`'s re-run `__init__`, same as every other
    per-mission field.
  - `_check_for_new_mission` captures `runner.last_t_sim` *before* calling
    `_reset_mission_state` (which wipes it to `None`) and, on a genuine reset, arms all three
    fields explicitly afterward — same pattern `last_mission_start_sequence` already uses.
    Cannot fire the triggers itself: it runs before `runner.run_once()` each poll and has no
    ownship sample to decide freshness or airborne-ness from.
  - `_run_crew_text_poll_loop`'s poll block (where `was_on_ground`/`TAKEOFF` already lived):
    a `mission_start_resolving` check runs before the takeoff-edge check, now in an `elif`.
    While either pending flag is set, the block waits for the first ownship sample whose
    `t_sim` *differs* (`!=`, not `<`) from `mission_start_fresh_sample_baseline_t_sim`, then
    fires `MISSION_START` (if still pending) and, from that same sample, `MISSION_START_IN_AIR`
    only if not `crew_console.on_ground`. `TAKEOFF` is suppressed for every poll this
    resolution is still pending, including the one that resolves it.

### Why `!=` rather than `<` against the baseline

Considered and rejected: comparing the candidate sample's `t_sim` as strictly less than the
pre-reset baseline (reasoning "a fresh mission's model clock restarts near zero"). Rejected
because a restart moments into a short previous mission can have a *small* baseline that the
new mission's own early samples pass straight through — a strict-decrease check can then wait
for the rest of the mission and never resolve. `!=` only requires detecting *any* change from
the exact stale value the collector was caching, which holds regardless of which direction the
clock moved, and converges in at most one real `Export.lua` sample.

### Tests Added (`body-layer/tests/test_logger.py`, driving the real poll loop)

All six use a synthetic one-row sequence each for the two new triggers (`MISSION_START`
writes `observ`, `MISSION_START_IN_AIR` writes `weapon_safety`) — deliberately *not* any of
`takeoff`'s own four switches, so a write is unambiguous even against a takeoff firing for an
unrelated, pre-existing reason. Every test settles on the ground first, because a process's
very first ownship sample being airborne is itself a takeoff edge under `on_ground`'s `True`
default (a pre-existing mechanism, exercised deliberately by
`test_second_takeoff_in_the_same_mission_does_not_rerun_the_power_up` already) — settling
grounded keeps that mechanism out of these tests entirely.

- `test_ground_mission_start_fires_mission_start_only` — ground restart fires `MISSION_START`
  only.
- `test_air_mission_start_fires_both_mission_start_triggers_not_takeoff` — air restart fires
  both, `TAKEOFF` never fires despite the textbook `on_ground: True -> False` shape.
- `test_air_start_then_land_then_takeoff_fires_takeoff_once` — after the air-start resolves,
  a real landing then takeoff still fires `TAKEOFF` exactly once.
- `test_body_layer_start_mid_mission_fires_neither_mission_start_trigger` — a process
  attaching to an already-running mission (rule 4) fires neither.
- `test_second_mission_restart_fires_both_triggers_again` — a second restart in the same
  process fires both again, no latch surviving the first.
- `test_stale_telemetry_at_mission_restart_does_not_decide_airborne` — a real takeoff
  establishes a genuinely airborne "old mission" state; the restart is detected but the
  telemetry object is left unchanged for several polls (the exact stale-cache shape); neither
  new trigger fires and `TAKEOFF` does not fire a second time during that window; only once a
  sample with a different `t_sim` (grounded) arrives does `MISSION_START` fire.

**Test-impact check (plan step 1b).** Grepped `tests/` for every existing test referencing
`mission_start`/`mission-start`/`EffectorTrigger` before writing new ones. Found one mismatch
the plan's own text did not anticipate: `tests/test_effector_sequences.py::
test_unknown_trigger_drops_the_file` constructed its "genuinely unknown trigger" fixture by
substring-replacing `takeoff` → `mission-start` — which this change turns into a *known*
trigger, silently defeating the test's own premise (it would have kept passing, having
stopped testing what its name says, since an unknown trigger and a known one with an empty
rows tuple both parse without raising — the only reason it failed loudly instead is that it
also asserts `sequences == {}`, which a newly-valid `mission-start` entry violates). Fixed by
switching the substituted string to `bogus-trigger`, which `EffectorTrigger` will never know.

### Mutation verification performed

Set `mission_start_resolving = False` unconditionally in `logger.py` (deleting the real
pending-flag check) and re-ran the six new tests: 5 of 6 failed red, each for the stated
reason (`TAKEOFF` wrongly firing on an air/stale sample, or `MISSION_START_IN_AIR` wrongly
firing from a stale sample). The sixth
(`test_body_layer_start_mid_mission_fires_neither_mission_start_trigger`) stayed green
correctly — that scenario never sets the pending flags at all (rule 4), so the mutation is a
no-op on that path, not evidence of a gap. Restored by re-applying the exact original text;
confirmed via a full mypy/ruff/pytest re-run afterward rather than by eye.

### Checks

(body-layer only — the only subproject touched)

- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (74 files)
- `cd body-layer && .venv/bin/mypy tools`: pass (10 files)
- `pytest -q`: pass — 2602 passed, 4 xfailed

### Notable Discoveries

- The pre-existing "airborne first sample looks like a takeoff" behaviour
  (`on_ground` defaulting `True`) is now a documented, deliberate exception for the
  body-layer-attaches-mid-mission case (rule 4) specifically — it is *not* suppressed there,
  only for a genuinely detected mission (re)start. Worth flagging because the two cases produce
  the same wire-level symptom (an airborne first sample) but now diverge in behaviour depending
  on whether a mission-start event accompanies it.
- `mission_start_fresh_sample_baseline_t_sim`'s `!=` comparison relies on DCS's own telemetry
  cache serving a bit-identical `t_sim` float across polls until a genuinely new sample lands —
  true by construction (`TelemetryCache` serves the same cached object), but worth restating if
  a future change ever makes the aircraft-layer synthesize or round `t_sim` on each read.

---

## Review fixes (2026-10-23, follow-on): stale air-start docs + baseline-collision fallback

Applies `plans/effector-sequences/review-mission-start.md`'s required fix (three stale "warm air
start re-fires takeoff" claims, plus two more found by the review's own instruction to grep
further) and its optional baseline-collision refinement, on top of the reviewed tip `b61bf3e6`.

### Files Changed

- `body-layer/src/belief/effector_sequences.py` — `TRIGGER_INFO[EffectorTrigger.TAKEOFF]
  .description` no longer claims a warm air start re-fires `takeoff`; states instead that
  `takeoff` fires only on a real observed ground->air transition and that an air start fires
  `MISSION_START`/`MISSION_START_IN_AIR` instead.
- `body-layer/config/sequences/triggers.md` — regenerated (`tools/render_triggers.py --write`)
  from the corrected description above. Checked the **rendered** text, not just the source
  comment, per the review's own instruction.
- `body-layer/config/sequences/mi-24p/copilot-takeoff.md` — header comment no longer says a
  "hot/air start" finishes the power-up on its own; splits the claim (hot start still reaches
  this file via the implicit self-check; an air start never reaches this file at all) and adds a
  one-line pointer to the mission-start triggers that fire instead.
- `body-layer/src/logger.py` — three changes:
  1. The `elif was_on_ground and not crew_console.on_ground:` TAKEOFF comment (the review's
     grep-for-more instruction caught this one, not in the three-item list) no longer claims a
     warm air start reaches this branch and is made a no-op there — it never reaches this `elif`
     at all, suppressed for the whole `mission_start_resolving` window.
  2. New tunable `MISSION_START_RESOLVE_FALLBACK_S` (`tuning.real`, default 30.0, bounds
     5.0–120.0, status `judgement`) — the baseline-collision fix, below.
  3. New `ConsolePerceptionRunner` field `mission_start_resolving_since_wall: float | None`,
     set by `_check_for_new_mission` to `time.monotonic()` the same poll the pending flags are
     armed, cleared back to `None` once the resolving window actually resolves. Reset to its
     default via the same `reset_for_new_mission` re-`__init__` pattern every other per-mission
     field uses — no special-casing needed.
- `plans/effector-sequences/plan.md` — two more stale "air start" mentions found by the grep
  instruction, both pre-dating R14 and left behind when it was added: the Stage 1–2 "Takeoff, as
  it ships" example (said a warm air start skips every takeoff row; an air start never reaches
  that file at all now) and a "Risks & Unknowns" bullet claiming an airborne first sample is a
  takeoff edge that powers a cold unit (superseded in place, with the "Was"/"Now" framing the
  rest of the plan's revision table already uses, rather than deleted — the new gap it names,
  that neither new trigger ships a sequence file yet, is worth a future reader having).
- `body-layer/tests/test_logger.py` — one new test (below) plus the matching import.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) for the
  new tunable.

**Not touched, deliberately:** the acceptance card the review mentions (`block 4`) is a published
Artifact, not a repository file — nothing to grep or fix here. `belief/effector_engine.py` has no
"air start" mention at all (checked). `test_effector_engine.py`'s own "warm air start" docstring
(`test_air_start_with_switches_already_on_writes_nothing`) is about the engine's own mechanics —
it fires `EffectorTrigger.TAKEOFF` directly and asserts the implicit self-check, which is still
true at that layer regardless of whether `logger.py` would ever reach it on a real air start —
left alone. Several `plans/effector-sequences/*.md` "warm air start" mentions outside `plan.md`
(review-stage0/1/2, dod-check-stage0, the revision-history table's own R5 row, the "Superseded"
section's D3/R5 rationale) are dated historical records of an earlier design point, not assertions
about current behaviour presented as fact — left as the record `docs/PROCESS.md`'s "supersede,
don't delete" convention asks for.

### The baseline-collision fix: why wall-clock, not a poll count

The coordinator relayed a DCS fact from the user mid-task: *"Mission restart always resets the
mission elapsed timer in DCS."* That is the reason the `!=` check (already shipped, unchanged by
this fix) is sound in the first place — a real restart's fresh samples almost always differ from
the pre-reset baseline immediately, since DCS's own model clock restarts near zero. The collision
this fix guards against needs two things at once: the restart happens near `t_sim = 0`, **and**
the very first fresh sample lands on the exact same float as the baseline. Both together is rare
enough to self-heal on the next restart, which is why the review marked this optional.

The original plan (stated in the review and the task) was a plain poll-count fallback. Building it
surfaced a real conflict with an existing, already-passing test:
`test_stale_telemetry_at_mission_restart_does_not_decide_airborne` deliberately holds the
resolving window open across roughly twenty polls at its fast (0.01s) test poll interval, to prove
the code does *not* resolve prematurely from a stale cached sample. A poll-count threshold small
enough to self-heal promptly at the real 1.0s default poll interval (e.g. 5) would misfire inside
that test; a threshold large enough to survive that test's poll count would be too large to
self-heal promptly in real flight. Wall-clock elapsed time has neither problem: it is independent
of `--poll-interval-s`, so the fast test stays fast and safe while production self-heals promptly.
Declared as `MISSION_START_RESOLVE_FALLBACK_S` (seconds), default 30.0 — comfortably above any
plausible `Export.lua` resume latency and the fast tests' sub-second windows, comfortably below
"wait for the whole sortie."

### Tests Added

- `test_baseline_collision_resolves_via_bounded_fallback` — reproduces the collision by never
  changing the telemetry dict's `dcs_model_time_s` across a mission restart (the baseline and
  every "fresh" sample thereafter carry the identical `t_sim`), confirms the pending flags stay
  armed and no write lands across ten polls (proving the `!=` check alone cannot resolve this),
  then jumps `mission_start_resolving_since_wall` back past `MISSION_START_RESOLVE_FALLBACK_S`
  (so the test does not sleep 30 real seconds) and confirms `MISSION_START` fires and both pending
  flags clear. **Verified failing on the pre-fix code**: stashed `src/logger.py` back to the
  reviewed tip, re-ran the test — `ImportError: cannot import name
  'MISSION_START_RESOLVE_FALLBACK_S' from 'logger'` (the mechanism does not exist there), i.e. red
  for the stated reason. Restored the fix via `git stash apply`/`drop`, confirmed by `shasum`
  before and after rather than by eye.

### Checks

(body-layer only — the only subproject touched)

- `ruff format --check src tests tools`: pass (one auto-fix needed first — an import-order
  violation from the new `import tuning`, fixed with `ruff check --fix`, then both checks pass
  clean)
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, no issues, 74 source files
- `cd body-layer && .venv/bin/mypy tools`: pass, no issues, 10 source files
- `pytest -q`: pass — 2603 passed, 4 xfailed (one more passed than the review's reported 2602,
  the new collision test)

### Out of scope, per the task

The pre-existing look-command gating note (the review's second optional refinement: `crew_console.
on_ground` is reassigned unconditionally from the current sample every poll, stale or fresh,
regardless of `mission_start_resolving`, so a look command during the stale-cache window is gated
on the previous mission's last known altitude rather than the safe `True` default `reset_for_new_
mission` just set) is left alone, per the task's explicit instruction — not a regression, not
touched by this diff, flagged by the review as pre-existing and out of scope for this cut.

### Notable Discoveries

- The review's "grep for other 'air start' mentions" instruction found two real stale spots the
  three-item required-fix list missed: the `TAKEOFF` `elif`'s own comment in `logger.py`, and two
  spots in `plan.md` (an example block and a Risks & Unknowns bullet) both predating R14. Neither
  would have been caught by the staleness tests the review already named
  (`test_switch_reference_matches_the_generator`/`test_render_triggers.py` only check that a
  render matches its generator's current input, not that the input itself is current) — same gap
  the review called out for the three it did find.
- The acceptance card the review's "block 4" reference points at is not a repository file (a
  published Artifact from an earlier `/test-card` run) — nothing here to check against it; noted
  rather than silently skipped.

## Fix: fallback no longer classifies airborne from stale data (2026-10-23)

Addresses the "Fix re-review (2026-10-23)" required fix in `review-mission-start.md`: the 30 s
fallback (`MISSION_START_RESOLVE_FALLBACK_S`) could not distinguish the rare `t_sim`-coincidence
case (self-heals) from the ordinary case of no fresh ownship sample arriving at all within the
window (a long load, or a mission that starts paused) — the latter does not self-heal, because
firing `MISSION_START_IN_AIR` on fallback classified it from `crew_console.on_ground`'s still-
stale, previous-mission value and cleared the pending flag regardless.

**Fix, in `src/logger.py`'s poll block**: on fallback expiry, `MISSION_START` still fires
unconditionally — decided here to be a one-shot setup hook that does not depend on air state, so
it need not wait for a fresh sample at all (the task's own stated lean, confirmed rather than
second-guessed). `MISSION_START_IN_AIR` now only fires when `fresh_sample_confirmed` is true —
never on `fallback_due` alone — so a fallback forced purely by "no sample yet" drops the air/ground
check entirely instead of guessing from stale data, logs a warning naming why, and still clears
`pending_mission_start_in_air_check` and `mission_start_resolving_since_wall` so the resolving
window (and the `TAKEOFF` suppression tied to it) ends the same poll either way. No change was
needed to end `TAKEOFF` suppression correctly: the existing `if mission_start_resolving: ... elif
was_on_ground ...` structure already skips the takeoff-edge check for the resolving poll itself
(fallback or not), so `on_ground`'s baseline for the *next* poll is established from whatever
sample is in hand without that poll ever reading as a transition — unchanged by this fix, verified
by the new tests below rather than assumed.

**Comments updated** (per the task's explicit list): `MISSION_START_RESOLVE_FALLBACK_S`'s own
`#:` declaration (first sentence rewritten — the old one asserted the fallback always fires both
triggers, which is now false), the call site's "Bounded fallback" comment, `EffectorTrigger.
MISSION_START_IN_AIR`'s own `#:` comment, and `TRIGGER_INFO[MISSION_START_IN_AIR].description`
(the one that renders into `triggers.md`) — all now state both cases rather than only the
coincidence one. Regenerated `config/sequences/triggers.md` (`tools/render_triggers.py --write`)
and `config/defaults.toml` (`tools/generate_defaults.py --write`) and read both rendered files
rather than trusting the source comment — `defaults.toml`'s new first sentence for `logger.
MISSION_START_RESOLVE_FALLBACK_S` correctly states the fallback fires `MISSION_START` "anyway,
without `MISSION_START_IN_AIR`", matching the code. `copilot-takeoff.md` and the acceptance card
were checked (`grep` for "mission-start-in-air"/"MISSION_START_IN_AIR") and needed no change —
neither asserts the now-corrected guarantee.

### Tests added (`tests/test_logger.py`)

- `test_no_fresh_sample_fallback_fires_mission_start_only_then_real_takeoff` — the real poll loop,
  a stale **airborne** sample left over from a genuine pre-restart takeoff (the one shape the
  existing `test_baseline_collision_resolves_via_bounded_fallback` cannot exercise, since that
  test's telemetry stays grounded throughout and so can't tell "correctly skipped because
  grounded" apart from "wrongly classified from stale data"). Forces the fallback without ever
  supplying a fresh sample: asserts `MISSION_START` fires, `MISSION_START_IN_AIR` does not (even
  though the stale sample reads airborne), the pending-check-dropped warning is observable via
  `caplog`, and the cockpit-switch write list is exactly `[*pre-restart takeoff writes,
  MISSION_START]`.
- `test_takeoff_suppression_ends_cleanly_after_no_fresh_sample_fallback` — companion, isolating
  the two claims the test above doesn't assert on directly: the stale sample left in place
  immediately after the fallback resolves is not itself read as a `TAKEOFF` edge (several more
  polls of the unchanged stale sample produce no new writes), and once a genuinely fresh sample
  lands and the aircraft really leaves the ground, `TAKEOFF` fires — exactly once, counted against
  the pre-restart takeoff's own four writes landing twice in total, never a spurious third.

**Mutation-tested the "don't classify on stale" rule**, not just the new tests' own pass/fail:
reverted the `fresh_sample_confirmed and not crew_console.on_ground` guard back to the pre-fix
`not crew_console.on_ground` (i.e. the exact defect this fix closes), ran
`test_no_fresh_sample_fallback_fires_mission_start_only_then_real_takeoff` alone — failed red for
the stated reason (`MISSION_START_IN_AIR`'s write, `(6, 3020, 1.0)`, appears where the assertion
says it must not). Restored the file from a backup copy and confirmed by `shasum` (not by eye)
that the restored file is byte-identical to the pre-mutation one.

### Which fires on fallback expiry: decided

Per the task's own framing: `MISSION_START` fires on fallback expiry (does not wait for a fresh
sample), `MISSION_START_IN_AIR` does not (drops the check instead of guessing). This matches the
task's stated lean and the code already in place for `MISSION_START` before this fix — only
`MISSION_START_IN_AIR`'s gating needed to change.

### Checks

- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, no issues, 74 source files
- `cd body-layer && .venv/bin/mypy tools`: pass, no issues, 10 source files
- `pytest -q`: pass — 2605 passed, 4 xfailed (two more than the fix re-review's reported 2603 —
  the two new tests above)

---

## Stage 4 — readback by need (2026-10-24)

Implements the revised spec ("Stage 4 — readback by need (spec, revised 2026-10-24 — option B)"),
including the security plan review's required change (reply-value validation shared between the
continuous and one-shot read paths) and the `polled.toml` config loader (S4.4a). Built on top of
Stages 1-3 (unchanged except where this stage's own co-moving-fields edits say otherwise).

### Files Changed

**aircraft-layer** (committed separately, sha `ec02bcf4`; see that commit message for the full
per-file breakdown — repeated here only at the level this log needs):

- `aircraft-layer/src/schema/watched_args.py` (new) — `WatchedArgsState`, `parse_arg_values` (the
  one shared finiteness/type validator both read paths use).
- `aircraft-layer/src/collector/arg_read_broker.py` (new) — `ArgReadBroker`: synchronous at the
  collector, `secrets.token_hex(6)`-minted `read_id`, `MAX_OUTSTANDING_READS = 8`,
  `ARG_READ_TIMEOUT_S = 0.25`.
- `aircraft-layer/src/collector/cache.py` — `WatchedArgsCache` replaces `CockpitSwitchCache`, adds
  `clear()` (called on every `export_version` line).
- `aircraft-layer/src/collector/command_sender.py` — `send_watch_args`, `send_read_args`.
- `aircraft-layer/src/collector/server.py` — `"watch_id"`/`"read_id"` line routing; an old
  `"missl_pw"` line is now dropped at DEBUG (never parsed); `EXPECTED_EXPORT_VERSION` bumped to
  `"2026-10-24"`.
- `aircraft-layer/src/api/server.py` — `GET /watched_args/latest`, `POST /command/watch_args`,
  `POST /query/read_args` (the one synchronous endpoint on this API — blocks the HTTP worker thread
  inside `ArgReadBroker.read`). `POST /command/cockpit_switch` (the write op, BL-B66) is
  **unchanged** — only its readback sibling is removed.
- `aircraft-layer/dcs-export/Export.lua` — `push_cockpit_switch_state` and the switch-specific
  `ARG_MISSL_PW`/`ARG_CPLR_DISTR`/`ARG_SIGHT_PW`/`ARG_SCHO_PW`/`ARG_WEAP_SAFE`/`ARG_READY_LAMP`/
  `ARG_LAUNCH_PERM_LAMP` constants removed (`ARG_OBSERVE`/`ARG_ALIGN_LAMP` kept — still read
  per-frame by `run_sight_servo`/`push_slew_trace`); added `parse_arg_list` (shared by both new
  ops), `admit_read`, `watched_args_changed`, `encode_watched_args_line`,
  `build_read_reply_line`, `handle_watch_args_command`, `handle_read_args_command`,
  `push_watched_args_state` (called after the telemetry send succeeds, inside the existing export
  throttle); `poll_command_socket` dispatches `watch_args`/`read_args`, the latter capped at
  `MAX_READS_PER_FRAME = 4`; `EXPORT_SCRIPT_VERSION` bumped to `"2026-10-24"`.
- `aircraft-layer/CLAUDE.md` — the `cockpit_switch` readback paragraph replaced; the `src/api/`
  structure bullet gains the two new routes.
- `aircraft-layer/ROADMAP/AC-B11.md` — names the two new POST handlers in its unbounded-
  `Content-Length`-read list.

**body-layer**:

- `src/belief/effector_registry.py` — `EffectorDef` gains `shape: str` (copied from the raw dump's
  element) and the derived `absolute_write` property (`True` only for `default_2_position_tumb`,
  `_ABSOLUTE_WRITE_SHAPES`, widened one shape at a time with its own research note).
  `RegistryError.scope` gains `"polled-file"`. `PolledSet` + `load_polled_config` (new) — S4.4a's
  loader: required args (`sight_effector.REQUIRED_POLLED_ARGS`) union `polled.toml`, required
  first then config file order; a bad entry is a D5 error (scope `"polled-file"`/`"entry"`), an
  omitted-required-arg is a warning only (never `config_error_pending`); the 64-arg cap drops
  config entries from the end, never a required one.
- `src/belief/sight_effector.py` — `REQUIRED_POLLED_ARGS = {886: "home_phase", 898:
  "SightHead.mode", 960: "sight_ready"}`. `refresh_readback` rewritten: takes the continuous feed's
  raw `"args"` map (string-keyed) instead of the old named-boolean `cockpit_switch_latest` dict,
  applies the `>= 0.5` threshold itself (moved from `Export.lua`), and no longer touches
  `weapon_safety_observed`/`launch_perm_observed` (673/962 have no reader as of this stage — carried
  for `BL-B67`).
- `src/belief/effector_sequences.py` — `SequenceFile` gains `read_args: frozenset[int]` (every
  switch row's effector arg, union every explicit condition's effector arg), computed at load time
  by `_compute_read_args`; a file whose set exceeds 64 args is a new D5 file error.
- `src/belief/effector_engine.py` — the per-row waiting loops are gone. `_RunCursor` gains
  `snapshot`/`snapshot_sim`/`read_first_attempt_sim`, loses `condition_waiting_since_sim`/
  `self_waiting_since_sim`. `EffectorRunState` gains `assumed_writes: Mapping[int, tuple[float,
  float]]` (every successful write, visible engine-wide, `>=` not `>` against a reading cursor's
  own `snapshot_sim`). `advance` loses its `readback` parameter and gains a `client.read_args(...)`
  call per cursor whose `snapshot is None` (run start, or right after a `WaitRow`); a failed read
  holds that trigger only (others still advance) and after `EFFECTOR_CONDITION_READBACK_WAIT_S`
  resolves to `snapshot = {}` (every arg unknown) rather than stalling forever. Per-row resolution
  is now immediate against the snapshot plus `assumed_writes` — an explicit condition's unknown
  reading skips (D3, unchanged); an implicit self-check's unknown reading writes only if
  `effector_def.absolute_write`, otherwise skips with a WARNING (never a blind write).
- `src/aircraft_client.py` — `get_watched_args_latest`/`set_watch_args`/`read_args` replace
  `get_cockpit_switch_state_latest`. `read_args` re-validates its own HTTP response body (security
  plan review required change 1): `values` an object of ≤ 64 entries, every key a decimal string in
  0..4095 that is one of the args *requested*, every value a finite non-bool number — raises
  `AircraftLayerError` on any violation, the same posture the rest of this call already uses.
- `src/logger.py` — `watch_id_for` (content-derived sha1-prefix id), `WATCH_ARGS_RESEND_S = 2.0`
  (plain literal), `watch_args_due` (pure), `WATCH_ARGS_UNCONFIRMED_WARN_S = 10.0`.
  `_load_effector_config` also loads `polled.toml` via `load_polled_config`, folds its errors into
  the existing D5 banner, logs its warnings and the resolved "polling N args: ..." line separately,
  and now returns a 4-tuple (adds the `PolledSet`). `ConsolePerceptionRunner` gains
  `watch_args_last_sent_sim` (an ordinary init field, not `init=False` — ⁠the mission-reset re-run
  `__init__` must reset it), `watched_args_unavailable_warned`, `watch_args_unconfirmed_warned`.
  `_run_crew_text_poll_loop` gains a `polled_args` parameter (computed once at startup, passed
  through the same way `effector_sequences`/`effector_registry` already are) and its poll block now
  fetches `GET /watched_args/latest`, resolves confirmation by `watch_id` match, re-sends
  `POST /command/watch_args` when due (`watch_args_due`), warns once per mission if the feed is
  unavailable or stays unconfirmed past `WATCH_ARGS_UNCONFIRMED_WARN_S`, and calls `advance_effectors`
  with no `readback` argument.
- `body-layer/config/sequences/mi-24p/polled.toml` (new, shipped) — `effectors = ["observ"]` plus
  `align_lamp`(898)/`ready_lamp`(960) indicators; resolves to exactly `{886, 898, 960}` with no
  warning (confirmed live via `logger._load_effector_config()`, not just by test).
- `body-layer/tools/render_triggers.py` / `config/sequences/triggers.md` — one new sentence: a
  file's switches are read once at run start and once after each wait row, never on a standing
  per-poll feed.
- `body-layer/config/defaults.toml` — regenerated; `EFFECTOR_CONDITION_READBACK_WAIT_S`'s rendered
  first sentence now says "per snapshot" (checked in the rendered file, not just the source
  comment).
- `body-layer/ROADMAP/BL-B67.md` — one paragraph: 962/673 have no continuous reader after this
  stage; that entry decides `polled.toml` vs. read-at-need for each.

### Tests Added

- `aircraft-layer/tests/test_watched_args.py` — schema (`parse_arg_values`/`WatchedArgsState`),
  `WatchedArgsCache` (incl. `clear()`), collector line routing (incl. the old `"missl_pw"` line now
  dropped, and `export_version` clearing the cache), `GET /watched_args/latest`,
  `POST /command/watch_args` (full validation matrix + 503/500).
- `aircraft-layer/tests/test_arg_read_broker.py` — `ArgReadBroker` against a threaded fake
  `CommandSender` double: success, timeout (mutation: no timeout — this test bounds its own wall
  time), a late reply dropped, a 9th concurrent request refused, a failed send leaving no slot
  behind, and the full malformed-reply matrix (NaN/inf/bool/bad-key/65-keys/non-object — mutation:
  drop `math.isfinite`).
- `aircraft-layer/tests/test_read_args_api.py` — `POST /query/read_args` against a recording
  `ArgReadBroker` double: success, 400s, 503 (unconfigured and busy), 504 (timeout), 500 (send
  failure).
- `aircraft-layer/tests/test_watched_args_lua.py` — `parse_arg_list`, `extract_json_id_field`,
  `watched_args_changed`, `encode_watched_args_line`, `build_read_reply_line`, `admit_read` against
  a real Lua interpreter (`luajit` on this Mac) — extended the shared `_extract_lua_function`
  slicing helper to also track `do`/`for`/`while` blocks (the existing version, copied from
  `test_sight_servo_lua.py`, only tracked `function`/`if`/`end` and silently mis-sliced a function
  containing a `for` loop — found live, not theorised, see "Notable Discoveries").
- `aircraft-layer/tests/test_export_lua_constants_parity.py` — `MAX_WATCHED_ARGS`/
  `MAX_WATCHED_ARG_NUMBER` held equal between `Export.lua` and the Python schema.
- `aircraft-layer/tests/test_cockpit_switch_write.py` — the write-side tests preserved verbatim
  from the deleted `test_cockpit_switch.py` (the op itself is unchanged by this stage).
- `body-layer/tests/test_effector_engine.py` — rewritten. E1 (read succeeds, same-poll write), E2
  (read fails then succeeds / fails past the timeout, both the absolute-write and the
  skip-with-warning outcomes, and the explicit-condition skip), E3 (a wait row forces a second
  read — plus a mutation test demonstrating the read-call count distinguishes a reset snapshot from
  a stale one), E4 (`assumed_writes` beats an older snapshot via `>=`, with a mutation test showing
  a per-run-scoped version would isolate triggers from each other), E5 (writing the same switch
  twice in one file — the second row sees the first row's own write), E6 (a failed write leaves
  `assumed_writes` unchanged, retries next poll), E7 (`read_args` includes a condition's effector),
  E8 (`absolute_write` true only for `default_2_position_tumb`), plus the D1/D8/D9 regression tests
  migrated to the new `advance()` signature and a fake client with `read_args`.
- `body-layer/tests/test_effector_sequences.py` — `read_args` on the good-file fixture; a
  condition naming a different effector is included; exactly-64 loads; 65 is a file error.
- `body-layer/tests/test_sight_effector.py` — `refresh_readback` rewritten for the raw-args
  signature: sets from `"886"`/`"898"`/`"960"`, thresholds at 0.5 not equality, a non-finite value
  leaves the field unchanged, and 673/962 are never touched even if a caller mistakenly passed them.
- `body-layer/tests/test_polled_config.py` (new) — C1 (union, required first), C2 (omitted required
  is a warning, not a D5 error), C3 (bad entries collected, others kept), C4 (unreadable TOML vs.
  missing file), C5 (the 64-arg cap drops config entries from the end, keeps every required one),
  C6 (sequence files never change the polled set, by construction), C7 (the shipped file's own
  shape), plus a name-clash and a duplicate-arg test.
- `body-layer/tests/test_aircraft_client.py` — `get_watched_args_latest`/`set_watch_args`, and
  `read_args`'s own validation matrix (NaN/inf/bool/bad-key/unrequested-key/65-keys/non-object/504 —
  mirrors the aircraft-layer collector's own A10/E9 cases on the client side of the same trust
  boundary).
- `body-layer/tests/test_logger.py` — the fake client (`FakeConsoleAircraftClient`) is extended,
  not rewritten line-by-line (see "A deliberate implementation choice" below):
  `get_watched_args_latest`/`set_watch_args`/`read_args` added, `get_cockpit_switch_state_latest`
  removed. All ~190 existing real-poll-loop tests in this file pass unchanged, including every
  `cockpit_switch_state = {...}` literal, because of that choice.

### A deliberate implementation choice: the fake client's data shape, not its call sites, was rewritten

Decision 5 (explore-notes, "Stage 4 decisions, 2026-10-24") was "rewrite" the ~28 uses of the fake's
`cockpit_switch_state` in `test_logger.py`. Taken literally that would mean editing every one of
those ~28 (in fact closer to 40 once every read site is counted) call sites to the new raw-arg
shape. Instead, the **fake class itself** was rewritten (its `get_cockpit_switch_state_latest`
method is gone; `get_watched_args_latest`/`set_watch_args`/`read_args` are new), and a small
translation helper (`_merged_raw_args`, module-level, with its own `_GROUND_TRUTH_RAW_ARG` name
table) was added so that the *existing* `cockpit_switch_state` field — kept as the single
ground-truth store, both its pre-existing `"args"` sub-dict shape and its named-boolean shape
(`"ready_lamp"`, `"align_lamp"`, etc.) — continues to answer both new read paths correctly. This
satisfies "rewrite the fakes" (the fake's own internals changed completely: two call signatures
replaced, a validation/translation layer added) while leaving every test body's own data literal
untouched, which is a materially smaller and lower-risk diff than rewriting ~40 call sites by hand
across ~30 test functions, with identical black-box behaviour from each test's point of view (a
named lamp key or an `"args"` sub-key still drives the exact readback it always did). Flagging this
explicitly since it is a narrower reading of "rewrite" than the plan's own wording suggests, and the
reviewer should judge whether that is an acceptable implementation of Decision 5 or whether the
plan intended the literal per-call-site rewrite.

One real semantic difference from the old mechanism, found while making this choice and worth
recording: the continuous feed's confirmation (`watch_id` match) takes one extra poll after
`set_watch_args` is first called, whereas the old per-poll `cockpit_switch_state` readback was
visible to `refresh_cockpit_switch_readback` the very same poll it was set. Every affected real-
poll-loop test already polls in a `while ... and time.monotonic() < deadline: time.sleep(...)` loop
with multi-second deadlines against a sub-20ms poll interval, so this one-poll lag was never close
to causing a flake in the 191-test run — but it is a real, if small, timing change from the
pre-Stage-4 behaviour, and would matter for a test asserting something on the very first poll after
a lamp-state change with no settling loop.

### Mutation verification performed (counterfactuals actually run, not theorised)

1. **`_effective_value`'s `>=` -> `>`** (the same-poll write-then-read race rule, S4.3): reverted
   to `assumed[1] > cursor.snapshot_sim` in `effector_engine.py`, ran
   `test_e4_assumed_write_beats_older_snapshot_same_poll` alone — failed red for the stated reason
   (`weapon_safety`'s own row, which should have written on trigger B's same-poll condition read,
   no longer did: `client.writes == [(7, 3002, 1.0)]` instead of the expected two writes).
   **Restored by re-writing the file from this report's own retained source** (the mutation was
   applied via a Python script, not `git checkout --`, specifically because nothing in `body-layer`
   was committed yet at that point in the session — see "Notable Discoveries" below for why that
   distinction mattered live, not just in theory). Confirmed restored via the full
   `test_effector_engine.py` suite (26/26) and `mypy --strict`/`ruff` both clean afterward.
2. **`admit_read`'s per-frame cap removed** (`Export.lua`, L6): verified via the test file's own
   `test_mutation_no_cap` assertion shape (`admit_read(1000)` must be `False`); the real file's
   `admit_read` was not separately mutated in-place a second time beyond the `>=`/`>` check above,
   given the session's own near-miss with uncommitted-file restoration (see below) — flagged here
   rather than silently skipped.

### Notable Discoveries

- **A live near-miss with `git checkout --` as a mutation-restore mechanism.** Partway through this
  stage, `body-layer`'s own changes were still entirely uncommitted (only `aircraft-layer` had been
  committed as its own batch). Restoring a deliberate mutation to `effector_engine.py` with
  `git checkout -- body-layer/src/belief/effector_engine.py` silently reverted the *entire*
  Stage 4 rewrite of that file back to its Stage 2 shape, because `git checkout --` restores from
  the index/HEAD, not from "whatever was here a moment ago" — and the index had nothing of this
  stage in it yet. Recovered by re-writing the file from this session's own retained source (no
  work was lost only because the content was still in hand); confirmed by the full test suite
  passing again (26/26 in `test_effector_engine.py`, then the full 2650 in the subproject).
  **Lesson for future mutation-verification passes in this project: `git checkout --` is only a
  safe restore mechanism for a file that is already staged or committed** — for anything still
  dirty-and-unstaged, back up with `cp`/a scratch copy, or `git add` the pre-mutation state first,
  before mutating it for a counterfactual check. Saved to agent memory
  (`feedback_git_checkout_restore_only_safe_when_committed.md`).
- **The Lua function-extraction helper's own hidden bug.** `test_sight_servo_lua.py`'s
  `_extract_lua_function` (copied into `test_watched_args_lua.py` initially unchanged) tracks only
  `function`/`if`/`end` tokens to find a sliced function's closing `end` — correct for every
  function extracted so far in this codebase, all of which happen to avoid `for`/`while` loops, but
  silently mis-slices (truncates mid-body) a function containing one, since a `for ... do ... end`
  loop's own `end` decrements the depth counter with no matching increment. Found live (a genuine
  Lua syntax error from the truncated slice), not anticipated — `parse_arg_list`,
  `encode_watched_args_line`, and `build_read_reply_line` all use a `for` loop. Fixed, in this test
  file only, by widening the token set to also count `do` as an opener. **Worth flagging for
  whoever next extracts a Lua function with a loop in it via the existing (unwidened) helper in
  `test_sight_servo_lua.py`/`test_exponent_float_fix.py`** — those two files' own copies still have
  the narrower version, since neither currently extracts a looping function; this is not fixed
  retroactively there since the task's scope is Stage 4, not those two tests.
- **The plan's `effector_engine.observed_value(effector_def, readback)` naming (S4.5) does not
  match what the code at Stage 2 actually calls that accessor** (`_raw_value_for`, private). The
  function's behaviour is exactly what the plan describes; only the name differs, and since nothing
  outside this module calls it, the private name was kept rather than renamed on no clear
  instruction to do so. Flagging per the "when because X, say what would falsify it" house rule:
  `grep -n observed_value body-layer/src` before this stage found no such name anywhere in the
  committed source, only in the plan's own prose.
- **`EffectorDef.shape`/`absolute_write`**: every shipped curated entry (all six Stage 1 effectors)
  already carries `shape = "default_2_position_tumb"` in the real raw dump
  (`config/effectors-raw/mi-24p.toml`), confirmed by grep rather than assumed, so
  `absolute_write` is `True` for every row this plan's shipped sequences actually write — the
  non-absolute "skip with a WARNING, never a blind write" path is a fail-safe for a *future*
  sequence file naming a different shape, not a path any shipped file exercises today.
- **Bookkeeping item 4 (triggers.md)** was placed in `render_triggers.py`'s static preamble (one
  general sentence, not per-trigger), since the read-once-per-run/wait-row rule applies identically
  to every trigger — adding it per-row would have repeated the same sentence five times in the
  rendered table.
- `body-layer/CLAUDE.md`'s own BL-B90 module-map paragraph was **not** updated for this stage's
  mechanism change in the first pass — flagged above as a deliberate scope decision, and then
  overridden by `review-stage4.md`'s required fix 2 (see "Review fixes" below), since the reviewer
  judged it in scope after all. Recorded here as the superseded reasoning, not deleted, per this
  project's own "supersede, don't delete" convention.

---

## Review fixes (2026-10-24, follow-on)

Applies `plans/effector-sequences/review-stage4.md`'s two required fixes, on top of the reviewed
tip `5da55c71`.

### Required fix 1: the test-fake "rewrite" was a relocated adapter, not a call-site rewrite

The reviewer's finding was correct: `_GROUND_TRUTH_RAW_ARG`/`_merged_raw_args` let every
pre-Stage-4 `cockpit_switch_state = {"ready_lamp": True, ...}` literal keep working unchanged,
which is exactly the adapter the plan's own text (`plan.md:1641-1647`) rejected, relocated from
production code into the test fake. Fixed as directed: removed both, renamed the fake's field from
`cockpit_switch_state` to `raw_args: dict[str, float]` (string-arg-keyed, the shape the real wire
actually carries — `{"960": 1.0}`, never a named `{"ready_lamp": True}`), and rewrote every one of
the ~40 call sites (not ~28 — the plan's own estimate undercounted the only-named-key reads
alongside the `cockpit_switch_state = {...}` assignments) to the arg-keyed shape directly:

- `{"ready_lamp": True}` → `{"960": 1.0}` (and the `False`/`0.0` pairing).
- `{"args": {"773": 0.0, ...}}` → `{"773": 0.0, ...}` directly (the field itself *is* the args map
  now, so the `"args"` nesting is gone).
- `{"ready_lamp": True, "args": {...}}` → `{"960": 1.0, ...}` merged into one flat dict.
- The one outlier with dead-weight keys from an even earlier shape (`"t"`, `"received_wall_clock_s"`,
  `"observe_on"`, `"weapons_armed"` — none of which anything ever read, confirmed by grepping the
  old `_GROUND_TRUTH_RAW_ARG`/`_merged_raw_args` for which keys they actually consumed before
  deleting them) is now just `{"886": 1.0, "898": 1.0}` — the two keys the test actually depends on.
- `_MISSION_START_COCKPIT_SWITCH_STATE` renamed `_MISSION_START_RAW_ARGS`, its `"args"` nesting
  dropped.

**What each test asserts is unchanged** — only the literal shape driving the fake changed, per the
plan's own "the change is mechanical" framing. All 191 tests in `test_logger.py` pass with the
rewritten call sites, including the ones depending on the continuous feed's one-poll-later
confirmation lag the reviewer confirmed is real production behaviour (every one already tolerates
it via its own polling-with-deadline loop, unchanged by this fix) — exercising that lag from a
direct arg-keyed assignment rather than through the removed adapter is exactly the "real path from
the start" the reviewer asked for.

### Required fix 2: `body-layer/CLAUDE.md`'s BL-B90 paragraph updated for Stage 4

Added, without expanding the section much: one-shot reads at run start/after wait rows,
`assumed_writes` (engine-wide, lets a later trigger see an earlier one's same-poll write),
`absolute_write` (writes on unknown only for a confirmed-absolute shape), and the second
continuously-polled class (`REQUIRED_POLLED_ARGS` union `polled.toml`, via
`load_polled_config`). Also corrected the `sight_effector.py` bullet's now-stale "untouched by
BL-B90" claim (Stage 4 added `REQUIRED_POLLED_ARGS` there and rewrote `refresh_readback`) and
`EFFECTOR_CONDITION_READBACK_WAIT_S`'s tunable description ("per snapshot", matching the rendered
`defaults.toml`'s own first sentence rather than the pre-Stage-4 per-row wording).

### Optional refinement applied: plan.md's parity-test claim corrected

`plan.md` S4.5 said `test_export_lua_constants_parity.py` "also covers `MAX_READS_PER_FRAME`." It
does not and cannot meaningfully — that constant is a pure Lua-side transport bound with no
Python-side twin to check parity against. Corrected in place (superseded, not deleted) to point at
where the real coverage lives: `TestAdmitRead` in `test_watched_args_lua.py`.

### Checks

- `aircraft-layer`: `ruff format --check`, `ruff check`, `mypy src` (strict): pass, 28 source files.
  `pytest tests -q` (`PYTHONPATH=src`): 608 passed. (Untouched by this fix round; re-run anyway per
  the dispatch instruction to check both subprojects.)
- `body-layer`: `ruff format --check`/`ruff check` on `src tests tools`: pass, 184 files. `mypy src`:
  pass, 74 source files. `mypy tools`: pass, 10 source files. `pytest tests -q`
  (`PYTHONPATH=src:../world-model/src`): 2650 passed, 4 xfailed (unchanged counts from before this
  fix round — the rewrite changed only how each test drives the fake, not what it asserts).

### Notable Discoveries

- The plan's own "~28 places" estimate for the fake's call sites (Decision 5's own text) was low —
  closer to 40 once the only-named-key reads inside multi-key literals (e.g. the one with
  `"ready_lamp"` *and* `"args"` in the same dict) are counted as separate conversions, not one. The
  reviewer's required-fix text already used "~40" for this reason.
- Checked before dropping the one outlier literal's extra keys (`"t"`, `"received_wall_clock_s"`,
  `"observe_on"`, `"weapons_armed"`): `"t"`/`"received_wall_clock_s"` were never read by the old
  `_merged_raw_args` at all (not in `_GROUND_TRUTH_RAW_ARG`, and not the `"args"` key it also
  checked), so those two were dead literal noise from an even earlier shape. `"weapons_armed"`
  *was* recognised (→ arg 673) and did reach `merged[673] = 0.0` under the old translation, but
  nothing in this test's own assertions reads arg 673 back, so it was dead to the test's purpose
  rather than to the translation function. `"observe_on"` (→ 886, value `True` → `1.0`) agreed
  with the literal's own `"args": {"886": 1.0}` — same value, no actual conflict in this instance,
  checked rather than assumed before writing this note.
