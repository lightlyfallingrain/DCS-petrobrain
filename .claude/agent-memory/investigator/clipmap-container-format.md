---
name: clipmap-container-format
description: Byte-level structure of DCS Syria's Mods/terrains/Syria/clipmaps/*/*.tif.clipmap container (confirmed by direct decode)
metadata:
  type: reference
---

`.tif.clipmap` files (found under `Mods/terrains/Syria/clipmaps/{colortexture,normalmap,splatmap}/{scale}/`)
are a custom ED container, NOT a plain DDS despite storing DDS-compatible pixel data.
Confirmed by direct byte-level decode of 4 Syria 128m-tier samples
(`world-model/research/2026-09-03-m2-rastercharts-recon.md`, session 9).

**Fixed 0x34-byte (52-byte) header** (offsets confirmed identical across colortexture/
normalmap/splatmap/different-level samples):
- `0x00` u32 = 3 (constant, meaning unknown)
- `0x04` f32 = tile scale (e.g. 128.0), matches the `{scale}m` in the filename
- `0x08` u32 = tile width in texels (256 for the 128m tier samples)
- `0x0c` u32 = length of the tag string that follows
- `0x10` (N bytes, N from 0x0c) = compression tag string: `"bc3"` (BC3/DXT5) for
  colortexture and splatmap samples, `"bc1"` (BC1/DXT1) for normalmap
- `0x13` u8=1, `0x14` u32=6, `0x18` u32=1, `0x1c` u32=0 (constant, meaning unknown —
  `6` plausibly a mip-count)
- `0x20` i32 = clip-level marker = level_index * 32 (e.g. filename level `-1` → `-32`,
  level `0` → `0`)
- `0x24` u32 = tile height in texels (mirrors 0x08)
- `0x28`, `0x2c` u32 = 32, 32 — this is NOT pixel dimensions (a plausible but wrong
  guess); it's the entry count of the row-offset table that follows at 0x30.

**Payload**: NOT raw BC-compressed bytes. Each 256x256 (or whatever `0x08`/`0x24` say)
tile's pixel data is zlib-deflate-compressed individually, one stream per chunk,
each preceded by a 4-byte LE compressed-length field. The header's row table at 0x30
is 32 x 12-byte records `[u32 flag=1][u32 offset_of_length_prefix][u32 zero]`; the
real zlib stream (magic `78 da`) starts 4 bytes after the record's offset value.
Decompressing one chunk yields exactly width*height bytes for BC3 (1 byte/px) or
width*height/2 for BC1 (0.5 byte/px) — an exact match with zero slack, strong
confirmation of both header field meanings and compression tag.

**Decode recipe**: read header, walk the 32-entry table, `zlib.decompress()` each
chunk, then prepend a minimal synthetic 128-byte DDS header (DDSD_CAPS|HEIGHT|WIDTH|
PIXELFORMAT|LINEARSIZE, DDPF_FOURCC = `DXT5`/`DXT1` matching the tag) to the
decompressed bytes and open with Pillow — same technique as the RasterCharts DDS
decode from earlier sessions.

**Caveat**: a SECOND index table immediately follows the first 32-record table
(starting ~0x1b0) with a different/shifting record shape — NOT decoded yet. Don't
blindly scan the whole file for `78 da` magic bytes — false positives occur inside
compressed data past the region the first table vouches for (confirmed: several
`invalid block type`/`invalid distance` zlib errors when doing this). Always drive
decode off the index table, not a magic-byte scan.

**Visual result**: level-0 (`...AA00`) colortexture tiles decode to clearly
photorealistic aerial/satellite-style imagery (vegetation patches, water body edges,
terrain mottling) closely matching the F10 "Sat" map mode's visual character. Level
`-1` (`...AA-1`) tiles decode to flat near-uniform color — a coarse/fallback LOD, not
a decode failure.

Related: [[forum-dcs-world-fetch]]
