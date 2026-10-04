# Full-theatre rebuild — geomorphons landforms + Latin-script names

**STATUS UPDATE, 2026-10-04.** This build ran (that's how `WM-B1`'s Block A/B were confirmed and
how the `fix/landform-relief-gate` defects below were found). `WM-B1` is fully cleared by it —
nothing left to re-check. The terrain half is **superseded**: that run exposed two real defects
(no relief gate, geometry ~16x denser than the DEM supports), now fixed on
`fix/landform-relief-gate`, which requires a *new* `syria-full` rebuild (the terrain cache fully
invalidates). Use `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` /
https://claude.ai/artifact/S6sod3ZdB1mCWSYj8twCPP for that re-run — it only asks about what
changed, not a repeat of Blocks A/B/C below.

**Artifact card (read this at the desk running the build):**
https://claude.ai/artifact/DKf9eTTWKmJtAKmKF96FdW

**Checkout.** Both features land on `main` once the orchestrator sequences the merge following
this DoD pass — `git checkout main && git pull`, then confirm with
`git log --oneline -5` that you see `Merge feature/landform-geomorphons` *and*
`Merge fix/latin-place-names` in the history. If you only see the Latin-names merge, the
geomorphons branch hasn't landed yet — wait for it, since this card's terrain blocks need it.

**No DCS, no flight.** This is a desk/build task on whichever machine has the real SRTM `.hgt`
tiles, `Syria.routes`, `towns.lua`/`beacons.lua`, and the merged `syria-theatre.osm.pbf` staged —
normally your Windows box. Per the project's execution-boundary rule, only you run a real
full-theatre build; no agent has built or can build `syria-full.sqlite` (the raw data is
gitignored).

## Why one build for two features

`WM-B1` (Latin-script place names) and `WM-B6` (geomorphons ridge/valley) both only take effect on
a full-theatre rebuild, and nothing else in either feature requires one of its own — so they ride
the same rebuild rather than costing you two. `WM-B1`'s own roadmap entry already names this
rebuild as the thing that verifies it; this card carries that verification query forward alongside
`WM-B6`'s.

## What changed, in one line

**`WM-B6`**: the parked marker-controlled-watershed ridge/valley detector is replaced end to end by
geomorphons classification run at native SRTM resolution (~90 m, not the old 500 m grid),
vectorised, skeletonised, traced through junctions, and Chaikin-smoothed — cached per SRTM tile so
a rebuild doesn't redo the expensive pass. **`WM-B1`**: OSM-sourced place names now prefer a
Latin-script `name:en`/`int_name` over the raw (often Arabic) `name` tag, so more features render
in the cockpit instead of falling back to a generic label.

**Nothing in the cockpit changes from either.** `WM-B6`'s Stages 3-5 (landform adjacency, bearing,
the actual "at the foot of the hill" / "next valley" callout) remain unbuilt — this build only
changes what lands in `feature(kind='ridge'/'valley')` and in `tags_json.name`/`name_source`.

## Setup

From `world-model/`, with the venv active:

```sh
cd world-model
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes \
    --srtm-dir data/raw/dem/syria-full/ \
    --osm-pbf data/raw/osm/syria-theatre.osm.pbf
```

Read directly from `tools/build_world_model.py` as it stands on the merged branch — no new flag
for either feature. `--srtm-dir` triggers the terrain (geomorphons) stage unconditionally once any
`.hgt` tiles are found; the terrain cache's path is derived automatically from the output
`.sqlite` path, no flag needed. `--osm-pbf` triggers OSM ingest, which is where the Latin-name
preference applies. This overwrites `data/world-model/syria-full.sqlite`.

### What to expect while it runs

**Terrain stage timing is an extrapolation from 27 real tiles sampled across the theatre, not a
measured full run** — no agent can run the real 131-tile build (execution-boundary rule). Expect:

- **≈ 14 minutes of CPU time** for the terrain stage specifically (down from an earlier ~25-minute
  estimate, after a performance fix to the smoothing step — see `world-model/ROADMAP.md`'s `WM-B6`
  entry for the before/after numbers).
- **One progress log line per SRTM tile**, 131 tiles total.
- **Peak RSS for the terrain stage under ~1.8 GB** — measured directly (not extrapolated) by
  streaming 27 real tiles through the actual pipeline and tracking `ru_maxrss`; it plateaus after
  the largest single tile rather than growing with cumulative theatre size, which is the property
  that was fixed (the original version grew unbounded toward an estimated 29+ GB).
- OSM ingest and the `.routes` walk are unchanged by this branch — their own timing is whatever
  your last `syria-full` build already showed.

### Resumability

**If you interrupt the build, re-running the same command skips SRTM tiles already processed.**
The terrain cache is a separate file from the base `.sqlite` (same pattern as the existing OSM
classified-feature cache), keyed per tile, and survives even though the base store itself is
always deleted and rebuilt from scratch on every run. This is verified by a direct unit test
(`test_ingest_terrain_resumes_a_partially_completed_cache`) and by a cold-vs-warm timing
measurement on one real tile (16.65 s cold, 0.75 s warm — ≈22x) — **not** by an actual kill of a
live 131-tile process, which no agent can run. The OSM stage has its own independent cache from an
earlier milestone and resumes the same way.

## Block A — ridge/valley counts, and why this comparison needs a caveat

```sh
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/world-model/syria-full.sqlite')
for row in conn.execute(\"select kind, count(*) from feature where kind in ('ridge','valley') group by kind\"):
    print(row)
"
```

