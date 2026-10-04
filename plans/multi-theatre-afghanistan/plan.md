### Goal

Make the world-model pipeline and its runtime consumers (body-layer, mission-interpreter)
work for the Afghanistan theatre — registry entries plus the handful of Syria-hardcoded spots
the investigator found — while keeping the registry/entry pattern so Caucasus and Kola are
later *entries*, not a second design pass.

### Context already established (not re-derived here)

- `world-model/research/2026-10-04-multi-theatre-afghanistan-caucasus-recon.md` (investigator,
  2026-10-04, landed at `bc41bbd`): Afghanistan `tmerc` params fitted from `beacons.lua`
  (`central_meridian=63, scale_factor=0.9996, false_easting=-300149.9912,
  false_northing=-3759656.9499`), method validated against Syria (0.03 m) and Caucasus
  (<0.01 m vs pydcs) before being trusted on Afghanistan — **provisional, not yet live-
  confirmed**. All four parsers (`towns.lua`/`beacons.lua`/`.routes`/`.rn4`) work on
  Afghanistan's real files unmodified; two Syria-hardcoded bugs found (count guards,
  `pipeline.py`'s `"Syria.routes"` provenance string). Raw DEM (288 `.hgt`, 28–40°N/54–78°E)
  and the six-country OSM extract set are already staged on disk, gitignored, main checkout
  only.
- The architecture already generalizes: `THEATRE_PROJECTIONS`, `REGIONS`,
  `THEATRE_RASTER_REGISTRATIONS` are per-theatre dict registries, not per-theatre code forks
  (confirmed again by reading `coordinates/projections.py`, `build/region.py`,
  `raster/registration.py` directly this session). `store`/`query` are already fully
  theatre-parametrized (`Region.theatre` stored and read back, `describe_position(conn,
  theatre, x, z, ...)` takes `theatre` as a caller argument) — no code there needs to change
  for a new theatre.
