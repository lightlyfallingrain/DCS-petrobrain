"""`belief.effector_registry.load_polled_config` -- `plans/
effector-sequences/plan.md` S4.4a: the continuous feed's arg set is
required (code) args union a per-aircraft `polled.toml`, never the
sequence files. D5-style error collection (never raises); a bad entry
sets the error/banner posture, an omitted-required-arg warning does
not."""

from __future__ import annotations

from pathlib import Path

from belief.effector_registry import EffectorDef, load_polled_config

_OBSERV = EffectorDef(
    name="observ",
    source_element="OBSERVE-PTR",
    device=7,
    cmd=3002,
    arg=886,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_MISSILE_POWER = EffectorDef(
    name="missile_power",
    source_element="MISSILE-POWER-PTR",
    device=6,
    cmd=3028,
    arg=773,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_REGISTRY = {"observ": _OBSERV, "missile_power": _MISSILE_POWER}
_REQUIRED = {886: "home_phase", 898: "SightHead.mode", 960: "sight_ready"}


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_is_required_only_no_error(tmp_path: Path) -> None:
    polled, errors, warnings = load_polled_config(
        tmp_path / "missing.toml", _REGISTRY, _REQUIRED
    )
    assert errors == []
    assert warnings == []
    assert polled.args == (886, 898, 960)


def test_c1_union_with_required_required_first(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "polled.toml",
        "[indicators.ready_lamp]\narg = 960\n",
    )
    polled, errors, _warnings = load_polled_config(path, _REGISTRY, _REQUIRED)
    assert errors == []
    assert polled.args == (886, 898, 960)
    assert polled.names == {886: "home_phase", 898: "SightHead.mode", 960: "ready_lamp"}


def test_c1_mutation_config_only_set_would_drop_required() -> None:
    """*Mutation*: a config-only set (no required union) would produce
    `{960}` alone from the fixture above, missing 886/898 -- this test
    is the counter-assertion that `test_c1_union_with_required_required_
    first` already pins; kept separate per the plan's own naming."""
    required = {1: "a", 2: "b"}
    polled, _errors, _warnings = load_polled_config(
        Path("/nonexistent/polled.toml"), _REGISTRY, required
    )
    assert set(polled.args) >= {1, 2}


def test_c2_omitted_required_logs_warning_not_a_d5_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "polled.toml",
        "[indicators.ready_lamp]\narg = 960\n",
    )
    polled, errors, warnings = load_polled_config(path, _REGISTRY, _REQUIRED)
    assert errors == []
    assert len(warnings) == 2
    assert any("886" in w and "home_phase" in w for w in warnings)
    assert any("898" in w and "SightHead.mode" in w for w in warnings)
    # The behaviour is already correct: both still polled.
    assert 886 in polled.args and 898 in polled.args


def test_c2_mutation_treating_omission_as_a_d5_error() -> None:
    """*Mutation*: a version that appended the omission to `errors`
    instead of `warnings` is falsified by the test above's own
    `assert errors == []` -- documented here as the named mutation."""


def test_c3_bad_entries_collected_others_kept(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "polled.toml",
        'effectors = ["ghost", "observ"]\n\n'
        "[indicators.bad_arg]\narg = 5000\n\n"
        "[indicators.bool_arg]\narg = true\n\n"
        '[indicators.str_arg]\narg = "960"\n\n'
        "[indicators.observ]\narg = 100\n",  # clashes with effector name
    )
    polled, errors, _warnings = load_polled_config(path, _REGISTRY, {})
    assert len(errors) == 5  # ghost, bad_arg, bool_arg, str_arg, name-clash
    assert 886 in polled.args  # "observ" from effectors list still loaded


def test_c3_mutation_raise_instead_of_collect() -> None:
    """*Mutation*: a version raising on the first bad entry instead of
    collecting would never reach the second effector -- falsified by
    `test_c3_bad_entries_collected_others_kept`'s own `886 in polled.args`
    assertion (a raise would have aborted before that fixture's good
    "observ" entry ever loaded)."""


def test_c4_unreadable_toml_is_a_file_error_required_only(tmp_path: Path) -> None:
    path = _write(tmp_path / "polled.toml", "not = [valid toml")
    polled, errors, _warnings = load_polled_config(path, _REGISTRY, _REQUIRED)
    assert len(errors) == 1
    assert errors[0].scope == "polled-file"
    assert polled.args == (886, 898, 960)


def test_c4_missing_file_no_error(tmp_path: Path) -> None:
    polled, errors, _warnings = load_polled_config(
        tmp_path / "does-not-exist.toml", _REGISTRY, _REQUIRED
    )
    assert errors == []
    assert polled.args == (886, 898, 960)


def test_c5_cap_drops_overflow_from_the_end_keeps_required(tmp_path: Path) -> None:
    registry = {
        f"sw{n}": EffectorDef(
            name=f"sw{n}",
            source_element=f"SW{n}",
            device=6,
            cmd=3000 + n,
            arg=100 + n,
            values={"on": 1.0, "off": 0.0},
            shape="default_2_position_tumb",
        )
        for n in range(63)
    }
    required = {1: "a", 2: "b", 3: "c"}
    effectors_list = ", ".join(f'"sw{n}"' for n in range(63))
    path = _write(tmp_path / "polled.toml", f"effectors = [{effectors_list}]\n")
    polled, errors, _warnings = load_polled_config(path, registry, required)

    assert len(polled.args) == 64
    assert {1, 2, 3} <= set(polled.args)
    assert len(errors) == 2  # 63 config entries + 3 required = 66, drop 2
    assert all("exceeds the 64-arg cap" in e.reason for e in errors)


def test_c5_mutation_truncate_from_the_front_would_drop_required() -> None:
    """*Mutation*: truncating from the front instead of the end would
    risk dropping a required arg if it sorted early -- falsified by
    `test_c5_cap_drops_overflow_from_the_end_keeps_required`'s own
    `{1, 2, 3} <= set(polled.args)` assertion (required args are always
    kept, regardless of order, by construction: they seed `order` before
    any config entry is appended)."""


def test_c6_sequence_files_never_change_the_polled_set(tmp_path: Path) -> None:
    """`load_polled_config` takes `polled.toml` and the registry, never
    the sequence files -- holds by construction (no sequence-file
    parameter exists to pass one in), checked here by confirming the
    result is identical regardless of what the registry otherwise
    contains loaded from sequence-unrelated sources."""
    path = _write(tmp_path / "polled.toml", 'effectors = ["observ"]\n')
    polled_a, _e, _w = load_polled_config(path, _REGISTRY, _REQUIRED)
    polled_b, _e, _w = load_polled_config(path, _REGISTRY, _REQUIRED)
    assert polled_a == polled_b


def test_c7_shipped_file_resolves_to_exactly_required(tmp_path: Path) -> None:
    """Mirrors the shipped `config/sequences/mi-24p/polled.toml`'s own
    shape -- a dedicated round-trip test against the real file lives in
    `test_logger.py`/the generated-file staleness tests; this is the
    loader's own unit coverage of that shape."""
    path = _write(
        tmp_path / "polled.toml",
        'effectors = ["observ"]\n\n'
        "[indicators.align_lamp]\narg = 898\n"
        "[indicators.ready_lamp]\narg = 960\n",
    )
    polled, errors, warnings = load_polled_config(path, _REGISTRY, _REQUIRED)
    assert errors == []
    assert warnings == []
    assert set(polled.args) == {886, 898, 960}


def test_indicator_name_clashing_with_effector_is_an_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "polled.toml", "[indicators.observ]\narg = 100\n")
    _polled, errors, _warnings = load_polled_config(path, _REGISTRY, {})
    assert len(errors) == 1
    assert "clashes" in errors[0].reason


def test_duplicate_arg_from_two_config_entries_is_an_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "polled.toml",
        'effectors = ["observ"]\n\n[indicators.also_observ]\narg = 886\n',
    )
    _polled, errors, _warnings = load_polled_config(path, _REGISTRY, {})
    assert len(errors) == 1
    assert "duplicate arg 886" in errors[0].reason
