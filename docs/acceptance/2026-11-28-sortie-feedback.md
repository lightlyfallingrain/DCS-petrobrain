# Sortie feedback — 2026-11-28: BL-16 LV-2 breaks

**Branch flown:** `feature/bl16-lift-vector-law` (card: `2026-11-27-bl16-lv2-card.md`).
**Logs:** `docs/acceptance/logs-2026-11-28/lv2-aircraft_layer_debug.log`,
`lv2-aircraft_layer_flight_trace.log` (gitignored, local only).

## User's words (verbatim)

> *"LV-2 breaks — Fail. Break pulls (too much) cyclic back causing loss of speed and oscillation
> out of control."*

### Status

Captured; log analysis and `/explore` with the user follow before any fix (CLAUDE.md, "Flight
feedback is captured, then explored, then planned").

### Log reading (one break flown: left, ~213 km/h, ~190 m AGL, t = 57 s)

| t (s) | what happened |
|---|---|
| 57.3 → 59.7 | roll-in to 60° in ~2.4 s — fast, as asked; overshoots to **66°** |
| 59 → 61 | nose drops −2° → −8°, sink grows to −9 m/s; law answers with aft cyclic (+0.28) and collective ramping to **full up** (u_c = 1.0 at 61.1) |
| 61 → 64 | full collective at ~60° bank: nose rises −6° → **+19°**, AoA 46°, IAS 213 → 120 km/h. Cyclic goes **full forward** (out_pitch = a1100 = −1) from 63.3 and cannot stop it |
| 64 → 68 | pitch integrator winds to −1 under the forward saturation; once bank comes off, nose falls to **−52°** — the oscillation |
| 68 → 80 | recovery: sink −14 m/s, rotor 88 % (warning), h_ref 190 → 45 m — **>100 m lost and below the 50 m break floor** |

Inference: the vertical channel, not the pitch channel, starts it. Height-give lowered the
reference (w_ref ≈ −7 m/s) but the real sink (−9.8) was faster, so the law still demanded
+2 m/s² up on top of ~2.3 G of turn → full collective. At 200+ km/h full collective pitches the
nose up harder than full forward cyclic can hold. Rests on: `a1100` sign = aft positive (third
re-fly, `flight_control.lua` header).

## Mode-2 fixes card (`2026-11-27-mode2-fixes-card.md`)

User's words (verbatim):

> *"'Speed 250' - OK. 'speed up' - OK. 'slow down' -> 'action file error' -- fix the action
> file."*
> *"recovery - PASS"*

`[[BL-B139]]` (recovery) PASS; `[[BL-B140]]` ("speed 250") PASS.

"Slow down" cause: the rule file (`config/rules/flight.lua`) was fine. Sequence in the speech
log: "speed 250" → "speed up" (overlay now reads the literal `MAX`) → "slow down". The gate
reads `flight_authority_state.ias_kmh` (known) and passed; the mode-2 action reads the
overlay's `held_speed`, which parsed `"MAX"` as `None`, and its `assert` fired — the engine
reports any action exception as "Action file error.". The gap was flagged in `step_speed`'s
own docstring. Fixed: `"MAX"` parses to the MAX sentinel (so slow down → 250), and the assert
is now an ordinary "unable, not ready".
