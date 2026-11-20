# Helicopter flight dynamics and physics, for BL-16 mode 1 lift-vector control law

**Date:** 2026-11-20
**DCS version:** not applicable to most of this note — this is general/real-world helicopter
physics research, not a DCS probe. Where DCS/Mi-24P-specific claims appear (rotor direction, SAU,
DCS flight-model community reports), they are forum material, not locally verified, and version
not checked.
**Theatre:** not applicable.

### Question

`plans/flight-lift-vector/plan.md` (BL-16 mode 1 lift-vector law, stage 1, no SAU) designs a
control law around: cyclic tilts the lift vector, collective sets its length, pedals fly the slip
ball, and a chain of absorbers gives way under limits (speed, then turn rate, then height for an
ordinary manoeuvre; height, then speed, then turn rate for a break). The plan rests on specific
physics claims — body-rate vs. Euler-rate kinematics in a turn, torque/pedal coupling with speed,
why slowing down needs both pitch-back and less collective, RPM droop and retreating-blade stall as
one mechanism, VRS as a separate boundary. This investigation checks those claims against the
general helicopter-flight-dynamics literature (not a DCS probe — the plan already routes the
DCS-specific unknowns to LV-0) and surfaces anything from the physics that the plan does not yet
account for.

### What this means for the lift-vector law

- **The body-rate/Euler-rate claim in the plan is exact kinematics, not a hypothesis.** The
  standard aircraft kinematic transform (ZYX Euler sequence) gives, for pitch ≈ 0 (a non-climbing
  turn): `q ≈ ψ̇·sinφ`, `r ≈ ψ̇·cosφ`, `p ≈ φ̇`. At 60° bank this is exactly `q ≈ 0.87·ψ̇`,
  `r ≈ 0.5·ψ̇` — matching the plan's own numbers (§ "What reading the code turned up"). This raises
  confidence in LV-1's planned fix (damp and read turn rate on Euler rates) **once LV-0 confirms**
  `LoGetAngularVelocity` returns body rates, not Euler rates. See Findings 1, 10.
- **"Slowing down is always pitch back and also less collective" (the user's rule, plan §G) has a
  textbook mechanism, not just a Mi-24 habit.** Blade loading (hence RPM droop risk and
  retreating-blade-stall margin) rises with both load factor *and* forward speed (dynamic pressure
  on the retreating blade). Cutting collective lowers blade loading directly; pitching back trades
  speed for height, which only helps indirectly (lower speed → more stall margin, but only once
  speed has actually dropped — collective is what drops blade load immediately). This supports the
  plan's "less collective is the direct lever, pitch-back is the energy trade" framing. See
  Finding 6.
- **A risk the plan does not yet name: induced-power-with-load-factor is nonlinear (∝ n²), not
  linear.** The plan's lift-length feed-forward `u_c,ff = K_L(V)·(n_d − 1)` is linear in `n_d`. At
  low bank this is a fine local approximation; at a 60° break (`n ≈ 2`) the *power*, and so the
  rotor's actual demand on RPM, is already 4× the level-flight figure by momentum theory, growing
  faster than the lift-length feed-forward's linear term suggests. This does not invalidate the
  approach (the integrator corrects whatever the feed-forward misses, by design, finding E), but it
  is worth Architect/Implementer knowing that `K_L` may need to taper at high bank rather than stay
  constant, if LV-2's break card shows a collective lag that scales with bank rather than being
  roughly constant. See Finding 9.
- **ADS-33's response-type ladder (rate command → attitude-command/attitude-hold → translational
  rate command as cues degrade) is exactly the shape of the plan's own "Stage 2 seam" and its `λ`
  blend.** The plan's inner loop today is attitude-command-like (`target − attitude` feedback with
  rate damping); the SAU stage (trim-hold, released during a change) is the real-world analogue of
  ACAH-with-trim-follow-up used on several real autopilots (Black Hawk's modernized control laws use
  ACAH in pitch/roll, rate command direction hold in yaw, and switch to pure rate command past
  attitude/rate limits). This is independent confirmation that the planned stage-2 SAU seam (inner
  attitude loop only) is the conventional place to add it. See Finding 11.
