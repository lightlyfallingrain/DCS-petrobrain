# Relief gate + geometry decimation — re-run the `syria-full` terrain rebuild

**Artifact card:** https://claude.ai/artifact/S6sod3ZdB1mCWSYj8twCPP

**This supersedes the terrain half of `docs/acceptance/2026-10-02-geomorphons-latin-names-
rebuild.md`.** That card's build already ran (you ran it) and is how these two defects were
found, so it is not a repeat — most of what it asked for stands verified. This card is the
*re-run*, scoped to only what the relief-gate/decimation fix changes.

## What the 2026-10-02 build already verified — don't re-check these

- **`WM-B1` (Latin-script place names): fully verified, cleared.** Name-source counts landed
  exactly as predicted (`via_name_en`≈12,926, `via_int_name`≈864, 13,073-of-49,226). No action
  needed on this card.
- **`WM-B6` raw extraction at theatre scale: verified, mechanism confirmed.** The build produced
  `ridge=700,142, valley=740,255` — matching the branch's own measured figures exactly — so the
  geomorphons extraction, tracing, caching and store-write path all work correctly at full
  131-tile scale. That part of the pipeline is not being re-tested.

## What that build also found, and this branch fixes

Checking your own `syria-full.sqlite` against your own acceptance criteria
(`plans/terrain-feature-probing/explore-notes.md`'s ~50-150 m "maskable-behind" band) found two
real defects: **no relief gate** (89-92 % of stored ridges/valleys under 50 m of relief, and the
Bekaa floor at Baalbek read as a valley — exactly the case your own criteria rule out) and
**stored geometry ~16x denser than a 90 m DEM supports** (`feature` was 7.98 of the store's
8.1 GB). Both are fixed on `fix/landform-relief-gate` — see
`plans/landform-relief-gate/implementation.md` for the full account.

**This rebuild is what re-verifies the fix at theatre scale** — everything below is new
measurement, not a repeat of Block A/B from the 2026-10-02 card.

## Checkout

```sh
git checkout main && git pull
git log --oneline -5   # look for "Merge fix/landform-relief-gate"
```

## Setup — the terrain cache will fully invalidate, on purpose

**`EXTRACTOR_VERSION` went `1 -> 2`, and the cache key gained two new fields
(`min_relief_m`, `decimation_tolerance_fraction`).** Your existing terrain cache (built
2026-10-02, ~7.4 GB) has neither — its `meta` table predates both knobs, so
`terrain_cache.reader.load_cache_meta` returns "no stored identity" and the pipeline reprocesses
every tile from scratch. **This means the ~14-minute terrain stage runs again in full, not the
~22x-faster warm path** (0.75 s/tile instead of 16.65 s/tile) — that is correct and intended for
this rebuild, not a regression. Everything else (OSM ingest, roads, towns/beacons) is unaffected
and reads warm as before.

Run from `world-model/`, with the venv active — the command itself is unchanged, no new flag:

```sh
cd world-model
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes \
    --srtm-dir data/raw/dem/syria-full/ \
    --osm-pbf data/raw/osm/syria-theatre.osm.pbf
```

This overwrites `data/world-model/syria-full.sqlite`. Expect **≈14 minutes** of terrain-stage CPU
time (full cold reprocess, per the figure above), same order as the first build.

## Block A — did the relief gate hold? (expected: zero violations)

```sh
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/world-model/syria-full.sqlite')
rows = conn.execute('''
    select kind, count(*) from feature
    where kind in ('ridge', 'valley')
      and json_extract(tags_json, '\$.elevation_range_m[1]')
          - json_extract(tags_json, '\$.elevation_range_m[0]') < 50.0
    group by kind
''').fetchall()
print('violations (should be empty):', rows)
"
```

**Expect: an empty list.** Any row means a line with less than 50 m of relief made it into the
store — the gate did not hold. (Verified: this exact query's logic was run here against a
schema-matching synthetic store, correctly flagging an injected 22 m-relief row and correctly
passing a 100 m-relief row — real `tags_json.elevation_range_m` is stored as `[min, max]`, same
shape used above.)

## Block B — ridge/valley counts and store size

```sh
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/world-model/syria-full.sqlite')
for row in conn.execute(\"select kind, count(*) from feature where kind in ('ridge','valley') group by kind\"):
    print(row)
"
du -sh data/world-model/syria-full.sqlite
```

**Expect:** ridge+valley combined roughly **16 %** of the 2026-10-02 build's 1,440,397 (i.e.
roughly 230,000-240,000, close to the 234,799 figure already measured directly against your
existing store before this rebuild — that number is a direct SQL query result, not an
extrapolation, and should not move once the fix is in). Store size **~2.4-2.5 GB** — this part
**is** extrapolated (from a 36.5-36.7x measured geometry-byte reduction on real sample data, not
from a full-theatre run) and is the single biggest "did the prediction hold" number on this card.
Anywhere far from that range is worth a debugger pass before calling this fix verified rather
than merely merged.

## Block C — the falsifiable checks, same renders as before

`tools/inspect_terrain.py` was rewritten on this branch to render exactly what gets stored
(relief-gated, decimated geometry) instead of the raw traced skeleton it drew before — **every
terrain render this project judged landforms by prior to this branch was showing something other
than what the store holds.** These are the first renders that show the real thing.

```sh
.venv/bin/python tools/inspect_terrain.py \
    --srtm-dir data/raw/dem/syria-full/ --center -114453.8,25280.8 --radius-km 20 \
    --out /tmp/baalbek-relief-gate.png

.venv/bin/python tools/inspect_terrain.py \
    --srtm-dir data/raw/dem/syria-full/ --center -54775.0,217141.7 --radius-km 20 \
    --out /tmp/palmyra-relief-gate.png
```

(Both commands run here end-to-end against synthetic `.hgt` tiles built to the real SRTM naming
convention and byte layout, to confirm the flags/argument order are exactly right — they are
unchanged from the 2026-10-02 card.)

**Baalbek — the prize, again.** Your own eye on `/tmp/baalbek-relief-gate.png`: does the Bekaa
floor stay clean of ridge/valley lines, same as the committed
`world-model/data/renders/baalbek-relief-gate.png`? This DoD pass's own read-only query against
your existing (pre-rebuild) store already confirms the specific 22 m-relief valley near Baalbek
is exactly the kind of row the gate removes, and the committed render shows the gated result —
this rebuild should reproduce the same picture at full scale.

**Palmyra.** Does `/tmp/palmyra-relief-gate.png` still show the long isolated ridge chain (~6+ km)
crossing flat desert, same as the committed `palmyra-relief-gate.png`?

## What is NOT re-tested here

- `WM-B1`'s name-source counts and the coastal-hills count/length figures from the 2026-10-02
  card — already cleared, see above.
- The region-scoped-build-doesn't-clip-to-bbox gap — unrelated to this fix, still open, see
  `world-model/ROADMAP.md`'s `WM-B6` entry.
- Nothing in the cockpit changes from this fix either — Stages 3-5 (landform adjacency, bearing,
  the callout) remain unbuilt.

## Bring back

- Block A — any relief-gate violations (expect zero)?
- Block B — ridge/valley count near 230-240k, store size near 2.4-2.5 GB?
- Block C — Baalbek clean, Palmyra chains intact, by your own eye?
- Which rebuild (date/host) cleared this, so `world-model/ROADMAP.md`'s live-acceptance-debt list
  can be closed out.
