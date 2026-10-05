## Security Deep Analysis: terrain-feature-probing Rev3, Stages 3a-5

**Verified sha:** `b95b3c69ee284e8172f2ea5ebcd931af7ca31c5b` (matches expected tip for
`feature/terrain-callout-stages-345`). Main checkout's worktree landed on `main` as expected; the
branch was snapshotted with `git archive feature/terrain-callout-stages-345 | tar -x` into a scratch
directory and all commands run with cwd inside `<scratch>/world-model`, using
`/Users/sg/Code/DCS-petrobrain/world-model/.venv/bin/python` (the snapshot has no `.venv` of its
own).

### Dependency Status

No dependency change. `git diff main...feature/terrain-callout-stages-345 -- '**/pyproject.toml'`
is empty.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `world-model/src/query/divides.py` (whole file) | new query-time geometry primitive | Reads `features_in_bbox` (same R*Tree-pruned path `describe_position` already uses) → same `_row_to_feature`/`json.loads(geom_json)` parser as every other reader call. No second parser introduced. | None |
| `body-layer/src/belief/enrichment.py:714-716` (`terrain_divide_qualifier`) | ownship-relative computation | `target` passed in is `world_position` (terrain-aware **belief** position from `_terrain_aware_world_position`/`contact.last_position`), never `Observation.derived_world_position` or a DCS object id. Confirmed by reading the call sites, not the docstring. | None |
| `body-layer/src/belief/enrichment.py:616-652` (`WorldEnrichmentCache`) | caching containment | `_cache` dict is keyed/typed as `dict[str, tuple[GeoPosition, GeoPosition, list[SemanticFact]]]` — no slot for a divide count. `terrain_divide_qualifier` is called directly from `tools.py`'s `_add_enrichment_facts`, never through `cache.get_or_compute`. Confirmed no helper on this path caches on contact alone. | None |
| `world-model/src/store/reader.py:272-306` (`closest_point_on_feature`) | new geometry helper for `bearing_deg` | Pure function of `(x, z, feature)`; feature comes from the store (trusted local build artifact), `(x, z)` from the caller's already-believed position. No ground-truth input. | None |
| `world-model/src/query/divides.py:_segment_intersection_t` | degenerate geometry | Zero-length ridge segment → `denom == 0.0` → `None` (no crash). Single-vertex `LineString` → `range(len(points)-1)` is empty, loop never runs. NaN/inf coordinates → comparisons against `[0,1]` are `False` under IEEE 754, so such a crossing is silently dropped (undercount, the function's own documented accepted failure mode) rather than raising or overcounting. Contact at ownship's exact position → `segment_length_m == 0.0` → explicit `return 0` before any bbox query. | None — tests don't cover the single-vertex/NaN cases explicitly, but the code path is safe by construction; not a blocking gap for this pass. |
| `world-model/src/query/divides.py` cost shape | hot-path cost (5 Hz loop) | Plan's measured density (~5 lines/corridor at Baalbek, ~19 theatre-average for a 5 km corridor) is empirically measured against the real shipped `syria-full` data, not estimated. Upstream bound verified in code: `perception/association.py:116` `PLAYER_BUBBLE_RADIUS_M = 10000.0` gates contact existence itself (`association.py:285`, `range_m(observer, target) <= PLAYER_BUBBLE_RADIUS_M`) before a `Contact` exists to call `terrain_divide_qualifier` on, so the corridor length this function ever sees is bounded at the source, not just by convention. A pathologically fragmented crest inside that bounded corridor is a performance/perf-reviewer concern over a trusted, locally-built `.sqlite` (not attacker-controlled input per this project's threat model), not a security finding. | None (informational; worst-case-under-adversarial-fragmentation stays out of scope per this pass's scoping note) |
| `body-layer/src/belief/speech.py:934-948` | terrain qualifier → spoken text | `facts["terrain_qualifier"]` only ever set from `terrain_divide_qualifier`'s own `str` return (`"next valley"` / `"beyond the ridge"`); no string built from external/untrusted data reaches the speech path here. | None |
| Diff-wide | hardcoded secrets / shell / eval / pickle | `grep` across all 6 changed source files for `eval(`, `exec(`, `os.system`, `subprocess`, `pickle`, `yaml.load`, `__import__`, `# type: ignore`, `cast(` — no hits. | None |

### Verdict

APPROVED

### Required Fixes (if any)

None.

### Notes carried for memory

- `divides_between`'s call sites confirmed clean on the no-omniscience boundary: `target` is always
  the terrain-aware **belief** position (`world_position`), never `Observation.
  derived_world_position`. `ownship` (`OwnshipState`) is the player's own aircraft state, which is
  legitimately known exactly — not a leak.
- `WorldEnrichmentCache` cannot accidentally absorb the ownship-relative divide qualifier: its tuple
  shape has no slot for it, and the call site bypasses the cache entirely. This is the second
  ownship-relative value (after `relative_geometry`) following the same documented pattern; worth
  checking again if a third such value is added later — same class of bug, different field.
- `PLAYER_BUBBLE_RADIUS_M` (10 km, `association.py`) is the real, code-verified upper bound on the
  observer→target corridor `divides_between` ever receives, confirmed by reading the contact-gating
  code rather than trusting the plan's claim.
