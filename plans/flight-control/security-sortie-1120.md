## Security Deep Analysis: BL-16 sortie-1120 bug-fix batch

Reviewed `git diff 98174b54..b59aa99e` (44 files, ~5200 lines) on `sec/sortie-1120`
(`b59aa99eb41e2edd1e0da79ddbeaa278fc0df0d0`, confirmed via `git rev-parse HEAD`), after
`plans/flight-control/review-sortie-1120.md` (APPROVED, Reviewer). Scope per root `CLAUDE.md`'s
security-agent role: internet/LAN security — arbitrary code execution, access to the computer,
what a LAN port scanner reaches, LLM prompt injection, dependency/framework vulnerabilities,
secrets. Correctness of Petrovich's in-sim behaviour is Reviewer's lane; where this pass touched
that ground anyway it is listed under "Passed to Reviewer" with no verdict, per root `CLAUDE.md`'s
security scope note.

### Dependency Status

No dependency change. No new package in either subproject's manifest; no install-time script
introduced. The batch is pure `.py`/`.lua` across `aircraft-layer` and `body-layer`.

### New surfaces reviewed

**`POST /command/reset` (new op, aircraft-layer).** Traced the full chain: `api/server.py`'s
`_handle_command_reset` → `collector.command_sender.CommandSender.send_reset` → loopback UDP →
`Export.lua`'s `commands.lua` `handle_reset_command` → `flight_control.lua`'s/`ai_pilot_wheel.lua`'s
own `reset(epoch)`.

- **Shape validation (`_handle_command_reset`, `api/server.py:1729-1775`):** `epoch` must be a
  JSON `int`, not `bool`, in `[0, 2**53-1]` (`_RESET_EPOCH_MAX`). `json.loads`'s default
  `NaN`/`Infinity`/`-Infinity` acceptance (the project's own recorded LAN-boundary lesson,
  `.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md`-class
  issue) does **not** apply here: those parse as Python `float`, and the `isinstance(epoch_raw,
  int)` check rejects any non-`int` outright before the range check ever runs — confirmed by
  reading the check, not inferred. Test coverage (`test_flight_control_api.py`) exercises missing
  epoch, negative, over-`_RESET_EPOCH_MAX`, and non-JSON body; `bool` exclusion is implemented but
  has no dedicated test (`epoch: true` would otherwise satisfy a bare `isinstance(x, int)` check in
  Python) — low-risk gap, code is correct, only the test is missing.
- **`commands.lua`'s `handle_reset_command`** dispatches to both modules unconditionally once
  `extract_json_number_field` confirms `epoch` is present; no further interpretation of the value
  (by design — documented in both the server docstring and the Lua comment: `epoch` is a liveness
  marker, not a staleness counter, so it is correct that it isn't bounds-checked a second time
  here).
- **What `reset()` actually does, read directly in both Lua files**
  (`flight_control.lua:2001-2005`, `ai_pilot_wheel.lua:1892-1897`): unconditionally calls
  `on_stop()` — releases mode 1's axes back to the player, drops mode 2's open goal/CBTM/HVRT
  state (ED's AI resumes flying) — then stamps the echo field. This is exactly the behaviour
  Decision 13's "yes, let go" direction asked for on a genuine body-layer restart
  (`docs/acceptance/2026-11-20-sortie-feedback.md`).
- **Who can trigger it:** any device that can reach this API — i.e. anyone already able to reach
  every other `/command/*` endpoint, since none of them carry a sender check (`AC-B14`'s own
  posture: shape-validated, not origin-validated). **New here is not the absence of auth (that is
  this project's accepted standing posture, root `CLAUDE.md`'s LAN-only/single-user threat model,
  and the `cockpit_switch` precedent, user direction 2026-10-21) but that this is the first op
  whose entire purpose is "unconditionally let go of whatever Petrovich is doing," rather than one
  outcome reachable via a narrower channel.** Filed as `[[AC-B23]]` rather than argued to a verdict
  here, since it is a judgement call about the whole `/command/*` surface's trust model, not a
  defect in this batch's own validation (which is solid).
- **Confusability with a stale/bogus reset:** read `body.py`'s `_resolve_command_reset` — it
  compares `runner.parked_flight_state.lua_reset_epoch`/`crew_console.flight_control_state.
  lua_reset_epoch` against `runner.command_reset_epoch` (minted once at this process's own
  start-up, `int(time.time() * 1000)`). A forged reset from elsewhere on the LAN, carrying a
  different epoch, does not falsely confirm body-layer's own pending reset (the compare would
  simply fail to match) — it instead *also* triggers the same `on_stop()` a second time on the
  Lua side via the unconditional dispatch above. No privilege-escalation or state-confusion path
  found; the worst case is an extra, unwanted release, already covered by `[[AC-B23]]`.

