---
name: wm_b1_name_tags_not_merged_from_raw_osm
description: ingest_osm's StoredFeature.tags dict for named features is built fresh, never spread from raw OSM tags -- no reserved-key collision possible from hostile OSM data.
metadata:
  type: project
---

Checked during WM-B1 (latin-place-names) security deep analysis, 2026-10-02. In
`world-model/src/build/ingest_osm.py`, `_ingest_node`/`_ingest_line`/`_ingest_area` construct the
`StoredFeature.tags` dict explicitly (`{"name_source": ...} if ... else {}`, plus the pre-existing
`inner_rings`/`landcover_class` entries for areas) -- they never do `dict(raw_osm_tags)` or spread
the untrusted OSM tag dict wholesale. So a malicious/mischievous OSM contributor cannot plant a tag
literally named `name_source` (or `inner_rings`/`landcover_class`) to collide with or spoof a
reserved key; the reserved keys are always code-assigned, never copy-through.

**Why this matters generically**: this is the shape of check to redo any time a new reserved
`tags[...]` key is added (`store/models.py`'s reserved-tag convention) -- confirm the dict is
still built explicitly, not merged from the parser's raw tag dict (`osm/pbf.py`'s
`{tag.k: tag.v for tag in n.tags}` output), before approving.

Also confirmed in the same pass: the Latin-1 ingest-side name filter
(`_is_latin1_renderable`/`_select_name`) is incidental to security, not load-bearing for it --
`body-layer/belief/enrichment.py::displayable_name` independently re-applies the identical check
at render time, by design (the two subprojects don't share this logic via import). Don't treat the
ingest-side filter as the only thing standing between a hostile name string and the cockpit overlay
-- it isn't, and it was never meant to be.
