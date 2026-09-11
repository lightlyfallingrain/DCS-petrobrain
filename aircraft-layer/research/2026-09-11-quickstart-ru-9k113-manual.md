# Real 9K113/ПН crew procedure (RU QuickStart manual) vs. our DCS AI-wheel probes

**Date:** 2026-09-11
**DCS version:** matches other 2026-09-11 notes (2.9.29.27278) — this note is a document read, not a live probe
**Theatre:** n/a

### Question

We had established live-probe facts about Petrovich's command surface (see
`2026-09-11-SUMMARY-petrovich-control.md`) but no explanation for *why*
`SRCH 9K113 LOS` appears broken and `DesignateAttackPoint` (cmd 3020) doesn't
aim him. The real Mi-24P Quick Start manual (`docs/concept/mi-24_info/DCS
Mi-24P QuickStart RU.pdf`, Russian, 167 pages) documents the real 9K113
Raduga-Sh complex and its crew procedure in detail (§4.5.4, §4.6.7, §5.3.8,
§5.4). Does the real procedure match, contradict, or explain our probe
results? Pages read: 46-53, 66-75, 105-116, 122-131 (RU text throughout,
translated/paraphrased below).

### Findings

- **The real complex has no "search" concept at all — evidence: documented — source: §5.3.8 steps 12-14 (pp. 112-113).**
  After enabling the system, the operator physically looks through the ПН
  (guidance-device) oculars (`[LAlt+A]` "nestle close to") and *manually finds
  the target by eye* ("Отыскать цель"), switching between x3.3 and x10
  magnification as needed. There is no automated scan mode, no sweep pattern,
  no "search a bearing" primitive anywhere in the real system's documented
  operation. Petrobrain's DCS-side `SRCH FWD` / `SRCH BRST` / `SRCH PILOT LOS`
  / `SRCH 9K113 LOS` wheel options are therefore **entirely a DCS/AI-layer
  invention with no real-hardware analog** — they exist to give the AI
  (Petrovich) something equivalent to "start looking," not because the real
  jet has a search button. This means the manual cannot explain *why* one of
  those AI abstractions misbehaves; that question is internal to DCS's
  AI-scripting layer (`HelperAI.lua` and friends — see
  `project_petrovich_perception` memory), not the aircraft systems.

- **The operator's control input is rate (angular-velocity), not position — evidence: documented — source: §5.3.8 step 14 (p. 113), literal text.**
  > "Необходимо помнить, что оператор управляет не угловым положением ЛВ ПН, а
  > угловой скоростью ЛВ ПН. Т.е. при перемещении мыши или джойстика задаётся
  > направление и скорость движения ЛВ ПН относительно СГФ. Чем сильнее
  > отклонён джойстик, или чем дальше перемещена мышь, тем быстрее начинает
  > двигаться прицельная марка."

  This is an exact match for what we already found live: **the player axis
  (cmds 3025/3026) accumulates** rather than snapping to a value (per
  `2026-09-11-SUMMARY-petrovich-control.md` §2). The manual confirms this is
  not a DCS quirk but a faithful model of the real ПУ ПН joystick, which is a
  genuine rate-control device — deflection magnitude sets angular velocity,
  not target angle. By contrast, **the AI-positional axis (cmds 3060/3061,
  which our probe used successfully for `look_at(bearing)`) has no real-world
  counterpart** — it is a DCS-internal convenience channel that lets AI code
  set an absolute angle directly, bypassing the (real, rate-based) joystick
  model entirely. This resolves an open question implicitly: our "linear,
  positional, one-write" sight control is confirmed synthetic/AI-only, not a
  simulated hardware path, so it should not be expected to have any in-sim
  physical limit beyond whatever DCS's AI code enforces.

- **"Designate an attack point" does not exist as a real 9K113 capability — evidence: documented (absence) — source: §5.3.8 whole procedure (pp. 105-116), full read.**
  The entire real engagement procedure (system power-up → PU selection →
  optical acquisition → manual tracking → pilot boresighting via the ASP-17
  small-ring → fire) contains **no coordinate entry, no waypoint/point
  designation, no "look here" input of any kind.** Targeting is 100% visual
  and manual. This supports (does not merely fail to contradict) the existing
  probe conclusion that `DesignateAttackPoint` (cmd 3020) not aiming Petrovich
  is not a bug in our test — cmd 3020 is a DCS/AI-menu construct layered over
  a system that, in reality, has nothing resembling "attack point
  designation." Its real behavior (stopping a search) is plausible as the
  closest DCS could map an "AI menu verb" onto — cancel current activity —
  rather than a genuine aim command.

