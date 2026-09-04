"""Tests for `dcs_data.beacons.parse_beacons_lua` against a hardcoded
fixture: the full Latakia `airfield21` group (8 beacons) plus one `world_*`
entry, copied verbatim from the synced dump.

Provenance: `world-model/research/2026-09-03-m5-nodes-lua-probe.txt`
(`beacons.lua` full-content section, lines ~2622-2705 for `airfield21_0`
through `_7`, and the `world_0` "BANIAS" entry near the top of the same
section), plus the raw copy staged at
`world-model/data/raw/dcs/syria/map/beacons.lua` (gitignored).

The field-order test below is the one this module's docstring calls out as
load-bearing: `position = { x, y, z }` where the **middle value is
elevation**, not the DCS-plane `z` coordinate -- pinned with
`airfield21_3` (HOMER), whose `y` (121.697601, an elevation) is
conspicuously larger than a coastal-plain `z` value and whose real `z`
(5622.082031) is unambiguously not that middle number.
"""

from pathlib import Path

import pytest

from dcs_data.beacons import BeaconEntry, parse_beacons_lua

_WORLD_ENTRY = """\
	{
		display_name = _('BANIAS');
		beaconId = 'world_0';
		type = BEACON_TYPE_AIRPORT_HOMER;
		callsign = 'BAN';
		frequency = 304000.000000;
		position = { 22735.679688, 7.987951, 5935.380859 };
		direction = 0.000000;
		positionGeo = { latitude = 35.228286, longitude = 35.957919 };
		sceneObjects = {'t:138619822'};
	};"""

_AIRFIELD21_ENTRIES = """\
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_0';
		type = BEACON_TYPE_ILS_GLIDESLOPE;
		callsign = 'IBA';
		frequency = 109100000.000000;
		position = { 43058.035156, 28.401319, 5704.970703 };
		direction = -1.444000;
		positionGeo = { latitude = 35.411208, longitude = 35.948517 };
		sceneObjects = {'t:380250018'};
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_1';
		type = BEACON_TYPE_ILS_LOCALIZER;
		callsign = 'IBA';
		frequency = 109100000.000000;
		position = { 40423.035156, 25.705146, 5690.542969 };
		direction = -1.456000;
		positionGeo = { latitude = 35.387479, longitude = 35.949253 };
		sceneObjects = {'t:142020950'};
		chartOffsetX = 3027.000000;
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_2';
		type = BEACON_TYPE_VOR_DME;
		callsign = 'LTK';
		frequency = 114800000.000000;
		position = { 41480.648438, 28.008296, 5966.445313 };
		direction = 0.000000;
		positionGeo = { latitude = 35.397078, longitude = 35.951928 };
		sceneObjects = {'t:38187886'};
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_3';
		type = BEACON_TYPE_HOMER;
		callsign = 'LTK';
		frequency = 414000.000000;
		position = { 50737.488281, 121.697601, 5622.082031 };
		direction = -1.444000;
		positionGeo = { latitude = 35.480331, longitude = 35.944991 };
		sceneObjects = {'t:12948489'};
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_4';
		type = BEACON_TYPE_RSBN;
		callsign = 'LTK';
		channel = 7;
		position = { 41451.058594, 27.958459, 5953.934082 };
		direction = 0.000000;
		positionGeo = { latitude = 35.396808, longitude = 35.951801 };
		sceneObjects = {'t:2144928065'};
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_5';
		type = BEACON_TYPE_DME;
		callsign = 'IBA';
		frequency = 109100000.000000;
		position = { 43057.664063, 28.401666, 5717.976074 };
		direction = 178.907120;
		positionGeo = { latitude = 35.411209, longitude = 35.948660 };
		sceneObjects = {'t:816144813'};
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_6';
		type = BEACON_TYPE_PRMG_LOCALIZER;
		callsign = 'LTK';
		channel = 9;
		position = { 43417.753906, 28.010303, 5806.485352 };
		direction = 178.552524;
		positionGeo = { latitude = 35.414475, longitude = 35.949512 };
		sceneObjects = {'t:142789829'};
		chartOffsetX = 2930.000000;
	};
	{
		display_name = _('LATAKIA');
		beaconId = 'airfield21_7';
		type = BEACON_TYPE_PRMG_GLIDESLOPE;
		callsign = 'LTK';
		channel = 9;
		position = { 41140.093750, 27.429463, 5768.382324 };
		direction = 178.556007;
		positionGeo = { latitude = 35.393957, longitude = 35.949866 };
		sceneObjects = {'t:379400000'};
	};"""


