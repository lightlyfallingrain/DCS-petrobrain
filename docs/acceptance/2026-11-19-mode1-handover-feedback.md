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
