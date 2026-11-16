# RasterCharts across every installed terrain — layout, naming, sheet mosaic, timing

**Date:** 2026-11-16. **For:** [[MI-B4]], the raster chart viewer. **Measured by:** the Claude
session on the Windows DCS machine (`windows-session`), at the main loop's request. Everything
was read in memory from the real zips: nothing was extracted, nothing written into DCS, and the
repo was not touched. **Evidence class:** reproduced-locally on the DCS machine, except where a
line says "by eye" or "not decoded".

**This corrects a hypothesis written into MI-B4 the same day.** MI-B4 guessed that the sheet
letters were the column and the level the row. **It is the other way round** (section E).

## A. Install layout

- **DCS install:** `F:\Games\DCS World` (WSL: `/mnt/f/Games/DCS World`).
- **`Mods/terrains/`:** Afghanistan, Caucasus, Kola, MarianaIslands, Syria.
- **`DemoMods/terrains/`** holds Iraq, Mariana Islands, Nevada, Normandy, PersianGulf and
  TheChannel, but only as store stubs (theme icons, `entry.lua`, `manifest.bin`) with no
  RasterCharts. `Saved Games/DCS/Mods` has no terrains.

| terrain | `RasterCharts/` contents |
|---|---|
| Afghanistan | `rasterCharts.zip` 1,348,709,375 B; `rasterCharts.sup5` 1,478,792 B |
| Kola | `rasterCharts.zip` 1,107,127,242 B; `rasterCharts.sup5` 1,073,608 B |
| MarianaIslands | `rasterCharts.zip` 538,162,420 B; `rasterCharts.sup5` 747,696 B |
| Syria | `rasterCharts.zip` 648,555,761 B; `rasterCharts.sup5` 615,216 B |
| Caucasus | **no root zip.** `rasterCharts.sup5` 2,092,872 B, plus `0.25M/ 0.5M/ 1M/ 2M/ 5M/` holding 83 zips (section D) |

## B. Zip contents

**Common to every zip, Caucasus included:** every entry is deflated, exactly 1,398,256 bytes raw,
and sits at the zip root with no subfolders.

| terrain | entries | raw bytes | compressed bytes |
|---|---|---|---|
| Afghanistan | 3072 | 4,295,442,432 | 1,347,849,193 |
| Kola | 2240 | 3,132,093,440 | 1,106,498,228 |
| MarianaIslands | 1557 | 2,177,084,592 | 537,726,316 |
| Syria | 1280 | 1,789,767,680 | 648,198,619 |
| Caucasus (83 zips) | 4351 | 6,083,811,856 | 2,200,756,219 |

**Naming varies by terrain.** The Syria-derived strict pattern
`^(\d+)m([a-z]+)(-?\d+)_x(\d+)_z(\d+)\.tif\.dds$` misses Afghanistan 1152, Kola 2240 and Mariana
1557 entries. The variants:

- `32m_aa00_x0_z0` (underscore after the scale): all of Kola; Afghanistan's 1152 (`xad`, `xae`,
  `xaf` sheets); 1495 of Mariana's.
- `32mab00_...` (no underscore): Afghanistan's other 1920; all of Syria.
- **No scale prefix at all**, e.g. `aa00_x5_z0`, `xab-1_x0_z5`: 62 of Mariana's. **Their scale is
  unknown.**

**This pattern matches 100% of entries on every terrain, case-insensitive:**

```
^(?:(\d+)m_?)?([a-z]+)(-?\d+)_x(\d+)_z(\d+)\.tif\.dds$
```

**Groups, as (scale, sheet, level): x range, z range, tile count.**

- **Syria 32m:** sheets {aa, ab, xab, xac} × levels {-2, -1, 00, 01}, every one x0–7 z0–7, 64
  tiles. 16 sheets.
- **Syria 64m:** sheets {aa, xab} × levels {-1, 00}, full. 4 sheets.
- **Afghanistan 32m:** sheets {aa, ab, ac, xab, xac, xad, xae, xaf} × levels {-3..02}, all full.
  48 sheets × 64 = 3072.
