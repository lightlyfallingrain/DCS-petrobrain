---
name: emitter-visibility-stage-b-firing
description: BL-B73/AC-B8 (gun-fire emitter visibility) -- cross-Hook Lua state sharing for the 128-cap splice, closed-mapping for a second bit (targets_ownship), universal FakeAircraftClient breakage from an unconditional new call site
metadata:
  type: project
---

Built Stage B of `plans/emitter-visibility/plan.md` (`BL-B73` gun-fire visibility, `AC-B8` the
firing-event transport) on `feature/emitter-events`. Worth remembering:

**A new unconditional call site in a shared perception source breaks every `FakeAircraftClient`
duplicate in the test suite, not just the ones testing the new feature.** Adding
`self.aircraft_client.get_firing_latest()` (no try/except guard around the call itself, though the
*result* is still independently-degradable) to `NakedEyePerceptionSource.poll()` broke 60 tests
across five separate files (`test_naked_eye_source.py`, `test_detection_trace.py`,
`test_emission_pipeline.py`, `test_player_bubble.py`, `test_logger.py`) — each has its own
hand-duplicated `FakeAircraftClient`/`FakeConsoleAircraftClient`, not a shared fixture, and none of
them had the new method. Caught by running the **full** suite immediately after the change, not
just the new tests — this project's own `verify_full_suite_not_just_new_files` lesson, reconfirmed.
Fix: add `get_firing_latest` returning a well-formed "nobody firing" default to every duplicate,
matching the real `AircraftLayerClient.get_firing_latest`'s own "never `None`" contract.

**Two Hook scripts sharing one `"scripting"`-state global needs no new transport.** The 128-
sightline-cap mitigation (splice currently-firing units ahead of the nearest-first sort) could have
been built as a collector round trip (collector learns who's firing from `EmitterTracker`, pushes a
list back to the LOS Hook's own inbound listener, mirroring `LookDirectionSender`). Instead: the
firing-events Hook's own event handler writes `PB_ACTIVE_FIRING_UNITS[name] = true/nil` directly, in
real time, as a plain global in the mission-scripting state — and the LOS Hook's own `dostring_in`
call just reads it (`PB_ACTIVE_FIRING_UNITS or {}`) inside its own snippet, since both Hooks'
`dostring_in` calls target the same `"scripting"` state and that state's globals persist across
calls (`petrobrain-f10-commands-hook.lua`'s `PB_F10_QUEUE` already proves this). Zero round-trip
latency, zero new wire format. Worth checking for this pattern before reaching for a new channel
whenever two Hook scripts both touch the mission-scripting state.

**A second bit crossing the perception/belief boundary needs its own closed set, not a widened
kind-mapping.** Stage A's review established `Percept.emitter_kind` via `_EMITTER_KIND_BY_PROVENANCE`
rather than letting `Observation.provenance` cross wholesale. Stage B needed a *second* independent
fact (`targets_ownship`) to cross for the same `FIRING` kind. Folding it into a fourth `EmitterKind`
value ("firing at us" as its own kind) would have been a fabricated taxonomy — the kind is the same,
only the target differs. Instead: two `PROVENANCE_EMITTER_FIRING*` constants both map to the same
`EmitterKind.FIRING.value` via the existing dict, and a second, independent `frozenset`
(`_TARGETS_OWNSHIP_PROVENANCE`) answers the second question. Generalizes: when a closed-mapping
pattern needs to carry a second orthogonal fact, add a second closed mapping rather than widening
the first one's range.

**`luac5.1 -p` fails on every Hook script's header comment in this codebase, not just new ones** —
the `--[[ ... --]]` block comments use `[[ID]]` link markup (e.g. `` `[[BL-B72]]` ``), and Lua 5.1's
nested-long-bracket deprecation trips on the inner `[[`. Confirmed this is pre-existing and harmless
by running `luac5.1 -p` against `petrobrain-mission-telemetry-hook.lua` *unmodified* and getting the
identical error — so a new Hook script failing the same way is not a regression. Verify a new Hook
script by stripping the header (`awk '/^--\]\]$/{found=1; next} found'`) and compiling the body, plus
extracting each `dostring_in` snippet string and compiling it separately.

See [[feedback_lua_dostring_in_snippet_must_be_self_contained]] (still the right check: every helper
in the new `EVENT_REGISTER_CODE` snippet is defined inside the string, not as a Hook-local function)
and [[verify_full_suite_not_just_new_files]].
