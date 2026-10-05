# Terrain feature probing — redesign around named-landform knowledge, not LOS

> **REVISION 3 — 2026-10-05. Read "Revision 3" immediately below; it replaces Stages 3, 4 and 5.**
> Everything from "### Goal" downward is the 2026-09-29/2026-10-01 document, **kept in place
> unaltered** (`docs/PROCESS.md`, "Superseding a decision" — the original stays, with a pointer to
> its replacement). Its Stages 1–2 mechanism (marker-controlled watershed, "Option C") was
> abandoned and never shipped: geomorphons replaced it (`WM-B6`, `plans/landform-geomorphons/`),
> followed by `fix/landform-relief-gate`. **There are no basins.** Every Stage 3–5 statement below
> that rests on basin structure — adjacency "comes free", `adjacent_feature_ids`, the saddle-
> elevation risk — is void. Stages 1–2 themselves are history, not work to do.

---

## Revision 3 (2026-10-05) — Stages 3–5 against traced lines, with no basins and no rebuild

### Goal (Revision 3)

Let Petrovich qualify a contact report with a relative terrain reference — *"armor, ten o'clock,
four kilometers, next valley"* — computed at **query time** from the shipped flat set of traced
ridge/valley `LineString`s, with **no theatre rebuild and no re-derived basin structure**, and with
a selection rule whose default answer is to say nothing.

### What the ground actually is now (measured 2026-10-05, rebuilt `syria-full`)

- 234,799 landform rows (ridge 122,567, valley 112,232), flat `LineString`s, no topology.
- Tags per row: `elevation_range_m` `[min, max]`, `orientation_deg`, `cell_count`. Nothing else.
- Median line 5–6 vertices, ~1 km long; median relief ~90 m, hard floor 50.0 m.
- Lines are **fragmented by construction**: cut at SRTM tile seams (`plans/landform-geomorphons/`,
  "clip, don't merge") and at skeleton junctions the junction-walk declines to pair.
- Density: ~0.8 ridge lines/km² theatre-average; 297 ridge / 282 valley in a 40 km Baalbek window.

So inside the user's ~5 km working radius there are **tens** of lines of each kind. Any rule that
names "the" valley by nearest-line alone will name something arbitrary most of the time.

### Decision 1 — adjacency is computed at query time. No build-time tag, no rebuild.

**Rejected: tagging `adjacent_feature_ids` at build time.** Cost: an all-pairs adjacency pass over
234,799 rows, a `EXTRACTOR_VERSION`/cache-key bump, and a **full cold ~14-minute `syria-full`
rebuild that the user ran only yesterday** (2026-10-04 23:59) — paid again, by the user, on their
own machine, before a single callout changes. Against that, the runtime saving is nil: the
answer is ownship-relative (see Decision 2), so a per-feature static tag could not have answered it
anyway.

**Chosen: query time.** Measured shape of the work, not estimated class: a bbox query over the
ownship→contact corridor returns **~5 lines at Baalbek density, ~19 at theatre average** for a 5 km
corridor, each 5–6 vertices — low hundreds of segment-segment intersection tests. This is cheaper
than the `nearest_feature` call `describe_position` already makes on the same path.

**Containment rule the implementer must honour:** the result depends on ownship, which moves every
poll, so it is **never** cached in `WorldEnrichmentCache` — same reason `relative_geometry` is not.
It is computed **in the contact-report build path only**, not in the per-tick enrichment path.

### Decision 2 — "one divide" = one deduplicated ridge crossing on the ownship→contact segment

Stated plainly, as the task asked: **geomorphons output cannot support a basin-adjacency graph
without re-deriving something basin-like, and this plan does not re-derive it.** A traced line set
has no faces, so "the valley the contact is in" is not an object that exists in the data.

But the pilot's phrase does not actually need one. *"Target 2 o'clock, next valley"* is a claim
about **what lies between us and it**, and that is directly computable:

> **`divides_between(conn, theatre, observer, target)` → `int`** — the number of distinct ridge
> lines the straight segment observer→target crosses.

- **0** — no divide between us. No divide-relative qualifier.
- **1** — *"next valley"* / *"beyond the ridge"*.
- **≥2** — too far through the terrain for the phrase to mean anything. Say nothing.

This is the user's water-flow analogue at the level that matters — a divide is a thing you cross,
not a wall you are enclosed by — and it is honest about uncertainty in a way a fabricated basin
graph would not be.

**Two mechanical rules make it robust against the data's known defects:**

1. **Fragment-gap undercount is accepted and documented, not papered over.** A continuous crest
   stored as two segments with a seam gap can let the sightline slip through and report 0. The
   mitigation is the merge rule below plus the conservative output mapping (≥2 ⇒ silence, 0 ⇒
   silence about divides); a false 0 costs a missing qualifier, never a wrong one.
2. **Crossings within `DIVIDE_MERGE_M` of each other *along the segment* count as one divide**
   (first guess 400 m). This collapses both the two-fragments-of-one-crest case and the parallel
   sub-crests of a single ridge mass. Without it, one ridge mass reads as "2 divides" and the
   feature silently never fires.

Only ridges with the stored 50 m relief floor participate, which is every stored ridge — the gate
is already applied at build time, so no extra filtering is needed, and that is why this works at
all against the pre-relief-gate data it would not have.

### Decision 3 — landform selection: a dominance rule whose default is to name nothing

Two findings drive this, both checked rather than assumed:

- **`NEAR_FACT_RADIUS_M["ridge"]/["valley"] = 1000.0` in `body-layer/src/belief/enrichment.py` is
  now badly wrong.** It was set when the store held 12 ridges over a 20 × 20 km region. Against
  234,799 lines, *something* is within 1000 m almost everywhere in relief, so the gate admits
  essentially always.
- **Terrain currently never reaches the pilot anyway**, for a different reason: landform rows carry
  `confidence={"geometry": "low"}` → 0.4 via `_FEATURE_CONFIDENCE_NUMERIC`, and
  `speech.py::_contact_report_text` speaks only `max(semantic, key=confidence)`. A road or
  settlement fact outbids it. So the live symptom today is silence, and the risk on wiring Stage 5
  naively is that it flips straight to over-naming.

**The rule:**

A *position* qualifier (`"in a valley"` / `"on a ridge"`) is emitted only when **both** hold:

- the nearer of {nearest ridge, nearest valley} is within **`TERRAIN_QUALIFIER_MAX_M`** (first guess
  **300 m** — under a third of the median line length; beyond that, at this density, the nearest
  line is noise), and
- it is nearer than the other kind by at least **`TERRAIN_DOMINANCE_FACTOR`** (first guess **2×**).

Otherwise **name none.** This is the explicit answer to "when is the right answer to name nothing":
in dense mixed relief both kinds are close, there is no clear winner, and Petrovich stays quiet.
It also disposes of the stated trap — a contact in a valley that sits nearer a ridge line produces
*no* qualifier rather than the wrong one.

Optional tiebreak, **not required** (keep it simple and debuggable first): compare the contact's own
terrain elevation against the candidate line's `elevation_range_m`. A contact near the low end of a
valley line's range is plausibly in it. Add only if flying shows the dominance rule alone is too
quiet.

### Decision 4 — Stage 4 scope: feature→position bearing, closing BL-B14's world-model half only

`BL-B14`'s one expensive item needs **the direction from the feature to the contact**, which no
`*Info` dataclass carries. Stage 4 adds it for `RoadInfo`, `SettlementInfo`, `WaterInfo` **and**
`TerrainLineInfo` — the existing plan's "ridge/valley and road/water" scope, confirmed.

The real work is not the bearing, it is the closest point: `store.reader.nearest_feature` returns
only `(feature, distance)`, and for a `LineString` the honest bearing origin is the **closest point
on the polyline**, not its centroid. So `_distance_to_feature` gains a companion returning that
point, and `nearest_feature` returns it alongside the distance.

**Use the existing `geometry.signed_side_of_polyline` for "which side", not a bearing subtraction.**
It is already in `world-model/src/geometry/__init__.py` and is correct for a polyline; re-deriving
side from `bearing_deg` minus `orientation_deg` would reintroduce a 180° ambiguity it already
solves.

**What this closes:** the *world-model half* of `BL-B14`'s "Needs world-model support — the one
expensive item" bullet. **`BL-B14` does not go to `[x]`** — its two dependent wording items
("200 meters north of the road", "next to the road, north side") are body-layer phrasing and stay
open after Stage 4 lands. Mark the bullet as unblocked, not done.

### Decision 5 — Stage 5 phrasing: a qualifier, at most one, usually absent

Terrain is a trailing qualifier on a contact report. It is never the subject, Petrovich never
volunteers cover advice, and the report never grows a second fragment.

```
Contact, three o'clock, five kilometers.                        <- the common case, deliberately
Truck, one o'clock, two kilometers, in a valley.                <- 0 divides, valley dominant <300 m
Infantry, nine o'clock, one kilometer, on a ridge.              <- 0 divides, ridge dominant <300 m
Armor, ten o'clock, four kilometers, next valley.               <- 1 divide, valley dominant at target
Contact, two o'clock, three kilometers, beyond the ridge.       <- 1 divide, no dominant form at target
```

Never: *"you could hide behind the ridge on your left"*, *"recommend an approach from the north"* —
cover and attack advice is out of scope (`explore-notes.md`: navigation phrasing waits until
Petrovich flies).

**Priority against the existing single-fragment rule.** `speech.py` already emits at most one
semantic fragment. The divide-relative form (1 divide) **replaces** the generic `"near X"` winner
when it fires, because "there is a ridge between you and it" outranks "it is near a road" for a
pilot deciding whether to climb. The position form (`"in a valley"`) **competes normally** in the
existing `max(..., key=confidence)` and will usually lose — which is correct and intended.
**Group reports drop the terrain qualifier entirely**, same as the existing group rule for
enrichment facts: one member's valley is not the group's.

### Effort/Value check on Stage 3 — the original Stage 3 fails it, this one passes

The Stage 3 written below (build-time basin adjacency) is a **bad trade now**: it needs a
re-derived basin layer geomorphons does not produce, an all-pairs pass over 234,799 rows, and a
user-run full rebuild — to answer a question that is ownship-relative and therefore cannot be
precomputed. Under Decision 2 the same pilot-visible value costs a segment-crossing counter of
~100 lines with no rebuild, so the ordering question the task raised ("do 4–5 first and skip 3")
does not arise: 3b is now the cheapest stage in the plan.

**No stage in this revision requires a theatre rebuild.** Everything is query-time over the store
the user already has.

### Affected Modules / Files (Revision 3)

