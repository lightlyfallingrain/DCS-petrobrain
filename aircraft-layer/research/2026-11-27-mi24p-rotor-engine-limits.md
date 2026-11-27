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

## V_NE and retreating blade stall (second user paste, 2026-11-27)

Supplied by the user as reference texts (not ED's manual verbatim; secondary summaries). The user's
own call on the existing guard: *"'Above 230 km/h it forbids any collective increase' -> no, that's
well within operating range."*

**V_NE (IAS km/h) by barometric altitude and weight** — set to prevent retreating blade stall and
high-speed pitch-up (*podkhvat*):

| altitude | ≤ 11 200 kg (normal) | 11 200–11 500 kg | 11 500–12 000 kg |
|---|---|---|---|
| 0–500 m | 335 | 320 | 300 |
| 500–1 000 m | 335 | 320 | 300 |
| 1 000–2 000 m | 320 | 300 | 280 |
| 2 000–3 000 m | 300 | 280 | 260 |
| 3 000–4 000 m | 280 | 260 | — |
| 4 000–4 500 m | 260 | — | — |

Note in the source: exceeding 330–350 km/h in a shallow dive at low altitude is the commonest
trigger for an abrupt right roll and loss of lift in DCS.

**G and handling above 200 km/h** (stub wings carry ~25 % of lift in cruise; elevator linked to
collective, so a hard pull stalls blades and wings together):

| condition | max G | handling rule |
|---|---|---|
| light load, < 1 000 m | 1.8 | smooth cyclic; lower collective 1–3° before sharp turns |
| combat load | 1.5–1.6 | collective ≤ 11–12° in high-speed manoeuvring |
| > 2 000 m | 1.3–1.4 | below 280 km/h before steep bank |
| turbulence | 1.3–1.4 | V_NE − 30–40 km/h |

**Thresholds:** normal rotor RPM 95 % ± 2 %; never below 92 % at high speed (low RPM lowers the RBS
threshold). No single official RBS table: onset depends on airspeed, weight, density altitude, rotor
RPM and load factor. **Symptoms:** low-frequency vibration, uncommanded nose pitch-up, roll right
(retreating side). **Recovery:** lower collective 1–3° first, then smooth forward cyclic, level wings.

## Against the flight law (BL-16) and the sixth re-fly

- **Blade-stall guard:** `retreating_blade_stall_ias_kmh = 250` (guard from 230 km/h) sits well inside
  the operating range by the table above (V_NE 335 km/h at Petrovich's normal 50–800 m AGL band).

- **Low side:** `rotor_rpm_warning_pct` = 88 matches the 88 %-for-30-s minimum; the 85 % floor
  matches the autorotation minimum. The hand-flown fast acceleration dipped to 85.4 % (2026-11-25).
- **High side, new:** the law has no rotor-overspeed guard. In the sixth re-fly's deceleration
  (t≈300–310 s) rotor read 100–101 % for several seconds with collective pinned full down —
  inside 101 %/20 s, but at the limit. Lowering collective in a flare raises rotor RPM further, so
  a high-side guard should stop collective going lower near ~100 %. Raising collective to hold altitude
  also brings RPM down, so the guard works in the same direction as the altitude fix.
- **Normal band:** cruise 93–97 %; level flight in the traces reads ~95–96 %.
