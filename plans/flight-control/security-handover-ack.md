## Security Deep Analysis: fix/handover-ack-seq

Branch `fix/handover-ack-seq`, reviewed at tip `ed2e2323df8cec5369e8b0dcd5d92d735e2e8a2a`
(reviewed and APPROVED WITH MINOR FIXES by Reviewer in `plans/flight-control/review-handover-ack.md`),
base `main` @ `bba8d03b`. Scope per `docs/acceptance/2026-11-19-mode1-handover-feedback.md` and
`plans/flight-control/debug.md`: the take-ack seq-matching fix, the ack-timeout system release, the
`release_controls` recovery widening, and `core.lua`'s new `fmt_int_or_null`/`is_finite_number`.

### Dependency Status

No dependency change — confirmed (`git diff bba8d03b..ed2e2323 -- '*pyproject.toml*'
'*requirements*.txt'` empty). Pure code change to existing modules in `aircraft-layer/` and
`body-layer/`.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/dcs-export/Petrobrain/core.lua` (`is_finite_number`, `fmt_int_or_null`) | New non-finite guard on a wire-encoding path | **Fixes a gap, does not open one.** `fmt_num_or_null` previously emitted `nan`/`inf`/`-inf` as literal unquoted text, which is not valid JSON and would have produced a malformed line on the loopback TCP feed to the collector — same failure class as the project's own recorded NaN/Infinity lessons (`project_nan_infinity_int_conversion_at_lan_boundary.md`, `project_nan_infinity_int_conversion_at_lua_action_boundary.md`), but on the *encode* side rather than the *parse* side. The new guard makes both helpers emit `null` instead, which the existing `_optional_int`/`_optional_number` parsers (`aircraft-layer/src/schema/flight_control.py`, unchanged by this diff) already handle as a normal optional-field absence. No new attack surface: this socket is loopback-only (`Export.lua` → collector, same box), and the fix only ever degrades a bad value to `null`, never upgrades one. | None |
| `aircraft-layer/src/schema/flight_control.py` `_optional_int` | Strict `isinstance(raw, int)` before use | Unchanged by this diff. Already the *safe* shape relative to the NaN/Infinity lesson above (it rejects any non-`int`, including a float, with the module's own typed `FlightControlParseError`, rather than calling a bare `int()` on an `int\|float`-typed value) — not the gap pattern those two memories describe. Confirmed by reading; no action needed here. | None |
| `body-layer/src/belief/flight_control.py` `release_controls` (`state.lua_mode in ("active", "taking")`) | New condition for `acted=True`/phase→`PILOT` | `lua_mode` is a mirror of a value that crosses the LAN-facing `aircraft-layer` HTTP API (`GET /flight_control/latest`, server bound `0.0.0.0` per `aircraft-layer/CLAUDE.md`). A garbled or spoofed value here can only drive this branch toward **releasing** the simulated aircraft back to the player and sending Lua an unconditional, idempotent `"release"` — the safe/fail-toward-pilot direction already implicit in this module's design (a timeout already defaults to `PILOT`), not a "crafted status line grants an unintended take" path. No scenario in this diff lets a received value *grant* control; every new/changed branch only ever gives it up. | None |
| `body-layer/src/belief/crew_console.py` `drain_flight_control` (`flight_control_system_release_pending`) | New one-shot field, system-queued `"release"` on ack timeout | Same direction as above — queues a release, never a take. Reviewer's own re-review (mutation-tested) already confirmed it cannot be silently clobbered by a same-poll player command and is cleared on `OVERLAY`/mission restart. No path from a garbled wire value to an unintended *take*. | None |
| `body-layer/src/body.py` `_apply_flight_control` (`take_seq=next_seq` on send) | `take_seq` now set from body-layer's own `wire_seq` counter at send time | `wire_seq` itself is reconciled against `lua_last_cmd_seq` (pre-existing, `security-m1-m2.md` Finding A, untouched by this diff) — a received counter can only ever advance `wire_seq` forward to catch up after a restart, never cause body-layer to *believe* a take succeeded that it did not itself just send; the ack match still requires `lua_take_seq == take_seq`, both sides of which trace back to a value body-layer generated. No new path to a spoofed take-ack. | None |
| five changed `.lua`/`.py` files, full pattern sweep (dynamic exec, shell-out, file writes, new sockets) | `grep` for `eval\|exec\|pickle\|loadstring\|dofile\|dostring\|subprocess\|os\.system\|os\.popen\|os\.execute\|io\.popen\|open(...[wa]\|shutil\.\|os\.remove\|os\.rename` against only the lines this diff touches | Zero hits. Remaining matches in the full files (`dofile` in header comments describing the pre-existing module-load mechanism, `shutil.get_terminal_size`/`path.open("a")` elsewhere in `body.py`) are outside the diff, confirmed by `git diff` on those exact lines returning empty. No new code-execution, shell-out, or filesystem surface. | None |
| aircraft-layer `0.0.0.0`-bound API, `flight_control` write path's bounded vocabulary (`aircraft-layer/CLAUDE.md`) | Project invariant: no raw axis values on the wire, Lua re-checks bounds | Unaffected — this diff touches only the handover state machine and a numeric-format bug on existing, already-bounded fields (`seq` counters). No new field, no new `cmd` value, no widened vocabulary. `Export.lua`'s own `handle_flight_control_command` bound-checking is untouched. | None |

### Verdict

**APPROVED**

No exploitable vulnerability, no new dynamic-code-execution or shell-out path, no new filesystem
write path, no widened LAN-facing surface, no secrets, no dependency change. The one LAN-facing
input this diff's logic depends on (`lua_mode`, crossing the unauthenticated `aircraft-layer` API)
can, if garbled or spoofed by an infected LAN peer, only push belief toward releasing the simulated
aircraft back to the player — the fail-safe direction this module already defaults to on timeout —
never toward granting an unintended take. The Lua-side `fmt_int_or_null`/`is_finite_number` change
closes a pre-existing malformed-JSON-on-encode gap (this project's own recorded NaN/Infinity
int-conversion lesson, previously only checked on the parse side) rather than opening one.

### Passed to Reviewer

None — Reviewer's own two passes (required fix + re-review) already covered the correctness
questions (same-poll clobber, stale `lua_mode` mirror, restart handling, deferred-take clock); this
pass found nothing further in that territory to hand back.

### Filing

No finding in this pass crossed the bar for a backlog item — every row above is "no action
required," confirmed by reading and, where the mechanism was non-obvious (the `wire_seq`
reconciliation, the NaN/Infinity encode-side fix), traced against the actual code and the project's
own prior memory on the pattern. Not filed, intentionally: there is nothing here to schedule.