- `RegionDefinition` already supports rectangular (non-square) half-extents, added specifically
  because Kola's footprint is ~1.4–1.7× elongated (`research/2026-09-05-m7-kola-square-vs-
  rectangle-stress-test.md`) — Afghanistan's own beacon-derived bbox (x span 1,023.9 km, z span
  1,249.1 km, ratio ~1.22) also benefits from this, not just Kola.
- `coord_probe.lua` (`world-model/tools/dcs-mission-probe/`), the script M1 used to live-verify
  Syria's projection, is theatre-agnostic as written (`coord.LOtoLL` + `world.getAirbases()`,
  no Syria-specific code) — directly reusable for Afghanistan, no modification needed.
- Mission-interpreter already extracts `mission["theatre"]` from a real `.miz` as a plain
  string, confirmed against an actual sample (`mission-interpreter/research/2026-09-12-miz-
  file-structure.md`'s correction note) and carries it through to the `--emit-compact` runtime
  artifact body-layer already loads at startup for BL-7 (`schema/build.py`'s
  `Tagged[str]` `theatre` field → `runtime/compact.py`'s `RuntimeMissionUnderstanding.theatre`
  → `body-layer/src/belief/mission_phase.py`'s `load_mission_understanding`). The wiring to
  pick a theatre's *store* from this value does not exist yet — today `--theatre` and
  `--world-model-db` are both separate, required, hand-typed flags on `logger.py`, independent
  of `--mission-understanding`.

### Affected Modules / Files

- `world-model/src/dcs_data/towns.py`, `beacons.py` — `EXPECTED_TOWN_COUNT`/
  `EXPECTED_BEACON_COUNT` become per-theatre dicts; `parse_towns_lua`/`parse_beacons_lua` take
  an explicit `theatre` argument.
- `world-model/src/build/pipeline.py` — `parse_towns_lua`/`parse_beacons_lua` call sites pass
  `region.theatre`; the hardcoded `Source(name="Syria.routes")` and the `f"Syria.routes (...)"`
  stage label become `routes_path.name`-derived.
- `world-model/tests/test_pipeline_build_region.py`, `test_probe_chunk_pipeline.py`,
  `test_pipeline_osm_cache.py` — monkeypatched `parse_towns_lua`/`parse_beacons_lua` lambdas
  need the new `theatre` keyword argument added (mechanical, not a rewrite of what they test).
- `world-model/tools/derive_m9_osm_clip_bbox.py` — takes a `region_name` argument instead of
  the hardcoded `REGIONS["syria-full"]`, so it works for `afghanistan-full` without a copy.
- `world-model/src/coordinates/projections.py` — new `THEATRE_PROJECTIONS["Afghanistan"]` entry,
  `confidence="provisional"`.
- `world-model/src/build/region.py` — new `REGIONS["afghanistan-full"]` entry (rectangular
  half-extents).
- `world-model/tests/test_coordinates.py` (or wherever Syria's control-point test lives) — a new
  Afghanistan control-point test, using a `beacons.lua` pair, with a docstring/comment stating
  it checks self-consistency with the provisional fit, not live-confirmed real-world accuracy
  (per `world-model/CLAUDE.md`'s "every transform needs a known control-point test" rule).
- `world-model/RUN.md` — an Afghanistan build section: the six-country OSM extract list, the
  already-staged input paths, the `afghanistan-full` build command, the lowercase-`map/`-path
  note (Afghanistan matches Syria's casing, unlike Caucasus — worth stating once here so the
  next theatre's RUN.md addition inherits the pattern).
- `body-layer/src/logger.py` — theatre/store resolution at `main()`: an optional
  `--world-model-dir`, and deriving `--theatre`/`--world-model-db` from a loaded
  `--mission-understanding` artifact's `theatre` field when the explicit flags are omitted.
- `body-layer/src/perception/geometry.py`'s `open_world_model` call sites (or a thin wrapper
  next to it) — a theatre-mismatch guard using `store.reader.load_only_region`, already
  imported one level up in the same package.
- Out of scope, stated explicitly rather than left silent: **raster chart (F10 map, M2)
  registration.** Nothing in the serving path (`query/describe.py`, body-layer, mission-
  interpreter) consumes `raster/registration.py` — only two diagnostic tools do
  (`inspect_raster.py`, `inspect_osm_overlay.py`'s background-image option). An Afghanistan
  sortie loses nothing a pilot would notice by this staying unregistered; it would only affect
  a diagnostic-tool invocation nobody runs during a sortie.

### Implementation Plan

1. **Fix the two Syria-hardcoded bugs the investigator found, independent of Afghanistan.**
   Each is small and separately testable:
   - `EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT` → `dict[str, int]` keyed by theatre
     (`{"Syria": 1182, "Afghanistan": 1225, "Caucasus": 1759}`, extending as later theatres are
     added — exact counts are already known from the investigator's note, so Caucasus can be
     added now even though its registry entries aren't). `parse_towns_lua(path, theatre)` /
     `parse_beacons_lua(path, theatre)` raise a clear `ValueError` (not `KeyError`) naming the
     theatre if it isn't in the dict yet — keeps the project's existing "fail loudly on a count
     change" intent exactly, just scoped per theatre instead of globally. `pipeline.py`'s two
     call sites pass `region.theatre`.
   - `build/pipeline.py`'s roadnet-ingest stage: `Source(name="Syria.routes")` →
     `Source(name=routes_path.name)`; `f"Syria.routes ({...})"` → `f"{routes_path.name} ({...})"`.
   - `tools/derive_m9_osm_clip_bbox.py`: add a `region_name` positional CLI arg (default
     `"syria-full"` to keep the existing invocation working), replacing the hardcoded
     `REGIONS["syria-full"]` lookup.
   - Test: existing Syria-path tests still pass unchanged in behavior (count values and
     provenance strings for Syria are identical to before); update the three monkeypatch
     lambdas to accept `theatre`.

2. **Register Afghanistan.**
   - `THEATRE_PROJECTIONS["Afghanistan"]`, `confidence="provisional"`, `source` citing the
     2026-10-04 investigator note and stating explicitly what would upgrade it (Stage 4 below).
   - `REGIONS["afghanistan-full"]`: derive the padded DCS x/z centre + rectangular half-extents
     from the **union of `towns.lua` (projected to x/z with the new params) and `beacons.lua`**
     point clouds — not beacons alone (main-loop amendment 2026-10-05: Afghanistan has only 49
     beacons, all airfield-tied, and the investigator found towns.lua the safer lower-bound source;
     beacons alone gave x span 1,023.9 km, z span 1,249.1 km), padded the same way Syria's was (+30 km/side), mirroring
     `research/2026-09-05-m7-syria-theatre-extent.md`'s method — a small reproducible script,
     not a hand-typed number, the same discipline `derive_m9_osm_clip_bbox.py` already uses for
     Syria's OSM clip bbox.
   - Control-point test: pick one Afghanistan `beacons.lua` entry, assert
     `dcs_to_wgs84("Afghanistan", x, z)` reproduces its `positionGeo` to the same ~0.03 m floor
     the investigator's fit already measured. Comment states plainly this is self-consistency
     with the provisional fit (per the M1 circularity caveat already on record for Syria/
     Afghanistan's `positionGeo`), not a live-DCS or real-world check.
   - Cheap pre-check, no live mission needed: confirm the exact string DCS writes to
     `mission["theatre"]` for an Afghanistan mission matches the registry key `"Afghanistan"`
     exactly (case included) — open any Afghanistan `.miz` (a blank one saved in the Mission
     Editor is enough) and read `mission["theatre"]` directly, or run mission-interpreter's
     existing `.miz` parser against it. This does not need a running mission or Mission
     Scripting access, only a saved mission file, so it can happen before Stage 4's live probe.

3. **Build `afghanistan-full` and verify it the same way `syria-full` is verified.** Using the
   already-staged inputs (`data/raw/dem/afganistan-full/`, `data/raw/osm/afganistan-full/`):
   job (a) (OSM: download is done, run `extract`/`merge`/`tags-filter` with the six-country list
   the investigator already validated), then job (b)
   (`tools/build_world_model.py afghanistan-full --towns ... --beacons ... --routes ...
   --srtm-dir ... --osm-pbf ...`). Check per `RUN.md` §3.5: non-zero `road`/`junction`/
   `settlement`/`named_place`/`water`/`landcover`/`coastline` counts (Afghanistan is landlocked: `coastline` = 0 is expected there — main-loop amendment 2026-10-05), then spot-check a known
   place (e.g. Kabul) via `describe_position`. Add the resulting RUN.md section once the real
   command has actually been run and the counts checked, not written speculatively.

4. **Live projection verification (user task, Windows DCS box) — the provisional→confirmed
   upgrade.** Mirrors M1→M1-verification exactly:
   - Build a minimal Afghanistan mission (any aircraft, any airfield start — the mission content
     doesn't matter, only that it loads the Afghanistan terrain).
   - Run `coord_probe.lua` unmodified via a `DO SCRIPT FILE` trigger a few seconds after mission
     start (same procedure as `tools/dcs-mission-probe/README.md` already documents for Syria).
     It dumps `coord.LOtoLL` for the theatre origin and every airbase `world.getAirbases()`
     returns, to `Saved Games/DCS/Logs/coord_probe_output.json`.
   - Copy that JSON back (same sync path M1 used) into
     `world-model/data/raw/dcs/<date>/`, and compare each point's live `lat`/`lon` against
     `dcs_to_wgs84("Afghanistan", x, z)`'s prediction using the provisional params.
   - **Pass criterion:** residual ≤ ~0.1 m at every sampled point (the same float-rounding-noise
     floor M1 measured for Syria, 0.00–0.03 m, and the investigator's own beacon-fit validation
     runs, ~0.03 m) → flip `confidence` to `"confirmed"` in `THEATRE_PROJECTIONS["Afghanistan"]`
     and update its `source` string to cite the new research note, exactly as Syria's M1→M1-
     verification did. A residual materially larger than that floor at *any* point (metres, not
     sub-metre) means the provisional fit is wrong and must not ship as confirmed — write a
     dated research note with the actual residuals and re-open this stage rather than silently
     accepting a worse number.
   - While the mission is open, confirm Stage 2's `mission["theatre"]` string match (same
     mission file covers both checks, no extra setup).
   - This step requires the user's own hands (Windows DCS box, a live or saved mission,
     Mission Editor access) — nothing here can be done from this environment or by Investigator,
     who also has no live DCS access. Record the result as a dated `world-model/research/` note
     either way (pass or fail), same discipline as every other finding in this plan.

5. **Body-layer picks the theatre from the mission, not a remembered flag.**
   - `logger.py`'s `main()`: if `--theatre`/`--world-model-db` are both given, they win
     unchanged (needed for small test regions like `latakia-20km`/`gemerek-20km`, and for
     running without a mission-understanding artifact at all). Otherwise, if
     `--mission-understanding` is given, derive `theatre` from the already-loaded
     `mission_data.theatre.value` and resolve the db path as
     `<world_model_dir>/<theatre.lower()>-full.sqlite`, where `--world-model-dir` is a new flag
     naming the directory holding the per-theatre full-theatre stores. If neither combination is
     satisfiable, `parser.error(...)` with a message naming both valid forms — no silent
     fallback to a default theatre.
   - **Mismatch guard, independent of how theatre was resolved:** right after
     `open_world_model(args.world_model_db)`, call `store.reader.load_only_region(conn)` (already
     a sibling import in `perception/geometry.py`, no new coupling) and compare
     `region.theatre` against the resolved `theatre`. A mismatch exits loudly before the first
     poll — today nothing catches "pointed `--theatre Syria` at an Afghanistan store," and
     `dcs_to_wgs84` would silently apply the wrong projection and produce a plausible-looking,
     wrong position for every contact. This is the same "never produce a convincing-but-wrong
     output silently" posture the roadnet container format already enforces, applied to the one
     place body-layer's own config can currently violate it.
   - Why this earns its place against the pilot-value test (CLAUDE.md): this is not a
     convenience feature for whoever runs the logger — it is what stands between "Petrovich's
     world knowledge is right" and "Petrovich's world knowledge is silently, confidently wrong"
     on the day the user actually flies an Afghanistan sortie with mission-interpreter already
     wired up. Scoped small: one derivation branch plus one guard, no new subprocess, no new
     dependency.

### Design confirmation: why Caucasus and Kola are entries, not rework

Every piece touched above is a per-theatre dict (`THEATRE_PROJECTIONS`, `REGIONS`,
`EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT`) or a derived value computed from one
(`to_wgs84_envelope`, the OSM clip bbox). Caucasus already has its own investigator-verified
provisional `tmerc` fit (<0.01 m vs pydcs) and extent data in the same 2026-10-04 note; Kola's
elevation-source blocker is already resolved (`viewfinderpanoramas` DEM3 covers it, same `.hgt`
format `elevation/dem.py` already reads, per the ROADMAP's 2026-10-04 update) and its aspect
ratio is exactly why `RegionDefinition` grew rectangular half-extents in the first place. Neither
needs `open_world_model`, `describe_position`, `store`/`query`, or body-layer's new theatre-
resolution logic to change again — they need the same five stages above re-run with their own
numbers. The one thing *not* yet generalized and not touched here is raster-chart registration
(explicitly out of scope, see above) — if a future milestone does give it a real consumer, that
consumer is where the next generalization decision belongs, not this plan.

### Risks & Unknowns

- Afghanistan's `tmerc` parameters are provisional until Stage 4's live probe — no second
  source exists for Afghanistan the way pydcs existed for Caucasus, so this is genuinely
  higher-risk than Caucasus will be when its turn comes.
- Afghanistan's true mesh extent beyond the beacon/towns point-cloud lower bound is not
  established (the `.surface5` scan stalled on a tool-performance problem, not a data question,
  per the investigator note) — `REGIONS["afghanistan-full"]`'s half-extents are a padded lower
  bound, same posture Syria's own `syria-full` region already has, not a corner-verified edge.
- The exact string DCS writes to `mission["theatre"]` for Afghanistan is assumed to be
  `"Afghanistan"` (matching the terrain folder name, same convention Syria/Caucasus already
  follow) but is not yet independently confirmed from a real `.miz` — Stage 2's pre-check closes
  this before Stage 5's code depends on it.
- Stage 1's monkeypatch-signature fix touches three existing tests; if any other test
  monkeypatches these two functions and was missed in this grep, it will fail loudly at test
  time (not silently) and needs the same one-line fix.
- `tools/probe_surface5_elevation.py`'s quadratic-ish blowup on `Afghanistan.surface5` is a real
  tool-performance bug, left unfixed per the investigator's own effort/value call — flagging
  again here so it isn't silently forgotten if a future milestone actually needs that data.

### Second-order effect

Once Afghanistan's registry entries exist and Stage 5 lands, the *pattern* for adding a theatre
is fully exercised end-to-end for the first time (build-side registries, live verification,
runtime theatre selection) — Caucasus and Kola become "repeat Stages 1–4 with their own numbers"
rather than requiring their own design pass, which is the whole point of doing Afghanistan first.
It also mildly narrows Mission Interpreter / BL-7: anything downstream that assumes
`--mission-understanding` is optional cosmetic metadata now has one real consumer (theatre
selection) depending on `theatre` being present and correctly spelled — a corrupted or
hand-edited compact artifact with a wrong `theatre` string now has a real, user-visible failure
mode (the Stage 5 mismatch guard) rather than silently being inert.

### Decisions Requiring User Input

- **None block starting Stages 1–3.** Stage 4 (live projection verification) is not a decision
  but a task only the user can physically perform (Windows DCS box, a live mission) — flagged
  above, not here, since there's no tradeoff to choose between.
- Recommended default for Stage 5's `--world-model-dir` convention
  (`<dir>/<theatre.lower()>-full.sqlite`) is a naming convention, not an architectural fork — if
  the user already has a different directory/naming scheme in mind for where per-theatre stores
  will live on the Windows box, say so before Implementer wires the path-join logic, since
  changing it later only costs a rename, but changing it silently different from what's actually
  on disk would make Stage 5 fail at the first real sortie.
