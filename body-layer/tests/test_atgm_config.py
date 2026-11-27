"""Tests for `belief.atgm_config` -- `[[BL-B67]]` Stage 5/6, `plans/
bl-b67-atgm-run/plan.md`. A bad/missing file is never fatal (module
docstring's D5 posture, restated for this file); `load_atgm_config`
always returns a usable `AtgmConfig`."""

from __future__ import annotations

from pathlib import Path

from belief.atgm_config import (
    DEFAULT_GUIDED_CATEGORY,
    DEFAULT_GUIDED_GUIDANCE,
    DEFAULT_KNOB_STEPS,
    DEFAULT_OWN_WEAPON_OBJECT_NAMES,
    AtgmConfig,
    default_atgm_config_path,
    load_atgm_config,
)


def test_missing_file_falls_back_to_code_defaults(tmp_path: Path) -> None:
    config, errors = load_atgm_config(tmp_path / "does-not-exist.toml")
    assert errors == []
    assert config.guided_category == DEFAULT_GUIDED_CATEGORY
    assert config.guided_guidance == DEFAULT_GUIDED_GUIDANCE
    assert dict(config.knob_steps) == dict(DEFAULT_KNOB_STEPS)
    assert config.own_weapon_object_names == DEFAULT_OWN_WEAPON_OBJECT_NAMES


def test_well_formed_file_loads_cleanly(tmp_path: Path) -> None:
    path = tmp_path / "atgm.toml"
    path.write_text(
        "[guided_filter]\n"
        "category = 1\n"
        "guidance = 8\n"
        "\n"
        "[knob_steps]\n"
        "1 = 1\n"
        "2 = 2\n"
        "\n"
        "[exclusion]\n"
        'own_weapon_object_names = ["Ataka_9M120", "C_8"]\n',
        encoding="utf-8",
    )
    config, errors = load_atgm_config(path)
    assert errors == []
    assert config.guided_category == 1
    assert config.guided_guidance == 8
    assert dict(config.knob_steps) == {1: 1, 2: 2}
    assert config.own_weapon_object_names == frozenset({"Ataka_9M120", "C_8"})


def test_malformed_toml_falls_back_with_an_error(tmp_path: Path) -> None:
    path = tmp_path / "atgm.toml"
    path.write_text("not [ valid toml", encoding="utf-8")
    config, errors = load_atgm_config(path)
    assert len(errors) == 1
    assert config == AtgmConfig()


def test_bad_guided_filter_entry_falls_back_to_default_for_that_field(
    tmp_path: Path,
) -> None:
    path = tmp_path / "atgm.toml"
    path.write_text(
        '[guided_filter]\ncategory = "not an int"\nguidance = 8\n',
        encoding="utf-8",
    )
    config, errors = load_atgm_config(path)
    assert len(errors) == 1
    assert config.guided_category == DEFAULT_GUIDED_CATEGORY
    assert config.guided_guidance == 8


def test_bad_knob_steps_table_falls_back_to_default(tmp_path: Path) -> None:
    path = tmp_path / "atgm.toml"
    path.write_text(
        '[knob_steps]\none = "not an int"\n',
        encoding="utf-8",
    )
    config, errors = load_atgm_config(path)
    assert len(errors) == 1
    assert dict(config.knob_steps) == dict(DEFAULT_KNOB_STEPS)


def test_bad_exclusion_entry_falls_back_to_default(tmp_path: Path) -> None:
    path = tmp_path / "atgm.toml"
    path.write_text(
        "[exclusion]\nown_weapon_object_names = [1, 2]\n",
        encoding="utf-8",
    )
    config, errors = load_atgm_config(path)
    assert len(errors) == 1
    assert config.own_weapon_object_names == DEFAULT_OWN_WEAPON_OBJECT_NAMES


def test_station_for_step_identity_default() -> None:
    config = AtgmConfig()
    for step in range(1, 9):
        assert config.station_for_step(step) == step


def test_station_for_step_falls_back_to_the_step_itself_when_unmapped() -> None:
    config = AtgmConfig(knob_steps={1: 1})
    assert config.station_for_step(5) == 5


def test_default_atgm_config_path_is_per_aircraft(tmp_path: Path) -> None:
    path = default_atgm_config_path("mi-24p", sequences_dir=tmp_path)
    assert path == tmp_path / "mi-24p" / "atgm.toml"


def test_real_shipped_atgm_toml_loads_cleanly() -> None:
    """The real `config/sequences/mi-24p/atgm.toml` this plan ships --
    confirms the committed file and this loader agree."""
    path = default_atgm_config_path("mi-24p")
    config, errors = load_atgm_config(path)
    assert errors == []
    assert config.guided_category == 1
    assert config.guided_guidance == 8
    assert config.own_weapon_object_names == frozenset(
        {"Ataka_9M120", "AT_6", "C_8CM", "C_8"}
    )
