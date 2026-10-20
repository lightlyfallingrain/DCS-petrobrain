---
name: landmark_words_area_m2_tag_trust
description: world-model's StoredFeature.tags (a json.loads-deserialized dict[str, Any]) has no schema/type validation at any describe.py read site, including the new SettlementInfo.area_m2 -- assessed as no realistic attack path in this single-player/LAN-only project, not a vulnerability to fix per-feature.
metadata:
  type: project
---

Checked during `landmark-words-no-names` (F7) security deep analysis, 2026-10-20.
`world-model/src/query/describe.py:444` added `area_m2=feature.tags.get("area_m2")` to
`_settlement_info`, read downstream by `body-layer/src/belief/enrichment.py`'s
`_settlement_size_word` in a `<` comparison against a tunable. A non-numeric `tags["area_m2"]`
would raise `TypeError` there rather than degrade.

**Why this was not filed as a finding needing a fix:**

1. **The write side is code-assigned, not copy-through.** `ingest_osm.py:644` always sets
   `tags: dict[str, Any] = {"area_m2": net_area_m2}` with `net_area_m2` a computed `float`
   (shoelace formula, `ring_area_m2`) — same "reserved tag keys are code-assigned, never spread
   from raw OSM tags" shape as [[project_wm_b1_name_tags_not_merged_from_raw_osm]]. There is no
   ingest-time path for a hostile OSM contributor to inject a wrong-typed `area_m2`.
2. **The read side (`feature.tags.get(...)` on an unchecked `json.loads` blob) is a pre-existing
   pattern**, not new to this feature — `describe.py:462`/`502` (`_preferred_settlement`) already
   read the same tag the same unchecked way, two functions above this change.
3. **The only way to get a wrong-typed value in there at all is a hand-corrupted or foreign
   `.sqlite` store** — a local build artifact the project's own offline pipeline produces, which
   `body-layer/CLAUDE.md` already documents as something *the user* manually copies between
   machines (no sync mechanism, no runtime download). In a single-player, LAN-only project, the
   only party who could substitute a bad store is the store's own owner — there is no attacker
   model where this crosses a trust boundary.

**How to apply generically:** when a plan adds a new `describe.py` field sourced from
`feature.tags.get(...)`, don't re-litigate whether the tags dict should be schema-validated — it's
an accepted, already-reasoned trust boundary (reasserted here, originally reasoned in
[[project_wm_b1_name_tags_not_merged_from_raw_osm]]). Check instead (a) whether the *write* side
is still code-assigned rather than spread from raw external data, same as that memory's check, and
(b) whether anything in the new plan changes who can substitute the `.sqlite` store at runtime (it
would need to, for this reasoning to lapse — e.g. a future networked/shared-store scenario this
project is explicitly not building yet, root `CLAUDE.md`'s single-player scope).

See `plans/landmark-words-no-names/security-review.md` for the full disposition.
