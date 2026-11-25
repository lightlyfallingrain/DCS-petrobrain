### Implementation Summary

Implemented BL-B124 Stages 1-3 only, per the plan's 2026-11-25 amendment (Stage 4 "wire the real
value into body.py's poll loop", Stage 5 "LAUNCH_FLASH" and Stage 6/BL-B136 "EXPLOSION" are **not**
in this batch).

**Stage 1 (amended):** mission date + wall clock now ride the firing-events Hook's existing 1 Hz
`net.dostring_in` poll, not a `.miz`/MI-3/MI-6 thread. `EVENT_POLL_CODE` also reads
`timer.getAbsTime()` and `env.mission.date` (both `pcall`-guarded independently of the event drain),
appends them after a `\1` separator (the same device the LOS Hook's own `probes` key already
established), and the outer Hook script splits that off and sends it as a new `mission_clock`
envelope key — `"<abs_time_s>|<year>|<month>|<day>"` or the literal sentinel `"unavailable"` on a
guarded read failure. `schema.firing.MissionClockSample` parses it (a malformed sub-wire drops to
`None` without failing the rest of the batch); `EmitterTracker` carries the most recent reading and
exposes it on `GET /firing/latest`'s existing response shape. Body-layer's `get_firing_latest()` is
a shallow pass-through, so it already returns the new key with no client-side change at all.

**Stage 2:** `perception/light_level.py` (new, pure, no DCS import). `sun_elevation_deg()` is a
standard low-precision solar-position formula, numerically verified against the plan's own anchor
table (reproduces -5.338/-3.482/+0.303 deg against the plan's stated -5.3/-3.5/+0.3 at the test
mission's -28/-18/+2 min-from-sunrise points). `light_factor(optic, sun_elevation_deg)` is the
anchored, per-optic, per-tier `(presence, class, type)` curve: piecewise-linear between the three
measured anchors, flat `(1,1,1)` above the new `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG` tunable and flat
`(0,0,0)` below the new `SIGHT_FULL_DARK_SUN_ELEV_DEG` tunable. The three anchors' per-optic/
per-tier factors are computed as `measured_range / BTR-60_naked-eye_baseline_scaled_by_optic_mult`
(the baseline already established in `body-layer/research/
2026-09-21-aspect-magnification-and-distinctiveness.md` -- presence 3.1/class 0.4/type 0.2 km),
clamped to `[0.0, 1.0]` where the raw ratio exceeded 1.0 (the naked eye's own +0.3 deg class/type
figures) -- documented in the module's own comments with the source numbers, per the "decomposition,
not a bare total" convention.

**Stage 3:** `light_factor: tuple[float, float, float] = (1.0, 1.0, 1.0)` threaded through
`tier_ranges()`/`_achieved_tier()`/`check_visibility()` and the whole `optic_policy.py`/
`attack_run.py` call chain up to both modules' own `decide()` entry points, plus
`naked_eye_source.py`'s `poll()` (as a per-poll dataclass field, matching `optic`/`scan_plan`'s own
shape). Mechanical: every new parameter defaults to a true no-op, nothing in `body.py` supplies a
real value yet.

### Files Changed
- `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` — `EVENT_POLL_CODE` also reads
  `timer.getAbsTime()`/`env.mission.date`; `sendPayload`/`pollAndSend` split the result on `\1` and
  add the optional `mission_clock` envelope key.
- `aircraft-layer/src/schema/firing.py` — new `MissionClockSample` dataclass +
  `FiringEventBatch.mission_clock` field (default `None`) and `from_wire`'s new
  `mission_clock_raw` kwarg.
- `aircraft-layer/src/collector/firing_receiver.py` — `EmitterTracker` carries
  `_last_mission_clock`, overwritten every `ingest()`, exposed in `snapshot()`.
  `FiringEventsReceiver._handle_datagram` extracts the new envelope key.
- `aircraft-layer/src/api/server.py` — docstring update for the new `mission_clock` key on
  `GET /firing/latest`.
- `body-layer/src/aircraft_client.py` — docstring updates only (`get_firing_latest` is a shallow
  pass-through; no code change needed for the new key to reach body-layer).
- `body-layer/src/perception/light_level.py` (new) — Stage 2's pure astronomy + light factor curve.
- `body-layer/src/perception/visibility.py` — `tier_ranges()`/`_achieved_tier()`/
  `check_visibility()` gain `light_factor`; `check_visibility`'s own `size_curve_threshold_m`
  (gate 3) is scaled by `light_factor[0]` too, kept in sync with `_achieved_tier`'s call (see
  Notable Discoveries).
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains a
  `light_factor` field (per-poll, like `optic`), threaded to its `check_visibility()` call;
  `reset_for_new_mission`'s docstring updated to name it alongside the other per-poll fields.
