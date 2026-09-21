# ED's native detection/identification model — gap analysis against our own model

**Date:** 2026-09-19
**DCS version:** 2.9.29.27278 (last confirmed install version, per prior sessions in
`2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`). Nothing in this session
contradicts that version; not re-verified live.
**Theatre:** n/a (scripting-API / native-model question, not terrain-specific)

> **PARTLY SUPERSEDED 2026-09-20 — read
> [`2026-09-20-dcs-install-detection-deep-read.md`](2026-09-20-dcs-install-detection-deep-read.md)
> alongside this.** `Scripts/AI/Detection.lua`, named below as the single highest-value unread
> artifact, has now been read on the Windows box. It **refutes this document's Finding 1
> conclusion that ED models neither movement nor dwell**: ED has a `motion_factor` (a detection-
> distance bonus up to 1.5x, keyed to angular speed over angular size) and an aspect- and
> class-dependent detection-*time* model, plus a scan-time term for optic sensors. The reasoning
> here was sound on the evidence available — the Mi-24P tree genuinely contains neither term — but
> the conclusion generalised from the module to the engine, and the engine file says otherwise.
> The rest of this document (the identification ladder, what is readable at runtime, the
> no-omniscience assessment) stands.

### Question

User, verbatim: *"ED native model should be researched in detail for detection and identification
logic. What is there that we have not thought of, what is there that we are missing?"* Five
sub-questions were posed (detection terms/formula, ED's identification ladder vs. our
UNKNOWN→PRESENCE→CLASS→TYPE lattice, bidirectional gap analysis — what we model that ED doesn't and
vice versa, what's readable at runtime and from where, weather/light readability). This is
reconnaissance for Architect, not a design decision — no pipeline code written.

This is **not a fresh investigation of DCS internals from zero**. It is a synthesis/gap-analysis
pass over evidence this project already gathered (`2026-09-08-pb1-5-worldobjects-filter-and-ambient-
detection.md`, six sessions, most of the hard native-file reading already done) plus three new
threads: `Scripts/AI/Detection.lua` (a lead, not yet read), live-readable weather (new, resolved
this session), and an explicit read of our own current model to make the comparison real rather
than generic.

### Our own model, restated (so the gap analysis has something concrete to compare against)

- **`body-layer/src/perception/visibility.py`** — naked-eye channel. Three independent gates
  (cockpit occlusion mask, angular-radius range threshold, terrain LOS), all must pass. The range
  threshold is `size_m / angular_radius_threshold_rad * BINOCULAR_RANGE_MULTIPLIER`, capped at
  10 km — this project's own derivation, calibrated 2026-09-17 against a 9-range in-game
  screenshot ladder (`body-layer/research/2026-09-17-vision-range-calibration-pass2.md`), not a
  reproduction of ED's own formula. Three recognition tiers (`lowres`/`medres`/`hires`), gated at
  `lowres` (presence only) since Stage 7 of `plans/classification-refinement/plan.md`.
- **`body-layer/src/perception/clustering.py`** — angular separability (disc-overlap: two objects
  merge when their angular separation is under half the sum of their apparent angular diameters),
  with a count derived from angular extent over mean angular unit size. Purely geometric,
  class-agnostic.
- **`hybrid_source.py`/`naked_eye_source.py`** — the two channels: HelperAI's real
  `list_indication(6)` text (a genuine detection-existence signal, `association.py`'s gate) and
  the synthetic `visibility.py` plausibility filter over unfiltered `LoGetWorldObjects` ground
  truth.
- **`belief/classification.py`** — a four-level totally-ordered lattice (UNKNOWN/PRESENCE/CLASS/
  TYPE) with an explicit fusion rule (`fold_classification`): refine on more-specific+consistent,
  reinforce on repeat, hold on less-specific, contradict-and-collapse-to-common-ancestor on
  same-or-higher-level disagreement, with a lockout against oscillation.
- **Explicitly flagged as unaddressed in our own code**: `min_contrast_f`, `min_fog_transparency`,
  `extra_eyesight_ratio`'s real native role (we repurposed the *number* 4.0 as a binocular
  magnification, not as whatever it actually multiplies in ED's code); movement as a detection cue
  (explicitly named in the 2026-09-17 ROADMAP entry: "movement is a strong real detection cue this
  does not model"); range uncertainty (belief holds ground-truth range, a documented omniscience
  leak, moved into the deferred "attention direction and detection cones" milestone 2026-09-19);
  attention/scan state and per-optic FOV splits (same deferred milestone).

### Findings

#### 1. ED's detection terms and formula

**`HelperAI.lua`** (Mi-24P-specific tuning file, fully read in a prior session — evidence:
reproduced-locally, file read) is the only DCS-shipped source found anywhere that states ED's
detection constants as plain numbers:

```lua
group_criterion              = 20      -- units, grouping threshold
min_angular_radius_for_group = 0.05    -- rad
scan_rad_around_point        = 2500    -- m
min_angular_radius = { lowres = 0.0043, medres = 0.008, hires = 0.02, iff = 0.025 }  -- rad
min_contrast_f               = 0.001
extra_eyesight_ratio         = 4.0
min_fog_transparency         = 0.3
slowpoke_search_radius       = 15
atgm_range_114 = 4500 ; atgm_range_120 = 6000
```

- **`min_angular_radius` is a real angular-size-vs-range curve, per recognition tier** — evidence:
  reproduced-locally (the constant exists; the *tier semantics* `lowres`=existence/`medres`,`hires`
  =classification/`iff`=friend-foe are **inferred from naming convention only**, not documented
  anywhere — a prior session (`2026-09-08...` Session 6, Q1) grepped this exact string across every
  Lua file in the Mi-24P tree and across six binaries via `strings`, and found **zero other
  reference to it anywhere** — the value is defined once and consumed entirely natively. This is a
  genuine, verified negative (absence confirmed by direct grep/strings sweep), not an unread gap,
  with the stated caveat that a hashed/interned string comparison in native code would be invisible
  to a `strings` scan.
- **`min_contrast_f`, `min_fog_transparency`, `extra_eyesight_ratio` have never been located in any
  consuming code** — same Session 6 sweep, same result: defined once, zero other references in any
  synced Lua file. Their exact algebraic role (multiplicative term? threshold subtracted from the
  angular-radius test? gate applied before or after the angular check?) is **not documented
  anywhere and not derivable from any file this project has read.** This is the single largest gap
  between "we have ED's numbers" and "we have ED's formula" — we have three of the numbers, and
  zero of the equation they belong to.
- **No dwell/time-integration term exists in any Lua-visible constant** — Session 6 Q4, same
  exhaustive-grep method, applied to every `HelperAI.lua` constant (`slowpoke_*`, `safety_switch_
  time`, `usr_time`, `scho_time`, `pn_time`, `shoot_in_time`, `device_timer_dt`). None is
  referenced outside its own definition line; the `slowpoke_*` cluster reads by name as a
  hard-to-reacquire-target search-loop heuristic (Petrovich's own scan pattern), not a
  per-target recognition-confidence accumulator, and the `*_time`/`atgm_range_*` cluster reads as
  an ATGM launch-sequence timer group. **This is evidence — not proof — that ED's detection
  criterion is per-frame/instantaneous, not time-integrated.** Our own model has no dwell term
  either. Where ED and our model plausibly agree (see gap table).
- **This project's own `visibility.py` reads the tier-boundary numbers backwards from real
  screenshots, not from `HelperAI.lua`'s original values** (`MEDRES` 0.008→0.014, `HIRES`
  0.02→0.028, `LOWRES` 0.0043→0.003, per the 2026-09-17 calibration). This is worth stating
  plainly: **our current constants are no longer even claiming to be ED's own values** — they
  started there and were corrected against observed in-game behavior when the originals proved
  wrong in both directions (over-generous classification, under-generous presence). This is a
  defensible modeling choice (measured behavior beats an unverified internal constant whose
  consuming formula we don't have), but it means any future claim of "matching ED's model" should
  be understood as "matching ED's *outcomes*, not ED's *formula*" — we don't have the formula.
- **`Scripts/AI/Detection.lua` exists and has never been read.** Grep of the local DCS install
  listing (`world-model/data/raw/dcs/2026-09-02/DCS-files.txt`, checked before asking the user for
  anything, per project convention) surfaces `./Scripts/AI/Detection.lua` — a **generic,
  engine-wide** AI detection script, outside any aircraft module's own directory, alongside
  `Scripts/AI/CarsConstants.lua`, `Scripts/AI/Skill_Factors.lua`, `Scripts/AI/Shells_By_Target_
  Types.lua`. This is the single most plausible location for the *general* ground-unit/AI
  detection algorithm that `min_contrast_f`/`min_fog_transparency`/`extra_eyesight_ratio` actually
  belong to — `HelperAI.lua` reads as a per-aircraft *tuning* override into a shared engine
  mechanism, not a self-contained algorithm, and this file is exactly the kind of shared location
  that would hold it. **Not fetched or read this session** — no path from this Mac session to the
  Windows DCS install's actual file content (only a filename listing is available locally; the
  content-sync directory `win-mac-sync/from-windows/` does not contain it). **This is the highest-
  value single next artifact to pull** — see Possible Approaches.

#### 2. ED's identification ladder

**Real, and it is a near-exact structural analogue of our PRESENCE→CLASS→TYPE lattice — but it is
not gated by "distance known" at all, and it tops out one level below ours.**

- The ambient/naked-eye callout (`"N CONTACTS, H O'CLOCK"`, confirmed live via a user-supplied
  screenshot and cross-checked against `HelperAI_lengths_ng.lua`'s composed-speech fragment bank —
  evidence: reproduced-locally, full file read) has a fixed vocabulary of exactly the shape our
  lattice predicts: a **count** bucket (`OP_1UNIT` … `OP_MORETHAN15UNITS`, 7 buckets — this
  project's own `belief.cardinality`/`clustering.count_bucket_for` mirrors this vocabulary
  directly, already, by design), a **bucketed range** (`OP_D100M`…`OP_D10k`, 24 buckets), a
  **clock bearing** (12 positions), elevation (higher/lower), and a **coarse class** (`OP_ARMORED`,
  `OP_TRUCK(S)`, `OP_INFANTRY`, `OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`, `OP_SPAAG`, `OP_ZU23`,
  `OP_SHIP(S)`, plus air classes). **This is functionally our PRESENCE/CLASS levels, expressed as
  ED's own output vocabulary** — evidence: reproduced-locally (exhaustive fragment-bank read,
  Session 6 Q2).
- **The scope/HelperAI channel (`list_indication(6)`) is a separate, richer signal that reaches a
  fourth level ED's ambient callout never does**: specific reporting names ("Ural truck", "Slava
  cruiser", "SA-3 Low Blow radar") drawn from a flat 376-entry `unit_type → display_name` lookup
  table (`HelperAI_reporting_names.lua`, evidence: reproduced-locally, full read). This is our
  TYPE level's ED analogue.
- **"Distance known" as a separate flag does not exist anywhere in the Lua-readable surface.**
  Neither channel exposes a numeric range as a distinct field — the ambient callout *buckets*
  range into one of its 24 fragments (itself a form of "range known, but only this coarsely"),
  while the scope channel's `list_indication` text carries **no numeric field of any kind**,
  confirmed across ~4000 live samples in the original PB-1/PB-1.5 spike
  (`aircraft-layer/CLAUDE.md`'s own standing note: "No numeric field exists anywhere in this feed
  ... bearing/range are never derivable from Petrovich's own systems, only from
  `/world_objects/latest` via association"). **This directly answers the user's specific concern**:
  ED itself never hands the crew (or Petrovich) a raw number for range — even its own richest
  channel only ever bucketed it into one of 24 named ranges via the ambient callout, or omitted it
  entirely via the scope channel. **Our current practice of handing belief a ground-truth range is
  a real omniscience leak that ED's own native model does not have an equivalent of** — ED never
  computes an exact range for its crew-facing output either; it only ever had one internally to
  decide which bucket to speak. This is strong, reproduced-locally evidence for the direction
  already taken in the 2026-09-19 ROADMAP move (range vagueness into the deferred
  attention-cones milestone) — it is not a new problem this investigation surfaces, but it *is* the
  first time it's grounded in what ED itself actually exposes, rather than argued from first
  principles.
- **ED's ladder has no "type known" step distinct from what our lattice calls CLASS vs. TYPE within
  the *same* channel** — ED gets there by switching channels entirely (ambient callout is
  permanently capped at class; the scope channel, once populated, is permanently at full specific
  name — Session 6 Q3 found no range-conditional logic anywhere near the `list_indication` text
  controllers, and no consumer of any distance/range value anywhere in the three UI-definition
  files that build that tree). **Our lattice instead treats specificity as continuous and
  range-dependent within one channel (naked-eye) via three angular-radius tiers, which ED's own
  ambient channel does not do at all** — ED's ambient channel has exactly one specificity level
  (coarse class), gated by presence-only vs. class-populated, not by a graded range-to-tier curve.
  **This is a place we have built something ED does not have**, not a gap in our favor or against
  it — see gap table.

#### 3. What we model that ED does not, and vice versa (bidirectional)

- **Movement as a detection cue: neither model has it, contrary to the user's stated
  expectation that this would be "our biggest single gap."** Every timer/motion-adjacent constant
  in `HelperAI.lua` was exhaustively grepped (Session 6 Q4) and none references a velocity term
  feeding the angular-radius/contrast detection gate — the `min_angular_radius` curve is
  a pure static geometric threshold (size vs. range), with no time-integration or velocity
  modifier found anywhere in the Lua-visible surface. This is corroborated by the 2026-09-17
  screenshot ladder, which used static targets throughout and is explicitly flagged in
  `body-layer/ROADMAP.md` as leaving movement untested. **So this is a real gap in our model, but
  the evidence does not support "ED has it and we don't" — the honest framing is "neither model has
  a verified movement term, and ED's own file structure (a purely geometric angular-size curve)
  gives no indication one exists internally either."** This matters for the recommendation: it
  removes "reproduce ED's movement term" as an option (there may be nothing to reproduce), and
  reframes the choice as an independent design decision, not a catch-up.
- **Unit size/signature fields in a unit database.** Both models use a *characteristic size*
  driving the angular-radius calculation — ED's is presumably per-unit-type internally (never
  located in any Lua file; `object_model.size_m()`, our own lookup, was not re-read this session
  but is the direct analogue). **Not confirmed whether ED's per-type size figures are Lua-readable
  anywhere** — the community-mod `db_units_cars.lua`/`db_units_ships.lua` files found in the file
  listing belong to third-party asset packs (ColdWarAssetsPack, Currenthill Assets Pack,
  HeavyMetalCore), not to core/stock DCS, and were not opened this session. **Unresolved — see
  below.**
- **Aspect (angle-on-target) and camouflage/concealment attributes.** No evidence either way. No
  file read in this or any prior session names an aspect or camouflage term anywhere near the
  detection constants. Neither our model nor any confirmed ED source has this. Genuinely
  unresolved, not a confirmed negative — nothing was specifically searched for these two terms this
  session beyond the general `HelperAI.lua` sweep (which is Mi-24P-tuning-scoped and would not
  contain a general-engine aspect term even if one exists).
- **Vegetation/tree occlusion.** Our terrain LOS gate (`perception.geometry.line_of_sight_clear`,
  reused as-is by `visibility.py`) samples world-model's DEM-derived elevation grid — bare-earth
  terrain only, per this project's standing world-model scope (vegetation/buildings flagged as
  "relevant later" in prior investigator memory, `project_terrain_semantics_future_features.md`).
  **Confirmed our LOS gate does not model vegetation occlusion at all.** Whether ED's own engine
  models trees as LOS-blocking for AI detection was not investigated this session (out of scope of
  the files read); DCS's forest rendering uses SpeedTree (`bin/speedtree7.dll`, confirmed present
  in the file listing) which is a rendering-layer technology, not evidence either way about whether
  the *gameplay* LOS/detection model treats forest canopy as opaque. **Unresolved.**
