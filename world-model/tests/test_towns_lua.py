"""Tests for `dcs_data.towns.parse_towns_lua` against a hardcoded fixture.

The fixture below is a literal, hand-copied subset of the real Syria
`towns.lua` dump -- see `test_dcs_grid.py`'s established pattern of
hardcoding real-world-sourced data directly in the test module rather than
reading a file, since `data/raw/` is gitignored and cannot be a pytest
fixture at scale.

Provenance: `world-model/research/2026-09-03-m5-nodes-lua-probe.txt`
(`map/towns.lua` grep-pass section, `20260903T204237Z`), plus the raw copy
staged at `world-model/data/raw/dcs/syria/map/towns.lua` (gitignored). The
three "Yeniyurt" lines are real, distinct entries (different coordinates)
confirmed by re-parsing the full 1,182-entry dump -- see
`plans/m5-first-persistent-model/plan.md`'s towns.py spec ("31 entries have
duplicate names").
"""

from pathlib import Path

import pytest

from dcs_data.towns import TownEntry, parse_towns_lua

_SMALL_FIXTURE_ENTRIES = [
    '["Aleppo"] = { latitude = 36.219471, longitude = 37.142091, display_name = _("Aleppo")},',
    '["Latakia"] = { latitude = 35.525744, longitude = 35.785411, display_name = _("Latakia")},',
    '["Jablah"] = { latitude = 35.363965, longitude = 35.927291, display_name = _("Jablah")},',
    '["Al Hannadi"] = { latitude = 35.480731, longitude = 35.927036, display_name = _("Al Hannadi")},',
    # Duplicate name at a genuinely different coordinate -- both must survive.
    '["Yeniyurt"] = { latitude = 36.632240, longitude = 34.116905, display_name = _("Yeniyurt")},',
    '["Yeniyurt"] = { latitude = 36.885415, longitude = 36.150480, display_name = _("Yeniyurt")},',
    '["Yeniyurt"] = { latitude = 37.378770, longitude = 37.465119, display_name = _("Yeniyurt")},',
]


def _write_fixture(tmp_path: Path, entries: list[str]) -> Path:
    fixture_path = tmp_path / "towns.lua"
    lines = [
        'local gettext = require("i_18n")',
        "local       _ = gettext.translate",
        "",
        "towns = {",
        *entries,
        "}",
    ]
    fixture_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixture_path


def _patch_expected_count(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    import dcs_data.towns as towns_module

    monkeypatch.setattr(towns_module, "EXPECTED_TOWN_COUNT", n)


def test_parse_towns_lua_parses_all_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_expected_count(monkeypatch, len(_SMALL_FIXTURE_ENTRIES))
    fixture_path = _write_fixture(tmp_path, _SMALL_FIXTURE_ENTRIES)

    entries = parse_towns_lua(fixture_path)

    assert len(entries) == len(_SMALL_FIXTURE_ENTRIES)


def test_parse_towns_lua_parses_fields_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_expected_count(monkeypatch, len(_SMALL_FIXTURE_ENTRIES))
    fixture_path = _write_fixture(tmp_path, _SMALL_FIXTURE_ENTRIES)

    entries = parse_towns_lua(fixture_path)

    assert entries[2] == TownEntry(
        name="Jablah", display_name="Jablah", lat=35.363965, lon=35.927291
    )


def test_parse_towns_lua_duplicate_name_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of returning a list, not a dict: 3 distinct
    'Yeniyurt' entries at different coordinates must all survive."""
    _patch_expected_count(monkeypatch, len(_SMALL_FIXTURE_ENTRIES))
    fixture_path = _write_fixture(tmp_path, _SMALL_FIXTURE_ENTRIES)

    entries = parse_towns_lua(fixture_path)

    yeniyurt_entries = [e for e in entries if e.name == "Yeniyurt"]
    assert len(yeniyurt_entries) == 3
    assert {(e.lat, e.lon) for e in yeniyurt_entries} == {
        (36.632240, 34.116905),
        (36.885415, 36.150480),
        (37.378770, 37.465119),
    }


def test_parse_towns_lua_raises_on_malformed_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed_entries = [
        *_SMALL_FIXTURE_ENTRIES,
        '["Broken"] = { latitude = "not a number" },',
    ]
    _patch_expected_count(monkeypatch, len(malformed_entries))
    fixture_path = _write_fixture(tmp_path, malformed_entries)

    with pytest.raises(ValueError, match="Unparseable"):
        parse_towns_lua(fixture_path)


def test_parse_towns_lua_raises_on_count_mismatch(tmp_path: Path) -> None:
    # Real EXPECTED_TOWN_COUNT is 1182; this fixture has 7 entries, so the
    # count assertion must fire without needing a malformed line.
    fixture_path = _write_fixture(tmp_path, _SMALL_FIXTURE_ENTRIES)

    with pytest.raises(ValueError, match="Expected 1182"):
        parse_towns_lua(fixture_path)
