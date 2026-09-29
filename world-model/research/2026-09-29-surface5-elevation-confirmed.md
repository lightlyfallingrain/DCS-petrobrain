# `Syria.surface5` does encode elevation — confirmed against DCS ground truth

**Date:** 2026-09-29
**Machine:** the Windows box (DCS installed).
**Theatre:** Syria. **DCS version:** as installed (`Mods/terrains/Syria/surface/Syria.surface5`,
30,426,200,576 bytes, mtime 2026-06-25).

### Question

The timeboxed `.surface5` decode spike from `docs/handoff/2026-09-29-windows-dcs-session.md` Task 3,
framed there — correctly — as **a disproof attempt**: two ED forum threads were read on 2026-09-29
and found to contain no prior art, the one person publicly asking this exact question gave up and
used a Lua script instead, and `2026-09-05-m7-terrain-mesh-elevation-relitigation.md` Finding 5 rested
on a single float-magnitude pattern match at one byte offset, never cross-checked against anything.

The decisive test named in that note: decode a node's anchor point and compare it to `land.getHeight`
at the same (x, z).

### Base

`git rev-parse HEAD` → `7b4d2b2` (`main`), branch `investigate/terrain-elevation-source`.
Read-only against the DCS install throughout, per `world-model/docs/CONVENTIONS.md`.

### Findings

**1. The container is a self-describing columnar format, and its node-descriptor region is
front-loaded into the first ~130 MB of the 30.4 GB file.**

- **evidence: reproduced-locally** — **source:** `tools/probe_surface5_elevation.py`, run against
  the installed file.
- Header: `<u32 version=2><u32 48><u64 273400528>`, 20 zero bytes, then
  `<u32 24>landscape5::Surface5File`.
- Each descriptor record carries length-prefixed ASCII field names — `Surface5.0`, `Land`,
  `shaderDefine`, `NODEFINITIONS`, `Pbase`, `nextLodIndex`, `Nbase`, `maxEdge`, `depth`, `TRITYPE`,
  `TRI` — each preceded by its own `<u32 namelen>`, which is what makes the walk safe (the bare
  strings also occur inside payload often enough to poison an unvalidated scan).
- **Records stop between 100 MB and 150 MB.** Sampling at twelve points across the file found
  descriptors only in the first chunk and none at 2.5 GB or beyond: the remaining ~30.3 GB is `TRI`
  payload. **9,769 descriptors** were recovered, covering **194,573,812 nodes**.
- Record length varies, so the walk anchors on `TRITYPE` — the transform block sits at a fixed
  `-0x44` (origin) and `-0x34` (local bbox) from it.

**2. Every record carries a world tile origin and a local bounding box, and `world = origin + bbox`
is the correct geo-referencing.**

- **evidence: reproduced-locally** — **source:** as above, checked against 129 real
  `land.getHeight` samples.
- The bbox is six float32: `(x_min, y_min, z_min, x_max, y_max, z_max)` in tile-local metres, with
  **y as elevation**, plus a separate three-float world origin. Median tile is **9,009 m** across.

**3. The y-axis is DCS elevation. This is the finding, and it is not a magnitude match — it is
129/129 against ground truth, with a null control.**

- **evidence: reproduced-locally** — **source:** `Saved Games/DCS/Logs/terrain_probe_output.jsonl`
  (121 points, M5 grid probe, 2026-09-10) and `elevation_probe_output.jsonl` (8 scattered airfield
  points, M4 spot-check, 2026-09-06) — both produced by DCS's own `land.getHeight` through
  mission-editor triggers, so they are DCS ground truth, not SRTM.
- For each of the 129 points, the **smallest** containing tile was selected and its y-range checked:

  | test | result |
  |---|---|
  | covered by some tile | 129/129 |
  | true height strictly inside that tile's `[y_min, y_max]` | **129/129** |
  | median y-range width of those tiles | 253.2 m (max 574.4 m) |
  | **null control** — same test, heights shuffled between points | **mean 71.1/129, best of 200 trials 82** |

- The null control is what makes this evidence rather than arithmetic. A 253 m band over a 9 km tile
  is not a catch-all: reassigning the heights at random passes barely half the time, and 200 shuffles
  never got past 82. Going from 71 to 129 by using the *correct* pairing is not something a wrong
  decode does.
- Cross-checks that agree independently: y-maxima across records reach **3,093 m** (Syria's map
  includes Taurus terrain around 3,000 m; Mt Hermon is 2,814 m), and the derived world extents cover
  the theatre bbox established in `2026-09-05-m7-syria-theatre-extent.md`
  (x −421,912…345,432; z −320,235…390,775).

**This promotes Finding 5 of `2026-09-05-m7-terrain-mesh-elevation-relitigation.md` from "inferred,
plausible field-name/magnitude match" to "reproduced-locally, confirmed."** The disproof attempt
failed to disprove it.

**4. The mesh is far denser than anything currently in the pipeline — 114 m median node spacing
against the shipped grid's 1,000 m.**

