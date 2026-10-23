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
