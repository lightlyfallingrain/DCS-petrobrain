# Tree cover and perception — user direction, 2026-10-13

**Captured before any planning pass, per the standing direction of 2026-10-05** (*"write down the
provided feedback so that it is not lost. Then use the explore skill to investigate with user what
the behaviour should be"*). This is design direction on cockpit behaviour, not a sortie observation,
but it is the same class of input and the same rule applies: **the user's own words are the
specification.**

Sequencing he set: **after `BL-B59`.**

---

## His words, verbatim

> *"after BL-B59, effect of tree cover on perception. There's data on that in repo. Basically no
> unit that is among trees can be detected. Unit near treeline is a challenge, because tree's would
> block sight from some directions but not all. For now we can leave that out of the model, but if
> you have ideas on how "near trees" could be handled, I'm interested. We could simply imagine
> forested are to be a 10m tall opaque block and so LOS just beyond that would be highly dependent
> on direction (target behind or ahead of trees) and alitude difference (player at much higher alt
> could see over the trees at a higher angle. Player low in tree hides both himself and the unit
> from seeing eachother.) but that'd need detailed altitude data that we decided to drop.*
>
> *Proceed with simple model of anything in forest is not seen and let's explore later what near
> the trees could be and if it is possible and worth it."*

---

## What is decided, and what is explicitly not

**Decided — build this:** a unit **inside** forest is **not detected**. Flat, binary, no
directionality, no altitude term.

**Explicitly deferred to a later `/explore`:** the treeline case — a unit *near* the edge, where
canopy blocks some bearings and not others. His own framing of why it is hard is the part to keep:
it needs **direction** (is the target behind the canopy or in front of it from this bearing) and
**altitude difference** (from high above, you see over the canopy at a steeper angle; down among the
trees, the canopy hides you and the unit from each other symmetrically).

**The obstacle he names himself**: the 10 m-opaque-block model *"would need detailed altitude data
that we decided to drop."* Any later proposal has to answer that, not route around it.

---

## What the repo already holds — this is the data he means

Verified at `1884775`, not assumed:

| what | where | state |
|---|---|---|
| forest polygons | world-model, from OSM | **built and served** |
| `inside_landcover` → `landcover_class` | `world-model/src/query/describe.py` | returns the smallest-area containing polygon, holes honoured; `None` means unmapped, not open |
| `"forest"` → the fact `"in forest"` | `body-layer/src/belief/enrichment.py`, `_LANDCOVER_CLASS_TEXTS` | **already reaches the crew layer as spoken text** |
| the visibility gates | `body-layer/src/perception/visibility.py`, `check_visibility` | five gates: gaze, cockpit mask, per-optic FOV, angular radius, terrain LOS — **landcover is not one of them** |

So the simple model is close to free: the datum is already in the belief layer, and what is missing
is a gate consuming it. That is the whole of the build.

**Why there is no DCS-side alternative, settled and not to be re-litigated**
(`aircraft-layer/research/2026-09-29-tree-los-probe-results.md`, closed 2026-10-01): **no DCS call
gives tree-aware line of sight.** `land.isVisible`, `getIP`, `world.searchObjects` at every volume
and `getSurfaceType` are all terrain-and-scenery only, probed against vehicles parked inside canopy.
ED's own AI does sample tree geometry (`trees_LOS_test_T4 = true`) but that path is compiled. The
per-tree placements *do* exist in `Syria.surface5` — ~8,789 node sections in the first 150 MB, a
readable 2,665-entry asset table naming six species — but the field table's offsets are not file
offsets and every candidate base gives degenerate clouds: the **same payload wall the elevation
decode hit from a different direction**, two attempts, two payloads (`X-B32`). So the statistical
landcover model is not a fallback; it is the answer.

---

## Ideas on the treeline case, for the later conversation

He asked for ideas, so these are recorded for the `/explore`, **not** proposed for building now.
Each is listed with what it would cost against the constraint he named.

1. **Edge distance as a probability ramp, no direction at all.** Detection probability falls from 1
   at some distance outside the polygon to 0 at the boundary. Needs only a point-to-polygon-edge
   distance, which the geometry module already has (`distance_point_segment`). Cheapest by far, and
   it buys the *fact* of degradation without the *asymmetry* he actually described — a unit just
   inside the northern edge is equally hidden from the north and the south, which is wrong in the
   case he cares about.

2. **Chord length through canopy along the sightline.** Intersect the ownship→target segment with
   the forest polygon and use the length of canopy it crosses. This is the one that captures
   "behind or ahead of the trees" directly, needs no altitude at all, and reuses polygon machinery
   that exists. It is the most promising shape, and its cost is one segment-polygon intersection per
   candidate per poll — which must be measured against the 12.6 ms poll budget before it is
   believed cheap, since the forest polygons are the bulk of the store.

3. **A grazing-angle term, which is where the altitude problem actually bites.** His 10 m block is
   geometrically right and needs the *depression angle* from ownship to target, which needs both
   altitudes. Ownship altitude is free and exact. Target ground elevation is the dropped datum — but
   note it may be less dropped than it looks: a unit's own DCS-reported altitude arrives with the
   object, and the elevation grid's retirement was argued partly on that basis. Worth checking
   whether the altitude needed here is already in hand before treating this as blocked.

4. **Mutual occlusion when ownship is itself low among trees.** His last clause, and the only one
   that is symmetric — if the helicopter is inside the canopy polygon at low altitude, the canopy
   hides it from the unit as much as the unit from it. Cheap to express once (1) or (2) exists, and
   it changes *threat* behaviour, not just detection, so it may belong to a different milestone
   entirely.

**The question the `/explore` should actually settle** is not which of these, but whether any of it
earns its place: does the pilot notice a treeline asymmetry in the air, or is binary in-forest
enough to make the picture read right? That is his call on evidence, and the simple model is what
produces the evidence.

---

## Next step, in order

1. `BL-B59` — in flight on `fix/bl-b59-retention-hysteresis`.
2. Then the **simple model**: a landcover gate in `check_visibility`, inside-forest → not detected.
   Ordinary Architect → Implementer → Reviewer work; no `/explore` needed, the direction is
   unambiguous.
3. Then `/explore` the treeline case against the ideas above, with flight evidence from (2) in hand.
