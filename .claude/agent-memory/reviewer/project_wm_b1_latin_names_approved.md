---
name: wm-b1-latin-names-approved
description: WM-B1 (Latin-1 romanisation preference at OSM ingest) reviewed APPROVED clean; how the cache-invalidation and duplicated-check checks were verified.
metadata:
  type: project
---

`fix/latin-place-names` (bbdb1ef) reviewed APPROVED, no required fixes. `build.ingest_osm._select_name`
prefers `name:en`/`int_name`/`name` by Latin-1-renderability, tags the winner as reserved
`tags["name_source"]`, `CLASSIFIER_VERSION` 4→5.

**Technique used, reusable for the next `CLASSIFIER_VERSION`-bump review**: don't just read
`cache_meta_matches` — construct a stale `OsmCacheMeta(classifier_version=<old>)` vs current and call
it directly. Also check the pipeline's `expected_meta` reads the live module constant, not a captured
value, at the call site (`build/pipeline.py` around the `_stage("OSM overlay...")` block) — both took
under a minute and catch the exact "fix appears to do nothing after rebuild" failure mode this
project has been burned by before ([[feedback_rerun_mypy_dont_trust_log]] is the analogous "don't
trust the log" lesson for mypy; this is the cache-invalidation analogue).

**Found one real but minor gap**: the implementer claimed "both docstrings point at each other with
a keep-in-sync note" for the duplicated Latin-1 check (`world-model`'s new `_is_latin1_renderable` vs
`body-layer`'s pre-existing `belief.enrichment.displayable_name`). Only the world-model side actually
has that note — body-layer's docstring predates the fix and still reads as if `WM-B1` were open.
The two checks *do* agree today (verified by reading both), so this is pure doc staleness, not a
silent-half-fix — but it's a reminder that an implementer's self-report about "both sides" of a
flagged duplication needs the same verify-don't-trust treatment as everything else: read both files,
not one.

Measured counts (19,553/49,226 non-Latin-1; 13,073/67% gain a romanisation; 6,480/33% don't) were
spot-checked against the roadmap entry only, not re-derived from the real store — full-theatre
builds are the user's to run per project rule, and this branch's own log already did the real-data
measurement.
