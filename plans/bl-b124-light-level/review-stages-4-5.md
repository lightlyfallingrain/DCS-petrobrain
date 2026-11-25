### Review Summary

Reviewed BL-B124 Stages 4–5 on `feature/bl-b124-light-level`, range `b1978652..728fcf8e`
(fast-forwarded cleanly into this worktree from `d565c5ed` — HEAD was a strict ancestor, tree
clean; no divergence).

**Scope matches `implementation.md`'s own stated boundary.** Stage 4 (`body.py`'s poll loop
computes a real `sun_elevation_deg` and threads it through `decide_optic`/`naked_eye_source`/
`drain_attack_run`) and Stage 5 (`EmitterKind.LAUNCH_FLASH`, `S_EVENT_SHOT` → collector branch →
`emitters.py` fold) are what's built. No `mission-interpreter/` change (correctly — the
2026-11-25 amendment fully superseded the `.miz`/MI-3/MI-6 thread). Hybrid channel
(`hybrid_source.py`) and daylight behaviour are untouched by this diff (`git diff --stat`
confirms; the full suite's unchanged pass count for everything outside the touched modules
confirms it behaviourally).

**Departure 1 (plan's own `light_factor` tuple → `sun_elevation_deg` + per-optic resolution)
is a real fix, not a regression, and I verified it by mutation, not by reading.** Stage 3's
single shared `light_factor` tuple would have dimmed every optic identically — I reproduced
that exact defect by reverting `_light_factor_for` to always resolve `UNAIDED_OPTIC` regardless
of the optic argument, and `TestBlB124SunElevationPerOptic::test_improvement_window_m_shrinks_
each_bound_by_its_own_optics_factor` failed immediately (`0.5 != 0.5`, the two bounds collapsing
to the same ratio). Reverted. Spot-checked the anchor math by hand at −8° and −3.5°: naked eye
and binoculars both sit at a flat `(0,0,0)` through the whole `[−12°, −5.3°]` segment (their own
−5.3° anchor is already `(0,0,0)`, so the segment from the flat-dark floor to that anchor
interpolates between two zeros), while the 9K113 (wide and narrow) interpolates from `0.0` up to
`0.227`–`0.389` over the same segment — i.e. at −8° binoculars/eye are already fully blind and
the 9K113 still has real range. That is exactly the user's Q5 order ("binoculars as long as they
can viably see, then 9K113 only while there is enough light... after that naked eyesight only
for light sources"). I grepped every `tier_ranges()` call site in `optic_policy.py`/
`attack_run.py` (14 + 1 signatures) and confirmed each resolves `_light_factor_for(<the optic
that call site is actually evaluating>, sun_elevation_deg)` — `improvement_window_m` and
`least_capable_sufficient_optic`/`guidance_request_for`, the two functions that compare several
named optics in one call, each resolve a fresh factor per rung rather than reusing one value
across optics.

**Stage 5 (`LAUNCH_FLASH`) matches the plan and the explore-notes exactly, verified by mutation
at every seam**: `FIRING` wins over `LAUNCH_FLASH` wins over `BURNING` in `resolve_emitters`
(confirmed: reordering the `dict.update` calls flips `test_resolve_emitters_launch_flash_wins_
over_burning_for_the_same_unit`); `S_EVENT_SHOT` never overwrites an existing `FIRING` entry
(confirmed: removing that guard flips `test_shot_event_does_not_overwrite_an_existing_firing_
entry`); death removes a `LAUNCH_FLASH` entry the same as `FIRING` (confirmed: narrowing the
death-removal kind tuple flips `test_death_removes_a_launch_flash_entry_like_firing`);
presence-only is inherited correctly from the shared emitter-bypass clamp in `visibility.py`
(pre-existing, unmodified code path — `LAUNCH_FLASH` just adds a third kind into the same
clamp). `LAUNCH_FLASH_DURATION_S` as a plain aircraft-layer module constant (not a body-layer
`tuning.*` entry) is the right call and matches root `CLAUDE.md`'s "outside body-layer the loader
does not exist" instruction, mirroring `FIRING_MIN_VISIBLE_S`/`FIRING_WATCHDOG_S`'s own existing
posture.

**Midnight rollover and extrapolation are both real, tested, and mutation-verified.**
`test_abs_time_s_past_86400_rolls_over_the_calendar_day` covers the Julian-day arithmetic
directly; I separately reverted `_resolve_sun_elevation_deg`'s extrapolation delta
(`abs_time_s0 + (ownship.t_sim - model_time_at_capture)` → `abs_time_s0`) and
`test_extrapolates_between_samples_via_model_time_delta` caught it immediately (`75.948 !=
75.933`).

**Tunables render correctly.** Read the rendered `body-layer/config/defaults.toml`, not the
source comments: `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`, `SIGHT_FULL_DARK_SUN_ELEV_DEG` (both already
fixed in the Stage 1–3 review round) and the new `MISSION_CLOCK_MAX_AGE_S` all carry their full
dangerous-direction warning intact as a single first sentence.

**Checks**: `ruff format --check`/`ruff check` clean on both subprojects; `cd body-layer &&
.venv/bin/mypy src` clean (94 files); `cd aircraft-layer && .venv/bin/mypy src` clean (28 files);
body-layer full suite (`-m "not slow"`, parallel) 3769 passed, 4 xfailed; aircraft-layer full
suite (`-m "not slow"`) 1065 passed; `luac5.1 -p` clean on every `.lua` file (no Lua touched by
Stages 4–5, confirmed by `git diff --stat -- '*.lua'` against the Stage 3 tip being empty).

### Required Fixes

- **A dead/frozen firing-events feed is indistinguishable from a healthy one, so the fail-loud
  contract this stage exists to deliver (user Q6: "mission should always have both readable.
  Error if not") silently does not fire in exactly the failure mode it was built for.**
  `_resolve_sun_elevation_deg` treats "this poll's `GET /firing/latest` parses a well-formed
  `mission_clock` dict" as "fresh," and resets `light_level_unavailable_since_wall` to `None`
  and `light_level_last_clock_model_time_s` to the current `t_sim` every time that happens —
  but `EmitterTracker.snapshot()` (aircraft-layer) has no mechanism to distinguish "a new sample
  just arrived" from "nothing has arrived in minutes and this is the same cached
  `MissionClockSample` from before the Hook died," because `_last_mission_clock` is only
  overwritten by a fresh `ingest()` call and is never cleared or timestamped independently.
  I reproduced this directly (not just reasoned about it): calling `_resolve_sun_elevation_deg`
  repeatedly with the *same, unchanged* `mission_clock` dict across ownship samples spanning
  ~57 minutes of `t_sim` returns the exact same frozen sun elevation every single call, and
  `light_level_error_logged` never becomes `True` — the grace/error path this stage built is
  never reached at all. The failure direction is the wrong one for the no-omniscience goal the
  module's own docstring states: a feed that dies at noon leaves Petrovich behaving as if it
  were permanently noon, including deep into a night the mission actually reaches — the exact
  opposite of "force full dark," not merely a missed error log. This is the same failure shape
  already named in this role's own memory (`feedback_watchdog_backstop_conflates_failure_modes`):
  the mechanism's docstring and tests cover "parse failed/absent," the scary, obvious case, and
  never consider "parses fine but is stale," the quiet one.
  **Remedy**: give `EmitterTracker` (or the wire) a way to distinguish a genuinely new sample —
  e.g. compare the batch's own `dcs_model_time_s` (already in the snapshot, already advances
  monotonically within a mission) against the previous snapshot's, or stamp `received_wall_
  clock_s` at ingest time rather than at `snapshot()`-call time (today it is `time.time()`
  evaluated fresh on every `GET`, so it cannot answer "when did this last change" either) — and
  have `_resolve_sun_elevation_deg` treat an unchanged `dcs_model_time_s` across polls as "no new
  sample," not "fresh." This does not need to block merge if the user accepts the risk as a
  known gap (it mirrors the project's already-accepted "no staleness warning for a stale Hook
  script" limitation elsewhere, `docs/acceptance/2026-11-16-bl16-qnh-mission-start-sortie.md`),
  but it should be a conscious decision, not a silent one — flagging here rather than filing
  straight to backlog because it directly contradicts a user answer this feature's plan quotes
  verbatim (Q6).

### Optional Refinements

- **A second, independent `GET /firing/latest` round-trip per poll** (`body.run_once`'s own
  comment acknowledges this: `NakedEyePerceptionSource` already fetches the same endpoint
  internally for emitter resolution, but `ConsolePerceptionRunner` has no access to that
  source-internal fetch, so light level fetches it again). Explicitly justified as negligible at
  1 Hz in the code's own comment, and I have no measurement suggesting otherwise — purely a
  "could share one fetch instead of two" tidiness note, not a correctness or performance concern
  worth blocking on. Worth a line in a future stage if `NakedEyePerceptionSource`'s own fetch
  path is ever refactored to expose its last snapshot to the runner.
- **`MISSION_CLOCK_MAX_AGE_S`'s grace window is measured in wall-clock seconds
  (`time.monotonic()`), not sim time**, so a paused mission (sim clock frozen, wall clock
  running) will start counting toward "error if not readable" even though nothing is actually
  wrong — the Hook simply has nothing new to report while paused. This is probably the right
  call (the Hook polls on its own 1 Hz wall-clock cadence regardless of pause state, so wall time
  is the correct unit to bound *its* responsiveness against), and `aircraft-layer/CLAUDE.md`'s
  own testing note ("always include a paused-state check alongside any moving-aircraft check")
  suggests this exact scenario is meant to be checked live rather than assumed — flagging only so
  the test card's dawn pass includes a deliberate pause, since nothing in the unit suite exercises
  a paused-mission mission_clock read.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read of Stages 4–5's own diff (`body.py`'s new functions/fields, `optic_policy.py`'s
rename, `attack_run.py`/`crew_console.py`'s threading, `emitters.py`'s `LAUNCH_FLASH` fold,
`firing_receiver.py`'s `S_EVENT_SHOT` branch, every new test file). Mutation-verified six
load-bearing claims directly (cross-optic factor resolution, extrapolation delta, emitter
precedence, non-overwrite of `FIRING`, death removal, and the fail-loud gap itself). Did not
re-review Stages 1–3's own code beyond what Stage 4 renamed/threaded through it — that review
(`review-stages-1-3.md`) already covers that ground and nothing in this diff reopens it. The
frozen-feed scenario was reproduced directly against the real function, not asserted from
reading.

### Fix round (commit `baba22f4`)

**Re-reviewed on `feature/bl-b124-light-level`, fast-forwarded cleanly (HEAD was a strict
ancestor of `baba22f4`, tree clean, no divergence).**

**Required Fix 1 — fixed, and the fix is correct.** The guard at `_resolve_sun_elevation_deg`
(`body.py`) is now `if fresh is not None and fresh != runner.light_level_last_clock:` — a
sample counts as fresh only when it differs from the one already stored, so a dead/frozen
feed (same cached `mission_clock` dict served forever) now falls into the pre-existing
unavailable/grace-window/one-shot-error path instead of silently refreshing the timers every
poll. Both the function's own docstring and the `light_level_unavailable_since_wall` field
comment were updated to match the new condition — the old prose was the exact premise the
defect lived under, and both now correctly state "genuinely new" rather than "parsed."

Verified three ways, independently of the implementer's own mutation note:

1. **Reproduced the original defect's absence, by mutation against the real function.**
   Reverted the guard to the pre-fix `fresh is not None`, ran the three new tests —
   `test_a_frozen_feed_serving_the_same_dict_forces_dark_and_logs`,
   `test_repeated_identical_sample_does_not_reset_the_unavailable_timer`,
   `test_extrapolation_keeps_advancing_through_a_run_of_repeated_samples` — and all three
   failed for the stated reason (the extrapolation one with a direct numeric mismatch,
   `75.940... != 75.933...`; the other two on the `is None`/equality assertions). Restored the
   file; `diff` against the pre-mutation copy was empty, confirming an exact restore. This is
   the same reproduction this review ran against the original defect, now run against the
   fix's absence — the three tests are the ones actually carrying the fix, not decorative.
2. **Dead feed → forced-dark + one error: confirmed directly**, by reading the new
   `test_a_frozen_feed_serving_the_same_dict_forces_dark_and_logs` test and its pass under the
   restored code: ~57 simulated minutes of an identical repeated dict, then the wall-clock
   timer pushed past `MISSION_CLOCK_MAX_AGE_S`, ends in `SIGHT_FULL_DARK_SUN_ELEV_DEG` and
   `light_level_error_logged is True` — the exact outcome Required Fix 1 asked for.
3. **Healthy feed at 1 Hz, body-layer polling faster, cannot trip the error falsely or stall
   extrapolation — checked by reading the numbers, not assumed.** A genuine sample seen on
   several consecutive fast polls before the Hook's next 1 Hz update *will* repeat the dict and
   *will* start `light_level_unavailable_since_wall` ticking on the first repeat (the guard
   cannot distinguish "about to get a new sample next tick" from "the feed just died" — it has
   no other signal to go on, same limitation the Required Fix's own remedy text names as
   unresolved). But `MISSION_CLOCK_MAX_AGE_S` defaults to 5.0 s (`lo=2.0`/`hi=30.0`,
   `perception/light_level.py`) against a 1 Hz source, i.e. several poll cycles of slack — the
   timer clears back to `None` the moment the next genuinely-new sample arrives, long before
   5 s elapses under any live cadence, so no false error is reachable at the shipped default.
   Extrapolation does not stall either: `light_level_last_clock_model_time_s` is only
   reassigned on a genuinely-new sample now, so a run of repeats keeps extrapolating from the
   *last real* sample's capture time rather than re-anchoring (and therefore freezing) on every
   repeat — `test_extrapolation_keeps_advancing_through_a_run_of_repeated_samples` is exactly
   this case and passes.
4. **Mission restart reset — confirmed.** `ConsolePerceptionRunner.reset_for_new_mission`'s own
   docstring lists `light_level_last_clock`/`light_level_last_clock_model_time_s`/
   `light_level_unavailable_since_wall`/`light_level_error_logged`/
   `light_level_sun_elevation_deg` among the fields that reset to their declared default on a
   genuine DCS mission (re)start, and `_reset_mission_state` calls it. A frozen sample from a
   mission that just ended cannot leak across a restart and be compared against the new
   mission's first real sample as "unchanged."

**Scope held**: only `body-layer/src/body.py`, its own tests, and `implementation.md` changed
— no aircraft-layer file touched (`git show --stat baba22f4`), consistent with the fix being
entirely on the consumer side of the existing wire shape, not a wire/schema change. The
Optional Refinement on wall-clock-vs-sim-time was correctly left as a live-test-card item, not
silently folded into this fix — `implementation.md`'s own "Review fix round" section gives the
reasoning (reworking four pre-existing tests for an optional refinement would exceed the
required fix's own scope).

**Checks, this round**: `ruff format --check`/`ruff check` clean on `body-layer/src`,
`body-layer/tests`; `cd body-layer && .venv/bin/mypy src` clean (94 files); body-layer full
suite (`pytest tests -q -m "not slow" -n auto`, run against the real venv since this worktree
carries none of its own) — 3772 passed, 4 xfailed (the review's prior 3769 + the 3 new tests,
exactly accounted for). No tunable changed, so `config/defaults.toml` correctly untouched.

### Fix Round Verdict
APPROVED

### Fix Round Review Confidence
Full read of the fix commit's diff (`body.py`, `test_body.py`, `implementation.md`).
Mutation-verified the fix itself (guard reverted, all three new tests failed for the stated
reason, restore confirmed exact by `diff`). The healthy-feed-at-1Hz concern was checked
analytically against the shipped default and bounds, not reproduced with a live 1 Hz
simulation — the margin (5 s grace vs. ~1 s cadence) is wide enough that this is adequate
confidence without a timed reproduction, and the live test card already carries the one
scenario (a deliberate pause) that genuine-cadence analysis alone cannot settle.