- `world-model/src/query/divides.py` — **new**. `divides_between(conn, theatre, observer, target)`
  plus `DIVIDE_MERGE_M`. Home chosen to match `query/line_of_sight.py`'s existing precedent: an
  ownship-agnostic point-A-to-point-B query over the store, consumed by body-layer. **It is not
  LOS** and must not sample elevation — `line_of_sight.py` keeps that job; this counts named
  crossings, which is a *naming* question.
- `world-model/src/store/reader.py` — `nearest_feature` additionally returns the closest point on
  the matched feature (new companion to `_distance_to_feature`). Existing callers keep their shape.
- `world-model/src/query/describe.py` — `bearing_deg: float | None` added to `RoadInfo`,
  `SettlementInfo`, `WaterInfo`, `TerrainLineInfo`; populated from the closest point. Keeps the
  absent-is-a-fact convention: `None` means the store row could not supply it, never a default.
- `body-layer/src/belief/enrichment.py` — `NEAR_FACT_RADIUS_M["ridge"]/["valley"]` retuned; new
  `TERRAIN_QUALIFIER_MAX_M`, `TERRAIN_DOMINANCE_FACTOR` and the dominance selection; new
  report-time (uncached) terrain-qualifier builder taking ownship.
- `body-layer/src/belief/speech.py` — the qualifier slot and the divide-form priority rule in
  `_contact_report_text`; group path unchanged (drops it).
- `body-layer/BACKLOG.md` — `BL-B14`'s expensive bullet marked unblocked by Stage 4, item left open.
- `world-model/ROADMAP.md` — Stages 3–5 status.
- **Not touched**: `world-model/src/terrain/*` (the detector is done), `probe_store/`,
  `aircraft-layer`, `query/line_of_sight.py`.

### Implementation Plan (Revision 3) — four independently mergeable stages

1. **Stage 3a — stop the over-naming before adding anything** (`body-layer` only, no world-model
   change). Retune `NEAR_FACT_RADIUS_M` for ridge/valley and add the `TERRAIN_QUALIFIER_MAX_M` /
   `TERRAIN_DOMINANCE_FACTOR` dominance rule from Decision 3. Tests: a fixture with both kinds close
   emits nothing; one kind clearly dominant emits it; both far emits nothing. Mergeable alone, and
   the only stage that changes live behaviour without adding a new surface.
2. **Stage 3b — `query/divides.py`.** The crossing counter with `DIVIDE_MERGE_M` dedupe. Tests over
   hand-built polyline fixtures: zero/one/two crossings, two collinear fragments of one crest
   counting as one, a near-miss not counting. Then one offline check against the real
   `syria-full` store at Baalbek (a segment across a flank should read 1, along the floor 0) — a
   read-only query, not a build.
3. **Stage 4 — closest point and `bearing_deg`** through `nearest_feature` → `describe.py`. Closes
   `BL-B14`'s world-model half. Independently reviewable; no body-layer change required to merge.
4. **Stage 5 — the callout.** Wire Decision 5's phrasing and priority rule. **Flyable acceptance
   last**: fly a real approach across a flanking ridge at Baalbek and confirm the three forms
   ("in a valley", "next valley", silence) appear where the terrain says they should.

### Risks & Unknowns (Revision 3)

- **Fragment-gap undercount** (Decision 2, rule 1) — a seam-split crest can read 0 divides. Costs a
  missing qualifier, never a wrong one; `DIVIDE_MERGE_M` mitigates the opposite error. Not fixed.
- **Four first-guess constants** (`TERRAIN_QUALIFIER_MAX_M` 300, `TERRAIN_DOMINANCE_FACTOR` 2×,
  `DIVIDE_MERGE_M` 400, the ≥2-divides silence). None is derived; all are "tune by flying".
- **Query-time cost is argued from density, not timed.** ~5–19 polylines of 5–6 vertices per
  corridor is the basis. If a real session shows otherwise the fallback is a per-report memo keyed
  on (rounded ownship cell, contact id), not a build-time tag.
- **The ownship dependency is an easy caching mistake.** Putting the divide count into
  `WorldEnrichmentCache` would make it go stale while the helicopter flies, producing a confidently
  wrong "next valley". Called out here because the cache is right there in the same module.
- **Stage 3a changes live behaviour on its own** — it is the only stage that can make Petrovich
  quieter (or, if the thresholds are wrong, noisier) before anything new exists to say.
- **VOID — the saddle-elevation risk recorded in the superseded Risks section below.** It described
  a watershed prominence gate over basin pairs. There are no basins and no saddle computation; it
  cannot affect Revision 3's adjacency, which does not read basin structure.
- **Knowledge-graph coverage**: `graphify-out/` does not exist in this worktree, and the main
  checkout's graph (built 2026-10-05 02:03) predates nothing relevant here but returned only
  diffuse matches for "landform adjacency / next valley" and for BL-B14's bearing history. Prior
  work was therefore established by reading `plans/landform-geomorphons/plan.md`,
  `plans/landform-relief-gate/`, `world-model/ROADMAP.md` (`WM-B6`, Live acceptance debt),
  `body-layer/BACKLOG.md` (`BL-B14`) and the source directly. **"Next valley" has no prior
  specification other than this plan's own superseded Stage 3; feature→position bearing has no
  prior design other than `BL-B14`'s statement of the need.**

### Second-order effect (Revision 3)