- **Kola 32m:** sheets {aa, ab, ac, xab, xac} × levels {-3..03}, all full. 35 sheets × 64 = 2240.
- **Mariana: sparse, with partial sheets.**
  - 16m: ac00 (x1–6 z4–7, 22 tiles), ad00 (x0–7 z5–7, 24), ae00 (x3–5 z4–7, 12), af00 (x0–6 z0–5, 17).
  - 32m: aa -2 (50), -1 (64), 00 (64); ab -2 (29), -1 (48), 00 (64), 01 (64), 02 (26); ac -1 (40),
    00, 01 (64), 02 (26); ad -1 (36), 00, 01 (64), 02 (26); xab -2 (35), -1 (43), 00 (50).
  - 64m: aa -2 (62), -1 (64), 00 (x0–7 z0–5, 44); ab -2 (x0–7 z1–7, 56), -1 (64), 00 (x0–7 z0–5,
    48); xab -2 (64), -1 (64), 00 (x0–7 z0–4, 33).
  - No scale: aa-1 (3), aa00 (8), ab00 (6), ac01 (22), ad01 (3), xab-1 (15), xab00 (5).

**So a tile server must not assume full 8×8 sheets.** Missing tiles are normal.

## C. DDS headers

One size everywhere, Caucasus included: **1024×1024, fourCC `DXT5`, mipMapCount 11**, pixel-format
flags `0x4`.

## D. Caucasus

83 zips, 4351 entries. Inner names are lowercase and match the loose pattern 100%. **One zip is
always one sheet.** The scale tier and sheet are therefore readable from the inner names alone;
the zip names are inconsistent in case and underscore, so do not parse them.

| subdir | zips | scale | inner name example | sheets |
|---|---|---|---|---|
| `0.25M/` | 32 | 16m | `16m_aa-1_x0_z0.tif.dds` | AA -3..04 (8); AB -3..00 (4); AC -3..00 (4); xAB -1..05 (7); xAC 03..06 (4); xAD 04..06 (3); xAE 04..05 (2). Many partial, e.g. AA-2 has 9 tiles, AC-* have x4–7 only. |
| `0.5M/` | 39 | 32m | `32m_ag-1_...` | AG -1..05; AH, AI, AJ, AK each -1..06. The level-06 row is partial. Zip names mix `32M_AG00.zip` and `32m_AH01.zip`. |
| `1M/` | 4 | 64m | `64maa00_x1_z6.tif.dds` (no underscore) | 64mAA00 (50 tiles), 64mAA01 (59), 64mxAB00 (64), 64mxAB01 (64) |
| `2M/` | 4 | 128m | no underscore | 128mAA-1 (32), 128mAA00 (33), 128mxAB-1 (64), 128mxAB00 (64) |
| `5M/` | 4 | 256m | underscore | 256m_AA-1 (14), 256m_AA00 (15), 256m_xAB-1 (38), 256m_xAB00 (36) |

Inner samples: `0.25M/16m_AA-1.zip` 64 tiles, compressed 209k–529k each; `1M/64mAA00.zip` 50 tiles
x1_z6..x7_z7, compressed 24k–715k; `5M/256m_xAB00.zip` 36 tiles x0–5 z0–5, compressed 292k–744k.
All 1024² DXT5 with 11 mips.

**No index file anywhere in `RasterCharts/`.** The only other file, on every terrain, is
`rasterCharts.sup5` (magic `landscape5::sup5File`). It holds one record per tile (Syria stride
344 B), each carrying `RasterChart` / `colorTexture` / `<name>.tif` / `colorTexCoord` / `TRI`. Its
tile-name count equals the zip entry count on all five terrains. It looks like a material/texture
table, not georeferencing; no obvious coordinate floats near the names. **Not decoded.** Not needed
for a pan/zoom viewer.

## E. Sheet adjacency — Syria, measured

MAD = mean absolute difference in RGB 0–255 along 1-px edge strips at full resolution.

**Inside a sheet** (all adjacent pairs, n=896 at 32m): (x,z)→(x,z+1) right|left 6.68 (median 4.57);
(x,z)→(x+1,z) bottom|top 6.87 (median 4.74). Every other pairing 36.7–38.7. Random pairs 61.9.
64m the same: 6.63 / 8.07 against 44.7–49.0, random 54.1. **So inside a sheet, z is the column
(increasing east) and x is the row (increasing south).** This agrees with WM-M2.

