"""Tests for `elevation.dcs_grid.parse_probe_output` against a hardcoded fixture.

The fixture below is a literal, hand-copied full run of `elevation_probe.lua`'s
Stage 1 smoke test (M4 plan): 8 points scattered across the Gemerek bbox
(south=39.170, west=36.050, north=39.195, east=36.090), collected from a live
DCS mission via `tools/wsl/collect_elevation_log.sh` -- `land.getHeight`
against the installed Syria terrain. Mirrors `test_osm_features.py`'s pattern
of hardcoding real-world-sourced data directly in the test module rather than
reading a file, so tests never depend on live probe output being present --
see `world-model/CLAUDE.md`'s testing conventions.

Provenance: `world-model/data/raw/dcs/2026-09-03/elevation_probe_output.jsonl`.
Heights range 1163.18-1339.91m, plausible for the Sivas plateau region this
bbox sits in (~1000-1500m typical elevation) -- see
`world-model/research/2026-09-03-m4-elevation-recon.md` for the extraction
mechanism this confirms (first live call of `land.getHeight` against this
install, per the recon note's "Unresolved" item).
"""

import json
from pathlib import Path

import pytest

from elevation.dcs_grid import DcsElevationSample, parse_probe_output

_FIXTURE_LINES = [
    '{"name": "corner_sw", "x": 459922.0100, "z": 27944.7300, "height_m": 1339.9072}',
    '{"name": "corner_se", "x": 459810.2700, "z": 31401.0200, "height_m": 1194.5427}',
    '{"name": "corner_nw", "x": 462697.1200, "z": 28035.0800, "height_m": 1312.7600}',
    '{"name": "corner_ne", "x": 462585.3600, "z": 31490.1400, "height_m": 1163.1772}',
    '{"name": "center", "x": 461253.5000, "z": 29717.7400, "height_m": 1233.6289}',
    '{"name": "interior_1", "x": 460767.9600, "z": 29269.6000, "height_m": 1260.9650}',
    '{"name": "interior_2", "x": 461517.0500, "z": 30158.6600, "height_m": 1211.1519}',
    '{"name": "interior_3", "x": 462052.5700, "z": 30781.2500, "height_m": 1177.7704}',
]


def _write_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "elevation_probe_output.jsonl"
    fixture_path.write_text("\n".join(_FIXTURE_LINES) + "\n", encoding="utf-8")
    return fixture_path


def test_parse_probe_output_returns_all_points(tmp_path: Path) -> None:
    fixture_path = _write_fixture(tmp_path)

    samples = parse_probe_output(fixture_path)

    assert len(samples) == 8
    assert [s.name for s in samples] == [
        "corner_sw",
        "corner_se",
        "corner_nw",
        "corner_ne",
        "center",
        "interior_1",
        "interior_2",
        "interior_3",
    ]


def test_parse_probe_output_parses_fields_exactly(tmp_path: Path) -> None:
    fixture_path = _write_fixture(tmp_path)

    samples = parse_probe_output(fixture_path)

    corner_sw = samples[0]
    assert corner_sw == DcsElevationSample(
        name="corner_sw", x=459922.01, z=27944.73, height_m=1339.9072
    )


def test_parse_probe_output_heights_are_plausible_for_region() -> None:
    """Sanity check on the real fixture data itself, not just the parser:
    the Gemerek bbox sits on the Sivas plateau (~1000-1500m typical
    elevation) -- a value near sea level or implausibly high would indicate
    land.getHeight returned garbage, not a parsing bug. This is Stage 1's
    core confirmation (see M4 plan Stage 1 / research note "Unresolved")."""
    heights = [json.loads(line)["height_m"] for line in _FIXTURE_LINES]

    assert all(1000.0 <= h <= 1500.0 for h in heights)


def test_parse_probe_output_raises_on_null_height(tmp_path: Path) -> None:
    fixture_path = tmp_path / "elevation_probe_output.jsonl"
    fixture_path.write_text(
        '{"name": "failed_point", "x": 0.0, "z": 0.0, "height_m": null}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="failed_point"):
        parse_probe_output(fixture_path)
