# BL-16 mode 1 handover — sortie feedback (2026-11-19)

Flown on `main` at `bba8d03b`, mode 1 (unparked, raw axes). User's words, verbatim:

> "you have controls" -> "unable, not ready" but Petrovich does take controls
>
> "turn right 2 0" -> "unable, not flying" though controls are written and I cannot control
>
> "I have controls" -> no effect since state says I already have controls, though I don't

## Diagnosis (main loop, code read)

One defect, two consequences.

1. **The take ack can never match.** `Export.lua` (`flight_control.lua`, `cmd == "take"`) records
   `fc_pending_take_seq = seq` — the **wire** message seq — and reports it as `fc_take_seq`.
   body-layer's `decide_flight_control` compares it against `FlightControlState.take_seq`, its own
   separate per-take counter (`take_seq + 1`). The two counters are different numbers, so the
   `TAKING → ACTIVE` branch never fires and `HANDOVER_ACK_TIMEOUT_S` (2 s) always does:
   "Unable, not ready." The tests build states with the two values set equal by hand, so they
   never saw it.
2. **The timeout only changes belief, not the aircraft.** `TAKING → PILOT` on timeout sends no
   `release`, so Lua stays `active` flying the axes while belief says the player has them. From
   then on every `flight_control*` rule answers "Unable, not flying", and "I have controls" from
   `PILOT` is a silent no-op — the recovery phrase that Decision 13 says must always act does
   nothing.

User approved fixes a (match the ack by the take's wire seq), b (ack timeout also sends `release`)
and c ("I have controls" releases whenever Lua reports holding the axes, whatever belief says).

## Mode 2, same day

> "even more important, why did handing control over not work? Just tested with mode 2, same
> 'unable not flying'"

`speech-20261119-232426.jsonl`: "altitude two zero zero radar" → `set_altitude`, `act`, then the
`flight_control` gate refused with `NOT_FLYING`. Mode 2 has no ack, so this means body-layer's
`parked_flight_state.parked_active` was false — `apw_parked_active` from `ai_pilot_wheel.lua`
(stick 852 stowed AND camera in the operator seat). Cause not yet known; needs the live
`GET /ai_pilot_wheel/latest` sample from that state. Open hypothesis: mode 1's Lua side was left
`active` by the earlier failed take (defect 2 above; only a mission restart or a `release` clears
it) and is interfering.

## Common root cause, both modes (found 2026-11-19, from the collector console)

`curl /ai_pilot_wheel/latest` and `/flight_control/latest` both returned `null` while telemetry
was live. The Windows collector console showed, user-supplied:

```
2026-11-19 23:41:20,711 WARNING dropping malformed ai-pilot-wheel line: '{"t":107.962,"apw_parked_active":true
2026-11-19 23:41:20,711 WARNING dropping malformed flight-control line: '{"t":107.962,"fc_mode":"off","fc_take
```

`core.lua`'s `fmt_num_or_null` formats every number `%.5f`, so a seq goes out as `-1.00000`,
which JSON parses as a float; both schemas' seq fields demand `int` and reject the whole line.
`fc_last_cmd_seq` is never null, so **every** flight-control line has been dropped since
`307d6a81` (2026-11-18); the AI-wheel line is dropped once `apw_goal_seq`/`apw_cbtm_seq` is set.
Reproduced against the schemas. Mode 2's "not flying" is `parked_active` never arriving; mode 1's
take ack never arrived at all (the seq mismatch above was real too, but secondary). No test parses
what Lua actually emits.