**Between sheets, 32m, best match per sheet:**

- East neighbours (A right | B left): aa-2→aa-1 9.7; aa-1→aa00 9.9; aa00→aa01 9.3; ab-2→ab-1 3.7;
  ab-1→ab00 17.7; ab00→ab01 18.0; xab-2→xab-1 1.4; xab-1→xab00 4.2; xab00→xab01 2.7; xac-2→xac-1
  2.8; xac-1→xac00 7.3; xac00→xac01 3.9. Runner-up always 28–55. Level-01 sheets have no east
  match (best 36–46): they are the east edge.
- South neighbours (A bottom | B top): ab→aa at every level 13.3–20.9 (runner-up ≥39); aa→xab
  1.8 / 2.9 / 5.0 / 11.9 (runner-up ≥37); xab→xac 15.7 / 20.6 / 27.0 / 19.4 (runner-up 33.7–56).
  xac sheets have no south match (≥29): they are the south edge.
- Caveat: values under ~3 come partly from blank off-chart margin. The ordering is unambiguous
  regardless.

**Result — the 32m mosaic is 4 × 4 sheets of 8192 px:**

- **Columns, west → east: the level, -2, -1, 00, 01.** Level increases east.
- **Rows, north → south: ab, aa, xab, xac.** The letters are a signed row index that increases
  **north**: … ab = +1, aa = 0, xab = −1, xac = −2 …, `x` meaning minus and the second letter
  the magnitude (a = 0, b = 1, c = 2, …).

**64m:** aa-1→aa00 east 18.2; xab-1→xab00 east 10.3; aa-1→xab-1 south 5.8; aa00→xab00 south 7.4;
everything else ≥47. So 2 × 2: rows aa, xab; columns -1, 00. Same convention.

**Visual check:** both mosaics assembled from 64-px thumbnails in that order are seamless —
Cyprus, the Levant coast and the Dead Sea all continuous.

**64m vs 32m coverage — by eye only, no numeric registration:** the two tiers cover the same
ground, roughly Turkey's south coast to Sinai and the Nile delta, Cyprus to the Iraqi border, in
near-identical framing (Cyprus at 32m mosaic pixels ~190–420 × 410–540 at 1024², at 64m ~195–420 ×
420–545). **They are different chart series:** 32m a relief-tinted TPC-style chart, 64m an
ONC-style chart with paler relief and a green lowland tint. Both have pale off-chart margins in the
west.

**Not tested:** the convention on any terrain other than Syria; Caucasus's `0.5M` sheet letters
AG–AK, which would be rows +6..+10 under it; whether tiers of one terrain align numerically.

## F. Environment and timing

- **Windows `python.exe`: 3.14.7 (MSC v.1944, AMD64), Pillow NOT installed.**
- WSL: the repo's `world-model/.venv` Python with Pillow 12.3.0, numpy 2.4.6.
- **Mipmaps decode directly with Pillow:** `Image.frombytes('RGBA', (512, 512), mip1, 'bcn', 3)`
  (also `(3, '')`) on bytes `[128 + 1,048,576 : + 262,144]`. MAD against a 2× box downsample of
  the base is 4.77, against an unrelated tile 66.4, so it is the real mip.
- **Timing, Syria zip read from WSL over `/mnt/f` (the 9P bridge, slower than native Windows I/O):**

| operation | time |
|---|---|
| read + inflate one entry, first 20 (cold cache) | 114.7 ms mean |
| decode the base image (`Image.open` + RGBA) | 6.5 ms mean |
| read + inflate all 1024 entries of the 32m tier once | 16.1 s (~16 ms/entry warm) |
| read + decode + edge extraction, all 1280 | 81.9 s |

The mosaics (`mosaic32.png`, `mosaic64.png`) and per-sheet thumbnails are on the DCS machine under
`windows-session`'s WSL scratchpad (`.../scratchpad/out/`), not in the repo.