- `body-layer/src/belief/optic_policy.py` — `light_factor` threaded through all six named
  `tier_ranges()` call sites and up through `can_still_improve`/`_glass_can_improve`/
  `_area_or_glass_can_improve`/`_decide_sighting_locked`/`_decide_sighting`/
  `_decide_without_guidance`/`look_target_for` to this module's own `decide()`. The three
  `can_improve`-callback functions (`can_still_improve`, `_glass_can_improve`,
  `_area_or_glass_can_improve`, `sight_can_still_improve`) keep `light_factor` as a keyword-only,
  default-only parameter rather than widening their `Callable[[LookTarget], bool]` contract — see
  Notable Discoveries.
- `body-layer/src/belief/attack_run.py` — `decide()` gains `light_factor`, threaded to its
  `guidance_request_for` call.
- `body-layer/config/defaults.toml` — regenerated (`SIGHT_FULL_DARK_SUN_ELEV_DEG`,
  `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG` under `[perception.light_level]`).
- `body-layer/tests/test_naked_eye_source.py` — added `light_factor` to
  `_PER_POLL_OVERWRITTEN_FIELDS` (the field-coverage test's own designed extension point for a new
  per-poll field).

### Tests Added
- `aircraft-layer/tests/test_firing_schema.py` — `MissionClockSample.from_wire` (round-trip,
  `"unavailable"` sentinel → `None`, malformed field count/value raises), plus
  `FiringEventBatch.from_wire`'s `mission_clock_raw` threading (absent by default, parses, sentinel,
  malformed sub-wire dropped without failing the rest of the batch).
- `aircraft-layer/tests/test_firing_receiver.py` — `EmitterTracker.snapshot()` carries the most
  recent batch's `mission_clock` (and goes back to `None` when a later batch cannot read it); the
  full UDP-envelope path (`mission_clock` key present/absent) reaches the snapshot correctly.
- `body-layer/tests/test_light_level.py` (new) — `sun_elevation_deg` against the plan's anchor
  table (within tolerance), monotonic through dawn, correct day-rollover handling, noon-high/
  midnight-low sanity; `light_factor` flat at the two end points, per-optic/per-tier ordering
  (sight narrow > eye at dusk, eye/binocular type is zero at -18 min), piecewise-linear
  interpolation, every component staying in `[0, 1]`.

