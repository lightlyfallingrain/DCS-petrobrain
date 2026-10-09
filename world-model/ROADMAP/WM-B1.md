# WM-B1 — Prefer a Latin-script place name at OSM ingest

- [x] **WM-B1 — Prefer a Latin-script place name at OSM ingest.** #status/done Named places currently store OSM's `name`
  tag verbatim, so Syrian features arrive in Arabic script — and **DCS cannot render non-Latin-1
  text**, so they reach the cockpit overlay as blanks (observed live, 2026-09-18). Body-layer now
  guards at render time (`belief.enrichment.displayable_name` drops an unrenderable name so the
  caller falls back to "a wadi"/"a village"), which makes the current data usable but loses real
  information: many of these features *do* have an `name:en` or `int_name` tag carrying a perfectly
  good romanisation. Fix at ingest: prefer `name:en`, then `int_name`, then `name`, and record which
  was used. Needs a rebuild to take effect, so it should ride along with the next full-theatre run
  rather than triggering one.

  **Implemented, `fix/latin-place-names`** (2026-10-02). `build.ingest_osm._select_name` picks the
  first of `name:en`/`int_name`/`name` that both exists and actually encodes as Latin-1 (a
  romanisation can itself still fail that check), applied uniformly across every classified kind
  that carries a name — `named_place` (point and dam-line), `water`/`coastline` lines, and
  `settlement`/`landcover` areas via `_ingest_ring`, not just the one kind the item names. Which tag
  won is recorded as a new reserved `tags["name_source"]` entry (`store/models.py`'s existing
  convention; no schema change, `tags` is already a generic JSON blob) — `"name:en"`, `"int_name"`,
  or `"name"` (the last also covers the no-romanisation-available fallback, so a feature that would
  previously have stored an untranslatable name unmarked still does, just now distinguishable from an
  actual romanisation). `CLASSIFIER_VERSION` bumped 4 → 5 to force `osm-classified-cache` invalidation
  (verified: `cache_meta_matches` compares it against the cached meta, so a stale `CLASSIFIER_VERSION
  = 4` cache is correctly rejected rather than silently served). Renderability is checked with the
  same `name.encode("latin-1")` test as body-layer's `belief.enrichment.displayable_name`, but **not
  imported from it** — `body-layer` → `world-model` is the one sanctioned in-process cross-subproject
  import (root `CLAUDE.md`'s "Module independence"), and the reverse direction would be a new,
  unjustified coupling; both copies' docstrings say to keep them in sync by hand.

  **Measured against the real `syria-full` build** (`data/world-model/syria-full.sqlite` +
  `data/raw/osm/syria-theatre.osm.pbf`, read-only copies, never the live files): of 49,226
  `named_place`/`settlement` rows, 19,553 (40%) currently store a non-Latin-1 name — not only Arabic;
  this theatre's merged extract also carries Greek/Hebrew/Turkish names outside Syria proper. Of
  those, **13,073 (67%) have a usable `name:en` or `int_name` in the source `.osm.pbf`** (12,926 via
  `name:en`, a further 864 via `int_name` where `name:en` was absent or itself unrenderable) — this
  fix's real yield on the next rebuild. The remaining 6,480 (33%) have neither tag, or neither
  renders, and keep falling back to the raw non-Latin-1 name, same as before — body-layer's
  render-time guard still degrades those to a generic label. Worth saying plainly: a third of the
  affected features gain nothing from this change; it is a real improvement, not a complete fix.

  Full detail: `plans/latin-place-names/implementation.md`.

  **DoD (2026-10-02): Reviewer and Security both APPROVED, no required fixes; mechanical checks
  (`ruff format`/`check`, `mypy --strict`, `pytest`) independently reproduced — 511 passed, 3
  skipped, 20 new tests, zero regressions against `main`'s 491/3 baseline. No separate acceptance
  card: this change produces zero observable effect until a full-theatre rebuild runs (the user's
  to trigger), expected to ride along with [[WM-B6]]'s rebuild rather than its own. So this `[x]` means
  code merged and gated, not verified against real output yet — that verification is the following
  check, to run against `syria-full.sqlite` once that rebuild completes:**

  ```sql
  SELECT
    SUM(CASE WHEN json_extract(tags_json, '$.name_source') = 'name:en' THEN 1 ELSE 0 END) AS via_name_en,
    SUM(CASE WHEN json_extract(tags_json, '$.name_source') = 'int_name' THEN 1 ELSE 0 END) AS via_int_name,
    SUM(CASE WHEN json_extract(tags_json, '$.name_source') IS NOT NULL THEN 1 ELSE 0 END) AS any_name_source,
    COUNT(*) AS total
  FROM feature
  WHERE kind IN ('named_place', 'settlement');
  ```

  (table/column names confirmed against `world-model/src/store/schema.py`'s real `CREATE TABLE
  feature (... tags_json TEXT ...)` — not guessed from the ORM-style naming `StoredFeature`/`tags`
  might suggest.) `name_source = 'name'` covers both an already-Latin-1 name that never needed
  romanising *and* the 6,480 still-unrenderable fallback rows, so SQL alone can't isolate the
  "gained nothing" count — follow with a Python pass over rows where `name_source = 'name'`,
  checking `name.encode("latin-1")` the same way `_is_latin1_renderable` does, and count the
  failures. Predicted: `via_name_en` near 12,926, `via_int_name` near 864 (summing to the
  13,073-row yield), and roughly 6,480 of the `name_source = 'name'` rows failing that Python-side
  encode check. A result far off any of these means the fix did not take effect as expected on the
  real extract and needs a debugger pass before this item can be called verified, not just merged.

  **Milestone Completion question**: this does not change what the next milestone should be or
  invalidate a downstream assumption — it is a localized data-quality improvement inside the
  existing OSM ingest pipeline; [[WM-B6]] (geomorphons), already in flight, is unaffected in either
  direction, and no other roadmap item depended on `name`/`name_source` having a particular shape
  before this landed.

Its live-acceptance-debt record follows. The source document kept that list at the head of the
file, away from the entry it was about; both are reproduced here, with the entry first so that its
own checkbox and `#status/*` tag are the entry's state, and the dated clearance note below it.

- [x] **`fix/latin-place-names` (`WM-B1`) — cleared by the user's 2026-10-02 `syria-full` build.** #status/done
  Name-source counts landed exactly as predicted: `via_name_en`≈12,926, `via_int_name`≈864,
  13,073-of-49,226. No outstanding item.
