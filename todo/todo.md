# Todo

## User priority tasks
Prioritize any open task here over any other task in this file or roadmap files.

- [x] Create integrity audit skill, see instructions @todo/integrity-audit-skill.md — `.claude/skills/integrity-audit/SKILL.md` created 2026-09-08. 6-phase diagnostic audit (inventory → cross-file consistency → staleness → genericity leaks → duplication/dead mechanisms → memory hygiene → classify+report); never self-edits config, writes dated report to `audits/system-integrity/`.
- [x] claude workflow changes — `AGENTS.md` updated 2026-09-08: new "Auto-Advance" section (proceed through Architect → Implementer → Reviewer → (loop) → DoD without stopping between stages) and Escalation Rules extended with the local/reversible/non-material autonomy criterion. Existing `UserPromptSubmit` hook already injects "apply automatically, no user input needed" each turn — left as-is per user decision to observe first; hook mirror-update deferred unless AGENTS.md alone proves insufficient.
    - [x] move automatically to next stage in worklfows: architecht -> implementor -> reviewer -> (loop back to implementer if fixes are needed) -> DoD. If there is genuine ambiguity or need for user input/verification/perception, stop and hand to user. In normal cases, proceed to next step in workflow.
    - [x] If multiple reasonable technical approaches exist, choose one when the tradeoff is local, reversible, and does not materially affect product behavior, future architecture, dependencies, cost or risk. Escalate consequential or difficult-to-reverse decisions or where there is ambiguosity about expected behaviour.


## Current Focus

World Model Builder good-enough, gate lifted 2026-09-06 (user decision: move to rest of chain to test/improve end-to-end). Aircraft layer (DCS I/O + API, per `docs/concept/division-or-responsibility.md`) — **done, merged to main 2026-09-07** (`51654ec`). PB-1 (text-only perception logger / BL-0 + BL-1 scaffolding) — **done, ready to merge 2026-09-08**. World Model's own backlog (M9 OSM, incremental per-layer builds) stays deferred/unscheduled — see `world-model/ROADMAP.md`.

**PB-1.5 (done, merged to main 2026-09-09).** `feature/pb1.5-naked-eye-detection`. A second,
independent perception channel: `NakedEyePerceptionSource` reports plausibly-visible ground objects
from `LoGetWorldObjects`, gated by FOV + angular-size + terrain-LOS, and quantised to ED's own
callout vocabulary (12 clock bearings, 24 range buckets, coarse class). New modules
`object_model.py`, `visibility.py`, `naked_eye_source.py`, `reporting_names.py` plus ED's committed
595-row DCS-type→reporting-name mapping. 102 body-layer tests.

