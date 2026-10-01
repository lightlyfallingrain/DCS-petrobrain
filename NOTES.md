# NOTES.md

Knowledge harvested from feature work and investigation. Short, factual, one idea per bullet. Obvious patterns from code or CLAUDE.md belong in CLAUDE.md, not here — these are insights earned by doing.

## Coordinate Transforms & Projections

- **Syria's projection is Transverse Mercator, not Lambert Conformal Conic.** Community folklore said "Lambert per theatre" but investigation found pydcs (LGPL-3.0, empirically fitted) uses `+proj=tmerc` with fitted parameters, confirmed via 226-point live `coord.LOtoLL` reproductions to 0.00–0.03m residual (Finding 1 of M1 verification note). ED doesn't document this directly in terrain Lua; empirical fitting is the only practical approach.

- **DCS internal geodesy vs. real-world misalignment is per-airport terrain-art placement error, not a projection defect.** Three independent real-world ARPs (Damascus 1137.5m, Latakia 1314.1m, Beirut 962.8m residual) show non-systematic direction/magnitude across ~250km, ruling out datum shift/parameter error. Consistent with terrain artists placing each airbase independently against satellite imagery without ARP-grade surveying (Finding 4 of M1 verification note). Budget ~1–1.3km expected displacement in M2/M3 when registering DCS geometry against OSM/real-world features; do not assume DCS airbase points line up with published ARPs better than that.

- **`beacons.lua` positionGeo is not an independent ground-truth source.** Every beacon entry's `positionGeo` is computed by ED's internal projection (baked at terrain build time), matching `coord.LOtoLL` to within 0.03m — it's a *free, offline* source equivalent to `coord.LOtoLL` itself, not a real-world cross-check (Finding 2 of M1 verification note). Useful for offline pipeline development, but evidence-wise belongs in the same category as `coord.LOtoLL`, not as external validation.

- **Theatre-agnostic transform design means adding a second theatre requires only a registry entry.** `src/coordinates/` layer doesn't encode Syria-specific logic — the `dcs_to_wgs84`/`wgs84_to_dcs` functions are theatre-agnostic. New theatres need only a new `TmercParams` entry in `THEATRE_PROJECTIONS` dict with `source` and `confidence` fields populated. Confidence starts `"provisional"` for unprobe-verified theatres; flips to `"confirmed"` only after live `coord.LOtoLL` cross-check.

## Testing & Provenance

- **Control-point tests must use externally-published ARPs, not DCS-derived points.** Early approach using pydcs's hardcoded `Damascus` point inflated the residual by ~1741m (the pydcs point itself was imprecise vs. live `coord.LOtoLL` output). M1 control points use SkyVector/eAIP real-world ARPs instead, avoiding circularity (Finding 3 of M1 verification note). Lesson: when validating a DCS extraction pipeline against external truth, ensure the external truth is actually independent, not recalculated from the same source.

- **Confidence field distinguishes third-party-fitted from live-install-verified parameters.** Syria's registry entry is `confidence="confirmed"` because Finding 1 reproduced 226 live DCS points to sub-cm residual; future theatres can be added with `confidence="provisional"` without code changes. This protects against silently encoding unverified community claims as fact, per project invariant (docs/CONVENTIONS.md).

## Raster Charts & Registration

- **RasterCharts tile axes are asymmetric relative to DCS's x/z convention.** z-tile-index increases east (same direction as DCS +z), but x-tile-index increases south (opposite DCS +x=north) — this is not derivable from filename grammar alone and must be applied explicitly in coordinate math. Session 8 finding: failure to encode the asymmetry propagates a sign error through half the transformation (M2 registration fitting against real-world control points confirmed this empirically; the mistake would have been caught only by cross-checking residuals per axis, not by inspection alone).

- **RasterCharts storage structure is theatre-specific, not uniform.** Syria uses a single `rasterCharts.zip` archive containing all tiles; Caucasus uses a genuine multi-scale tile pyramid with per-scale subdirectories and many small per-tile `.zip` files. The pipeline must not assume single-archive layout generalizes to all theatres (M0 finding from `DCS-files.txt`). Theatre-to-archive-structure detection belongs in the probe/extraction layer, not the registration math.

- **Registration parameters must be fitted to a specific scale/sheet/level combination; do not assume portability across variants.** M2 fitted `origin_x`/`origin_z` against Syria's `64m` sheet `aa` level `00` only — other scales (`32m` tier) and other levels/sheets for the same scale are untested. Cross-validating registration against a second sheet (e.g. `64m` `ab`, or the `32m` tier) before upgrading `confidence` from `"provisional"` is a Stage 4 task, not automatic (M2 implementation summary, session 29).

- **Per-sheet/level registration independence mirrors the multi-projection pattern from M1.** Just as different theatres need separate `TmercParams` entries, different RasterCharts sheets/scales need separate registration entries if confidence is to be meaningfully tracked. The registry structure (`THEATRE_RASTER_REGISTRATIONS: dict[str, RasterRegistration]`) is sufficient for per-theatre but not per-sheet; extending it to handle sheets (e.g. dict-of-dicts or a composite key) is left to when multi-sheet support is actually needed, not pre-built on speculation.

- **A held-out control point (Gemerek, not used in the empirical fit) confirmed the registration residual is real, not overfit.** Result: ~129m x-axis, ~5.5km z-axis — consistent with the ~9% z-axis looseness already flagged from the fit points themselves. `confidence` correctly stays `"provisional"` off one held-out point rather than being opportunistically upgraded (M2 Stage 4).

- **RasterCharts tile `level` suffix semantics remain unresolved** (`-2`, `-1`, `00`, `01` in filenames) — no locally sampled tile exists at any level besides `"00"`, so `default_level="00"` is a documented process choice, not a confirmed mapping. Do not reason by analogy from the unrelated `clipmaps` container format (`level*32` does not transfer). Needs a WSL-side sample at another level before this can be resolved (M2 Stage 4, deferred to investigator).

- **Ruff's isort first-party detection is cwd-dependent and will silently flip-flop without `known-first-party` pinned.** Running `ruff check world-model/src world-model/tests` from the repo root vs. cwd=`world-model/` resolved local packages (`coordinates`, `raster`, `control_points`) into different import-sort buckets, causing the same I001 finding to be "fixed" and recur 3+ times across M1/M2 sessions. Fixed by pinning `[tool.ruff.lint.isort] known-first-party` in `world-model/pyproject.toml` — always verify a lint fix from the *canonical* invocation cwd, not whichever cwd the agent happened to be in.

## External Binaries & CLI Utilities

- **macOS `say` command silently falls back to default voice on unknown `--voice` argument.** Unlike typical CLI tools that error on invalid arguments, `say -v "Nonexistent Voice Name" "text"` exits 0 and produces audio in the system default voice, not an error. Do not rely on voice-name validation via the CLI — invalid voices must be caught in code or accept silent fallback behavior. Confirmed live during BL-10 implementation (2026-09-17). Implication: any voice-selection feature must either (a) validate against `say -v '?'` output before invoking `say`, or (b) accept that an invalid voice name degrades silently to default.

## External Data & Integration

- **pyosmium's sparse_mem_array index handles geometry resolution in C++, preventing Python-side memory blowup on large extracts.** M9's concern about 646 MB Turkey extracts was resolved by using `osmium.SimpleHandler.apply_file(..., locations=True, idx="sparse_mem_array")`: the index builds in C++ and resolves way-node geometry without materializing a Python dict of tens of millions of (node_id, lat, lon) tuples. A naive approach (Python dict-based node cache) would blow up ~4–5 GB on Turkey's 13M+ nodes; `sparse_mem_array` stays under 100 MB. Any future work parsing large `.osm.pbf` extracts should use this approach; the memory saving is non-negotiable at continental scale (M9 implementation note).

- **Query surface can remain unchanged when data source swaps if upstream shape is consistent.** M9's Design Decision 3 verified that swapping OSM source from Overpass JSON (via `osm.features.load_features`) to Geofabrik `.pbf` (via `osm.pbf.load_features`) required zero changes to `query/describe.py`, `store/schema.py`, or `store/reader.py` — the `OsmFeatureSet`/`OsmNode`/`OsmWay` shapes and the two parsers' output contracts are identical. This pattern generalizes: when a feature's scope is purely a data-sourcing problem (different origin, same shape, same downstream interface), the implementation surface is contained to the source/parse layer, not scattered across dependent code. Build with this in mind: design the shape once, make data sources interchangeable (M9 plan and review).

- **Overpass API requires an explicit `User-Agent` header; requests with none are rejected (HTTP 406).** `urllib.request`'s default carries no User-Agent, triggering rejection from `overpass-api.de`. Setting a client-side user-agent string before the request fixes it (M3 finding; `osm/overpass.py`'s `_USER_AGENT` constant). Important for any future code using Overpass or similar strict HTTP services.

- **Different real-world reference conventions for the same named place produce measurable geographic separation.** Gemerek's OSM node coordinate (39.1831222, 36.0711044) and the Wikipedia-sourced by-eye chart reading from M2 (39.18194, 36.06806) are ~300m apart in longitude — both correct, just different conventions ("the town node" vs. "town symbol on a paper chart"). When comparing transforms between DCS/OSM/chart readings, verify which reference point each source uses before claiming alignment or misalignment as evidence of error (M3 displacement report finding).

- **Rural Turkish regional OSM coverage is dense enough for rendering (96 highways, 17 buildings in a 2.8×3.4km Gemerek bbox).** Was considered a fallback scenario risk, but turned out adequate without fallback to Sivas. Not a universal finding — coverage varies by region/tagging practice — but useful baseline for assessing whether a control point's OSM data will be meaningful (M3 Stage 1).

## DCS Elevation Extraction

- **DCS elevation is Mission Scripting–only; no offline heightmap exists.** Terrain surface data under `Mods/terrains/Syria/` is proprietary undocumented binary formats (`.ng5`, `.surface5`, `.tile`, `.sup4`), and `terrain.cfg.lua.pak.crypt` is packed/encrypted. `land.getHeight({x, y=z})` via a live-mission trigger script is the only known extraction route (M4 investigator recon finding). Offline pipeline code cannot call `land.getHeight` — only live-mission probes can, requiring the same workflow pattern as M1's `coord.LOtoLL` probe.

- **SRTM grid-size derivation from file length generalizes across resolutions.** M4's `dem.py` derives grid size from file byte count (`sqrt(byte_count/2)`) rather than hardcoding 3601×3601 (SRTM1 default). This proved invaluable when the user supplied SRTM3 (1201×1201, ~90m) instead of SRTM1 (~30m) — no code change was needed to parse it correctly. The choice costs nothing and protects against silent mis-sizing if future work encounters other resolution variants (M4 implementation note, Addendum 2).

