# DCS install deep read — ED's detection model, and five questions that were waiting for this box

<!-- doc-provenance:start -->
**Evidence for:** [[AA-3]]
<!-- doc-provenance:end -->

**Date:** 2026-09-20
**DCS version:** 2.9.29.27278 (build `20260826-084519`, read from `autoupdate.cfg` this session)
**Theatre:** n/a for the detection model (engine-wide `Scripts/AI/`); terrain-generation finding
checked against all five installed terrains (Syria, Caucasus, Kola, Afghanistan, MarianaIslands)
**Machine:** the Windows/DCS box. `$DCS_INSTALL_PATH` = `F:\Games\DCS World`. DCS was **not
running**, so nothing here is a live probe — every finding is a file or binary read.

### Question

Clear the backlog of items explicitly parked as "needs the Windows box." Five were outstanding:

1. **Read `Scripts/AI/Detection.lua`** — named in
   `2026-09-19-ed-native-detection-identification-gap-analysis.md` as *"the single highest-value
   thing to read on the Windows box"* and in `body-layer/ROADMAP.md`'s cones-milestone prerequisite.
2. **Find the consumer of `min_contrast_f` / `min_fog_transparency` / `extra_eyesight_ratio`** —
   three sessions of grepping the Mi-24P tree had found none.
3. **Does ED treat forest/vegetation as LOS-opaque for AI detection?** (`body-layer/ROADMAP.md`,
   "Detection under real world conditions", factor 1.)
4. **Is unit velocity available from `LoGetWorldObjects`?** — the one build-blocking unknown in the
   movement-detection design recorded 2026-09-20.
5. **SPU-8 intercom switch and volume knob device arguments** — `audio-adapter/ROADMAP.md` slice 2,
   *"an investigator pass plus a probe on the Windows box."*

All five are answered below. Two of them **refute claims currently written into the roadmap**.

---

### Findings

#### 1. `Scripts/AI/Detection.lua` exists, is plaintext, and is the engine's whole visual-detection tuning file

— **evidence:** reproduced-locally — **source:** `$DCS_INSTALL_PATH/Scripts/AI/Detection.lua`
(6123 bytes, mtime 2025-06-26), read in full.

132 lines, three top-level tables: `visual_detection`, `detection_by_optic_sensor`,
`detection_by_radar`. It is pure data — no functions, no logic. Its provenance markers are worth
noting because they establish it is live rather than vestigial: one constant carries an ED Jira
reference (`https://jira.eagle.ru/browse/DCSCORE-5960 , Andrey request increase ships visibility`)
and another a dated tuning note (`21.11.24 new fogg threshold tune for new fogg`).

The parts that bear on this project:

```lua
terrain_LOS_test = true,  Earth_curvature_LOS_test = true,  objects_LOS_test = true,
trees_LOS_test = false,   trees_LOS_test_T4 = true,
recognition_distance_ratio_threshold = 0.25,   -- naked eye
max_detection_distance = 50000.0,
average_det_time_max_dist_0   = 1.0,   average_det_time_max_dist_180   = 10.0,
average_det_time_max_dist_0_for_ground_units = 10.0,
average_det_time_max_dist_180_for_ground_units = 60.0,
atmosphere_transparency_factor = {          -- visibility_km = exp((h1_km + h2_km) * k + b)
    max_visibility_at_ground_level = 10000.0,
    max_visibility_at = { detector_altitude = 4000, target_altitude = 0.0, max_visibility = 42000 },
    fog_transparency_threshold = 0.085 },
in_reflected_light = {
    fixed_size_target_detection = { target_size = 6.0, detection_distance = 5500.0 },
    detection_distance_by_class = { ["Ground vehicles"] = {3300.0, 5500.0},  -- ground / airborne detector
                                    ["Infantry"] = {800.0, 800.0}, ["Helicopters"] = 6500.0, ... } },
motion_factor = { angular_speed_to_angular_size_ratio_max = 10.0,
                  detection_distance_factor_max = 1.5 },
background_factors = {   -- "reduces detection distance of airborne targets ONLY!"
    [AIR]=1.0, [LAND]=0.6, [FOREST]=0.3, [ROAD]=0.8, [RUNWAY]=0.8, [WATER]=0.75 },

detection_by_optic_sensor = {
    scan_time_for_double_scan_to_view_angular_square_ratio = 0.1,
    recognition_distance_ratio_threshold = 0.5,   -- optics, vs 0.25 naked eye
    IR_view_trough_fog_and_overcast = false }
```

