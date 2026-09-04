"""Tests for `elevation.dcs_grid.parse_terrain_probe_output`.

The fixture below is a literal, hand-copied subset of `terrain_probe_smoke.lua`'s
real rung-1 output (121 points, collected from a live DCS mission via
`tools/wsl/collect_terrain_probe_log.sh`) -- `land.getHeight` and
`land.getSurfaceType` against the installed Syria terrain, the first live
call of `getSurfaceType` against this install. Mirrors `test_dcs_grid.py`'s
pattern of hardcoding a small real-data subset directly in the test module
rather than reading the gitignored raw file, so tests stay reproducible
without a live probe having run.

Provenance: `world-model/data/raw/dcs/2026-09-04/terrain_probe_output_smoke.jsonl`.
See `world-model/research/2026-09-04-m5-stage3-smoke-rung.md` for the full
121-point enum distribution and sanity checks this subset was drawn from.

The 7 lines below deliberately span all three enum values the real run
produced (`LAND=1`, `WATER=3`, `ROAD=4`, `RUNWAY=5`; `SHALLOW_WATER=2` was
not observed in this rung -- absence noted, not asserted as impossible) plus
one real oddity worth pinning in a test rather than only a research note:
`r0c32` is `WATER` at `height_m=79.8625`, i.e. not sea level -- surrounded by
`LAND` neighbours at similar elevations, plausibly a small inland body in
the Jabal Ansariyah foothills rather than a parser bug (see the research
note's discussion). `r12c20` (`RUNWAY`) sits 805.7m from the Stage 1
derived LATAKIA airfield point (41740.54, 5697.76) -- an independent,
unplanned cross-subsystem sanity check the plan reserves formally for Stage
4, cheap to note here.
"""

from pathlib import Path

import pytest

from elevation.dcs_grid import DcsTerrainSample, parse_terrain_probe_output

_FIXTURE_LINES = [
    '{"name": "r0c0", "x": 34934.8920, "z": -4314.9240, "height_m": 0.0000, "surface_type": 3}',
    '{"name": "r0c4", "x": 34934.8920, "z": -2314.9240, "height_m": 0.0000, "surface_type": 3}',
    '{"name": "r0c16", "x": 34934.8920, "z": 3685.0760, "height_m": 9.1380, "surface_type": 1}',
    '{"name": "r0c32", "x": 34934.8920, "z": 11685.0760, "height_m": 79.8625, "surface_type": 3}',
    '{"name": "r12c20", "x": 40934.8920, "z": 5685.0760, "height_m": 27.0237, "surface_type": 5}',
    '{"name": "r32c20", "x": 50934.8920, "z": 5685.0760, "height_m": 126.6403, "surface_type": 4}',
    '{"name": "r40c40", "x": 54934.8920, "z": 15685.0760, "height_m": 283.9335, "surface_type": 1}',
]

# The same 7 grid points, re-sampled from the real *full* (rung 3/3,
# 1,681-point) capture -- `data/raw/dcs/2026-09-04/terrain_probe_output_full.jsonl`,
# grep'd directly from that file for these names. Copied here verbatim
# (byte-identical to `_FIXTURE_LINES` above) to pin the cross-run
# determinism finding recorded in the research note
# (`2026-09-04-m5-stage3-smoke-rung.md`, "Rung 3/3 update" -- "all rung-1
# and rung-2 points recur ... with zero mismatches") as an actual test
# assertion rather than only a narrated claim.
_FULL_RUNG_FIXTURE_LINES = [
    '{"name": "r0c0", "x": 34934.8920, "z": -4314.9240, "height_m": 0.0000, "surface_type": 3}',
    '{"name": "r0c4", "x": 34934.8920, "z": -2314.9240, "height_m": 0.0000, "surface_type": 3}',
    '{"name": "r0c16", "x": 34934.8920, "z": 3685.0760, "height_m": 9.1380, "surface_type": 1}',
    '{"name": "r0c32", "x": 34934.8920, "z": 11685.0760, "height_m": 79.8625, "surface_type": 3}',
    '{"name": "r12c20", "x": 40934.8920, "z": 5685.0760, "height_m": 27.0237, "surface_type": 5}',
    '{"name": "r32c20", "x": 50934.8920, "z": 5685.0760, "height_m": 126.6403, "surface_type": 4}',
    '{"name": "r40c40", "x": 54934.8920, "z": 15685.0760, "height_m": 283.9335, "surface_type": 1}',
]


