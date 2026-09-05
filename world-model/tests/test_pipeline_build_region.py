"""M7 Stage 1 wiring tests for `build.pipeline.build_region`: a rectangular
(non-square) region builds correctly, and an absent OSM cache is skipped
rather than required -- the two things Stage 1 changes about `build_region`
(`syria-full` is rectangular and, per the plan's clarification 2, has no
OSM cache at all).

`parse_towns_lua`/`parse_beacons_lua` are monkeypatched rather than reading
real files: both raise `ValueError` unless their input has *exactly*
`EXPECTED_TOWN_COUNT` (1,182) / `EXPECTED_BEACON_COUNT` (151) entries (a
deliberate DCS-format-drift guard, see `dcs_data.towns`/`dcs_data.beacons`
module docstrings), so a hand-written small fixture file cannot go through
the real parsers -- this module tests `build_region`'s wiring, not those
parsers, which already have their own fixture-based tests
(`test_towns_lua.py`, `test_beacons_lua.py`).
"""

from pathlib import Path

import pytest

from build.pipeline import build_region
from build.region import RegionDefinition
from dcs_data.towns import TownEntry

# A real towns.lua entry (world-model/research/2026-09-03-m5-recon.md
# Finding 17) whose DCS-projected position is known to fall well inside a
# region centred nearby -- see the Aleppo beacon control point in
# tests/control_points.py for the corresponding DCS x/z.
_ALEPPO_TOWN = TownEntry(
    name="Aleppo", display_name="Aleppo", lat=36.219471, lon=37.142091
)
_FAR_AWAY_TOWN = TownEntry(name="Nowhere", display_name="Nowhere", lat=0.0, lon=0.0)

# Centred near the Aleppo beacon control point (126175.3, 123040.0),
# generous enough to contain the Aleppo town entry above. Deliberately
# rectangular (unequal half-extents), the M7 Stage 0 generalization this
# test exercises -- every pre-M7 region was square.
_TEST_REGION = RegionDefinition(
    theatre="Syria",
    name="test-rectangular-region",
    centre_x=126175.3,
    centre_z=123040.0,
    half_extent_x_m=5000.0,
    half_extent_z_m=20000.0,
)


@pytest.fixture(autouse=True)
def _patch_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "build.pipeline.parse_towns_lua",
        lambda path: [_ALEPPO_TOWN, _FAR_AWAY_TOWN],
    )
    monkeypatch.setattr("build.pipeline.parse_beacons_lua", lambda path: [])


def test_build_region_rectangular_region_without_osm_cache(tmp_path: Path) -> None:
    """The exact shape of an M7 `syria-full`-style build: a rectangular
    region, no `osm_cache_path`, no `routes_path`, no `probe_output_path`.
    Should build successfully, clip the far-away town, keep the in-region
    one, and report every optional layer as skipped rather than erroring."""
    report = build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=None,
        out_path=tmp_path / "test-rectangular-region.sqlite",
    )

    assert report.feature_counts["named_place"] == 1
    assert report.osm_skipped is True
    assert report.roadnet_skipped is True
    assert report.probe_skipped is True
    assert report.terrain_skipped is True


def test_build_region_osm_cache_path_given_but_missing_is_skipped_not_an_error(
    tmp_path: Path,
) -> None:
    """A stale/nonexistent `--osm-cache` path degrades the same way a
    missing `--routes`/`--probe-output` already does -- skipped and
    reported, never a crash (mirrors `routes_path`'s existing "absence
    reported as absence" contract, see `build.pipeline` module docstring)."""
    report = build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=tmp_path / "does-not-exist.json",
        out_path=tmp_path / "test-rectangular-region-2.sqlite",
    )

    assert report.osm_skipped is True
    assert "road" not in report.feature_counts