def _write_fixture(tmp_path: Path, blocks: str) -> Path:
    fixture_path = tmp_path / "beacons.lua"
    fixture_path.write_text(
        "beaconsTableFormat = 2\nbeacons = {\n" + blocks + "\n}\n", encoding="utf-8"
    )
    return fixture_path


def _patch_expected_count(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    import dcs_data.beacons as beacons_module

    monkeypatch.setattr(beacons_module, "EXPECTED_BEACON_COUNT", n)


def test_parse_beacons_lua_parses_all_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_expected_count(monkeypatch, 9)
    fixture_path = _write_fixture(tmp_path, _WORLD_ENTRY + "\n" + _AIRFIELD21_ENTRIES)

    entries = parse_beacons_lua(fixture_path)

    assert len(entries) == 9


def test_parse_beacons_lua_position_field_order_middle_is_elevation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`position = { x, y, z }` -- the middle value is elevation, not the
    DCS-plane z coordinate. airfield21_3 (HOMER) pins this: its y
    (121.697601 m) is an elevation, plainly distinct from its real z
    (5622.082031)."""
    _patch_expected_count(monkeypatch, 8)
    fixture_path = _write_fixture(tmp_path, _AIRFIELD21_ENTRIES)

    entries = parse_beacons_lua(fixture_path)
    homer = next(e for e in entries if e.beacon_id == "airfield21_3")

    assert homer.x == pytest.approx(50737.488281)
    assert homer.y == pytest.approx(121.697601)
    assert homer.z == pytest.approx(5622.082031)
    assert homer == BeaconEntry(
        display_name="LATAKIA",
        beacon_id="airfield21_3",
        beacon_type="HOMER",
        callsign="LTK",
        frequency=414000.0,
        x=50737.488281,
        y=121.697601,
        z=5622.082031,
        direction=-1.444,
        lat=35.480331,
        lon=35.944991,
        airfield_group="airfield21",
    )


def test_parse_beacons_lua_airfield_group_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_expected_count(monkeypatch, 9)
    fixture_path = _write_fixture(tmp_path, _WORLD_ENTRY + "\n" + _AIRFIELD21_ENTRIES)

    entries = parse_beacons_lua(fixture_path)

    banias = next(e for e in entries if e.beacon_id == "world_0")
    assert banias.airfield_group is None

    ils_glideslope = next(e for e in entries if e.beacon_id == "airfield21_0")
    assert ils_glideslope.airfield_group == "airfield21"


def test_parse_beacons_lua_optional_frequency_is_none_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RSBN/PRMG beacons carry `channel`, not `frequency` -- must be `None`,
    never guessed or defaulted to zero."""
    _patch_expected_count(monkeypatch, 8)
    fixture_path = _write_fixture(tmp_path, _AIRFIELD21_ENTRIES)

    entries = parse_beacons_lua(fixture_path)
    rsbn = next(e for e in entries if e.beacon_id == "airfield21_4")

    assert rsbn.frequency is None


def test_parse_beacons_lua_raises_on_malformed_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed_block = (
        "\t{\n\t\tdisplay_name = _('BROKEN');\n\t\tbeaconId = 'world_99';\n\t};"
    )
    _patch_expected_count(monkeypatch, 9)
    fixture_path = _write_fixture(tmp_path, _WORLD_ENTRY + "\n" + malformed_block)

    with pytest.raises(ValueError, match="missing required field"):
        parse_beacons_lua(fixture_path)


def test_parse_beacons_lua_raises_on_count_mismatch(tmp_path: Path) -> None:
    # Real EXPECTED_BEACON_COUNT is 151; this fixture has 8 entries.
    fixture_path = _write_fixture(tmp_path, _AIRFIELD21_ENTRIES)

    with pytest.raises(ValueError, match="Expected 151"):
        parse_beacons_lua(fixture_path)
