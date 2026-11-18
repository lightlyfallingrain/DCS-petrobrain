# Review — BL-16 mode 1, Stage M1 ("the seam and handover")

Branch `feature/bl16-raw-axes`, HEAD `cdfdc20eb8bcb26658672e931d2732e96f800e99` (matched the
expected sha exactly; no merge was needed, tree clean).

Reviewed against: `plans/flight-control/plan.md` "Revised 2026-11-18 — mode 1 (unparked, raw
axes) re-cut" (M0–M5, including the "Amended 2026-11-18" U5–U10/seat-rule subsection, Decisions
21–25); `plans/flight-control/alignment.md`'s 2026-11-18 entries (both ALIGNED); and
`plans/flight-control/implementation.md`'s "Mode 1, Stage M1" account, checked against the code
rather than trusted.

### Review Summary

Stage M1 (the seam, handover, and the axes-mode dispatch/clamp/readback bodies — the control law
itself is Stage M2, not built here) is well-executed against an unusually precise plan: the
Lua/Python wire shape, the `_by_mode` dispatch combinator, the handover state machine (Decision
22/24), Decision 25's seat-independence, the AC-B14 double-validation, and the tuning/`defaults.toml`
pattern are all built as specified and pass every mechanical check (`ruff format/check`, `mypy
--strict`, `luac5.1 -p`, the `GETGLOBAL` audit, the targeted `-k flight` test runs in both
subprojects, and a read of the rendered `defaults.toml`).

Two things need fixing before this can merge, plus one sequencing dependency on a sibling branch:

1. **A stale-goal leak across a release → re-take cycle**, contradicting the plan's own stated
   guarantee that `held_*` fields are `None` until Lua's first `active` status after a take.
2. **Decision 13's own test ("at every confidence") is missing** — the plan's M1 Tests list names
   it explicitly; it is not present anywhere in the diff.
3. A dependency note on the measured seat-swap park-edge blip (flight 8) — see below. M1's own
   code is clean on this point; it is a merge-sequencing issue, not a fix M1 itself owes.

## Dependency: the measured seat-swap park-edge blip (flight 8) — M1's own code is clean

