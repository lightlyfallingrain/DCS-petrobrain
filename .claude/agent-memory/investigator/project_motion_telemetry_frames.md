---
name: project_motion_telemetry_frames
description: Mi-24P LoGetVectorVelocity/LoGetAccelerationUnits/LoGetAngularVelocity frames and axes, settled as far as existing M0-A flight data goes (BL-16 lift-vector law, 2026-11-20)
metadata:
  type: project
---

Full writeup: `aircraft-layer/research/2026-11-20-motion-telemetry-frames.md`. Settled from
re-reading `2026-11-18-bl16-m0-flight-axes-findings.md`'s own numbers (no new flight this session —
no DCS reachable) plus the already-wired code in `flight_control.lua`:

- **`LoGetAngularVelocity`** — fully settled, x=roll rate, z=pitch rate, y=yaw rate positive when
  heading *decreases* (negated in code). rad/s. Nothing new; already wired in
  `flight_control.lua:1390-1400`.
- **`LoGetVectorVelocity`** — **y is world-frame vertical velocity**, m/s. Inferred from
  `LoGetVerticalVelocity` == `.y` *exactly* across a flight with varying bank/pitch — a body-frame
  y would not track true vertical under changing attitude, so the exact match is itself the
  evidence for world frame. x/z (north/east vs. some other convention) unmeasured — no maneuver in
  the existing data isolates them, only inferred by analogy with this project's general DCS x=north/
  y=up/z=east convention used elsewhere (`world-model/coordinates`).
- **`LoGetAccelerationUnits`** — **y is body-frame specific force (load factor, g, gravity
  included)** — a real G-meter reading, which is exactly "what the pilot feels." Evidence: y
  measured 0.69–1.35 g in nearly-level cruise (±5.3° bank) — only a load-factor quantity sits near
  1 g at rest; a world-frame vertical accel would sit near 0. x (longitudinal)/z (lateral) named
  but sign/scale unmeasured — same caution as x/z above, do not wire a law term on them without a
  maneuver that isolates each (level accel/decel for x, banked turn for z).
- **`LoGetSlipBallPosition`** confirmed **dead** on the Mi-24P (returns `nil`, live-confirmed
  2026-11-20 calibration flight) — use draw args 943 (pilot)/784 (operator) instead
  (`2026-11-20-slip-ball-recon.md`). By the same pattern, treat `LoGetAngleOfAttack`/
  `LoGetAngleOfSideSlip` as nil-risk on this module until probed — never assumed to work just
  because the symbol exists in `Sim_ControlAPI.md`'s permission-tier list.

**Technique note, not project-specific**: a frame/axis question that looks like it needs a
dedicated probe can sometimes already be answered by **an exact-equality cross-check between two
already-logged fields across a varying-attitude flight** (here: `LoGetVerticalVelocity` vs.
`LoGetVectorVelocity().y`) — cheaper than flying a new maneuver, but only works when one of the
two fields has a frame-independent physical meaning (true vertical speed is the same number in any
frame) to anchor against.

See also [[project_bl16_sau_desk_recon]] (the open-items list this partially resolves) and
[[reference_sim_controlapi_doc_naming]] (the doc's naming quirks, a different gap).