The header comment states the conditions the distances are quoted under, which matters for any
comparison: *"skill = excelent, LOS present, no fog, illumination = 1.0, background = air,
non-moving target, no nearly located targets, no smokes, target is not shooting, no dust and
inversion tail, no lights."*

#### 2. **ED does model movement, and it models dwell. The 2026-09-19 desk pass got this backwards.**

— **evidence:** reproduced-locally — **source:** `Detection.lua:90-93`, `:33-36`, `:109`

`body-layer/ROADMAP.md` currently says, as the first of four results carried forward from the desk
pass: *"The movement suspicion was wrong, and that is useful. … **Neither ED nor we model movement
or dwell.** So it is not catch-up."* **Both halves of that are false.** The desk pass reached them
honestly — it had exhausted the Mi-24P tree and could not read this file — but the conclusion must
not stand, because the cones milestone's own framing was built on it.

- **Movement** is `motion_factor`: a multiplicative bonus on detection *distance*, up to **1.5×**,
  driven by the ratio of angular speed to angular size, saturating at **10.0**.
- **Dwell** is `average_det_time_max_dist_*`: detection is not instantaneous, it takes an average
  time that depends on **aspect** (ahead vs. behind) and on **target class** (ground units are much
  slower to find), modulated per skill by `VISUAL_AND_OPTIC_DETECITON_TIME_FACTOR` (finding 4).
- **Scan pattern** is `detection_by_optic_sensor`: detection time scales with the ratio between the
  scanned angular area and the instrument's field of view.

This is the part of the cones milestone described in `body-layer/ROADMAP.md` as *"the one part with
no precedent anywhere in this codebase."* There is now a precedent, with numbers.

#### 3. ED's motion term is range-invariant, and is a different quantity from ours

