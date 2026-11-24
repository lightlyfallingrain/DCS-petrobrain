# Sortie feedback 2026-11-24 — BL-16 LV-1 card, row 1

Branch flown: `feature/bl16-lift-vector-law` @ 97ffe624. Card:
`docs/acceptance/2026-11-23-bl16-lv1-card.md`.

## User's words, verbatim

> # LV-1 flight
> Petrobrain feature/bl16-lift-vector-law @ 97ffe624
>
> ## 1 Take into a held heading
>
> Fail - still creates bank and escalates out of control, logs attached

Logs: `aircraft_layer_flight_trace.log` (estimator trace only, t=0..144.9) and
`aircraft_layer_debug.log`. Only row 1 was flown.

## What the logs show (main loop's first read, not yet a diagnosis)

- Take at t=112.19 (`flight cmd kind=take seq=1`, ack `a:m1`), off→m1. Release at t=137.11
  (ack `a:m1 mode=m1`). Trace ends t=144.9.
- Before the take: steady, vg 55.9 m/s, v_u +1.1, a_r −0.07, ball −0.033, sideslip (aoss) −1.9°.
- **First 8 s after the take, before any bank oscillation:** ball moves monotonically
  −0.03 → +0.56, sideslip −1.9° → +18°, a_r 0 → +2.5 m/s² with psidot ≈ 0 (flight path curving,
  nose not following), v_u climbs 1.1 → 5.7 m/s. The ball running to +0.5 (≈ full left pedal on
  the 2026-11-20 calibration) is the earliest wrong thing.
- Then a growing lateral oscillation, period ~10 s: a_r +2.5 (t≈118) → −5.3 (t≈126) → +6.2
  (t≈130) → −10 (t≈136); roll rate peaks 30–37 °/s; v_u swings +11.5 → −3.5 → +6.9 m/s.
- The trace carries no law internals (phi_d, theta_d, t_r, t_p, t_y, u_c, r_d, a_*_d), so which
  loop drives it cannot be read from these logs.

## Hypotheses to check (not decided)

1. Pedal ball loop sign inverted (positive feedback). The loop's sign rests on
   "positive pedal command = right", derived from a weak (+0.23..+0.40) on-ground correlation of
   arg 1103 with yaw rate (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`).
2. Collective→pedal torque feed-forward or the turn-coordination pedal overlay with a wrong sign.
3. Lateral trim loop (phi_i on a_r error) fighting sideslip-induced side force, and the vertical
   loop climbing for a reason not yet known.

## User's answer, after the first read

Asked whether the pedals moved after the take, and which way:

> yes, lot's of left pedal

Left pedal is what moves the ball right (2026-11-20 calibration), so this supports hypothesis 1:
the ball loop is driving the pedal away from centring.

## Re-fly after the pedal-sign flip (same day, 7f362fa4 + card)

User's words, verbatim:

> Actually, it's worse now, even more left pedal at takeover

> the pedal write is definetely reversed now, so apparently it was not before

Logs: `logs-2026-11-24/refly_flight_trace.log` (law internals now present; this flight starts at
the line whose `t=0.000` carries `mode=off phi_d=nil`) and `refly_debug.log`. Take t=24.97 (off→m1,
~135 km/h level), release t=34.98.

Main loop's read of the law trace:
- **The commanded pedal does not jump at the take**: `out_pedals` −0.302 at t=25.05, −0.295 at
  25.4, −0.28 at 25.7 — smooth, small. Yet **yaw rate goes −0.5 → −9 °/s within 0.8 s of the
  take** (heading decreasing, nose left), before the law's pedal changed by more than 0.03. Flight 1
  shows the same kick (−0.05 → −5.9 °/s within 1 s). Something at the take itself moves the
  aircraft, which no gain sign can cause — candidates: the actual pedal position is not where the
  captured value says (capture/write mismatch, i.e. a mirror at the take), or the hardware pedal
  and `LoSetCommand` combine.
- After that, the law ran right-pedal per its new convention: `t_y` to its −0.5 limit plus the
  turn-coordination term −0.33 (heading-hold asked +16 °/s right), `out_pedals` −0.83. The user saw
  heavy **left** pedal. So a negative command is physically left — the debugger's flip was wrong,
  matching the user's statement.
- Sideslip reached 67°, ball +0.65. Collective drove steadily down from 0.106 to −0.01 (u_c_rate
  −0.05/s) from the take until it stopped — not yet explained.
- The trace still lacks the **actual** axis args (1100–1103) next to the commands, so the take
  mismatch cannot be confirmed from the logs.

Logs kept locally (gitignored): `docs/acceptance/logs-2026-11-24/` in the `DCS-petrobrain-epochfix` worktree.
