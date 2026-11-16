---
name: pillow_dds_dxt5_write_and_mip_offsets
description: Pillow 12.3.0 writes single-level DXT5 DDS (pixel_format="DXT5"); building/reading a multi-mip fixture needs a hand-assembled header plus the measured per-mip byte-size formula.
type: reference
---

Measured directly against `world-model/.venv` (Pillow 12.3.0) while planning `raster-chart-viewer`
(2026-11-16, `plans/raster-chart-viewer/plan.md`) — not from a research note, a live check I ran
myself, cheap and repeatable on any machine with this venv.

**Writing**: `Image.save(path, pixel_format="DXT5")` works and produces a valid DDS, but **only a
single mip level** (`dwMipMapCount=0` in the written header) — Pillow's DDS encoder does not build
a mip chain.

**Building a multi-mip fixture anyway**: encode each mip level's image individually via the same
`save(..., pixel_format="DXT5")` call, strip each one's 128-byte header (`"DDS "` + 124-byte
`DDS_HEADER`), concatenate the raw block data in mip order (largest first), and write one combined
128-byte header by hand with `dwMipMapCount` set to the real count and `DDSCAPS_MIPMAP`
(`0x400000`) set in `dwCaps`. Verified round-trip: `Image.open()` recovers the base image;
`Image.frombytes("RGBA", (w, h), <slice>, "bcn", 3)` at the right offset recovers any later mip,
decoding to the expected downsample of the base.

**Per-mip byte size** (DXT5 = 16 bytes/4×4 block, and a mip smaller than one block still occupies
one whole block, never 0): `mip_bytes(level) = ceil(max(1, base_size >> level) / 4) ** 2 * 16`.
For a 1024×1024 base across all 11 levels this sums to exactly 1,398,128 bytes; +128 header =
1,398,256 — **exactly** the per-entry raw size `raster-chart-viewer`'s research note measured on
the real Syria zip (1,789,767,680 / 1280 entries), confirming the formula against real data without
a second live DCS-machine probe.

Reusable for any future DDS/DXT-adjacent test-fixture need (world-model's `src/raster/` reads real
tiles but has no synthetic-fixture builder of its own — this technique would cover that gap too, if
ever needed, without a new dependency).
