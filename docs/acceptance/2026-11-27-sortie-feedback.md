# Sortie feedback 2026-11-27 — BL-16 LV-1, sixth re-fly (speed change)

Branch flown: `feature/bl16-lift-vector-law` @ 8dadf03d. Card:
`docs/acceptance/2026-11-23-bl16-lv1-card.md`, section "Re-fly 2026-11-25 (6th)".
Logs (gitignored): `docs/acceptance/logs-2026-11-27/refly6_flight_trace.log`,
`refly6_debug.log`.

## User's words, verbatim

> BL-16, acceleration and deceleration
>
> * fairly good, accelerates and decelerates at decent rate, good.
> * problems:
>    * deceleration leads to descent as well. Should maintain altitude.
>    * on command to speed 60, nearing the 60 speed, right pedal was added too late and too slowly
>      which caused left yaw to run away. This is more slow speed behaviour, so can go to that stage.

## Reading

- Speed-change rate: **accepted** ("decent rate, good"). The fifth re-fly's "much too long" is closed.
- **Open, LV-1:** deceleration loses altitude; altitude must hold through a slow-down.
- **Deferred by the user to the slow-speed stage:** at the 60 km/h command, right pedal came in late
  and slowly near 60, left yaw ran away. User's own routing: *"This is more slow speed behaviour, so
  can go to that stage."*

## Follow-up: blade-stall guard threshold (2026-11-27)

Debug round 2 found the residual decel dip comes from the retreating-blade-stall guard, which forbids
any collective increase above 230 km/h IAS (250 km/h limit − 20 km/h margin). User, verbatim:

> "Above 230 km/h it forbids any collective increase" -> no, that's well within operating range.

The user supplied two reference texts on Mi-24P V_NE and retreating blade stall in DCS; filed verbatim
in substance at `aircraft-layer/research/2026-11-27-mi24p-rotor-engine-limits.md`, "V_NE and
retreating blade stall". Key points: V_NE 335 km/h IAS up to 1 000 m at normal weight (≤ 11 200 kg),
falling with altitude and weight; no single RBS table, onset depends on speed, weight, density
altitude, rotor RPM and G; keep RPM ≥ 92 % at high speed; G limits above 200 km/h ~1.8 G light /
1.5–1.6 G combat load; recovery is lower collective first.