- **Sensor field of view and scan.** ED's `min_angular_radius_for_group`/`scan_rad_around_point`
  constants hint at a spatial search-radius concept (`scan_rad_around_point = 2500`, superseded in
  our own `visibility.py` history — see that module's docstring on why this constant was rejected
  as a range cap: it was found to bind *every* ground vehicle, defeating the angular-size curve,
  and the pilot observed contacts beyond 2500 m). **No FOV-cone or scan-pattern term was found
  anywhere in the Lua-visible surface** — this is consistent with the deferred "attention direction
  and detection cones" milestone description's own framing ("today's channels implicitly assume
  Petrovich is looking everywhere at once within range/FOV gates" — that gap is already
  self-diagnosed in our roadmap, not newly discovered here). Nothing in this session's evidence
  informs that milestone's design beyond confirming ED's own naming (`scan_rad_around_point`)
  doesn't describe a cone or scan sweep — it describes (per its rejected use in our own code) a
  flat radius, which the deferred milestone should not treat as an authoritative ED precedent for
  its own cone design.
- **What we have that ED's ambient channel does not**: a *continuous*, range-graded three-tier
  angular-radius classification curve within one channel (naked-eye), vs. ED's ambient channel's
  single coarse-class step. Also: a fusion/lattice with explicit contradiction-collapse and
  reinforcement (`fold_classification`) — nothing found in any ED source suggests the native engine
  tracks a *belief history* across observations at all; every ED signal found is presented as
  current/instantaneous state (a currently-populated list row, a currently-firing callout), with no
  evidence of persistence, decay, or fusion across observations. **Our belief-layer memory
  machinery (decay, contradiction lockout, reinforcement) has no ED analogue found anywhere** — not
  because ED forgot it, but because ED's job (a game AI that always has ground truth internally) is
  different from ours (a model that must degrade honestly). This is worth stating explicitly to
  Architect: it is not a gap to close, it is the actual point of this project's departure from
  ED's model.