`query/divides.py` is the first terrain-*relational* query in the store (everything before it is
nearest-X). When Petrovich eventually flies, "cross the ridge to the right and dip into the valley"
needs exactly this primitive plus ray ordering — so the deferred navigation milestone inherits a
working divide counter instead of starting from a flat line set. It also narrows one thing
deliberately: by never materialising basins, it leaves "follow the whole crest" (the merged-segment
problem `WM-B6` parked) still unsolved, which is the right trade while the consumer is a contact
report.

### Decisions Requiring User Input (Revision 3)

- **May the terrain qualifier displace the existing `"near a road"` fragment when a divide fires?**
  Decision 5 recommends yes (one fragment total, terrain wins in the divide case). The alternative —
  terrain never displaces, only fills an empty slot — is quieter but means "next valley" almost
  never gets said near roads. Product call, not a technical one.
- **Stage 3a tightens ridge/valley `NEAR_FACT_RADIUS_M` from 1000 m immediately.** This changes what
  Petrovich says on the next flight, before any new feature exists. Confirm it should ship on its
  own rather than ride with Stage 5.
- **The four constants above are first guesses.** Confirm the intent is to fly them and adjust,
  rather than have them swept offline against renders the way the relief gate was.

---

## Superseded — the 2026-09-29 / 2026-10-01 plan, kept for the record

Dated 2026-09-29, revised same day after the consumer was named concretely, **revised again
2026-10-01** after an Explore conversation (`plans/terrain-feature-probing/explore-notes.md`)
settled what "ridge" and "valley" must mean for the pilot and replaced the discrete-Laplacian
detector's whole design. Supersedes `plans/live-terrain-sampling/design-input.md` as the design;
that file stays as the record of the user's original LOS-driven scheme, most of which does not
survive below.

**Reading order for this revision**: `explore-notes.md` is controlling wherever it disagrees with
anything below it was written after. `world-model/research/2026-10-01-terrain-features-full-build-
inspection.md` is the real-data finding that forced this revision (first full-theatre `ridge`/
`valley` extraction is noise at landform scale, with one finding — the Bekaa valley not
classifying — reversed by the user: that is *correct* behaviour, not a defect).

### Goal (unchanged)

Give Petrovich the ability to reference named terrain features in crew callouts — *"contact, three
o'clock, 2 km, at the foot of the hill"*, *"armor, ten o'clock, next valley"*. Line of sight is not
touched by this plan and never has been: `query/line_of_sight.py`'s `line_of_sight_clear` samples
`store.reader.sample_grid` against the raw `elevation` grid directly, point-by-point along the
sightline, completely independent of this module's `ridge`/`valley` feature extraction. Confirmed
by reading the code, not assumed — the two mechanisms share a grid, nothing else. This plan's
detector answers "what would a pilot call this feature", never "can unit A see unit B"; that
boundary does not move.

### Why this revision exists — the first real output was wrong, and the earlier findings explain how

`research/2026-10-01-terrain-features-full-build-inspection.md` ran the shipped Stage 1/2 work
(un-gated extraction, 500 m SRTM spacing) against the real `syria-full` theatre for the first time
and found:

1. Flat terrain correctly produces no features (no false positives) — the one part of the old
   mechanism that is not in question.
2. **Fragmentation**: 75 % of ridges and 70 % of valleys are under 15 cells.
3. **Zigzag polylines**: median sinuosity (path length ÷ end-to-end distance) 2.17 (ridge) / 2.21
   (valley) — a "line" that wanders twice as far as it travels.
4. **Parasitic pairing**: every ridge carries a valley line along its own foot, because the
   detector finds *break-of-slope*, not a landform body — concavity at a hill's toe looks
   identical to concavity between two hills to a per-cell discrete Laplacian.
5. (Originally flagged, now reversed by the user) the Bekaa's flat floor not classifying as
   `valley`. **This is correct**: *"Not kilometres wide flat bottom, while technically being a
   valley, it's meaningless in the Mi-24 flight profile scale. In that sense Bekaa not being valley
   is correct."* A kilometres-wide basin provides nothing to hide behind at this scale.

The 2026-09-29 spacing sweep (`research/2026-09-29-terrain-feature-probing-spacing.md`) had already
shown, before any of this, that **the checkerboard ceiling is spacing-invariant**: going finer
(250 m, 100 m) reproduces the same noise at higher density rather than resolving it, and 500 m
remained the storage *and* processing spacing for exactly that reason. The 2026-10-01 inspection's
own conclusion names the real cause: *"a definition mismatch, not a tuning failure — no threshold
fixes a detector that is measuring the wrong thing."* Retuning `DEFAULT_CURVATURE_THRESHOLD_M`
cannot fix defects 2–4; they are structural to a per-cell, single-neighbour-step curvature test.

### What "ridge"/"valley" must mean, from the Explore conversation — condensed, see `explore-notes.md` for the user's own words

- **A valley is the concave form between hills — not a wide flat basin.** It may have a flat
  bottom; being *between* raised ground is what matters, not basin width in itself except at the
  scale where the basin becomes too wide to reference as one feature (the Bekaa case).
- **The only scale that matters is ~5 km around the helicopter**, and the consumer is LOS/position
  reasoning: what's there, what masks what, where to attack from, where to hide.
