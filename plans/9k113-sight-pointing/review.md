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