- **Mast bumping is correctly ruled out** — the Mi-24's main rotor is a 5-blade, individually hinged
  (articulated) rotor, not a 2-blade teetering rotor; mast bumping is a teetering-rotor-specific
  hazard (flapping hinge coincides with the mast, so excessive flap angle lets the hub strike the
  mast). Nothing in the law needs to watch for it. See Finding 7.
- **Dynamic rollover is a near-ground, skid/wheel-pivot hazard (take-off/landing), not an in-flight
  one** — it needs a point of the airframe pinned to the ground while collective is pulled. It is
  out of scope for a law that only reads in-flight telemetry, unless a later milestone adds ground
  handling. Not a gap in this plan. See Finding 8.
- **VRS's envelope (low forward speed + a sufficient descent rate) is a genuinely separate boundary
  from retreating-blade stall (high forward speed + load factor + low RPM)** — opposite ends of the
  speed axis. The plan's envelope guards (Decision 28 RPM, Decision 31 VRS, blade-stall IAS margin)
  already treat them as separate caps, which the literature supports; no two of these should ever be
  collapsed into one "margin" number. See Finding 5.
- **One unresolved real-world nuance the LV-1/LV-2 cards should watch for, not architecturally
  consequential:** VRS's most commonly cited numeric boundary (descent > ~300–500 fpm below ~30 kt)
  is itself contested across sources (figures range with disc loading and type), so the plan's
  `VRS_*` constants (kept, not re-derived here) should be treated as DCS-flight-model-specific
  tuning, not a transferable physics constant. See Finding 5.

### Findings

