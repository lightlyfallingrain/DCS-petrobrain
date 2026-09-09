---
name: pb1-5-naked-eye-revision
description: PB-1.5 plan revision (2026-09-09) — ED detection-model grounding, ED ambient vocabulary, and a discovered pre-existing gap in HybridPerceptionSource
metadata:
  type: project
---

Revised `plans/pb1.5-naked-eye-detection/plan.md` in place after Investigator Session 5
(`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`) landed
findings that changed two load-bearing premises. Durable facts worth remembering beyond this one
plan:

- **`LoGetWorldObjects`/`WorldObjectSample` (aircraft-layer/src/schema/world_objects.py) carries
  no physical-dimensions field** — only `object_type` (a DCS unit-type string), position,
  heading, coalition. Any future channel needing target physical size (e.g. an angular-size
  detectability model) must either hand-author a per-type size lookup table (unvalidated
  vocabulary, same class of risk as `association.py`'s keyword table) or add an aircraft-layer
  schema change — no DCS-exposed per-unit-type dimension database is known to exist in Lua
  (untested, not investigated as of 2026-09-09).

- **`HelperAI.lua` (Mi-24P Lua, fetched to `win-mac-sync/from-windows/`) contains ED's own
  Petrovich detection-model constants in plain Lua**: `min_angular_radius = { lowres = 0.0043,
  medres = 0.008, hires = 0.02, iff = 0.025 }` (rad, a range-by-target-angular-size curve across
  recognition tiers), plus `min_contrast_f`, `extra_eyesight_ratio`, `min_fog_transparency`,
  `scan_rad_around_point = 2500`. Any future body-layer detectability heuristic should check this
  file first rather than inventing constants from scratch — see [[body_layer_api_decisions]] for
  related body-layer API context.

- **`HelperAI_lengths_ng.lua` is a composed-speech fragment bank** (C-side enum names in trailing
  comments) that is the actual source of Petrovich's `"N CONTACTS, H O'CLOCK"`-style ambient
  voice callout — assembled natively, never a literal exported string, which is why four prior
  sessions of grepping found nothing. Full vocabulary: 12 clock bearings (`OP_A1H`…`OP_A12H`), 24
  range buckets (`OP_D100M`…`OP_D10k`), 8 count buckets (`OP_1UNIT`…`OP_MORETHAN15UNITS`), coarse
  ground/air class enums (`OP_ARMORED`, `OP_TRUCK`, `OP_SPAAG`, `OP_GROUPSOMETHING`, …). This is a
  reusable "what granularity can a DCS crew member perceive" template for any future channel
  (naked-eye detection, and potentially a Mission Interpreter "what could the player plausibly
  have known" check).

- **The `PKV` device is refuted as a lead** — `PKV_page.lua`/`PKV_base_page.lua` are pure
  gunsight-reticle rendering, no text/list_indication tree. Don't re-propose it.

- **Discovered, adjacent, NOT fixed in this revision**: `body-layer/src/perception/
  hybrid_source.py` (PB-1, already merged) reads only `middle_list_text` from HelperAI's
  `list_indication(6)` per poll. A re-analysis of the existing PB-1 spike log
  (Session 5 part 2) showed the list is actually a **multi-row window** — `middle`/`upper_*`/
  `lower_*` leaves can hold *distinct simultaneous* contacts (e.g. `Slava cruiser` +
  `Tarantul III corvette` at once), not "one selected target." `hybrid_source.py` is silently
  discarding real rows if this holds generally. Flagged as a recommended separate backlog item,
  not fixed as part of PB-1.5 (scope: PB-1.5 only adds a second, independent naked-eye source).
  **If picked up later**: re-check `hybrid_source.py`'s poll() and `association.py`'s
  single-detection docstring assumption against this finding before touching either file.

- **Recurring design pattern used in this revision, worth reusing elsewhere**: when a plan's
  omniscience-invariant defense is a heuristic pending a live-probe verification of a real
  signal, explicitly *decouple* the heuristic's design from the exportability question — build it
  so a later-confirmed real signal is a straight *source swap* behind the same filter/
  quantisation machinery, not a redesign. Avoids re-litigating the architecture every time a new
  investigator session moves the needle on the underlying DCS-internals question (this plan went
  through 5 investigator sessions before landing).