**Measured, flight 8** (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`,
branch `probe/bl16-flight-axes`): on a pilot → operator seat swap with the copilot controls
unparked, the camera reaches the operator seat while arg 852 still reads 0.963 (stowed), and 852
then animates down over ~0.3 s, so `ai_pilot_parked_active` reads `true` for 3 frames (24 ms)
before it clears — exactly the case M0-I's own pass criterion and the plan's own named Risk
describe. The user's decision (2026-11-18, recorded in `plans/flight-control/plan.md` on branch
`8685fc67`, under Decision 25): after a camera seat change, `parked_active` holds its previous
value for a ~0.5 s settle delay before being evaluated; under DCS's automatic AI-handover setting
a swap into the copilot seat with stowed controls is then a genuine park edge. That fix is landing
separately, **on main**, in `ai_pilot_wheel.lua` where `ai_pilot_parked_active` is itself computed
(branch `fix/apw-seat-swap-settle`) — so mode 2 gets it immediately and mode 1 inherits it once
this branch rebases onto (or merges after) that fix.

**M1's own obligation was only to read parked state exclusively through `ai_pilot_wheel.is_parked()`/
`ai_pilot_parked_active`, never re-deriving it from arg 852 or the camera seat directly — confirmed
by reading the code.** `flight_control.lua` contains no reference to `852` anywhere (`grep -n "852"
aircraft-layer/dcs-export/Petrobrain/flight_control.lua` is empty) and calls `ai_pilot_wheel.
is_parked()` as its one source for `is_parked` (line 502); it is never derived a second way. On the
body-layer side, `decide_flight_control`'s `parked_active` parameter is threaded from `runner.
parked_flight_state.parked_active`, itself `advance_parked_flight_state`'s mirror of the
`apw_parked_active` wire field `ai_pilot_wheel.lua` already pushes — again, no independent
re-derivation. **No Required Fix follows from this for M1's own code.** The one action item is
sequencing: this branch should not merge ahead of (or should rebase onto) `fix/apw-seat-swap-settle`
landing on main, since until then M1 inherits the same measured blip mode 2 does — and, unlike mode
2 (which happens to self-heal because its own takeover-sequence pacing delays are both 0.5 s, longer
than the 24 ms blip), M1's self-arm and refused-unpark-take complete synchronously, inside the blip
itself, with no equivalent incidental protection. That is the debounce fix's job to close, not
M1's.

## Required Fixes

### 1. Stale `fc_goal_*`/`held_*` leak across a release → re-take cycle

The plan states, for axes mode: *"the `held_*` fields come from Lua's reported goal values. They
are `None` until Lua's first `active` status, so the per-parameter gates HOLD through the takeover
window."* This is false for any session after the first: `handle_flight_control_command`'s
`"release"` branch (`flight_control.lua`) clears `fc_mode`/`fc_captured`/`fc_release_reason` but
**never** clears `fc_goal_heading_deg`/`fc_goal_turn`/`fc_goal_alt_m`/`fc_goal_alt_ref`/
`fc_goal_ias_kmh`; neither does a fresh `"take"`. `push_flight_control_state` keeps echoing the
stale values regardless of `fc_mode`, so `advance_flight_control_state` mirrors them into
`FlightControlState.held_*` on the very next poll, and `current_crew_state()` treats `phase ==
"TAKING"` as already "flying axes" (`flying_axes = phase in ("TAKING", "ACTIVE")`) — so a command
issued in the brief `TAKING` window, or `ACTIVE` before any fresh goal is ever spoken, reads the
*previous session's* heading/altitude/speed goal as "held", not `None`.

Concretely: this defeats `rules/gates.py`'s own HOLD-until-known safety window
(`_flight_control_heading`/`_flight_control_altitude`/`_flight_control_speed` pass immediately on a
stale non-`None` value instead of holding for a real one), and it means a relative command spoken
early in a *new* activation (`turn left 30`, `climb 50`) computes against the heading/altitude from
the *previous* handover, not the current flight — Flight M-A's own script exercises multiple
take/release cycles (steps 1–2, 6–9, 11) where this is live.

Not tested anywhere in the diff — no test in `test_flight_control.py`, `test_flight_control_lua.py`
or `test_body_flight_control.py` releases and re-takes within the same simulated session to check
`held_*`/`fc_goal_*` read back `None`.

**Fix**: clear `fc_goal_heading_deg`/`fc_goal_turn`/`fc_goal_alt_m`/`fc_goal_alt_ref`/
`fc_goal_ias_kmh` in the `"release"` branch (matching what `on_stop` already does for a mission
restart), and add the release→re-take test.

### 2. Decision 13's own test ("at every confidence") is missing

The plan's M1 Tests list names it explicitly: *"Decision 13 at every confidence."* `voice_commands.
classify_response`'s `HANDOVER_TOKENS` branch (confirmed correct by reading it: `i_have_controls`
acts at any confidence, `you_have_controls` acts from `CONFIRM_FLOOR` up else "say again", the
ambiguous pair releases while flying else "say again", neither ever answers "confirm?") has **no
test anywhere in this diff** — `test_voice_commands.py` is untouched by this branch (confirmed:
`git diff f06c53fb..HEAD -- tests/test_voice_commands.py` is empty), and the only tests naming
`HANDOVER_TOKENS`/the two tokens (`test_rules_flight_actions.py`) dispatch through
`CrewConsole.handle_command` directly, bypassing `classify_response`'s own floor logic entirely.

The behaviour itself reads correct from the code; this is a coverage gap against the plan's own
named test, not a known behaviour defect — but it is exactly the kind of gap `implementation.md`'s
own "Tests Added" section should have surfaced and did not.

## Optional Refinements

- **`MIN_IAS_KMH`/`MAX_IAS_KMH` have an unguarded cross-key ordering invariant.** The Implementer's
  own stated reasoning ("their `lo`/`hi` ranges... cannot cross invert it via any single in-bounds
  override") is correct as far as it goes (a *single*-key override is always safe given the current
  defaults) but understates the gap: *two* simultaneous overrides — `MIN_IAS_KMH` near its own `hi`
  (200) and `MAX_IAS_KMH` near its own `lo` (100) — invert the ordering with nothing to catch it.
  `clamp_speed`'s `max(MIN, min(MAX, kmh))` would then silently collapse to always returning `MIN`,
  regardless of `kmh`. Non-crashing, requires a deliberate two-key misconfiguration, flagged for
  review as the project's own tuning convention asks — worth a guard in the style of `tuning.
  _check_scan_decay_coupling` at some point, not blocking this merge.
- **The unpark-take's failed-capture fallback (`capture_from_seat("pilot")` returning `nil`) maps to
  `fc_refuse_cause = "on_ground"`.** This is a defensible fail-closed default (there is no cause for
  "an axis arg read NaN" on the wire), but the name is a mismatch — it has nothing to do with AGL.
  Consider either a dedicated cause or a one-line comment at that call site making the mapping's
  reasoning as explicit as `check_unpark_preconditions`'s own comment already is for its two causes.

## Confirmed sound (no action needed)

- **`FC_AXES_ENABLED.collective = false`** despite the sign/scale now being measured (flight 6) is
  consistent with the bar pedal was held to (sign **and** scale **and** step-response lag, not sign/
  scale alone) — approved as the right reading, not a looser one smuggled in.
- **The M1/M2 boundary for the ten `axes_*` goal actions** (M1 builds dispatch/clamp/send/readback;
  M2 makes the commanded values actually get flown toward) is a reasonable resolution of the plan's
  genuinely overlapping M1/M2 bullets, and it is tested (`tools/check_rules.py`'s "axes flying"
  scenario dry-runs all ten).
- **`wire_seq` vs. `take_seq`** — the split was necessary (the plan's literal `goal_seq` wording
  would have collided a goal-scoped counter with the message-level staleness check); well-documented
  in both the module docstring and `STRUCTURE.md`.
- **`ai_pilot_wheel.lua`'s own double-quote bug (`text_or_null` wrapping an already-quoted
  `json_escape_string` result)** is confirmed **not repeated** in `flight_control.lua`'s own
  `text_or_null` (returns `json_escape_string(value)` directly) — read the actual function, not just
  the claim.
- **No seat gate anywhere** (Decision 25): confirmed by reading `take_controls`'s refusal chain,
  `flight_mode()`, `rules/gates.py`'s flight categories, and the Lua capture-seat resolution — none
  reads a seat to decide *whether* mode 1 runs, only *which* arg set to read on a voice take.
  `TestSeatNeverGatesMode1` pins this with a differential test.
- **No LAN message carries a raw axis value** — confirmed by reading
  `AircraftLayerClient.write_flight_control`'s and `CommandSender.send_flight_control`'s own
  signatures (`seq`/`cmd`/`limits`/`goal` only) and the API-side shape validation.
- **Rendered `config/defaults.toml` read**, not just the `#:` source comments: all eight new
  `[belief.flight_control]` entries render correctly, first sentences are self-contained, and
  `MAX_IAS_KMH`'s comment no longer mentions `FLOOR_AGL_M` (the cross-reference
  `test_tuning_comment_renders.py` caught and the Implementer fixed).
