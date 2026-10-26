# BL-16 flight-control desk recon: SAU channels, axis-write obedience, and read-side shapes

**Date:** 2026-10-26
**DCS version:** not verified locally this session — no DCS install reachable (Mac dev machine,
`DCS_INSTALL_PATH` unset). This project's own most recent live-confirmed version for this cockpit
surface is **2.9.30.28738** (`2026-10-22-9k113-ai-axis-obedience-prior-art.md`, from the probe log
headers); the command-surface enumeration this note leans on most (`mi24p-command-surface.md`) was
generated against **2.9.29.27278**. Treat anything below sourced from those files as that old, not
re-verified this session.
**Theatre:** n/a — cockpit/scripting-API question, not terrain.

### Question

Desk-only reconnaissance (no live DCS, no user flying) to narrow the stage-0 Windows probe
`BL-16` already calls for (`body-layer/ROADMAP/BL-16.md`, "Before any plan: measure"): what the
Mi-24P SAU channels/modes actually are and what ED's own material says is or isn't implemented;
how trim/special-options affect the joystick-axis-to-cyclic relationship; whether anyone has
prior art driving flight axes from `LoSetCommand`/`Export.lua` and what obedience/override
behaviour they found; the exact read-side shapes for the listed `LoGet*` calls and for pilot
control-position readback; and the radar altimeter's range/validity envelope.

### Findings

**1. SAU (device 10, `AUTOPILOT`) channels K/H/T/B, authority, and documented gaps**

- `autopilot_commands` (`mi24p-command-surface.md` §10, ids 3001–3072) enumerates `ButtonK*`,
  `ButtonH*`, `ButtonT*`, `ButtonB*` on/off pairs (each with an `*EXT` twin), plus `Trimmer`/
  `TrimmerMULT`, `DeltaK`/`DeltaH`/`DeltaT` (no `DeltaB`), `RouteAngle`/`RouteAngleAXIS`,
  `HeightOn/Off`, `HoverOn`, `RouteOn`, `SpeedOn/Off`, `AutopilotOff`/`AutopilotOffOP` (operator
  seat has its own kill switch), `Friction`, and an `External_*` block (3051–3067:
  `External_Roll`/`Pitch`/`Yaw`/`ADP_*`/`Speed`/`Radio_Altitude`/…) that looks like a second,
  avionics-bus-style input surface into the same device — untested, not discussed anywhere else in
  this project's research. — **evidence: reproduced-locally** (command IDs only; no semantics) —
  **source:** `aircraft-layer/research/mi24p-command-surface.md:987-1060`.
- **K/H/T/B letter mapping, resolved:** multiple independent ED-forum snippets agree —
  `H`=yaw (Направление), `K`=roll (Крен), `T`=pitch (Тангаж), `B`=altitude (Высота). One forum
  user's phrasing: *"in the English cockpit... H is yaw, K is roll, T is pitch, and B is
  altitude"*, attributing the English labels to the Russian originals. — **evidence:
  forum-claim-unverified** (WebSearch snippets of `forum.dcs.world/topic/274656`, not independently
  read — see Unresolved) — **source:** WebSearch results for that thread and
  `forum.dcs.world/topic/319297`. This is consistent with, and resolves, the project's own
  shorthand in `plans/flight-control/explore-notes.md` ("pitch, bank and yaw... course when course
  mode is on... altitude hold, not so well") — course mode is almost certainly the `H` (yaw)
  channel engaged with `RouteOn`/`RouteAngle`, and the altitude channel the user flagged as weak is
  `B`.
- **Modes.** Chuck's Guide (a well-regarded third-party DCS manual, not ED's own) lists, as section
  headings only (content not extracted — paywalled behind its PDF, see Unresolved): *Autopilot
  Overview*, *AFCS Overview*, *Trim Options*, *Anti-Torque Pedal Microswitches*, and under
  *Autopilot Operation*: *Flying With Trim*, *Hover Control Mode*, *Altitude Hold Mode*,
  *Route/Course Mode*, *Speed Hold Mode*. — **evidence: forum-claim-unverified** (table of contents
  only; no body text read) — **source:** `https://chucksguides.com/aircraft/dcs/mi-24p/`. This is
  the first evidence this session found that **a Speed Hold Mode and an Altitude Hold Mode are
  named, documented features of the module** (not merely "possibly not implemented" as the user's
  recollection of an older DCS document had it) — it does not say how well either holds, which is
  exactly the open question the user already flagged.