- **A form earns the label by being maskable-behind — "sharp and/or high."** Worked out
  range-independently from a 200 m AGL sightline: a form must rise **~50–150 m over a short
  horizontal run** to break line of sight, depending on where along the sightline it sits. This is
  a *relief-amplitude* criterion, not a per-cell-step curvature value — the old detector's 20 m
  threshold was applied to curvature over one 500 m cell step, an order of magnitude below anything
  that actually masks, *and* contaminated by cell-to-cell roughness at that same step size.
- **Relative descriptors only — no gazetteer, no stable names.** `name` stays `None`.
- **Terrain qualifies a contact report only.** Navigation phrasing (*"follow that valley"*) is
  explicitly deferred to when Petrovich flies; nothing in this revision builds toward it, same as
  the original plan's item 6.
- **"Next valley" = adjacent across exactly one divide**, confirmed and sharpened by the user,
  rejecting a ray-ordering reading as navigation-only.
- **The analogue is water flow, not rooms/doorways**: terrain is a surface with preferred low paths
  that can always be left by climbing, not an enclosure. This points at **valleys as basins and
  ridges as the divides between them** — continuous, connected, and naturally adjacent across a
  shared boundary — rather than independently-classified edge cells.

### The three candidate mechanisms considered, and which one this plan picks

The user offered drainage/divide extraction via flow accumulation as *"a candidate direction for
the architect, not a settled decision"* and asked for evidence-based argument if something else
serves better. Three real candidates, evaluated against the five defects above plus the Bekaa
exclusion and Stage 3's adjacency need:

**A — Smoothed, multi-scale curvature.** Box-smooth the elevation grid at a landform-scale window
(removing cell-to-cell roughness), then run the existing discrete-Laplacian test at a wider stencil
distance (sample neighbours several cells away, matching the "50–150 m over a short run" criterion
in real metres instead of one grid step), keeping `_connected_components`/`_principal_axis`
unchanged. Cheapest option, stdlib-only, directly attacks the scale mismatch behind defects 2–3.
**Rejected as primary**, because it is still an *edge* detector: it has no notion of a basin's own
width or area, so it cannot express the Bekaa-exclusion rule as anything other than a second
heuristic bolted on after the fact, and the parasitic-pairing defect (4) is structural to any
per-cell concavity test, not a resolution artefact — smoothing reduces its frequency but cannot
eliminate it by construction, since a hill's own toe is genuinely concave regardless of scale.

**B — Full D8 hydrology** (depression-filling, flow-direction, flow-accumulation, stream-network
thresholding). This is the literal reading of "water flow" and would give a fully general drainage
network. **Rejected**: it solves a problem this consumer doesn't have (which way water ultimately
exits the theatre to the sea) at the cost of a pit-filling pass whose entire purpose is correctness
over regions this plan doesn't care about. It is also the most dependency- and tuning-heavy option
(accumulation-threshold tuning is its own multi-pass sweep, on top of everything else), for a
contact-report flavour feature.

**C — Marker-controlled watershed over a landform-scale-smoothed grid, gated by basin relief and
width. Chosen.** This takes the user's water-flow analogue at the structural level that actually
matters here — *valleys are basins, ridges are the divides between them* — without the full
flow-routing machinery Option B needs to answer a question this plan never asks. Concretely:

1. **Smooth** the elevation grid at a landform-scale window (`scipy.ndimage.uniform_filter`, NaN/
   gap-aware: filter the value-where-sampled and the sampled-mask separately and divide, leaving a
   cell `None` if too few of its window were sampled — same "never fabricate from missing data"
   rule `classify_curvature` already follows, loosened from "all four neighbours" to "a majority of
   the window" since this is an average, not an edge-sensitive derivative).
2. **Seed** basins at the smoothed grid's local/regional minima (`scipy.ndimage.minimum_filter`,
   standard marker-controlled-watershed input — no separate ridge-seed step is needed; see point 4).
