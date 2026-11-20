# Review: BL-16 sortie-1120 bug-fix batch

Reviewed branch `fix/bl16-sortie-1120`, tip `222e5328` (checked out as `review/sortie-1120`,
`git rev-parse HEAD` confirmed `222e5328`), against base `98174b54`. This batch was partially
merged to `main` ahead of review for flight testing (per user direction); this review is the gate
for the whole batch, all seven items.

Scope reviewed: `git diff 98174b54..222e5328` (42 files, ~5000 lines) across
`aircraft-layer/dcs-export/`, `aircraft-layer/src/`, `body-layer/src/`, their respective test
suites, `body-layer/config/defaults.toml`, `plans/flight-control/{debug,implementation,plan}.md`,
`docs/acceptance/2026-11-20-sortie-feedback.md`, `aircraft-layer/research/2026-11-20-slip-ball-recon.md`.

`plans/flight-control/plan.md` has no `U<n>` decision ids in the sections this batch touches
(Decisions 13, 22-32, F-P7 use "Decision N" numbering, not `U<n>`) — ran
`.claude/scripts/accepted-items-ledger.sh plans/flight-control` anyway; it reports only the
unrelated `U1`/`U2`/`U3` placeholders elsewhere in the plan as unanswered, nothing to ledger for
this batch. Read Decisions 13, 22-32 and F-P7 by hand instead, cross-referenced against
`debug.md`/`implementation.md`'s own citations of each: all are either implemented as decided
(F-P7/Decision 32's "latest wins" rework, Decision 27's turn-rate-pedal shape, Decision 30's
`collective_limited` widening) or correctly left untouched because out of this batch's scope
(Decision 29 break-height-budget, Decision 31 VRS, Decision 13 handover-token mechanics).

## Checks run (this session, independently — not just trusted from the docs)

**aircraft-layer** (worktree has no own `.venv`; used `/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`):
- `ruff format --check src tests` — pass (86 files).
- `ruff check src tests` — pass.
- `mypy src` (from `aircraft-layer/`) — pass, 28 files.
- `luac5.1 -p` on `Export.lua`, `ai_pilot_wheel.lua`, `commands.lua`, `core.lua`,
  `flight_control.lua` — all pass.
- `luac5.1 -l -p | grep GETGLOBAL` on all five touched Lua files — every name a genuine Lua
  stdlib/DCS API or an already-intentional cross-module table (`ai_pilot_wheel`, `flight_control`,
  `client`, `debug_log`, `safe_call`, `extract_json_*`, `fmt_*_or_null`, `json_escape_string`). No
  stray global from any new local in this batch.
- `pytest tests -q -p xdist -n auto` — **1046 passed**.

**body-layer** (used `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`):
- `ruff format --check src tests` — pass (228 files).
- `ruff check src tests` — pass.
- `mypy src` (from `body-layer/`) — pass, 92 files.
- `pytest tests -q -p xdist -n auto` — **3729 passed, 4 xfailed** (pre-existing, unrelated), 0
  failed, 148.6s.

All figures match what `implementation.md`/`debug.md` report for the same commands; independently
reproduced here, not merely read off the docs.

## Item-by-item (checks (a)-(g) from the brief)

