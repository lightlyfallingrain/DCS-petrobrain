from __future__ import annotations

import pytest
from fixtures.synthetic_dds import build_multi_mip_dds, gradient_image

from raster_chart_viewer import ddsmip


def test_mip_byte_size_never_zero_below_one_block() -> None:
    # A mip smaller than one 4x4 block still occupies a whole block.
    assert ddsmip.mip_byte_size(10, base_size_px=1024) == 16  # 1x1 px
    assert ddsmip.mip_byte_size(9, base_size_px=1024) == 16  # 2x2 px
    assert ddsmip.mip_byte_size(8, base_size_px=1024) == 16  # 4x4 px exactly


def test_mip_byte_size_formula_matches_measured_syria_total() -> None:
    # research note + plan: 11 mips of a 1024 base sum to exactly
    # 1,398,128 bytes; +128 header = 1,398,256, the real per-entry size
    # measured on the Syria zip (1,789,767,680 / 1280 entries).
    total = sum(ddsmip.mip_byte_size(level, 1024) for level in range(11))
    assert total == 1_398_128
    assert total + ddsmip.DDS_HEADER_SIZE_BYTES == 1_398_256


def test_mip_byte_offset_is_cumulative() -> None:
    assert ddsmip.mip_byte_offset(0) == ddsmip.DDS_HEADER_SIZE_BYTES
    assert ddsmip.mip_byte_offset(1) == (
        ddsmip.DDS_HEADER_SIZE_BYTES + ddsmip.mip_byte_size(0)
    )


@pytest.mark.parametrize("base_size_px,mip_count", [(64, 7), (32, 6), (8, 4)])
def test_decode_mip_matches_independent_downsample(
    base_size_px: int, mip_count: int
) -> None:
    """Decoding any mip of a synthetic multi-mip fixture matches an
    independently computed downsample of the base image -- the plan's
    Stage 2 acceptance check, same MAD-style tolerance the research note
    used on real data. The reference downsample is plain pixel averaging,
    never Pillow's own `resize` or this module's own decode path, so the
    comparison cannot be trivially self-confirming."""
    data = build_multi_mip_dds(base_size_px, mip_count)
    base_image = gradient_image(base_size_px).convert("RGBA")
    base_pixels = base_image.load()
    assert base_pixels is not None

    for level in range(mip_count):
        decoded = ddsmip.decode_mip(data, level, base_size_px)
        size_px = ddsmip.mip_size_px(level, base_size_px)
        assert decoded.size == (size_px, size_px)
        block = base_size_px // size_px if size_px else base_size_px
        reference = _box_average_downsample(base_image, size_px, block)

        decoded_pixels = decoded.load()
        assert decoded_pixels is not None
        total_abs_diff = 0
        count = 0
        for y in range(size_px):
            for x in range(size_px):
                dr, dg, db, _da = decoded_pixels[x, y]
                rr, rg, rb, _ra = reference[x, y]
                total_abs_diff += abs(dr - rr) + abs(dg - rg) + abs(db - rb)
                count += 1
        mad = total_abs_diff / (count * 3)
        # Measured directly while writing this test: the correct mip's
        # MAD against this box-average reference tops out around 32 (the
        # smallest, 4x4-px mips, where one DXT5 block must encode the
        # whole gradient along a single interpolated colour line);
        # comparing against a deliberately wrong crop instead gives ~78.
        # 50 sits well clear of the real figures on both sides.
        assert mad < 50, f"level {level}: MAD {mad} too high to be the real mip"


def _box_average_downsample(
    image: object, size_px: int, block: int
) -> dict[tuple[int, int], tuple[int, int, int, int]]:
    """Independent reference downsample: average each `block`x`block`
    source region into one output pixel. Deliberately not Pillow's own
    `resize` (which is what the fixture builder itself used to build
    each mip before DXT5-encoding it) -- using the same resampling
    method here would make this check tautological."""
    from PIL import Image

    assert isinstance(image, Image.Image)
    pixels = image.load()
    assert pixels is not None
    base_size = image.size[0]
    result: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for oy in range(size_px):
        for ox in range(size_px):
            r_sum = g_sum = b_sum = a_sum = 0
            n = 0
            for sy in range(oy * block, min((oy + 1) * block, base_size)):
                for sx in range(ox * block, min((ox + 1) * block, base_size)):
                    r, g, b, a = pixels[sx, sy]
                    r_sum += r
                    g_sum += g
                    b_sum += b
                    a_sum += a
                    n += 1
            n = max(1, n)
            result[(ox, oy)] = (r_sum // n, g_sum // n, b_sum // n, a_sum // n)
    return result
