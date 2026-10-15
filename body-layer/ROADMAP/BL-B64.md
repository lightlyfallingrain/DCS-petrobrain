# BL-B64 — The 9K113 sight, entry 1 of 3: perception

- [x] **BL-B64 — Simulate what the 9K113 lets Petrovich *see*: the wide and narrow optics, the
  directional 20 km player-bubble exemption, a non-instant slew, a long-dwell timing shape, and a
  range model that is approximate rather than exact.** #status/done #needs-flight
  **Merged to `main` 2026-10-15 as `ec39c0e`**, DoD PASS (`plans/9k113-sight/dod-check.md`).
  **The acceptance sortie is outstanding** — card at
  `docs/acceptance/2026-10-15-9k113-sight-acceptance-card.md`, and it must be flown with the
  body-layer service restarted between missions until `[[BL-B68]]` lands. Shipped with OBSERV on a
  voice command (`"observ on"`/`"observe on"`); the F10 radio-menu item was explicitly skipped by
  user direction and belongs to `[[BL-B66]]`.
  **Specification: `docs/concept/9K113.md`** (the user's own words, 2026-10-14) **plus
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §1–§11** (his direction of 2026-10-15,
  which outranks the plan wherever they differ).
  **Plan: `plans/9k113-sight/plan.md`** — sections 10–18 are this entry; 0–6 are the first pass,
  preserved with its superseded reasoning marked in place.

  **Split 2026-10-15.** This item was *"the whole capability"*; the user's §5 direction made it three
  entries in a fixed order — *"Lets start with that, that let's us test the behaviour. We'll then add
  actually manipulating the systems in cockpit. Only then can we add the ATGM attack run."*

  | | entry | what it delivers |
  |---|---|---|
  | 1 | **`BL-B64`** (this) | perception — what the sight lets him see |
  | 2 | `[[BL-B66]]` | effectors — the real cockpit switches moving |
  | 3 | `[[BL-B67]]` | the ATGM attack run |

  **`BL-B64` keeps its number and became the *first* entry rather than an umbrella.** An umbrella
  would never close, sitting `[ ]` open indefinitely and making the backlog's status unreadable; the
  three entries are held together by the shared specification document and by cross-links instead.
  Numbers are never reused or renumbered, so the two new entries took `BL-B66`/`BL-B67` (`BL-B65`,
  the weapons safety switch, already existed). **Note for anyone following an old pointer:** four
  entries refer to *"the 9K113 slice"*, and where they mean the attack run they now mean
  `[[BL-B67]]`.

  ## Why perception goes first

  The reason is the user's own and it is **testability**, not cost: this is the stage that lets the
  behaviour be flown. It also depends on nothing outside body-layer, while every cockpit-visible use
  sits behind a write channel on devices 6/7 that is **unverified**.

  Three assets make it cheap, all already on disk:

  1. **The multipliers are measured** — `perception/optics.py`'s own docstring records wide
     **3.55/7.00/6.50** and narrow **5.81/13.75/15.00** from detection-cones slice 2A, deliberately
     not instantiated. FOV (11.5°/6.0° full angle) and field of regard (±60° az, +20/−15° el) are in
     `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`. **No calibration sortie is
     needed.**
  2. **`BINOCULAR_OPTIC` has no cockpit representation and never has.** A purely-simulated optic is
     the established pattern here, not a shortcut.
  3. **`[[BL-B55]]` is one parameter** (`self.optic` is already in scope at
     `naked_eye_source.py:949`).

  ## `[[BL-B55]]` closes as this entry's own stage — the two must not be separated

  A sight seeing to 13–19 km while every look still carries naked-eye range error
  (`σ_down ≈ 0.17·R`) would report a precise-sounding range wrong by **~2.3–3.3 km at those
  ranges** — worse than having no sight at all, and the exact pathology `BL-B55` was filed against.
  So it is a stage here, not a prerequisite to schedule ahead.

  ## What the 2026-10-15 direction added, and the one finding it could not have

  - **Both fields of view from the start** (§8). Two `Optic` rows, not a mode flag; wide↔narrow uses
    the same reach-versus-field mechanism as naked eye↔binoculars.
  - **A 20 km directional cone** (§7), when OBSERV is on, in the direction the sight points, at the
    sight's own FOV. **Body-layer only** — DCS exports every unit in the mission (user-confirmed), so
    there is no culling to work around, the export side needs no change and aircraft-layer's `AC-B3`
    is **not involved**. `PLAYER_BUBBLE_RADIUS_M = 10000.0` is a cost filter of our own choosing.
    The design was already prescribed by that constant's own docstring: evaluate the exemption
    *inside* `filter_player_bubble()`, narrowed to the sight's FOV, **never by raising the radius**.
  - **Slew is deferred to the effectors, but one field split is owed here** (§8, settled by **§12**).
    The sight is slewed by a **rate**-commanding joystick — *"The axis input is the slew speed. Not
    desired angle, but angular speed of slew"* — so pointing it is a control loop, not an action with
    an argument, and *"We don't need this modeled before the effectors, but we must be ready for how
    it will work with the effectors so we don't have to redo much of the mechanism."*
    **The requirement on this entry: keep *desired aim* and *actual sight direction* distinct from
    the start**, even while `actual := desired` instantly. Today they are collapsed — but on **one
    line** (`logger.py` ~881–885, where `OpticDecision.look_azimuth_deg` becomes a `Gaze`), and every
    consumer downstream already reads the *actual* side. So the cost is a field pair on `OpticState`
    (already carried across polls, already frozen-and-replaced, so replay determinism is preserved
    by construction), one trivially-bodied `advance_sight_aim()` at that call site, and building both
    the `Gaze` **and the §7 cone** from actual. ~A dozen lines. Must be **per-optic**: for the eye and
    binoculars `actual := desired` is permanently correct, not a placeholder. Plan §15a.
  - **An inverted dwell shape** (§9): long dwell at the sight, brief glances away and back — the
    opposite of binoculars. Shared mechanism, different constants, but it inverts `optic_policy`'s
    *resting phase*, which is a shape change rather than a retune (plan §13).
  - **Ranging is approximate and a group is ranged once at its middle unit** (§11). First phase may
    be instant but **must never be exact**. The shared per-group draw is a correctness argument, not
    an optimisation — independent per-unit draws would scatter a group's believed positions, which is
    what `[[BL-12]]`'s cohesion cap cannot absorb.
  - **No elevation angle is ever spoken** (§2, §10) — there is **no elevation scale on the
    instrument at all**, only an azimuth arc (10/30/60° off boresight;
    `docs/concept/mi-24_info/9k113-reticle-narrow-x10.png`). World reference (*"on the ridge"*) is
    cross-reference and is fine. Azimuth feeds `[[BL-14]]`'s existing o'clock-then-left/right
    register; **no new guidance vocabulary**.

  **The finding the direction could not have: the cone alone buys nothing.** `visibility.py:854`
  computes `range_threshold_m = min(NAKED_EYE_RANGE_CAP_M, size_curve_threshold_m)` with the cap at
  `10000.0`, so a narrow-sight candidate at 13.6 km is admitted by the cone and then **clamped back
  to 10 km and rejected**. This entry needs **two** changes — the cone in `association.py` *and* an
  optic-aware range cap in `visibility.py` — and neither is sufficient alone.

  ## Effort/value, honestly

  **No longer "nearly free", but still the cheap slice and still first.** Five things closed at zero
  cost (the ASP-17 crosshair use case removed entirely by §1, the *"poor vertical"* mechanism
  answered without touching the optics, autonomous OBSERV's `/explore` cancelled by §6, a sight-
  specific guidance vocabulary, and per-unit ranging). The growth is concentrated in two places: the
  `optic_policy` resting-phase refactor, and the cone-plus-cap pair whose downstream LOS cost needs a
  **bench measurement** (plan §12b — estimated +20–40% on a 12.6 ms tick, bounded by area at 5–10%
  more candidates). ~~Cheap lever if it measures high: the cone is only load-bearing for narrow
  mode — wide reaches ~8.3 km for a 7 m vehicle, *inside* the existing bubble — so dropping wide
  from phase 1 halves the added cost for almost no product loss.~~

  **The lever is withdrawn — user direction, 2026-10-15: both cones are in phase 1.** The
  narrow-only fallback is not available, so the cost analysis above stands without a cheaper
  position to retreat to. Build both.

  **And the same direction reframes what the measurement is for.** *"We only ever need LOS for the
  units that are in the current FOV. And that is dependent on the optics type."* That is already how
  `check_visibility` gates — gaze → cockpit mask → optic FOV → range/size → LOS — so **this entry
  must not reorder those gates**; it is a confirmation, not a change.

  The consequence worth carrying: `UNAIDED_OPTIC` has `fov_half_angle_deg is None`, so for the naked
  eye **the FOV gate is a no-op** and the eye is bounded only by gaze and the 10 km cap. The 9K113
  is the first optic that genuinely narrows it, and the cone has the *same shape* as that gate — so
  the cone admits roughly what the FOV gate would have admitted anyway, just further out. Whether
  that is more or less LOS work than the naked eye does today depends on unit density in the pointed
  sector and **cannot be settled from geometry**. So the benchmark counts **candidates reaching the
  LOS step, per optic, against the naked eye as baseline** — not candidates admitted by the bubble.

  **Direction §12 is net negative work for this entry**: it removed the slew rate limit the plan was
  going to carry here and replaced it with the field split above.

  Related: `[[BL-B55]]` (closes here), `[[BL-B66]]`, `[[BL-B67]]`, `[[BL-B62]]` (the
  relative-versus-map channel — its named consumer is the ATGM run, so `BL-B67`, not this entry),
  `[[BL-B63]]` (the selective fast lane, a hard dependency of `BL-B67` and not of this entry),
  `[[BL-12]]` (the cohesion cap this entry's range model is what makes behave at range),
  `[[BL-14]]`, `[[BL-B23]]` (never-pruned `ContactStore` — this entry gives it a genuinely new
  growth source by admitting contacts past 10 km for the first time).

  ---

  **Added by direction, 2026-10-15: set `UNAIDED_OPTIC.fov_half_angle_deg` from `None` to `90`**
  while the optic table is being revised (§14 of the direction document). *"a fairly sane 180 degree
  naked eye max FOV (that's a peripherial vision FOV, but we can refine later for focus FOV)"*.

  **Nearly a no-op, verified rather than assumed**: `FULL_GAZE` is already `half_width_deg = 90.0`
  (`perception/gaze.py:194`) and the gaze gate runs before the optic gate, so the bound already
  exists — this moves it into the place that should own it. **The one real difference**:
  `within_gaze` compares azimuth only, `within_optic_fov` computes a great-circle separation
  including elevation, so a candidate near 90° azimuth *and* well off the horizon now falls outside.
  A test pinned exactly at the 90° boundary can flip; that is a behaviour change, not a refactor.

  **Why it belongs in this entry**: it closes the asymmetry recorded above — the naked eye is
  currently the one optic whose FOV gate is a documented no-op, which makes "LOS is bounded by the
  optic's FOV" true of every optic *except* the default. Afterwards it holds universally.

  Leaves `within_optic_fov`'s `fov_half_angle_deg is None` branch unreachable; keep it with a
  comment (a future peripheral-awareness pseudo-optic may want it) rather than deleting it.
  Reconciling 180° peripheral against `FOCUS_CONE_HALF_WIDTH_DEG = 15.0` is explicitly **later**.

