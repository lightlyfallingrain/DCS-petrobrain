# BL-B104 — Performance Review

Batch: Stages 1–5, 7, 8 of `plan.md`. Reviewed at tip `0c2a1792` (`git diff main...HEAD`),
2026-10-30. One pass for the batch, per root `CLAUDE.md` "Agents".

Budget context: body-layer polls at the 1.0 s default (fixed delay); Export.lua's world-objects
producer runs at its own ~5 Hz; the LOS Hook runs one bridged batch per poll, capped at
`MAX_SIGHTLINES_PER_CALL = 128`. No hard real-time budget is set for this phase, so the question is
whether anything here scales worse than what already runs.

### Performance Review

What was measured (micro-benchmark on this tip's `src/`, body-layer venv, 20 000 calls each). Its
can-fail probe was run and asserted first: the module path had to resolve into this worktree, and
two observation ids had to give different outputs, so a stub or stale import would have failed the
run instead of producing a number.

| call | cost | frequency |
|---|---|---|
| `surface_range_estimate` | 3.9 µs | once per admitted **surface cluster** per poll |
| `perturbed_bearing_range` (baseline, already paid) | 2.3 µs | once per cluster per poll |
| `surface_domain` | 0.14 µs | once per candidate per poll |

So a surface cluster costs about 4 µs more per poll: three extra sha256 draws plus a handful of
trig calls. For tens of clusters that is well under a millisecond against a 1 s poll.

Body-layer checks on this tip: ruff format/check clean, mypy strict clean (79 files), pytest
2856 passed, 4 xfailed.

### Findings

#### LOS Hook: one `land.getHeight` per candidate
- **Location:** `petrobrain-line-of-sight-hook.lua`, `unitAGL(c)` inside the per-candidate loop.
- **Risk:** It is called for **every** candidate in the wedge, not only helicopters, because the
  Hook does not know the category. At most 128 per poll. It runs beside the two
  `land.isVisible`/building raycasts the loop already makes per candidate. A heightmap lookup is a
  cheaper class of call than a ray, so the worst case adds well under the batch's existing cost.
  Not measured in DCS. `bridge_call_ms` is already on the wire, so a regression would show up there.
- **Action:** MONITOR. Compare `bridge_call_ms` before and after on the next sortie with a dense
  scene. Restricting the call to helicopters would mean sending category into the bridged chunk.
  That costs more complexity than ≤128 heightmap reads are worth.

#### LOS datagram size growth
- **Location:** the same loop, `tostring(agl)` appended per entry.
- **Risk:** Lua 5.1 `tostring` prints up to 14 significant digits, so each entry grows by about
  16 bytes. Modelled at the cap with short names, the datagram grows from 3.3 KB to 5.3 KB. Long
  mission-editor names add a few KB more. The receive buffer is 65 536 bytes and the link is
  loopback, so this is far from any limit.
- **Action:** LATER (optional). `string.format("%.1f", agl)` would trim about 10 bytes per entry.
  It is cosmetic and nothing needs it.

#### Export.lua: `category`/`subcategory` per world object
- **Location:** `encode_world_objects_line`.
- **Risk:** Two table-field reads and two short scalar encodes per object, on a line already built
  per object. That is a small constant on top of existing O(n) work.
- **Action:** none.

#### Naked-eye clustering split by domain
- **Location:** `NakedEyePerceptionSource`, two `cluster_candidates` calls concatenated.
- **Risk:** None. The visible list is scanned twice (O(n)). Clustering is pairwise, so splitting n
  into two disjoint sets cannot cost more than clustering n at once (a² + b² ≤ (a+b)²). It is a
  slight saving.
- **Action:** none.

#### Belief: gate growth rate, `Contact.record`, enrichment
- **Location:** `contact_growth_rate_mps`, `Contact.record`/`from_percept`, `implied_position`,
  `_terrain_aware_world_position`.
- **Risk:** All the additions are O(1): one branch, one field write, and one `GeoPosition`
  rebuild. Two effects run the **favourable** way:
  - A stopped or never-moving surface contact now grows at 0.3 m/s instead of its class speed. Its
    gate stays tighter, so association should see fewer ambiguous matches, not more.
  - `_terrain_aware_world_position` now returns early for surface contacts. That removes a
    per-contact terrain solve from the enrichment path, which this role has measured before as the
    dominant per-contact cost (memory `project_report_query_enrichment_dominates`). Exactly how much
    this saves was not re-measured.
- **Action:** none.

#### Hybrid source: horizontal range for surface candidates
- **Location:** `hybrid_source.py`, `horizontal_range_m` plus two `GeoPosition` builds per surface
  result.
- **Risk:** A small constant per scope result.
- **Action:** none.

#### Wire parsing (aircraft-layer schema)
- **Location:** `line_of_sight._parse_entry` (an extra `rsplit` and a `float()` probe per entry),
  `world_objects._optional_int`.
- **Risk:** Constant work per entry or object, at the collector's existing parse frequency.
- **Action:** none.

Tests and the mock-flight harness are not on any hot path and were not assessed.

### Verdict
**PASS WITH NOTES** (APPROVED — MONITOR). Nothing has to change now. The one item to watch is
`bridge_call_ms` on the next dense-scene sortie. That is the only cost this batch adds that was not
measured, and the hook already reports it.
