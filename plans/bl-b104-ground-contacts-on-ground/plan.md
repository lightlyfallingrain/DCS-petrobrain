# BL-B104 — Ground contacts are on the ground: plan

Architect, 2026-10-30. Branch `feature/bl-b104-ground-contacts-on-ground`, planned against tip
`025a91b4`. Inputs: `body-layer/ROADMAP/BL-B104.md`, `alignment.md` (E1–E7, findings 1–5),
`explore-notes.md` (Q1–Q5 answers, which override the entry's original "range not guessed"
shape), `docs/acceptance/2026-10-30-sortie-feedback.md` §4, `plans/atgm-run-sight-tracking/`.
Recon: `aircraft-layer/research/2026-10-30-world-object-category-and-agl.md` (investigator, this
pass).

### Goal

A seen surface unit (vehicle, infantry, static, ship, landed/low-hovering helicopter) is believed
**on the ground at its own height**, and its distance is a **perceived estimate fused from two
cues** — the look's depression angle (strong when looking steeply down) and the size/terrain
judgement Petrovich already makes (strong at shallow angles) — so the sight, guidance words and
reports point at where the unit stands, with an error no worse than today's and better when close.

### The model in one picture

```
             ownship (alt A, exact)
               *
               |\  δ = perceived depression (true δ + own noise + nothing from the exact channel)
             h |  \
               |    \         cue B: D_B = h / tan(δ_perceived)        σ_B = (h²+D²)/h · σ_δ
               |      \       cue A: D_A = D + noise                    σ_A = 0.17·D · optic scale
   ------------+--------*---- unit's own ground height (read from unit data at the look)
               |<-- D -->|
                          fused in inverse distance (1/D), where cue B is linear in tan δ:
                                  1/D̂ = (w_A/D_A + w_B·tan δ_perc/h) / (w_A + w_B)
                                  w_A = (D²/σ_A)²,  w_B = (D²/σ_B)²   (true geometry)
                                  σ_down = (1/σ_A² + 1/σ_B²)^-½
                                  + one per-object systematic offset, z_obj · 0.4 · σ_down
                          believed point = (bearing, D̂) from the look's observer, alt = unit height
```

