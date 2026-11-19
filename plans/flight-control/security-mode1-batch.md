## Security Deep Analysis: BL-16 mode-1 batch (break turn, break away, rotor envelope, VRS, rates as goals)

Branch `feature/bl16-mode1-break`, tip `c1d8dfd8` (Reviewer APPROVED). HEAD (`e2067c77`) was a
strict ancestor of the stated tip with a clean tree; fast-forwarded to `c1d8dfd8`. Diff reviewed:
`e62b7ff9..c1d8dfd8`.

### Dependency Status

No dependency change. No new package, no new import, no new install-time script.

### Scope note

This pass covers computer/network security — arbitrary code execution, host access, what a LAN
port scanner reaches, LLM prompt injection, dependency risk, secrets — per the project's security
scope (root `CLAUDE.md`, "Scope" section). Control-law correctness (bank limit removal, integrator
windup, the 60-80° bank figure not being reached) is player-experience/correctness and was already
covered by Reviewer (`plans/flight-control/review-mode1-batch.md` — recorded as a named Risk for
Flight M-A, not a defect). See "Passed to Reviewer" below.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py` `_FLIGHT_CONTROL_GOAL_BOUNDS["turn_rate_deg_s"]` (~line 552) | New wire field, HTTP→DCS boundary | Bounded `(-90.0, 90.0)`, checked with `math.isfinite`, bool-rejected, same validation loop every other goal field uses (lines 1619-1640). No gap. | None |
| `aircraft-layer/src/api/server.py`, `max_bank_deg` removal (~line 520) | Wire-field removal, not widening | Removed key-for-key from `_FLIGHT_CONTROL_LIMITS_BOUNDS`, `Export.lua`'s `FC_LIMIT_BOUNDS`, and `belief/flight_control.py`'s `flight_control_limits()` together — a stale sender's `max_bank_deg` value now finds nothing to accept rather than being silently applied somewhere unbounded. Verified all three sides agree (grep for `max_bank_deg`/`MAX_BANK_DEG` across both subprojects, as the Reviewer also did). | None |
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` `handle_flight_control_command` (~1257-1291) | Limits re-check at the DCS-side boundary | `FC_LIMIT_BOUNDS` loop re-validates every present `limits.*` field against its own hard ceiling and rejects the **whole message** on any violation (the AC-B14 posture) — this still runs after the mode-1 batch's five new `limits` keys were added. | None |
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` `apply_goal_fields`/`handle_flight_control_command` | Goal fields (`heading_deg`, `alt_m`, `ias_kmh`, `turn`, and the new `turn_rate_deg_s`) have **no second bound check in Lua** — only `limits.*` is re-checked by the `FC_LIMIT_BOUNDS` loop. | Not a gap introduced by this batch: pre-existing shape (confirmed against `e62b7ff9`, before this diff, for the other goal fields — none were re-checked in Lua either). The only path into this socket is loopback UDP from the collector process on the same box (`command_sender.py`'s `DEFAULT_HOST = "127.0.0.1"`), and `send_flight_control` re-serializes the already-validated Python values via `json.dumps` rather than forwarding client-supplied text — a LAN attacker cannot reach this listener directly, only through `server.py`'s own validation first, which does bound `turn_rate_deg_s` and every other goal field. `aircraft-layer/CLAUDE.md`'s claim that "Export.lua's own `handle_flight_control_command` re-checks every bound" is accurate for `limits` only, not `goal` — a documentation-accuracy note, not a security finding; not filing, see below. | Not filed, intentionally (doc accuracy, no exploitable path; see reasoning above) |
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` `read_rotor_rpm_pct` (~line 400) | New `GetDevice(0):get_argument_value(ROTOR_RPM_ARG_PILOT)` read, reusing the existing draw-arg-read pattern (`ai_pilot_wheel.lua`'s stick-park read) | `ROTOR_RPM_SOURCE = "dummy"` by default — the live arg read is not active in this batch. `pcall`-wrapped via `safe_call`; a non-number or NaN result (`raw ~= raw`) falls back to the dummy value rather than propagating. No new DCS API surface, no new write, read-only. | None |
| `body-layer/config/rules/flight.lua` `BREAK_TURN_RATE_DEG_S = 40` | User-editable rule file value flowing into an action parameter | `rules/engine.py`'s `_make_action_wrapper` (lines 198-267) enforces `ActionParam(lo=1, hi=90)` generically **before** `action.invoke` ever runs, with an explicit `math.isfinite` check ahead of the `int()` cast (the same `nan`/`inf`-from-rule-arithmetic guard the module's own comment cites, "security Required Fix 1"). A hand-edited out-of-range or non-finite value in `flight.lua` is rejected with `RuleRuntimeError`, never passed through. This is defense-in-depth that already existed before this batch; the new `rate_deg_s` params on `cbtm_break`/`cbtm_break_away` (`body-layer/src/rules/actions.py` ~515-530) use it correctly. | None |
| `aircraft-layer/src/api/server.py` `_handle_command_flight_control` (~1535-1536) | `Content-Length`-driven unbounded `rfile.read` | Same pre-existing pattern as every other `POST` handler in this file, already tracked as `AC-B11` (`aircraft-layer/ROADMAP/AC-B11.md`). This handler is not new in this batch (it shipped in Stage M1); the mode-1 batch only added fields to its existing body. Handler count is unchanged, so AC-B11's own count does not need a correction. | None (already filed as AC-B11) |

### Passed to Reviewer

One line, no verdict: the removed `max_bank_deg` clamp (no ceiling on `phi_d`/the `phi_i`
integrator in `flight_control.lua`'s `law_update`) is a named correctness Risk already recorded in
`plans/flight-control/plan.md` and `review-mode1-batch.md` for Flight M-A — player-facing control
behaviour, not a security exposure (the actuator output stage still clamps `u_roll` to `[-1, 1]`
regardless, so no crash/overflow path exists).

### Verdict

PASS

No required fixes. No new finding needed an ID: the one goal-field-not-rechecked-in-Lua
observation above is a documentation-accuracy note with no exploitable path (explained inline, not
filed), and the Content-Length pattern on this handler is already covered by the standing `AC-B11`
backlog item.