#### 4. What is readable at runtime, and from where

Restating and extending the aircraft-layer's existing, live-confirmed picture
(`aircraft-layer/CLAUDE.md`):

- **`Export.lua` environment** (what the current live pipeline is built on): `LoGetWorldObjects`
  (unfiltered ground truth, no filter args beyond a category string — documented,
  `Export.lua.reference-file-from-DCS-installation.lua` lines 624-629), `list_indication(6)`
  (HelperAI's real detection-existence text, no numeric fields), `Export.LoGetVectorWindVelocity`/
  `Export.LoGetWindAtPoint` (confirmed present in `Sim_ControlAPI.md`, live-readable wind — not
  previously flagged as available in this project's research). **No fog/visibility/cloud/light-
  level getter of any kind exists in the `Export.lua` environment** — a full grep of the reference
  file for `fog|visib|cloud|precip|light` this session returns only weapon-station/cockpit-light
  *commands* (`command = 175 -- On-board lights`), never an environment-state reader.
- **Mission Scripting environment (`world.weather` singleton, trigger/do-script context) — a
  different, separate Lua sandbox from `Export.lua`, per this project's own already-established
  finding (`project_aircraft_layer_live_io.md`: "Export.lua ≠ Mission Scripting sandbox").**
  `world.weather.getFogThickness()` and `world.weather.getFogVisibilityDistance()` are real,
  documented **getters** (not just the setters this project's roadmap entry assumed) — confirmed
  via Hoggit wiki fetch this session (`wiki.hoggitworld.com/view/DCS_func_getFogThickness`,
  signature `number world.weather.getFogThickness()`, "Returns the current fog thickness in
  meters. Returns zero if fog is not present," added DCS 2.9.10). **Evidence: documented (fetched
  from the wiki directly, not a WebSearch-summary artifact this time — the URL resolved and was
  read).** `timer.getTime()` (elapsed mission seconds, pauses with the game) and a distinct
  `timer.getAbsTime()` were also found in the same environment, implying absolute-time (and by
  extension, with the mission's date, sun-angle-derivable) state is queryable from Mission
  Scripting — **not independently confirmed this session; the wiki fetch for `getTime` returned
  content but did not resolve `getAbsTime`'s own signature, only that it's a sibling name.** No
  cloud-density or direct sun-altitude getter was found in either environment.
- **This is architecturally significant, not just a trivia find**: because `world.weather` lives in
  the Mission Scripting sandbox, not `Export.lua`, **it is not reachable by the aircraft-layer's
  existing live pipeline at all** — the same way F10 radio-menu commands needed a separate Hook
  channel (`net.dostring_in("scripting", ...)`, confirmed live-working per
  `project_f10_radio_menu_command.md`) rather than `Export.lua`. A weather-reading channel would
  need the same pattern: a Hook script polling via `net.dostring_in("mission", "return
  world.weather.getFogThickness()")` (or similar) and forwarding the result over the existing
  loopback-UDP/collector mechanism — not a Export.lua addition. This is a real, buildable path, not
  a dead end, but it's a different implementation shape than "just read another Export.lua field."
- **Hook/GUI environment** (`Sim_ControlAPI.md`, already locally synced and read in full this
  session): no weather/fog/visibility function of any kind is documented there — confirms weather
  must come from the Mission Scripting environment specifically, bridged via `net.dostring_in`,
  matching the F10-commands precedent exactly.

#### 5. Weather and light

Directly answered by Finding 4 above: **`world.weather.getFogThickness()` and
`getFogVisibilityDistance()` are real, live-readable getters, but only from Mission Scripting, not
from Export.lua** — this reverses this project's prior working assumption (aircraft-layer's own
`CLAUDE.md` implicitly treats weather as `.miz`-only, and the body-layer ROADMAP task list flags
weather/light as "needing an investigator pass before any conditions work is planned," without
stating whether any live reader exists at all). It does now have an answer: yes, a live path
exists, gated behind the same Hook-bridge pattern already proven for F10 commands. Cloud
density/light-level specifically remain **not found** — the Hoggit search for a general
"Category:Environment" listing 404'd, and no targeted getter for cloud base/density or ambient
light level was located this session. This is a real gap in the search, not a confirmed absence —
see Unresolved.

### Gap Table

| Dimension | ED has it | We have it | Verdict |
|---|---|---|---|
| Angular-size-vs-range detection curve | Yes (`min_angular_radius`, 4 tiers) — documented as a constant, formula/consumer undocumented | Yes — `visibility.py`, recalibrated against screenshots, not ED's raw numbers | **Both, differently.** Worth keeping our recalibrated numbers; don't "correct" them back toward ED's originals without new evidence — see visibility.py's own docstring warning against exactly this. |
| Contrast term (`min_contrast_f`) | Possibly (constant exists, consumer never found) | No | **ED maybe, we don't.** Not worth modeling until the formula is found — we'd be guessing at both the ED value's role and our own substitute. |
| Fog transparency term (`min_fog_transparency`) | Possibly (constant exists, consumer never found; but a *separate*, confirmed-live `world.weather.getFogThickness()` getter exists) | No | **ED maybe (internally) + a real live signal exists (externally).** This is the strongest "worth building" item in this table — see Possible Approaches. |
| Movement as a detection cue | **No confirmed evidence either way** — no term found in any Lua-visible constant, contrary to expectation | No (explicitly flagged gap in our own ROADMAP) | **Neither, confirmed.** Not "ED has it, we're missing it" — an open design surface for us, not a catch-up. |
| Dwell/time-integrated recognition | No (exhaustive negative, Session 6 Q4) | No | **Neither.** Consistent; no departure to justify either way. |
| Unit size/characteristic-size lookup | Presumably yes internally; Lua-readability unconfirmed | Yes (`object_model.size_m()`) | **Both, unconfirmed on ED's side.** Not urgent — our own value is what actually matters here. |
| Aspect / angle-on-target | Unconfirmed, not specifically searched | No | **Unresolved both ways.** |
| Camouflage/concealment | Unconfirmed, not specifically searched | No | **Unresolved both ways.** |
| Vegetation/tree LOS occlusion | Unconfirmed (rendering tech present, gameplay-model unconfirmed) | No (DEM-only LOS, confirmed) | **Unresolved on ED's side; confirmed absent on ours.** |
| Sensor FOV / scan pattern | No term found; `scan_rad_around_point` reads as a flat radius, not a cone (and was rejected from our own range-cap use for exactly that reason) | No (deferred milestone, self-diagnosed already) | **Neither confirmed; don't treat ED's `scan_rad_around_point` as cone precedent.** |
| Identification ladder (presence→class→type) | Yes — ambient callout (presence+class) + scope channel (type), across two separate channels | Yes — one continuous lattice, one channel (naked-eye) grading through all three tiers by range | **Both, differently — ours is more capable (continuous) than ED's ambient channel (fixed one-shot class), but that's a design choice we made, not something we copied.** |
| "Distance known" as an explicit ladder step | **No** — ED never exposes numeric range on any crew-facing channel; only ever buckets it (ambient) or omits it (scope) | **No, but worse** — belief currently holds ground-truth range, a known/flagged omniscience leak | **We have a real gap ED's own model doesn't have an equivalent of.** Directly corroborates the 2026-09-19 ROADMAP decision to move range uncertainty into the deferred attention-cones milestone — do it; ED's own restraint here is evidence the instinct was right, not just an internal argument. |
| Belief persistence/decay/fusion across observations | Not found anywhere (everything ED exposes reads as instantaneous state) | Yes (`decay.py`, `fold_classification`, contradiction lockout) | **We have it, ED (as far as Lua-visible) doesn't — and shouldn't be expected to.** This is the actual point of departure the project exists for; not a gap to close. |
| Live weather (fog thickness/visibility) reading | Yes — `world.weather.getFogThickness()`/`getFogVisibilityDistance()`, Mission Scripting only | No | **ED has it, we don't, and it's reachable.** See Possible Approaches — needs the same Hook-bridge pattern as F10 commands, not an Export.lua change. |
| Live time-of-day / sun angle | Plausible (`timer.getAbsTime()` sibling found, not confirmed) | No | **Unresolved, worth a follow-up fetch, not urgent.** |
| Cloud density / ambient light level | Not found this session | No | **Unresolved — the search gap, not a confirmed absence.** |

### Reproducible Test

Nothing executed live this session (no DCS access from this Mac session; per the project's
standing execution-boundary rule, live sessions run on the user's Windows box). Three concrete
probes, in priority order:

1. **Fetch `Scripts/AI/Detection.lua`** (and its siblings `CarsConstants.lua`, `Skill_Factors.lua`,
   `Shells_By_Target_Types.lua`) from the Windows DCS install to `win-mac-sync/from-windows/`, the
   same sync mechanism already used for every other file this project has read
   (`PKV_init.lua`, `HelperAI.lua`, etc.). This is a **file read, not a live probe** — cheapest
   possible next step, and the single most likely source to finally locate the consumer of
   `min_contrast_f`/`min_fog_transparency`/`extra_eyesight_ratio`.
2. **Live-probe `world.weather.getFogThickness()`/`getFogVisibilityDistance()` reachability via a
   Hook script**, mirroring `dcs-export/petrobrain-f10-commands-hook.lua`'s already-proven
   `net.dostring_in("scripting", ...)`/poll pattern (confirmed live-working per
   `project_f10_radio_menu_command.md`) — except targeting the **"mission"** sandbox
   (`net.dostring_in("mission", "return world.weather.getFogThickness()")`) rather than
   `"scripting"`, since `world.weather` is a Mission Scripting table, not a Hook-state one. This
   distinction (`"scripting"` vs `"mission"` as the `net.dostring_in` target) has not been tested
   by this project for *any* prior channel — the F10 precedent used `"scripting"` because the
   `missionCommands`/menu API lives there; whether `net.dostring_in("mission", ...)` can reach
   `world.weather` from a Hook script's context at all is itself unverified and should be the
   probe's first checkpoint before building anything further on top of it.
3. **Confirm `timer.getAbsTime()`'s actual signature and whether a mission's calendar date is
   independently queryable** (`env.mission.date`? a `Weather.dll`-backed sun-angle function?) — a
   Hoggit wiki fetch of `wiki.hoggitworld.com/view/DCS_func_getAbsTime` directly (not via
   WebSearch summary) would settle this in one call; not done this session due to time, not
   difficulty.

### Possible Approaches

- **Do not chase ED's exact detection formula further without reading `Detection.lua` first.**
  Every avenue *within* `HelperAI.lua` and the Mi-24P Lua tree is now exhausted (three separate
  exhaustive-grep sessions, zero consumers found) — the only path left that isn't disassembly is
  the generic engine file. If it also turns out to be pure constant-definition with a native
  consumer, that's a clean, final negative worth recording and closing this line of inquiry for
  good; if it has actual logic, it may finally answer what `min_contrast_f`/`min_fog_transparency`
  multiply and in what order relative to the angular-radius test.
- **Weather is worth building, on the strength of this session's finding.** A real, documented,
  live getter exists (`world.weather.getFogThickness`/`getFogVisibilityDistance`), reachable by the
  same architectural pattern (Hook → `net.dostring_in` → loopback UDP → collector → LAN API) this
  project has already built once for F10 commands and validated live. This directly unblocks the
  body-layer backlog item flagging weather/light as needing an investigator pass — the pass is
  done, the answer is "buildable, but not via Export.lua, and the `net.dostring_in("mission", ...)`
  reachability itself needs one more live checkpoint before committing to a design (probe #2
  above)."
- **Do not model movement as "catching up to ED"** — the evidence this session found is that ED's
  own detection curve (as far as any Lua-visible file shows) has no movement term either. If
  Architect wants to add movement sensitivity to `visibility.py`, it should be scoped and justified
  as this project's own modeling choice (real-world detectability is genuinely movement-sensitive,
  independent of whether ED's engine happens to model it), not as reproducing an ED mechanism —
  there may be nothing there to reproduce. This changes the framing but not necessarily the
  priority; the user's instinct that this is a real gap worth closing stands regardless of ED's own
  behavior.
- **Keep the range-uncertainty work already scheduled in the deferred attention-cones milestone as
  scoped** — this session's Finding 2 is corroborating evidence, not new scope. ED's own restraint
  (never exposing a raw number, even on its richest channel) is a second independent argument for
  the same conclusion the project had already reached from the no-omniscience invariant alone.
- **Do not treat `OP_GROUPSOMETHING`/the ambient channel's one-shot class ceiling as something to
  imitate for our naked-eye channel's upper tiers.** ED's ambient channel is capped at coarse class
  by construction (a fixed fragment bank with no per-model vocabulary at all — Session 6 Q2's
  exhaustive read). Our own continuous, range-graded three-tier curve is *already* a deliberate,
  documented departure from that (`visibility.py`'s own docstring: "our tier semantics are our own
  modelling choice, not verified against ED internals"). This session's evidence supports keeping
  that departure, not walking it back — ED's ceiling looks like an engineering/asset-bank
  simplification (a fixed WAV-duration table), not a considered perceptual model worth copying
  exactly.
- **No omniscience risk identified in any of this session's findings that isn't already flagged.**
  Every ED-exposed field found this session (fog thickness/visibility distance, wind, elapsed
  time) is either genuinely crew-perceivable (a pilot/gunner can feel/see fog and wind) or already
  excluded from consideration (a raw numeric range was explicitly checked and found *not* to be
  something ED itself ever exposes on a crew-facing channel — reinforcing rather than undermining
  the no-omniscience posture). Flag for Architect regardless: if a future weather channel is built,
  it should report the same *bucketed/qualitative* shape ED's own crew-facing outputs use
  elsewhere (a thickness-in-meters number is more precise than what a crew member would actually
  say — "fog is getting thick" vs. "fog thickness is 340 m" — the same anti-omniscience
  quantisation this project already applies to range and count).

### Unresolved

- ~~**`Scripts/AI/Detection.lua` unread**~~ — **RESOLVED 2026-09-20**, read on the Windows box:
  `2026-09-20-dcs-install-detection-deep-read.md` finding 1.
- ~~**Whether `min_contrast_f`/`min_fog_transparency`/`extra_eyesight_ratio` are consumed anywhere
  in the DCS install at all**~~ — **RESOLVED 2026-09-20.** The whole-install Lua sweep is now a
  clean negative (three hits, all definitions), and `CockpitMi24.dll`'s import table shows the
  consumer is the engine's own `wDetector`, which `Detection.lua` configures. See finding 5 of
  `2026-09-20-dcs-install-detection-deep-read.md`.
- **Whether `net.dostring_in("mission", ...)` can reach `world.weather` from a Hook script's own
  execution context** — architecturally plausible (the F10 precedent proves the general
  `net.dostring_in` + poll mechanism works from a Hook script), but the `"mission"` target string
  specifically has never been tested by this project. This is the one live checkpoint standing
  between "documented API exists" and "buildable channel."
- **Cloud density and ambient light level** — no getter found, but the search was not exhaustive
  (the Hoggit `Category:Environment` index page 404'd; a `Category:Functions` fallback listing was
  returned by search but not opened). A direct fetch of that category page, or of
  `DCS_func_getAbsTime`, would close this with one more tool call each.
- ~~**Whether ED's engine treats forest/vegetation as LOS-opaque for AI detection purposes**~~ —
  **RESOLVED 2026-09-20: yes, on every terrain this project uses.** `trees_LOS_test_T4 = true` and
  all five installed theatres are Terrain-4. Finding 8 of the 2026-09-20 deep read.
- **Aspect and camouflage/concealment** — not specifically searched for beyond the general
  `HelperAI.lua` constant sweep; a targeted grep of `Scripts/AI/Detection.lua` (once fetched) and a
  targeted Hoggit/forum search for these two terms specifically would be the next step if Architect
  judges them worth resolving before any aspect-aware design work.
- **Per-unit-type characteristic size — whether ED's own value is Lua-readable anywhere in core
  DCS** (not a third-party asset-pack `db_units_*.lua`, which was found but not opened and belongs
  to community mods, not stock content). **Answered negatively 2026-09-20** for stock units: they
  live in the encrypted `Scripts/Database.edce`, and `Detection.lua` only carries per-*class*
  distances. The live `Unit.getDesc().box` route remains untested.