*The milestone's central question was answered, and the answer was negative.* A purpose-built live
probe (`aircraft-layer/dcs-export/Export.probe-pb15.lua`, flown as an OBSERV OFF / OBSERV ON A/B)
established that **DCS's ambient contact callout has no Lua-readable companion** — `list_indication(6)`
produced zero change events across the whole sight-off segment while `GROUND, 11 O'CLOCK` and
`GROUND, 12 O'CLOCK` appeared on screen, and the HelperAI tree is not even instantiated until the
sight comes on. So the synthetic filter is not a fallback awaiting a better signal; it is the only
implementation. Full findings: `aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`.
Also recovered from the module's own Lua: ED's detection constants (`HelperAI.lua`) and the composed
callout vocabulary (`HelperAI_lengths_ng.lua`), both in
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`.

*Key decisions:* the channel deliberately models a **binocular-aided** observer (`medres` 0.008 rad
x 4.0), not the unaided eye — the user's choice, so "naked-eye" is now a misnomer the code docstrings
warn about. `NAKED_EYE_RANGE_CAP_M` was raised 2500 → 5000 m so the per-type size curve, not the cap,
does the discriminating (infantry 900 m, truck 3000, T-72 3500, SA-3 4500; only ships cap).

*One live bug, found and fixed:* the first sortie reported the ownship itself as a contact —
`LoGetWorldObjects` is unfiltered and includes the player's aircraft, which neither channel excluded.
Fixed in both channels (`association.exclude_ownship`); the scope channel had the same latent bug.

*Open follow-ups, none blocking:* tier calibration against the user's "if the player can see a unit,
Petrovich should too" standard (infantry at 900 m is the tightest); identity-based rather than
proximity-based ownship exclusion; ground-unit classification coverage at 60.1% by deliberate choice.
All in Backlog.

*Does this change the next milestone?* **No architectural change for PB-2/BL-2.** Both channels
already flow through the uniform `PerceptionSource` interface, so "the synthetic channel is primary"
is a framing and priority shift, not a contract change. What it does raise is the priority of the
scope channel's known defects — the user confirmed that channel stays, being needed for future
acquire/lock/fire gameplay.

PB-2 (BL-2: contact memory and data association over time) follows after this — PB-1's completion does not invalidate or change downstream assumptions for BL-2, but BL-2 should ideally consume both detection channels (scope + naked-eye) rather than being built against the scope-only channel and reworked later.

**Aircraft layer (done, 2026-09-07):** `feature/aircraft-layer-telemetry` merged to main. Export.lua → Windows collector → LAN `/telemetry/latest` API, live-tested against cockpit instruments (bank/IAS/heading/alt all match), 5 Hz export-rate bug found+fixed, `altitude_radar_m` stays null (deprioritized — use `altitude_agl_m` instead, confirmed equivalent), `/telemetry/since` dropped as unneeded scope. `aircraft-layer/CLAUDE.md` + `WORKFLOW.md` document the subproject. Full history: `plans/aircraft-layer/implementation.md`.

**PB-1 (done, 2026-09-08):** `feature/pb1-perception-logger` ready to merge. Stages 1–3 (live spike, BL-0 harness, world_objects endpoint) completed earlier; stages 4–9 (hybrid HelperAI perception source + association + text logger) completed with zero Reviewer required fixes across two review passes. Live acceptance test (stage 7) ran end-to-end on real Mi-24P sortie with manually-placed ground targets; two observations logged with plausible bearing/range values in an ambiguous-candidate scenario (4 Ural trucks clustered together). The original architecture (two-tier branching on geometry source) was completely falsified by Session 4's live spike; pivoted to single hybrid implementation (HelperAI text as real detection gate, `LoGetWorldObjects` geometry via association algorithm). Full history: `plans/pb1-perception-logger/plan.md`, `implementation.md`, `review.md`, `dod-check.md`. Key lessons harvested to `NOTES.md`: live spikes resolve DCS architectural unknowns better than desk research; PYTHONPATH/venv gaps only surface in end-to-end deployment; ambiguous-scene live testing essential for association validation.

- [x] M0 — record installed DCS version + confirm Syria terrain present, in `world-model/research/`.
- [x] M1 (recon) — prove DCS x/z ↔ lat/lon transform for Syria against a known real-world control point; measure error. pydcs tmerc params confirmed against live install; real-world residual ~1.0-1.3km (terrain-placement error, not projection defect). See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M1 (implement) — `src/coordinates/` built per plan, control-point tests pass. Windows/WSL probes run: pydcs Syria tmerc params confirmed against live `coord.LOtoLL` (sub-meter match, 226 points); real-world residual ~1.0-1.3km vs published ARPs, explained as DCS terrain-placement error. See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M2 — Raster understanding. `src/raster/` (Pillow DDS loader + empirical registration), `tools/inspect_raster.py` diagnostic, control-point + held-out-point tests pass. See `world-model/ROADMAP.md` M2 entry and `plans/m2-raster-understanding/`.
- [x] M3 — OSM overlay. `src/osm/` (Overpass API fetch + in-memory parse), `tools/inspect_osm_overlay.py` diagnostic overlay, tests pass, held-out Gemerek validation. Attribution rendered onto output PNG. Spatial-storage choice deferred to M5. See `world-model/research/2026-09-03-m3-osm-overlay.md` and `plans/m3-osm-overlay/`.
- [x] M4 — DCS elevation. `src/elevation/` (`land.getHeight` live-mission probe via io/lfs, SRTM3 `.hgt` parsing), `tools/inspect_elevation.py` diagnostic, control-point + real-fixture tests pass. 100-point Gemerek grid vs SRTM3: mean delta +13.89m, west-edge outlier traced to real terrain-mesh-resolution mismatch, not a bug. `MissionScripting.lua` io/lfs edit intentionally left in place (more probes expected M5+). See `world-model/research/2026-09-03-m4-dcs-elevation.md` and `plans/m4-dcs-elevation/`.
- [x] M5 — First persistent model. `src/store/` (stdlib `sqlite3` + R*Tree, JSON geometry), `src/roadnet/` (DCS-native `.routes` binary parser), `src/dcs_data/` (towns/beacons Lua parsers), `src/query/describe_position`. Region: Latakia (`latakia-20km`). Real store: 3,266 roads, 338 settlements, 117 water, 108 named places, 1,681-point elevation/surface_type probe grid at 100% coverage, 8.57 MB `.sqlite`. Two real defects found+fixed: `pyproj.Transformer` per-call rebuild (perf), roadnet resync denormalized-float validation gap (correctness). `.rn4` graph decoding, airfield taxiways/structures, Latakia SRTM tile, full-theatre resync audit deferred to M6+. See `world-model/research/2026-09-04-m5-first-persistent-model.md` and `plans/m5-first-persistent-model/`.
- [x] M6 — Terrain semantics. Ridge/valley classification over `latakia-20km`'s elevation grid. `ridge=12, valley=12` at tuned thresholds, `confidence: "low"` on every feature — a real grid-resolution-vs-feature-scale limitation, not a bug. See `world-model/research/2026-09-05-m6-terrain-semantics.md`.
- [x] M7 — Full theatre pipeline. Scaled to the whole Syria theatre: SRTM-primary elevation, OSM dropped (deferred to a future milestone via geofabrik.de extracts), M6 terrain classifier out of scope. Real `syria-full.sqlite`: `road=14833` (exact match to independent census), 35 airfields, 1,182 named places, 461 MB, full rebuild 449.3s, `describe_position` p99 803ms (tail flagged as a follow-up, not blocking). All 8 theatre-spread control points within tolerance; SRTM-vs-DCS-probe spot-check mean delta -7.19m/stddev 11.52m, tighter than M4's baseline. `surface_type` stays `"unavailable"` theatre-wide — accepted, documented gap. See `world-model/research/2026-09-06-m7-stages-1-2-3-full-build-results.md` and `plans/m7-full-theatre-pipeline/`.
- [x] M8 — Incremental probe store. `src/probe_store/` (schema, writer, reader, paths), separate `-probe.sqlite` per theatre, ATTACH-based probe-then-base fallback in `describe_position`, tri-state coverage keyed `(kind, chunk_ix, chunk_iz)`, locked chunk/probe spacing, drift detection on both write and read paths. All 244 tests pass (241 base + 3 new from required fix). Two-store separation prevents "newest grid wins" silent failure; read-path drift protection closes reviewer-found cross-theatre/stale-lattice gap. Fixture-only testing; no live-mission channel (deferred to Runtime). See `plans/m8-incremental-store/plan.md`, `plans/m8-incremental-store/implementation.md`, `plans/m8-incremental-store/review.md`, and `world-model/docs/M8_PROBE_STORE.md`.

## Milestones

Full sequence lives in `world-model/ROADMAP.md` (M0 through M9, World Model side). Aircraft layer / Mission Interpreter / Runtime work now in scope — see root `CLAUDE.md` "Current priority" (gate lifted 2026-09-06).

- [x] **PB-1.5 — Naked-eye visual detection channel.** Done, merged to main 2026-09-09. Live acceptance passed. See Current Focus.

(World Model M9 moved to Deferred below, 2026-09-06)

## Backlog

- [ ] **Exclude the ownship by identity rather than by proximity.** The 2026-09-09 fix
  (`association.exclude_ownship`, commit `549aee6`) drops any world object within
  `OWNSHIP_ECHO_EXCLUSION_RADIUS_M = 50.0` m of ownship. That is correct for the bug it fixes and
  has no false positives in practice, but it is a heuristic standing in for an exact answer, and it
  carries a narrow false-*negative* window: any genuine object within 50 m of the aircraft is
  silently dropped. Plausible cases — troops disembarking beside a landed helicopter, another
  aircraft in close formation, a vehicle the aircraft is hovering directly over.

  The exact fix is identity-based and lives one layer down: `Export.lua` knows the player's own
  object via the DCS export API (`LoGetPlayerPlaneId()`), so it could omit that entry from the
  `world_objects` payload, or flag it so body-layer can drop it by id rather than by distance. That
  removes the false-negative window entirely and is robust regardless of what
  `LoGetWorldObjects`'s `pairs()` key turns out to mean.

  Not done in the bug fix because it is an aircraft-layer change affecting every consumer of
  `/world_objects/latest`, where the body-layer-side fix was contained and shippable. Worth doing
  when aircraft-layer is next touched.

- [x] **Settle whether `LoGetWorldObjects`'s `object_id` is stable across polls** — **closed 2026-09-09 by live evidence.** PB-1.5's acceptance sortie emitted 2 observations in 70 s; unstable ids would have re-emitted every object every tick. The prediction recorded below ("the next live sortie settles it for free") held. Original entry: — needs a live
  capture, described in `plans/pb1.5-naked-eye-detection/debug.md` "Needs live DCS".
  `world_objects.py`'s own docstring calls it "the numeric key from Lua `pairs()` iteration" and a
  "within-one-poll identifier only until verified live", and Lua does not guarantee `pairs()`
  order. Both perception channels' debounce keys on it.

  The 2026-09-09 debugging established the debounce mechanism is *not* broken given a stable id —
  the live log's irregular repetition was the FOV gate flapping on a meaningless near-zero-baseline
  bearing, fully explained by the ownship bug. So this is unconfirmed rather than known-broken, and
  was deliberately not "fixed" speculatively. **The next live sortie settles it for free**: with the
  ownship echo gone, if real contacts re-emit on every poll instead of once, the ids are unstable.
  Watch for that during acceptance testing.

- [?] **Direction (raised 2026-09-09, needs Architect): stop consuming DCS's detection at all, and
  own perception end-to-end.** After the PB-1.5 live probe
  (`aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`), the user's position is
  that this "heavily leans towards entirely dropping the current naked-eye DCS detection logic,
  possibly even suppressing the texts in the radio callouts, and implementing our own detection
  mechanism based on all world objects."

  **Why the probe pushes this way.** DCS's ambient channel is unusable as an input: it emits no
  Lua-readable signal (probe Finding 1), it is text-only with no audio (Session 5 part 3), its
  reports lag well behind what the player can plainly see (Finding 5), and the one channel that
  *is* readable — the HelperAI target list — only exists while the sight is on and is gated on it.
  So every path that treats DCS as the detection authority is either unreadable, late, or
  sight-coupled. PB-1.5 already builds the alternative.

  **What it would change.** PB-1.5's `visibility.py` stops being a fallback that stands in for a
  missing signal, and becomes the primary, intended detection mechanism. That retroactively
  reframes the plan's Decision 1, which the user accepted "for now" expecting to revisit it —
  the revisit would resolve *toward* the synthetic filter rather than away from it. It also makes
  the range/tier constants product-critical rather than provisional, and raises whether the scope
  channel stays a second source or becomes just one more input to our own model.

  **Open questions — all four answered by the user 2026-09-09:**
  1. *Can DCS's radio callout texts be suppressed?* **Needs investigation, deferred.** Any approach
     touching module files fights integrity checks and is overwritten by updates; DCS's `SUBTITLE`
     option (Session 2 finding) is an unverified lead. Investigator task if/when this is revived.
  2. *Is suppression wanted?* **Only if possible, and low priority — deferred.** Not a blocker for
     anything else here.
  3. *Does the HelperAI scope channel survive as a distinct source?* **Yes — it stays.** The user
     needs it for later gameplay: commanding Petrovich to acquire a target, lock it, and fire.
     Those are a future, currently-deferred milestone, but they depend on the scope channel, so it
     is not collapsed into our own model and not dropped. **Consequence: the association namespace
     bug (backlog item below) matters more than its "PB-1 code, already merged" framing suggests —
     it is on the path to a wanted feature, not a dead branch.**
  4. *What does this do to BL-2/PB-2?* **Very little.** BL-2 (contact memory and association —
     persistent contact identities, detected/lost/reacquired, observation-vs-belief split, decay,
     behind a debug console that is the ancestor of the brain API; see `plans/body-layer/plan.md`)
     consumes `Observation` records through the `PerceptionSource` interface regardless of which
     channel produced them, and was never going to consume the DCS ambient channel because that
     channel is not readable. The only real change is emphasis: our own synthetic channel becomes
     BL-2's main source of contacts, with the scope channel as the second. No interface change.

  **Net remaining scope of this item**, once the deferrals above are taken out: adopt PB-1.5's
  filter as the primary detection mechanism rather than a fallback, and stop treating DCS's ambient
  output as an input we are waiting on. Both are framing/documentation changes plus calibration —
  no new machinery. Still `[?]`: do not start without the user's instruction.

- [ ] **`association.py` matches across two different DCS name namespaces and scores 0 on most real
  units** — *priority raised 2026-09-09: the user confirmed the scope channel is needed for later
  gameplay (commanding Petrovich to acquire/lock/fire), so this is on the path to a wanted feature
  rather than dead code.* — found 2026-09-09 while validating PB-1.5's `object_model.py`. `HybridPerceptionSource`
  matches HelperAI's detection text against `LoGetWorldObjects` candidates via
  `association._type_match_score`, but the two feeds speak **different vocabularies**: HelperAI
  emits Petrovich's *reporting* names (`"Slava cruiser"`, `"SA-3 launcher"`, `"Tarantul III
  corvette"`, `"SA-3 Low Blow radar"`) while `LoGetWorldObjects` emits DCS *type* names
  (`MOSCOW`, `5p73 s-125 ln`, `MOLNIYA`, `snr s-125 tr`). Measured scores for those four real
  pairs: **0, 0, 0, 0**. `"Ural truck"` vs `Ural-375` scores 1 — the only case that works, and
  only because the two names coincidentally share a word.

  This is not theoretical: those are exactly the units the PB-1 spike log actually captured
  (`aircraft-layer/research/2026-09-08-...`, Session 5 part 2, Finding 6). PB-1's live acceptance
  test passed because it used Ural trucks — the single type where the coincidence holds. So the
  scope channel's association is likely near-nonfunctional for ships, SAM sites and most armour,
  and this was invisible until now.

  **The fix is already in the repo**: PB-1.5 committed ED's complete 595-row type→reporting-name
  mapping (`body-layer/src/perception/data/dcs_type_to_reporting_name.tsv` +
  `reporting_names.py`). `association.py` should resolve each `LoGetWorldObjects` type name to its
  reporting name before scoring, so both sides speak the namespace HelperAI actually uses.

  Not fixed under PB-1.5 — it is PB-1 code, already merged to `main`, and a behaviour change to
  the scope channel deserves its own before/after evidence and live re-test rather than riding
  along in a milestone about a different channel. Related to, but distinct from, the multi-contact
  gap flagged in `plans/pb1.5-naked-eye-detection/plan.md` Risks (`hybrid_source.py` reads only
  `middle_list_text` and may be discarding real simultaneous rows). Both are worth doing in one
  pass over `hybrid_source.py`/`association.py`.