- **evidence: reproduced-locally (node counts and tile areas) + inferred (spacing is
  `sqrt(area/nodes)`, i.e. an average, not a measured grid step)** — **source:** as above.
- `sqrt(area/nodes)`: **min 13.3 m, p10 37.6 m, median 113.9 m**. The shipped SRTM grid is 1,000 m
  with a measured 11.52 m stddev against DCS (`world-model/ROADMAP.md`), which is the error that
  caused the missed-AAA defect.
- **Caveat that matters:** nodes are LOD-quadtree mesh vertices, not a regular grid, and the same
  ground is covered at several LOD levels. This is a density figure, not a guaranteed sample spacing.

**5. Per-node elevation values were NOT decoded, and this is where the spike stops.**

- **evidence: reproduced-locally (a failed decode, stated as such)**.
- Each field entry is `<u16 type><u32 elemsize><u16 ?><u64 count><u64 offset>`. For `Pbase`:
  `type=2, elemsize=12` (3 floats — a position), `count = 3 × nodes` exactly, across every record
  checked.
- An attractive hypothesis — that `count` is a byte length and positions are 8-bit-quantised per
  axis into the tile bbox — is supported by the offsets being spaced exactly `count` bytes apart.
  **It is wrong.** Reading the bytes at `Pbase`'s stated offset (`0x1b18` for record 1) lands inside
  a *later descriptor record*, not a payload: float32 `1.0`s, a transform block and a `TRITYPE`
  string. So the u64 is not a file offset, the payload was not located, and no per-node height was
  read.
- **What exists today is therefore a per-tile min/max envelope**, correct and confirmed, but an
  envelope. A 9 km tile with a 253 m band is useless for line-of-sight: the AAA defect needs a height
  at a point, to within metres.

### Reproducible Test

```sh
cd world-model && .venv/bin/python tools/probe_surface5_elevation.py \
  --surface5 "$DCS_INSTALL_PATH/Mods/terrains/Syria/surface/Syria.surface5" \
  --ground-truth "$DCS_SAVED_GAMES_PATH/Logs/terrain_probe_output.jsonl" \
  --ground-truth "$DCS_SAVED_GAMES_PATH/Logs/elevation_probe_output.jsonl"
```

Run 2026-09-29; output is Findings 1–4 verbatim. Reads ~150 MB, takes seconds, never touches the
30.3 GB payload. The tool is a throwaway investigation script — nothing imports it.

### Recommendation: probe, not files

**The handoff asked for a clear answer to "probe, files, or neither". It is probe**, and the reason
is not that the file route failed — it is that the file route succeeded at proving it is *possible*
while the probe route simultaneously became *cheap*.

- `aircraft-layer/research/2026-09-29-bridge-call-cost-at-scale.md` measured the bridge at 568 units:
  **mean 1.99 ms, p99 8 ms at 1 Hz**, with per-item cost around 2.6 µs. The affordability concern
  that motivated looking at files at all is not supported.
- The file route's remaining work is Finding 5: locating and decoding the `Pbase` payload inside a
  30 GB undocumented container with no prior art. The 2026-09-05 estimate was 1–2+ weeks with a real
  chance of stalling on an undocumented compression scheme. Today's spike moved the *identity*
  question, not the *decode* question, so that estimate still stands.
- What that fortnight would buy is elevation that `land.getHeight` returns exactly and immediately,
  for free, live. The file route's one genuine advantage — theatre-wide coverage without flying —
  matters only for an offline pre-build, and M8's probe store already accumulates coverage
  incrementally across sorties.

**Effort clearly outweighs value.** Recommend recording `.surface5` as confirmed-and-parked rather
than pursuing it, and spending the effort on the probe route instead.

**The one thing that would reopen it:** if the elevation-cost probe comes back expensive enough that
in-flight probing cannot reach useful sample density, the file route is the fallback — and it is now
a *known-good* fallback with a confirmed geo-reference and a working index walker, which it was not
this morning. That is worth the spike even under a "don't build it" recommendation.

### Unresolved

- **Where `Pbase`'s per-node payload actually lives** (Finding 5). The u64 after the field name is
  not a file offset. Resolves with: decoding the descriptor's remaining unnamed integer fields, or
  walking the `TRI` blocks' own explicit length fields to find the data region.
- **Whether `TRI` payloads are compressed, and with what scheme** — unchanged since 2026-09-05; no
  zlib magic in any sampled head, which is suggestive but not conclusive.
- **Whether the format generalises to other theatres** (handoff Task 4). Deliberately not run: Task 4
  was conditional on Task 3 succeeding *and* being pursued, and the recommendation is not to pursue
  it. The walker is theatre-agnostic by construction (`--surface5` takes any path), so this is one
  command whenever it is wanted. **Kola remains the right second target** — it is the next stress
  case and SRTM does not cover ~68–69°N at all, so nothing currently fills that gap.
- **Whether the 13.3 m finest spacing is real or an artefact** of averaging over a degenerate
  small tile. Not checked; the median is the figure to trust.