### Checks
(aircraft-layer, body-layer)
- ruff format --check: pass (both)
- ruff check: pass (both)
- mypy --strict (run from inside each subproject): pass (both)
- pytest -q: aircraft-layer full suite 1062 passed (1049 at Stage 1, +13 new tests across Stages
  1-3). body-layer **full suite** (not just targeted): 3768 passed, 4 pre-existing xfailed, 0
  failed -- caught and fixed one real defect this stage introduced
  (`test_tuning_comment_renders.py`'s cross-key-comment check, see Notable Discoveries), green on
  the re-run after the fix.
- Lua syntax (`luac5.1 -p`) on the Hook file and the extracted bridged `EVENT_POLL_CODE` literal:
  both clean; `GETGLOBAL` audit shows no stray names.

### Notable Discoveries
- **A real correctness trap, caught and closed in Stage 3 even though it has zero behavioural
  effect yet**: `check_visibility()`'s gate 3 (`size_curve_threshold_m`, the range-admission bound)
  recomputes `tier_ranges()`'s own presence formula inline rather than calling `tier_ranges()`.
  Threading `light_factor` into `tier_ranges()`/`_achieved_tier()` alone would have left gate 3
  admitting candidates at today's unscaled range, so a dimmed-out candidate beyond its true
  (scaled-down) presence threshold would still fall through `_achieved_tier`'s "beyond even lowres"
  fallback to a spurious detection the moment Stage 4 supplies a real value. Fixed by scaling
  `size_curve_threshold_m` by `light_factor[0]` too. Recorded in agent memory
  (`feedback_tier_ranges_gate3_duplicate_formula.md`).
- **Deliberate, bounded scope decision on the callback functions**: `can_still_improve`,
  `_glass_can_improve`, `_area_or_glass_can_improve` and `sight_can_still_improve` are each passed
  as bare `can_improve: Callable[[LookTarget], bool]` callbacks at several call sites. Rather than
  widen that callback contract (which would require every call site that passes one of these by
  name to instead pass a closure/`functools.partial` carrying a real `light_factor` -- work with no
  payoff until Stage 4 has a real value to give it), each of the four keeps `light_factor` as a
  keyword-only, default-only parameter: structurally compatible with the existing callback type
  (a function with an extra optional parameter still satisfies `Callable[[LookTarget], bool]`), and
  each already threads it correctly into its own `tier_ranges()`/sub-call. Flagging this explicitly
  as a scope decision: Stage 4 (not built here) will need to decide whether any of these four call
  sites should become light-factor-aware, and if so will wrap the callback in a closure rather than
  changing the shared type.
- **The mission-interpreter subproject is untouched** -- the 2026-11-25 amendment fully superseded
  the original "thread `.miz` date through MI-3/MI-6" plan; `mission-interpreter/`'s own `CLAUDE.md`
  and test suite were read to confirm this (no `date`/`start_time` field exists past `RawMission`,
  consistent with the investigator's own 2026-11-25 note), and no file in that subproject was
  changed.
- **Dataclass field-bucket test caught the new `light_factor` field immediately** --
  `test_naked_eye_source.py::test_reset_for_new_mission_field_coverage_is_complete` failed the
  instant the field was added, exactly as its own docstring says it should; fixed by adding
  `"light_factor"` to `_PER_POLL_OVERWRITTEN_FIELDS` (the test's designed extension point, not a
  change to the test's own logic).
- **Plan's test-impact check (role instructions step 1b):** the plan names no specific tests by
  file (it is new-code-only for Stages 1-3), so there was no "named test that doesn't exist" to
  check. `grep`-ing the test suite for modules this stage touches found the field-coverage test
  above (not named in the plan) as the one test requiring an edit — everything else is new tests
  added by this implementation.

### Review fix round (`plans/bl-b124-light-level/review-stages-1-3.md`, APPROVED WITH MINOR FIXES)

- **Required Fix 1 — dangerous-direction warning dropped from the rendered `defaults.toml`.**
  Both new tunables' `#:` comment blocks had the warning as the *second* sentence;
  `generate_defaults.py` only ever renders the first. Rewrote each block, folding the warning into
  one long first sentence — the same convention `LOWRES_ANGULAR_RADIUS_RAD`/
  `MEDRES_ANGULAR_RADIUS_RAD` already use in `visibility.py` — then regenerated
  `config/defaults.toml` (`tools/generate_defaults.py --write`) and read the **rendered** lines, not
  the diff, to confirm the warning survives:
  `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`'s rendered comment now ends "...which is the dangerous direction
  since it under-dims a still-dim morning, while a *larger* value only keeps dimming performance
  later into the morning than measured."; `SIGHT_FULL_DARK_SUN_ELEV_DEG`'s now ends "...which is the
  dangerous direction for the no-omniscience goal this feature exists for -- an over-generous floor
  leaves Petrovich reporting a unit no real crewman could see." Neither sentence names the sibling
  tuning key, so `test_tuning_comment_renders.py`'s cross-key check (correctly) stays silent on
  this change. Removed the trailing period inside the `"In real darkness, cannot see anything."`
  quoted fragment (now `"In real darkness, cannot see anything"`) while merging, since a period
  inside a quoted span the generator's `_SENTENCE_SPLIT` regex treats specially was no longer needed
  once the sentence boundary moved past it.
- **Required Fix 2 — `light_factor` had no test proving gate 3 and `tier_ranges()` stay in sync.**
  Added three tests to `test_visibility.py`, right after the existing
  `test_tier_ranges_presence_threshold_uses_the_optic_s_own_cap`: a T-72B (presence threshold
  2333.33 m at `light_factor=(1.0, 1.0, 1.0)`, 233.33 m at `(0.1, 1.0, 1.0)`) placed at 300 m is
  rejected at gate 3 under the shrunk factor (proving gate 3 itself reads the parameter, not just
  `_achieved_tier`'s internal `tier_ranges()` call); the same candidate at 200 m clears gate 3 and
  resolves to a real tier (never the "beyond even lowres" fallback the desync would otherwise force
  it into). Added the review's suggested optional direct `tier_ranges()` test too — it isolates the
  pure-function scaling (presence scaled by its own factor; class/type pulled down to match via the
  existing `min()` chain whenever their own unscaled values would have exceeded it) from gate
  ordering, cheaper to localise if this regresses later.

**Checks re-run after both fixes**: `ruff format --check`/`ruff check` clean on `src`/`tests`;
`cd body-layer && .venv/bin/mypy src` clean (94 source files); targeted run
(`test_visibility.py`, `test_light_level.py`, `test_tuning_comment_renders.py`,
`test_tuning_defaults_toml.py`) 77 passed, 1 xfailed; `.claude/scripts/fast-tests.sh body-layer`
(smoke + 58 targeted files, parallel) 2381 passed, 4 xfailed — no regressions from either fix.

### Stage 4 — wiring the real value into `body.py`'s poll loop

Fast-forwarded onto the Stages 1–3 commit (`0ba18855`), no divergence.

**Mission clock + sun elevation.** `body.ConsolePerceptionRunner` gains five new
per-mission fields (`light_level_last_clock`, `_last_clock_model_time_s`,
`_unavailable_since_wall`, `_error_logged`, `_sun_elevation_deg`), reset on a genuine
mission (re)start like every other per-mission field. `run_once` (guarded on
`self.theatre is not None` — no source is polled otherwise, so the extra `GET
/firing/latest` would be pure waste and would force every aircraft-layer test double in
this subproject to implement a method whose answer is discarded) fetches `get_firing_
latest()` and calls the new `_resolve_sun_elevation_deg(runner, ownship, firing)`:

- A fresh, well-typed `mission_clock` sub-dict (`_parse_mission_clock_dict`) updates the
  cache and clears the unavailable timer/error latch.
- Absent/malformed, with a cached sample still inside `MISSION_CLOCK_MAX_AGE_S` (new
  tunable, `perception.light_level`, default 5.0s): extrapolates `abs_time_s` forward via
  the ownship model-time delta (`ownship.t_sim - light_level_last_clock_model_time_s`) —
  the "between 1 Hz Hook polls" case, not a failure, no log line.
- Never had a sample yet, still within the same `MISSION_CLOCK_MAX_AGE_S` window (answers
  the plan's own "what happens in the first second after load" question — the mission's
  own age, not a separate grace constant): forced to `SIGHT_FULL_DARK_SUN_ELEV_DEG`
  (never daylight — user Q6), silently.
- Beyond that window, or `dcs_to_wgs84` raising `ValueError` for an already-validated
  theatre (should not happen, treated the same as a genuine anomaly): one `logger.error`
  per mission (`light_level_error_logged`, cleared the moment a fresh sample arrives) plus
  the same forced-dark value.

**The cross-optic correctness defect, found while wiring the value, not invented for
this stage.** Stage 3 threaded one `light_factor: tuple[float, float, float]` through
every `tier_ranges()` call in `belief/optic_policy.py`/`attack_run.py`, but several of
those functions compare **two different named optics in one call**
(`improvement_window_m`: `UNAIDED_OPTIC` vs `BINOCULAR_OPTIC`; `least_capable_sufficient_
optic`/`guidance_request_for`: every rung of `_LADDER`) — and `perception.light_level.
light_factor`'s curve is genuinely per-optic (the user's own dawn anchors, Q5: "use
binoculars as long as they can viably see, then 9K113 only..."). A single shared tuple
would dim every optic identically, collapsing exactly the differentiation Stage 2's own
`_MEASURED_FACTORS` table encodes. **Fixed, not deferred**: renamed the threaded parameter
from `light_factor` to `sun_elevation_deg: float | None` throughout `optic_policy.py`/
`attack_run.py` (14 + 1 signatures), and resolve the real per-optic tuple at each
`tier_ranges()` call site via a new `_light_factor_for(optic, sun_elevation_deg)` helper —
`None` stays the true no-op `(1.0, 1.0, 1.0)` for every pre-existing caller/test. This also
resolves Stage 3's own deferred decision on the four bare `can_improve` callbacks
(`sight_can_still_improve`/`_area_or_glass_can_improve`): their five call sites now wrap
them in a `lambda t: fn(t, sun_elevation_deg=sun_elevation_deg)` closure instead of
leaving them at their keyword-only default.

`NakedEyePerceptionSource.light_factor` is assigned in `body._apply_active_gaze`, *after*
`decide_optic` has already chosen this poll's optic (`optic_decision.optic`) — the factor
is computed against that specific optic, not a value threaded in from further up, so the
two can never disagree about which optic a factor belongs to. `crew_console.
drain_attack_run`/`belief.attack_run.decide` gained the same `sun_elevation_deg` keyword,
threaded from `runner.light_level_sun_elevation_deg` (cached on the runner since
`drain_attack_run` runs later in the poll loop, after `run_once` has already returned).

**Test fixture fallout.** `test_body.py`'s `FakeConsoleAircraftClient.get_firing_latest`
needed a `mission_clock` key (a fixed solar-noon 2020-06-01 sample) added — without it,
every naked-eye-detection test driven through the real poll loop with a resolved theatre
went dark (the designed Stage 4 behaviour correctly firing against a fixture nobody had
anticipated). Five `spy_drain_attack_run`-shaped test doubles needed the new keyword
added to their own signatures (mechanical, not a logic change).

### Stage 5 — `EmitterKind.LAUNCH_FLASH`

`aircraft-layer/src/collector/firing_receiver.py`'s `EmitterTracker._apply()` gains a
branch for `S_EVENT_SHOT` (missiles and rockets alike, per the user's own "treat missile
and rocket launch similarly"): opens/refreshes a `LAUNCH_FLASH` entry at the initiator's
own name, `expires_at_sim = now + LAUNCH_FLASH_DURATION_S` (new constant, 4.0s default —
**a plain module constant, not a body-layer `tuning.*` entry**, departing from the plan's
own "Behaviour constants" section, which named it `perception.emitters.
LAUNCH_FLASH_DURATION_S` — see Notable Discoveries). Never overwrites an existing
`FIRING` entry for the same unit (a sustained gun engagement should not go dark early
because the same unit also launched something); removed by `S_EVENT_DEAD`/`_CRASH`
alongside `FIRING`.

`body-layer/src/perception/emitters.py` gains `EmitterKind.LAUNCH_FLASH` (never
`LAUNCH_SMOKE` — the user's own distinction between the few-second flash and `[[BL-B74]]`'s
longer-lived smoke trail) and `launch_flash_emitters()`, folded into `resolve_emitters()`:
`FIRING` wins over `LAUNCH_FLASH` wins over `BURNING` for wording priority (belt-and-
suspenders over the collector's own non-overwrite rule above). `naked_eye_source.py` gains
`PROVENANCE_EMITTER_LAUNCH_FLASH`, added to the existing `_PROVENANCE_BY_EMITTER_KIND`
dict — the cluster-level fold in `_build_observation` needed no further change, since that
code already reads any kind present in the dict generically. `belief.percept`'s closed
`_EMITTER_KIND_BY_PROVENANCE` mapping gains the matching entry.

### Files Changed (Stages 4–5)
- `body-layer/src/body.py` — `_resolve_sun_elevation_deg`, `_parse_mission_clock_dict`,
  five new `ConsolePerceptionRunner` fields, wiring into `run_once`/`_apply_active_gaze`.
- `body-layer/src/perception/light_level.py` — `MISSION_CLOCK_MAX_AGE_S` tunable; module
  docstring updated ("wired into body.py's poll loop as of Stage 4").
- `body-layer/src/belief/optic_policy.py` — `light_factor` → `sun_elevation_deg` rename
  across 14 signatures, new `_light_factor_for` helper, five `can_improve` closures.
- `body-layer/src/belief/attack_run.py` — same rename on `decide()`.
- `body-layer/src/belief/crew_console.py` — `drain_attack_run` gains `sun_elevation_deg`.
- `body-layer/src/perception/naked_eye_source.py` — `light_factor` field docstring
  updated; `PROVENANCE_EMITTER_LAUNCH_FLASH` + `_PROVENANCE_BY_EMITTER_KIND` entry.
- `body-layer/src/perception/emitters.py` — `EmitterKind.LAUNCH_FLASH`,
  `launch_flash_emitters()`, `resolve_emitters()` three-way merge.
- `body-layer/src/belief/percept.py` — `PROVENANCE_EMITTER_LAUNCH_FLASH` mapping entry.
- `aircraft-layer/src/collector/firing_receiver.py` — `EMITTER_KIND_LAUNCH_FLASH`,
  `LAUNCH_FLASH_DURATION_S`, `_apply()`'s new `S_EVENT_SHOT` branch, death-removal extended.

### Tests Added (Stages 4–5)
- `body-layer/tests/test_body.py` — `TestResolveSunElevationDeg` (8 tests: fresh-clock
  matches a direct `sun_elevation_deg` call, extrapolation between samples, no-theatre,
  within-grace-no-error, beyond-grace-logs-once, logs-once-not-every-poll, recovery clears
  the latch) and `TestParseMissionClockDict` (4 tests).
- `body-layer/tests/test_optic_policy.py` — `TestBlB124SunElevationPerOptic` (2 tests): the
  cross-optic fix proven by showing `improvement_window_m`'s two bounds (unaided vs
  binocular) shrink by *different* ratios at the plan's own −3.5° anchor, and
  `sight_can_still_improve` resolving a real, non-default factor vs. full dark.
- `aircraft-layer/tests/test_firing_receiver.py` — replaced the flipped
  `test_shot_event_does_not_create_an_entry` with four tests: entry creation, fixed-window
  expiry (not watchdog-extended), non-overwrite of an existing `FIRING` entry, death
  removal.
- `body-layer/tests/test_emitters.py` — `launch_flash_emitters()` (4 tests, mirroring
  `firing_emitters`'s own) and `resolve_emitters()` precedence (3 tests: firing-wins,
  launch-flash-wins-over-burning, independent-unit merge).
- `body-layer/tests/test_naked_eye_source.py` — three end-to-end `poll()`-level tests
  (bubble-range admission, firing-precedence, launch-flash-over-burning precedence).
- `body-layer/tests/test_percept.py` — the closed-mapping test for the new provenance.

### Checks (Stages 4–5)
- aircraft-layer: `ruff format --check`/`ruff check` clean; `mypy src` clean (28 source
  files); full suite (`-m "not slow"`) 1065 passed.
- body-layer: `ruff format --check`/`ruff check` clean; `mypy src` clean (94 source files);
  full suite (`-m "not slow"`) 3768 passed, 4 xfailed (up from 3744 before these two
  stages — 24 net new tests, some existing tests gained one new assertion line each).
- `defaults.toml` regenerated after the new `MISSION_CLOCK_MAX_AGE_S` tunable; rendered
  comment read directly (not the diff) to confirm the dangerous-direction warning survived
  the single-long-first-sentence convention.

### Notable Discoveries (Stages 4–5)
- **A real, behaviour-relevant defect in Stage 3's own approved design**, found only once
  a real `sun_elevation_deg` was available to feed it (its own default-no-op tests could
  not have caught it) — see "the cross-optic correctness defect" above. Reported here
  rather than silently worked around, per this role's "say what would make the claim
  false" habit: the falsifying check was `light_factor(UNAIDED_OPTIC, -3.5) !=
  light_factor(BINOCULAR_OPTIC, -3.5)` (confirmed true, both anchors already in Stage 2's
  own `_MEASURED_FACTORS` table), which is now a standing test
  (`test_improvement_window_m_shrinks_each_bound_by_its_own_optics_factor`).
- **`LAUNCH_FLASH_DURATION_S`'s location departs from the plan's own "Behaviour constants"
  section**, which named it `perception.emitters.LAUNCH_FLASH_DURATION_S` (implying a
  body-layer tuning entry). The watchdog duration it actually controls lives entirely in
  aircraft-layer's `EmitterTracker` (the same module that already declares
  `FIRING_MIN_VISIBLE_S`/`FIRING_WATCHDOG_S` as plain constants, since aircraft-layer has
  no `tuning.*` loader — root `CLAUDE.md`'s "Outside body-layer the loader does not exist
  yet" instruction). Declared it there instead, with the same "flagged as a tuning
  candidate" comment those two siblings already carry, rather than inventing a second
  tuning mechanism or a cross-process constant with no consumer.
- **`test_shot_event_does_not_create_an_entry` (aircraft-layer) flipped**, exactly the
  class of test the plan's own "treat the test-impact list as a hypothesis" step warns
  about — not named by the plan (it predates this feature, from `[[BL-B74]]`'s seam), and
  found by `grep`ping `S_EVENT_SHOT` across the test suite before writing the `_apply()`
  branch, not after the fact.
- **`decide_optic`'s own `OpticDecision`/`AttackRunState` plumbing needed no change** —
  only the keyword threading. The five `can_improve` closures are the only control-flow
  change in `optic_policy.py`; everything else is a parameter rename plus a
  `_light_factor_for` call at each existing `tier_ranges()` site.
- **Not flown.** Both stages are code-complete and fully unit/integration-tested against
  fakes; the plan's test card (dawn pass, night light-source row, pilot-seat cockpit mask
  measurement) is the user's own live acceptance step, not run here.

### Review fix round (`plans/bl-b124-light-level/review-stages-4-5.md`, APPROVED WITH MINOR FIXES)

**Required Fix 1 — a frozen `mission_clock` feed read as fresh forever.** `_resolve_sun_
elevation_deg` (`body.py`) treated any poll where `GET /firing/latest`'s `mission_clock`
sub-dict *parsed* as "fresh," resetting `light_level_unavailable_since_wall` to `None` and
`light_level_error_logged` to `False` every time — but aircraft-layer's `EmitterTracker.
snapshot()` keeps serving its last-ingested `MissionClockSample` verbatim once the Hook/
collector feed dies, with no mechanism to distinguish "a new sample just arrived" from "this
is the same cached sample as five minutes ago." The fix is one line: a sample now counts as
fresh only when it **differs** from `runner.light_level_last_clock`
(`if fresh is not None and fresh != runner.light_level_last_clock:`). A repeated or absent
sample now falls into the existing "unavailable" branch identically, so the pre-existing
grace-window/one-shot-error machinery (unchanged) now actually reaches the dead-feed case it
was built for; extrapolation also keeps advancing correctly through a run of repeats, because
`light_level_last_clock_model_time_s` no longer gets wrongly re-anchored to the current
`t_sim` on every repeat (it previously froze the resolved elevation at the frozen sample's own
value for as long as the repeats continued, rather than extrapolating forward from the last
genuinely new sample).

Both the function's own docstring and the `light_level_unavailable_since_wall` field comment
were updated in place to state the new "differs from the stored sample" condition — the old
wording ("a fresh `mission_clock` sample this poll... clears the unavailable-since timer")
was the exact premise the defect lived under, so it had to change, not just the code beside it.

**Grace window stays wall-clock, not sim-time (the review's Optional Refinement 2).**
Considered switching `MISSION_CLOCK_MAX_AGE_S`'s timer to sim-time (`ownship.t_sim` deltas)
instead of `time.monotonic()`, which would also silence the "paused mission" false-positive
the review names — but the review's own stated reasoning for keeping it wall-clock is sound
independently of that: the Hook polls `GET /firing/latest` on its own 1 Hz *wall-clock*
cadence regardless of DCS pause state, so wall time is the correct unit to bound *its*
responsiveness against, not the mission's sim clock. Switching to sim-time would also have
required reworking the four pre-existing tests that set `light_level_unavailable_since_wall`
directly via `time.monotonic() - (MISSION_CLOCK_MAX_AGE_S + 1.0)` (`test_unreadable_past_the_
grace_window_is_a_logged_error` and its three neighbours) — modifying existing tests without
explicit permission, for a change the review itself flagged only as a live-test-card item
("the test card's dawn pass includes a deliberate pause"), not a required fix. Left as
wall-clock; the paused-mission scenario remains a known, accepted gap to be checked live, per
the review's own recommendation, not guarded in the unit suite.

**Tests added** (`body-layer/tests/test_body.py`, `TestResolveSunElevationDeg`):
- `test_a_frozen_feed_serving_the_same_dict_forces_dark_and_logs` — feeds the identical
  `mission_clock` dict across ownship samples spanning ~57 minutes of advancing `t_sim`
  (mirroring the review's own reproduction), then pushes the wall-clock unavailable-since
  timestamp past `MISSION_CLOCK_MAX_AGE_S` and confirms forced full dark + the one-shot
  `ERROR` log fires — the exact scenario the review reproduced directly against the live
  function.
- `test_repeated_identical_sample_does_not_reset_the_unavailable_timer` — the narrower,
  mutation-sensitive claim: a second repeat of the same dict must not re-clear
  `light_level_unavailable_since_wall` back to `None`.
- `test_extrapolation_keeps_advancing_through_a_run_of_repeated_samples` — one repeat
  followed by an absent sample must still extrapolate from the *original* genuinely-new
  sample's capture time, not from the repeat's (wrongly re-anchored) one.

**Verified by mutation, not by reading.** Reverted the guard from `fresh is not None and
fresh != runner.light_level_last_clock` back to the pre-fix `fresh is not None`
(`shasum` before: `1f9670f3936415f6fa7d0eb9c01bc3f0f74535a8`); all three new tests failed
immediately (the extrapolation one with a direct numeric mismatch, `75.940... != 75.933...`,
the two guard tests on the `is None`/equality assertions), while all seven pre-existing
`TestResolveSunElevationDeg` tests kept passing under the mutation — confirming the new tests
are the ones actually exercising the fix, not duplicating existing coverage. Restored the
fix; `shasum` after matched the pre-mutation value exactly, confirming the restore was exact.

**Checks (this round):** `cd body-layer && ruff format --check src tests` clean;
`ruff check src tests` clean; `.venv/bin/mypy src` clean (94 source files, run via the real
`body-layer/.venv` since this worktree carries no `.venv` of its own); smoke
(`pytest tests --collect-only`) 3803 tests collected; `pytest tests/test_body.py -m "not
slow"` 251 passed; full body-layer suite (`pytest -m "not slow" -n auto`) 3772 passed,
4 xfailed (up from the review's own 3769 passed, 4 xfailed — the 3 new tests). No tunable
changed, so `config/defaults.toml` was not regenerated (confirmed via `git diff --stat
config/defaults.toml src/tuning.py`, empty).

## `[[BL-B137]]` fix — `mission_clock` NaN/Infinity no longer silently forces full daylight
(2026-11-25)

The security deep analysis's one non-blocking finding (`security.md` Finding 1), closed the
same day on `feature/bl-b124-light-level` rather than left for later: `MissionClockSample.
from_wire`'s `float(abs_str)` parsed `"nan"`/`"inf"`/`"-inf"` without raising, and the value
propagated through `sun_elevation_deg`'s formula to a clean `90.0` deg (full daylight) at the
`max(-1.0, min(1.0, nan))` clamp — the one outcome this feature's own design (user Q6: "error
if not readable") forbids, and silently: `_resolve_sun_elevation_deg`'s "fresh only if it
differs" guard (this plan's own earlier Required Fix) is defeated by `nan != nan` being `True`
in Python, so the malformed sample read as "fresh" on every poll and never reached the
staleness/error path that would log it.

**Fix, both ends named in the finding:**

1. **`aircraft-layer/src/schema/firing.py`, `MissionClockSample.from_wire`** — added
   `math.isfinite(abs_time_s)` to the success condition, raising `FiringParseError` otherwise
   (same posture as the existing `ValueError` path for a non-numeric field).
   `FiringEventBatch.from_wire`'s existing `except FiringParseError: mission_clock = None`
   already drops this to "unavailable" without failing the rest of the batch — no change
   needed there.
2. **Body-layer, two independent layers** (the finding's own "treat a non-finite input or
   result as unavailable" framing, not just the wire fix) — `abs_time_s` is also reachable via
   a value `_resolve_sun_elevation_deg` extrapolates fresh every poll
   (`abs_time_s0 + (ownship.t_sim - model_time_at_capture)`), which never passes back through
   the wire parser above:
   - `body._parse_mission_clock_dict` now checks `math.isfinite(abs_time_s)` alongside its
     existing `isinstance` checks, rejecting a non-finite value to `None` the same way a
     wrong-typed one already is.
   - `perception.light_level.sun_elevation_deg` itself now raises `ValueError` on a non-finite
     `abs_time_s` at entry, and again on a non-finite `sin_altitude` intermediate — checked
     *before* the clamp that was silently resolving it, not after. `_resolve_sun_elevation_deg`
     wraps its call to `_compute_sun_elevation_deg` in `try`/`except ValueError`, falling
     through to the same beyond-grace path the pre-existing `dcs_to_wgs84` `ValueError` catch
     already used — forced full dark, one-shot logged `ERROR`, never a silent daylight value.

**Tests added:**
- `aircraft-layer/tests/test_firing_schema.py` — `TestMissionClockSample.
  test_non_finite_abs_time_s_raises` (parametrized over `"nan"`/`"inf"`/`"-inf"`/`"Infinity"`)
  and `test_non_finite_abs_time_s_is_dropped_not_raised_at_batch_level` (the
  `FiringEventBatch`-level drop-without-failing-the-batch posture).
- `body-layer/tests/test_light_level.py` — `TestSunElevationDeg.
  test_non_finite_abs_time_s_raises` (parametrized over NaN/±Infinity) and
  `test_without_the_guard_nan_silently_resolves_to_full_daylight`, which runs the bare
  `max(-1.0, min(1.0, nan))` clamp directly (not this module's code) to demonstrate the exact
  failure mode the guard pre-empts is real, not a defensive-programming reflex.
- `body-layer/tests/test_body.py` — `TestResolveSunElevationDeg.
  test_non_finite_mission_clock_never_resolves_to_daylight` (end to end, via `GET
  /firing/latest`'s dict shape) and `test_a_corrupted_stored_clock_falls_back_to_dark_not_
  daylight` (constructs a non-finite `runner.light_level_last_clock` directly, bypassing
  `_parse_mission_clock_dict`'s own guard, to isolate and prove the second-layer `try`/`except`
  around `_compute_sun_elevation_deg` is itself load-bearing); `TestParseMissionClockDict.
  test_non_finite_abs_time_s_is_rejected` (parametrized).

**Checks:** `aircraft-layer` — `ruff format --check src tests` clean (one file reformatted
by `ruff format` after the edit, re-verified clean), `ruff check src tests` clean,
`.venv/bin/mypy src` clean (28 source files), `pytest tests -q` 1070 passed.
`body-layer` — `ruff format --check src tests` clean (two test files reformatted after the
edit, re-verified clean), `ruff check src tests` clean, `.venv/bin/mypy src` clean (94 source
files), `pytest tests/test_light_level.py tests/test_body.py -q` 274 passed,
`pytest tests -q` (full suite, deselecting the one known-at-baseline-broken test) 3803
passed / 4 xfailed / 1 deselected — the 5 `test_bl_b104_scenario_mock_flights.py` failures
(`look_direction` → `HTTP Error 501: Unsupported method ('POST')`, `tests/support/
mock_aircraft_layer.MockAircraftLayerServer` has no `do_POST`) reproduce identically against
the unmodified `4525ebcd` baseline, checked in a disposable worktree — pre-existing, unrelated
to this change.

**Mutation proof, actually run** (not asserted from reading) — each guard removed with
`Edit`, tests re-run, red confirmed for the stated reason, guard restored, `shasum`
before/after matched exactly:
- `MissionClockSample.from_wire`'s `math.isfinite` check removed →
  `test_non_finite_abs_time_s_raises` (all four parametrizations) and
  `test_non_finite_abs_time_s_is_dropped_not_raised_at_batch_level` fail (NaN/Infinity parse
  through to a real `MissionClockSample` instead of raising `FiringParseError`). Restored;
  `firing.py`'s `shasum` matched.
- `sun_elevation_deg`'s two guards (the entry-point `abs_time_s` check and the pre-clamp
  `sin_altitude` check) removed together → `test_non_finite_abs_time_s_raises[nan]` fails
  (`DID_NOT_RAISE`), but **the `inf`/`-inf` parametrizations still pass** — not because any
  guard caught them, but because `math.sin`/`math.cos` on an infinite argument already raises
  Python's own `ValueError: math domain error` before either guard would fire. **NaN is the
  one value neither Python's own arithmetic nor the pre-existing code ever caught** — matching
  the security finding's own emphasis on `nan != nan` as the specific defeat mechanism, not
  Infinity. Restoring only the entry-point check (leaving the `sin_altitude` check removed)
  made all three parametrizations pass again, confirming the entry-point check alone is what
  is load-bearing for this test; the `sin_altitude` check is a second, deliberately redundant
  layer for an intermediate going non-finite by some other path than a non-finite `abs_time_s`
  (none identified, but cheap to keep). Restored both; `light_level.py`'s `shasum` matched.
- `_resolve_sun_elevation_deg`'s `try`/`except ValueError` around `_compute_sun_elevation_deg`
  removed → `test_a_corrupted_stored_clock_falls_back_to_dark_not_daylight` fails by raising
  `ValueError` out of `_resolve_sun_elevation_deg` instead of returning
  `SIGHT_FULL_DARK_SUN_ELEV_DEG` (`test_non_finite_mission_clock_never_resolves_to_daylight`
  stays green under this same mutation — it never reaches `_compute_sun_elevation_deg` at all,
  because `_parse_mission_clock_dict` already rejected the NaN upstream, which is itself a
  useful confirmation that the two body-layer guards are independent, not duplicate coverage
  of the same path). Restored; `body.py`'s `shasum` matched.

`body-layer/ROADMAP/BL-B137.md` marked `[x]`/`#status/closed`; `body-layer/ROADMAP/
body-layer-backlog.md`'s index line annotated done. `[[BL-B135]]`'s own entry already
cross-links `BL-B137` by id and needed no change.