- [ ] **Incremental per-layer pipeline builds** — `build_region` currently deletes and recreates the entire `.sqlite` on every call, forcing a full rebuild of all layers each time. User-requested capability: run individual pipeline sections (e.g., roads only, elevation only, validation only) and *add* that data into an existing store, allowing staged builds and partial re-runs when debugging a single layer. Deferred post-M7 (raised during M7 DoD acceptance testing, explicitly not blocking). Considered for M8 and **explicitly dropped** from it (2026-09-06) to keep that milestone scoped to the probe store — this remains open and unscheduled for a later milestone. M9 (OSM) would benefit from it; see `plans/m9-osm-geofabrik/plan.md` design decision 4. See `plans/m7-full-theatre-pipeline/` for context and `world-model/src/build/pipeline.py`'s `build_region` implementation.

## Deferred

- Spatial storage/library choice — resolved by M5: stdlib `sqlite3` + R*Tree, JSON geometry (not GeoPackage/SpatiaLite/PostGIS). See `world-model/research/2026-09-04-m5-first-persistent-model.md`.
- M9 — OSM augmentation (geofabrik). **Deferred, value reassessed 2026-09-06.** OSM's original role split ("DCS = where, OSM = what") is now partly absorbed: DCS-native gives exact roads/named places/elevation, and M8's live-probe path can fill point-level `surface_type`/water ground-truth incrementally with zero new dependency. Remaining unique OSM value is narrow — settlement **boundary polygons** (DCS only gives town-center points) and semantic **tags** (road class/ref, land-use, POI type) that neither DCS nor probing produce. Not worth the new-dependency/`.osm.pbf`-parsing cost (see `plans/m9-osm-geofabrik/plan.md` open dependency decision) while no downstream consumer (Mission Interpreter/Runtime, both not yet built) needs settlement-extent reasoning or richer naming. Revisit only when such a consumer's requirements actually call for it — user decides when.