- **Corroborating, unofficial numeric claims** (forum snippets, explicitly lower-confidence than
  the above): one poster reports Mi-8/17 documentation gives speed-hold tolerance of **±10 km/h**
  and the Mi-24 **±5 km/h**; another reports the indicated-airspeed controller **does not engage
  below ~150 km/h IAS**. A third reports **altitude hold sometimes refuses to engage unless the
  other three channels (K/H/T) are already on**. — **evidence: forum-claim-unverified** — **source:**
  WebSearch snippets of `forum.dcs.world/topic/337425`, `/topic/294928`, `/topic/285970` (none
  independently fetched — all three 403'd when tried directly, see Unresolved).
- **Trim/`Trimmer` interaction with the attitude-hold reference — two claims found, in apparent
  tension, neither independently verified:**
  1. *"pressing trim cancels the autopilot, releasing it holds the attitude you're at when
     released"* — i.e. holding `Trimmer` suspends the K/H/T hold, and releasing it re-references
     the hold to whatever attitude the aircraft is at that instant.
  2. *"the trim hat tells the autopilot a new center position but does not update the pitch/roll
     attitude hold"* — i.e. trim only changes where the force-trim spring centers, leaving the SAU's
     own attitude target untouched.
  One other forum thread title (`315954`, "flight model over trimmed if trim pressed") and a
  cross-aircraft comparison (`340834`, *"the Mi-8's trim button doesn't affect the autopilot, while
  the Mi-24 combines the attitude-reset job with the trim button"*) both point toward claim 1 being
  closer to the Mi-24P's actual (if buggy/jarring) behaviour. — **evidence:
  forum-claim-unverified, with an internal disagreement** — **source:** WebSearch snippets of
  `forum.dcs.world/topic/315954`, `/topic/340834`, `/topic/356308`, `/topic/48733` (all 403'd
  direct-fetch; see Unresolved). **This is squarely a stage-0 probe item, not settleable from the
  web** — BL-16's own explore-notes already ask it ("does `Trimmer` re-reference the hold?") and
  nothing found here resolves the contradiction.

**2. Special options / trim modes vs. axis-to-cyclic relationship**

No ED documentation, manual excerpt, or forum thread found this session states explicitly whether
DCS's "trimmer" special option (central-spring-return joystick vs. non-self-centering/FFB) changes
whether a given `LoSetCommand(2001, v)` write is read by the flight model as an **absolute** cyclic
position or as an offset **relative to** a trim datum. The forum material found (§1 above) describes
only the *in-cockpit* trim button/hat, which is a distinct mechanism from the DCS *options-menu*
joystick-centering setting this question is actually asking about — the search did not surface
discussion of the latter for this module at all. — **evidence: absent.** This question is
**unresolved by desk research** and squarely a Windows-probe item: command a known `LoSetCommand`
value, read back `LoGetADIPitchBankYaw`/control-surface or stick-draw-argument state, and repeat
with the pilot's "central position trimmer" option toggled, to see if the same write produces a
different aircraft response.

**3. Prior art driving flight axes from `Export.lua`/`LoSetCommand`**

- **`LoSetCommand` for the global flight-axis iCommands (2001-2004, 2022-2024) is itself
  first-party documented and not deprecated**, per this project's own prior finding: `Scripts/
  Export.lua:854` plus `API/Sim_ControlAPI.md:538`'s "available only when sensor export is
  allowed" list — this settles the long-running "`LoSetCommand` deprecated?" forum doubt in the
  negative, **as far as shipped docs for 2.9.29 go**. — **evidence: reproduced-locally** —
  **source:** `mi24p-command-surface.md` §1, `§8`.
- **No one in the DCS community has published a working recipe for driving an AI-contended or
  player-flown control axis externally and documented the obedience/override rule**, mirroring
  exactly what this project already found for the 9K113 AI slew axis: searches for
  George/Jester-AI device-level driving, and specifically for flight-axis `LoSetCommand` persistence
  against a live joystick, returned either nothing on-topic or snippets about unrelated trim bugs.
  One forum post is the closest analogue found: the *DCS Helicopter Assist* project's author
  advises **unbinding the physical joystick axis from DCS entirely and routing input through a
  virtual (vJoy) device** specifically *"to avoid double control"* — i.e. the community's own
  practical answer to "does a script write fight the physical stick" is **don't let both write at
  once**, not "the engine arbitrates it cleanly." — **evidence: forum-claim-unverified** —
  **source:** WebSearch snippet of `forum.dcs.world/topic/378853` ("I created a helicopter assist
  for people who only have Xbox controllers"), not independently fetched (403'd).
- **This project's own 9K113 AI-axis finding is the closest first-party evidence of the *shape* of
  the problem, on a different device/channel but the same engine**: a per-poll external write and a
  native AI writer can both target the same control, and when they do, "whichever writer the engine
  applies last on a given frame wins," producing an all-or-nothing-per-frame contention pattern with
  no exposed arbitration state. — **evidence: reproduced-locally (on the AI-sight axis, not the
  flight axes)** — **source:**
  `aircraft-layer/research/2026-10-22-9k113-ai-axis-obedience-prior-art.md`, finding 1. **This
  generalises as a hypothesis, not a fact, to the flight axes**: whether `LoSetCommand(2001…)`
  against a live physical joystick behaves the same way (frame-order contention) or differently
  (e.g. the engine sums/blends axis sources, or one source is authoritative by design) is exactly
  BL-16's stage-0 question and is **not answered** by the 9K113 case, which is a cockpit-device
  command channel (`GetDevice():SetCommand`), not the global iCommand channel flight axes use.
  Do not assume the two channels share a dispatch mechanism without testing — they are documented
  as structurally different (`mi24p-command-surface.md` §1's "two command channels" table).
- **No source found (project-internal or web) states what happens to a `LoSetCommand`-driven axis
  once writes stop** — snap back to the physical stick's current position on the next frame, hold
  the last written value until the next physical movement, or something else. **Absent**, and a
  stage-0 probe item.

**4. Read-side shapes (`Sim_ControlAPI.md`) and pilot control-position readback**

- **`aircraft-layer/research/reference/Sim_ControlAPI.md` is a bare function-name listing by
  export-permission tier — it documents no return shapes, units, or argument signatures for any
  `Export.Lo*` call**, including every getter named in the question (`LoGetVerticalVelocity`,
  `LoGetAngularVelocity`, `LoGetAccelerationUnits`, `LoGetVectorVelocity`, `LoGetSlipBallPosition`,
  `LoGetMagneticYaw`, `LoGetMechInfo`, `LoGetRadarAltimeter`). Checked directly: grepping the file
  for `args -`/`results -`/`returns` near any of these names returns nothing; the only lines near
  them are the permission-tier headers (`Sim_ControlAPI.md:504-551`). — **evidence:
  reproduced-locally (the absence itself — confirmed by direct read, not inferred)** — **source:**
  `aircraft-layer/research/reference/Sim_ControlAPI.md:500-551`.
- **Three of the eight are already confirmed live, for this exact module, by this project's own
  deployed `Export.lua`** — the one piece of actual evidence here:
  - `LoGetSelfData()` — ownship position + true heading (comment at
    `dcs-export/Export.lua:20`, used at line 1507/1948).
  - `LoGetADIPitchBankYaw()` — pitch/bank/yaw, **radians** (comment at line 21, used at line
    1511/1977).
  - `LoGetRadarAltimeter()` — **metres + a validity flag** (comment at line 24, used at line 1980)
    — "not always valid" is the script's own comment, consistent with every altitude-based
    system having a no-signal/out-of-envelope case.
  — **evidence: reproduced-locally** — **source:** `aircraft-layer/dcs-export/Export.lua:20-24,
  1507-1980`.
- **The other five** (`LoGetVerticalVelocity`, `LoGetAngularVelocity`, `LoGetAccelerationUnits`,
  `LoGetVectorVelocity`, `LoGetSlipBallPosition`, `LoGetMagneticYaw`, `LoGetMechInfo`) **have never
  been called anywhere in this project's code**, and this session found no community source
  (Hoggit wiki search, GitHub code search) giving their return shape either — the WebSearch results
  for `LoSetCommand`/flight-axis topics returned nothing about these getters at all. — **evidence:
  absent.** Likely shapes can be *inferred* from the DCS scripting convention used by the three
  confirmed getters above (a flat table of named fields, SI-ish units with an explicit "radians"
  or "metres" choice per field) and from this being a decades-stable public API most other DCS
  community export scripts (not searched exhaustively this session) are known to use — but this is
  **inferred, not documented or reproduced**, and should not be hardcoded into a plan without a
  stage-0 read.
- **No documented or community-confirmed getter returns pilot stick/collective/pedal *control*
  position for a helicopter.** `LoGetMechInfo().controlsurfaces` is explicitly flagged in this
  project's own prior research as **fixed-wing-shaped** (`elevator`/`eleron`/`rudder` fields) and
  **unverified for the Mi-24P** — whether it populates from cyclic/rotor state or sits empty (the
  way `LoGetTargetInformation` is empty for this module) is unknown. — **evidence: documented
  absence of a helicopter-shaped getter; the helicopter case itself is inferred/unverified** —
  **source:** `mi24p-command-surface.md:508-521`.
- **The only concrete, already-identified read path for actual stick/collective/pedal position is
  the cockpit draw-argument channel** (`get_argument_value` on the arg numbers that animate the
  physical stick/collective/pedal meshes), which this project's own §1 raw-table-gap finding
  already surfaces two of: `COLLECTIVE-CORR-PTR` (args 0,0) and `OP-COLL-THROTTLE-PTR` (args 0,0),
  both on device `ENGINE_INTERFACE`, both LMB=collective/RMB=throttle on a dual-function lever —
  **note the draw-arg number "0" for both is suspicious and may be a generator placeholder, not a
  real arg** (this file's own correction block documents the generator's known blind spot on raw-
  table elements; "0, 0" should be treated as unverified rather than assumed to mean "no
  argument"). No cyclic-stick or pedal draw argument has yet been identified by number anywhere in
  this project's research. — **evidence: reproduced-locally (the elements exist) /
  inferred-with-caveat (the arg numbers)** — **source:** `mi24p-command-surface.md:26-56`.
- **DCS-BIOS has no published Mi-24P module.** One widely-forked DCS-BIOS repo's own README lists
  only A-10C/UH-1H/MiG-21bis as supported and explicitly invites requests for more; a separate
  search turned up one forum user (`molevitch`) referencing a `Mi-24P.lua` DCS-BIOS file for radio
  (ARC-15/JADRO) controls only, with no mention of flight-control draw args, and reporting it
  partially broken (dial values not registering). No GitHub source for that file was found or read
  this session. — **evidence: forum-claim-unverified (the file's mere existence) / absent (its
  content)** — **source:** WebSearch snippets re `DCS-Skunkworks/dcs-bios`, `toxaq/dcs-bios`, and
  `forum.dcs.world` (molevitch profile content); no URL to the actual `Mi-24P.lua` file was
  surfaced, so it could not be fetched this session.

**5. Radar altimeter (RV-5) range and bank-angle validity**

- **No Mi-24P-specific documentation found anywhere this session** — neither ED's own material nor
  a forum thread states the RV-5's range ceiling or pitch/bank validity envelope for this module.
  — **evidence: absent.**
- **Analogues from other DCS modules, found but not transferable without a probe:** A-10C's radalt
  (per a forum quote of that aircraft's own `-1` manual) is rated to ±120° bank above 3000 ft (±35°
  pitch) and even better below 3000 ft, but **DCS's actual A-10C implementation cuts out well
  before 90° bank**, an ED-acknowledged discrepancy between documented and implemented behaviour
  on a *different* module. AV-8B's is reported as ±45° pitch/roll, ≤5000 ft AGL, falling back to
  barometric on invalid return. — **evidence: forum-claim-unverified, and explicitly of a
  different aircraft** — **source:** WebSearch snippets of `forum.dcs.world/topic/272130`,
  `/topic/168642`. **These numbers must not be carried over to the Mi-24P** — the A-10C case is
  itself documented as DCS deviating from its own manual, which is exactly the kind of
  per-module quirk a desk search cannot settle.
- **This project's own `LoGetRadarAltimeter()` comment** ("metres + validity flag (not always
  valid)") is the only Mi-24P-specific, reproduced-locally fact available — it confirms a validity
  flag exists and is sometimes false, but not the envelope that triggers it. — **evidence:
  reproduced-locally (existence of the flag) / absent (its trigger conditions)** — **source:**
  `aircraft-layer/dcs-export/Export.lua:24`.

### Reproducible Test

None run this session — desk recon only, no DCS install reachable. The stage-0 Windows probe BL-16
already calls for is the reproducible test; this note narrows what it needs to measure (see
Unresolved below, which doubles as that probe's checklist).

### Possible Approaches

- **Treat the K/H/T/B mapping (H=yaw, K=roll, T=pitch, B=altitude) as a working assumption for
  stage-0's probe script and card**, but have the probe itself confirm it against the in-cockpit
  labels/`list_indication` text rather than hardcoding command IDs blind — it is forum-sourced, not
  ED-primary, even though three independent snippets agree.
- **Do not build any plan assuming altitude/speed hold are absent.** Chuck's Guide naming both as
  real section headings is enough to raise the prior above the user's own recollected "possibly not
  implemented" — but not enough to confirm they hold *well*, which is the dimension that actually
  matters for BL-16 (whether Petrovich's own loop needs to own them, or can lean on the SAU for the
  cruise/steady-state portion). Stage 0 should test engaging `SpeedOn`/`HeightOn` and watching
  `LoGetIndicatedAirSpeed`/`LoGetAltitudeAboveGroundLevel` hold or drift over e.g. 30 s, independent
  of reading any more manual text.
- **Resolve the Trimmer-vs-attitude-hold contradiction (finding 1) with a probe, not more
  reading** — command a K/H attitude hold, then hold/release `Trimmer` while deliberately off the
  held attitude, and watch whether the hold re-references to the release-moment attitude (claim 1)
  or stays fixed (claim 2). This single test also tells BL-16 whether "maintain current state"
  on handover (settled point 3) can be implemented as "press Trimmer once, then engage K/H/T" or
  needs Petrovich's own loop to hold the initial reference itself.
- **For the axis-write-persistence question (finding 3's open half), reuse the 9K113 probe's own
  method** (`plans/9k113-sight-pointing/plan.md`'s wobble-detection approach) against `LoSetCommand`
  2001-2004: write a known value, hold the physical stick away from center, and watch
  `LoGetADIPitchBankYaw`/collective-draw-arg to see which one wins each frame. If the flight axes
  turn out to show the same frame-order contention as the 9K113 AI axis, the existing wobble
  technique is probably directly reusable; if DCS instead gives the script channel outright
  priority (plausible, since the global iCommand channel is architecturally different from a
  cockpit device command — finding 3), no wobble is needed at all, which would simplify BL-16
  materially.
- **For control-position readback, probe the draw-argument channel directly** rather than hunting
  further for a numbered arg: `get_argument_value` across a swept range of plausible argument
  numbers while visibly moving the physical stick/collective/pedals, watching which argument
  tracks motion. This is cheap (one probe script, no new DCS-side code) and sidesteps the dead end
  that community sources (DCS-BIOS) don't cover this module's flight controls.
- **For the radar altimeter, probe rather than borrow another module's envelope** — command a
  shallow and a steep bank at a known AGL and watch `LoGetRadarAltimeter`'s validity flag flip; this
  answers BL-16's actual need (can Petrovich's altitude-hold loop trust radar-AGL through a turn)
  without needing the exact angle threshold from a manual that may not match DCS's implementation
  anyway (A-10C precedent).

### Unresolved — needs the stage-0 Windows probe

Everything below is either flatly absent from any source checked this session, or found only as
unverified/contradictory forum material that a 403'd fetch could not resolve further:

1. **Does a per-frame `LoSetCommand(2001-2004)` override a physical stick that keeps sending its
   position, and is the 9K113-style "wobble" needed or sufficient?** (BL-16's own stage-0
   question, restated — nothing found here resolves it; the 9K113 case is evidence of the *shape*
   of contention on a different channel, not proof the flight-axis channel behaves the same way.)
2. **Is a raw-axis write from the operator seat accepted at all, and does it act the same way from
   either seat?** (BL-16's own question; not addressed by any source found.)
3. **Does `Trimmer` re-reference the K/H/T attitude hold on release, or leave it fixed?** Two
   contradictory, unverified forum claims found (finding 1) — a probe is the only way to settle
   this, not further reading.
4. **How well do altitude hold (`B`/`HeightOn`) and speed hold (`SpeedOn`) actually hold**, as
   opposed to merely existing as named modes (Chuck's Guide table of contents only) — this decides
   whether Petrovich's own feedback loop needs to own altitude/speed outright (as the user's
   2026-10-26 "fly the lift vector" direction already assumes) or can lean on the SAU for part of
   the steady-state regime.
5. **What DCS's "central position trimmer"/special-option joystick-centering setting does to the
   relation between a `LoSetCommand` write and effective cyclic position** — absent from every
   source checked; genuinely unresearched territory, not merely hard to find.
6. **What happens to an axis once script writes stop** — snap to the physical stick's current
   position next frame, hold last-written value, or something else — absent everywhere checked.
7. **Exact return shape/units for `LoGetVerticalVelocity`, `LoGetAngularVelocity`,
   `LoGetAccelerationUnits`, `LoGetVectorVelocity`, `LoGetSlipBallPosition`, `LoGetMagneticYaw`,
   `LoGetMechInfo`** — `Sim_ControlAPI.md` names them with no shape; no community source found
   either. A probe that calls each once and dumps the returned table/values (the same
   `debug_dump` pattern `Export.lua` already uses for `LoGetSelfData`) settles this in minutes once
   on the Windows box, and should be added to the stage-0 probe script rather than attempted again
   from the Mac side.
8. **Whether any numbered draw-argument tracks the pilot's cyclic or pedal position** — only the
   collective/throttle lever's two args are known (and those read "0, 0", possibly a generator
   artifact per finding 4), nothing for cyclic or pedals. A sweep-and-watch probe (Possible
   Approaches, above) is the only way to find this; no further reading will.
9. **Radar altimeter's actual bank/pitch validity envelope and range ceiling for the Mi-24P
   specifically** — absent; other modules' numbers (A-10C, AV-8B) are explicitly not transferable.
10. **Every ED-forum thread cited above as a WebSearch-snippet-only source returned 403 on direct
    `WebFetch` this session**: `topic/274656` (K/H/T/B labeling), `topic/315954`,
    `topic/340834`, `topic/356308`, `topic/48733` (page 2) (Trimmer/attitude-hold), `topic/337425`,
    `topic/294928`, `topic/285970` (speed/altitude hold numbers), `topic/378853` (vJoy
    double-control workaround). Per project convention, these are recorded as **unread**, not as
    dead ends — if any of them matters once BL-16 is actually planned, ask the user to open the URL
    in a browser and paste the content back rather than treating the 403 as a closed door.
11. **Chuck's Guide's actual body text for the Autopilot/AFCS chapter** was not read — only its
    table of contents (via a page that appears to gate the body behind a PDF download). If the
    stage-0 probe needs a documented-mode cross-check before flying, fetching/paginating that PDF
    (or asking the user, who may already own it) is cheaper than re-deriving mode behaviour
    live for every mode.
