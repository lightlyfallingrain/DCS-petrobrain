"""DDS/DXT5 mipmap byte-offset arithmetic and decode.

Every RasterCharts tile measured across every installed terrain is a
1024x1024 DXT5 (BC3) DDS with 11 mipmap levels (research note section C).
Pillow's DDS plugin only ever returns the base image (level 0); every
smaller mip sits at a computable byte offset immediately after it, since
all of a DDS file's mip data is one contiguous block after the 128-byte
header -- confirmed directly against Pillow 12.3.0/13.0.0 and cross-
checked against the exact per-entry raw size (1,398,256 bytes) the
research note measured on the real Syria zip (see
`.claude/agent-memory/architect/reference_pillow_dds_dxt5_write_and_mip_offsets.md`).
"""

from __future__ import annotations

import math

from PIL import Image

#: The base image size every measured RasterCharts tile shares (research
#: note section C). `mosaic.py` imports this too -- one source of truth
#: for "a native tile is 1024px", since mip arithmetic and tile-grid math
#: both depend on the same fact.
TILE_BASE_SIZE_PX = 1024

#: DXT5 is 16 bytes per 4x4 pixel block; a mip smaller than one block
#: still occupies one whole block, never 0.
_DXT5_BYTES_PER_BLOCK = 16
_DXT5_BLOCK_SIDE_PX = 4

#: `"DDS "` (4 bytes) + the 124-byte `DDS_HEADER` struct -- fixed size on
#: every DDS file, mip data begins immediately after it.
DDS_HEADER_SIZE_BYTES = 128


def mip_size_px(level: int, base_size_px: int = TILE_BASE_SIZE_PX) -> int:
    """The pixel side length of mip `level` (0 = base image). Never
    smaller than 1px, even once halving would reach 0."""
    return max(1, base_size_px >> level)


def mip_byte_size(level: int, base_size_px: int = TILE_BASE_SIZE_PX) -> int:
    """Raw DXT5 block-data size, in bytes, of mip `level`."""
    size_px = mip_size_px(level, base_size_px)
    blocks_per_side = math.ceil(size_px / _DXT5_BLOCK_SIDE_PX)
    return blocks_per_side**2 * _DXT5_BYTES_PER_BLOCK


def mip_byte_offset(level: int, base_size_px: int = TILE_BASE_SIZE_PX) -> int:
    """Byte offset of mip `level`'s first block, from the start of the
    DDS file (i.e. including the 128-byte header)."""
    return DDS_HEADER_SIZE_BYTES + sum(
        mip_byte_size(earlier_level, base_size_px) for earlier_level in range(level)
    )


def decode_mip(
    entry_bytes: bytes, level: int, base_size_px: int = TILE_BASE_SIZE_PX
) -> Image.Image:
    """Decode mip `level` directly out of one zip entry's already-
    inflated raw DDS bytes -- no temp file, no re-encoding. `level=0`
    (the base image) could equally go through `Image.open`, but using
    the same slice-and-decode path for every level keeps one code path
    rather than two."""
    size_px = mip_size_px(level, base_size_px)
    offset = mip_byte_offset(level, base_size_px)
    length = mip_byte_size(level, base_size_px)
    block = entry_bytes[offset : offset + length]
    return Image.frombytes("RGBA", (size_px, size_px), block, "bcn", 3)
