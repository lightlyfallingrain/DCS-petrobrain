# Forest occlusion — the simple binary model

### Goal

A ground unit standing inside a mapped forest polygon is not detected by the naked-eye channel:
one additional gate in `perception.check_visibility`, flat and binary, no directionality, no
altitude term.

Specification: `docs/acceptance/2026-10-13-tree-cover-direction.md` (user direction, verbatim).
The treeline case is **explicitly deferred** to a later `/explore` and is not designed here.

---

### Decision 1 — which framing: the target-position gate, not an occluder along the sightline

Two framings existed. **Take the user's: a gate on the target's own position.**

`todo/backlog/X-B31.md` proposes forest polygons as *occluders along the sightline*, inside
`world-model/src/query/line_of_sight.py`. That framing was written before `BL-11` Stage 4 and is
now **pointed at a path that no longer runs in flight.** `plans/bl11-stage4-fail-closed/plan.md`
removed the offline primitive from the live gate and says so in its own words:

> any future work on that primitive … is now purely an offline/fixture-correctness concern with
> no runtime consequence

`check_visibility`'s gate 4 consults `candidate.live_los_clear` and nothing else;
`line_of_sight_clear` is never called from it, and a test asserts that negative. So a forest
occluder added there would change the offline oracle and `WM-B7`, and change **nothing Petrovich
does in the air**. Compounding it: the live verdict is DCS-driven, and DCS cannot see trees
(`X-B4`, closed — `isVisible`/`getIP`/`searchObjects` are terrain-and-scenery only). Trees can
therefore *only* enter the live path as a separate Mac-side gate, which is the user's shape.

**What X-B31's framing would have cost**, concretely: an edit to `query/line_of_sight.py` (shared
with the offline oracle and `WM-B7`), a world-model test pass, a segment-polygon intersection per
candidate per poll instead of a point test — and then either a second live LOS path or re-plumbing
`line_of_sight_clear` back into `check_visibility`, undoing Stage 4's fail-closed decision, to make
any of it observable. Non-trivial world-model work plus a reversal of a just-merged decision, for
zero in-flight behaviour change.

**It does not foreclose the chord-length treeline model** (the capture's most promising shape). That
model needs the same `features_in_bbox` over `landcover` and the same polygon rings this gate reads.
A `ForestOcclusion` object that today answers `occluded(target)` can later answer
`occluded(observer, target)` by chord length, in the same gate slot, with the same cache shape and
the same `GateOutcome`. Stage 1 is deliberately shaped so that is an internal change to one object.

### Decision 2 — `None` landcover is **not forest**. Measured, not assumed.

`inside_landcover`'s own contract: `None` means *"no mapped landcover (open ground or simply
unmapped)"*. Treating unmapped as forest is a guess in the blinding direction, and the magnitude
decides it. Measured against `world-model/data/world-model/syria-full.sqlite` (real store,
read-only; 2 km grid, 900 points per 60 km box, plus 400 road-adjacent samples):

| region (±30 km) | no mapped landcover | inside forest | areal forest |
|---|---|---|---|
| Latakia | **95.9%** | 2.8% | 3.2% |
| Damascus | 79.2% | 1.9% | 2.0% |
| Aleppo | 62.7% | 0.4% | 0.6% |
| Hama | 42.0% | 0.8% | 0.8% |
| Palmyra | 96.1% | 0.0% | 0.0% |

Unmapped is the *majority* answer everywhere and the overwhelming one in the coastal belt.
Treating `None` as forest would blind Petrovich on 42–96% of ground units — not a conservative
choice, a catastrophic one. **`None` → not occluded.** The gate fires only on a positive
`landcover_class == "forest"` containment.

### Decision 3 — the target only. Ownship-in-forest is out of scope, stated rather than implied.

The gate tests the **candidate's** position. It does **not** test ownship's, and it does **not**
feed threat/engagement state. The capture lists mutual occlusion as deferred item 4 and notes it
*"changes threat behaviour, not just detection, so it may belong to a different milestone
entirely"*. Recording it here so the asymmetry is a decision and not an accident.

