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
    DEFAULT_CURATED_PATH,
    DEFAULT_RAW_DUMP_PATH,
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

_REGISTRY_FIXTURE = {
    "missile_power": EffectorDef(
        name="missile_power",
        source_element="MISSILE-POWER-PTR",
        device=6,
        cmd=3028,
        arg=773,
        values={"on": 1.0, "off": 0.0},
    ),
    "observ": EffectorDef(
        name="observ",
        source_element="OBSERVE-PTR",
        device=7,
        cmd=3002,
        arg=886,
        values={"on": 1.0, "off": 0.0},
    ),
}


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


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
        tmp_path / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| missile_power != on | missile_power | on | | MISSILE POWER |\n"
        + "| | observ | on | | OBSERV |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

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


def test_wait_row_parses(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| wait_s(2.5) | | | | pause |\n"
        + "| | observ | on | | OBSERV |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert errors == []
    key = ("Mi-24P", "copilot", "takeoff")
    assert sequences[key].rows[0] == WaitRow(wait_s=2.5)


def test_wait_row_with_nonblank_cell_is_malformed(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| wait_s(2.5) | observ | on | | pause |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert "wait row" in errors[0].reason


def test_unknown_effector_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER
        + "\n"
        + _DATA_HEADER
        + "| | nonexistent_effector | on | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown effector 'nonexistent_effector'" in errors[0].reason


def test_unknown_value_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | sideways | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown value 'sideways'" in errors[0].reason


def test_unknown_effector_in_condition_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| ghost = on | observ | on | | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown effector 'ghost' in condition" in errors[0].reason


def test_unknown_trigger_drops_the_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER.replace("takeoff", "mission-start") + "\n" + _DATA_HEADER,
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert "unknown trigger 'mission-start'" in errors[0].reason


def test_malformed_row_wrong_cell_count_drops_the_file(tmp_path: Path) -> None:
    text = _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | on | extra |\n"
    _write(tmp_path / "t.md", text)

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert "malformed row" in errors[0].reason


def test_say_only_row_is_reserved_and_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "t.md",
        _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | | | Guidance unit ready. | x |\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 1
    assert (
        "say-only rows arrive with the guidance-unit-ready trigger" in errors[0].reason
    )


def test_duplicate_trigger_rejects_both_files(tmp_path: Path) -> None:
    body = "\n" + _DATA_HEADER + "| | observ | on | | x |\n"
    _write(tmp_path / "a.md", _TAKEOFF_HEADER + body)
    _write(tmp_path / "b.md", _TAKEOFF_HEADER + body)

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert len(errors) == 2
    files = {e.file for e in errors}
    assert files == {"a.md", "b.md"}
    for error in errors:
        assert "duplicate (aircraft, role, trigger)" in error.reason


def test_unreadable_file_is_collected_not_raised(tmp_path: Path) -> None:
    good = tmp_path / "good.md"
    _write(good, _TAKEOFF_HEADER + "\n" + _DATA_HEADER + "| | observ | on | | x |\n")
    bad = tmp_path / "bad.md"
    _write(bad, "not a table at all, no pipes here")

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    key = ("Mi-24P", "copilot", "takeoff")
    assert set(sequences) == {key}
    assert len(errors) == 1
    assert errors[0].file == "bad.md"


def test_switch_reference_file_is_skipped(tmp_path: Path) -> None:
    _write(
        tmp_path / "switch-reference.md",
        "not a sequence file, just a reference table\n",
    )

    sequences, errors = load_sequences(tmp_path, _REGISTRY_FIXTURE)

    assert sequences == {}
    assert errors == []


# --- round-trip of each shipped sequence file -------------------------------

_SEQUENCES_DIR = Path(__file__).resolve().parent.parent / "config" / "sequences"


@pytest.fixture(scope="module")
def real_registry() -> dict[str, object]:
    registry, errors = load_registry(DEFAULT_RAW_DUMP_PATH, DEFAULT_CURATED_PATH)
    assert errors == []
    return registry


def test_every_shipped_sequence_file_round_trips(
    real_registry: dict[str, object],
) -> None:
    sequences, errors = load_sequences(_SEQUENCES_DIR, real_registry)

    assert errors == []
    assert set(sequences) == {
        ("Mi-24P", "copilot", "takeoff"),
        ("Mi-24P", "copilot", "observ-on"),
        ("Mi-24P", "copilot", "observ-off"),
        ("Mi-24P", "copilot", "weapons-arm"),
        ("Mi-24P", "copilot", "weapons-safe"),
    }


def test_takeoff_file_reproduces_todays_switch_order(
    real_registry: dict[str, object],
) -> None:
    sequences, errors = load_sequences(_SEQUENCES_DIR, real_registry)
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
        assert row.condition == Condition(effector=row.effector, op="!=", value="on")
        assert row.petrovich_says == ""


def test_observ_and_weapons_files_are_single_unconditional_rows(
    real_registry: dict[str, object],
) -> None:
    sequences, errors = load_sequences(_SEQUENCES_DIR, real_registry)
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
