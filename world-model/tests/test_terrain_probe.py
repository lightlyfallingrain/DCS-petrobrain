"""Tests for `elevation.dcs_grid.parse_terrain_probe_output`.

**No real probe output exists yet** -- `land.getSurfaceType` has never been
called against this install (M5 Stage 3's whole point), so unlike
`test_dcs_grid.py`'s M4 fixture (a literal, real live-mission run), this
fixture is a synthetic literal that only pins the JSON-lines *format
contract* the plan already decided (`tools/dcs-mission-probe/
terrain_probe_*.lua`'s emitted shape: `name`/`x`/`z`/`height_m`/
`surface_type`, enum `LAND=1 .. RUNWAY=5` per plan.md Finding C) -- it does
not assert any claim about DCS's actual terrain. Once a live rung's real
output lands, replace/extend this with a hardcoded real fixture the same
way `test_dcs_grid.py` does, per `world-model/docs/CONVENTIONS.md`'s "verify
claims against the installed DCS version" rule.
"""

from pathlib import Path

import pytest

from elevation.dcs_grid import DcsTerrainSample, parse_terrain_probe_output

_FIXTURE_LINES = [
    '{"name": "r0c0", "x": 34934.8920, "z": -4314.9240, "height_m": 12.3400, "surface_type": 1}',
    '{"name": "r0c1", "x": 34934.8920, "z": -3814.9240, "height_m": -0.5000, "surface_type": 3}',
    '{"name": "r1c0", "x": 35434.8920, "z": -4314.9240, "height_m": 5.1000, "surface_type": 4}',
]


def _write_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "terrain_probe_output.jsonl"
    fixture_path.write_text("\n".join(_FIXTURE_LINES) + "\n", encoding="utf-8")
    return fixture_path


def test_parse_terrain_probe_output_returns_all_points(tmp_path: Path) -> None:
    fixture_path = _write_fixture(tmp_path)

    samples = parse_terrain_probe_output(fixture_path)

    assert len(samples) == 3
    assert [s.name for s in samples] == ["r0c0", "r0c1", "r1c0"]


def test_parse_terrain_probe_output_parses_fields_exactly(tmp_path: Path) -> None:
    fixture_path = _write_fixture(tmp_path)

    samples = parse_terrain_probe_output(fixture_path)

    assert samples[0] == DcsTerrainSample(
        name="r0c0", x=34934.892, z=-4314.924, height_m=12.34, surface_type=1
    )
    assert samples[1].surface_type == 3
    assert samples[2].surface_type == 4


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


def test_parse_terrain_probe_output_skips_blank_lines(tmp_path: Path) -> None:
    fixture_path = tmp_path / "terrain_probe_output.jsonl"
    fixture_path.write_text(
        _FIXTURE_LINES[0] + "\n\n" + _FIXTURE_LINES[1] + "\n",
        encoding="utf-8",
    )

    samples = parse_terrain_probe_output(fixture_path)

    assert len(samples) == 2