- **`GETGLOBAL` audit** on `flight_control.lua`/`ai_pilot_wheel.lua`/`commands.lua`/`Export.lua`: every
  name is stdlib, a genuine DCS API, or a module-level global set up elsewhere — no own helper
  referenced ahead of its own `local`.

## Checks run

- `ruff format --check` / `ruff check` — both subprojects: pass.
- `mypy src` (from inside each subproject) — both subprojects: pass, 0 issues.
- `luac5.1 -p` on every touched `.lua` file: pass.
- `pytest -k flight` — aircraft-layer: 52 passed; body-layer: 129 passed (both green, no skips).
- Did not re-run the full suites (DoD's own job per root `CLAUDE.md` "Verification"); the targeted
  runs above cover every file this branch touches.

## Verdict

**NEEDS REVISION** — Required Fix 1 contradicts a guarantee the plan states explicitly and is
untested, and Required Fix 2 is a plan-mandated test that does not exist. Neither looks
architecturally hard to close; recommend routing back through Implementer → Reviewer per
`AGENTS.md`'s normal loop. Separately, **merge should wait for (or this branch should rebase onto)
`fix/apw-seat-swap-settle` landing on main** — not a fix M1 owes, but a real exposure until that
lands (see "Dependency" above).

## Review Confidence

Full read of the plan section, both alignment entries, `implementation.md`, the complete
`flight_control.lua` module, `belief/flight_control.py`, the relevant `crew_console.py`/`body.py`
call sites, `rules/actions.py`, `rules/gates.py`, `config/rules/flight.lua`,
`schema/flight_control.py`, and the API-side validation in `aircraft-layer/src/api/server.py`.
Test files were checked by class/test-name inventory plus targeted full reads
(`test_body_flight_control.py` in full; `test_flight_control.py`/`test_flight_control_lua.py`/
`test_rules_flight_actions.py` by structure plus the specific assertions discussed above), not
line-by-line for every assertion in the larger files (538/567 lines) — the mechanical checks
(mypy/ruff/luac/targeted pytest) cover what a full read would otherwise catch mechanically.
