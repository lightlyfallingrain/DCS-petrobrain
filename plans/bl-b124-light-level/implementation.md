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
