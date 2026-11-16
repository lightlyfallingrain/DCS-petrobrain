"""Build a synthetic multi-mip DXT5 DDS entirely with Pillow -- no hand-
built block bytes anywhere.

Pillow's DDS writer (`Image.save(..., pixel_format="DXT5")`) only ever
writes a single mip level (`dwMipMapCount=0`); there is no installed
tooling that writes a real multi-mip DXT5 DDS directly. So each mip is
encoded individually via that same call, its 128-byte header stripped,
and the raw block data concatenated in mip order behind one hand-built
combined header -- exactly the method measured and verified round-trip
during planning (`.claude/agent-memory/architect/
reference_pillow_dds_dxt5_write_and_mip_offsets.md`). Parametrized by
base size and mip count so tests can use small fixtures (e.g. 64x64) --
`ddsmip.py`'s byte-offset formula is scale-invariant.

Never built from, and never contains, any real DCS chart data.
"""

from __future__ import annotations

import io
import struct

from PIL import Image

from raster_chart_viewer import ddsmip

#: `DDS_HEADER.dwFlags` bit meaning "dwMipMapCount is valid" -- Pillow's
#: own single-mip writer does not set it, so the combined header must.
_DDSD_MIPMAPCOUNT = 0x20000

#: `DDS_HEADER.dwCaps` bits meaning "this is a complex surface with a
#: mipmap chain" -- same reasoning as `_DDSD_MIPMAPCOUNT` above.
_DDSCAPS_COMPLEX = 0x8
_DDSCAPS_MIPMAP = 0x400000

#: Byte offsets of the fields this module patches, within the DDS file
#: (magic included) -- the standard `DDS_HEADER` layout, confirmed
#: directly against Pillow's own writer output while planning this
#: feature. `ddsmip.py` itself never reads these; it works from computed
#: offsets alone, so an incorrect value here would not break decoding --
#: only make the synthetic file a less faithful stand-in for a real one.
_FLAGS_OFFSET = 8
_MIPMAPCOUNT_OFFSET = 28
_CAPS_OFFSET = 108


def gradient_image(size_px: int) -> Image.Image:
    """A deterministic RGBA gradient, red increasing east and green
    increasing south -- simple enough that a test can compute its own
    independent downsample (plain pixel averaging) to check a decoded
    mip against, without reusing any resampling Pillow or this builder
    itself performs."""
    image = Image.new("RGBA", (size_px, size_px))
    pixels = image.load()
    assert pixels is not None
    denom = max(1, size_px - 1)
    for y in range(size_px):
        for x in range(size_px):
            pixels[x, y] = ((x * 255) // denom, (y * 255) // denom, 128, 255)
    return image


def build_multi_mip_dds(base_size_px: int, mip_count: int) -> bytes:
    """Build a `base_size_px`x`base_size_px` DXT5 DDS with `mip_count`
    levels (level 0 = the base image), laid out exactly as `ddsmip.py`
    expects to find it."""
    base_image = gradient_image(base_size_px)
    mip_blocks: list[bytes] = []
    template_header: bytes | None = None
    for level in range(mip_count):
        size_px = ddsmip.mip_size_px(level, base_size_px)
        resized = base_image.resize((size_px, size_px))
        buf = io.BytesIO()
        resized.save(buf, format="DDS", pixel_format="DXT5")
        data = buf.getvalue()
        if template_header is None:
            template_header = data[: ddsmip.DDS_HEADER_SIZE_BYTES]
        mip_blocks.append(data[ddsmip.DDS_HEADER_SIZE_BYTES :])

    assert template_header is not None
    header = bytearray(template_header)
    flags = struct.unpack_from("<I", header, _FLAGS_OFFSET)[0]
    struct.pack_into("<I", header, _FLAGS_OFFSET, flags | _DDSD_MIPMAPCOUNT)
    struct.pack_into("<I", header, _MIPMAPCOUNT_OFFSET, mip_count)
    caps = struct.unpack_from("<I", header, _CAPS_OFFSET)[0]
    struct.pack_into(
        "<I", header, _CAPS_OFFSET, caps | _DDSCAPS_COMPLEX | _DDSCAPS_MIPMAP
    )

    return bytes(header) + b"".join(mip_blocks)
