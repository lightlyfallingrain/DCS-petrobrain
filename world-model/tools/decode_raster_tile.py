#!/usr/bin/env python3
"""Diagnostic: decode a single RasterCharts DDS tile to a viewable PNG.

Promotes the ad hoc Pillow decode used during M2 recon (see
`world-model/research/2026-09-03-m2-rastercharts-recon.md`, session 3) into a
reusable probe script. Not part of the pipeline — just a way to sample and
visually inspect additional tiles without re-deriving the one-liner each time.

Usage (from `world-model/`):

    .venv/bin/python tools/decode_raster_tile.py <tile.tif.dds> [out.png]

If `out.png` is omitted, the output is written alongside the input with a
`.png` extension.
"""

import sys
from pathlib import Path

from PIL import Image


def decode_tile(dds_path: Path, out_path: Path) -> None:
    """Decode a DXT5/BC3 DDS tile to an RGB PNG at `out_path`."""
    Image.open(dds_path).convert("RGB").save(out_path)


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(1)

    dds_path = Path(sys.argv[1])
    if len(sys.argv) == 3:
        out_path = Path(sys.argv[2])
    else:
        # Tiles are named "<...>.tif.dds"; strip both suffixes so the default
        # output matches the "<...>.png" naming used in the M2 research notes.
        stem = dds_path.name.removesuffix(".tif.dds").removesuffix(".dds")
        out_path = dds_path.with_name(f"{stem}.png")
    decode_tile(dds_path, out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