**The old watershed detector's full-theatre counts were 8,189 ridges / 2,314 valleys** — one
feature per *basin boundary*. Geomorphons classifies and traces at the cell level instead, so it is
not the same kind of count and a much larger number is the **expected, intentional** result, not a
regression: a 27-tile sample during performance testing averaged ≈9,816 combined ridge+valley
features per tile, extrapolating to roughly **1.3 million** theatre-wide. This was already flagged
during design as an open product question (too many lines to ever *speak*, a separate
consolidation problem for when Stage 5 is built) — it is not something to be alarmed by here. What
*would* be a regression: counts near zero (detector found nothing) or counts wildly inconsistent
with the per-window numbers below (something broke between a single-window run and a full-theatre
one).

## Block B — WM-B1: did the Latin-name preference take effect?

```sh
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/world-model/syria-full.sqlite')
row = conn.execute('''
  select
    sum(case when json_extract(tags_json, '\$.name_source') = 'name:en' then 1 else 0 end) as via_name_en,
    sum(case when json_extract(tags_json, '\$.name_source') = 'int_name' then 1 else 0 end) as via_int_name,
    sum(case when json_extract(tags_json, '\$.name_source') is not null then 1 else 0 end) as any_name_source,
    count(*) as total
  from feature
  where kind in ('named_place', 'settlement')
''').fetchone()
print(row)
"
```

**Expect** (from `world-model/ROADMAP.md`'s `WM-B1` entry, measured against the real merged
extract ahead of this rebuild): `via_name_en` near 12,926, `via_int_name` near 864 (summing to a
13,073-row yield), out of 49,226 `named_place`/`settlement` rows. A result far off this means the
fix did not take effect as expected and needs a debugger pass before `WM-B1` can be called verified
rather than merely merged.

## Block C — the coastal-hills window, reproduced exactly

```sh
.venv/bin/python tools/inspect_terrain.py \
    --srtm-dir data/raw/dem/syria-full/ --center -5000,15000 --radius-km 8 \
    --out /tmp/coastal-hills.png
```

**Expect:** `ridge: 299 lines, longest 7.18 km` and `valley: 289 lines, longest 7.70 km` — this is
the exact command and exact output this DoD pass independently reproduced against the real SRTM
tiles, not a prediction. The rendered PNG should look like the committed
`world-model/data/renders/coastal-hills-geomorphons.png` (continuous multi-kilometre crests through
junctions, not fragmented stubs).

## Block D — THE PRIZE: Baalbek, the Bekaa must still not read as a valley

```sh
.venv/bin/python tools/inspect_terrain.py \
    --srtm-dir data/raw/dem/syria-full/ --center -114453.8,25280.8 --radius-km 20 \
    --out /tmp/baalbek.png
```

**Why this is the one that matters.** The Bekaa is a kilometres-wide flat basin — calling the
whole valley floor "a valley" the way a pilot would call a narrow draw is meaningless, and this was
the specific defect that got the old watershed detector parked. This DoD pass ran this exact
command against the real theatre SRTM tiles and the flat Bekaa floor itself is clean — no
ridge/valley lines cross it; all detected lines sit on the bordering mountain slopes. **Your own
look at `/tmp/baalbek.png` is still the real acceptance test** — this is the thing the user judges
by eye, not a count.

## Block E — Palmyra, isolated ridge chains must still appear

```sh
.venv/bin/python tools/inspect_terrain.py \
    --srtm-dir data/raw/dem/syria-full/ --center -54775.0,217141.7 --radius-km 20 \
    --out /tmp/palmyra.png
```

**Expect:** long, isolated ridge chains crossing otherwise flat desert — this DoD pass's own run of
this exact command shows exactly that pattern against the real tiles. Zero or fragmented-only
ridges here would mean the classifier is too conservative for flat-desert-with-isolated-relief
terrain.

## What is NOT fixed — say this plainly before you build anything else on top

- **Region-scoped builds (e.g. `latakia-20km`) do not clip terrain output to the region's bbox.**
  `ingest_terrain`'s processing unit is one whole SRTM tile regardless of which region is being
  built, so a region-scoped rebuild stores *every* ridge/valley line any covering tile produces —
  not just the region's own ~20-40 km extent. This does not affect the full-theatre build above
  (every tile is already in-theatre there) but will produce out-of-region geometry on the next
  `latakia-20km` rebuild. Known, documented, not fixed — see `world-model/ROADMAP.md`'s `WM-B6`
  entry.
- **Nothing in the cockpit changes.** Stages 3-5 (landform adjacency, bearing in
  `describe_position`, the actual callout) remain unbuilt. Don't fly expecting Petrovich to say
  anything different about terrain — this build only changes what two inspection
  tools/queries show you.
- **A two-adjacent-tile seam was never exercised against real SRTM data**, nor was a literal
  kill-mid-build test of the resume mechanism (see "Resumability" above) — both are verified at the
  unit-test level only.

## Bring back

- Block A — ridge/valley counts: in the hundreds-of-thousands-to-low-millions range (not near zero,
  not wildly off the 27-tile extrapolation)?
- Block B — WM-B1 name-source counts: close to the predicted 12,926 / 864 / 13,073-of-49,226?
- Block C — coastal-hills: does your own run match 299/289, 7.18 km/7.70 km?
- Block D (the prize) — Baalbek: does the Bekaa floor read clean to your eye?
- Block E — Palmyra: are the isolated chains there, and do they look right?
- Anything that surprised you is worth more than anything on this list.