— **evidence:** inferred (algebra over finding 1's constants) — **source:** `Detection.lua:90-93`

ED's ratio is angular speed over angular size. Both scale as `1/range`, so **range cancels**:

```
ratio = (v_perp / r) / (size / r) = v_perp / size          [body-lengths per second]
```

So `angular_speed_to_angular_size_ratio_max = 10.0` means "moving at ten of its own lengths per
second," and the bonus is the same at 500 m as at 5 km. For a 7 m vehicle that is 70 m/s to
saturate — ground vehicles essentially never do. A truck at 5 m/s gives ratio 0.71; if the ramp to
1.5 is linear (unknown — only the endpoints are in the file), that is roughly **+3.5% detection
distance**. Fast aircraft saturate easily.

**This is not our 8 arcmin/sec threshold and must not be swapped for it.** The two answer different
questions:

| | ED's `motion_factor` | Our movement gate (`body-layer/ROADMAP.md`, 2026-09-20) |
|---|---|---|
| Question | Does movement make the target *easier to spot*? | Can the crew *tell that it is moving*? |
| Output | Continuous gain on detection range (≤1.5×) | Binary `moving` / `stopped`, a reporting trigger |
| Quantity | `v⊥ / size`, range-invariant | `v⊥ / range`, absolute angular rate |
| Constant | 10.0 saturation, 1.5 max gain | 8 arcmin/sec ≈ 2.33 mrad/s |

They compose rather than compete, exactly like the optics/conditions split already argued in the
roadmap. Our design is **not** made redundant by ED's — ED has no "is it moving" state at all.

Worked cross-check, same truck (7 m, 5 m/s crossing) at 5 km: ours computes 3.4 arcmin/sec →
reads as stationary (the sanity check the threshold was adopted against); ED gives it ratio 0.71 →
a few percent of extra detection range. Both are defensible, and neither is the other.

#### 4. `Skill_Factors.lua` quantifies Petrovich-class omniscience: **27×**

— **evidence:** reproduced-locally — **source:** `$DCS_INSTALL_PATH/Scripts/AI/Skill_Factors.lua`
(`VISUAL_AND_OPTIC_DETECITON_DIST_FACTOR = 12`, `..._TIME_FACTOR = 13`; per-skill tables at
lines 81-401)

| Skill | Detection **distance** factor | Detection **time** factor |
|---|---|---|
| Cadet | 0.45 | 4.0 |
| Average | 0.55 | 2.0 |
| Good | 0.70 | 1.5 |
| High | 0.85 | 1.2 |
| Excellent | 1.00 | 1.0 |
| **Human** (file comment: *"for example, gunners on UH-1"*) | **27.0** | **1.0** |
| Net client | 27.0 | 1.0 |

`HUMAN_SKILL` is the tier ED uses for **AI crew serving a human player** — Petrovich's own class.
5500 m (ground vehicle, airborne detector) × 27 = 148.5 km, clipped by
`max_detection_distance = 50000`. So a human's AI gunner is, by design, limited by line of sight and
essentially nothing else.

This is the clearest single number the project has ever had for *why* it exists. The no-omniscience
invariant is not arguing against an accident or a bug; it is replacing a deliberate 27× gameplay
concession. Worth quoting in `docs/concept/PETROBRAIN_SYSTEM.md` if that document ever wants one
concrete fact instead of an argument.

**Caveat, stated because it is easy to over-claim:** that `HUMAN_SKILL` is what the Mi-24P's
HelperAI runs at is **inferred from the file's own comment**, not proven for this module. What is
proven is the tier, its value, and its stated purpose.

#### 5. The three "unconsumed" constants: the consumer is the engine, and the mechanism is now visible

— **evidence:** reproduced-locally (symbol tables) + inferred (the linkage) — **source:**
`strings` over `Mods/aircraft/Mi-24P/bin/CockpitMi24.dll` and `bin/WorldGeneral.dll`

A whole-install Lua grep (12.8 s, every `.lua` under `$DCS_INSTALL_PATH`) for
`min_contrast_f|min_fog_transparency|extra_eyesight_ratio` returns **exactly three hits, all three
of them the definitions** in `HelperAI.lua:42,58,60`. That is now a clean, final, install-wide
negative for the Lua layer — the previous sessions' result generalised.

The import table of `CockpitMi24.dll` then shows where they go. The Mi-24P cockpit **constructs and
drives the engine's own detector**:

```
??0wDetector@@QEAA@XZ                         wDetector::wDetector()
?init@wDetector@@QEAAXPEAVMovingObject@@PEBUwDetectorInfo@@@Z
?get_detector_info@wDetectorInfoStorage@@QEBAPEAUwDetectorInfo@@PEAVMovingObject@@@Z
?getContrastFactor@wDetector@@QEAAMPEAVMovingObject@@AEAVwTargetDetectionStatus@@@Z
?isTargetDetected@wControl@@UEBA_NIAEAVwTargetDetectionStatus@@@Z
?getDetectedTargets@wControl@@UEBAX...
```

and `WorldGeneral.dll` exports the other end, including the Lua loader itself:

```
?load_from_state@wDetectorInfo@@UEAAXAEAVConfig@Lua@@@Z      <- Detection.lua -> native struct
?getMaxVisibilityDistWithFog@wDetector@@QEAAMPEAVMovingObject@@AEAVwTargetDetectionStatus@@
                                            W4SpectrumBand@wVisualDetectorImpl@@MM@Z
?update@wTargetDetectionStatus@@QEAAXNEEEEAEBVVec3f@osg@@0@Z  <- double + FOUR byte fields + 2 vectors
```

**The reading this supports** (inferred, high confidence, not proven): the two constant sets are
**layered, not alternative**. `Detection.lua` configures the engine detector that decides whether a
target is reported at all; `HelperAI.lua`'s constants are the Mi-24P's own filter applied on top of
what that detector returns — `min_contrast_f` as a floor against `getContrastFactor()`,
`min_fog_transparency` against the fog term in `getMaxVisibilityDistWithFog()`, and
`min_angular_radius`'s `lowres/medres/hires/iff` ladder deciding what Petrovich may *say* about a
target the engine has already handed him. `extra_eyesight_ratio = 4.0` is consistent with a
detection-distance multiplier for his optics — which is what this project independently repurposed
it as, and then independently re-derived from a 6×30 Б-6 with a vibration penalty.

That closes a three-session hunt with an answer of the right shape. It also means our model and
ED's are more alike than the gap analysis assumed: **ED also has a two-stage structure** (engine
detection, then a module-specific reporting filter), which is exactly our
`hybrid_source` → `classification` split.