3. **Grow basins** from those seeds by a priority-flood-style flood fill in ascending elevation
   order (a min-heap over cells, Vincent & Soille 1991's watershed-by-immersion, adapted to grid
   cells rather than image intensity) — every sampled cell ends up assigned to exactly one basin.
   This is a textbook graph algorithm, not a new numerical method; it is the one part of this
   mechanism that does **not** vectorize (it's an inherently serial priority-queue traversal), so it
   stays a hand-written `heapq` loop over plain Python/numpy-indexed cells — the existing codebase
   already demonstrates this project tolerates a full-theatre (~2.5 M-cell) pure-Python pass at
   one-time-build cost (Stage 1's shipped curvature pass already does this).
4. **Ridges fall out as basin boundaries**, gated on their *own* prominence — a boundary between two
   basins is emitted as a `ridge` only if it rises `relief_m` (candidate 50–150 m, tuned by looking,
   same discipline as before) above the **lower** of the two adjoining basins. This is evaluated
   independently of whether either basin individually qualifies as a named `valley` below, which is
   what correctly keeps Palmyra's isolated desert ridge chains (finding: "located correctly,
   shaped badly") as ridges even though the flat desert on either side is not itself a valley.
5. **Valleys are basins that pass two gates**: `relief_m` (basin floor-to-rim, same 50–150 m family)
   **and** a width ceiling along the basin's minor principal axis (candidate ~2–3 km, tuned by
   looking **specifically at the Bekaa**, which must fail this gate while real valleys pass it — the
   concrete, checkable form of the user's "kilometres wide flat bottom" exclusion). A basin that
   fails either gate contributes no `valley` row, but can still have a qualifying `ridge` on one of
   its boundaries (point 4).
6. **Geometry extraction reuses `_principal_axis` and the projection-sort unchanged** — for a
   qualifying valley, over the basin's own lower-elevation core cells (not independently-classified
   curvature cells); for a qualifying ridge, over the shared-boundary cell set between two basins
   (grouped into separate components with `_connected_components` where two basins touch at more
   than one disjoint stretch). Output stays a `LineString`, no change to `store.models.StoredFeature`
   or `to_stored_features`'s shape.
7. **Adjacency is exact, not heuristic — and comes free.** Two valleys are "across one divide" iff
   their basins share a boundary that qualifies as a ridge (point 4). This is a direct read of the
   basin-adjacency structure already computed in step 3, not a separate geometric nearest-neighbour
   pass — a real simplification of what Stage 3 (below) otherwise would have needed to approximate.
8. **A size floor stays** as a safety net against seed-detection artefacts (a single noisy-pixel
   local minimum producing a one-cell basin) — same role `DEFAULT_MIN_CELL_COUNT` plays today,
   retuned for basins rather than curvature components.

**New dependency: `numpy` and `scipy` are added to `world-model/pyproject.toml`.** Scoped narrowly
and justified concretely, per the standing user decision that numpy/scipy is approved *when
actually needed* and the existing "no numpy for a problem this small" reasoning still stands for
small problems: they are used **only** for step 1's smoothing and step 2's extremum detection
(`scipy.ndimage.uniform_filter`/`minimum_filter`, vectorized O(n) over a ~2.5 M-cell theatre grid,
where a hand-rolled Python nested loop would be the slow part of the whole pipeline for no benefit
over a well-tested library call doing exactly this). The basin-growth watershed (step 3) and the
axis/boundary extraction (step 6) stay the existing stdlib approach — `_connected_components` and
`_principal_axis` are reused unmodified, not reimplemented in numpy, because nothing about them was
the bottleneck or the source of any of the five defects. **This is the concrete "which operations,
what it buys" the dependency approval asked for; nothing else in `world-model` reaches for numpy
because of this change.**

### Effort/value note

Option C is a materially larger build than the curvature pass it replaces — a new seeding/growth
algorithm alongside the kept axis-extraction code, plus two new tunable gates (relief, width) each
needing their own look-at-real-output pass. It is not, however, the "full hydrology" project the
water-flow analogue could have implied: there is no pit-filling, no flow-accumulation threshold
sweep, no stream-network extraction. The size is comparable to M6's original build (which also
chained three algorithmic steps and two empirical tuning passes), and is justified by being a fix
to a feature that is **already live** — `body-layer/src/belief/enrichment.py` already emits "a
ridge line"/"a valley line" callouts today from whatever the detector currently produces, so this
is correcting shipped, currently-wrong output, not speculative scope.

### What survives from Stages 1–2 and what is superseded

- **Survives unmodified**: the pipeline un-gating (`ingest_terrain` now runs against whichever
  `elevation` grid is present, not only a DCS probe grid).
- **Reopened — processing spacing is a swept knob again, not an inherited decision** (user,
  2026-10-01: *"grid size, I agree, investigate what gives good results and use that"*). This
  revision originally carried 500 m forward on the 2026-09-29 sweep's finding that finer spacing
  reproduced the same checkerboard at higher density. **That finding is about the Laplacian**, and
  transferring it to a different mechanism is exactly the kind of inherited-premise error this
  project keeps paying for. The specific worry: a sharp 500 m-wide V-notch — the "sharp and/or
  high" form the Explore conversation says is the meaningful kind — is *one cell* at 500 m, so
  watershed seeding may resolve it where per-cell curvature could not. Sweep processing spacing
  (500 m / 250 m / 100 m, SRTM is 30–90 m native and already on disk) alongside the smoothing
  window in Stage 1, and record what was chosen and why. **Storage spacing remains a separate
  decision from processing spacing** — a fine transient processing grid can emit only the
  `LineString` features while the stored grid stays coarse; `grid_sample` sizing is 12.2 MB at
  1000 m, ~210 MB at 250 m, ~1.3 GB at 100 m of a 589 MB store.