**(a) Item 3 — 0.5 tolerance hunting risk.** Read `ai_pilot_wheel.lua` directly
(`AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M`/`AI_PILOT_HEADING_TOLERANCE_DEG`, lines ~112-216, and the
tick functions `ai_pilot_goal_tick_altitude`/`ai_pilot_goal_tick_heading`, ~961-1019). This is not
a bare `abs(diff) <= 0.5` threshold with nothing else: the hold is continuous (the AI-wheel button
is held, not pulsed) and the direction decision (`ai_pilot_correction_direction`/`ai_pilot_goal_heading_direction`)
is re-evaluated every tick, switching direction *immediately* the instant the needed direction
flips, with no release-and-repress delay. The comments honestly flag the one real unverified
assumption underneath this (every observed overlay reading has been a bare integer, so 0.5 is
being treated as "exactly the nearest whole unit" — not independently re-confirmed with a
fractional-reading screenshot) and independently derive a bound on per-tick movement (~2-3 units
at the 5 Hz poll rate from `HelperAI.lua`'s own ramp constants) to argue the redirect-on-overshoot
behaviour converges rather than hunts forever. This is a reasoned, tested design, not an
oversight — **optional**: worth a specific live-flight watch for oscillation at the exact 0.5 band
the next time mode 2's goal convergence is flown, since the integer-display assumption is the one
unverified input the whole argument rests on.

**(b) Item 2 — ordering/latest-wins.** Read `body.py`/`belief/ai_pilot_wheel.py`'s
`command_order_seq`/`cbtm_action_order`/`heading_requested_order` mechanism and
`ai_pilot_wheel.lua`'s `handle_ai_pilot_goal_command` directly. The design correctly separates "a
goal commanded *before* a break" (dropped, `heading_requested_order is None or < cbtm_action_order`)
from "a goal commanded *during or after* a break" (ends the CBTM episode and flies at once,
including dropping `break_away`'s own pending second press via the same
`ai_wheel_cbtm_pending_release_t` release both code paths already share). `debug.md` documents
explicit mutation testing for this exact mechanism — tests reverted to the pre-fix behaviour on
both the body-layer (`heading_predates_break` forced to `True`) and Lua (`elseif` branch removed)
sides, confirmed red, then restored byte-for-byte (`shasum`-verified) — which is exactly the
standard this role is supposed to hold work to. No required fix.

**(c) Item 4 — collective sign/scale, RPM/stall caps, pedal stacking.** Confirmed
`FC_AXES_ENABLED.collective = true` is read by every per-axis loop (`capture_from_seat`,
`axis_magnitude`, `write_outputs`, the status feed — all iterate `FC_AXES_ENABLED` generically,
`flight_control.lua:1142,1158,1320,1433,1941`), not a flag with dead code behind it.
`collective_limited` (line 852) correctly ORs saturation, RPM-floor proximity, and blade-stall
margin, each only capping a further *increase* in collective rate (never forcing it down).
**`ROTOR_RPM_SOURCE = "dummy"`** (line 451) returns a fixed `90.0%` regardless of real engine
state — this is Decision 28's deliberate stand-in ("engine-proxy-or-dummy now, arg 42 a one-place
swap later"), not a bug, but it means the RPM-floor cap cannot yet react to anything the aircraft
actually does; worth surfacing to the user as a known limitation, not a required fix, since it's
exactly what Decision 28 called for at this stage. The torque-pedal sign
(`K_PEDAL_FROM_COLLECTIVE_RATE`) and the turn-coordination sign (`K_TURN_COORD_PEDAL`) are both
explicitly commented as unmeasured guesses pending the slip-ball calibration flight — honestly
flagged, not hidden. **Stacking**: `turn_coord_pedal` is correctly mutually exclusive with
`break_bias` (both gated on `state.rate_override_deg_s`, confirmed at line 928 and 983) — they
never both fire the same frame. `turn_coord_pedal` *does* stack additively with the torque
feedforward term (`d_t_y`, folded into `t_y`) at `law_outputs` (`pedals = t_y + turn_coord_pedal`,
line 1044) — this is intentional and correct, not double-counting: the two represent physically
distinct, genuinely additive effects (torque compensation vs. turn coordination), and the user's
own stacking concern (confirmed by re-reading the brief) was specifically about the break bias,
which is the one pairing that is in fact exclusive. No required fix.

**(d) Item 5 — unpark seed values/missing overlay.** `held_targets()` reads the same module-level
locals (`ai_pilot_course_text`/`ai_pilot_alt_text`/`ai_pilot_alt_add_text`/`ai_pilot_speed_text`)
`update_ai_pilot_wheel_overlay` already populates every poll — no new parse site. Units: speed
converts km/h → m/s (`/3.6`), altitude reference maps `"B"` → `"baro"`, anything else (including
missing) → `"agl"` — matches the module's existing reference vocabulary. Per-field independence
means a missing/failed read (module not loaded, `safe_call` failure, or any single field absent)
degrades gracefully to the pre-existing behaviour for that field alone (bank-heuristic for
heading, stopping-height formula for altitude, measured IAS for speed) — never a hard failure.
Debug.md documents toy-plant and real-Lua-interpreter reproduction of both the pre-fix divergence
(unpark never levels/converges) and the fix (converges within the same step budget). **Optional**:
a genuinely *stale* (not missing) overlay reading — e.g. the overlay hasn't ticked this exact
frame — isn't separately distinguished from a fresh one; this is the same staleness posture every
other reader of these locals already has (no fresher data exists anywhere in the process), so not
a new risk this batch introduces, but worth a note if a future live flight shows a seed lagging by
more than one poll.

**(e) Item 7 — reset ordering/race/fail-loud.** `body._resolve_command_reset` gates
`_apply_ai_pilot_wheel_goal`/`_apply_flight_control` (and their speech drains) behind
`runner.command_reset_confirmed`, checked *before* either is called each poll — so no seq-carrying
command is sent from body-layer until both Lua modules have echoed the current process's epoch
back. This closes the ordering race for anything body-layer itself originates; it does not (and
cannot) guard against a stale datagram from a *previous* process incarnation still in flight over
UDP when it already is sent, but that is a pre-existing property of every command channel on this
wire (best-effort, log-and-continue), not something this batch's reset mechanism was asked to fix,
and the reset op's own idempotence (no `seq`, freely re-sendable) means a late stale reset arriving
after a real one simply re-confirms the same epoch harmlessly. Read `222e5328`'s own diff directly
(the fail-loud commit): `commands_ready` is checked in `rules.gates._require_controls` *after*
`has_controls` (so "not flying" still wins), and refuses with the existing `NOT_READY` token rather
than being accepted and held silently — confirmed this is a real, user-visible refusal path via
`tests/test_rule_gates.py`'s own assertions, not a log line nobody reads. `core.lua`'s
`fmt_int_or_null` switch from `%d` to `%.0f`: Lua numbers are IEEE-754 doubles, and `%.0f` on a
double formats it as the nearest representable integer with no 32-bit-`long` truncation risk
`%d` had on Windows — a millisecond epoch (~1.7e12) is comfortably inside the 2^53 exact-integer
range doubles represent exactly, so no precision loss either way; `%.0f` is strictly safer here,
not merely equivalent. Mission-restart / repeated body-layer-restart behavior is handled by the
three `command_reset_*` fields being explicitly preserved across `reset_for_new_mission` (confirmed
in `body.py`, and independently caught by `test_mission_start_reset.py`'s own separate
preserve-set fence per `implementation.md`'s own "Notable Discoveries"). No required fix.

**(f) Cherry-pick conflict resolution (`flight_control.py`, both sides).** Diffed both files in
full against base: every new field (`slip_ball_pilot_raw`/`slip_ball_operator_raw`/`slip_ball_lo_api`/
`reset_epoch` on the aircraft-layer schema; the mirrored `lua_reset_epoch` plus the same three
slip-ball fields on the body-layer belief side) is declared, parsed/mirrored in
`from_dict`/`advance_flight_control_state`, and round-tripped in `to_api_dict` where applicable —
no half-applied field, no duplicated logic, no name mismatch between the two sides. Confirms the
piecemeal merge-to-main sequence (`20e6a599`, `1658d451`, `222e5328`, the two `Merge fix/bl16-sortie-1120`
commits) landed cleanly.

**(g) Tests genuinely exercise each fix.** For items 1, 2, 5, 7, `debug.md`/`implementation.md`
both document explicit red/green mutation verification — the fix was temporarily reverted (on
either the body-layer Python side, the Lua side, or both) and the new test confirmed to fail for
the stated reason before being restored byte-for-byte (verified by `shasum`). This is a materially
higher bar than this role's checklist asks for by default, and I independently re-ran the full
suites rather than trusting the reported counts alone (see "Checks run" above — they match).

## Comment pruning

Spot-checked the comment blocks directly above each changed line in `flight_control.lua` and
`ai_pilot_wheel.lua` (the pedal-drift fix, the break-bias unwind, the turn-coordination overlay,
the rotor-RPM seam). No durable dated/measured line was removed; every superseded reasoning (e.g.
the old "collective disabled" framing in the module header and `axis_command`'s own comment) was
updated in place rather than deleted outright, consistent with "prune the comment you are standing
next to." No findings here.

## Verdict

**APPROVED.**

No required fixes. The optional watch items above ((a) the 0.5-tolerance integer-display
assumption, (c) the dummy rotor-RPM source being a known stand-in per Decision 28, (d) overlay
staleness as a pre-existing, unchanged property) are all already honestly flagged as unverified
assumptions in the code's own comments, with a stated path to resolution (the slip-ball
calibration flight, arg 42's future swap-in). None blocks merge; they are things to watch on the
next live sortie, not defects in this batch.

**Branch to fly:** `main` (this batch has already been partially merged for flight testing per
user direction; this review clears the remainder for merge).

## Review Confidence

Full read of all seven fixes' design and code (not just the docs' account of them): read the
actual Lua control law (`flight_control.lua`, `ai_pilot_wheel.lua`, `commands.lua`), the actual
Python diffs (`aircraft-layer/src/schema/`, `aircraft-layer/src/api/server.py`,
`aircraft-layer/src/collector/`, `body-layer/src/body.py`, `body-layer/src/belief/*`,
`body-layer/src/rules/gates.py`, `body-layer/src/aircraft_client.py`), independently ran every
mechanical check (`ruff format/check`, `mypy --strict`, full `pytest` for both subprojects,
`luac5.1 -p` and the `GETGLOBAL` sweep on all five touched Lua files) rather than trusting the
reported figures, and cross-referenced every claimed fix against `docs/acceptance/2026-11-20-sortie-feedback.md`'s
verbatim user direction and `plans/flight-control/plan.md`'s Decisions 13/22-32/F-P7 (read by
hand, ledger script found no `U<n>` ids in this section).