### Decision 4 — optic-independent.

The gate runs identically for `UNAIDED_OPTIC` and `BINOCULAR_OPTIC`: magnification does not see
through canopy. The 9K113 is unimplemented and gets no special case. No new `Optic` field.

### Decision 5 — acquisition only; already-detected contacts decay by the existing ladder.

Checked `belief/decay.py` before designing anything new, and **nothing new is needed.** A contact
that drives into woods simply stops receiving percepts and walks the existing ladder:
`OBSERVED_WINDOW_S` 16 s → `POSITION_HALF_LIFE_S` 30 s → `LOST_THRESHOLD_S` 120 s → `CONTACT_LOST`.
That is the correct pilot-facing behaviour (he tracked a tank, it went into the trees, Petrovich
loses it over two minutes) and it is identical to what already happens on a terrain-LOS mask. No
new constant, no new hysteresis, no `forest_masked_since_sim`.

**One pre-existing asymmetry found and deliberately left alone:** `_callout_may_speak`
(`belief/contacts.py`) tests only the **cockpit mask**, not LOS and not forest — so
`CONTACT_RANGE_CROSSED`/`CONTACT_MOTION_CHANGED` can still fire on a stale believed position for a
contact Petrovich cannot currently see. That is already true of terrain-masked contacts; this gate
does not make it worse and fixing it is a separate question. Named here so it is not re-discovered
as a defect of this feature.

### Decision 6 — `forest` only. `orchard` is a user decision, deferred by default.

The store holds 9,710 `forest` polygons and **7,171 `orchard`** ones. Orchards are trees, but
planted in rows with lanes and far lower canopy — partial cover, which is the deferred treeline
problem wearing a different hat. Default: **forest only**, matching the user's literal words.
Magnitude if he wants orchard in: it is comparable in extent to forest theatre-wide and *larger*
in places (Palmyra road-adjacent: 5.0% orchard vs 0.0% forest). Listed under Decisions Requiring
User Input.

---

### Measured cost — affordable, with a cache; not affordable without one

`describe_position` is **84.6 ms per call in situ** (`BL-11` amendment A7) and is not the path.
The cheap path is `store.reader.containing_polygons(conn, ["landcover"], x, z)` — one degenerate-bbox
R*Tree prune plus `polygon_contains`. Measured on the real `syria-full` store, 400 road-adjacent
points:

| path | median | p95 | max |
|---|---|---|---|
| `containing_polygons(conn, ["landcover"], x, z)` | **0.075 ms** | 0.271 ms | 1.54 ms |
| same, `["landcover","settlement"]` (`describe`'s set) | 0.110 ms | 0.694 ms | 1.63 ms |
| `features_in_bbox` alone (row fetch + JSON parse) | 0.068 ms | 0.200 ms | — |

Forest rings are small: median 16 vertices, p95 89, max 494; `geom_json` median 939 B. The cost is
the row fetch and JSON parse, not the point-in-polygon.

**1120× cheaper than `describe_position`, and still too dear uncached at the tail**: 200 candidates
× 0.075 ms = **15 ms**, already past the 12.6 ms median poll budget, and 54 ms at p95. Two things
fix it, both cheap:

1. **Gate position: last.** The chain is cheap-before-expensive; this is the only DB-touching test
   left in it (gate 4 is now a joined boolean). So forest goes **after** terrain LOS, and only
   candidates that cleared gaze, mask, FOV, range/size and LOS pay for it. That is a small set by
   construction — the ones actually about to be reported.
2. **A quantised-position memo**, the same shape as `WorldEnrichmentCache`'s
   `ENRICHMENT_CACHE_POSITION_GRID_M = 50.0` cell key, but keyed on `object_id` and living in
   perception (the belief-layer cache is keyed by `contact_id` and is not reachable from a
   pre-belief gate). Ground units are static or slow: a 50 m cell at 10 m/s is 5 s, i.e. ~5 polls
   per miss at this project's own 1 Hz poll interval (`logger.py`'s `_DEFAULT_POLL_INTERVAL_S`,
   corrected from an earlier 5 Hz figure — found by the security deep analysis and independently
   by the performance review). At an ~80% hit rate (1 miss in every ~5 polls, not ~95%) the
   steady-state cost of the gate is still a dict lookup most polls; the performance review's own
   finding is that the *direction* of this argument still holds even at the corrected rate.

