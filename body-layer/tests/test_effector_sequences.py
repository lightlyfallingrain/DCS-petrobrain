"""`belief.effector_sequences` -- `plans/effector-sequences/plan.md`
Stage 1, D5. One dedicated test per validation rule the plan's Stage 1
item lists: unknown effector, unknown value, unknown trigger, malformed
row, say-only row (reserved), duplicate (aircraft, role, trigger) --
both files rejected, unreadable file, plus a round-trip of each shipped
sequence file against the real registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from belief.effector_registry import (
    DEFAULT_RAW_DUMP_DIR,
    DEFAULT_SEQUENCES_DIR,
    EffectorDef,
    load_registry,
)
from belief.effector_sequences import (
    Condition,
    SequenceFile,
    SwitchRow,
    WaitRow,
    load_sequences,
)

_DEFAULT_CURATED_PATH = DEFAULT_SEQUENCES_DIR / "mi-24p" / "effectors.toml"
_DEFAULT_RAW_DUMP_PATH = DEFAULT_RAW_DUMP_DIR / "mi-24p.toml"

_REGISTRY_FIXTURE = {
    "missile_power": EffectorDef(
        name="missile_power",
        source_element="MISSILE-POWER-PTR",
        device=6,
        cmd=3028,
        arg=773,
        values={"on": 1.0, "off": 0.0},
        shape="default_2_position_tumb",
    ),
    "observ": EffectorDef(
        name="observ",
        source_element="OBSERVE-PTR",
        device=7,
        cmd=3002,
        arg=886,
        values={"on": 1.0, "off": 0.0},
        shape="default_2_position_tumb",
    ),
}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


#: R13 (per-aircraft layout): every test below writes its fixture
#: file(s) under `tmp_path / "mi-24p"` (the `aircraft = "Mi-24P"` header
#: lower-cased) and passes `_REGISTRIES`, not a bare registry, to
#: `load_sequences` -- `tmp_path` itself plays the role of `sequences_dir`.
_REGISTRIES = {"mi-24p": _REGISTRY_FIXTURE}

_TAKEOFF_HEADER = (
    "| file-param | for |\n"
    "| --- | --- |\n"
    "| aircraft | Mi-24P |\n"
    "| petrovich-role | copilot |\n"
    "| run-on-trigger | takeoff |\n"
)
_DATA_HEADER = "| condition | effector | value | petrovich-says | comment |\n| --- | --- | --- | --- | --- |\n"


def test_good_file_loads(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| missile_power != on | missile_power | on | | MISSILE POWER |\n"
        + "| | observ | on | | OBSERV |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert errors == []
    key = ("Mi-24P", "copilot", "takeoff")
    assert set(sequences) == {key}
    seq = sequences[key]
    assert isinstance(seq, SequenceFile)
    assert seq.rows == (
        SwitchRow(
            condition=Condition(effector="missile_power", op="!=", value="on"),
            effector="missile_power",
            value="on",
            petrovich_says="",
            comment="MISSILE POWER",
        ),
        SwitchRow(
            condition=None,
            effector="observ",
            value="on",
            petrovich_says="",
            comment="OBSERV",
        ),
    )
    # plan S4.3: read_args is every switch row's own effector arg, union
    # every explicit condition's effector arg -- here the condition and
    # the row both name `missile_power` (773), so the set is just the
    # two distinct args, not three.
    assert seq.read_args == frozenset({773, 886})


def test_wait_row_parses(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| wait_s(2.5) | | | | pause |\n"
        + "| | observ | on | | OBSERV |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert errors == []
    key = ("Mi-24P", "copilot", "takeoff")
    assert sequences[key].rows[0] == WaitRow(wait_s=2.5)


def test_wait_row_with_nonblank_cell_is_malformed(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| wait_s(2.5) | observ | on | | pause |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert "wait row" in errors[0].reason


def test_unknown_effector_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| | nonexistent_effector | on | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown effector 'nonexistent_effector'" in errors[0].reason


def test_unknown_value_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | sideways | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown value 'sideways'" in errors[0].reason


def test_unknown_effector_in_condition_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| ghost = on | observ | on | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown effector 'ghost' in condition" in errors[0].reason


def test_read_args_condition_naming_a_different_effector_is_included(
    tmp_path: Path,
) -> None:
    """plan S4.3: "a condition that names another switch is included"."""
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| observ = on | missile_power | on | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert errors == []
    key = ("Mi-24P", "copilot", "takeoff")
    assert sequences[key].read_args == frozenset({886, 773})


def test_read_args_over_64_distinct_args_is_a_file_error(tmp_path: Path) -> None:
    """plan S4.3: "a file whose set exceeds 64 is a D5 file error"."""
    registry = {
        f"sw{n}": EffectorDef(
            name=f"sw{n}",
            source_element=f"SW{n}-PTR",
            device=6,
            cmd=3000 + n,
            arg=n,
            values={"on": 1.0, "off": 0.0},
            shape="default_2_position_tumb",
        )
        for n in range(65)
    }
    rows_text = "".join(f"| | sw{n} | on | | x |\n" for n in range(65))
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + rows_text,
    )

    sequences, errors = load_sequences(tmp_path, {"mi-24p": registry})

    assert sequences == {}
    assert len(errors) == 1
    assert "exceed the 64-arg wire bound" in errors[0].reason


def test_read_args_exactly_64_distinct_args_loads(tmp_path: Path) -> None:
    registry = {
        f"sw{n}": EffectorDef(
            name=f"sw{n}",
            source_element=f"SW{n}-PTR",
            device=6,
            cmd=3000 + n,
            arg=n,
            values={"on": 1.0, "off": 0.0},
            shape="default_2_position_tumb",
        )
        for n in range(64)
    }
    rows_text = "".join(f"| | sw{n} | on | | x |\n" for n in range(64))
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + rows_text,
    )

    sequences, errors = load_sequences(tmp_path, {"mi-24p": registry})

    assert errors == []
    key = ("Mi-24P", "copilot", "takeoff")
    assert len(sequences[key].read_args) == 64


def test_unknown_trigger_drops_the_file(tmp_path: Path) -> None:
    # `bogus-trigger` -- not `mission-start`, which `EffectorTrigger` now
    # knows (`plans/effector-sequences/explore-notes.md`, "Two new
    # triggers: mission start") and would therefore no longer exercise
    # this "genuinely unknown" case.
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER.replace("takeoff", "bogus-trigger") + "\n" + _DATA_HEADER,
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown trigger 'bogus-trigger'" in errors[0].reason


def test_malformed_row_wrong_cell_count_drops_the_file(tmp_path: Path) -> None:
    text = _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | on | extra |\n"
    _write(tmp_path / "mi-24p" / "t.md", text)

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert "malformed row" in errors[0].reason


def test_say_only_row_is_reserved_and_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | | | Guidance unit ready. | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 1
    assert (
        "say-only rows arrive with the guidance-unit-ready trigger" in errors[0].reason
    )


def test_duplicate_trigger_rejects_both_files(tmp_path: Path) -> None:
    body = "\n" + _DATA_HEADER + "| | observ | on | | x |\n"
    _write(tmp_path / "mi-24p" / "a.md", _TAKEOFF_HEADER + body)
    _write(tmp_path / "mi-24p" / "b.md", _TAKEOFF_HEADER + body)

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert len(errors) == 2
    files = {e.file for e in errors}
    assert files == {"a.md", "b.md"}
    for error in errors:
        assert "duplicate (aircraft, role, trigger)" in error.reason


def test_unreadable_file_is_collected_not_raised(tmp_path: Path) -> None:
    good = tmp_path / "mi-24p" / "good.md"
    _write(good, _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | on | | x |\n")
    bad = tmp_path / "mi-24p" / "bad.md"
    _write(bad, "not a table at all, no pipes here")

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    key = ("Mi-24P", "copilot", "takeoff")
    assert set(sequences) == {key}
    assert len(errors) == 1
    assert errors[0].file == "bad.md"


def test_switch_reference_file_is_skipped(tmp_path: Path) -> None:
    _write(
        tmp_path / "mi-24p" / "switch-reference.md",
        "not a sequence file, just a reference table\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRIES)

    assert sequences == {}
    assert errors == []


# --- per-aircraft layout (R13) ----------------------------------------------


def test_aircraft_header_not_matching_its_own_directory_is_a_file_error(
    tmp_path: Path,
) -> None:
    """A file under `mi-8/` whose header still says `aircraft = Mi-24P`
    is never silently resolved against either directory -- it is its
    own file error (R13)."""
    _write(
        tmp_path / "mi-8" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | on | | x |\n",
    )

    # A registry is loaded for "mi-8" too, so the row itself resolves
    # cleanly -- this isolates the aircraft/directory mismatch check
    # from the "unknown effector" check that would otherwise fire first.
    sequences, errors = load_sequences(
        tmp_path, {**_REGISTRIES, "mi-8": _REGISTRY_FIXTURE}
    )

    assert sequences == {}
    assert len(errors) == 1
    assert errors[0].file == "t.md"
    assert "maps to directory 'mi-24p'" in errors[0].reason
    assert "under 'mi-8'" in errors[0].reason


def test_bad_registry_in_one_aircraft_directory_does_not_affect_another(
    tmp_path: Path,
) -> None:
    """R13: "each aircraft directory is independent" -- a sequence file
    under a directory with no loaded registry (simulating a registry
    that failed to load) fails its own "unknown effector" check, while a
    sibling aircraft directory with a good registry still loads."""
    _write(
        tmp_path / "mi-24p" / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | on | | x |\n",
    )
    other_header = _TAKEOFF_HEADER.replace("Mi-24P", "Mi-8")
    _write(
        tmp_path / "mi-8" / "t.md",
        other_header + "\n" + _DATA_HEADER + "| | observ | on | | x |\n",
    )

    # No registry at all loaded for "mi-8" -- as if its own registry had
    # failed to load entirely (D5's cascade).
    sequences, errors = load_sequences(tmp_path, {"mi-24p": _REGISTRY_FIXTURE})

    assert set(sequences) == {("Mi-24P", "copilot", "takeoff")}
    assert len(errors) == 1
    assert errors[0].file == "t.md"
    assert "unknown effector 'observ'" in errors[0].reason


# --- round-trip of each shipped sequence file -------------------------------

#: R13: the real, committed per-aircraft layout. `load_sequences` takes
#: the *parent* of the aircraft directories (`DEFAULT_SEQUENCES_DIR`),
#: not the `mi-24p/` directory itself.
_REAL_SEQUENCES_PARENT_DIR = DEFAULT_SEQUENCES_DIR


@pytest.fixture(scope="module")
def real_registries() -> dict[str, dict[str, object]]:
    registry, errors = load_registry(_DEFAULT_RAW_DUMP_PATH, _DEFAULT_CURATED_PATH)
    assert errors == []
    return {"mi-24p": registry}


def test_every_shipped_sequence_file_round_trips(
    real_registries: dict[str, dict[str, object]],
) -> None:
    sequences, errors = load_sequences(_REAL_SEQUENCES_PARENT_DIR, real_registries)

    assert errors == []
    assert set(sequences) == {
        ("Mi-24P", "copilot", "takeoff"),
        ("Mi-24P", "copilot", "observ-on"),
        ("Mi-24P", "copilot", "observ-off"),
        ("Mi-24P", "copilot", "weapons-arm"),
        ("Mi-24P", "copilot", "weapons-safe"),
        ("Mi-24P", "copilot", "mission-start-in-air"),
    }


def test_takeoff_file_reproduces_todays_switch_order(
    real_registries: dict[str, dict[str, object]],
) -> None:
    """R12 (2026-10-23 user correction): the shipped takeoff file no
    longer carries an explicit `!= on` self-condition on any row -- the
    engine's own implicit self-check (Stage 2) is what makes a re-run or
    a warm start a no-op now, not a `condition` cell this loader parses."""
    sequences, errors = load_sequences(_REAL_SEQUENCES_PARENT_DIR, real_registries)
    assert errors == []
    rows = sequences[("Mi-24P", "copilot", "takeoff")].rows

    assert [r.effector for r in rows if isinstance(r, SwitchRow)] == [
        "missile_power",
        "cplr_distr",
        "sight_power",
        "scho_pwr_b1",
    ]
    for row in rows:
        assert isinstance(row, SwitchRow)
        assert row.value == "on"
        assert row.condition is None
        assert row.petrovich_says == ""


def test_observ_and_weapons_files_are_single_unconditional_rows(
    real_registries: dict[str, dict[str, object]],
) -> None:
    sequences, errors = load_sequences(_REAL_SEQUENCES_PARENT_DIR, real_registries)
    assert errors == []

    observ_on = sequences[("Mi-24P", "copilot", "observ-on")].rows
    assert observ_on == (
        SwitchRow(
            condition=None,
            effector="observ",
            value="on",
            petrovich_says="",
            comment="OBSERV ON",
        ),
    )
    observ_off = sequences[("Mi-24P", "copilot", "observ-off")].rows
    assert observ_off == (
        SwitchRow(
            condition=None,
            effector="observ",
            value="off",
            petrovich_says="",
            comment="OBSERV OFF",
        ),
    )
    weapons_arm = sequences[("Mi-24P", "copilot", "weapons-arm")].rows
    assert weapons_arm == (
        SwitchRow(
            condition=None,
            effector="weapon_safety",
            value="armed",
            petrovich_says="",
            comment="WEAPONS ARMED",
        ),
    )
    weapons_safe = sequences[("Mi-24P", "copilot", "weapons-safe")].rows
    assert weapons_safe == (
        SwitchRow(
            condition=None,
            effector="weapon_safety",
            value="safe",
            petrovich_says="",
            comment="WEAPONS SAFE",
        ),
    )
