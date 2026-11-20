# Motion telemetry frames for BL-16's lift-vector control law

**Date:** 2026-11-20
**DCS version:** not verified locally this session — no DCS install reachable from this worktree
(Mac dev machine). The facts below that come from a live flight are sourced from the M0-A probe's
own log header: DCS version is not stated in the quoted findings doc either, so the most recent
confirmed version anywhere in this project's aircraft-layer research remains **2.9.30.28738**
(`2026-10-22-9k113-ai-axis-obedience-prior-art.md`). Treat anything below as current only as far as
that version goes; it should be re-stated from the `dcs.log` header or `autoupdate.cfg` the next
time someone is on the Windows box.
**Theatre:** n/a — this is a cockpit/scripting-API question, not terrain. The M0-A flights were on
Caucasus (magnetic variation 7.27–7.31°), which is irrelevant to the axes themselves.

### Question

BL-16 mode 1's control law (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`) currently
derives `a_x`/`a_z` from a filtered numerical derivative of IAS/vertical-speed, explicitly because
`LoGetAccelerationUnits`'s body-frame mapping was "unconfirmed" (module header, the fallback the
plan itself anticipated). The user's direction (2026-11-20) is that DCS's own raw motion telemetry
— not just derived rates — can let Petrovich detect aircraft state and acceleration the way a real
pilot would *feel* it, and should be used instead of leaning on instruments alone ("we cannot know
the exact lift vector... but we can observe aircraft behaviour and manipulate lift vector...").
This note settles which axes/frames `LoGetVectorVelocity` and `LoGetAccelerationUnits` actually use
on the Mi-24P, confirms `LoGetAngularVelocity`'s mapping already found, and says what a probe
flight would still need to measure before the law can switch off the numerical-derivative fallback.

### Findings

1. **`LoGetAccelerationUnits` is body-frame specific force (a G-meter reading, gravity included),
   not a world-frame acceleration.**
   - **y is the vertical/load-factor axis, measured 0.69–1.35 g in level-ish cruise with bank
     excursions of only ±5.3°.** A world-frame vertical acceleration would sit near 0 g except
     during an actual climb/descent rate change; a body-frame *specific force* sits near **+1 g**
     in level flight (reaction to gravity plus lift) and swings with maneuvering load exactly as
     measured here — this is the signature of a load-factor/"what the G-meter reads" quantity,
     the same convention DCS uses for the fixed-wing G-meter instrument. — **evidence: inferred**
     (from the M0-A numbers plus the general DCS G-meter convention) — **source:**
     `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md` ("`LoGetAccelerationUnits`
     is in g... y is the load factor (0.69–1.35 g)").
   - **x is longitudinal, z is lateral** — named but not sign/scale-measured in M0-A (no
     correlation reported against a known longitudinal/lateral event). — **evidence:
     reproduced-locally (axis identity only, from the probe dump labels) / inferred (that this
     maps to "forward"/"right" with a particular sign)** — **source:** same file.
   - **Units are g** (not m/s²) — stated directly in the finding, consistent with the 0.69–1.35
     range for y (which would be an absurd m/s² reading for level flight, but a normal g-load).
   - **Frame is body axes, not world/NED/ENU.** Nothing in `Sim_ControlAPI.md` states this — it is
     a bare name in the permission-tier list with no shape (confirmed by direct grep, no
     "args"/"results" lines near it: `Sim_ControlAPI.md:520`). The body-frame conclusion rests on
     the load-factor signature above, which only makes sense if gravity's reaction shows up fixed
     on one axis (the aircraft's own vertical) rather than smeared across x/y/z as bank changes —
     this is exactly how the module's own control-law header already reads it ("filtered dV/dt
     and dw/dt instead, `LoGetAccelerationUnits`'s own axis-to-body-frame mapping being
     unconfirmed" — i.e. the plan already assumed body-frame, just not yet with enough confidence
     to switch). — **evidence: inferred, not reproduced** — **source:** `flight_control.lua`
     module header (frame fallback comment) + M0-A numbers above.
   - **"Usable directly as what the pilot feels" — yes, with a caveat.** A body-frame G-meter
     reading (gravity included) is *literally* the specific force a pilot's inner ear and body
     feel, which is exactly what the user's direction is asking Petrovich to use instead of reading
     instruments. The caveat is that **x/z sign and scale are still unmeasured** (no probe has
     stepped a known longitudinal or lateral maneuver and read the correlation the way M0-A did for
     y against bank/pitch) — using x/z blind risks a wrong-sign law term, the same failure mode
     the module already avoided once for the pedal axis (M0-B) and the slip ball (`K_beta`).
     — **evidence: inferred for the caveat, not yet reproduced for x/z.**

2. **`LoGetVectorVelocity` is world-frame, not body-frame; units m/s.**
   - **`LoGetVerticalVelocity` equals `LoGetVectorVelocity().y` exactly**, across a flight whose
     bank varied ±5.3° and pitch varied several degrees (M0-A flight 1). A **body-frame** y-velocity
     would differ from the true vertical speed whenever the aircraft is banked or pitched (it would
     read the velocity component along the airframe's own "up" axis, not along true vertical); the
     two values only coincide exactly, frame after frame, under continuously varying attitude if
     `y` is **already resolved into the world/earth vertical axis**. — **evidence:
     reproduced-locally (the equality itself, which is the strongest evidence in this note) /
     inferred (that equality implies world frame)** — **source:**
     `2026-11-18-bl16-m0-flight-axes-findings.md` ("Vertical speed is in m/s. `LoGetVerticalVelocity`
     equals `LoGetVectorVelocity().y` exactly").
   - **This resolves `2026-10-26-bl16-flight-control-desk-recon.md` finding 4's open item** ("the
     other five [getters]... have never been called anywhere in this project's code" / Unresolved
     item 7/4): `LoGetVectorVelocity`'s return frame is no longer unestablished — the y-axis
     equality is a reproduced-locally fact from a flight that happened after that recon note was
     written, even though neither the recon note nor the M0-A findings doc drew the frame
     conclusion explicitly. Also narrows `2026-11-20-slip-ball-recon.md` Unresolved item 4 (which
     cited the same open question as a reason not to build the velocity-derived sideslip fallback):
     the frame is now known for y; x/z are still open (below).
   - **x/z axis identity (north/east vs. some other world convention) is not measured.** DCS's
     general scripting-API coordinate convention (used consistently across `LoGetSelfData`,
     `coord.LLtoLO`, and this project's own `world-model/coordinates` module) is a left-handed
     system with **x = north, y = up, z = east**, in metres/m-s. This is the project's own working
     assumption elsewhere (`world-model`'s coordinate conversion already treats DCS x/z this way),
     but **no probe has specifically correlated `LoGetVectorVelocity().x`/`.z` against a known
     heading** the way the y-axis was pinned against vertical speed. — **evidence: inferred (by
     analogy with the project's established DCS-coordinate convention elsewhere, not reproduced for
     this specific call)** — **source:** `world-model/docs/CONVENTIONS.md` coordinate handling
     (general DCS x/z convention), cross-referenced against the absence of a direct test in
     `2026-11-18-bl16-m0-flight-axes-findings.md` and `2026-10-26-bl16-flight-control-desk-recon.md`.

3. **`LoGetAngularVelocity` mapping — confirmed, M0-A, no new information this session.**
   - **x = roll rate** (correlates +0.95 with d(bank)/dt), **z = pitch rate** (correlates +0.79 to
     +0.97 with d(pitch)/dt), **y = yaw rate, positive when heading *decreases*** (correlates −0.95
     with d(heading)/dt — i.e. the sign the control law already negates:
     `flight_control.lua`'s `read_measured()` does `r_deg_s = -math.deg(ang.y)` precisely because
     of this). — **evidence: reproduced-locally** — **source:**
     `2026-11-18-bl16-m0-flight-axes-findings.md`, cross-checked directly against the live code at
     `flight_control.lua:1390-1400`, which already implements this mapping and cites the same
     finding in its own comment. Nothing to add; this item is fully settled and already wired in.
   - **Units are rad/s** (the code converts with `math.deg`), consistent with every other DCS
     `LoGet*` angle/rate call using radians.

4. **Other telemetry for the law.**
   - **True airspeed vector.** No dedicated "TAS vector" call exists separately from
     `LoGetVectorVelocity` (ground-relative world velocity, per finding 2) and
     `LoGetTrueAirSpeed`/`LoGetIndicatedAirSpeed` (scalars, already read by `read_measured()`).
     Deriving an airspeed *vector* (accounting for wind) would need `LoGetVectorWindVelocity`
     (listed in `Sim_ControlAPI.md:547`, never called anywhere in this project, shape unknown)
     subtracted from `LoGetVectorVelocity` — **evidence: inferred (the subtraction is the obvious
     construction), absent (no probe has called `LoGetVectorWindVelocity` or confirmed its
     frame/units, which by the same reasoning as finding 2 would need its own y-axis-style sanity
     check before trusting x/z)**.
   - **`LoGetAngleOfAttack`/`LoGetAngleOfSideSlip`** exist in the same `allow_ownship_export` tier
     as every other confirmed getter (`Sim_ControlAPI.md:518-519`), but **no probe has called
     either on the Mi-24P**, and the slip-ball recon's own finding on the adjacent
     `LoGetSlipBallPosition` is a direct warning sign: that call **returns `nil` on this module**,
     confirmed live 2026-11-20 (`2026-11-20-slip-ball-recon.md`, calibration flight). A helicopter
     has no vaned AoA vane the way a fixed-wing module does, so `LoGetAngleOfAttack` returning
     `nil`/garbage on the Mi-24P is at least as likely as the slip-ball case, not merely possible.
     — **evidence: absent (no data) / inferred (the nil-risk, by analogy with the sibling call that
     already failed on this exact module)**.
   - **`LoGetADIPitchBankYaw`** — already confirmed live and already read by `read_measured()`
     (pitch/bank in radians); no new finding needed here.
   - **`LoGetSlipBallPosition`** — confirmed **dead** on the Mi-24P (returns `nil`), use cockpit
     draw args 943 (pilot)/784 (operator) instead, sign/scale now measured
     (`2026-11-20-slip-ball-recon.md` calibration flight, 2026-11-20). Not itself part of this
     question's scope (acceleration/velocity frames) but the same fallback posture — prefer a
     measured draw-arg read over an Lo-API call with an unverified or already-disproven return —
     applies to `LoGetAngleOfAttack`/`LoGetAngleOfSideSlip` above.

5. **The existing M0-A log data does not settle x/z for either `LoGetVectorVelocity` or
   `LoGetAccelerationUnits`, and no raw log file is present to re-derive it from.** The flight logs
   underlying `2026-11-18-bl16-m0-flight-axes-findings.md` (`aircraft_layer_probe_flight_axes.log`
   and its successors) are not checked into the repo (gitignored, live on the Windows/collector
   box) — only the reduced findings document is. The y-axis conclusions above were reachable
   because the findings doc already reports the specific correlations needed; the x/z axes were
   never reported because the flights that produced them never isolated a maneuver that would
   distinguish north/east or longitudinal/lateral. **A new probe flight is needed**, not a
   re-reduction of existing data.

### Reproducible Test

Not run this session — no DCS install reachable. This is the M0-E step-response probe the plan
already calls for (`plans/flight-control/plan.md` row "M0-E | step response: a 0.05 step on each
enabled axis from captured, 2 s, then back | sign, rough gain and lag recorded"), extended with two
extra log fields so the same flight also answers this note's two open items. No new probe script
is strictly required — `Export.probe-flight-axes.lua` already dumps `vx/vy/vz` and `ax/ay/az`
per-frame (lines 272-277) — but the **maneuver set** needs to isolate what M0-A's incidental cruise
data could not:

| maneuver | what it settles |
|---|---|
| **Steady heading, straight and level, note compass heading** (e.g. flying due north) | `LoGetVectorVelocity().x`/`.z` sign against a known heading — if `x` grows while `z` stays ~0 on a northbound heading, `x` is forward/north; repeat on an eastbound heading to pin `z`. |
| **Level accel/decel** (push collective/nose over briefly, then recover) | correlates `ax` (longitudinal specific force) against the airspeed change — settles `x`'s sign (accelerating forward should read positive `ax` if `x` is "nose-forward positive") and gives a first gain number for `K_TILT_FROM_AX`. |
| **Climb and descent, steady rate** | cross-checks `ay` against the already-known vertical-speed sign; in steady, wings-level climb `ay` should read slightly *below* 1 g at the start of the climb (accelerating the rotor's lift reaction) and return toward 1 g once the climb rate is steady — a weaker signal than finding 1's bank-excursion data but confirms the sign independently. |
| **Steady banked turn, known direction (e.g. right turn)** | correlates `az` (lateral specific force) and `ay` together against a *known* turn direction — settles `z`'s sign and gives the law's still-placeholder `K_TILT_FROM_AZ_SATURATED`/lift-vector-correction gains a real number instead of the first-cut guess. |
| **Pedal yaw step, wings level, no bank** (reuses M0-B's own pedal step shape) | isolates `az` from pure yaw with no bank, to separate "lateral accel from sideslip" from "lateral accel from bank" in the turn maneuver above. |
| **Call `LoGetAngleOfAttack()`/`LoGetAngleOfSideSlip()` once per frame and log the raw return**, same `debug_dump` pattern already used for `LoGetSelfData` | settles whether either is usable at all on this module (nil-risk per finding 4) before any law term is built on them. |

Log fields needed (all already dumped by the existing probe, or trivial one-line additions): `t`,
heading (`LoGetSelfData().Heading` or `LoGetMagneticYaw`), bank/pitch
(`LoGetADIPitchBankYaw`), IAS/VS (`LoGetIndicatedAirSpeed`/`LoGetVerticalVelocity`), `vx/vy/vz`
(`LoGetVectorVelocity`), `ax/ay/az` (`LoGetAccelerationUnits`), plus the two new raw dumps for AoA/
AoSS. Readout/report pattern, reusing the slip-ball calibration card's shape (status line + a curl
loop sourcing `run-scripts/petrobrain.env` and `$DCS_COLLECTOR_IP`, never a literal IP):

```sh
source run-scripts/petrobrain.env
while true; do curl -s http://$DCS_COLLECTOR_IP:7791/flight_control/latest | python3 -c "import sys,json; d=json.load(sys.stdin) or {}; print(d.get('t'), d.get('fc_vx'), d.get('fc_vy'), d.get('fc_vz'), d.get('fc_ax'), d.get('fc_ay'), d.get('fc_az'))"; sleep 0.5; done
```

(This assumes `flight_control.lua`'s status push grows `fc_vx`/`fc_vy`/`fc_vz`/`fc_ax`/`fc_ay`/
`fc_az` fields — a wire-shape decision for Architect/Implementer, not made here. Today's status
feed does not carry these; the M0-A probe's own debug log is the only place they are currently
dumped, and that probe is a separate deployable from `flight_control.lua` itself.)

### Possible Approaches

- **Prefer `LoGetAccelerationUnits`'s y-axis (confirmed body-frame load factor) over the numerical
  IAS/VS derivative for the vertical/lift-vector channel now** — it is already body-frame specific
  force, already known-signed (positive ≈ 1 g in level flight, varies with maneuvering load), and
  is exactly "what the pilot feels" per the user's own framing. This removes one of the two
  `TAU_ACCEL_FILTER_S`-filtered derivative terms (`a_z_f`) without waiting for a further probe.
- **Keep the numerical-derivative fallback for `a_x` (longitudinal) and anything using
  `LoGetAccelerationUnits().z` (lateral) until the M0-E maneuver set above runs** — x/z sign and
  scale are inferred only, and a wrong sign there is a worse failure than the filtered-derivative
  fallback the law already has (slow but not backwards).
- **Use `LoGetVectorVelocity`'s world-frame y (confirmed) freely**, but keep deriving ground-track/
  heading-rate information from `LoGetSelfData().Heading` and `LoGetAngularVelocity` as the law
  already does, rather than trying to recover heading from `vx`/`vz` — the axis identity for those
  two components is still inferred-by-convention, not measured for this specific call.
- **Do not add `LoGetAngleOfAttack`/`LoGetAngleOfSideSlip` to the law speculatively.** Log them
  once (cheap, same dump pattern as every other getter this project has probed) during the M0-E
  flight; if either returns `nil` or garbage (the slip-ball precedent), drop them the same way
  `K_beta`'s Lo-API route was dropped in favour of the draw-arg read.
- **If a flight to re-run M0-E is not available soon, a narrower one-maneuver probe (just the
  "known heading, straight and level" row) is enough to settle `LoGetVectorVelocity`'s x/z
  identity alone**, independent of the fuller step-response flight the control-law gains still
  need — worth doing first and separately if flight time is scarce, since it is the cheapest item
  on this list and unblocks the world-frame velocity vector for other consumers (e.g. a true
  ground-track heading cross-check) immediately.

### Unresolved

- **`LoGetAccelerationUnits().x`/`.z` sign and scale** — inferred as "longitudinal"/"lateral" by
  name only; no maneuver has isolated either. Resolved by the level accel/decel and banked-turn
  rows above.
- **`LoGetVectorVelocity().x`/`.z` axis identity (north/east, or some other convention)** —
  inferred by analogy with this project's general DCS-coordinate convention, not measured for this
  specific call. Resolved by the known-heading row above.
- **Whether `LoGetAngleOfAttack`/`LoGetAngleOfSideSlip` return anything usable on the Mi-24P** —
  absent; the slip-ball precedent (a sibling Lo-API call returning `nil` on this exact module) is a
  real warning, not a confirmed failure for these two specifically.
- **`LoGetVectorWindVelocity`'s frame/shape** — never called by this project; would need its own
  sanity check (same class as `LoGetVectorVelocity`'s y-axis check) before a true-airspeed-vector
  construction could be trusted.
- **DCS version this would be re-measured against** — not stated anywhere checked this session;
  confirm against `dcs.log`'s header or `autoupdate.cfg` the next time the Windows box is reachable,
  per this role's own standing instruction to record version provenance per probe.
