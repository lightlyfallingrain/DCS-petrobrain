# Mi-24P rotor and engine limits — reference values (2026-11-27)

Source: two tables from the DCS Mi-24P documentation, supplied by the user. User, verbatim:
*"Data from the Mi-24 DCS documentation. Since this is a game, we don't have to exatcly adhere to
these, but these are the reference values."* So these are **references for the flight law's guards,
not hard requirements**.

Gauge scale: rotor and engine gauges read 0–110 %, gauge % = draw arg × 110 (calibrated
2026-11-25, `docs/acceptance/2026-11-24-sortie-feedback.md`).

## Aircraft

| item | value |
|---|---|
| Max takeoff weight | 12 000 kg |
| Max speed | 335 km/h |
| Max main rotor speed | 101 % for no more than 20 s |
| Min main rotor speed | 88 % for no more than 30 s |
| Min main rotor speed in autorotation | 85 % |
| Max PTIT | 880 °C; normal 720–750 °C |

## Main rotor RPM (NR)

| absolute limits | NR | max time |
|---|---|---|
| Max rated and takeoff power | 103 % max | 20 s |
| Max rated and takeoff power | 88 % min | 30 s |
| All settings above limited cruise | 101 % max | 20 s |
| All settings below limited cruise | 103 % max | 20 s |

| normal operating | NR | max time |
|---|---|---|
| Idle | 45–65 % (two engines), 40–55 % (one) | 20 min |
| Cruise | 93–97 % | not limited |
| Limited cruise | 97 % max | 60 min |
| Takeoff | 94 % max | 6–15 min |
| Max rated power | 94 % max | 6–60 min |
| Autorotation (no power) | 90–98 %; avoid transient overspeed 115 %, underspeed 85 % | — |

## TV3-117VMA engine (N1)

| power setting | max PTIT °C | max N1 % |
|---|---|---|
| Max rated | 990 | 101.0 |
| Takeoff | 990 | 101.0 |
| Max limited cruise | 955 | 99.0 |
| Limited cruise | 910 | 97.5 |
| Cruise | 870 | 95.5 |
| Idle | 780 | max idle N1 table value |

## Against the flight law (BL-16) and the sixth re-fly

- **Low side:** `rotor_rpm_warning_pct` = 88 matches the 88 %-for-30-s minimum; the 85 % floor
  matches the autorotation minimum. The hand-flown fast acceleration dipped to 85.4 % (2026-11-25).
- **High side, new:** the law has no rotor-overspeed guard. In the sixth re-fly's deceleration
  (t≈300–310 s) rotor read 100–101 % for several seconds with collective pinned full down —
  inside 101 %/20 s, but at the limit. Lowering collective in a flare raises rotor RPM further, so
  a high-side guard should stop collective going lower near ~100 %. Raising collective to hold altitude
  also brings RPM down, so the guard works in the same direction as the altitude fix.
- **Normal band:** cruise 93–97 %; level flight in the traces reads ~95–96 %.