#### 6. ED separates detected from recognised, by a **distance ratio** — and gives optics a bigger ratio

> **STATUS 2026-09-21 — this disagreement was raised in slice 2 and resolved in ED's favour.**
> The passages below and in finding 7 that describe `perception/optics.py` as modelling "an optic
> as magnification plus a field-of-view cone, with the same three angular tiers behind it", and
> finding 7's `M=4.0` binocular row, describe code that **no longer exists**. Cones slice 2A
> replaced the single per-optic magnification with **per-tier multipliers**
> (`BINOCULAR_OPTIC` 2.42/3.50/3.00) and retired `BINOCULAR_RANGE_MULTIPLIER` outright. ED's
> `recognition_distance_ratio_threshold` split (0.25 naked / 0.5 optic) was one of the two
> independent reasons; the other was a live sortie measuring the same direction
> (`body-layer/research/2026-09-21-slice2-model-decisions.md` decision 1,
> `2026-09-21-aspect-magnification-and-distinctiveness.md` Finding 2).
>
> The recommendation "do not copy ED's optic recognition ratio without a decision" was followed:
> the decision was taken deliberately, with our own measurement, not by copying ED's constant.

— **evidence:** reproduced-locally — **source:** `Detection.lua:27`, `:110`

`recognition_distance_ratio_threshold` = **0.25** for the naked eye, **0.5** for optic sensors:
*"target will be recognized if ratio between the distance and the maximal detection distance is
less than this value."*

Two things fall out that bear directly on the cones milestone:

- ED's ladder is **two states** (detected → recognised), not four. The four booleans the scripting
  API exposes (`Controller.getDetectedTargets`'s `visible`/`type`/`distance`) are a different
  surface; `wTargetDetectionStatus::update`'s four byte-sized parameters are consistent with a
  small flag set, but their meaning is not readable statically. Our UNKNOWN→PRESENCE→CLASS→TYPE
  lattice is finer than ED's shipped tuning data, which stays our own modelling choice.
- **An optic is not only a magnifier in ED's model.** Doubling the recognition ratio says looking
  through glass buys proportionally *more* recognition than detection. `perception/optics.py`
  currently models an optic as magnification plus a field-of-view cone, with the same three angular
  tiers behind it — the 2026-09-17 calibration's central finding, that the tiers belong to the eye
  and the optic only multiplies the angle. ED disagrees with that. **Not a defect** — our version is
  screenshot-calibrated on this exact aircraft and ED's is a game-tuning constant — but it is a
  real, specific disagreement and belongs in the cones slice-2 discussion rather than being
  discovered mid-implementation.

#### 7. Sanity-check of our calibrated constants against ED's

— **evidence:** inferred (arithmetic over findings 1 and 4 and `perception/visibility.py`)

Our threshold is `size_m / range`, so ED's `fixed_size_target_detection` converts directly:
6.0 m / 5500 m = **1.09e-3**. For a 7 m vehicle:

| Channel | Threshold (size/range) | Range, 7 m vehicle |
|---|---|---|
| Ours, naked eye presence (`LOWRES`, M=1.0) | 3.0e-3 | 2,333 m |
| **ED, excellent-skill AI, ideal conditions** | 1.09e-3 generic / 1.27e-3 ground-vehicle class | **5,500 m** |
| Ours, binoculars (M=4.0) | 0.75e-3 | 9,333 m |
| ED, average-skill AI | ×0.55 | 3,025 m |
| ED, **human-crewed AI gunner** | ×27, clipped | **50,000 m** |

Our naked eye is ~2.4× more conservative than ED's best AI; our binoculars ~1.7× more generous.
Both sit in a defensible band around ED rather than wildly off it, which is a reassuring
independent check on a calibration that came from screenshots and a ruler.

**One concrete improvement candidate.** `NAKED_EYE_RANGE_CAP_M = 10000.0` is numerically identical
to ED's `max_visibility_at_ground_level = 10000.0` — but ED's is the *ground-to-ground* value of a
curve that climbs with altitude, and ours is a flat cap. Solving ED's own formula from its two
stated points (b = ln 10, k = ln(4.2)/4 ≈ 0.3588):

```
visibility_km = 10 · e^(0.3588 · (detector_km + target_km))     ≈ ×1.43 per combined km
```

600 m AGL → 12.4 km · 1 km → 14.3 km · 2 km → 20.5 km. A helicopter is almost never at the
altitude our cap was implicitly set for. Cheap to adopt, one function, no new data.

#### 8. Vegetation: ED **does** test trees for LOS on every terrain this project uses

— **evidence:** reproduced-locally for the constants; inferred (strong) for what `T4` denotes —
**source:** `Detection.lua:21-22`; `Mods/terrains/*/entry.lua:1`

`trees_LOS_test = false` but `trees_LOS_test_T4 = true`. `T4` is the only such token in the
install's Lua outside livery texture names, and every one of the five installed terrains opens with
`if not USE_TERRAIN4 then return end` — so `T4` is the Terrain-4 engine generation, and **all five
installed theatres, Syria included, are T4**. On Syria, ED's AI detection samples tree geometry for
line of sight.

Our `query.line_of_sight.line_of_sight_clear` samples the bare terrain mesh only. **We are strictly
more permissive through forest than ED is** — which makes factor 1 of the "detection under real
world conditions" backlog item (*"cheapest by a wide margin, because the data is already here"*)
not merely cheap but a gap against the engine's own behaviour.

A second, separable term: `background_factors[FOREST] = 0.3` cuts detection distance to 30% against
a forest background — but the file states in capitals that background applies to **airborne targets
ONLY**. So ED models "hard to see an aircraft against trees" and does *not* model "hard to see a
tank against trees" as a contrast effect; for ground units the forest effect is the LOS test alone.
Our own backlog note anticipated exactly this asymmetry (*"a contact in forest is hard to see, and a
contact against forest is a different problem again"*) — ED resolves it by only modelling one side.

#### 9. Light and fog: what is readable, and from where

— **evidence:** reproduced-locally — **source:** `Scripts/Export.lua` (shipped API list),
`MissionEditor/modules/me_mission.lua:515-552`

- `Export.lua`'s complete getter list contains **no weather getter beyond
  `LoGetVectorWindVelocity` and `LoGetBasicAtmospherePressure`**. Fog is confirmed absent from the
  Export channel; the mission-sandbox bridge remains the only candidate route, still unprobed.
- **Time of day *is* available from Export.lua alone**, which the light-level backlog item did not
  know: `LoGetMissionStartTime()` + `LoGetModelTime()`, both documented in the shipped file
  (lines 433-434). With the mission date (already parsed by the Mission Interpreter from the `.miz`)
  and ownship lat/long (already in telemetry), sun elevation is ordinary astronomy computed locally
  — **no Hook, no `net.dostring_in`, no new channel.** Factor 2 of the conditions backlog item is
  therefore much cheaper than factor 3, and independent of it.
- ED's fog model, from the mission-editor migration code: legacy `fog.density` 0-10 maps to
  visibility `{10000, 5120, 2560, 1280, 640, 320, 160, 80, 40, 20, 10}` m, and the current
  representation is `fog2.manual = {{time, visibility, thickness}, …}` — a **time series**, so fog
  changes during a mission. Anything built here must sample, not read once.

#### 10. `LoGetWorldObjects` carries **no velocity** — the movement design must difference in the collector

> **CORRECTION 2026-09-21 — the first clause stands, the heading's conclusion does not.**
> `Object.getVelocity()` returns a vec3 in m/s for every unit, in the **Mission Scripting**
> environment (Hoggit `DCS_func_getVelocity`; it is how Tacview records speed). So "we must
> difference in the collector" was never the only option — the mission-sandbox bridge is a second
> route, and a more accurate one. Full finding:
> [`2026-09-21-unit-velocity-via-mission-scripting.md`](2026-09-21-unit-velocity-via-mission-scripting.md).
>
> Note this finding **already named `Unit.getVelocity()`** in its own last paragraph, correctly, as
> costing "the whole Hook bridge." The error is in the heading and the framing, not the evidence:
> the question asked was "is velocity available *from `LoGetWorldObjects`*", the answer was correct
> and rigorous (a full `pairs()` enumeration, so no synonym could hide), and that correct narrow
> answer was then recorded and relayed as the answer to the broader question "can we get unit
> velocity". A negative result from searching one surface only ever bounds that surface.

— **evidence:** reproduced-locally — **source:** `Scripts/Export.lua:129-136`;
`$DCS_SAVED_GAMES_PATH/Logs/aircraft_layer_debug.log` (10.4 MB, 2026-09-19 sortie), one-shot dump

The movement-detection design records as build-blocking: *"whether unit velocity is directly
available from `LoGetWorldObjects` or must be differenced in the collector."* **It must be
differenced.** The complete field set in a real dump is:

```
Pitch, Bank, Heading, Type{level1..4}, Country, CoalitionID, Coalition, GroupName,
Name, UnitName, Position{x,y,z}, PositionAsMatrix{x,y,z,p}, LatLongAlt{Lat,Long,Alt},
Flags{Born, Static, Human, Invisible, AI_ON, RadarActive, Jamming, IRJamming}
```

The string `Velocity` appears **zero times** in the entire debug log. Note the contrast within the
same API: `LoGetLockedTargetInformation()` *does* return a velocity vector (`Export.lua:136`), but
only for a locked target — not for the global object table.

Consequences for the design, which otherwise stands unchanged: the collector already holds
successive `Position` samples per `object_id`, so differencing is local and cheap; but it needs
per-object previous-position state and is sensitive to the poll interval, and `object_id`
continuity across polls becomes load-bearing for movement in a way it is not for position. The
mission-sandbox alternative (`Unit.getVelocity()`) exists but costs the whole Hook bridge.

#### 11. SPU-8: every argument slice 2 asked for, plus a correction to an existing reference

— **evidence:** reproduced-locally — **source:**
`Mods/aircraft/Mi-24P/Cockpit/Scripts/clickabledata.lua:999-1050`

| Arg | Control | Seat |
|---|---|---|
| 452 | Network 1/2 switch | pilot |
| 453 | SPU-8 radio volume knob (axis, 0-1, step 0.05) | pilot |
| 454 | Circular call button | pilot |
| 455 | Radio source selector, 6 pos at 1/5: R-863 / NF / R-828 / JADRO-1A / ARC-15 / ARC-U2 | pilot |
| **456** | **Radio/ICS switch** | pilot |
| **457** | **SPU-8 main volume knob** (axis, 0-1, step 0.05) | pilot |
| 376 / 377 | SPU-8 NET-2 / NET-1 ON-OFF | pilot |
| **738** | **stick trigger: 1.0 = RADIO (LMB), 0.5 = ICS (RMB), 0.0 released** | pilot |
| 656-661 | operator mirror of 452-457 | operator |
| **664** | **SPU-8 intercom power ON/OFF** | operator |
| 856 | operator stick trigger (same 1.0/0.5 encoding) | operator |

Slice 2 named "the switch and the knob": **456 and 457** for the pilot's own set, with **664** the
only actual intercom *power* switch and it lives on the operator's panel (`crew_member_access = 1`).
That asymmetry is worth knowing before designing "intercom off means he cannot hear you" — the
player flying as pilot cannot reach 664.

**Two corrections to existing project artifacts fall out of this:**

- `2026-09-19-ptt-gate-feasibility.md` lists as unresolved: *"Full-press (radio-transmit) numeric
  value of arg 738 — inferred to be higher than 0.5 but the exact value is not stated."* It is
  **1.0**, stated directly by `arg_value = {1.0, 0.5}` with `arg_lim = {{0.0, 1.0}, {0.0, 0.5}}`.
  Third-party (DCS-SRS) inference is no longer needed.
- The same doc flags: *"Arg 738 itself does not appear anywhere in this project's own clickabledata
  dump."* **Confirmed, and the cause is a generator blind spot, not a stale arg.**
  `mi24p-command-surface.md` captures the `default_2_position_tumb(…)` / `default_axis(…)` helper
  forms, but **13 of 749 elements in `clickabledata.lua` are raw table literals** and are missing
  entirely: `COLLECTIVE-CORR-PTR`, `OP-COLL-THROTTLE-PTR`, `CLOCK-{LEFT,RIGHT}-PTR`,
  `CLOCK-{LEFT,RIGHT}-OP-PTR`, `ILS-ADJUST-HANDLE-PTR`, `BRAKE-LEVEL-OP-PTR`,
  `RADAR-ALTIMETER-KNOB-PTR`, `STICK-PTT-PTR`, `OP-STICK-PTT-PTR`, `TIMIR-LEFT-OP-PTR_2-9_5`,
  `TIMIR-LEFT-OP-PTR_8-38`. The multi-action controls — both PTTs, both collectives — are exactly
  the ones in that set, so the gap is not random with respect to what this project wants.

#### 12. Methodological: `strings` cannot see DCS's Lua-facing names. Absence is not evidence.

— **evidence:** reproduced-locally — **source:** control test over `bin/{Scripting,WorldGeneral,
Weather}.dll`, `bin/DCS.exe`

Searching binaries for a Lua API name returns nothing **even for functions that indisputably
exist**: `outText`, `getHeight`, `getPlayer`, `getAbsTime` and `getDetectedTargets` all score 0 in
every binary tested, as do Mi-24P globals that certainly drive behaviour (`min_angular_radius`,
`slowpoke_ratio`, `atgm_range_114`). Only `device_timer_dt` surfaced, in `CockpitBase.dll`.

So the earlier plan of confirming `world.weather.getFogThickness()` by grepping the install's
binaries would have produced a **false negative**. What *is* readable is the C++ export/import
symbol tables, which are not packed and which produced findings 5 and 6 above. Search for class and
method names (`wDetector`, `getContrastFactor`), never for Lua-facing names.

---

### Reproducible Test

Everything here re-runs from a shell on the DCS box with `$DCS_INSTALL_PATH` set. No DCS session
needed, nothing written to the install.

```sh
cat "$DCS_INSTALL_PATH/Scripts/AI/Detection.lua"
sed -n '81,401p' "$DCS_INSTALL_PATH/Scripts/AI/Skill_Factors.lua" | grep -A2 'DETECTION'
grep -rn --include='*.lua' -E "min_contrast_f|min_fog_transparency|extra_eyesight_ratio" "$DCS_INSTALL_PATH"
strings -n 8 "$DCS_INSTALL_PATH/bin/WorldGeneral.dll" | grep -E 'wDetector|wTargetDetectionStatus' | sort -u
strings -n 8 "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/bin/CockpitMi24.dll" | grep -E 'Detect|Contrast'
head -1 "$DCS_INSTALL_PATH"/Mods/terrains/*/entry.lua
sed -n '999,1050p' "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/clickabledata.lua"
grep -oE '^LoGet[A-Za-z0-9_]+' "$DCS_INSTALL_PATH/Scripts/Export.lua" | sort -u
grep -c Velocity "$DCS_SAVED_GAMES_PATH/Logs/aircraft_layer_debug.log"      # -> 0
# control test for finding 12 (all should print 0):
for s in outText getHeight getAbsTime getFogThickness; do \
  echo "$s $(strings -n 5 "$DCS_INSTALL_PATH/bin/DCS.exe" | grep -cx "$s")"; done
```

**Still needs a live session** (DCS was not running): probe #2 from the 2026-09-19 doc —
`net.dostring_in("mission", "return world.weather.getFogThickness()")` from a Hook script. Finding
12 means this genuinely cannot be settled statically; the probe is now the *only* route.

---

### Possible Approaches

- **Correct the roadmap before anything is designed on top of it.** The "neither ED nor we model
  movement or dwell" bullet is load-bearing for how the cones milestone was framed, and it is
  wrong. Done in this branch (`body-layer/ROADMAP.md`), but flagged here because the correction
  matters more than the finding.
- **Cones slice 2 now has a precedent to argue with, not from.** ED's shape is: detection takes
  *time*; that time depends on aspect (6× penalty for behind, ground units) and on how much sky you
  are sweeping per unit of field of view. Using `scan_time_for_double_scan_to_view_angular_square_
  ratio = 0.1` as anchored — 0.1 s when the scanned area is twice the FOV — a 9K113 narrow field
  (~6°) sweeping its ±60° × 35° field of regard is an area ratio of ~150, implying roughly 7 s to
  find something in the sector. That is the right order for a real sight sweep. Treat the arithmetic
  as illustrative (the file gives one anchor point, not the curve) but the *form* as evidence that a
  dwell model keyed to FOV-over-scan-area is workable.
- **Adopt the altitude-dependent visibility ceiling (finding 7) as a small, standalone change.** It
  replaces a flat constant whose value we share with ED's ground-level case, with ED's own curve.
  Cheap, self-contained, and it stops the cap being pessimistic at every altitude a helicopter
  actually flies.
- **Wire landcover into `visibility.py` as an LOS term, not only a contrast term** (finding 8).
  ED's split — trees block LOS for everyone, forest background dims only airborne targets — is a
  cleaner decomposition than the one the backlog sketched, and it needs no new data.
- **Do not copy ED's optic recognition ratio without a decision** (finding 6). It contradicts a
  calibration this project paid a screenshot campaign for. Raise it in slice 2, decide deliberately.
- **Regenerate `mi24p-command-surface.md` with a generator that handles raw table literals**
  (finding 11), or at minimum append the 13 missing elements by hand. A reference whose gaps
  correlate with multi-action controls is worse than one with random gaps, because the things it
  misses are the things worth actuating.

### Unresolved

- **Whether `Detection.lua` is actually loaded at runtime.** Strongly supported —
  `wDetectorInfo::load_from_state(Lua::Config&)` exists, the file carries a dated 2024 tuning
  comment and an ED Jira reference — but not proven, and finding 12 means it cannot be proven by
  string search. A live probe would need to observe detection behaviour change, not read a file.
- **Whether Petrovich's HelperAI runs at `HUMAN_SKILL`.** The 27× tier exists and its comment names
  player-crewed AI gunners; the linkage to this specific module is inferred.
- **The shape of ED's motion ramp** between ratio 0 and the 10.0 saturation, and of the
  detection-time curve between max distance and close range. Only endpoints are in the file.
- **`world.weather` reachability via `net.dostring_in("mission", …)`** — unchanged from 2026-09-19,
  and now known to be unresolvable without a running DCS.
- **Per-unit characteristic size for stock units is not Lua-readable.** A grep for `BMP-2` across
  all of `CoreMods` returns nothing — stock unit definitions live in the encrypted
  `Scripts/Database.edce`. `Detection.lua`'s `detection_distance_by_class` is per *class*, not per
  type. The live route (`Unit.getDesc().box` in the mission sandbox) is untested and would need the
  same bridge as weather.
- **What `wTargetDetectionStatus`'s four byte parameters are.** Their count is suggestive of the
  detected/visible/type/distance flag set, but that is pattern-matching against the scripting API's
  documented shape, not evidence.