1. **Euler-rate kinematic transform in a steady, non-climbing turn: `q ≈ ψ̇·sinφ`, `r ≈ ψ̇·cosφ`,
   `p ≈ φ̇`.** This is the standard ZYX Euler-angle-rate-to-body-rate relation used throughout flight
   dynamics (Stevens & Lewis, *Aircraft Control and Simulation*; Padfield, *Helicopter Flight
   Dynamics*, ch. 3 kinematics). — **evidence: documented** (textbook-standard aircraft kinematics,
   confirmed by general knowledge and cross-checked against secondary sources below) — **source:**
   general flight-dynamics textbook kinematics (Stevens & Lewis; Padfield ch. 3); corroborating
   secondary material: a UAV coordinated-turn paper giving `r_body = (g·tanφ/V)·cosθ·cosφ`
   ([arXiv:2301.00730](https://arxiv.org/pdf/2301.00730)), a US patent on attitude-drift-during-turns
   giving the steady-turn roll-angle relation
   ([US 6456905](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6456905)), and a
   NASA report on coordinated-turn kinematics for helicopters specifically, which notes sideslip
   strongly affects pitch attitude and roll rate
   ([NASA NTRS 19810013509](https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/19810013509.pdf)).
   This matches the plan's own derivation exactly (`plan.md`, "What reading the code turned up",
   items 1–2), so it is corroboration, not new information for the plan — but it upgrades the plan's
   claim from "the architect's own math" to "textbook-standard, independently cross-checked".

2. **Rotor flapping has a phase lag between cyclic input and maximum blade displacement** — exactly
   90° for a 2-blade teetering rotor, 80–90° for a fully articulated rotor with offset hinges
   (closer to 90° as hinge offset shrinks), ~75–80° for semi-rigid. The rotor control system is
   mechanically pre-shifted (pitch-flap coupling / "delta-3", swashplate phasing) to correct for
   this so that stick input direction matches aircraft response direction; the lag is caused by
   blade flapping dynamics, not gyroscopic precession (gyroscopic precession is also 90° but is a
   different, non-causal coincidence; Nick Lappos's PPRuNe post on this is widely cited and matches
   Leishman's treatment). — **evidence: documented** (standard rotor dynamics result) —
   **source:** [Phase lag (rotorcraft), Wikipedia](https://en.wikipedia.org/wiki/Phase_lag_(rotorcraft))
   citing Leishman, *Principles of Helicopter Aerodynamics*, p. 188 (book itself not fetched this
   session — cite is secondhand); PPRuNe thread quoting Nick Lappos
   ([pprune.org thread](https://www.pprune.org/rotorheads/printthread-19744-helicopter-dynamics-phase-angle.html)).
   **Implication for the law:** this is exactly why the plan treats the lift-vector direction as
   "steered, not computed" (plan §D, "the never-known lift vector" test) — the actual mapping from
   cyclic input to disc tilt is a dynamic, lagged, mechanically-corrected relationship the law never
   needs to model explicitly, only observe and correct against. No change recommended; this confirms
   the plan's own framing.

3. **Torque reaction is proportional to main-rotor power/thrust, so tail-rotor thrust demand varies
   with flight condition** — highest torque-compensation demand is typically at high power settings
   (hover, climb, heavy load), and the *pedal position* needed to trim also varies with airspeed
   because of two separate, additive effects: (a) torque compensation itself, and (b) at low speed,
   translating tendency / tail-rotor-induced drift (a steady sideways thrust component that must be
   trimmed out, historically compensated on the Mi-24 by canting the main rotor mast 2.5° — see
   Finding 4) plus weathervaning into relative wind. At speed, torque compensation still varies with
   power, but translating tendency and weathervaning effects diminish as the vertical fin/tail
   surfaces take over directional stability aerodynamically. This is consistent with the user's
   observation that slip varies with speed (`plan.md`/explore-notes), and with the plan's
   speed-scheduled `K_β(V)` pedal gain (§F) rather than a fixed gain. — **evidence:
   forum-claim-unverified for the Mi-24-specific numbers, documented for the general mechanism** —
   **source:** FAA Helicopter Flying Handbook (translating tendency/drift, retreating blade,
   dissymmetry of lift listed as distinct topics —
   [faa.gov PDF](https://www.faa.gov/sites/faa.gov/files/helicopter_flying_handbook.pdf)); general
   mechanism is standard single-main-rotor helicopter theory (Leishman, Johnson).

4. **Mi-24 design-specific torque/drift compensation**: the main rotor mast is canted ~2.5° to the
   right of the fuselage specifically to compensate translating tendency at the hover, and the tail
   boom/fin assembly is asymmetric to produce a side force at speed that unloads the tail rotor (so
   less tail-rotor thrust, and so less pedal, is needed as airspeed rises) — a mechanical reason, on
   top of the generic effects in Finding 3, for pedal need to fall with speed on this specific
   airframe. — **evidence: forum-claim-unverified** (Wikipedia, not a flight manual or ED technical
   source) — **source:** [Mi-24, Wikipedia](https://en.wikipedia.org/wiki/Mi-24). **Implication:**
   corroborates (does not newly establish) the plan's choice to schedule pedal/torque-FF gains by
   speed rather than use one fixed gain; no architectural change suggested.

5. **Vortex ring state (VRS) and retreating-blade stall are separate boundaries at opposite ends of
   the speed envelope, and should never be merged into one "margin" signal.** VRS needs low forward
   airspeed (most commonly cited risk zone below ~30 kt) combined with a sufficient descent rate
   (commonly cited at >300 fpm indicated / >500 fpm true, the gap attributed to ASI/VSI lag and
   error); the exact numbers are disc-loading- and type-dependent and vary across sources. Warning
   signs: sudden uncommanded descent, main-rotor vibration, rising sink rate, reduced cyclic
   authority, "lightness in the seat" at the incipient stage — but a fully developed VRS can also
   feel smooth with little vibration, so sink rate itself may be the only reliable cue. Retreating-
   blade stall, by contrast, needs *high* forward speed combined with high load factor / low rotor
   RPM / high density altitude (see Finding 6) — it is a high-airspeed, high-blade-loading
   phenomenon, the physical opposite end of the envelope from VRS. — **evidence: documented** (the
   mechanism and ordering of effects) **/ forum-claim-unverified** (the specific numeric
   boundaries, which the plan does not use directly anyway — `VRS_*` and the stall-IAS margin are
   kept as existing, presumably DCS-flight-model-tuned constants) — **source:**
   [SKYBRARY, Vortex Ring](https://skybrary.aero/articles/vortex-ring);
   [Wikipedia, Vortex ring state](https://en.wikipedia.org/wiki/Vortex_ring_state); UK CAA-sourced
   AIC via [pprune.org](https://www.pprune.org/9975159-post140.html);
   [Aviation Week, "How to Avoid a Vortex Ring State"](https://aviationweek.com/business-aviation/flight-deck/how-avoid-vortex-ring-state-part-3).
   **Implication:** no change to the plan — it already keeps VRS and blade-stall/RPM as separate
   guards (Decision 31 vs. Decision 28 in the referenced `flight-control` plan). This is confirmation
   the separation is physically correct, worth recording so a future "simplify the envelope" pass
   does not collapse them.

6. **Retreating-blade stall mechanism and contributing factors**: the retreating blade's airspeed
   relative to the air is (rotor tip speed − forward speed), which is lower than the advancing
   blade's; to produce equal lift across the disc the retreating blade must fly at a higher angle of
   attack, and past a critical AoA it stalls. Contributing/aggravating factors, per the FAA handbook
   and Wikipedia's summary of it: high gross weight (→ higher load factor needed → higher AoA
   everywhere), high airspeed (→ lower relative speed on the retreating side for the same rotor
   RPM), low rotor RPM (→ same effect — this is the direct RPM-droop/blade-stall link the user
   named), high density altitude, steep turns (→ higher load factor, same mechanism as gross
   weight), and turbulence. **This directly supports the user's rule** ("slowing down is always
   pitch back and also less collective… blade load is what causes both RPM drop and retreating
   blade stall"): both RPM droop and blade-stall margin are driven by the same underlying variable,
   blade loading, which rises with load factor (bank) and airspeed and falls when RPM rises or
   collective (and so thrust/loading) is reduced. — **evidence: documented** — **source:** FAA
   Helicopter Flying Handbook ch. 11 contents (Translating Tendency/Drift, Retreating Blade,
   Dissymmetry of Lift listed separately —
   [faa.gov PDF](https://www.faa.gov/sites/faa.gov/files/helicopter_flying_handbook.pdf));
   [Retreating blade stall, Wikipedia](https://en.wikipedia.org/wiki/Retreating_blade_stall),
   citing the FAA handbook for the same contributing-factor list.

7. **Mast bumping is specific to 2-blade teetering (semi-rigid) rotors**, where the single flapping
   hinge sits at/near the mast and an excessive flap angle lets the rotating hub strike and
   potentially shear the fixed mast. Fully articulated rotors (individual flap/lead-lag hinges per
   blade, offset from the mast) and rigid/hingeless rotors are not susceptible to this failure mode
   in the same way. The Mi-24's main rotor is a 5-blade, individually-hinged, fully articulated
   system. — **evidence: documented** for the general rotor-type/mast-bumping relationship,
   **forum-claim-unverified** for "Mi-24 rotor is articulated" (secondary sources, not the flight
   manual) — **source:** FAA Helicopter Flying Handbook ch. 4 (rotor systems);
   [Rotorhead, Wikipedia](https://en.wikipedia.org/wiki/Rotorhead); rotor-type claim from
   [aerospaceweb.org Mi-24 page](https://aerospaceweb.org/aircraft/helicopter-m/mi24) and general
   secondary Mi-24 references, not cross-checked against a flight manual this session.
   **Implication for the plan:** confirms the plan's own parenthetical ("not relevant for
   articulated Mi-24 rotors") — no limit/watch needed for mast bumping in this law.

8. **Dynamic rollover is a near-ground hazard, not an in-flight one**: it requires some part of the
   airframe (a skid, a wheel) to be effectively pinned to the ground so the aircraft pivots about
   that point rather than translating freely; collective is then pulled while a roll moment
   (sideways drift, crosswind, uneven ground, a stuck tiedown) exists, and past a critical roll
   angle (commonly cited 5–8°, though this figure is contested — a separate source puts *static*
   rollover near 30°, a different failure mode) main-rotor thrust itself continues the roll and no
   amount of opposing cyclic can stop it; the only recovery is lowering collective (smoothly, not
   abruptly — an abrupt cut can bounce the aircraft onto the other skid and roll the other way).
   — **evidence: documented** for the mechanism, **contested/unresolved** for the exact critical
   angle — **source:**
   [Dynamic rollover, Wikipedia](https://en.wikipedia.org/wiki/Dynamic_rollover);
   [FAA AC 90-87](https://www.faa.gov/documentLibrary/media/Advisory_Circular/ac90-87.pdf);
   [Traficom (Joonas Kursu), Static and Dynamic Rollover](https://traficom.fi/sites/default/files/media/file/11701-Static_and_Dynamic_Rollover%2C_Joonas_Kursu.pdf).
   **Implication:** out of scope for this law, which only reads in-flight telemetry and has no
   ground-contact/skid-pivot model; correctly not in the plan's envelope list. Would only matter for
   a future ground-handling/hover-taxi feature, not mode 1's flight law.

9. **Load factor in a coordinated turn is `n = 1/cos(φ)` (bank angle `φ`)** — exact at 60° bank,
   `n = 2.0`. Because rotor/wing induced power scales with `n²` under simple momentum theory, the
   *induced power* required at 60° bank is roughly 4× the level-flight value, not 2× — power rises
   faster than load factor. This is a standard result (the "turn performance" literature), though no
   source found this session gives a complete helicopter-specific thrust/power-required formula
   combining load factor with rotor profile power and parasite drag at speed — that full treatment
   would need Prouty or Leishman directly. — **evidence: documented** for the `n = 1/cosφ` relation
   and the general momentum-theory `n²` power scaling, **inferred** that this exact `n²` scaling
   applies unmodified to a specific helicopter's power-required curve (profile and parasite power
   terms do not scale the same way, so the real curve is flatter than pure `n²` at realistic speeds)
   — **source:**
   [Hong Kong PolyU coordinated-turns module](https://www.polyu.edu.hk/researchgrp/khng/virtual-lab/modules/coordinated-turns/)
   (n = secφ); a turning-performance reference table via
   [nar-associates.com](https://nar-associates.com/technical-flying/turning/turnprpa_wide_screen.pdf)
   giving 1/cosφ = 2.000 at 60° and noting induced power at 60° bank is ~4× the level-flight value;
   NASA note that for helicopters bank angle and rotor-tilt (normal-load-factor) angle can differ
   markedly in high-load-factor turns
   ([NASA NTRS 19830013934](https://ntrs.nasa.gov/api/citations/19830013934/downloads/19830013934.pdf)).
   **Implication for the plan:** flagged above in "What this means" — `K_L(V)`'s linear-in-`n_d`
   feed-forward is a fine local approximation but may need to taper at high bank if LV-2's break
   card (60–80° bank) shows the collective lag growing disproportionately with bank rather than
   staying roughly constant. Not a blocker; a tuning note for LV-2, not an architecture change.

10. **DCS Mi-24P `LoGetAngularVelocity` axes (x=roll rate, y=yaw rate [positive when heading
    decreases], z=pitch rate)** are already measured and documented locally, not by this
    investigation. — **evidence: reproduced-locally (prior session)** — **source:**
    `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, Flight 1 ("Body rates"
    bullet). Cited here only to note that Finding 1's general kinematic transform is the tool LV-0
    needs to apply to these measured body rates to get Euler rates — this investigation does not
    establish whether the getter itself returns body or Euler rates (that is exactly LV-0's open
    question, correctly not pre-empted here per the plan's "Investigator not invoked" note).

11. **ADS-33E's handling-qualities framework ties control response type to how much visual/outside
    reference the pilot has**: as usable cues degrade, the required response type escalates from
    rate command, through attitude-command/attitude-hold (ACAH, alongside rate-command/direction-
    hold or height-hold depending on task), to translational-rate command, to keep Level 1 handling
    qualities. Quantitative ADS-33 metrics (bandwidth, phase delay) do not always match pilot
    opinion — one study found a design meeting Level 1 criteria was still rated "over-damped" and
    "sluggish" by test pilots. Real implementations (cited: Black Hawk's modernized control laws)
    use ACAH in pitch/roll with rate-command-direction-hold in yaw, switching to pure rate command
    once velocity/attitude limits are exceeded — an outer/attitude-hold, inner/rate-damped structure
    with an explicit "give way to rate command at the edges" rule. — **evidence: documented**
    (ADS-33E's response-type requirement is a named military-handling-qualities standard, confirmed
    via secondary academic/NASA sources; the standard's own text was not fetched this session) —
    **source:**
    [NASA/Theodore 2014, DVE ACAH study](https://rotorcraft.arc.nasa.gov/Publications/files/Theodore_2014.pdf);
    [AHS/Berger 2021, pitch rate-command/attitude-hold pilot-opinion study](https://oucampustest.sjsu.edu/researchfoundation/docs/VFS_2021_Berger.pdf);
    [AHS/Berger 2011, OH-58D lagged-rate ACAH retrofit](https://gcp-web.sjsu.edu/researchfoundation/docs/AHS_2011_Berger.pdf).
    **Implication:** confirms (does not newly establish) that the plan's inner attitude loop
    (ACAH-shaped) is the conventional place for the stage-2 SAU seam, and that "the inner loop gives
    way to something cruder once limits are hit" (the plan's priority chain, §G) mirrors how real
    fly-by-wire systems are structured, not an ad hoc Petrobrain invention.

12. **Mi-24 rotor specifications are inconsistently reported across secondary sources and were not
    confirmed from a primary manual this session**: main rotor diameter ~17.3 m, 5 blades, 3-blade
    tail rotor is consistent across sources; main rotor RPM (one source: 240 rpm) has no second
    corroborating source; cruise speed figures range 270–295 km/h and max speed 320–335 km/h across
    sources, with no Vne figure found. — **evidence: forum-claim-unverified** — **source:**
    [aerospaceweb.org Mi-24](https://aerospaceweb.org/aircraft/helicopter-m/mi24);
    [Red Star Mi-24P page](https://www.redstar.gr/en/russian-aerial-means/helicopters/russian-helicopters-mil/mi-24p-multipurpose-assault-helicopter.html);
    [weaponsandwarfare.com Mi-24](https://weaponsandwarfare.com/?p=21465). **Implication:** none of
    the plan's gains or limits need an absolute RPM/speed number from these sources — the existing
    `flight_control.lua`/`defaults.toml` constants (RPM floor, stall IAS margin, max bank, etc.) are
    presumably already tuned against the DCS flight model directly, which is the right source for
    them, not these secondary web figures. Flagged only so nobody later cites "240 rpm" as a
    confirmed design figure.

13. **Mi-24 "podkhvat" (pitch-up) at high speed, and a reported retreating-blade-stall-induced
    roll-over above a stated threshold, are recurring themes in the DCS forum community for this
    specific module**, consistent with Finding 6's general mechanism. One DCS forum poster: *"From
    200 kmh to max speed there is a pitch up behavior called 'Podkhvaht'... the manual places a
    heavy speed restriction on this, the faster you are the more you should limit G."* A separate
    thread, about a roll-over during a rocket-attack dive: *"It's almost certainly a retreating
    blade stall... generally you'll roll over in a retreating blade stall after [an airspeed the
    poster was unsure of, estimated]."* — **evidence: forum-claim-unverified** (both quotes are
    user reports on the DCS forum, not ED documentation or a flight-manual excerpt) — **source:**
    [DCS forum, "Mi-24P flight characteristics"](https://forum.dcs.world/topic/336740-mi-24p-flight-characteristics);
    [DCS forum, "started to roll out of control after shooting rockets"](https://forum.dcs.world/topic/275169-started-to-roll-out-of-control-after-shooting-rockets).
    **Implication:** this is a candidate real-world/DCS-model symptom the plan's envelope guards
    (blade-stall IAS margin, `MAX_ACCEL_MPS2`, bank limits) should already be covering generically;
    it does not suggest a new guard, but it is a concrete DCS-specific failure mode worth keeping in
    mind if LV-2's break card (which flies 60–80° bank at up to 250 km/h) ever shows an
    uncommanded roll — the forum consensus attributes that specific symptom to retreating-blade
    stall, not a control-law bug, and "rolling away from the stall" (opposite cyclic) is reported to
    make it worse rather than better, which the law's priority chain already avoids by giving speed
    and turn rate before it ever saturates cyclic further into a stalled condition.

14. **SAU channel behaviour and trim semantics as described by the user (explore-notes.md) are
    consistent with general real-world helicopter stability-augmentation-system (SAS) design** —
    attitude/rate-damping channels that can be "re-zeroed" to the current attitude on a trim-release
    event, overridable by control input, intended to relieve constant small corrections rather than
    fly the aircraft autonomously — and with scattered DCS-forum reports specific to the Mi-24/Mi-8
    AP-34-family system (trim-button behaviour differs between Mi-8 and Mi-24: Mi-8's AP servos are
    reported unaffected by trim, Mi-24's pitch/bank channels reportedly reset to zero on trim-button
    press). — **evidence: forum-claim-unverified** for the Mi-24/Mi-8-specific trim differences —
    **source:** [DCS forum, "the hind and the ap channels"](https://forum.dcs.world/topic/307703-the-hind-and-the-ap-channels);
    [DCS forum, "yaw sas"](https://forum.dcs.world/topic/274482-yaw-sas). **The user's own
    first-hand account in `explore-notes.md` ("SAU in mode 1") is the higher-confidence source for
    this project** — it is a direct report of flying the aircraft, not a secondhand forum claim, and
    the plan already treats it that way. This finding only notes that it is not contradicted by,
    and is broadly consistent with, how real SAS/trim systems are described in the general and
    DCS-community literature.

### Reproducible Test

None — this was desk research against the real-world and DCS-community literature, not a probe.
The physics claims that matter mechanically to the law (body-rate vs. Euler-rate frame, velocity
source axes/sign, the ball calibration) are already correctly routed to LV-0's live-flight card in
the plan, not to this kind of research — see the plan's "Investigator not invoked (step 3)" note,
which this investigation does not override. The general kinematic transform in Finding 1
(`q = θ̇cosφ + ψ̇cosθsinφ`, `r = -θ̇sinφ + ψ̇cosθcosφ`, `p = φ̇ - ψ̇sinθ`) is the formula LV-0's
analysis should apply once it has measured which frame `LoGetAngularVelocity` returns.

### Possible Approaches

- If LV-0 or LV-2's cards show the collective feed-forward (`K_L·(n_d−1)`) lagging more at high
  bank than at low bank (Finding 9), the fix suggested by the physics is a mild power-law or
  piecewise taper on `K_L(n_d)` rather than a constant gain — still a "nudge, not a model" per the
  plan's own framing, just a nudge shaped to match how induced power actually grows with load
  factor. This is a tuning change within the existing design, not a new mechanism.
- No other finding here suggests adding a new guard, signal, or loop to the plan. The main value of
  this research is *confirmation* (Findings 1, 2, 6, 7, 11) and *one tuning flag* (Finding 9) for a
  plan whose structure already matches how real flight-control systems are built.

### Unresolved

- **Mi-24 primary documentation (flight manual, AP-34 technical description) was not reached.**
  Every Mi-24/Mi-8-specific claim here (rotor RPM, trim/SAU behaviour details, mast cant angle,
  asymmetric tail) rests on Wikipedia and DCS-forum secondary sources, not a flight manual or ED's
  own technical documentation. None of it is load-bearing for the plan (the plan already treats the
  user's own flying experience, and LV-0's live measurements, as the authoritative source for
  anything DCS-specific) — flagged so it is not later cited as more authoritative than it is.
- **No complete helicopter-specific power-required-vs-bank-angle formula was found** (Finding 9)
  combining induced, profile and parasite power at a given airspeed and load factor. If `K_L`'s
  high-bank taper (above) ever needs a principled shape rather than a card-tuned one, Prouty's
  *Helicopter Performance, Stability, and Control* or Leishman's *Principles of Helicopter
  Aerodynamics* (neither fetched this session — both are copyrighted texts, not freely available
  online) would be the next source to check.
- **ADS-33E's own text (bandwidth/phase-delay Level 1/2/3 boundaries) was not fetched** — Finding 11
  rests on secondary NASA/AHS papers describing and applying the standard, not the standard itself.
  Not load-bearing for this plan (stage 2/SAU is out of scope for this stage), but worth fetching
  directly if the SAU stage later wants a quantitative handling-qualities target rather than "flies
  like the user describes."
