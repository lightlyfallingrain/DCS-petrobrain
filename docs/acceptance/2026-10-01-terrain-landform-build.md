# Terrain landform watershed — full-theatre build card

**Artifact card (cockpit-readable version of this document):**
https://claude.ai/artifact/AKXxX4R4R5a3tcztsR2qJC

**Checkout:** `git checkout feature/terrain-landform-features && git pull` (this will be `main`
once merged — confirm you're on the fix, not an older `main`, with `git log --oneline -3`).

**No DCS, no flight.** This is a desk/build task on whichever machine has the SRTM `.hgt` tiles and
`Syria.routes`/`towns.lua`/`beacons.lua` staged — normally your Windows box, since
`syria-full.sqlite` has never been built from this worktree (the real raw data is gitignored).
Per project rule, only you run a real full-theatre build — it is not something an agent can produce
or fabricate.

## What changed, in one line

The ridge/valley detector was replaced end to end: old per-cell curvature noise (11,749 ridges /
11,477 valleys on the 2026-09-30 `syria-full` build) is now a marker-controlled watershed gated on
relief and width. **Nothing in the cockpit changes from this build** — no callout differs, because
Stage 3 (adjacency), Stage 4 (bearing), and Stage 5 (the callout itself) are not built yet. This
build only replaces what gets written to `feature(kind='ridge'/'valley')` in the `.sqlite`.

## Setup

From `world-model/`, with the venv active (`.venv/bin/python ...` everywhere below):

```sh
cd world-model
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes \
    --srtm-dir data/raw/dem/syria-full/
```

This is exactly the Stage 2 command from `world-model/docs/M7_RUN_INSTRUCTIONS.md` — **no new
flag**. The terrain stage is unconditional: it runs automatically whenever any elevation grid
exists (confirmed by reading `build/pipeline.py` — `ingest_terrain` fires whenever
`load_full_grid(conn, "elevation")` returns a grid, no separate switch). This overwrites
`data/world-model/syria-full.sqlite`.

**What to expect in the build log** (timing/memory figures are an *estimate*, from the Performance
Reviewer's synthetic-grid measurement at real theatre shape — 2,555,208 cells — not from a real
`syria-full` run, since no agent has run one):

- The terrain stage ("terrain semantics (ridge/valley)") should take roughly **65-80 s**, against
  the old detector's measured 5.8 s — an 11-14x multiple that is a rounding error against the
  `.routes` walk (~430 s) and OSM ingest (25-30 min, not run here since M7 has no OSM).
- Peak RSS for that one stage: roughly **2 GB**. Not a concern against any stated constraint, but
  worth knowing if you're running this alongside DCS/Ollama on a memory-constrained box.

## Block A — counts, against the noise this replaces

```sh
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/world-model/syria-full.sqlite')
for row in conn.execute(\"select kind, count(*) from feature where kind in ('ridge','valley') group by kind\"):
    print(row)
"
```

**Expect:** both counts far below the old 11,749 ridges / 11,477 valleys — the whole point of this
change is fewer, real landforms instead of per-cell noise. There is no predicted exact number for
the full theatre (only three 20 km test regions were measured); a result in the hundreds-to-low-
thousands, not tens of thousands, is the signal that the gate is working as intended. If it comes
back anywhere near the old count, something regressed.

## Block B — fragmentation and sinuosity, against the three regions' prediction

```sh
.venv/bin/python -c "
import json, math, sqlite3, statistics
conn = sqlite3.connect('data/world-model/syria-full.sqlite')
for kind in ('ridge', 'valley'):
    rows = conn.execute('select geom_json, tags_json from feature where kind = ?', (kind,)).fetchall()
    n = len(rows)
    under_15 = 0
    sins = []
    for geom_json, tags_json in rows:
        coords = json.loads(geom_json)
        tags = json.loads(tags_json)
        if tags.get('cell_count', 999) < 15:
            under_15 += 1
        path = sum(math.hypot(coords[i+1][0]-coords[i][0], coords[i+1][1]-coords[i][1]) for i in range(len(coords)-1))
        end = math.hypot(coords[-1][0]-coords[0][0], coords[-1][1]-coords[0][1])
        if end > 0:
            sins.append(path / end)
    pct = 100.0 * under_15 / n if n else float('nan')
    med = statistics.median(sins) if sins else float('nan')
    print(f'{kind}: n={n}  pct_under_15_cells={pct:.1f}  median_sinuosity={med:.3f}')
"
```

**Expect** (predicted from the pooled result across `latakia-20km`/`baalbek-20km`/`palmyra-20km`,
independently reproduced twice by Reviewer against real SRTM data — never run at full-theatre
scale before this build):

| kind | % under 15 cells | median sinuosity |
|---|---|---|
| ridge | ~30% | ~1.22 |
| valley | ~22% | ~1.19 |

Against the old detector's 75% / 70% under-15-cells and 2.17 / 2.21 median sinuosity, this should
read as *materially less fragmented and far less zigzag* even if the exact full-theatre numbers
don't match the three-region figures precisely — a real theatre has terrain variety those three
regions don't.

## Block C — looking at it: `tools/inspect_terrain.py`

The tool renders a per-cell basin map (colour per basin, ridge/valley lines overdrawn) plus a
text report of every component's cell count, orientation, elevation range, and the gate values
that decided pass/fail. `--near NAME` centres the window on a named place already in the store
(exact match against `named_place`/`airfield`/`settlement`); `--radius-km` sets the half-width
(default 20).

**Verification note on everything below**: the flags (`--near`, `--center`, `--radius-km`,
`--out`) were run and confirmed against a small real `.sqlite` built through the actual pipeline
this session (`build_region` with a synthetic probe grid, not `syria-full`) — `--near` resolves
named places correctly and fails with a clear message when a name isn't found, `--center`/
`--radius-km`/`--out` all render as documented. **The specific invocations below
(`--near Baalbek`, `--near Palmyra`) are UNVERIFIED against real `syria-full` data** — no agent
has built or can build that store (gitignored real SRTM/DCS data, and per project rule only you
run the real full-theatre build). What *is* confirmed: both names come from this session's own
research notes as real `named_place` rows already present in `syria-full.sqlite`, with real DCS
coordinates on record (Baalbek x=-114453.8, z=25280.8; Palmyra x=-54775.0, z=217141.7) — so the
lookup should succeed, but the actual run against your real store is the first real test of it.

### THE PRIZE — Baalbek: the Bekaa must produce no valley

```sh
.venv/bin/python tools/inspect_terrain.py data/world-model/syria-full.sqlite \
    --near Baalbek --radius-km 20 --out /tmp/baalbek.png
```

**Why this is the one that matters.** The Bekaa is a kilometres-wide flat basin — at Mi-24 flight
profile and speed, calling the whole valley floor "a valley" the way a pilot would call a narrow
draw is meaningless; your own words, from the Explore conversation that redesigned this detector.
The old curvature detector got this wrong in the first full-theatre inspection
(`research/2026-10-01-terrain-features-full-build-inspection.md`) — the design was changed
specifically to fix it, and three region-scoped rebuilds (by the implementer, twice independently
by Reviewer) confirmed the Baalbek-window dominant basin (1,020 cells, ~1,274 m relief, ~13.7 km
core width against the 2,500 m width ceiling) correctly fails the width gate and produces zero
`valley` rows for the Bekaa body itself. **This full-theatre build is the first time that claim is
checked against the real, whole-theatre SRTM grid rather than a 20 km test window.**

**Record:** does the printed report show zero `valley` components whose cells fall in the Bekaa
floor itself? (A small, separate mountain-top basin near Baalbek is expected and fine — the test
regions' own result had one.)

### Palmyra: isolated ridge chains must still appear

```sh
.venv/bin/python tools/inspect_terrain.py data/world-model/syria-full.sqlite \
    --near Palmyra --radius-km 20 --out /tmp/palmyra.png
```

**Expect:** a handful of `ridge` components (3 in the 20 km test region) — isolated desert ridge
chains standing clear of the gate, not swallowed by it. Zero ridges here would mean the relief/
width gates are too strict for flat-desert-with-isolated-relief terrain, not just for the Bekaa.

### Latakia: the known-good region, for comparison

Latakia is **not** confirmed to exist as a `named_place` row in `syria-full` (unlike Baalbek/
Palmyra, whose `named_place` rows and exact DCS coordinates are on record in this session's
research notes) — use `--center` with `latakia-20km`'s own registered centre
(`src/build/region.py`) instead of `--near`, so this doesn't fail on a name-lookup miss:

```sh
.venv/bin/python tools/inspect_terrain.py data/world-model/syria-full.sqlite \
    --center 44934.892,5685.076 --radius-km 20 --out /tmp/latakia.png
```

An An-Nusayriyah-foothill region with real, varied relief — this is the region every tuning pass
in `research/2026-10-01-terrain-feature-probing-watershed-sweep.md` was checked against first. No
specific number to check; look at `/tmp/latakia.png` and the printed component list and judge
whether the lines read as real hills/valleys to you, the way the old checkerboard-noise classifier
never did.

## What is NOT yet true — say this plainly before you fly anything

**No callout changes as a result of this build.** This is Stages 1-2 only
(`plans/terrain-feature-probing/plan.md`) — the detector and its tuning. Stage 3 (landform
adjacency), Stage 4 (bearing in `describe_position`), and Stage 5 (the actual
*"at the foot of the hill"* / *"next valley"* callout) are not implemented. If you fly expecting
Petrovich to say anything different, you will be disappointed for no reason — this build only
changes what a `.sqlite` inspection tool shows you, not what reaches the cockpit.

## Bring back

- Ridge/valley counts (Block A) — in the hundreds/low-thousands, or still near the old 11k+11k?
- Fragmentation/sinuosity (Block B) — materially better than 75%/70% and 2.17/2.21?
- Baalbek (the prize): zero valleys over the Bekaa floor itself, yes or no?
- Palmyra: ridges still present, yes or no, how many?
- Latakia: does the render look like real terrain to your eye?
- Anything that surprised you is worth more than anything on this list.