- **Superseded, not reverted**: `curvature.py`'s per-cell discrete-Laplacian classification and its
  `DEFAULT_CURVATURE_THRESHOLD_M = 20.0` tuning. These were real, checked work (the 500 m/threshold
  cross-validation against M6's DCS-probe-derived components was a genuine finding), but the
  2026-10-01 inspection shows the mechanism itself — not its tuning — is wrong for landmark-scale
  bodies. `classify_curvature`/`CellCurvature`/`CurvatureClass` are replaced by Option C's
  smoothing + seeded-watershed pipeline; `_connected_components` and `_principal_axis` in
  `features.py` are kept and reused as described above.
- **Existing tests must be rewritten, not extended** — flagged below as an Escalation Rule item,
  not decided silently.

### Affected Modules / Files

- `world-model/pyproject.toml` — add `numpy`, `scipy` as dependencies (see justification above).
- `world-model/src/terrain/curvature.py` — replaced: `classify_curvature`'s per-cell discrete
  Laplacian is removed; new functions for landform-scale smoothing (`smooth_grid`) and basin
  seeding (`find_basin_seeds`), both thin wrappers over `scipy.ndimage`.
- `world-model/src/terrain/features.py` — new basin-growth (`grow_basins`, hand-written priority
  flood) and basin-gating (`qualifying_valleys`, `qualifying_ridges`) functions; `_connected_
  components`/`_principal_axis` reused unchanged for boundary/axis extraction; `extract_components`
  reworked to call the new pipeline instead of `classify_curvature`'s output. `to_stored_features`
  unchanged — same `StoredFeature` shape, same `provenance`/`confidence` convention.
- `world-model/src/store/models.py` — document two new reserved `tags` keys on ridge/valley rows
  (no schema change, same convention as `connecting_road_ids`/`inner_rings`):
  - `adjacent_feature_ids: list[int]` — the neighbouring valley/ridge feature ids across a shared
    qualifying divide (Stage 3).
  - `basin_width_m: float` (valley only) — kept for inspectability/debugging of the width gate, not
    currently read by any consumer.
- `world-model/tools/inspect_terrain.py` — render basin labels and the relief/width gate pass/fail,
  not just the old per-cell classification map, since that is now the thing Stage 1's acceptance
  check has to look at.
- `world-model/tests/test_terrain_curvature.py`, `test_terrain_features.py`, `test_ingest_terrain.py`
  — rewritten, not extended (see Escalation below).
- `world-model/src/query/describe.py` — unchanged by this revision's Stage 1/2; Stage 4's generic
  bearing work (below) still applies here, carried over from the 2026-09-29 plan unmodified.
- `body-layer/src/belief/enrichment.py`, `body-layer/src/belief/speech.py` — unchanged by Stage
  1/2; Stage 5's callout wiring still applies, carried over unmodified, now consuming the exact
  `adjacent_feature_ids` tag instead of a heuristic lookup (see Stage 3 below).
- **Not touched**: `world-model/src/probe_store/` (M8), `aircraft-layer`, `query/line_of_sight.py`
  (see "Goal" above — the boundary this plan does not cross).

### Implementation Plan

1. **Stage 1 (revised) — replace the detector with Option C, and pick the smoothing window and
   relief/width gates by looking.** Implement `smooth_grid`, `find_basin_seeds`, `grow_basins`,
   `qualifying_valleys`/`qualifying_ridges` as specified above. Run against `latakia-20km`
   (existing precedent region, real An-Nusayriyah-foothill relief) **and** a Bekaa-equivalent test
   region if one can be built region-scoped (the Baalbek SRTM tiles used for the 2026-10-01
   inspection's full-theatre render) — the Bekaa case needs its own region-scoped check since it is
   the concrete, falsifiable form of the width gate. Sweep smoothing-window radius and the relief/
   width thresholds AND the processing spacing (500 m / 250 m / 100 m), rendering each with the
   updated `inspect_terrain.py`, exactly as Stages 1–2
   originally did for the curvature threshold. **Acceptance, checkable without a sortie**: (a)
   fragmentation and sinuosity numbers recomputed over the new output are materially better than
   the 2026-10-01 baseline (75 %/70 % under-15-cells, sinuosity 2.17/2.21); (b) no ridge is paired
   with a valley running along its own foot in the rendered output; (c) the Bekaa basin fails the
   width gate and produces no `valley` row; (d) Palmyra's isolated ridge chains still produce
   `ridge` rows (regression check against the one thing the old detector got right).
2. **Stage 2 (revised) — retune relief/width thresholds against the real Stage 1 output**, same
   sweep-and-record method as before, written to a dated research note. Expect more than one pass,
   same as the original curvature threshold's 3.0 m → 20.0 m sweep.
3. **Stage 3 — landform adjacency. SUPERSEDED by Revision 3, Decisions 1–2 (2026-10-05).** Its
   premise — "basin-adjacency is already known from Stage 1's basin growth" — is void: Option C was
   abandoned before shipping and there are no basins. With Option C, this is no longer a separate geometric pass:
   basin-adjacency across a qualifying ridge is already known from Stage 1's basin growth (point 7
   above). Store it as `adjacent_feature_ids` on each valley/ridge `StoredFeature` at build time
   (static geography, computed once, never at runtime) — this is cheaper than the original plan's
   anticipated Stage 3, which expected to need a new geometric nearest-neighbour pass over
   independently-extracted `LineString`s; Option C's representation makes adjacency a direct
   read instead.
4. **Stage 4 — generic feature bearing in `describe_position`, retiring BL-B14. SUPERSEDED by
   Revision 3, Decision 4 (2026-10-05)** — scope is confirmed, but it closes only BL-B14's
   world-model half and the closest-point work in `nearest_feature` was not accounted for here.
   Unchanged from
   the 2026-09-29 plan: wire `geometry.bearing_deg` into the feature-info shape for ridge/valley
   **and** road/water, closing `body-layer/BACKLOG.md`'s BL-B14 bearing item when this lands.
5. **Stage 5 — the callout. SUPERSEDED by Revision 3, Decisions 3 and 5 (2026-10-05)** — there is
   no `adjacent_feature_ids` to look up, and this version has no selection rule, which against
   234,799 stored lines is the dominant failure mode. Unchanged in shape from the 2026-09-29 plan:
   *"contact, three o'clock, 2 km at the foot of hill"*, *"armor, 10 o'clock, next valley"*, using
   Stage 3's `adjacent_feature_ids` (now an exact lookup, not a heuristic) and Stage 4's bearing,
   plus the existing elevation-band foot/slope/crest approximation against `elevation_range_m`.
   **Flyable acceptance**: fly near a real extracted landform and confirm the callout is producible
   from pipeline output, not a hand-built fixture.
6. **Not this plan**: navigation (*"follow that valley"*, *"stay north of ridge"*) and the
   ray-ordering query it needs — unchanged from the original plan's item 6, reconfirmed directly by
   the user in `explore-notes.md`.

### Risks & Unknowns

- **VOID as of Revision 3 (2026-10-05) — no basins, no saddle computation exists.** Kept for the
  record only; see Revision 3's Risks section. **The ridge gate is strictly more permissive than it was before the 2026-10-01 saddle fix, and a
  Stage 3 implementer needs to know it.** The divide elevation is now the true pass height (minimum
  over contact pairs of the maximum of the two sides), where the first implementation took a naive
  minimum over the mixed boundary-cell set. The correct saddle is always **greater than or equal
  to** the naive one, so the prominence gate can now admit a ridge it previously rejected. None of
  `latakia-20km`, `baalbek-20km` or `palmyra-20km` sits near that boundary — confirmed by rebuilding
  all three with and without the fix and getting identical output, not assumed — but a future
  theatre can. **Stage 3's adjacency is defined across qualifying ridges**, so the set of ridges
  that qualify is Stage 3's own input: a change in that set changes which valleys are "adjacent
  across one divide". Recorded here rather than only in `implementation.md`, which is a session log
  a later implementer has no reason to read.
- **The smoothing-window and relief/width thresholds are four interacting knobs, not two** (the
  original plan had one). More tuning surface means more passes before Stage 1's acceptance check
  is satisfied — expected, not a sign the approach is wrong, but worth naming plainly since it is a
  real increase in tuning cost over the curvature mechanism.
- **The width gate is a single scalar (basin minor-axis extent) standing in for "would a pilot call
  this one feature"** — a long, narrow, but still very wide-in-cross-section basin could pass a
  naive width test while still reading as a macro-basin to a pilot. Flagged as an approximation to
  validate against the real Bekaa render, same as the foot/slope/crest elevation-band approximation
  the original plan already accepted.
- **Basin growth assigns every sampled cell to some basin, including flat desert** — those basins
  are expected to fail the relief gate and contribute nothing, but this needs confirming against
  real Palmyra output (Stage 1's own acceptance item (d)) rather than assumed.
- **Runtime cost of the heapq-based basin growth is an estimate, not measured**: ~2.5 M cells at
  O(n log n) heap operations is in the same complexity class as the existing curvature pass (which
  already completes in acceptable one-time-build time over the real theatre), but has not been
  timed. If a real `latakia-20km` or theatre run is unacceptably slow, the fallback is Option A's
  cheaper smoothing-only mechanism for the relief/pairing-reduction half of the problem, at the
  cost of losing exact adjacency and the width gate — not assumed necessary, flagged in case Stage
  1's real run shows otherwise.
- **`numpy`/`scipy` is a new dependency for `world-model`** — small in itself (both are mature,
  widely-available, already implicitly expected by this kind of raster work), but it is the first
  departure from the subproject's stdlib-only terrain code, so any future terrain work should not
  read this as blanket permission to reach for numpy where stdlib remains adequate (the user's own
  framing, carried forward here).
- **`add_probe_chunk`/M8 remains unexercised** — unchanged from the original plan's note; still
  correct, tested infrastructure for a need nothing currently asks for.

### Second-order effect

Unchanged in direction from the 2026-09-29 plan: this gives `syria-full` its first *landmark-scale*
ridge/valley output rather than its first output at all (which Stage 1/2 already delivered, and
which this revision found to be noise). It corrects an already-live consumer
(`enrichment.py`'s ridge/valley callouts) rather than only unblocking a future one. The exact
adjacency Option C produces for free also strengthens, rather than narrows, the later navigation
plan's starting position: `signed_side_of_polyline` and the ordered `LineString` axis both still
apply unchanged to Option C's output, and that plan now additionally inherits a real basin-
adjacency graph instead of having to build one from scratch when ray-ordering work begins.

### Decisions Requiring User Input — all settled 2026-10-01

Both items below were put to the user and answered the same day; they are kept here with their
answers rather than deleted, so the fork and its resolution stay on the record.

- **SETTLED, confirmed:** Option C (marker-controlled watershed) is the mechanism. User: *"1
  confirmed."*
- **SETTLED, approved:** the three test modules are rewritten rather than extended. User: *"2
  yes."*
- **SETTLED, reopened in this plan's favour:** processing spacing is swept in Stage 1 rather than
  inherited from the curvature-era decision — see "What survives from Stages 1–2" above.

The original statements of the two decisions follow.

- **Confirm Option C (marker-controlled watershed) over Option A (smoothed multi-scale curvature)
  and Option B (full D8 hydrology) as the replacement mechanism.** This architect's recommendation
  is C, argued above; A is cheaper but cannot express the Bekaa width-exclusion or fix the
  parasitic-pairing defect structurally, and B solves a problem (global drainage routing) this
  consumer does not have. This is a real architectural fork CLAUDE.md does not decide between, and
  the Option A/B/C tradeoff above is the full case for each — pick the one case where it needs a
  decision rather than my picking it unilaterally.
- **Existing tests must be rewritten, not extended** (`test_terrain_curvature.py`,
  `test_terrain_features.py`, `test_ingest_terrain.py`) — an AGENTS.md Escalation Rule trigger in
  its own right, named explicitly rather than folded into Stage 1's implementation work.
