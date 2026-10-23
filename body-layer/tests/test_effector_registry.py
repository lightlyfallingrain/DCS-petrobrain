"""`belief.effector_registry` -- `plans/effector-sequences/plan.md`
Stage 1, D5. Every bad-content case is entry- or file-scoped and
collected rather than raised; the real committed files are the
round-trip fixture."""

from __future__ import annotations

from pathlib import Path

from belief.effector_registry import (
    DEFAULT_CURATED_PATH,
    DEFAULT_RAW_DUMP_PATH,
    EffectorDef,
    RegistryError,
    load_registry,
)

_GOOD_RAW_DUMP = """
[elements.MISSILE-POWER-PTR]
device = 6
device_name = "WEAP_SYS"
cmds = [3028]
cmd_names = ["weapon_commands.Operator_URS_POWER"]
args = [773]
label = "Missiles Power"
shape = "default_2_position_tumb"
seat = "operator"
seat_explicit = true

[elements.OBSERVE-PTR]
device = 7
device_name = "I9K113"
cmds = [3002]
cmd_names = ["i9k113_commands.Observe"]
args = [886]
label = "OBSERVE"
shape = "default_2_position_tumb"
seat = "operator"
seat_explicit = true

[elements.WEAPON-SAFETY-PTR]
device = 6
device_name = "WEAP_SYS"
cmds = [3020]
cmd_names = ["weapon_commands.Operator_SWITCHER_SAFE_WEAP"]
args = [673]
label = "Main Weapon Safe Switch"
shape = "default_2_position_tumb"
seat = "operator"
seat_explicit = true
"""