- **Terrain-mesh-resolution mismatch has a distinct spatial signature from vertical datum offset.** A systematic, uniform delta across a grid points to a datum mismatch (e.g., EGM96 vs. DCS's unknown reference); spatially-localized, sign-varying deltas concentrated in geographically coherent regions indicate mesh-resolution noise. M4's delta report (-86m at the west edge, smooth gradient, +13.89m mean modest relative to ±86m range, positive/negative split 76/24) matches the latter signature, distinguishing it from a transform bug or datum offset. Use this pattern to interpret future elevation comparisons without over-claiming systematic shifts (M4 research note analysis).

- **`io`/`lfs` are stripped by default in installed `MissionScripting.lua`; probes require manual edit to use `io.open`.** This is a standing pattern for investigation-only probes (never for pipeline code). The edit must be reverted when probes are complete if persistent access is not needed. Document the prerequisite in probe headers, and revert status in research notes, not silently (M4 plan risk section, research note close-out).

- **Probe resilience via `pcall` per iteration prevents one failure from aborting the whole run.** Both `coord_probe.lua` (M1) and `elevation_probe.lua` (M4) wrap each point/query in `pcall`, yielding `null`/error for a failed point rather than terminating early and losing all prior data. Preserve this pattern in future probes; it buys robustness at negligible cost (M4 implementation note).

## Persistent Storage & Spatial Indexing

- **DCS-native road geometry is embedded in terrain files, not mission-scripting-only.** `Mods/terrains/<Terrain>/roads/<Terrain>.routes` (whole-theatre, ~2.25GB for Syria) and `.rn4` files contain pre-computed road centerlines, direction vectors, and type names — no live-mission probe required. The `.routes` format is an undocumented binary `landscape4::` container with position/direction arrays per-route and a ~156-byte/point trailer region; byte-exact reverse-engineering from real files (Finding G, M5 plan) enables offline extraction with mmap-based streaming to avoid loading the full file (M5 Stage 2).

- **Route-block resync via forward scan with a coordinate pre-filter is reliable, not speculative.** After each route's direction array, scanning forward for the next plausible `int32 N` (range 5–20000) followed by N xyz triples inside DCS's real coordinate envelope (`|x|,|z| < 1e6`, `-2000 < y < 6000`) yields zero false positives across 15 tested consecutive routes. The pre-filter (checking first/middle/last coordinates against bounds before full unpacking) is mandatory, not optional — naive scanning without it takes >6 CPU-minutes on a 50MB buffer (M5 Stage 2 rung 1 discovery).

- **R*Tree indexing is sufficient for describe_position's spatial queries on regional scale.** M5's Latakia store (3,710 features, ~9MB) achieves sub-millisecond nearest-feature queries via standard expanding-radius bbox search (500m/2km/8km/30km windows) over an R*Tree index, with exact geometry distance computed only over bbox-pruned candidates. No specialized geospatial DB is needed; pure SQL + stdlib is tractable (M5 performance note).

- **Multipolygon relations must be counted when they exist, not silently dropped.** Overpass queries for water/landuse features return both ways and relations; relations (typically multipolygon boundaries) represent ~1–2% of fetched elements and are structurally present but often untagged for the target category (e.g., a multipolygon relation with no `natural=water` tag on the relation itself, only on the outer way). Code that silently skips relations introduces an invisible false-positive risk later: ingested ways may look complete in isolation but represent only part of the real geographic feature (M5 Stage 1 finding — now tracked as `OsmFeatureSet.relations_skipped`).

- **Beacons.lua's `{x, y, z}` geometry has y (elevation) in the middle slot, not z.** This is the opposite of most DCS coordinate conventions and will silently place every beacon at sea level if not caught by a hard test. `beacons.lua`'s position field is a literal 3-element Lua table parsed left-to-right: `x`, elevation (NOT z), `z`. A test must pin the field order; DCS patch changes to the file format will make the test fail loudly (M5 Stage 1).

- **Towns.lua positional uncertainty remains genuinely unresolved despite a diagnostic.** M5's investigation (using an OSM-name-match diagnostic) returned one supporting match (Jablah: 465m residual) and one apparent false match (Al Hannadi: 6km, likely a different real-world place). n=1 is not decisive. Set the uncertainty conservatively to 1,300m (OSM's typical residual) and `confidence="medium"` rather than upgrading prematurely; a future session with hand-verified real-world place coordinates can re-investigate (M5 Stage 1 notable discovery).

## Multi-Store & Modular Storage

- **Two-store separation prevents the "newest grid wins" silent failure mode for non-rebuildable data.** M5's `reader._load_grid_meta` resolves grids with `ORDER BY id DESC LIMIT 1`, and every grid read inherits it — in a single table, adding a small probe-tier grid would answer for the whole theatre, with M7's 591,732-point SRTM baseline going silently dark. M8's two-store design (base + probe) eliminates this bug class by construction: base-only code cannot see probe rows, and probe-then-base fallback is explicit. When holding separate datasets with different lifecycles (base: delete-and-rebuild from raw; probe: accumulate from flights), a single table is a disaster-waiting-to-happen — enforce separation at the file/database level, not by convention (M8 plan rationale, confirmed in implementation).

- **Validation checks on a shared resource must be duplicated across all code paths that access it, not assumed to run once.** M8's write-path drift detection (`probe_store.writer.open_probe_store`) checks theatre/lattice/schema version and raises on mismatch — but M8's read path (`describe_position`'s direct `ATTACH`) bypassed that code entirely. Reviewer reproduced a cross-theatre silent answer (Kola probe attached to Syria base, returning Kola data labeled as valid). Every access path needs its own validation: `ATTACH` called its own `check_probe_paired_with_base` alongside `check_probe_schema_version`. Lesson for any multi-access-path design: do not assume "the validation ran somewhere else" — code each path independently, and test every path with a real mismatched state (M8 review finding, fix verified with 3 new tests including reviewer's own repro scenario).

- **Coverage tri-state keyed per (kind, chunk_ix, chunk_iz) enables extensibility without schema changes.** M8's coverage records (unqueried/queried_with_data/queried_void) are keyed `(kind, chunk_ix, chunk_iz)`, not by chunk alone, allowing the probe store to hold multiple data kinds (fine elevation, surface_type, ridge/valley today; more in future) with independent coverage tracking per kind. The `UNIQUE(kind)` constraint on grids prevents "newest grid wins" at the grid level. New kinds are added without schema migration — `upsert_grid_samples` and `upsert_chunk_coverage` are generic by kind. This pattern proved by test: `test_extensibility_new_raster_and_vector_kind_need_no_schema_change` creates invented kinds and confirms zero table/column additions via `sqlite_master` introspection (M8 implementation note).

## Planning & Process Lessons

- **Plan "Affected Modules" sections can become stale if locked decisions are made after the list is drafted.** M7's initial "Affected Modules" list named `src/build/ingest_terrain.py` for SRTM-related work, written before the plan's Locked Decision 5 ("M6's ridge/valley classifier is explicitly NOT rerun here") was finalized. The explicit lockout made the named reference stale, but the reference remained in the plan text — Implementer correctly treated the explicit lockout as authoritative and did not touch `src/terrain/`. Lesson: after freezing a plan with locked decisions, do a final pass over the "Affected Modules" section to remove any stale references introduced by the later constraints, or accept a note explaining the divergence (M7 Stage 2 implementation discovery).

- **Commit boundaries are not always obvious in a multi-stage feature branch.** M7's Stage 3 implementation (control-point validation) was coded into existence but not committed to the branch immediately; Stage 4's implementation caught it during testing and prompted a commit. The delay didn't cause a defect, but it meant a single `git log` read across the branch didn't show complete Stage 3 work until Stage 4 was reviewed. Lesson: commit each feature stage as soon as its tests pass and checks clear, not when "the next stage makes sense to combine." Per-stage commits give Reviewer/DoD/future-sessions better visibility into the incremental development (M7 implementation timeline note).