**Collective axis write (mode 1, `flight_control.lua`).** `FC_AXES_ENABLED.collective = true`
confirmed read generically by every per-axis loop (Reviewer's own finding, re-checked). The
write-path invariant stated in `aircraft-layer/CLAUDE.md` — "never an axis value on the wire" —
holds: body-layer sends only `goal`/`limits` fields (`handle_flight_control_command:1502-1538`,
read directly), each bounds-checked per-field against `FC_LIMIT_BOUNDS` with whole-message reject
on any violation (the `[[AC-B14]]` lesson, still in force, unchanged by this batch). The actual
collective output is derived locally and clamped unconditionally at `law_outputs`:
`collective = law_clamp(state.u_c, -1.0, 1.0)` (`flight_control.lua:1045`) — no path from a
wire-supplied number to an unclamped axis write.

**Slip-ball readout (`fc_slip_ball_pilot_raw`/`fc_slip_ball_operator_raw`/`fc_slip_ball_lo_api`).**
Read-only telemetry (`SLIP_BALL_ARGS`, draw-arg + `LoGetSlipBallPosition()` reads), sent outbound
only, never consulted by the control law this batch (confirmed by the module's own comment and by
reading `law_update`/`law_outputs` for any reference — none). No new input surface; parsed on the
Python side via the existing `_optional_number` helper from the collector's own loopback feed
(Export.lua is the trusted local producer, not a LAN-facing input boundary).

**CBTM-ending branch in the goal handler
(`ai_pilot_wheel.lua:handle_ai_pilot_goal_command`, the `elseif param ~= nil and
ai_pilot_cbtm.action ~= nil` branch, new this batch).** Ends an open CBTM episode and releases its
pending timed press the instant *any* goal command with a param arrives. Reachable by the same
caller who could already reach `/command/ai_pilot_goal` before this batch (no new channel, no new
caller class) — this is a behavioural rework of an existing write path's dispatch logic, not a new
attack surface. **Passed to Reviewer** below: whether "any goal message, from any source, ends a
break mid-press" is the correct trust boundary for *why* it fires is a correctness question about
command semantics, not a security one — the mechanism itself introduces no new reachability.

**Unpark seed read (`held_targets()` / `law_init_at_take`'s `seed` argument).** Confirmed (Reviewer
already did this; re-checked directly) it reads the same already-populated module-level locals
`update_ai_pilot_wheel_overlay` writes every poll — no new parse site, no new external input. Pure
in-process data flow inside Export.lua.

**`fmt_int_or_null` `%d` → `%.0f` (`core.lua`).** Formatting change only, not a parse/validation
boundary — no security content. (Reviewer already confirmed no precision loss; nothing to add.)

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py:1744-1745` (`_handle_command_reset`) | Unbounded `Content-Length` / `rfile.read` | Reproduces the pre-existing, already-tracked pattern (`[[AC-B11]]`, 11 occurrences at this batch's base) on the new endpoint — not a new category of risk; low/low on this project's own stated LAN threat model | None this batch — `[[AC-B11]]` updated with a correction noting the new occurrence (12 total) |
| `aircraft-layer/src/api/server.py:1734-1759` (`_handle_command_reset`) | Unauthenticated op whose sole effect is an unconditional control release / goal-state drop | Shape validation is solid (tested); no sender/origin check — consistent with every other `/command/*` endpoint on this project's accepted no-auth, LAN-only posture, but this is the first op built *specifically* to release control from any caller | Not blocking — filed `[[AC-B23]]` for a standing decision on whether `/command/*` as a whole should gain a sender check, rather than re-litigated per endpoint |
| `aircraft-layer/tests/test_flight_control_api.py` | `epoch: true` (bool) has no dedicated rejection test, though the code (`isinstance(epoch_raw, bool)` check) is correct | False positive risk, not a vulnerability — code already excludes `bool` before the `int`/range check | Not required; worth a one-line test addition if touching this file again |
| `aircraft-layer/src/api/server.py` reset epoch bound | `json.loads` NaN/Infinity acceptance at a LAN boundary | Not exploitable here — `isinstance(epoch_raw, int)` rejects any `float` (including `NaN`/`inf`) before the range check runs | False positive — documented, no fix needed |
| `flight_control.lua:1045` (`law_outputs`) | Axis value derived from wire-supplied `goal`/`limits` | Unconditional `law_clamp(-1.0, 1.0)` on every axis including the newly-enabled collective; no unclamped path found | None |

### Passed to Reviewer

- The CBTM-ending branch in `handle_ai_pilot_goal_command` (any goal message, regardless of
  source, immediately ends an open break/align episode) — a command-semantics/trust-boundary
  question about *when* a goal should pre-empt a break, not a new reachability question. No
  verdict given here.

### Verdict

**APPROVED.**

No required fixes. Two low-risk items filed for the backlog (`[[AC-B23]]` new, `[[AC-B11]]`
corrected with the new occurrence count) rather than left in this report's prose, per this role's
own closing-step rule. Neither blocks merge on this project's stated single-user, LAN-only threat
model.