Cue A **is today's estimate**, unchanged — `RANGE_FRACTIONAL_SIGMA` (0.17) times the optic's
existing range scale (the 9K113's stadiametric/size advantage is already `SIGHT_*_RANGE_SIGMA_SCALE`).
It is now documented as what it always was: the observer's size-and-terrain-reference judgement,
modelled statistically (explore Q2). Cue B is new. Their inverse-variance fusion can never be worse
than cue A alone, which is what makes E3's "no worse than today" a property of the arithmetic rather
than a tuning outcome.

With `DEPRESSION_SIGMA_DEG = 3.0` (the bearing error's own value — which reconciles both readings
of the user's *"same range as the azimuth angular error"*: the **angle** is the same, and the
**ground** error comes out at the ~±700 m he called sensible):

| AGL | distance | today (cue A) | cue B alone | **fused** |
|---|---|---|---|---|
| 300 m | 1 km | 170 m | 190 m | **127 m** |
| 300 m | 3 km | 510 m | 1.6 km | **486 m** |
| 300 m | 4 km | 680 m | 2.8 km | **661 m** (Q1's ~700 m) |
| 420 m | 5.3 km (sortie run 2) | 900 m | 3.5 km | **873 m** |
| 50 m | 3 km | 510 m | 9.4 km | **509 m** |
| 800 m | 1.5 km | 255 m | 189 m | **152 m** |
| 800 m | 800 m | 136 m | 84 m | **71 m** |

Shallow looks behave as today; steep and close looks firm up. Repeated looks still average the
per-look noise down to the never-averaging systematic floor (`SYSTEMATIC_BIAS_FRACTION`), so
"looks" shrink it too (E3, E7). Through the 9K113 both cues tighten via the existing per-optic
scales (narrow: σ_A ×0.3, σ_δ ×0.7).

**Fuse in inverse distance, not in metres — measured, not taste.** A Monte Carlo of this pass
(20 000 draws per geometry, σ_δ = 3°) compared three ways of combining the same two cues:

| geometry (AGL / distance) | metres, true-geometry weights | metres, perceived weights | **1/D, true weights** |
|---|---|---|---|
| 50 m / 500 m | RMS 1.67× today, bias +5.4 % | 1.06×, −4.8 % | **0.96×, −0.3 %** |
| 150 m / 1 km | 1.31×, +3.9 % | 0.95×, −4.0 % | **0.92×, −0.2 %** |
| 300 m / 2 km | 1.16×, +3.7 % | 0.95×, −3.8 % | **0.92×, 0.0 %** |
| 50 m / 3 km | 1.00×, −0.2 % | 1.74×, −12.6 % | **0.99×, −0.5 %** |
| 800 m / 1.5 km | 0.62×, +0.9 % | 0.59×, −0.3 % | **0.62×, −0.2 %** |

`h / tan δ` is heavy-tailed toward long wherever the depression error is a sizeable fraction of
the depression itself (alignment finding 1's lopsidedness), so averaging it in metres is *worse than
today* at moderate angles; weighting by the perceived depression over-corrects short. `tan δ / h`
is linear in the angle error, so averaging in 1/D is unbiased and never worse than cue A alone at
any grid point. The declared σ_down is the same either way (the table above); only how the mean is
formed differs. This is what the Stage 3 envelope test exists to hold.

**The altitude half is what failed in the sortie (alignment finding 2)** and lands first, in
Stage 2, on its own; the range half is Stage 3.

### Affected Modules / Files

aircraft-layer (wire — the only way to know a unit's domain; recon note above):
- `aircraft-layer/dcs-export/Export.lua` — emit the object's category (see Stage 1) per world object.
- `aircraft-layer/src/schema/world_objects.py` — optional category field on `WorldObjectSample`,
  `None` when an older `Export.lua` omits it.
- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`, `src/schema/line_of_sight.py` —
  per-candidate height above ground, for the helicopter rule only (Stage 5).

body-layer, perception:
- `src/perception/association.py` — `WorldObjectCandidate` gains the domain (`is_surface:
  bool | None`), resolved once in `from_dict`.
- `src/perception/domain.py` (**new, small**) — the one pure rule "category (+ AGL for helicopters)
  → surface / air / unknown". New file because both sources and a test table need it and neither
  source module should own the other's rule; it removes the duplication of writing it twice.
- `src/perception/clustering.py` — `ClusterCandidate`/`Cluster` carry the domain; never mix domains.
- `src/perception/naked_eye_source.py` — cluster each domain separately; surface clusters emit
  `surface_alt_m` and use the two-cue range.
- `src/perception/hybrid_source.py` — surface candidates emit `surface_alt_m` and horizontal range.
- `src/perception/estimation.py` — `surface_range_estimate(...)` (cue B, fusion, post-fusion
  systematic offset); `DEPRESSION_SIGMA_DEG` tunable.
- `src/perception/source.py` — `Observation.surface_alt_m: float | None = None`.
- `src/perception/geometry.py` — docstring of `project_from_bearing_range` only (its flat
  convention now applies to air contacts alone).

body-layer, belief:
- `src/belief/percept.py` — `Percept.surface_alt_m`, passed through (closed, purpose-named field;
  the module's own "how to add a new signal" pattern — it is a number, not a free-form string).
- `src/belief/association_over_time.py` — `implied_position`: altitude = `surface_alt_m` when set.
- `src/belief/contacts.py` — `Contact.on_surface: bool = False`, written beside `last_alt_m` at the
  two sites that write it (`record`, `from_percept`); field docstrings rewritten.
- `src/belief/attack_run.py` — `remembered_target_alt_m`: a surface contact's height is
  `contact.last_alt_m` (one source of a ground unit's height); air keeps the relative
  reconstruction.
- `src/body.py` — `_look_target_position` docstring (behaviour follows from the line above).
- `src/belief/enrichment.py` — `_terrain_aware_world_position` returns `contact.last_position`
  unchanged for surface contacts (already on the ground; no world-model grid on the live path for
  them, per the user's *"no world model elevation grid"*).
- `src/belief_truth_log.py` — compare horizontally; log believed altitude and `on_surface`.
- `src/tuning.py` consumers / `config/defaults.toml` (regenerated) — `DEPRESSION_SIGMA_DEG`,
  `HELI_SURFACE_AGL_MAX_M`.
- Tests: `test_estimation.py`, `test_percept.py`, `test_naked_eye_source.py`,
  `test_hybrid_source.py`, `test_clustering.py`, `test_contacts.py`, `test_association_over_time.py`,
  `test_attack_run.py`, `test_body.py`, `test_enrichment.py`, `test_belief_truth_log.py`, new
  `test_domain.py`; aircraft-layer `test_schema.py`.

Not changed: `position_belief.py` (the fused estimate is 2D x/z and stays so — only its inputs
move), the association gate constants, `sight_head.py`'s bearing-line search (stays the fallback for
far shallow targets, as BL-B104 already says), `RELATIVE_DIRECTION_SIGMA_DEG` and the relative
channel.

### Implementation Plan

**Stage 1 — Unit domain on the wire and through perception (no belief change).**
- aircraft-layer: forward `Type.level1` and `Type.level2` from `Export.lua` into two optional
  integer schema fields (`category`, `subcategory`); bump `EXPORT_SCRIPT_VERSION`. Old scripts
  parse with `None`. Recon: `LoGetWorldObjects` returns `LoGetObjectById`'s documented shape,
  `Type = {level1..level4}` included (DCS's own `Export.lua` template comments; the 2026-10-29
  note's "no Type table" read a Hoggit field-subset example, now corrected).
- `perception/domain.py`: `surface_domain(category, subcategory, agl_m) -> bool | None`, on the
  wsType enumeration (community-convergent, not yet read from the installed `wsTypes.lua`):
  `level1` Ground (2), Navy (3), Static (5) → surface; Weapon (4) → air; Air (1) → air, with
  helicopters (`level2` = 2) going through Stage 5's height test; Destroyed (6), anything else or
  missing → `None`. **`Flags.Static` is not the discriminator**: it is the mission-editor "placed
  without AI" flag, and those units are still ordinary ground vehicles. Static (5) is included as
  surface because whatever lands there (airfields, wrecks, structures) is on the ground either way.
- **`None` is treated as air — today's flat model, bit for bit.** Fail direction chosen so an
  un-redeployed `Export.lua` changes nothing rather than guessing; log once per session at WARNING
  when a non-empty poll carries no category at all, so the test card's "redeploy Export.lua" step
  cannot silently be missed.
- Clustering runs once per domain and concatenates; a cluster is never mixed by construction (a
  helicopter crossing a convoy cannot drag the convoy into the air model, or vice versa).
- Tests: schema with/without the field; domain rule table; mixed-domain candidates never share a
  cluster; air-only and `None`-only polls produce observations identical to today's.

**Stage 2 — Surface units at their own height (the sortie's failure; alignment finding 2).**
- Surface clusters emit `Observation.surface_alt_m = cluster.centroid_alt_m` (the members' own
  mean height, read at this look and only at a look); hybrid emits the matched candidate's
  altitude. → `Percept.surface_alt_m` → `implied_position` puts the look at that height.
- `Contact.on_surface` and `last_alt_m` written together from the latest look (record and
  from_percept — the only two writers; `speech.py`'s placeholder `Contact` takes the default).
- `remembered_target_alt_m(contact)`: `contact.last_alt_m` when `on_surface`, else unchanged. So the
  sight's belief aim, tier-1/tier-2 guidance elevation and `body._look_target_position` all read one
  height for a ground unit, and the stopgap is retired for ground contacts without deleting the air
  path it still serves.
- Enrichment short-circuit and truth-log changes above.
- Range model unchanged in this stage (cue A only), so any behaviour change is attributable to
  altitude alone.
- Tests (control points, all from the sortie): seen once at 1584 m MSL, ownship then descends 419 m
  → believed elevation from current ownship is the true depression, never above the horizon (run 1:
  +72° believed vs −84° truth); run-2 geometry (believed alt was ownship 1170 m, truth 750 m) → believed
  alt 750 m; air contact → `last_alt_m` is still ownship-at-look (E6); `remembered_target_alt_m` for a
  surface contact with and without a tier-1 look; cockpit-mask cases below.

**Stage 3 — The two-cue distance for surface units.**
- `estimation.surface_range_estimate(observation_id, object_id, true_distance_m, height_above_unit_m,
  optic) -> (range_m, sigma_down_m)`:
  - cue A: today's per-look down-range draw (`"look:{id}"`), σ_A = today's `look_sigma_m` down value;
  - cue B: perceived depression = true + per-look draw (new hash domain `"depression:{id}"`) × σ_δ,
    σ_δ = `DEPRESSION_SIGMA_DEG` × the optic's existing bearing scale; its observable is
    `tan(δ_perceived) / h` (inverse distance);
  - **cue B is absent when the perceived ray does not descend to the unit** (perceived depression
    zero or of the wrong sign — low hover, unit above, near-level look): range is cue A alone, i.e.
    today's estimate (explore Q2: *"range then … from unit angular size"*). h is signed, so a unit
    above the observer works the same way with an upward ray;
  - fuse **in inverse distance** (`1/D_A` and `tan δ_perc / h`) with weights from the look's true
    geometry (the existing "sigmas declared at the true range" convention, `PositionUncertainty`'s
    docstring); invert; clamp to the channel's detection cap; cue A floored at 1 m before inverting;
  - then one per-object systematic offset `z("bias:{object_id}") × SYSTEMATIC_BIAS_FRACTION ×
    σ_down`, **after** fusion. When cue B is absent this is today's formula exactly; when present it
    scales smoothly with the fused σ, so a unit's believed range does not jump as the weight moves
    from cue A to cue B during a closing run (which would otherwise risk a second "new contact",
    E5). Cross-range bias unchanged.
- `naked_eye_source`: surface clusters call it; air clusters call `perturbed_bearing_range` as today.
  Percept range for surface looks is horizontal ground distance (it already is for naked-eye; hybrid
  switches to horizontal for surface candidates).
- `DEPRESSION_SIGMA_DEG`: `tuning.real(..., 3.0, lo=0.1, hi=14.0, status="judgement")`, `#:` comment
  whose **first sentence** says what it does in the cockpit (the generator emits only that); check
  the rendered `defaults.toml`, not the comment.
- **The no-omniscience fence, made testable (E7, alignment finding 3):** cue B's depression is
  perturbed in its own hash domain with its own σ and is never derived from `RelativeDirection` or
  `RELATIVE_DIRECTION_SIGMA_DEG`. A grep test pins `estimation.surface_range_estimate` and the
  naked-eye surface branch to never reference `relative_direction`/`RELATIVE_DIRECTION_SIGMA_DEG`;
  a fusion test pins that a stationary unit looked at 200 times from a closing track converges to a
  point offset from truth by its systematic draw, not to truth.
- Tests: **envelope table as a control-point test** — for AGL ∈ {50, 150, 300, 500, 800} m ×
  distance ∈ {0.5, 1, 2, 3, 4, 5, 6} km, over ≥ 2000 deterministic observation ids (per-look noise
  only, systematic offset excluded): RMS ground error ≤ today's σ_A × 1.05 everywhere (E3 "no
  worse") and ≤ 0.85 × σ_A wherever depression ≥ 15° ("firms up close"); |mean bias| ≤ 2 % of
  distance (the measurement above shows < 1 %; a metre-domain fusion fails this at 50 m / 500 m,
  which is the regression the test guards); no NaN/negative/behind-observer range anywhere,
  including unit-above-observer and ray-above-horizon draws. Plus: cue B absent ⇒ result equals
  `perturbed_bearing_range`'s down component exactly; narrow sight tighter than naked eye at every
  grid point.

**Stage 4 — Association still holds one unit as one and two as two (E5), verified, not assumed.**
- Gating is 2D on the look's ellipse and constants do not change. The new σ_down is ≤ today's
  everywhere, so gates can only tighten, and only at steep geometry.
- Scenario tests through `ContactStore` with the real perception estimator:
  (a) one stationary BTR group seen every 2 s on a closing run 4 km → 0.5 km at 300 m AGL, across
  ≥ 200 object-id seeds: exactly one contact in ≥ 99 % of seeds;
  (b) two groups on one bearing at 3 km and 4.5 km, 150 m AGL: two contacts, each fed only by its own
  group's looks, in ≥ 99 % of seeds;
  (c) the same two at 300 m AGL during a closing run.
- If (a) or (b) fails, **stop and report** rather than retune the gate: a gate change is a
  behaviour change across every contact and needs its own decision.

**Stage 5 — Helicopters landed or hovering low follow the ground rule (explore Q4).**
- Carrier (recon Q3): `petrobrain-line-of-sight-hook.lua` already runs at 1 Hz in the mission
  scripting env over the look-wedge candidates and joins by unit name. Add one pcall'd
  `land.getHeight({x = p.x, y = p.z})` per candidate and publish `agl_m = p.y − height`
  (`land.getHeight` is already confirmed live by world-model; cost was load-tested). Schema field
  optional; body-layer joins it beside the LOS verdict.
- `domain.surface_domain` treats a helicopter as surface iff its AGL is known and
  ≤ `HELI_SURFACE_AGL_MAX_M` (tunable, default 10 m, judgement; *"a few metres up"*). Unknown AGL →
  air (today's model). **Height only, no speed condition.** MOOSE pairs height with speed < 1 m/s
  to recognise "landed", but the user's rule also covers a low hover, and a helicopter passing
  through a few metres AGL is, for the pilot, at the ground in that moment. `Unit:inAir()` is not
  used: it does not exist on `StaticObject`, and it reports `true` for a helicopter sitting on a
  building.
- Independent of Stages 2–4 and the rarest case in this item; can ship later without holding the
  rest.

**Stage 6 — Live acceptance (test card, branch `main` after merge).**
- Redeploy `Export.lua` (and the LOS hook if Stage 5 shipped). Fly an ATGM run started high on a
  group seen once, then descend into the run. Expected: sight starts within the wide field and says
  "Tracking." (E2); reports' distances firm up while closing (E3); no duplicate "new contact" on
  the target group during the run (E5); a helicopter or aircraft contact reported as before (E6);
  units passing under the nose stop being called out while hidden by the airframe (cockpit-mask
  change, below). `dcs-belief-truth` log: believed altitude within a few metres of truth for ground
  contacts; horizontal error ≈ the table above.

**Stage 7 — Manoeuvre-based scenario mock flights (added 2026-10-30, after Stages 1–5 shipped;
`explore-notes.md`'s "Scenario mock flights" section).** The user asked, separately from the
sortie fix itself, whether this project can exercise a scenario like the sortie's two runs without
DCS. The only existing end-to-end harness (`tests/test_mock_flight_chain.py`, built by
`plans/mock-flight-fixture/plan.md`) replays one static, hand-authored, no-manoeuvre fixture
(straight north, constant 700 m, 20 frames) through the real wire/pipeline/threading — it proves
the chain doesn't break, not that a believed position/sight-aim/speech outcome is *correct* for a
given flight shape. Two options were put to the user: scripted scenarios on the existing harness,
or record-and-replay a real sortie. *"2 is too cumbersome... 1 yes. Simple mock flights that still
contain some aircraft manoeuvre."* Record-and-replay is **rejected, not backlogged** — it was
compared, not merely unconsidered. This stage is test infrastructure, reusable by later features
the same way `mock_flight_canonical.json`/`MockAircraftLayerServer` already are — not a new
scenario each written by hand, and not a flight simulator.

- **New module, `body-layer/tests/support/mock_flight_scenario.py`** — a small builder that turns
  a short list of manoeuvre legs plus placed units into a frame list in the same shape
  `MockAircraftLayerServer` already consumes (`list[{"telemetry", "world_objects",
  "petrovich_indication", "line_of_sight"}]`), generated by code rather than hand-written JSON —
  the parametric reason `mock_flight_canonical.json` didn't need: that fixture is one flight,
  authored once; a manoeuvre scenario is legs integrated into a trajectory, which is what code is
  for, and `implementation.md`'s own "exact per-frame numbers were computed by a throwaway script
  ... not guessed" is already doing this by hand per fixture — this stage keeps that script instead
  of discarding it after one use.
  - `FlightLeg`: one of `Level`/`Climb`/`Descend`/`Turn`/`RunIn`/`Hover`, each a small frozen
    dataclass (`duration_s` or an end condition, target heading/altitude/climb-or-descent
    rate/speed, and — needed for the cockpit-mask cases — a target pitch, since "pitched-down
    attack attitude" is an attitude the existing `Level`/`Climb`/`Descend` shape has no field for).
    `RunIn` is a `Descend`/`Level` combination aimed at a named placed unit's ground point rather
    than a bare heading, matching how the sortie's own two runs are described (closing on a seen
    group). Integration is dead-reckoning only (heading/pitch/bank rates applied each poll tick) —
    no aerodynamics, no world-model terrain under the flight path (ownship altitude is a leg
    parameter, not derived from a grid, matching `build_mock_world_model`'s own flat-plane
    precedent).
  - `PlacedUnit`: `object_id`, `object_type`/reporting name, `category`/`subcategory` (BL-B104
    Stage 1's wsType fields — every placed unit in these scenarios is a ground unit, category=2,
    so the fused range/altitude model under test actually runs), `x`/`z`/`ground_alt_m`, stationary
    (no scenario here needs a moving unit; add a velocity field later if one does, not now).
  - `build_scenario_frames(ownship_start, legs, placed_units, poll_interval_s=5.0) ->
    list[Frame]`: integrates the legs into per-poll ownship telemetry
    (`position_x_m`/`position_y_m`/`position_z_m`, `pitch_rad`/`bank_rad`/`heading_true_rad`,
    `altitude_msl_m`/`altitude_agl_m`), converts each placed unit's fixed DCS x/z to lat/lon via
    world-model's `coordinates.dcs_to_wgs84` (the same real-geometry convention
    `mock_flight_canonical.json`'s own derivation used, not a monkeypatched transform), and emits
    `line_of_sight` verdicts of `building_clear=True, terrain_clear=True` for every placed unit on
    every frame (the flat, clear-by-construction world-model plane `build_mock_world_model`
    already provides for the terrain-LOS gate, matched here for the Hook-wire LOS gate so neither
    gate is the thing under test). `petrovich_indication` is left `None` throughout — these
    scenarios test the naked-eye/9K113 sight path the sortie feedback is about, not the Hybrid
    HelperAI channel, and leaving it unset keeps that channel contributing nothing rather than
    silently founding the contact a different way than the sortie did.
  - Fully deterministic by construction, no explicit seed needed: every per-look noise draw in
    `perception/estimation.py` and `naked_eye_source.py` is `hashlib.sha256` of a string built
    from the observation id/object id (`estimation.py:222`), not a stateful RNG — so a frame list
    built from a fixed `ownship_start`/leg list/unit list reproduces bit-identical believed
    positions on every run, the same property the existing `test_estimation.py` envelope tests
    already rely on.

- **New test file, `body-layer/tests/test_bl_b104_scenario_mock_flights.py`** — drives each
  scenario through the real threaded crew-text loop (`body._run_crew_text_poll_loop` +
  `belief.crew_console.CrewConsole`, the same pair `test_mock_flight_chain_threaded_crew_text_smoke`
  already wires, with `CrewConsole(output=io.StringIO())` so spoken lines are captured as text
  rather than needing a real audio adapter), issuing `"engage target"` (`CrewConsole.handle_line`)
  at the point in the scenario the sortie's own pilot commanded it, and asserting against:
  - **believed position/height vs. known truth** — `belief.tools.get_contacts`/`describe_contact`
    against `runner.store`, compared to each placed unit's real `(x, z, ground_alt_m)`;
  - **sight aim** — `runner.sight_head.world_az_true_deg`/`world_el_deg`/`aim_source`, the same
    fields `test_body.py`'s `TestSightLock*` tests and the atgm-run-sight-tracking plan's own
    `test_optic_policy.py` tests already read;
  - **speech** — the captured `io.StringIO` text, grepped for `render_tracking()`'s exact line and
    for callout suppression/resumption around the cockpit-mask cases below.

  Scenarios (each a `(ownship_start, legs, placed_units)` triple plus its own assertions
  function):
  1. **Run 1 shape — seen high, ~400 m descent, overflight.** Ownship starts level at the placed
     group's ground altitude + ~400 m, straight toward it; `Descend` leg losing ~400 m over the
     closing distance; continues past overflight. Asserts: the believed point is never above
     ownship at any poll (the sortie's own defect, alignment finding 2 — believed elevation tracks
     the true depression, never climbs to +72°); once masked overhead (cockpit-mask section below)
     the contact stops being spoken about rather than guided at a point in the sky.
  2. **Run 2 shape — shallow approach from 5 km at ~400 m AGL.** `Level` leg closing on the group
     at constant altitude from 5 km. Asserts: range error (believed vs. true ground range) stays
     inside the ~±700 m budget (plan's envelope table, 300 m AGL / 4 km row) and strictly shrinks
     poll-over-poll while closing, not merely "ends up small"; the sight is either already admitted
     within its wide field at `"engage target"` or the bearing-line search (`atgm-run-sight-
     tracking` plan) finds it within a bounded number of polls; `render_tracking()`'s line appears
     in the captured speech exactly once for the True→False→True-free span of this run (no
     duplicate "Tracking." while continuously seen).
  3. **Two groups on one bearing stay two contacts.** Two `PlacedUnit`s at, e.g., 3 km and 4.5 km
     on the same bearing, 150 m AGL level flight (mirrors Stage 4's own association scenario
     geometry, reused here as a scenario rather than a bare `ContactStore` drive) — asserts exactly
     two contacts throughout, each carrying only its own group's observations (no
     `CONTACT_CLASSIFICATION_CHANGED`/spurious merge events).
  4. **Cockpit-mask boundary cases** (the ones `implementation.md`'s Notable Discovery 4 flagged as
     untested): at 300 m AGL level flight, a unit directly ahead closing through the ~740 m
     forward-mask threshold (callout present beyond it, absent once inside — contact masked, not
     guided at a point behind the mask); a unit abeam closing through the ~1.7 km abeam-mask
     threshold, same assertion shape; and a `Descend`-to-attack-pitch leg that brings a forward
     target already inside the level-flight mask radius back into view (the mask angle moving with
     pitch, per `contacts._callout_may_speak`/`attack_run._no_look_cause`'s own geometry) — asserts
     the callout resumes once the nose comes down, without the contact ever having been reported
     while masked.

- **How a later feature adds a scenario**: a new `(ownship_start, legs, placed_units)` triple plus
  an assertions function in the same test file — no change to `mock_flight_scenario.py` unless a
  genuinely new leg shape or placed-unit property is needed (e.g. a moving unit, a second
  aircraft). The builder's job stops at "frames in the existing wire shape"; everything after that
  reuses `MockAircraftLayerServer`/`build_mock_world_model`/`_run_crew_text_poll_loop`/
  `CrewConsole` exactly as Stage 7's own tests and `test_mock_flight_chain.py` already do, so
  nothing about the harness itself needs to change to add scenario 5.

- Not built here: a moving-unit leg, a second aircraft/wingman, weapon-impact simulation,
  anything resembling record-and-replay (rejected above). `--slew-trace`/`--detection-trace`-style
  log output is not wired into these tests — they assert directly against `runner.store`/
  `runner.sight_head`/captured speech, the same shape `test_mock_flight_chain.py` and `test_body.py`
  already use, not a new logging-based assertion style.

### The cockpit-mask behaviour change (alignment "who else reads the believed altitude")

`contacts._callout_may_speak` and `attack_run._no_look_cause` test the believed position against
Petrovich's mask (22° down forward, 10° at 90°, 0° at 130°). Today both sides share the fake
ownship altitude, so a ground contact always looks level and is never masked. After Stage 2 the
real depression is used. Effect, at 300 m AGL in level flight: a ground contact closer than ~740 m
ahead or ~1.7 km abeam is now masked — callouts about it wait until it is visible again, and an
attack run that overflies its target reports "masked" instead of guiding at a point in the sky.

This makes belief agree with perception, which **already** applies the same mask to the truth
(`perception/visibility.py`) — Petrovich cannot see those units now; today he can still talk about
them as if he could. Planned as intended behaviour, covered by tests in Stage 2 (forward/abeam
boundary cases, and a pitched-down attack attitude that brings a forward target back into view),
and called out on the test card.

### Decisions taken here (local, reversible — revisit if they read wrong)

0. **The terrain-reference cue is a statistical error model only** — no terrain or feature query,
   no world-model lookup on the live path. User, 2026-10-30, verbatim: *"Since our simulation does
   not really see all the ground features, a statistical model for that will suffice. It'll be
   faster too."* (also appended to `explore-notes.md` under Q2).
1. **One judgement cue, not separate size and terrain cues.** Splitting them needs two unsourced
   numbers instead of one, and today's 0.17 already is the observer's whole range judgement. The
   9K113's size advantage is already its range scale. Sea needs no special case (Q3): cue A is the
   same, cue B works off sea level.
2. **Unit height read exactly from unit data, at a look only.** The user's direction (*"unit data
   has elevation"*, 2026-10-14; option A). It is not a position leak: it is the height of the ground
   the unit visibly stands on, and the true depression or range never crosses into belief. The
   stopgap already uses the same truth (`relative_direction.up_m` is truth-exact). A cluster's height
   is its members' mean (alignment's "heights of the units actually in that cluster").
3. **Reported range stays slant range to the believed ground point** — `relative_geometry` already
   computes it that way against the terrain-aware position, so this is the existing convention,
   now with a correct endpoint. It differs from horizontal by under 2 % beyond ~5× AGL and is what
   the eye perceives. The horizontal quantity is used where the model needs horizontal (percept
   range, fusion, truth-log error) — the slant-as-ground conflation alignment warns about is removed
   from the projection, not reintroduced in reporting.
4. **Air contacts unchanged** (Q5): flat model, ownship altitude at the look, today's range draw.
5. **`remembered_target_alt_m` narrowed, not deleted**: it still serves air contacts and keeps its
   callers; for surface contacts it returns belief's own height.

### Risks & Unknowns

- **Category values were never read live.** The `Type` field is documented. The enumeration comes
  from community sources that agree with each other, not from the installed `wsTypes.lua`. Still
  open: whether mission-placed static vehicles report `level1` 2 or 5 (surface either way under the
  rule above), and whether helicopters always report `level2` = 2. The Stage 1 WARNING log plus a
  one-shot `Type` dump on the Stage 6 card settles both. If the field were absent live, Stage 1
  falls back to option B: AGL from the LOS hook for every candidate, which is Stage 5's carrier
  generalised. That means more wire work but the same body-layer shape.
- **Helicopter AGL coverage**: the LOS hook covers the look wedge inside 10 km, which matches what
  the naked-eye channel admits. A helicopter admitted without a fresh hook record falls back to the
  air model. Acceptable for a rare case; stated so it is not discovered.
- **Systematic offset now scales with the fused σ**, so a heavily-observed close contact's floor is
  tighter than today's. Intended (closer = better), but it moves `position_belief`'s floor, which is
  computed from the declared single-look σ — the Stage 3 convergence test pins the interaction.
- **Gate tightening at steep geometry** could split a group whose members spread wider than the new
  σ when close — Stage 4 measures it; a failure stops the stage rather than retuning silently.
- **Cockpit-mask change** above is a felt behaviour change.
- **A ground unit moving over terrain** keeps the height of its last look between looks
  (alignment: never refreshed without a look). Error is the terrain slope over the distance moved;
  small at the cadence a watched contact is re-seen.
- **24 pre-existing test failures on `main`** (`fix/flexible-sequence-tests`, unrelated): the
  Implementer compares failures against `main`'s list, not against zero.
- **Stage 7's cockpit-mask boundary distances (~740 m forward, ~1.7 km abeam) are read off this
  plan's own stated figures, not re-derived from the mask geometry for the exact scenario attitude
  chosen.** If the actual threshold at the scenario's chosen altitude/attitude lands a few tens of
  metres off those figures, place the closing/abeam distances generously either side of the stated
  threshold (as the Stage 3 envelope test does for its own grid points) rather than exactly on it,
  so the test is not sensitive to the last-decimal value of a mask angle this stage does not own.
- **Dead-reckoned ownship integration (no aerodynamics) could produce an attitude DCS would never
  actually fly** (e.g. a `Turn` leg with no corresponding bank in the telemetry if the leg shape
  doesn't set one) — acceptable for a wiring/outcome proof the same way `build_mock_world_model`'s
  flat terrain is acceptable, but worth a one-line docstring note in `mock_flight_scenario.py` so a
  later reader doesn't mistake a leg's kinematics for a flight-model claim.

### Second-order effect

Narrows the live path's dependence on world-model terrain (ground contacts no longer need
`project_terrain_aware`), and gives `BL-B62` (relative channel as a general facility) a cleaner
boundary: the map belief now has its own honest vertical, so the relative channel is needed only
for what it was meant for — guidance while looking. A future air-contact model (Q5's "for now")
reuses the two-cue estimator with a different height source.

**On merge** (role step 10): amend `plans/attack-run/plan.md` Decision 4 REVISED with a pointer
(surface contacts now carry their own height in belief), and the `last_alt_m` memories
(`architect/project_last_alt_m_is_the_ownship_altitude.md`,
`debugger/project_contact_last_alt_m_flat_projection_trap.md`) to say the trap now applies to air
contacts only.

### Decisions Requiring User Input

None blocking. Two worth a glance before Stage 3 lands, both tunables with a stated default:

- **`DEPRESSION_SIGMA_DEG` starts at 3.0** — the bearing error's own value, i.e. your sentence read
  as the angle; the fusion turns that into the ~±700 m ground error you called sensible at
  300 m / 4 km. Lower it if Petrovich should firm up sooner when closing.
- **`HELI_SURFACE_AGL_MAX_M` starts at 10 m** for "landed or hovering a few metres up".
