# X-B4 — Does DCS's `land.isVisible` test trees, and what does a call cost

- [x] **X-B4 — Probe whether DCS's own `land.isVisible` / `land.getIP` tests trees, and what a call costs.** #status/done
  **CLOSED 2026-10-01** (merge `306ae05`) — answered in full, including the tree half. Details below.
  User direction, 2026-09-25, arising from the vegetation-model decision recorded in
  `body-layer/ROADMAP.md` ("Detection under real world conditions", factor 1). **Gates the 9K113
  half of that decision and nothing else** — the statistical model for naked eye and binoculars
  does not depend on the answer, so this probe blocks one channel, not the work.

  **The question, precisely.** `Scripts/AI/Detection.lua` sets `trees_LOS_test_T4 = true` and every
  installed theatre is Terrain-4, so **ED's AI detection** samples tree geometry for line of sight.
  That is *not* the same claim as **the scripting API** doing so. Our own
  `query.line_of_sight.line_of_sight_clear` samples the bare terrain mesh, which makes us strictly
  more permissive through forest than the engine — so if `isVisible` does see trees, it closes a
  known gap for the one channel that can afford to call it.

  **Deliverables:**
  - Does `land.isVisible(from, to)` account for trees, or terrain only? A vehicle in dense forest,
    ray passing through canopy, is the discriminating case.
  - Does `land.getIP` return the blocking point, and is it more useful? It distinguishes "a ridge"
    from "the treeline 200 m short of the target", which the sight channel would want to *say*, not
    merely know.
  - Per-call cost, at realistic candidate counts.
  - Can a result return synchronously, or must it come back through a side channel? **This one was
    left open when the mission-bridge probe item was closed** — it was never the blocker there
    (velocity is a push), and it is the blocker here (LOS is a question).

  **The transport is not in question.** `net.dostring_in("scripting", …)` has been in production
  since 2026-09-13 (`petrobrain-f10-commands-hook.lua`, 1 Hz). This probe is about what the
  function answers and what it costs, not about reaching it.

  **Two weather questions ride the same bridge and should be probed in the same session** (user,
  2026-09-26, from the condition measurements):
  - **Can meteorological visibility be read?** It is a *ceiling* on detection for every instrument,
    not a per-optic multiplier — the user's own framing, and the measurements show it: in rain 2 the
    9K113 wide and narrow fields both detect at exactly 3.7 km despite very different magnification.
    `Export.lua` has no fog or weather getter (confirmed by reading the shipped file), so this
    bridge is the only candidate. `world.weather.getFogThickness()` is the named target. ED's own
    representation is a **time series** (`fog2.manual = {{time, visibility, thickness}, …}`), so
    whatever is built samples rather than reads once.
  - **Can *where* it rains be read?** *"Rain and clouds are not uniform in DCS. Moving will get you
    in and out of rain."* Whether any API exposes the spatial distribution is open, and it is the
    harder question: an ownship-local visibility figure is sampled in the right place but says
    nothing about whether the target sits under a squall. If nothing exposes it, the fallback is an
    ownship-local reading applied scene-wide, with the limitation stated rather than hidden.

  Investigator pass plus a probe on the Windows box. **Run it before the 9K113 slice is scoped, not
  during it** — if the answer is terrain-only, that slice's LOS design collapses and the
  statistical model has to cover every channel instead.

  **WIDENED 2026-09-29 (user), and the probe is now written and deployed.** User: *"we could also
  check if it is possible to get data for trees and buildings from DCS. That would be valuable for
  LOS, if we can get that data."* That is a second question alongside the original one, and the
  two have different answers in prospect:

  - **Test it per ray** — `land.isVisible` / `land.getIP`, DCS answering "can A see B" including
    whatever it counts as occluding. A query, not data.
  - **Extract it as data** — `world.searchObjects(Object.Category.SCENERY, …)` for buildings, into
    the world model as ordinary `StoredFeature` rows. Trees are almost certainly not scenery
    objects (terrain-baked), so for them the per-ray test is likely the only route.

  **Read from the install, 2026-09-29:** `Scripts/AI/Detection.lua`'s `visual_detection` sets
  `objects_LOS_test = true`, `trees_LOS_test = false`, `trees_LOS_test_T4 = true`, and every
  installed theatre is Terrain-4 — so **ED's AI** does test buildings and trees. That says nothing
  about the scripting API, which is native (nothing in `Scripts/` defines `land.isVisible`; only
  `ScriptingSystem.lua`'s `class(SceneryObject, Object)`), so it can only be measured live.

  **FLOWN 2026-10-05 and answered.** Results:
  `aircraft-layer/research/2026-10-05-elevation-cost-probe-results.md`. The desert control did its
  job: the urban-minus-desert gap was 2-of-40 against 0-of-40, which this project then weighed
  against Finding 12's 52 rays through 52 located buildings (none blocked) and Finding 16/19's
  direct contradiction pair, and read as **`isVisible` is terrain-only** — so the control fired
  exactly as designed, and the 9K113 half of this item collapses as it anticipated. Buildings come
  from `world.searchObjects` + `VolumeType.SEGMENT` instead (Finding 21: 8.7 µs/sightline, sees
  buildings in 3D, *cheaper* than the terrain-only call), which is what [[X-B29]] is being built on.

  The probe also killed the premise of live elevation sampling altogether — see [[X-B26]], closed the
  same day: `land.getHeight` works through the bridge and is bit-identical to the mission-editor
  probe, but with DCS answering LOS directly almost nothing live needs elevation at all.

  Original plan for the probe follows. It (deployed) answers all of
  it on the next sortie, with a **desert control** — the same 40-pair terrain-only-vs-`isVisible`
  comparison run over Mezzeh and over Deir ez-Zor, because terrain-sampling error appears in both
  and subtracts out while buildings and trees do not. A near-zero urban-minus-desert gap means
  `isVisible` is terrain-only and this item's 9K113 half collapses, which is why the control is
  there rather than assumed away.

  **If `isVisible` is cheap and does see objects, the prize is larger than this item assumed**: it
  could replace our elevation-grid LOS outright rather than supplement it, which would also make
  the SRTM-resolution question ([[X-B26]]) much less pressing. The probe times it at 1/50/200 rays per
  bridge call for exactly that reason.

  **ANSWERED 2026-09-29, six flights. `land.isVisible` is terrain-only — it does NOT test
  buildings or trees.** Forty rays fired deliberately through forty buildings whose positions came
  from `world.searchObjects` itself, 60 m either side at 2 m AGL: **0 blocked, 40 clear**. The
  controlled sweep agrees, 0/40 in both the ownship area and the desert control. Full results:
  `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` Findings 12-14.

  This reconciles with `Detection.lua` rather than contradicting it: `objects_LOS_test` and
  `trees_LOS_test_T4` govern **ED's AI detection**, a different code path from the scripting API.

  **So the hope above is dead** — `isVisible` sees exactly the bare terrain mesh we already see,
  and routing occlusion through it would buy a bridge call and nothing else. [[X-B26]] is not relieved.

  **What it opens instead, and this is the better outcome:** we now have the raw material to do
  occlusion *better* than DCS's own scripting API offers. `world.searchObjects` returns 590 objects
  in a 600 m radius with positions and type names (denser and more authoritative than OSM
  footprints), and world-model already holds 44,811 OSM landcover polygons for trees. The missing
  piece is **extent** — scenery carries no dimensions (`getDesc` is
  `life/_origin/category/typeName/displayName`, and `life` is hit points), so a type-name → size
  table built once offline over a finite catalogue is what stands between here and a real occluder
  layer. **That is a new workstream, not a tweak** — file it before starting it.

  Costs settled across three flights: `getHeight` 0.8-1.1 us/point (a full 2,601-point M8 chunk is
  2.0 ms), `isVisible` 10.6 us/ray. Scenery search is superlinear and is the one to watch: 126
  objects at 300 m costs 1 ms, 590 at 600 m costs **18 ms** — keep it at or below 300 m.

  **FULLY CLOSED 2026-09-29 after ten flights — and the answer turned positive on a different
  call.** The user asked whether *any* DCS call accounts for buildings and trees. Dumping the live
  API surface (rather than answering from memory or the wiki) named
  `world.VolumeType.SEGMENT`, and it works:

  - **A SEGMENT volume search returns the buildings the sightline passes through**, with an
    open-ground control returning zero — so it intersects rather than merely proximity-matches.
  - **It is a true 3D test**: 6 hits at 2 m AGL, **0 at 15 m and above**, and 2 on a realistic
    200 m-to-2 m slant. Flying *over* a town is not blocked; looking *down through* it is.
  - **8.7 us per sightline** — *cheaper* than `land.isVisible`'s 10.6 us, which sees only terrain.
    200 candidates with full building occlusion cost 1.9 ms, ~1% duty at 5 Hz.
  - **No type-name → size table needed** — DCS does the intersection.

  So `land.isVisible` is a dead end (terrain-only *and* dearer), and **trees have no DCS route at
  all** — they are not scenery objects, so no volume search will ever find them. OSM landcover is
  not a fallback for trees, it is the only source. Full results:
  `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` Findings 15-21.

  What remains is build work, not research — see [[X-B31]] (renumbered from [[X-B28]] at merge:
  the Mac had independently filed [[X-B28]] the same day, and ids are never reused).