- **Full-rebuild-only pipeline architecture should be surfaced during Architect's planning phase, not discovered as a gap during DoD acceptance testing.** M7's user raised a real architectural limitation ("destructive full-rebuild" per `build_region`'s current design) during DoD acceptance testing, after code and tests were complete. The user explicitly deferred it as not blocking M7, but the discovery pattern is worth noting: for future multi-stage pipeline features, Architect should explicitly ask "will the user want to run individual stages incrementally, or always full-rebuild?" and document the answer in the plan's constraints section. This surfaces the question when scoping is still cheap, not when implementation is done (M7 DoD acceptance-testing finding).

- **Never undo a live-patch-and-revert sanity check with `git checkout -- <tracked file>` if that file carries unstaged work.** Proving a new tripwire test actually fails on a reverted implementation (patch a constant/behavior, run the test, confirm red, then undo) is good practice — but `git checkout --` on a file with unstaged edits silently discards everything back to `HEAD`, not just the temporary patch. Happened live during binocular-optic Stage 3b: all of `optic_policy.py`'s Stage 3b edits were lost this way and had to be reconstructed from memory of the diff — the file looked "restored" (green tests) but was actually reverted past the pre-patch state. Use a scratch copy instead (`cp file /tmp/backup`, patch, test, `cp /tmp/backup file`) for this class of check, unconditionally (binocular-optic Stage 3b implementation, 2026-09-23).

## Type Checking & Python Conventions

- **`float ** float` returns `Any` under `mypy --strict` — use `math.pow()` instead.** The `**` exponentiation operator's overloads admit a `complex` result in general, so mypy cannot narrow the return type to `float` even when both operands are `float` and the result is mathematically `float`. Solution: `math.pow(0.5, x)` has an unambiguous `float -> float` signature in typeshed and passes strict checking without surprises. Lesson: any future exponentiation in this codebase should use `math.pow()` proactively rather than triggering a `no-any-return` error later (BL-3 implementation note).

- **Platform-guarded Windows imports must use `if sys.platform == "win32": import ...`, not bare `try: import / except ImportError`.** typeshed's `winsound` stub (and similar Windows-only stubs) report all members as "no attribute" outside `sys.platform == "win32"`, so `mypy --strict` fails even on a bare `try` block that would work at runtime. The static platform check is recognized by mypy and skips type-checking the unreachable branch for non-Windows platforms. Pattern: `if sys.platform == "win32": import winsound; ... _player = _WinsoundPlayer() else: ... _player = NonWindowsStandIn()`, where the stand-in raises `RuntimeError` on any call (the code is never executed on Windows, and never expected to succeed on non-Windows). Confirmed via reproduction on this codebase (BL-10 implementation, `aircraft-layer/src/collector/audio_sender.py`, 2026-09-17).

## Petrobrain Runtime & Perception

- **Incremental committing during loss-prone work is standing practice, not a workaround.** PB-2/BL-2's implementation lost uncommitted work twice to unrelated infra issues (machine sleep, stream stalls) before Stage 2. From Stage 2 onward, every stage's implementation was verified (format, lint, test) and committed as soon as checks passed, rather than holding it until the next stage made sense to combine. This became deliberate practice: each feature stage should be committed independently once its tests pass and checks clear, giving better visibility into incremental development and protecting against context loss. Pre-implementation knowledge: commit boundaries are not always obvious; post-implementation discovery is expensive. Commit early (PB-2 implementation timeline discovery).

- **Plan citations to concept docs should be verified early — documented placeholders beat blocking.** PB-2 Stage 2's plan cited `docs/concept/PETROBRAIN_RUNTIME.md` §3.4 for a concrete "certainty table" with specific thresholds, but the doc has no numbered §3.4 section and no concrete table — only unnumbered `##` headings and informal descriptions of the *shape* (four attributes, four decay speeds, four example wordings). Rather than block, the implementer derived a tightly-constrained four-level ladder (`"observed"`/`"tracked"`/`"estimated"`/`"lost"`) matching the four wordings 1:1, documented it as a placeholder interpretation, and the Reviewer confirmed this was the right move. Lesson: when a plan depends on a concept-doc section that turns out not to exist as specified, a documented placeholder-with-reasoning beats treating it as a blocker or silently guessing. Flagged here so future plan authors verify concept-doc citations for real existence before finalizing a plan that depends on them (PB-2 Stage 2 notable discovery).

- **Cross-channel fusion reveals namespace/vocabulary mismatches that single-channel validation cannot.** PB-2 Stage 0 discovered that the scope-channel (HelperAI hybrid tier) was scoring 0 on real navy objects (`MOSCOW`, `MOLNIYA`), armoured SAM units (`snr s-125 tr`), and most non-truck targets — not because the channel itself was broken, but because the type-match logic scored only against DCS *type* names, not the reporting names ED publishes. Real `object_type` strings like `"SA-3 launcher"` (scope's human-readable output) never matched DCS internal types like `5p73 s-125 ln` because the two speak different vocabularies. Single-channel testing masked this entirely (naked-eye has its own OP_* vocabulary). Lesson: when adding cross-channel fusion, exercise real multi-channel fixture scenarios early; vocabulary mismatches are a defect class distinct from incomplete coverage and cannot be found by testing one channel in isolation (PB-2 Stage 0 scope-emphasis).

- **Three-valued class compatibility (compatible/unknown/incompatible) prevents silent bad merges better than binary logic.** PB-2 Stage 1's percept-to-contact gating uses a three-valued scheme: when one channel says `OP_TRUCK` and the other says `"Ural truck"` (scope free text), `object_model.profile_for` treats the latter as unknown (not incompatible, not confirmed). The gate requires both spatial AND class logic to pass, so `unknown` neither blocks nor confirms a merge. This weak vocabulary coupling means fusion will under-merge (producing duplicate contacts) when vocabularies diverge, but never causes a silent bad merge. Lesson: when designing a multi-source system where one source has richer vocabulary than another, a three-valued compatibility scheme is preferable to binary/flag-based logic — it surfaces the weakness (duplicate contacts visible to users) without hiding it (PB-2 Stage 1 design choice).

- **Emission-cap vs. acquisition-cap distinction requires architectural state split.** PB-2 Stage 3 required re-reading `NAKED_EYE_MAX_NEW_PER_POLL` as an acquisition-rate limit (throttle *entry* into the acquired set) rather than emission cap (throttle *output*). The modes have contradictory semantics: under `on_change`, a capped-out object never retries (marked "already seen" forever until it re-enters LOS), preserving the single-emission debounce; under `every_poll`, a capped-out object must be retried on later polls (progressively acquired), or a dense scene under-populates belief. Supporting both required two independent state sets (`_previously_visible_ids` for on_change debounce; `_acquired_ids` for every_poll progressive acquisition), not a re-read of one variable. Lesson: when a feature flag changes core state semantics, verify whether a single variable can represent both modes or if the divergence requires architectural split — this is not always obvious at design time (PB-2 Stage 3 implementation note).

- **Certainty as pure recency is a documented placeholder, not a defect.** PB-2 Stage 2 built `certainty_of(contact, now_sim)` as a pure function of elapsed time (`now_sim - contact.last_seen_sim`) with no reference to observation quality, uncertainty radius, or source. Later, PB-2 Stage 5 observed that a wide-uncertainty observation can restore certainty over a tighter earlier one, purely because it was newer. The plan and review both flagged this as documented placeholder behavior (all stages deliberately skip quality weighting), and Stage 5 added a backlog item capturing the pattern for future stages to be aware. Lesson: when building a placeholder design that works but has known limitations, document it loudly both in code comments and in backlog items, so future maintainers see it as "a design choice we know about" rather than "a bug nobody noticed." This prevents silent re-litigating (PB-2 Stage 5 finding).

- **A correct answer to a narrow question can be recorded as the answer to a broader one, and nothing in the chain looks careless.** An investigator pass asked "is unit velocity available from `LoGetWorldObjects`?" and answered it rigorously — a full `pairs()` enumeration of the raw table, listing a dozen fields this project never requests, so no synonym could have hidden. The finding was then written down, and relayed to the user, as *"confirmed, no velocity under any name"* — a fact about one call presented as a fact about DCS. `Object.getVelocity()` exists in the *Mission Scripting* environment and returns a vec3 for every unit, which is how Tacview records speed for everything on the map. The evidence was primary, the method sound, the conclusion overreached; what failed was that the **scope of the question was never re-examined once the answer was in hand**. The user caught it with a working counterexample — "Tacview does get speed, I find it hard to believe it would not be exported somehow" — which is the cheap general check: **when a negative finding says a capability does not exist, ask whether anything in the wild already does it.** A negative result from searching one surface only ever bounds that surface. Related: the same session's `apparent_extent_m` trig claim, checked only at the two angles where its error cancels (below) — both are cases where the *test* was sound and its *coverage* was the thing nobody questioned (2026-09-21, `aircraft-layer/research/2026-09-21-unit-velocity-via-mission-scripting.md`).

- **Live experimentation can completely invalidate an architecture before implementation starts — plan a cheap spike when DCS internals are undocumented.** PB-1's original plan drafted two mutually-exclusive concrete `PerceptionSource` tiers (real HelperAI-based feed vs. ground-truth proxy heuristic), branching on which DCS channel exposed native geometry. Session 4's four-hour live spike against the installed DCS instance discovered that *neither* channel exposed usable geometry (four candidate sources confirmed dead: ASP-17 `list_indication(2)`, sight params `get_param_handle`, `LoGetTargetInformation`, `LoGetLockedTargetInformation`), making both tiers unbuildable as originally conceived. The architecture then pivoted to a single hybrid implementation (HelperAI text gate + `LoGetWorldObjects` geometry via association), eliminating the branch entirely. No amount of desk research (forum threads, Hoggit wiki, reference manuals) could have predicted this outcome. Lesson: when a plan's core branch depends on undocumented DCS internals that resist off-instance investigation, schedule a cheap 2–4 hour live probe *before* committing to multi-branch architecture. A spike that falsifies a design is far cheaper than discovering it mid-implementation (PB-1 sessions 1–4).

- **PYTHONPATH and venv issues only surface in live end-to-end deployment, not in fixture-only testing.** PB-1's aircraft-layer and body-layer code passed all local unit tests and type checks, but the live acceptance test (stage 7) revealed two production issues: (1) neither `src/` directory is an installed package, so `PYTHONPATH=src` is not optional but mandatory, and (2) body-layer requires `body-layer/.venv`'s Python interpreter specifically (not system `python`), because the world-model seam pulls in `pyproj`, which is only installed in that subproject's venv. These issues were invisible to tests mocking network I/O and using installed-package conventions. Lesson: for any feature with venv dependencies or multi-subproject seams, add a live end-to-end deployment step (even if brief: run the real pipeline against real DCS for 10 minutes) to the acceptance criteria early, and document PYTHONPATH/venv requirements in workflow docs immediately after discovery (PB-1 stage 7 finding, fixed in `body-layer/CLAUDE.md` commit `fb32fc3`).

- **Ambiguous-scene live testing reveals association bugs that fixture-only testing cannot.** PB-1's plan specified "ideally with ... a second, similar decoy target nearby to exercise the ambiguous-match path live, not just in fixtures." This was intended as an optional refinement. Stage 7's live flight incidentally placed four similar Ural trucks clustered near each other, all populated in Petrovich's cockpit target list simultaneously — creating exactly the ambiguous-association scenario (multiple high-scoring candidates at tied confidence). This revealed that fixture-based testing of the association algorithm, while necessary, is insufficient validation: synthetic hand-authored candidates do not expose the proximity effects, rapid target-switching patterns, and pool-size variations that real multi-object scenes produce. Future perception/association work should treat live multi-object scenes as a mandatory validation step, not a "nice-to-have" verification (PB-1 implementation log, stage 7).

- **Reasonable interpretation choices in implementation should be documented explicitly when reviewed, to avoid second-guessing later.** PB-1's plan said "exact debounce window ... is an implementation detail, not architectural." The implementer chose "emit on any change from the last-emitted text, and treat a momentary empty/no-detection poll as clearing that memory" — the right choice (so a detection disappearing and reappearing with identical text still re-emits), but not the *only* reasonable interpretation. An alternative (emit only on text change, but *do not* reset debounce on empty) would have kept the last text in memory indefinitely. The chosen approach (reset-on-empty) was sound and matches the natural mental model of "detection went away, so the next one is new," but should have been explicitly flagged in the Reviewer's comments as "a judgment call, not a plan requirement." Lesson: when implementation interprets an underspecified plan detail reasonably, document that interpretation in the Reviewer's findings so future maintainers don't re-litigate it (PB-1 Reviewer optional-refinements section, item 1).

- **Reading a module's actual source code resolves DCS-internals questions faster than forum research.** PB-1.5 plan relied on four sessions of forum searching to establish what DCS's ambient detection outputs looked like. Session 5 of the investigator phase gained direct access to the installed DCS and read `HelperAI_lengths_ng.lua` (the speech-fragment bank) and `HelperAI.lua` (the detection constants) in plaintext Lua. Two hours of source-code reading answered definitively what four sessions of forum research could not: the exact vocabulary ED uses for contact callouts, the published detection constants (angular-radius tiers, scan radius), and confirmed that no exportable ambient-detection signal exists. Lesson: for undocumented DCS features, prioritize local Lua-file inspection over community sources; the Lua source is public in the installed DCS and often answers questions more reliably than folklore (PB-1.5 Investigator sessions 1–5).

- **Namespace mismatches in keyword-matching code are a defect class distinct from incomplete coverage.** PB-1.5's `object_model.py` had `OP_SHIP` keywords (`cruiser`, `frigate`, `corvette`, `destroyer`, `boat`, `ship`) that looked reasonable but were completely unreachable: `LoGetWorldObjects` emits DCS *type* names (`MOSCOW`, `leander-gun-achilles`, `CastleClass_01`), not English hull-class descriptors. This was masked by tests using fabricated strings like `"Grisha corvette"` (not a real DCS type) that passed by construction. Real data validation (auditing against all 595 actual DCS types) revealed the domain-mismatch bug. Follow-on work found two more: `"tank"` matching non-armored types (fuel truck, tanker aircraft), and a substring-categorization script matching `"a-6"` inside `"SA-6"`. All three were invisible to "the table is thin" reasoning — they are defects (wrong assumptions about data format), not just coverage gaps. Lesson: when validating keyword-match tables against real data, audit the *domain assumptions* (what format does `object_type` actually have?) before counting hits; a thin-but-correct table is acceptable, but a thick-but-wrong one is dangerous. Tests with fabricated fixtures that match the wrong vocabulary are worse than no test at all (PB-1.5 Review Pass 1 required fix and Pass 2 discovery).

- **Test fixtures that cannot fail independently are worse than no test.** PB-1.5's `test_coverage_floor_against_real_type_sample` had 100 ground-type entries that were hand-picked to already classify correctly, so `ground_coverage = (all 100 currently-pass) / 100 = 100%`. The coverage floor `_MIN_GROUND_COVERAGE_FRACTION = 0.9` was mathematically guaranteed to never trigger. A similar defect appeared earlier: `test_object_model.py::test_ship_keyword` asserted against `"Grisha corvette"`, a fabricated string that matched by construction. Both tests read as "regression guards" but could not actually fail if the underlying code broke — they are dead code dressed up as assertions. The Reviewer caught both only by inspecting fixture *contents*, never by reading the assertions. Lesson: when writing a test with a numerical floor or threshold, ensure the fixture includes realistic data *below* that threshold; when writing a test against a lookup table, spot-check the fixture against the actual domain vocabulary (not a fabricated/hand-convenient one). Fixture inspection is as critical as assertion inspection (PB-1.5 Pass 2 required fix and discovery).

- **The binocular-assumption reframing is load-bearing, not just a docstring nicety.** PB-1.5's plan derived its detection ranges from ED's published `HelperAI.lua` constants using a heuristic formula with unaddressed variables (contrast, fog, eyesight multiplier). The resulting ranges (truck ≈ 750 m bare, 3 km with a ×4 multiplier) were originally justified as "ED's own constant might apply here." User decision #6 reframed the ×4 as "the crew is using handheld binoculars, and we deliberately model that," making the range derivation this project's own modeling choice rather than a transcription of ED's formula. This reframing matters: if a future reader tries to "correct" the constants by re-deriving from an unaided-eye assumption, the whole model breaks silently. The docstring must state this plainly and warn against re-derivation — and it does, because the plan required it. Lesson: when a constant's meaning changes from "transcription of external data" to "this project's modeling choice," that decision must be wired into the code's documentation and architecture, not left as an optional clarification. A comment is insufficient; the module docstring must lead with it (PB-1.5 plan Decision #6, implemented and tested).

- **The synthetic filter is now the implementation, not a fallback.** PB-1.5's stage 7 live probe answered the open question: DCS's ambient contact callout emits no Lua-readable signal. The plan had accepted the visibility filter "for now," expecting to revisit it if a real signal was found. The probe result invalidates that expectation — there is no real signal to adopt. The synthetic filter (visibility.py's FOV + angular-radius + LOS composition) is the only implementation. This doesn't change architecture (the plan was already built this way), but it changes framing: the filter is not a workaround or a fallback, it is the product. This affects priority: the range/tier constants become product-critical for acceptance testing and tuning, not provisional. Lesson: treat a "for now" architectural assumption as a hypothesis to be tested, not as a permanent deferral. When a live probe closes the question definitively, update the priority and framing accordingly (PB-1.5 stage 7 research finding and backlog decision item on the user's direction to own perception end-to-end).

## Input Interface & Event Architecture (F10 crew commands)

- **CrewConsole's multi-input-source design correctly anticipated extensibility.** F10CommandQueue introduced the first bounded-FIFO event queue in aircraft-layer (previous caches were single-slot "latest" for continuous telemetry), implementing a second input surface via `handle_f10_command`. Both text input and F10 events route through the same `_print` funnel as `handle_line` and `drain_events`. The plan's second-order effect explicitly noted SRS input (BL-10) as a third future source — the architecture was already shaped to absorb it without rework. Lesson: anticipating input-source variety in the interface shape (multiple entry points → one output funnel) beats adding adapters later, and makes it possible to route all crew output (spoken or printed) through a unified delivery path (plans/f10-crew-commands/plan.md second-order effect, validated by implementation).

- **Discrete command event queues must use bounded FIFO, not latest-value cache.** Two F10 selections inside one poll interval would collapse into one with a single-slot cache, losing one user action silently. `F10CommandQueue.drain_all()` uses repeated `popleft()` rather than snapshot-then-clear, so a concurrent `push` from the receiver thread cannot be dropped between snapshot and clear. This distinguishes discrete commands from continuous telemetry: sensor readings (bearing, altitude, fuel) compress well into "latest value"; player actions (button presses, menu selections) lose information if queued as single-slot. Lesson: the cache pattern (FIFO vs. single-slot) depends on semantics, not just performance: events need queuing, observations need latest-value (plans/f10-crew-commands/plan.md decision 1, implementation note).

- **Wall-clock-only provenance is acceptable when DCS-derived model time requires unverified API.** F10 command timestamps come from receiver-thread wall-clock, not DCS sim-time — attaching model time would require `timer.getTime()` via mission-scripting state, unverified on the installed DCS version and not load-bearing for display/console-only features. Provenance is stated explicitly (no silent gaps), not fabricated. This established a reusable pattern: measure cost/benefit of exotic timing before accepting a new unverified API dependency; if the timing gain is marginal (display only, no critical gameplay loop), wall-clock is acceptable and stated plainly. Lesson: provenance completeness is not a binary property — accepting documented exceptions is better than fabricating unverified data (plans/f10-crew-commands/plan.md decision 1, risks and project invariant from docs/CONVENTIONS.md).

## Fixture Management & Test Infrastructure

- **Local world-model fixture `.sqlite`s have non-uniform schema/coverage — no single fixture is complete.** Two fixtures are available locally: (1) `latakia-20km.sqlite` (small, feature-rich, per M5) predates M7 Stage 2's `grid.provenance` schema bump and fails on any `describe_position` call with `sqlite3.OperationalError: no such column: provenance` — pre-existing gap, not a feature defect. (2) `syria-full.sqlite` (full theatre, post-M7) has current schema but incomplete feature layers: `airfield`/`named_place`/`navaid`/`road`/`runway` present, but `settlement`/`water`/`ridge`/`valley` missing (ingestion apparently never ran for full theatre). Testing that exercises all feature kinds currently requires fakes or a newly-built schema-current regional fixture. Future fixture work should target a complete build: either rebuild `latakia-20km.sqlite` with current M7+ schema, or run missing ingestion stages against `syria-full.sqlite` (BL-3 implementation note).

## DCS Visualization & UI Integration

- **Grounding a design in authoritative source values does not guarantee visual acceptance.** BL-2.5's refinement pass restyled the overlay window based on exhaustively verified values from DCS's real `Scripts/UI/gameMessages.dlg`: headerHeight=0 (enabling transparent chrome), position offsets computed to ±5px of the native message panel, per-line text colors/font/shadows byte-identical to the shipped file. Reviewer independently verified every claim against the real installed files. Yet the user flew the restyled overlay in a confirmation sortie and rejected it — it read worse in the cockpit than the original titled window despite being entirely grounded in authoritative reference values. Lesson: static verification of design grounding is necessary but not sufficient for visual acceptance. Live experimental validation (a short 5-minute sortie showing the restyled result in situ) must precede design commitment, especially when "better fidelity to real DCS UI" is the justification. A design that is factually correct can still be perceptually wrong (BL-2.5 DoD finding).

- **Bundling cosmetic and correctness changes in a single commit creates lossy reversion. Revert the whole commit and lose both.** BL-2.5's refinement pass combined three tasks — restyle (cosmetic), contact id (correctness fix), clipped-line sizing (correctness fix) — into two commits: `f8cca80` (contact id only), `499811b` (restyle + clipped-line sizing). When the user rejected the restyle, the whole-commit revert at `99c2586` removed the clipping fix that was bundled with it, reverting the clipped-line defect from "fixed" back to "open." The contact-id fix survived because it was in a separate commit. Lesson: separate commits by concern — one commit per acceptance criterion, or one per review gate trigger, not one per feature branch. A later revert of one concern should not collateral-damage unrelated fixes. This pattern already appears in PB-1/BL-2 practice (commit-per-stage), and BL-2.5 is a reminder that bundling is a loss of auditability and reversibility, not a time-save (BL-2.5 refinement lesson).

## Classification & Fusion (BL-2.6)

- **Spatial-gate radius must budget both the incoming percept's uncertainty AND the stored contact's position uncertainty symmetrically.** BL-2.6's live acceptance testing revealed that a single missed match (gate failure) from under-sized radius spawned a duplicate contact, and because that duplicate then counted as a second candidate for every subsequent percept near the same real object, the ambiguity-rule ("2+ candidates → new contact, never a merge") turned one transient miss into a permanent one-new-contact-per-poll runaway for the rest of the contact's session. Root cause: `association_over_time.spatial_gate_radius_m` budgeted only the incoming percept's uncertainty, treating the stored `last_position` as exact. It is not — that position was itself only known to within *its own* founding/most-recent percept's uncertainty. For naked-eye in particular, bucket-requantisation (clock-position anchors rotate with heading each poll) can implya fresh position a full bucket-width away from the previous reading. The fix: sum `uncertainty_radius_m(percept) + contact.last_position_uncertainty_m` before adding the elapsed-time growth term. This restores the symmetric two-sided error budget (both estimates carry error, not just the newer one) that radar-fusion theory prescribes. Lesson: when gating across time on position, store and use the uncertainty of *both* the held position and the incoming measurement, not one-sided (BL-2.6 debug session, fix verified live after re-flight).

- **Classification fusion's `hold` (lower-level rejected, held claim survives) is the fix for last-writer-wins oscillation.** Before BL-2.6, every new percept overwrote the contact's classification, so a contact could oscillate `OP_ARMORED` ↔ `T-72` ↔ `OP_ARMORED` poll-to-poll whenever two channels disagreed or observation quality varied. BL-2.6's fold rule replaces this with: higher level + consistent parent → refine; same level + same value → reinforce; **lower level → hold**; incompatible → collapse + lockout. The `hold` branch is critical: when the contact currently knows `T-72` and a coarser-observation updates with `OP_ARMORED`, the finer claim is simply not changed — a crew member who identified a T-72 does not forget it the moment he sees it at a distance. Refinement is monotone non-decreasing in specificity except on contradiction; confidence can decay, but level does not. Lesson: in any multi-source fusion system where sources have different quality/specificity, reject lower-level claims rather than overwriting — it prevents oscillation and models the real human behavior of accumulating confidence, not forgetting (BL-2.6 plan design section, live validated by user during Stage 10 docs review).

- **Classification identity confidence should decay from `established_sim` (last confirmation), not `last_seen_sim` (last observation time).** BL-2.6 Stage 11 implemented `classification_confidence_at(contact, now_sim)`, decaying `contact.classification.confidence` from `contact.classification.established_sim` (when the classification claim was last confirmed via refine/reinforce/collapse). This differs from `certainty_of`, which decays from `contact.last_seen_sim` (when the contact was last observed at all, regardless of whether the classification changed). The distinction matters: if a contact's classification is confirmed and then the contact is held (a coarser re-observation, same classification level), `established_sim` stays frozen while `last_seen_sim` keeps advancing — so confidence decays from the frozen date, not from the stale hold. This models "I confirmed he was a T-72 two minutes ago; I don't need to re-confirm every time I see him at a distance" rather than "his identity expires because I haven't looked at him recently." Lesson: for multi-attribute decay, distinguish between "last time this attribute was confirmed" and "last time the contact was perceived at all"; a hold is not a confirmation (BL-2.6 implementation log Stage 11, decay.py docstring).

- **Tier→specificity mapping is this project's own modeling choice, not a verified transcription of ED's internals.** BL-2.6 plan's investigator (Q1, Session 6 addendum) searched `HelperAI.lua` and four engine DLLs for any code that *consumes* the four `min_angular_radius` tiers (existence / class / class / IFF), finding zero references outside the table's own definition. This means the tier→specificity semantics ("`lowres` means presence-only, `medres` means class, `hires` means specific type") are *this project's own inference from naming* and *not* ED's documented or verifiable behavior. Yet they are now wired into `perception/visibility.py` as the production tier constants. The fix: the module docstring states plainly that this mapping is "this project's own derivation from ED's published constants, not a verified reproduction of ED's actual formula," and warns future readers not to "correct" it toward an ED semantics that was never established. This exact disclaimer pattern was already proven by PB-1.5's binocular-multiplier reframing. Lesson: when a constant's meaning or derivation cannot be independently verified against its source, document that limitation explicitly so a future reader does not silently treat it as ground truth and "correct" it based on folklore (BL-2.6 plan Investigator findings, Risk section, confirmed in body-layer/CLAUDE.md Visibility entry).

- **Moving a gating-tier threshold can change which constraint binds the maximum range for different object sizes.** BL-2.6 Stage 7 moved `NAKED_EYE_GATING_ANGULAR_RADIUS_RAD` from `MEDRES_ANGULAR_RADIUS_RAD` (0.008 rad) to `LOWRES_ANGULAR_RADIUS_RAD` (0.0043 rad) — a one-line constant change. For a truck-sized object (6m), the medres gate produced a threshold of 3km, which stayed below the range cap (5000m). Under the lowres gate, the same truck's theoretical threshold became 5.6km, but the cap binds first, dropping the practical threshold to 5km. This changed which physical constraint limits the range: the size curve vs. the cap. The consequence is relevant: cargo cap-bound objects have a "flattened size curve" where targets of different sizes all hit the same cap rather than being differentiated by size. Lesson: when tuning a range threshold, verify empirically which constraint (the formula's size-curve outcome vs. an independent cap) actually binds for different object classes; a change that looks like a one-line tweak can silently flip which limit is load-bearing for certain target types (BL-2.6 implementation log, Stage 7 notable discoveries).

- **User decision to allow naked-eye type-level output at hires range departed from architect recommendation, and now must stay stable.** BL-2.6's plan originally recommended capping naked-eye at class level (medres), mirroring ED's own ambient-callout vocabulary ceiling. User decision #1 (2026-09-09) chose to allow type-level (hires) output via `reporting_names.reporting_name_for(object_type)` — ground-truth reporting names at close range, not vocabulary-matched descriptions. This was an explicit override of the architect's recommendation. It now means "Petrovich can never mis-identify, only fail to identify" applies to naked-eye's hires tier too, matching the scope channel's own invariant. A future decision to revert naked-eye to class-only would break that symmetry and require careful re-review of downstream fusion logic. Lesson: document when user decision overrides architectural recommendation and explain the consequences (loss/gain of symmetry, new failure modes, etc.); this guides future maintainers on whether a decision is revisable or has become a design pillar (BL-2.6 plan Decisions section, live user input 2026-09-09).

- **sqlite3.Connection is thread-affine; a resource held in a shared data structure (ConsolePerceptionRunner) risks cross-thread reuse if read from a different thread.** BL-5 live acceptance testing triggered a `sqlite3.ProgrammingError` when the REPL thread tried to run a query against a connection created on the poll thread. BL-3 had added `ConsolePerceptionRunner.enrichment` (an `EnrichmentContext` holding a connection), and BL-5's enrichment-aware console commands read it directly from the REPL thread. The fix mirrored Stage 6's own precedent: each thread that needs to query the world model must open its own connection on that thread. Any future field added to `ConsolePerceptionRunner` that holds a sqlite3.Connection (or any other thread-affine resource) must be opened on the thread that uses it, never shared. Lesson: sqlite3 thread affinity is a recurring defect class in this codebase's polling/REPL threading architecture — flag it explicitly during review of any field addition to multi-threaded data structures (BL-5 bug fix, 2026-09-10).

- **Spatial-gate tuning can reopen a different failure mode at the opposite end; verify changes against both.** BL-2.6's symmetric-gate fix (budgeting both the incoming percept's uncertainty AND the stored contact's position uncertainty, per radar-fusion symmetry) widened the gate to prevent false-negatives (missed matches on stationary objects). Within 48 hours of user acceptance testing, a new failure mode appeared: two distinct, moderately-separated real objects (874m apart, at typical 1200m range) now had overlapping gates, triggering the "two-or-more candidates → always new contact" ambiguity rule repeatedly, spawning one contact per poll (false-positive runaway from what should have been separate tracks). Root cause was not a regression — the symmetric fix was correct — but a previously-masked trade-off: gate width trades off against candidate-pool density. Widening to fix single-object misses worsens multi-object false-positives under certain geometries. Solution: object-permanence correlation (recognizing re-observations of the same real object via persistent object-id maps) as the primary path, reducing gate re-exercise to exceptional cases. Lesson: spatial-association tuning is inherently multi-objective (false-negative sensitivity vs. false-positive false-merge risk); changes that fix one failure mode must be validated against the opposite mode via live multi-object geometry before accepting as complete (BL-2.6→contact-duplication-ambiguity-runaway fix chain, 2026-09-09/10).

## Mission Phase & Relevance (BL-7)

- **Relevance as a tie-breaker within tiers, never across tiers, preserves deterministic ranking.** BL-7 adds mission-phase proximity (distance to the active phase's route waypoint) to `_highest_attention_contact`, but only as a secondary sort within each attention tier (priority > watch > visible, then by phase proximity, then by recency). This prevents phase relevance from ever overriding the player's direct attention marks (`set_attention` / `watch_area`), which are the only ranking signal the player directly controls. The architectural lesson: when adding a second relevance dimension (phase proximity) alongside an existing, player-controlled one (attention tier), keep them orthogonal — the new dimension refines tie-breaks within the old hierarchy, not across it. This pattern generalizes: any future relevance metric should respect the tier hierarchy rather than trying to create a unified "best target" score (BL-7 plan decision, validated in implementation).

- **Cross-subproject file-based artifact consumption (not import) is the pattern for offline results from other layers.** BL-7 consumes Mission Interpreter's MI-6 `--emit-compact` JSON output via a plain file read + JSON parse, not a Python `import` across subproject boundaries. This breaks the body-layer ↔ world-model in-process-import rule without violating the "module independence" principle: mission-interpreter is not an exception (unlike world-model, which body-layer imports directly), so the boundary is a file I/O interface, not a shared Python package. The pattern: offline results from independent subprojects are consumed as files/JSON/HTTP, not imports. This keeps subproject lifecycles independent (mission-interpreter can be rebuilt/rerun without reimporting code) while still allowing downstream consumption (BL-7 implementation choice, mirrors "no world-model import" philosophy from root CLAUDE.md).

- **Monotonic state machines handling position uncertainty: require explicit capture radius to suppress jitter.** BL-7's `MissionPhaseTracker` advances `last_reached_waypoint_index` only when ownship position falls within `WAYPOINT_CAPTURE_RADIUS_M` of a waypoint, and never decrements even if ownship drifts back outside. This prevents the tracker from oscillating `reached ↔ unreached` on the same waypoint due to GPS jitter or position-update irregularity. The constant (`WAYPOINT_CAPTURE_RADIUS_M = 3000m`, uncalibrated placeholder) is not derived from data but chosen as a "large enough hysteresis zone." Lesson: any monotonic state machine (first-time triggers, phase transitions, critical-range crossings) that must handle continuous noisy observations needs an explicit capture/threshold constant, documented as a placeholder pending live calibration. Do not try to infer the right threshold from plan/data alone — live flight will show what works (BL-7 plan Risks section, implementation validated by fixture tests but live calibration deferred).

## Perception Calibration & Measurement

- **"Well-observed" does not mean "triangulated" — crossing-bearing fusion does not reliably tighten bearing uncertainty the way same-bearing repetition does.** With 2x2-covariance position fusion, repeated looks from *roughly the same* relative bearing preserve a favourable down-range-heavy anisotropy while shrinking toward the systematic-bias floor, and reliably collapse `bearing_uncertainty_deg` to a single sweep step. Looks fused from *crossing* bearings — real triangulation, which shrinks the overall covariance radius the most — smear the tightened covariance's orientation away from any one observer's own cross-range axis, so a query against it can read *worse* along one particular axis than a single, luckily-aligned look would; it does not reliably reach single-step even fully converged. The two scenarios respond differently to the same tuning constants (`LOOK_SWEEP_SIGMA`, `SYSTEMATIC_BIAS_FRACTION`), so "the contact has been seen a lot" is not by itself a predictor of how tight the optic sweep gets — the geometry of *how* it was seen matters as much as how often (precise-position-belief implementation, Stage 5 discovery, verified numerically before the test was written).

- **A mechanical Stage-1 declaration (an uncertainty field) and the Stage-2 behaviour it describes (actually perturbing the number) can ship independently, and only one of them is visible in a diff review that trusts the field's presence.** `perception/hybrid_source.py` got `PositionUncertainty(300, 300)` in Stage 1 but never got Stage 2's `perturbed_bearing_range` call — the channel kept handing belief truth-exact geometry behind a cosmetic band, on the channel the pilot actually flies with, and the plan's own explicit decision point about whether to extend the treatment there was never recorded as answered by either implementer. Caught only because Reviewer traced the call site rather than trusting the presence of the uncertainty field as proof the channel had been perturbed. When an error-model milestone touches multiple emission channels, verify each one calls the perturbation function, not just that each declares an uncertainty struct (precise-position-belief review, required fix).

- **Screenshot angle derivation requires attitude correction from airframe boresight.** When calibrating a body-relative perception mask by reading angles off cockpit screenshots, the visible horizon in the image sits offset from the airframe's boresight by the aircraft's pitch angle. Calibration protocol: measure angles relative to image center (boresight) where possible; where only the horizon is usable as reference, subtract the assumed pitch at capture time to recover boresight-relative angles. Document the assumed pitch alongside the derived table, so future re-derivations from captures at a different attitude can correct consistently rather than inheriting this one's attitude error. Failure to apply this correction produces a systematic offset in every derived breakpoint (cockpit-visibility, plan D7).

## OSM Multipolygon Assembly & Simplification (M9)

- **libosmium strips a relation's own `type` tag from the assembled area's tags.** An area assembled from a `type=multipolygon, landuse=forest` relation reports `tags == {"landuse": "forest"}` — the `type` key is missing entirely. The relation's own `type` tag gates *whether* area assembly happens (omitting `type="multipolygon"` produces zero areas), but it does not survive the assembled ring's tags. Any code consuming `OsmArea.tags` must never check for `type=multipolygon` on the area itself; the tag is present at relation-parsing time only, and is gone by the time multipolygon assembly completes (M9 Stage 1 discovery during fixture work).

- **Independent simplification of paired rings (outer + holes) can create invalid pairings; post-simplification validation is required.** Douglas-Peucker simplification is applied independently to the outer ring and each hole at a 30 m tolerance. Both can lose vertices independently, so a hole that was contained in the unsimplified outer can end up partially outside the simplified outer — a structural polygon defect. The fix: after simplifying both rings, verify every hole vertex still falls inside the simplified outer ring via `point_in_polygon` check; drop holes that fail this check and count them as `holes_dropped_not_contained_after_simplify`. This validation must happen at ingest time, not query time — readers (`store/reader.py`'s `polygon_contains`/`_distance_to_feature`) trust `inner_rings` to be well-formed and have no way to detect invalid pairings (M9 osm-landcover-optimization re-review required fix, commit 638239a).

- **OSM classifier cache invalidation strategy: full rebuild on version bump, with loud failure on stale cache.** The OSM classified-feature cache (`data/world-model/<region>-osm-cache.sqlite`) stores `OsmIngestStats` as JSON and reconstructs it via `OsmIngestStats(**json.loads(row[0]))`. A version-1 cache with an old stats shape (missing new fields, or removed fields that the new code doesn't recognize) will fail loudly — the dataclass `__init__` raises `TypeError` on unexpected keyword arguments. This is intentional: partial-cache reuse is not attempted; any classifier-version bump invalidates the entire cache, forcing a full re-parse. The cache-hit cost is negligible next to the parse cost (~9–10 s for a 20 km region), and the failure mode (loud crash vs. silent stale data) is the right choice (M9 osm-landcover-optimization implementation, cache validation tested).

- **Storing multipolygon holes as a derived JSON tag preserves schema stability across cache-invalidation boundaries.** Rather than adding a new `inner_rings` geometry column (which would bump `store.schema.SCHEMA_VERSION` and orphan all existing M8 probe-store pairings, since each probe store pins its base store's schema version), holes are stored as `tags["inner_rings"]`, a reserved derived tag alongside existing precedent (`junction.connecting_road_ids`, `terrain.elevation_range_m`). This keeps the base schema at version 3 (unchanged), so existing probe-store pairings remain valid across this milestone. The trade-off: hole rings must be JSON-parsed at query time rather than loaded from a dedicated column, a small price next to the M9 stage's overall parse-time reduction (6.5 s → cache-hit cascades at 0.07 s per repeat run). Pattern: when storing derived relational data from a source that may change (OSM geometry rules, classifier rules), prefer a reserved JSON-tag convention over schema extension, keeping the base schema stable (M9 osm-landcover-optimization plan Design Decision 2, validated in implementation).

## Spatial Gating & Clustering (Group Contact Model, Stages 1–2)

- **Two different radii in the same pipeline serving different purposes create a structural dead zone.** Group-contact cardinality (BL-x) introduces clustering (single-sided max-radius test for resolving power) upstream of the belief spatial gate (double-sided sum-radius test for temporal smoothing). At 690m with 205m cluster radius and 410m gate radius, a split whose children sit near the cluster boundary is re-absorbed by the gate — a common case, not edge — because `sum(uncertainty_a, uncertainty_b) ≥ max(uncertainty_a, uncertainty_b)` for any positive radii. The two radii serve different purposes (channel resolution vs. temporal coherence), so the divergence is not a bug; the mistake is applying the symmetric gate to a split-child percept that carries explicit cluster identity. Stage 3 must decide gate treatment: exempting freshly-split children, or making the gate single-sided when cluster identity says "this is not that." Document both radii and why they serve different purposes when designing multi-stage spatial pipelines — the asymmetry (single vs. sum) is legitimate tuning, not a sign of error (group-contact-model plan review finding, commit 3f6b1b2).

- **F10-label-sourced object_type values fail object_model.profile_for resolution when labels diverge from raw DCS type spellings.** Several units in the vision-calibration dataset (T-62, BMD1, AK-74/AK) are labeled via F10-map display names, not verified LoGetWorldObjects raw type strings. These fail `profile_for` lookup: `"T-62"` matches raw-table key `"T-62M"` (with M variant), `"BMD1"` (no hyphen) matches raw key `"BMD-1"` (hyphenated), and small-arms `"AK-74"`/`"AK"` have no match in the reporting-name-keyed second pass. The SA-10/SA-15/HL B8M1 cluster has a pre-existing gap (no keyword table entries at all, falling back to `DEFAULT_SIZE_M=5.0`). When F10 labels are the only available source, the workaround is to record ground-truth `size_m` independently in calibration fixtures rather than relying on `profile_for` — the fixture becomes the durable truth, not the lookup table. This decouples measurement integrity from the fragility of label-to-type matching. Future callers that use F10-labeled objects should follow this pattern: store independent sizes, treat `profile_for` as a cross-check, not the source (vision-range-calibration Pass 1 implementation note and `body-layer/research/2026-09-17-vision-range-calibration.md` object_type provenance section).

- **Calibration dataset design for non-breaking extension: store observed ground-truth directly, not inferred values.** The vision_calibration.json fixture captures each observation's objects, grades (per optic), source images, and conditions, with `size_m` recorded as independently-known real-world size (e.g., `"T-62": 7.0 m`), not looked up from `object_model.profile_for`. This choice was driven by the F10-label fragility noted above, but generalizes: storing what was directly observed (the fixture data) separately from what can be inferred or looked up (profile sizes, classification tiers) keeps the fixture extensible and the measurement chain auditable. New rows (closer range, different theatre, other optics) drop in without format change; the fixture shape is stable across future passes and data sources (vision-range-calibration Pass 1 plan Fixture format section, implementation preserved this pattern).

## Solve the problem in its natural coordinate space

Two full implement-review cycles were spent on a world-space model of a question that is purely
angular. The naked-eye channel's position uncertainty was first a scalar radius, then an anisotropic
ellipse (cross-range acuity, down-range bucket width) — both approximations of "what angle do these
two things subtend at the observer". Stating it directly in angular terms **deleted 144 net lines**
and removed a tuned constant, because the anisotropy then falls out of the geometry: an airborne
observer separates a down-range pair by *depression angle*, which no world-space radius can express
without being told to.

Two tells that a model is in the wrong space, both present here and both visible before the rework:

- **A term whose justification keeps getting replaced.** The down-range radius was first "reporting
  quantisation", then "depth perception is poor at range". A term that needs a new reason each time
  someone looks at it is usually standing in for something else.
- **Constants that cancel or turn out non-binding once restated.** In angular form the optic
  multiplier cancels out of the comparison entirely, and the acuity floor is provably non-binding
  for anything the channel detected at all. Both were load-bearing in world space and neither was
  real — and the second removed a planned calibration sortie's main purpose.

The correction came from the user's lived experience, not from analysis: *"two apples 20 cm apart at
50 cm are obviously two side by side, and may be one when one sits behind the other"*. Worth
pairing with `.claude/skills/explore/SKILL.md` — asking for the non-DCS analogue is what surfaced it.

## A design written against a stale test list produces phantom expectations

Stage 3b-i rev.2's design named a test as an xfail it expected to flip. The test did not exist: it
had been folded into another test by an earlier, unrelated commit. The design was not careless — it
was written against a test inventory that had already moved. When a plan specifies "test X should
now assert Y", confirm X exists at that moment rather than at the moment the surrounding reasoning
was formed.

## A component test can pass while the sentence it builds is wrong

Stage 4b composed a crew callout from two functions: `_cardinality_phrase` returned a quantity word,
and `_contact_report_text` joined it to a noun. Every unit test of the phrase passed —
`_cardinality_phrase(4, 5) == "a handful"` was correct in isolation. The composed sentence was
`"a handful trucks"`.

The defect existed **only** in the join, and nothing in the suite rendered the join and looked at
it. It surfaced the first time a human-facing tool printed whole callouts
(`body-layer/tools/speak_samples.py`), which was written for a different purpose entirely — to let
the user *hear* phrasing without needing DCS.

Two things worth carrying:

- **Where output is assembled from parts, assert on the assembled output**, not only on the parts.
  The parts were each correct; correctness did not compose. Grammar is a property of the sentence,
  so it cannot be tested anywhere else.
- **A tool built for a human to judge something subjective will also catch objective defects**, for
  free, because it is the first thing that looks at the real end product. That is an argument for
  building such tools earlier than they feel necessary.

The fix put the connector inside the phrase (`"a handful of"`), so the join stays a plain
phrase-plus-noun concatenation and the grammar lives in one place rather than being split across
two functions that must agree (2026-09-19).

## Optics/Calibration

- **A plausible physical argument for a constant is not evidence — check it against the
  photographic ground truth before committing.** `BINOCULAR_RANGE_MULTIPLIER` was raised from 4.0 to
  an "honest" 8.0 (a real 8x30 instrument, no derating) on physical reasoning that sounded more
  rigorous than the inherited, unexamined 4.0. Running it against `test_vision_calibration.py`'s
  9-range photographic ladder refuted it within one commit — four cases computed `hires` where the
  screenshots show `medres`. The eventual correct value (4.0, independently re-derived as 6x glass ×
  a ~0.67 unstabilised-platform penalty) happened to match the number it replaced, but only checking
  against the fixture revealed that the *physically cleaner-sounding* number was wrong. A fixture
  built for regression calibration doubles as a fast falsifier for a new hypothesis — run it before
  trusting the arithmetic, not after (detection-cones-slice1, 2026-09-20).

- **When a scope cut removes a feature, audit for dataclass fields that would hold the same
  placeholder value on every remaining instance — those are untestable by construction and should
  go too, not just the feature's own code.** Cutting the 9K113 sight from `Optic` also required
  cutting its four field-of-regard fields: with no sighted optic left in the table, every remaining
  instance would carry `None` on all four, so no test could ever exercise the restricting branch.
  The rule that emerged: carry a mechanism only as long as at least one real instance exercises its
  non-trivial branch (the FOV *field* stayed, because `BINOCULAR_OPTIC` got a real non-`None` value
  even without a live caller yet) — data nothing can ever read given the current instance set should
  be deferred with the feature that would have populated it, not left behind as inert scaffolding
  (detection-cones-slice1, 2026-09-20).

- **Rescaling a geometry test fixture under a changed range threshold is not a linear operation.**
  Shrinking a fixture's candidate ranges to fit a shorter detection ceiling, without also rescaling
  whatever fixed offset defines the angular separation between candidates (a cross-range offset, an
  AGL altitude difference), silently breaks the merge/split boundary the fixture exists to test:
  apparent angular size (`size_m / range_m`) is not scale-invariant even though the bearing angle
  between two uniformly-scaled points is. The fix re-derived the fixtures by iterating scale factors
  through the real clustering/pipeline functions until the required merge/split outcomes reproduced,
  rather than trusting a flat distance rescale (detection-cones-slice1, 2026-09-20).

- **A slackness proof "verified benign" against today's constants can have an unstated premise that
  later constants violate — record the premise, not just the verdict.** Slice 1 flagged
  `clustering.py`'s `_separable` floor (A), which hardcodes a range-multiplier constant, as benign
  twice. The proof was sound but incomplete: it holds only while the active optic's
  `presence_range_mult ≤ 4.0`, true of every multiplier in the table at the time. Slice 2A's
  per-tier multipliers introduced 5.81 (9K113 narrow), which breaks it — two genuinely separable
  contacts would silently merge. "Verified benign" in a prior review reads as a settled fact to a
  later reader; a proof is only as durable as its premise, and an unstated premise is invisible
  until something violates it. When a review verifies an invariant algebraically, write down the
  inequality it depends on, not just the conclusion — that turns the next constant change into a
  one-line check instead of a rediscovery (detection-cones-slice1 review, slice2A fix, 2026-09-21).

- **A plan can hold both halves of a contradiction and still read as consistent, because nothing
  ever puts the two numbers side by side.** Slice 2's plan stated, in two different sections, that
  2B's default gaze is `FULL_GAZE` at ±90° (a coarse-sector diagram figure) and separately that the
  cockpit mask's real rear cutoff is ±130° (a live measurement) — each sentence correct on its own,
  each written by someone reasoning locally, neither writer cross-checking against the other's
  number. Had the ±90° default shipped, it would have silently narrowed live detection through the
  90°–130° band, the exact regression 2B's acceptance gate exists to rule out (caught by the
  implementer during 2B, corrected in `e520e8b`). Same shape as the `_separable` slackness proof
  above: a fact stated once reads as settled, and staleness or contradiction only surfaces when
  something forces the two numbers into the same sentence. Worth checking for at plan-review time on
  any milestone that restates a numeric constant in more than one section (detection-cones-slice2,
  2B, 2026-09-21).

- **When several measured effects each look like they need their own tuning parameter, check
  whether one is a consequence of another before giving each a knob.** Slice 2's naked-eye
  multipliers were derived from the BTR-60 alone specifically because infantry's presence/class/type
  figures, run through the same arithmetic, produced *different* per-optic multipliers — which
  looked like a second, independent per-object-class calibration was needed. It wasn't: infantry's
  apparently-distinct multipliers are the distinctiveness clamp (`class = min(presence, ...)`) seen
  edge-on, not a third phenomenon. One per-class distinctiveness default plus the existing clamp
  reproduces all four measured infantry rows exactly, with no second multiplier table. The general
  form: before adding a parameter to explain a divergent measurement, check whether an *existing*
  mechanism, composed with the one already being built, already explains it (detection-cones-
  slice2, decisions doc + slice 2A implementation, 2026-09-21).

- **A trig "collapses back to the same constant" claim, checked only at 0°/90°, is exactly the
  proof-by-convenient-example that hides the bug at every other angle.** The aspect-aware-profiles
  plan's first draft gave every unmigrated profile a cubic fallback (`length_m = width_m = height_m
  = size_m`) and claimed `apparent_extent_m` returned the unchanged constant "at any aspect,"
  verified only at 0° and 90° — the two fixed points of `sin`/`cos` where the error cancels. At 45°
  the formula gives `s·√2`, a 41% increase. Caught before implementation by evaluating one oblique
  angle. Same shape as the `ACT_FLOOR` dimensionality mismatch above (a wrong constant, unnoticed
  because the check happened to land on the value's blind spot) — worth noting here too: the error
  would have *increased* detection range at a moment the model was already known to under-detect,
  so it would have read as the feature working, not as a bug. A wrong number that moves in the
  direction you're hoping for is the hardest kind to catch. Standing rule: any test of an angular/
  trig formula's "no-regression" claim must include a non-axis-aligned angle, not just the fixed
  points (aspect-aware-profiles plan and DoD, 2026-09-21).

- **A constant can be correctly valued and wrongly dimensioned — no amount of tuning the value
  fixes that.** `NAKED_EYE_MAX_NEW_PER_POLL = 3` was not a bad number; as an object-per-poll cap it
  matched a real reported constraint on Petrovich's attention. But it was counting the wrong thing —
  a dense ten-vehicle group and ten scattered singles cost the same 3-per-poll budget, so the group
  trickled in over three polls when a human takes it in as one glance. Slice 2A.5 fixed this by
  clustering *before* capping (cap groups, not objects) and left the value unchanged at 3, precisely
  so a later sortie could attribute any felt difference to the unit change alone. The general form:
  when a knob keeps producing the wrong-shaped behaviour across a range of values, check what it is
  a constant *of* before adjusting what it *equals* — the fix may be a dimension change, not a
  retune (detection-cones-slice2, 2A.5 plan and DoD, 2026-09-21).

- **A documented limitation is not the same as an examined one.** `naked_eye_source.py`'s own
  docstring had recorded, in plain language, that a capped-out object is never retried — the exact
  defect 2A.5 fixed. It sat there as an accepted scoping cut for multiple slices. What changed it
  from "known and accepted" to "a modelling error worth fixing" was not rereading the code but a
  user's perceptual observation (a dense group is *easier* to take in whole than a scattered one, so
  capping its members under-reports the case a human reports fastest) — an outside frame the
  docstring's author didn't have when writing it down. Writing a limitation down is necessary but not
  sufficient; it stays inert until something re-examines *why* it was accepted, and that re-framing
  is as likely to come from a domain observation as from more code-reading (detection-cones-slice2,
  2A.5 plan, 2026-09-21).

## Voice Recognition & Command Matching

- **Phrase scoring requires word-sequence matching, not character-sequence matching.** Early approach using whole-string character-level difflib (`SequenceMatcher` over the full normalized transcript) inflated scores for arbitrary speech with short-word overlap — "look at that" scored 0.727 against "scan_ahead", "watch out" scored 0.636 against "watch_nearest", both clearing action threshold under normal recognition confidence. Word-sequence scoring (SequenceMatcher over word lists, exact word matches score 1.0, character credit for equal-length "replace" opcodes only, divided by `max(len(heard), len(phrase))`) filters false positives while preserving real mishearings (e.g., "skin bearing 315" for "scan bearing 315"). This matters because fuzzy matching is a load-bearing defense in voice recognition against misheard words, and the right metric determines whether you catch mishearings or false-execute arbitrary speech (Inbound Speech Stage 2 review finding).

- **Seven fields required to distinguish three behavioural outcomes when command matcher returns `token=None`.** When a transcript fails to match any command token, body-layer must distinguish three distinct cases: (a) not a command attempt at all — fall through to the brain layer, (b) verb-anchored but no phrase matched — always prompt "Say again", (c) ambiguous match on best candidate — always prompt for confirmation. Two fields cannot encode three outcomes without fragile magnitude-based conventions (e.g., `match_ratio < -1` to encode ambiguity). Solution: explicit boolean fields `verb_anchored` and `ambiguous` in the transcript payload. This prevents future "maybe" outcomes being silently conflated with existing ones, and is why Decision 6's seam table (Inbound Speech plan) was updated from a three-field row to a seven-field row during Stage 2 implementation (Inbound Speech Stage 2 implementation discovery).

- **Gating floors must be compared against the quantity they were derived from, not a transformed version.** `ACT_FLOOR = 0.60` was derived from Stage 1's measured STT confidence distribution (correct answers: 0.60–0.95). An early implementation applied this floor to `confidence * match_ratio` — a product of two sub-1 quantities whose range is systematically lower than either input. Four real corpus clips put two commands in the confirm band despite having confidence values above 0.60, because the product (e.g., 0.78 * 0.83 = 0.65) was being compared against a floor measured on the confidence input (0.60) alone. The fix: `ACT_FLOOR` gates `confidence` directly; `match_ratio` stays in the wire signature for seam parity but does not gate. Lesson: when tuning a threshold floor, ensure the derivation (what distribution/scenario the number came from) matches the application (what quantity it gates). Off-by-one in dimensionality hides constant mistuning as "the implementation is wrong" when the constant itself is sound (Inbound Speech Decision 4 REVISED AGAIN, DoD 2026-09-20).

- **Interrupt-only responses require a separate communication path from speech output.** `stop_talking` initially rode the speech channel via `push_speech(..., urgent=True)` which worked end-to-end but produced "Copy." as a side effect — the interrupt was the delivery mechanism and speech was incidental. Removing the speech requires a separate interrupt-only path: `POST /audio/stop` → `AudioSink.interrupt()` → clear queue and stop in-flight playback, with zero speech output. This required explicit routing across all three subprojects (aircraft-layer new endpoint, audio-adapter new route, body-layer `stop()` call instead of `_print`). Lesson: when a feature requires "do X without any output," it is a separate semantic layer from "do X and speak about it"; design for interrupt-only paths explicitly rather than trying to compose them from the output channel (Inbound Speech Stage 3 follow-up, Decision 5 REVISED, 2026-09-20).

- **A structurally-complete trigger can still have near-zero practical value, and the arithmetic
  that shows it is cheap to run before shipping.** Watch-reporting's engagement-envelope warning is
  gated on believed classification (correct, no-omniscience-safe design), but doing the actual
  recognition-range-vs-weapon-range arithmetic for a SHORAD threat (the case it targets) showed the
  naked-eye/binocular optics available today only recognise the class at 13–47% of the way into a
  Shilka-class envelope — so the warning was going to fire from deep inside the danger zone, not at
  its edge, regardless of how correct the trigger logic was. The design was still worth shipping
  (accepted by the user with the caveat recorded), but the caveat only exists because someone ran
  the numbers instead of assuming "the trigger is correct" meant "the trigger is useful." Lesson:
  when a feature's value depends on a second, separately-tunable quantity (here: optic
  magnification), compute the actual margin against realistic inputs before or during design, not
  after a sortie reveals it — a few lines of arithmetic against already-known constants is far
  cheaper than a live-flight surprise (watch-reporting plan Decision 4d, 2026-09-24).

- **A plan's internal contradiction sits at the seam between sections, not inside one.** Twice in the detection-cones slice-2 series (2B, 2C), the literal wording of an Implementation Plan step said one thing while an earlier "hard part" section in the *same document* had already established the opposite: 2B's step 9 called `FULL_GAZE` a no-op while hard part 3 (and the real 130° cockpit envelope) made that false for the 90–130° band; 2C's step 12 read as a static commanded wedge while hard parts 1 and 2a required a commanded sector to itself sub-cycle. Both were caught only because the implementer cross-referenced sections rather than executing the literal step — a single-section read of either plan would have shipped the contradiction. Lesson: a plan review (self- or Reviewer-driven) should explicitly check the Implementation Plan's steps against the earlier discussion sections' own stated constraints, not just against CLAUDE.md invariants — the defect class this project keeps finding lives in that gap, not in either section read alone.

## Debugging & Root-Cause Diagnosis

- **A confident, code-derived reproduction can be a real defect on an unreachable path, while the
  user's own one-line diagnosis names the path that actually fires.** The `position-belief-runaway`
  debug session's own hypothesis (ill-conditioned triangulation — near-parallel disagreeing looks
  intersecting far outside either input) reproduced the reported numbers exactly, and was fixed.
  But the pre-existing association gate in `association_over_time.passes_gate` already rejects
  that large a single-poll disagreement before it ever reaches fusion in production — a fact
  established only by tracing `ContactStore.ingest`'s call path, not by the reproduction script
  itself. The mechanism that actually produced the live 87.5 km callout was a slow directional
  drift (many small, individually-plausible steps, each passing every existing gate), which is
  exactly what the user's own diagnosis named: *"position uncertainty needs a gate, cannot be
  further than detection range."* That one line pointed at a missing invariant (nothing checked a
  fused position against physical detection range at all), not at a numerically fragile formula.
  Lesson: when a live defect prompts a debugging session, a hypothesis that reproduces the
  reported numbers under direct construction is not yet shown to be the *production* path — trace
  whether the gates the real pipeline runs the input through would actually let that input reach
  the reproduced code, and weigh a domain expert's structural diagnosis ("there's no gate for X")
  as seriously as a numerically-confirmed mechanism (`position-belief-runaway` debug report +
  review, 2026-09-25).

## Model Selection & Local LLM Serving (brain-layer BR-1)

- **A smaller reasoning model can be slower than a larger one — reasoning-token count dominates
  latency, not parameter count.** Measured on the same prompt, warm: `qwen3:14b` answered in 16.0 s,
  `qwen3:4b` took 32.7 s — nearly twice as long from the *smaller* model, because `/no_think` does
  not reliably suppress `qwen3`'s reasoning trace and the reasoning trace itself is what costs the
  seconds, independent of model size. Lesson: for a latency-sensitive local-model pick, measure the
  actual wall time of the target model family under the target prompt shape before assuming smaller
  = faster; a reasoning-capable model's thinking budget can dominate parameter-count effects
  entirely (`plans/brain-layer/plan.md` Measurement 1, 2026-09-25).

- **A model recommendation based on "what's already on disk" is a different claim from "the current
  landscape was surveyed," and a reviewer without domain expertise can still catch the gap by
  knowing a release date.** The architect's original D6 pick (`qwen2.5:7b-instruct`) came from
  measuring two models that happened to already be pulled locally. The user's objection —
  "qwen2.5 is old, 2 years at this time... do investigation... first by web search" — was correct
  on a fact anyone could check (qwen2.5 released September 2024) without needing to know anything
  about model internals. The resulting search-first survey (`body-layer/research/
  2026-09-25-small-local-model-survey.md`) then vindicated the objection on the merits too: both
  replacement candidates (`qwen3:4b-instruct-2507-q4_K_M`, `granite4:micro`) matched or beat the
  incumbent's best behaviour at under a tenth of the latency and roughly half the disk footprint.
  Lesson: "measured what was on hand" and "surveyed what exists" are different claims, and a plan
  should say which one it's making — a recency check on a named model doesn't require domain
  expertise, only checking a release date (`plans/brain-layer/plan.md` D6 revision, 2026-09-25).

- **A plan's affected-files table naming a specific dependency is not itself a decision to use it.**
  The brain-layer plan's own affected-files table named FastAPI for `server.py` in one line, but no
  numbered Decision in the plan actually argued for that choice, and every other subproject in this
  repo declares `dependencies = []`. The implementer built on stdlib `http.server.
  ThreadingHTTPServer` instead — a structural copy of `audio-adapter/src/server.py`'s existing
  shape — and documented the refusal in `server.py`'s own docstring. Lesson: a table listing a
  dependency in passing does not carry the same weight as a reasoned Decision section, and per
  root `CLAUDE.md`/`AGENTS.md` a new third-party dependency is escalation-worthy on its own — an
  implementer should treat an unargued dependency mention as a candidate to challenge, not a
  commitment to honor (`plans/brain-layer/implementation.md`, 2026-09-25).

- **A thread-pool timeout wrapped around a blocking call bounds the caller, not the call.**
  `brain-layer/server.py`'s `_run_job` races `Decider.decide()` on a `ThreadPoolExecutor` and gives
  up after `decide_timeout_s`, but `shutdown(wait=False)` does not — cannot — stop the underlying
  call: Python has no mechanism to preempt a blocked thread. A genuinely hung call (not just a slow
  one) leaks its worker thread permanently; the timeout only lets the *caller* move on. The actual
  fix has to live one layer down, in whatever can make the blocking call itself return — here,
  `OllamaClient`'s own socket-level `urllib` timeout. A server-side wrapper timeout is worth keeping
  anyway as a decider-agnostic backstop, but it must be understood as bounding the symptom, not the
  cause (BR-1 Stage 2 performance review prerequisite 2, `plans/brain-layer/performance-review.md`).

- **A safety claim that holds in one drift direction is not thereby safe in the other, and adding a
  second trust boundary nearby can flip a previously-true claim false.** `brain-layer`'s
  `CLASSIFY_COMMAND_VOCABULARY` and body-layer's mirrored `OFFERED_CONFIRM_VOCABULARY` were
  documented as safe to let drift ("a mismatch here costs accuracy, never safety") when only the
  wider `DISPATCHED_COMMAND_TOKENS` check existed. Once a stricter membership check was added
  specifically against the offered vocabulary, the claim became true in only one direction (the
  list widening) and false in the other (a token *removed* from what's offered but not from the
  mirror re-admits exactly the gap the new check was built to close). The bug was in the docstring,
  not the code — caught only because Reviewer traced both drift directions explicitly rather than
  accepting the existing comment. Lesson: when a new check is added near an existing "safe to
  drift" claim, re-derive the claim rather than trusting it still holds — the claim's truth can
  depend on what else reads the same data, not just on the data itself (BR-1 Stage 2
  Security/Performance fold review, `d51a25b`, 2026-09-25).

- **A fix that makes a silent failure loud can introduce a new silent failure of its own — and a
  docstring claiming the mechanism is safe is not evidence that it is.** `aircraft-layer-hardening`'s
  first `CollectorServer.serve_forever` `accept()` guard classified a clean shutdown by re-reading
  `self._socket` inside the `except OSError` block, and the implementer's own docstring,
  `implementation.md`, and agent-memory file all stated this was safe because the attribute was
  "never re-read after the exception fires." That claim was false: `close()` sets `self._socket.close()`
  then `self._socket = None` as two separate statements, and a blocked `accept()` could raise from the
  `close()` call itself while `self._socket` still held the old object — misclassified as a real
  failure on 161 of ~230 real shutdowns (measured, not theoretical), teaching an operator to ignore
  the very ERROR line the fix existed to raise. The correct fix was an explicit flag
  (`self._shutting_down`) set as the first statement of `close()`, before the socket is actually
  closed, so the flag-write happens-before the syscall that can trigger the exception — inference
  from a mutated value replaced by an explicit signal set before the mutation. Lesson: when a fix's
  whole justification is "condition A is distinguished from condition B by reading attribute X, and
  that's safe because X is never re-read," don't accept that from the docstring — reproduce the
  actual race (run the real shutdown path repeatedly) before trusting it, and prefer an explicit
  flag written before the racy event over inferring intent from a value another thread also mutates
  (`plans/aircraft-layer-hardening/review.md`, `ac0bff9`, 2026-09-26).

- **A regression test that only asserts final outward status can pass for a reason unrelated to the
  bug it claims to guard against — and a reviewer's own suggested fix mechanism can share the same
  blind spot.** `audio-adapter-review-findings`'s negative-`Content-Length` tests asserted only
  `status == 400`, which passed against both the pre-fix and post-fix `server.py` — the pre-fix code
  already had an incidental `self.rfile.read(length) if length > 0 else b""` guard that took a
  different rejection path (JSON-parse failure on an empty body) to the same status code, so the
  hang the security review described was never actually reachable through this test. The reviewer's
  first suggested fix (spy on `rfile.read`, assert it's never called with a negative count) would
  *also* have passed on both versions, for the identical reason — the pre-fix ternary keeps that
  call from ever happening either way. What actually distinguished the two versions was the response
  body's specific error message, visible only once someone read both code paths' literal source
  rather than reasoning about them. Lesson: a review's suggested test mechanism is a hypothesis, not
  a verified fact — before writing the assertion, revert to the pre-fix code and run the candidate
  test against it; if it passes, the mechanism doesn't discriminate, no matter how plausible it reads
  (`plans/audio-adapter-review-findings/review.md` round 2, `1b2e337`, 2026-09-26).

- **A tuning-parameter widening (a threshold, a window, a word set) tends to fail in rounds, each
  round's single rule correct about the case that motivated it and wrong just outside that case —
  and each round is found by running the real adjacent subsystem end to end, not by reasoning about
  it or trusting a test that supplies its own default for the parameter under scrutiny.** The
  confirm-band affirmatives fix (widened `_AFFIRM_WORDS`/`_NEGATIVE_WORDS`, `CONFIRM_WINDOW_S`
  8.0→15.0s, new `CONFIRM_LATE_ANSWER_GRACE_S`) took five review rounds to land safely: first word
  is an answer word → swallows a real utterance opening with that word; require the whole transcript
  to match → breaks "roger, cancelling" style acknowledgements; and so on, each fix correct about its
  own motivating input and wrong on the next one probed. Every round was actually caught by
  constructing a real transcript and running it through the live matcher/`handle_transcript`, never
  by inspecting the widened set and reasoning "this looks safe." This is now the second/third time
  this exact lesson has surfaced in this project's retro material (see also the shutdown-race and
  audio-adapter-review-findings entries above) — it is a process pattern, not a one-off code note:
  any change that widens what a fixed set/threshold/window accepts should budget for multiple rounds
  of adjacent-subsystem end-to-end probing before it is trusted, not one plausible-looking pass
  (`plans/confirm-band-affirmatives/review.md`, five rounds, `867cbfe`, 2026-09-28).

- **A measured data-quality figure recorded correctly in a roadmap/docstring is not the same as
  that figure reaching its consumer.** M7's SRTM-vs-DCS elevation accuracy (mean −7.19 m, stddev
  11.52 m) was measured and written down accurately in `world-model/ROADMAP.md` three weeks before
  a real sortie found `query.line_of_sight.line_of_sight_clear` treating the same grid as exact —
  a unit sitting under a cell that overestimated ground height by close to that stddev read as
  permanently masked from every angle. Neither the measurement nor the consumer code was wrong in
  isolation; the defect lived in the unchecked gap between them. Fixed by adding an explicit
  tolerance sized to the recorded stddev (`_TERRAIN_TOLERANCE_M = 12.0`), not by re-measuring
  anything. Worth checking, whenever a store gains a new measured error figure, whether its
  consumers were re-examined against it — a number sitting in a research note does not audit its
  own callers (`plans/missed-aaa-detection/debug.md`, `fix/los-elevation-tolerance`, 2026-09-29).
- **When a design decision rests on lived-cockpit intuition rather than code, expect it to be
  refuted within minutes by the next thing the user says — the lesson is about *when* to ask, not
  about the domain.** During group-reporting's explore phase, the user's grouping input arrived
  across five short messages, and at least three of them invalidated a design just proposed: a
  gaze-wedge/sector model for group boundaries was refuted immediately by the convoy-through-
  ownship case ("I could fly through the middle of it and it would be on both sides of ownship, but
  be single group"); a floor of 3 members was refuted by "a pair of aircraft are a group, in theory
  — lead and wingman"; and a feared pair/couple vocabulary collision turned out to be one
  specificity ladder, not two competing forms. None of these were derivable from the code or from
  more design reasoning — they needed the person who has flown the aircraft. The actionable form of
  this is not "ask more" in general, but: when a design choice is about how a human perceives the
  simulated world (grouping, salience, disclosure), show a concrete proposal early and expect the
  first answer to move it, rather than iterating internally first (`plans/group-reporting/
  explore-notes.md`, 2026-09-28/29).

- **A tuning value chosen to compensate for a known-defective adjacent step is not stable once
  that step is fixed, and retuning it blind (without re-checking against the fixed step) can land
  on the same compensating value for the wrong reason.** The terrain-watershed valley geometry had
  a real defect (zigzag line extraction inflating sinuosity), and the first tuning round picked
  `core_fraction=0.1` specifically because widening it exposed more of that zigzag — the knob was
  compensating for the bug, not expressing the intended tradeoff. Fixing the geometry step first
  dropped sinuosity from 3.57 to 1.17 at that *same* 0.1 value with no retune at all, then a proper
  re-sweep against the fixed geometry found a better point (0.3) the old geometry could never have
  reached without a sinuosity penalty. Lesson: when a parameter's "best" value was set while a
  known adjacent defect was still present, treat that value as provisional and re-sweep after the
  fix lands, rather than inheriting it — a value that happens to look stable across a fix can still
  be compensating for the wrong thing (`plans/terrain-feature-probing/implementation.md`, second
  round, 2026-10-01).

- **A hand-built test fixture that is uniformly asymmetric/monotonic "to avoid tie-breaking
  ambiguity" is a documented design choice that doubles as a blind spot for exactly the bug class
  it was built to avoid.** Every fixture in `test_terrain_features.py` was deliberately constructed
  strictly monotonic specifically so axis-projection tie-breaks never occur — a reasonable choice
  for keeping the tests' expected values easy to hand-derive — but it also meant no test in the
  suite could ever exercise `_axis_sliced_line`'s `round()`-half-to-even tie-break, which collapsed
  a legitimate symmetric 4-cell component to a single point. The Reviewer found it only by
  constructing a new, deliberately symmetric case outside the existing fixture family. Lesson: when
  a fixture docstring says it avoids a class of input "to keep this simple/unambiguous," that is a
  flag to add one separate fixture that does the opposite, not a reason to trust the simple ones
  cover the mechanism (`plans/terrain-feature-probing/review.md`, round 1, 2026-10-01).

- **A plan's stated reason for scoping a dependency can be wrong even when the scoping decision
  itself is still correct — measure before repeating the justification, not just the conclusion.**
  The terrain-watershed plan scoped numpy/scipy to smoothing and extremum detection on the
  reasoning that basin growth and geometry extraction were "not the bottleneck." Measured: the
  numpy-scoped stages are under 5% of the terrain pipeline's runtime; the stdlib basin-growth/
  geometry stages are over 95%. The stated reasoning was backwards from what the measurement
  showed, but the conclusion (don't vectorize the inherently-serial priority-flood) still held for
  an unrelated reason (it doesn't vectorize, and the absolute cost is cheap regardless). A
  plausible-sounding justification that happens to produce the right answer is not evidence the
  reasoning was sound — it is worth measuring even when nobody doubts the conclusion
  (`plans/terrain-feature-probing/performance.md`, 2026-10-01).
- **In speech-rendering code, a test that asserts shape instead of the sentence is not a safety
  net — three wording defects in a row survived a fully green suite this way.** Group cohesion's
  review found `"a armor"`, `"a infantry"`, and `"A ground and a truck."` all shipped as the
  *expected* output of their own tests, because the assertions checked the absence of other
  branches' markers (`"in" not in speech.text`, `not speech.text.startswith("Now leading")`)
  rather than the actual rendered string. If a line is ever spoken to the pilot, its test must
  pin the literal sentence, not a property the sentence happens to have (`plans/
  group-cohesion-redesign/review.md`, both rounds; `plans/group-undermerging/implementation.md`).
- **The user's own worked utterances, not the rules inferred from them, are the specification —
  and checking the rendered output against the utterances directly is what catches defects that
  internal consistency never will.** The group-cohesion plan's first draft inferred a taxonomy
  from the debug pass's framing before utterances existed; once the user gave worked examples
  (`"AAA in the group"`, `"Shilka and zsu"`, `"SRSAM, Shilka, armor 2 o'clock 2.5 km"`), re-deriving
  the design against them directly (not the inferred rules) reversed one branch (leader change:
  full → delta) and found the indefinite-article defect, since every worked example renders class
  nouns bare (`plans/group-cohesion-redesign/plan.md` §4, `explore-notes-delta-taxonomy.md`).
- **The risk named in a plan is not necessarily the risk that dominates — profile the whole
  pipeline before optimising the step everyone is worried about.** The geomorphons plan flagged
  Zhang-Suen thinning as "the main technical risk... the thing that resolves full-theatre
  feasibility," on the reasonable-sounding theory that a per-pixel Python loop over a theatre-scale
  raster would be slow. Measured (`cProfile` on a real tile): thinning was 0.5-1.4% of per-tile
  time. The actual dominant cost — 92% of per-tile time, unflagged by anyone until profiled — was
  the Chaikin-smoothing deviation check's O(line_length²) full-polyline scan, invisible from reading
  the plan because nothing in the design discussion mentioned it as expensive. A plan's own risk
  assessment is a hypothesis, not a profiling result, even when the hypothesis sounds obviously
  right (`plans/landform-geomorphons/performance.md`).
- **A render used as evidence a change preserved behaviour is only evidence for the code paths it
  actually exercises — check what it calls, not just that its output looks the same.** The
  performance fix's own report noted that `tools/inspect_terrain.py`'s unchanged, byte-identical
  acceptance render proves classification and tracing are untouched, but that tool never calls
  `_smooth_for_storage` or `ingest_terrain` at all — so it says nothing about whether the Chaikin
  deviation-check rewrite preserved geometry, which is exactly the part that changed. The real
  evidence for that claim was a separate, explicit old-vs-new smoothed-geometry comparison run over
  real traced lines. The implementer caught and disclosed this gap in its own report rather than
  letting the unchanged render imply more than it proved (`plans/landform-geomorphons/
  implementation.md`; independently re-run by Reviewer round 3 on different tiles, zero
  mismatches).
- **On this project, a detector's output is accepted by looking at it, not by its metrics.** The
  geomorphons detector is the third attempt at ridge/valley extraction, after two were rejected on
  sight (a per-cell curvature classifier, then a marker-controlled watershed) despite both having
  internally-consistent metrics and passing review. The user's own description of what changed his
  mind was a side-by-side rendered comparison on one real ridge, not a number: watershed drainage
  broke the crest at every saddle, geomorphons kept it whole. Any future terrain/perception work
  whose correctness is fundamentally a matter of "does this look right to a pilot" should budget
  for a rendered comparison early, before investing in tuning metrics that a correct-looking render
  might make moot (`world-model/ROADMAP.md`'s `WM-B6` entry, decision dated 2026-10-01).
