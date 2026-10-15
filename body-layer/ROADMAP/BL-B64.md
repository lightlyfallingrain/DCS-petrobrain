# BL-B64 — The 9K113 sight: the whole capability, and its own specification

- [ ] **BL-B64 — Simulate the 9K113 Raduga-Sh sight: warm-up, OBSERV, slewing, the wide/narrow
  fields, and what it makes possible that the naked eye and binoculars cannot.** #status/open
  **Specification: `docs/concept/9K113.md`** (the user's own words, written 2026-10-14 — it is the
  specification, not a summary of one). Filed 2026-10-14 at his request, *"so that it does not get
  forgotten"*.

  **Why this entry had to be minted rather than appended to.** He asked for the reference to go on
  "the 9K113 roadmap item". There was none. `[[BL-B55]]` names *"the 9K113 slice"* in its own title
  and depends on it, and `[[BL-14]]`, `[[BL-B62]]` and the deferred ATGM attack run all point at it —
  so four entries referenced a slice that was never filed. That is exactly how a prerequisite goes
  missing: every document assumes someone else is tracking it.

  ## The hard prerequisite, established 2026-10-14

  **The 9K113 sight does not exist in code.** `perception/optics.py` declares exactly two optics,
  `UNAIDED_OPTIC` and `BINOCULAR_OPTIC`, and four other files say so about themselves
  (`belief/groups.py:385`, `perception/association.py:91`, `perception/visibility.py:49`,
  `perception/clustering.py:79`). So **every** 9K113-dependent capability — ATGM guidance above all —
  is gated on this entry, not on tuning or on the attack run. From the `BL-14` explore
  (`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`): *"ATGM guidance is with 9K113
  only, there is no naked eye channel for ATGM guidance."*

  ## What the specification contains, in outline — read the document, not this list

  - **A ~3 minute warm-up** with a cockpit switch sequence, a *"Guidance unit ready"* callout when
    the panel light illuminates, and a 1 s hand-movement delay simulated between switch actions.
  - **OBSERV as a mode**, with *"Observ on"* / *"Observ off"* callouts, gyro alignment before
    slewing, and the operational constraint that it is **not** left on for prolonged periods.
  - **Looking through it is exclusive**: flipping other switches takes his eyes off the sight, so he
    *does not see* what it shows — eyes away, hand to switch, back, each 1 s.
  - **Slewing** as an inspect-and-adapt loop, because the sight does not move instantly, and
    `9K113` slew controls are to be used *only while looking through it*. Ownship telemetry must
    carry 9K113 state.
  - **The capability it adds**: detection, classification and type identification at greater range
    (the existing calibration tables already hold the figures), good azimuth understanding,
    **poor vertical** understanding, a visual range aid useful inside ~5 km, gyro stabilisation
    against ownship movement, and the sight holding its last position while he uses the naked eye or
    binoculars.
  - **Strong manoeuvres force OBSERV off** to protect the gyros, with a 1–2 s reaction time
    acceptable.
  - **The ATGM attack run**: arm the weapons circuit, select a pylon with a missile, azimuth-only
    guidance, *"out of range"* / *"in range"* spoken once each, a launch callout naming the missile
    and estimated flight time, *"impact"* (with hit/miss if detectable), and resetting the guidance
    transmitter 1 s after impact.
  - **Rockets too**: the sight is not meant to guide them, but holding the crosshair on the target
    lets the pilot read the target's position off the ASP-17 — a second, non-ATGM use.

  ## What must happen before any of it is planned

  1. **An Investigator pass on the Russian QuickStart PDF.** The document's switch tables are
     deliberately `TBD` and it names the sections to read —
     `docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` pages 21–39, 42, 44, chapter 4.6
     (pp. 60–70) and chapter 5.3.8 (pp. 105–116). It also asks which ATGM types are supported, and
     the gyro alignment duration. **Do not guess these from the screenshots** — that is the role
     `investigator` exists for.
  2. **An `/explore` where it contradicts earlier decisions.** The document says so itself:
     *"Where this document contradicts something written earlier, explore with user."* At least one
     contradiction is already known — `BL-14` records the vertical axis as a *discrimination* aid,
     while this document says the 9K113 gives **poor** vertical understanding, which is a different
     claim about a different instrument.
  3. **`[[BL-B55]]` first or alongside**: `naked_eye_sigma_m` takes range only, so every look gets
     naked-eye-grade position error regardless of optic. A sight whose whole point is better
     resolution cannot be modelled through an optic-blind uncertainty function.

  Related: `[[BL-B55]]` (optic-blind uncertainty, names this slice in its title),
  `[[BL-B65]]` (the weapons safety circuit switch, which the specification says must be its own item
  before the ATGM run), `[[BL-14]]` (the naked-eye/binocular attack run, which ships without any of
  this), `[[BL-B62]]` (relative-versus-map perception channels; the ATGM run is one of its named
  candidate consumers).

  ---

  **Planned 2026-10-15 (architect, planning only — not implemented by user direction):**
  `plans/9k113-sight/plan.md`. Investigator findings it builds on:
  `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md` (plus its 2026-10-15 addendum,
  which closes the missile speed/range gap from sources the user supplied).

  **The plan splits this item along a seam the brief did not anticipate: perception versus
  effectors.** Axis A — sight-grade detection/recognition range and position precision — depends on
  nothing outside body-layer, and the optic multipliers it needs were already measured (they sit in
  a `perception/optics.py` docstring, deliberately not instantiated), so **it needs no calibration
  sortie**. Axis B — real cockpit switches, the ASP-17 mark, the ATGM run — depends on an unverified
  write channel on devices 6/7, a sub-1 s loop ([[BL-B63]]/`AC-B3`, filed not built), and a
  readiness lamp with no read path. The plan recommends Axis A as its own entry, merged, before Axis
  B is decided.

  **[[BL-B55]] is not a separate prerequisite to schedule ahead of this — it is Axis A's own stage,
  and the two must not be separated.** A sight seeing to 8 km while still carrying naked-eye range
  error (`σ_down ≈ 0.17·R`) would report a precise-sounding range wrong by ~1.4 km, which is worse
  than having no sight. So `BL-B55` closes as part of this work.

  **Five decisions remain the user's**, listed in the plan: whether a perception-only 9K113 is an
  acceptable interim; what *"poor vertical understanding"* actually means mechanically (the sourced
  FOVs are symmetric, so nothing in the optics supports it — and if it means the sight cannot
  separate two vertically-stacked units, ATGM target selection cannot work the way `BL-14`'s does);
  whether autonomous OBSERV is in scope at all (`/explore` owed); the missile word; and the launch
  callout's interim now that the flight-time numbers exist.