### Measured blast radius — small, and this is the finding to tell the user

**~1–3% of ground positions are inside a forest polygon** (table above; 3 of 400 road-adjacent
points theatre-wide, 0 of 300 near Latakia). The feature will remove *very few* contacts. It is a
correct, surgical change — not the mass silencing the 44,811-polygon figure might suggest, because
only 9,710 of those are forest and Syria's road network largely avoids them.

**This is the effort/value read, and it cuts both ways.** The build is genuinely small — one gate,
one cache, one `GateOutcome`, no world-model change — so it earns its place easily. But the user
should not expect a noticeable change in the air on an arbitrary sortie, and in particular
**it will not generate much evidence for the treeline `/explore` by itself.** To get that evidence
he has to deliberately park units in and at the edge of woods; the coastal belt north-east of
Latakia is where the forest polygons actually are (3.2% areal, the theatre's densest).

---

### Affected Modules / Files

- `body-layer/src/perception/forest.py` — **new.** `ForestOcclusion`: holds the world-model
  `conn`, the theatre, the memo dict, and `FOREST_LANDCOVER_CLASSES: frozenset[str] = {"forest"}`.
  One public method, `occluded(x, z) -> bool`. The only place a landcover polygon is read in the
  perception layer, and the seam the chord-length model later changes internally.
- `body-layer/src/perception/visibility.py` — `check_visibility` gains keyword-only
  `forest: ForestOcclusion | None = None` (additive, `None` a true no-op, same posture as
  `trace`/`live_los_coverage`). Gate 5, **last** in the chain. Note: `conn`/`theatre` are already
  parameters of this function and are currently **unused** — left behind by Stage 4 — so the gate
  needs no signature plumbing beyond the new object; prefer passing `conn` via `ForestOcclusion`
  rather than reviving the dead parameters implicitly.
- `body-layer/src/perception/detection_trace.py` — `GateOutcome.FOREST = "forest"`. Required: a
  debrief has to tell "lost in forest" from "lost to terrain LOS", which is the question the
  feature exists to raise.
- `body-layer/src/perception/naked_eye_source.py` — construct/hold a `ForestOcclusion` when enabled
  (it already holds `world_model_conn` and `theatre`), pass it at the existing call site.
- `body-layer/src/main.py` (or wherever the CLI lives) — `--forest-occlusion` /
  `--no-forest-occlusion` via `argparse.BooleanOptionalAction`.
- `body-layer/docs/STRUCTURE.md` — new `forest.py` entry; amend the `visibility.py` entry's "four
  composed plausibility gates" to five, and the `detection_trace.py` entry for the new outcome.
- `body-layer/tools/summarize_detection_trace.py` — the new outcome must appear in the debrief
  histogram, or the sortie log cannot answer the question.
- `todo/backlog/X-B31.md` — record that the trees-only slice is taken, and that **this plan
  supersedes its framing** for the live path (its sightline-occluder shape remains the right shape
  for the offline oracle, and for the later chord-length treeline model).
- Tests: `body-layer/tests/test_visibility.py` (gate fires / does not fire / `None` is not forest /
  default is no-op), new `test_forest.py` (containment, holes honoured, cache hit and miss across a
  cell boundary), `test_detection_trace.py` (one entry per call, outcome `FOREST`).

Not touched: `world-model/src/**` (no change at all), `belief/decay.py`, `belief/enrichment.py`,
`belief/contacts.py`, `events.py`.

### Implementation Plan

1. **Stage 1 — mechanism, off by default.** `perception/forest.py` with `ForestOcclusion` and its
   memo; `GateOutcome.FOREST`; gate 5 in `check_visibility` behind `forest is None`. No call site
   passes it yet, so every one of the 1704 existing tests is behaviour-unchanged. Unit tests for
   containment (including a polygon with `inner_rings` holes — a clearing inside a wood is *not*
   forest) and for the cache's cell-boundary miss.
2. **Stage 2 — wire it, still off.** `NakedEyePerceptionSource` constructs `ForestOcclusion` when
   configured; `--forest-occlusion`/`--no-forest-occlusion` added, defaulting **off**, a true no-op
   when absent; trace summariser learns the outcome. Flown in one sortie against the same scene with
   the flag on and off — that A/B is the whole reason the flag exists.
3. **Stage 3 — flip the live default to on.** Its own commit, nothing else in it, per
   `body-layer/CLAUDE.md`'s "mechanism and calibration never share a commit".
4. **Stage 4 — cost check in the loop.** Measure the gate's own per-poll contribution and the cache
   hit rate from a flown sortie's trace, against the 12.6 ms budget. The 0.075 ms figure above is
   a bench number on a warm store; the hit rate is the term that cannot be measured on the bench.

Everything testable without live DCS or a running collector: the store opens read-only and
`ForestOcclusion` takes a `conn`, so tests use a small synthetic fixture store, not `syria-full`.

### Risks & Unknowns

- **Cache hit rate is the one unmeasured term.** The cost argument rests on it. If ground units
  turn out to move enough to miss often, the uncached 15 ms/200-candidates figure is the ceiling
  and gate ordering alone has to carry it. Stage 4 measures it; a fallback is a coarser cell.
- **OSM forest polygons are not DCS's trees.** The invariant says DCS is authoritative and external
  GIS augments. Here DCS offers nothing at all (`X-B4`), so OSM is the only source — but a unit
  standing in DCS canopy that OSM does not map stays visible, and vice versa. The `provenance` on
  the landcover row already records this; the gate must not launder it into certainty. Accepted,
  and it is the honest state of the data rather than a defect to fix.
- **Pre-existing: `_callout_may_speak` ignores LOS and forest** (Decision 5). Out of scope,
  recorded.
- **The binary rule may mask what the treeline case would show.** At 1–3% coverage it fires rarely,
  so it generates little evidence either way — see the milestone question below.
- **No-omniscience:** the gate reads `candidate.x/z`, which in this channel is already
  `LoGetWorldObjects` ground truth feeding the *detection* decision — the same footing as every
  other gate in the chain, which is why the chain is in `perception/` and not `belief/`. It reads
  no DCS state the existing gates do not, adds no new ground-truth source, and
  `detection_trace_writer.py` remains the single sanctioned belief/truth crossing.

### Second-order effect / the milestone question

**It makes the treeline `/explore` easier to run, but only if units are placed deliberately.** The
binary rule puts the mechanism, the data path, the cache and the trace outcome in place, so the
chord-length model becomes an internal change to one object rather than a new subsystem — that is
the unblocking. What it does *not* do is produce evidence on its own: at 1–3% coverage, an ordinary
sortie will fire the gate a handful of times at most. So the `/explore`'s precondition is a sortie
with units parked in and at the edge of the Latakia-area woods, which is a thing to ask for, not a
thing to wait for.

It also narrows `X-B31` usefully: the trees half is now answered in the live path, leaving that item
about **buildings**, which is where its real architectural question (the LAN bridge, `X-B27`'s
topology) actually lives. Separating them means the topology decision no longer gates trees at all.

### Decisions Requiring User Input

1. **Orchard: in or out?** Default taken is **out** — forest only, his literal words. 7,171 orchard
   polygons, comparable extent to forest and larger in some regions. Including them widens the gate
   meaningfully; they are also the weakest case for a *binary* rule, since an orchard is lanes and
   low canopy rather than a wall of trees. Recommend leaving out and letting the treeline `/explore`
   decide whether orchard is a partial-cover case.
2. **Should Stage 3 (default on) land in this feature, or wait for a flown A/B?** Recommend landing
   Stages 1–2 and flying the A/B first, then Stage 3 on his word — the flag exists for exactly that
   and the blast-radius number says there is no urgency.