def _write_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "terrain_probe_output.jsonl"
    fixture_path.write_text("\n".join(_FIXTURE_LINES) + "\n", encoding="utf-8")
    return fixture_path


def test_parse_terrain_probe_output_returns_all_points(tmp_path: Path) -> None:
    fixture_path = _write_fixture(tmp_path)

    samples = parse_terrain_probe_output(fixture_path)

    assert len(samples) == 7
    assert [s.name for s in samples] == [
        "r0c0",
        "r0c4",
        "r0c16",
        "r0c32",
        "r12c20",
        "r32c20",
        "r40c40",
    ]


def test_parse_terrain_probe_output_parses_fields_exactly(tmp_path: Path) -> None:
    fixture_path = _write_fixture(tmp_path)

    samples = parse_terrain_probe_output(fixture_path)

    assert samples[0] == DcsTerrainSample(
        name="r0c0", x=34934.892, z=-4314.924, height_m=0.0, surface_type=3
    )
    assert samples[4] == DcsTerrainSample(
        name="r12c20", x=40934.892, z=5685.076, height_m=27.0237, surface_type=5
    )
    assert samples[5] == DcsTerrainSample(
        name="r32c20", x=50934.892, z=5685.076, height_m=126.6403, surface_type=4
    )


def test_parse_terrain_probe_output_surface_type_values_are_within_documented_enum(
    tmp_path: Path,
) -> None:
    """`land.getSurfaceType` had never been called against this install
    before this probe (see the plan's Finding C) -- the whole point of the
    smoke test was to confirm it returns plausible enum values rather than
    garbage. Every value observed in the real 121-point rung falls inside
    the documented `1..5` range."""
    fixture_path = _write_fixture(tmp_path)

    samples = parse_terrain_probe_output(fixture_path)

    assert all(1 <= s.surface_type <= 5 for s in samples)


def test_parse_terrain_probe_output_raises_on_null_height(tmp_path: Path) -> None:
    fixture_path = tmp_path / "terrain_probe_output.jsonl"
    fixture_path.write_text(
        '{"name": "failed_point", "x": 0.0, "z": 0.0, "height_m": null, "surface_type": 1}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="failed_point"):
        parse_terrain_probe_output(fixture_path)


def test_parse_terrain_probe_output_raises_on_null_surface_type(tmp_path: Path) -> None:
    fixture_path = tmp_path / "terrain_probe_output.jsonl"
    fixture_path.write_text(
        '{"name": "failed_point", "x": 0.0, "z": 0.0, "height_m": 10.0, "surface_type": null}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="failed_point"):
        parse_terrain_probe_output(fixture_path)


def test_parse_terrain_probe_output_is_deterministic_across_live_rungs(
    tmp_path: Path,
) -> None:
    """The same 7 grid points, sampled in two separate live DCS mission
    runs (rung 1's smoke test and rung 3's full grid), produced
    bit-identical `height_m`/`surface_type` values -- see the module
    docstring and `_FULL_RUNG_FIXTURE_LINES`'s provenance comment. This
    pins that real cross-run finding as a test assertion, not just a
    research-note narration."""
    smoke_path = _write_fixture(tmp_path)
    full_path = tmp_path / "terrain_probe_output_full_subset.jsonl"
    full_path.write_text("\n".join(_FULL_RUNG_FIXTURE_LINES) + "\n", encoding="utf-8")

    smoke_samples = {s.name: s for s in parse_terrain_probe_output(smoke_path)}
    full_samples = {s.name: s for s in parse_terrain_probe_output(full_path)}

    assert smoke_samples.keys() == full_samples.keys()
    for name, smoke_sample in smoke_samples.items():
        assert smoke_sample == full_samples[name], (
            f"{name}: smoke-rung and full-rung samples diverge "
            f"({smoke_sample!r} != {full_samples[name]!r})"
        )


def test_parse_terrain_probe_output_skips_blank_lines(tmp_path: Path) -> None:
    fixture_path = tmp_path / "terrain_probe_output.jsonl"
    fixture_path.write_text(
        _FIXTURE_LINES[0] + "\n\n" + _FIXTURE_LINES[1] + "\n",
        encoding="utf-8",
    )

    samples = parse_terrain_probe_output(fixture_path)

    assert len(samples) == 2