- **The pilot's ASP-17 sight only *displays* the operator's LOS; it does not drive it, and the real workflow direction is the opposite of what "SRCH PILOT LOS" suggests — evidence: documented — source: §4.5.4 (p. 46-47), §5.3.8 steps 2.2, 15 (pp. 106, 113).**
  §4.5.4: "Прицел используется... для наблюдения положения оси линии
  визирования (ЛВ) прибора наведения (ПН)" — the ASP-17 is used to *watch*
  where the operator's ПН is pointed, nothing more, in this context. §5.3.8
  step 2.2 makes this link **conditional on a specific switch position**: the
  ПУВЛ (weapon-type selector on the launch-control panel) must be set to "ВЫКЛ
  (УРС)" ("OFF, missile mode") — its comment reads literally "*это нужно для
  связи и отображения положения ЛВ ПН оператора*" ("this is needed to
  establish the link and display of the operator's ЛВ ПН position"). Step 15
  then has the **pilot maneuver the helicopter** to keep the ASP-17's marker
  inside the small sight ring — i.e., in the real crew workflow, **the
  operator leads (finds and tracks the target optically) and the pilot
  follows/aligns the airframe**, not the reverse. There is no real-world
  procedure where the operator's sight follows the pilot's gaze. This means
  DCS's `SRCH PILOT LOS` label describes a DCS-invented mode with the
  opposite information flow from the real aircraft, so the manual cannot
  validate or explain its exact semantics — but it does surface a concrete,
  previously-unconsidered confound for our `SRCH 9K113 LOS` probe: **our test
  did not confirm the ПУВЛ (weapon-selector) galette was set to УРС/missile
  mode**, and the manual states that switch position is a prerequisite for
  ЛВ-ПН position/link behavior on the launch-control panel side. It is
  plausible (not confirmed) that some of what we tested as "broken" was
  actually gated behind that switch.

- **Chapter 6 ("КАК ИГРАТЬ", pp. 130+) is generic DCS World UI/mission-launch documentation, not an Mi-24P/Petrovich AI-command reference — evidence: documented (by omission) — source: pp. 130-131, read in full to where content changes to that topic.**
  §6.1 mentions in passing that in complex scenarios "the player must manage
  (make decisions and give commands to) subordinate crews," but gives no
  detail — this is boilerplate DCS World campaign framing, not Mi-24P/Petrovich
  wheel-command documentation. No further command IDs or procedures were found
  here. Pages beyond 131 were not read (out of scope per task — chapter runs
  into generic mission-launch/UI content, not weapons-systems material).

### Reproducible Test

Not applicable — this is a document read, not a live probe. Page ranges used:
`Read` tool with `pages` param on `docs/concept/mi-24_info/DCS Mi-24P
QuickStart RU.pdf`: `46-53`, `66-75`, `105-116`, `122-131`.

### Possible Approaches

1. **Re-run the `SRCH 9K113 LOS` probe with the ПУВЛ weapon-selector galette
   explicitly set to УРС (missile-off/link) position** before testing the
   wheel command, per the newly-found prerequisite in §5.3.8 step 2.2. This is
   a cheap, concrete next live-probe step that the manual — not prior
   forum/code reading — surfaced.
2. Treat the AI wheel's search/designate verbs as **entirely a DCS
   AI-scripting abstraction** going forward — do not expect further manual
   sections to explain their internals. The next productive investigation
   avenue for "why is `SRCH 9K113 LOS` broken" is DCS's own AI Lua
   (`HelperAI.lua`, `Mi_24P_op`/`Mi_24P_pilot` profiles — already a known lead
   per `project_petrovich_perception` memory), not further manual reading.
3. Since real search is "look through the oculars until you spot something
   with your own eye," and DCS confirmed aiming the sight alone does not
   drive detection (`2026-09-11-petrovich-detection-readout.md`), the
   design implication (for Architect, not decided here) is that Petrovich's
   *actual* in-sim detection likely runs on its own internal logic gated by
   his `SEARCHING`/`TRACKING` state and possibly the wheel's specific search
   *verb*, not on raw sight-axis position — consistent with, but not proven
   by, this manual.

### Unresolved

- **User-confirmed from gameplay (2026-09-11c):** the ASP-17-displays-operator's-LOS-only-in-УРС behavior
  itself is accurate — matches lived DCS experience, not just the manual text.
  This confirms the *display* fact; it does not confirm whether the switch
  position affects `SRCH 9K113 LOS`'s command behavior — that's still a
  separate, untested claim.
- Whether setting ПУВЛ to УРС changes `SRCH 9K113 LOS`'s observed behavior is
  **not tested** — this is a new live-probe candidate, not a finding.
- The manual does not cover DCS's specific AI-wheel command IDs (3001–3021
  etc.) at all — as expected, since they're a DCS/ED invention, not a modeled
  aircraft system. No further manual section is expected to resolve this;
  confirming AI wheel semantics still requires either a live probe with the
  above switch change, or reading DCS's shipped AI Lua.
- Elevation/vertical limits of the real ПУ ПН (documented as +20°/-15° on the
  handle icon, p. 70, and separately ±40° on the horizontal head icon on the
  same figure) were seen in passing (Рис. 4.20 icons) but not cross-checked
  against the DCS elevation gauge range (`-0.75…+1.0`) our probe measured —
  worth a follow-up if elevation limits in degrees are ever needed precisely
  (flagged as still-unmeasured in the SUMMARY note).