_GOOD_CURATED = """
[effectors.missile_power]
source_element = "MISSILE-POWER-PTR"
values = { on = 1.0, off = 0.0 }

[effectors.observ]
source_element = "OBSERVE-PTR"
values = { on = 1.0, off = 0.0 }

[effectors.weapon_safety]
source_element = "WEAPON-SAFETY-PTR"
values = { armed = 1.0, safe = 0.0 }
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_good_registry_resolves_every_entry(tmp_path: Path) -> None:
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)
    curated = _write(tmp_path / "curated.toml", _GOOD_CURATED)

    registry, errors = load_registry(raw, curated)

    assert errors == []
    assert set(registry) == {"missile_power", "observ", "weapon_safety"}
    assert registry["missile_power"] == EffectorDef(
        name="missile_power",
        source_element="MISSILE-POWER-PTR",
        device=6,
        cmd=3028,
        arg=773,
        values={"on": 1.0, "off": 0.0},
        unverified=False,
    )
    assert registry["weapon_safety"].values == {"armed": 1.0, "safe": 0.0}


def test_unverified_flag_carried_through(tmp_path: Path) -> None:
    curated = _write(
        tmp_path / "curated.toml",
        _GOOD_CURATED.replace(
            "[effectors.missile_power]",
            "[effectors.missile_power]\nunverified = true",
        ),
    )
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)

    registry, errors = load_registry(raw, curated)

    assert errors == []
    assert registry["missile_power"].unverified is True
    assert registry["observ"].unverified is False


def test_unresolved_source_element_drops_only_that_entry(tmp_path: Path) -> None:
    curated = _write(
        tmp_path / "curated.toml",
        _GOOD_CURATED
        + '\n[effectors.ghost]\nsource_element = "NO-SUCH-ELEMENT"\nvalues = { on = 1.0 }\n',
    )
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)

    registry, errors = load_registry(raw, curated)

    assert set(registry) == {"missile_power", "observ", "weapon_safety"}
    assert len(errors) == 1
    assert errors[0] == RegistryError(
        scope="entry",
        name="ghost",
        reason="source_element 'NO-SUCH-ELEMENT' not found in the raw dump",
    )


def test_missing_values_table_drops_only_that_entry(tmp_path: Path) -> None:
    curated = _write(
        tmp_path / "curated.toml",
        _GOOD_CURATED + '\n[effectors.bad]\nsource_element = "OBSERVE-PTR"\n',
    )
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)

    registry, errors = load_registry(raw, curated)

    assert "bad" not in registry
    assert set(registry) == {"missile_power", "observ", "weapon_safety"}
    assert len(errors) == 1
    assert errors[0].scope == "entry"
    assert errors[0].name == "bad"
    assert "values" in errors[0].reason


def test_index_out_of_range_drops_only_that_entry(tmp_path: Path) -> None:
    curated = _write(
        tmp_path / "curated.toml",
        _GOOD_CURATED
        + '\n[effectors.bad]\nsource_element = "OBSERVE-PTR"\nindex = 5\nvalues = { on = 1.0 }\n',
    )
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)

    registry, errors = load_registry(raw, curated)

    assert "bad" not in registry
    assert len(errors) == 1
    assert errors[0].name == "bad"
    assert "out of range" in errors[0].reason


def test_colliding_device_cmd_arg_drops_both_entries(tmp_path: Path) -> None:
    curated = _write(
        tmp_path / "curated.toml",
        _GOOD_CURATED
        + '\n[effectors.missile_power_dup]\nsource_element = "MISSILE-POWER-PTR"\nvalues = { on = 1.0, off = 0.0 }\n',
    )
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)

    registry, errors = load_registry(raw, curated)

    assert "missile_power" not in registry
    assert "missile_power_dup" not in registry
    assert set(registry) == {"observ", "weapon_safety"}
    collision_names = {e.name for e in errors}
    assert collision_names == {"missile_power", "missile_power_dup"}
    for error in errors:
        assert error.scope == "entry"
        assert "collides with" in error.reason


def test_unreadable_raw_dump_disables_the_whole_registry(tmp_path: Path) -> None:
    curated = _write(tmp_path / "curated.toml", _GOOD_CURATED)
    missing_raw = tmp_path / "does-not-exist.toml"

    registry, errors = load_registry(missing_raw, curated)

    assert registry == {}
    assert len(errors) == 1
    assert errors[0].scope == "raw-dump"
    assert errors[0].name is None


def test_unparsable_raw_dump_disables_the_whole_registry(tmp_path: Path) -> None:
    curated = _write(tmp_path / "curated.toml", _GOOD_CURATED)
    raw = _write(tmp_path / "raw.toml", "this is not [valid toml")

    registry, errors = load_registry(raw, curated)

    assert registry == {}
    assert len(errors) == 1
    assert errors[0].scope == "raw-dump"


def test_unreadable_curated_file_disables_the_whole_registry(tmp_path: Path) -> None:
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)
    missing_curated = tmp_path / "does-not-exist.toml"

    registry, errors = load_registry(raw, missing_curated)

    assert registry == {}
    assert len(errors) == 1
    assert errors[0].scope == "curated-file"


def test_unparsable_curated_file_disables_the_whole_registry(tmp_path: Path) -> None:
    raw = _write(tmp_path / "raw.toml", _GOOD_RAW_DUMP)
    curated = _write(tmp_path / "curated.toml", "this is not [valid toml")

    registry, errors = load_registry(raw, curated)

    assert registry == {}
    assert len(errors) == 1
    assert errors[0].scope == "curated-file"


# --- round-trip against the real, committed files --------------------------


def test_round_trip_against_the_committed_registry() -> None:
    registry, errors = load_registry(DEFAULT_RAW_DUMP_PATH, DEFAULT_CURATED_PATH)

    assert errors == []
    expected = {
        "missile_power": (6, 3028, 773),
        "cplr_distr": (16, 3015, 761),
        "sight_power": (7, 3001, 885),
        "scho_pwr_b1": (6, 3030, 955),
        "observ": (7, 3002, 886),
        "weapon_safety": (6, 3020, 673),
    }
    assert set(registry) == set(expected)
    for name, (device, cmd, arg) in expected.items():
        assert (registry[name].device, registry[name].cmd, registry[name].arg) == (
            device,
            cmd,
            arg,
        )
    assert registry["cplr_distr"].unverified is True
    assert registry["missile_power"].unverified is False
    assert registry["weapon_safety"].values == {"armed": 1.0, "safe": 0.0}
