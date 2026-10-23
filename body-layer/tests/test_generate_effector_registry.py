"""`tools/generate_effector_registry.py` -- `plans/effector-sequences/
plan.md` Stage 0b, the offline switch-list generator.

Parses the Lua forms confirmed live against the installed Mi-24P module
(build 2.9.30.28738, 2026-10-23 -- see `aircraft-layer/research/
2026-10-23-mi24p-clickabledata-forms.md`), never the module's own
forms (never committed here -- see `body-layer/CLAUDE.md`'s DCS-native
posture). `tests/fixtures/effector_registry/{clean,dirty,bad_loop}/`
are synthetic fixtures written for this project, not ED source.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "effector_registry"


def _generator() -> ModuleType:
    path = _BODY_LAYER_ROOT / "tools" / "generate_effector_registry.py"
    spec = importlib.util.spec_from_file_location("generate_effector_registry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_effector_registry"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    return _generator()


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_BODY_LAYER_ROOT / "tools" / "generate_effector_registry.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


# --- unit-level: parse_devices / parse_command_defs -----------------------


def test_parse_devices_bracket_string_form_assigns_sequential_ids(
    gen: ModuleType,
) -> None:
    text = gen._strip_lua_comments(
        "devices = {}\n"
        'devices["ELEC_INTERFACE"]\t= counter()\n'
        'devices["ASP_17V"]\t\t\t= counter()\n'
    )
    assert gen.parse_devices(text) == {"ELEC_INTERFACE": 1, "ASP_17V": 2}


def test_parse_devices_literal_int_is_taken_at_face_value_and_continues_sequence(
    gen: ModuleType,
) -> None:
    text = 'devices["A"] = 5\ndevices["B"] = counter()\n'
    assert gen.parse_devices(text) == {"A": 5, "B": 6}


def test_parse_command_defs_resets_each_table_to_3001(gen: ModuleType) -> None:
    text = gen._strip_lua_comments(
        "start_command = 3000\n"
        "count = start_command\n"
        "elec_commands =\n{\n"
        "\tACGroundPower = counter();\n"
        "\tACGeneratorLeft = counter(),\n"
        "}\n"
        "count = start_command\n"
        "asp_commands =\n{\n"
        "\tPower = counter();\n"
        "}\n"
    )
    tables = gen.parse_command_defs(text)
    assert tables == {
        "elec_commands": {"ACGroundPower": 3001, "ACGeneratorLeft": 3002},
        "asp_commands": {"Power": 3001},
    }


def test_parse_command_defs_header_trailing_comment_and_blank_line(
    gen: ModuleType,
) -> None:
    """`spu8_commands = --radio stuff` and a blank line between the
    reset and the header (`timers_commands`, 2026-10-23 recon) must
    both still resolve -- comments are stripped before this parse ever
    runs, so a trailing comment collapses to nothing and a blank line
    is just more whitespace."""
    text = gen._strip_lua_comments(
        "start_command = 3000\n"
        "count = start_command\n"
        "spu8_commands = --radio stuff\n"
        "{\n"
        "\tCMD_A = counter();\n"
        "}\n"
        "count = start_command\n"
        "\n"
        "timers_commands =\n"
        "{\n"
        "\tLeft = counter();\n"
        "}\n"
    )
    tables = gen.parse_command_defs(text)
    assert tables["spu8_commands"] == {"CMD_A": 3001}
    assert tables["timers_commands"] == {"Left": 3001}


def test_parse_command_defs_device_commands_loop_form(gen: ModuleType) -> None:
    text = gen._strip_lua_comments(
        "start_command = 3000\n"
        "count = start_command\n"
        "device_commands = {}\n"
        "for cmd_num = 1,3 do\n"
        '\tdevice_commands["Button_"..cmd_num] = counter()\n'
        "end\n"
    )
    tables = gen.parse_command_defs(text)
    assert tables == {
        "device_commands": {"Button_1": 3001, "Button_2": 3002, "Button_3": 3003}
    }


def test_parse_command_defs_keys_table_is_never_touched(gen: ModuleType) -> None:
    """`Keys = { PlaneGear = 68, ... }` has no preceding reset marker
    and must not appear in the result at all."""
    text = gen._strip_lua_comments(
        "Keys = {\n\tPlaneGear = 68,\n}\n"
        "count = start_command\n"
        "elec_commands =\n{\n\tACGroundPower = counter();\n}\n"
    )
    tables = gen.parse_command_defs(text)
    assert "Keys" not in tables
    assert tables["elec_commands"] == {"ACGroundPower": 3001}


def test_parse_command_defs_unexpected_loop_shape_raises(gen: ModuleType) -> None:
    text = gen._strip_lua_comments(
        "start_command = 3000\n"
        "count = start_command\n"
        "device_commands = {}\n"
        "for cmd_num = 1,3 do\n"
        '\tdevice_commands["Button_"..cmd_num.."X"] = counter()\n'
        "end\n"
    )
    with pytest.raises(gen.CommandDefsParseError):
        gen.parse_command_defs(text)


def test_parse_command_defs_missing_table_after_reset_raises(gen: ModuleType) -> None:
    text = gen._strip_lua_comments("count = start_command\nsomething_else\n")
    with pytest.raises(gen.CommandDefsParseError):
        gen.parse_command_defs(text)


# --- unit-level: scan_clickabledata ----------------------------------------


_DEVICES = {"ASP_17V": 3, "SPU_8": 4, "ELEC_INTERFACE": 1}
_COMMANDS = {
    "asp_commands": {"Power": 3001},
    "spu8_commands": {"CMD_SPU8_TRIGGER_P": 3001, "CMD_SPU8_O_ICS_RADIO": 3002},
}


def test_helper_call_positional_extraction(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Sight Power"), devices.ASP_17V, '
        "asp_commands.Power, 529, nil, 1)\n"
    )
    heads, handled, unhandled, patches = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 1 and not unhandled and patches == 0
    el = handled["X"]
    assert (el.device_id, el.device_symbol) == (3, "ASP_17V")
    assert (el.cmd_id, el.cmd_symbol) == (3001, "asp_commands.Power")
    assert el.arg == 529
    assert el.label == "Sight Power"
    assert el.shape == "default_2_position_tumb"
    assert (el.crew, el.crew_explicit) == (1, True)


def test_helper_call_crew_absent_defaults_to_pilot_not_explicit(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529)\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (handled["X"].crew, handled["X"].crew_explicit) == (0, False)


def test_helper_call_crew_nil_is_not_explicit(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529, nil, nil)\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (handled["X"].crew, handled["X"].crew_explicit) == (0, False)


def test_helper_with_no_crew_parameter_defaults_pilot(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_square_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529, nil)\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (handled["X"].crew, handled["X"].crew_explicit) == (0, False)


def test_two_command_helper_records_cmd2(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_button_tumb(_("Hint"), devices.SPU_8, '
        "spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_O_ICS_RADIO, 702, nil, 1)\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    el = handled["X"]
    assert (el.cmd_id, el.cmd_symbol) == (3001, "spu8_commands.CMD_SPU8_TRIGGER_P")
    assert (el.cmd2_id, el.cmd2_symbol) == (3002, "spu8_commands.CMD_SPU8_O_ICS_RADIO")


def test_label_with_internal_comma_and_parens_is_not_split(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_button(_("Radio Source Selector Switch, '
        'R-863/NF/R-828(Eucalypt)/JADRO-1A"), devices.ASP_17V, asp_commands.Power, 1, nil)\n'
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (
        handled["X"].label
        == "Radio Source Selector Switch, R-863/NF/R-828(Eucalypt)/JADRO-1A"
    )


def test_leading_space_in_element_name_is_kept_verbatim(gen: ModuleType) -> None:
    text = (
        'elements[" X-PTR"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert " X-PTR" in handled


def test_trailing_commented_out_args_after_close_paren_are_stripped_first(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 83)--, false, nil, false, 0.5, {0, 1})\n"
    )
    stripped = gen._strip_lua_comments(text)
    _, handled, unhandled, _ = gen.scan_clickabledata(stripped, _DEVICES, _COMMANDS)
    assert not unhandled
    assert handled["X"].arg == 83


def test_raw_table_literal_uses_hint_device_action_arg_fields(gen: ModuleType) -> None:
    text = (
        'elements["STICK-PTT-PTR"] = {\n'
        "\tclass = {class_type.BTN, class_type.BTN},\n"
        '\thint = _("Trigger Button"),\n'
        "\tdevice = devices.SPU_8,\n"
        "\taction = {spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_TRIGGER_P},\n"
        "\targ = {738, 738},\n"
        "\targ_value = {1.0, 0.5},\n"
        "\tcrew_member_access = {0}\n"
        "}\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    el = handled["STICK-PTT-PTR"]
    assert (el.device_id, el.device_symbol) == (4, "SPU_8")
    assert (el.cmd_id, el.cmd_symbol) == (3001, "spu8_commands.CMD_SPU8_TRIGGER_P")
    assert el.arg == 738
    assert el.label == "Trigger Button"
    assert el.shape == "raw_table_literal"
    assert (el.crew, el.crew_explicit) == (0, True)


def test_raw_table_literal_old_schema_fields_are_not_accepted(gen: ModuleType) -> None:
    """The plan's first-pass guess (`cockpit_device_id`, `name`) is the
    wrong schema -- confirmed 2026-10-23 real field names are `device`/
    `hint`/`action`. A literal using the old names must be unhandled,
    not silently misparsed."""
    text = (
        'elements["X"] = {\n'
        "\tcockpit_device_id = devices.SPU_8,\n"
        '\tname = _("Hint"),\n'
        "\targ = 738\n"
        "}\n"
    )
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert len(unhandled) == 1


def test_post_assignment_patches_crew_member_access(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        'elements["X"].crew_member_access  = {1}\n'
    )
    heads, handled, unhandled, patches = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 2 and not unhandled and patches == 1
    assert (handled["X"].crew, handled["X"].crew_explicit) == (1, True)


def test_post_assignment_to_other_fields_is_counted_but_not_applied(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        'elements["X"].turn_box = true\n'
    )
    heads, handled, unhandled, patches = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 2 and not unhandled and patches == 1
    assert (handled["X"].crew, handled["X"].crew_explicit) == (0, False)


def test_unrecognised_helper_is_unhandled_not_a_crash(gen: ModuleType) -> None:
    text = 'elements["X"] = some_other_helper(_("Hint"), devices.ASP_17V, asp_commands.Power, 1)\n'
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert len(unhandled) == 1
    assert "unrecognised helper call" in unhandled[0].reason


def test_unknown_device_symbol_is_unhandled(gen: ModuleType) -> None:
    text = 'elements["X"] = default_button(_("Hint"), devices.NOT_REAL, asp_commands.Power, 1, nil)\n'
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert "unknown device symbol" in unhandled[0].reason


def test_unknown_command_symbol_is_unhandled(gen: ModuleType) -> None:
    text = 'elements["X"] = default_button(_("Hint"), devices.ASP_17V, asp_commands.NotReal, 1, nil)\n'
    _, handled, unhandled, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert "unknown command symbol" in unhandled[0].reason


def test_ambiguous_reference_neither_def_nor_patch_is_unhandled(
    gen: ModuleType,
) -> None:
    text = 'local x = elements["X"]\n'
    heads, handled, unhandled, patches = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 1 and not handled and patches == 0
    assert len(unhandled) == 1
    assert "neither" in unhandled[0].reason


def test_completeness_invariant_heads_equals_emitted_plus_unhandled_plus_patches(
    gen: ModuleType,
) -> None:
    text = (
        'elements["A"] = default_button(_("Hint"), devices.ASP_17V, asp_commands.Power, 1, nil)\n'
        'elements["A"].turn_box = true\n'
        'elements["B"] = unknown_helper(_("Hint"), devices.ASP_17V, asp_commands.Power, 1)\n'
        'local y = elements["A"]\n'
    )
    heads, handled, unhandled, patches = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == len(handled) + len(unhandled) + patches == 4


# --- end-to-end CLI, against the fixture directories -----------------------


def test_clean_fixture_report_mode_exits_zero_and_writes_nothing(
    tmp_path: Path,
) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run("--scripts-dir", str(_FIXTURES / "clean"), "--out", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    assert not out.exists()
    assert "9 emitted, 0 unhandled" in result.stdout


def test_clean_fixture_write_mode_produces_loadable_toml(tmp_path: Path) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir",
        str(_FIXTURES / "clean"),
        "--write",
        "--out",
        str(out),
        "--dcs-build",
        "2.9.30.28738",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.exists()
    data = tomllib.loads(out.read_text())
    assert len(data["elements"]) == 9
    stick_ptt = data["elements"]["STICK-PTT-PTR"]
    assert stick_ptt["shape"] == "raw_table_literal"
    assert stick_ptt["crew_explicit"] is True
    double_cmd = data["elements"]["DOUBLE-CMD-PTR"]
    assert double_cmd["cmd2"] == 3002


def test_dirty_fixture_fails_closed_without_allow_unhandled(tmp_path: Path) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir", str(_FIXTURES / "dirty"), "--write", "--out", str(out)
    )
    assert result.returncode == 2
    assert not out.exists()
    assert "4 unhandled" in result.stdout


def test_dirty_fixture_allow_unhandled_writes_the_rest(tmp_path: Path) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir",
        str(_FIXTURES / "dirty"),
        "--write",
        "--allow-unhandled",
        "--out",
        str(out),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = tomllib.loads(out.read_text())
    assert len(data["elements"]) == 9
    assert "MYSTERY-HELPER-PTR" not in data["elements"]


def test_bad_loop_fixture_is_fatal_regardless_of_allow_unhandled(
    tmp_path: Path,
) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir",
        str(_FIXTURES / "bad_loop"),
        "--write",
        "--allow-unhandled",
        "--out",
        str(out),
    )
    assert result.returncode == 2
    assert not out.exists()
    assert "device_commands" in result.stderr


def test_no_scripts_dir_and_no_env_var_is_a_clear_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DCS_INSTALL_PATH", raising=False)
    result = _run()
    assert result.returncode == 2
    assert "DCS_INSTALL_PATH" in result.stderr


def test_missing_required_file_is_a_clear_startup_error(tmp_path: Path) -> None:
    (tmp_path / "devices.lua").write_text("devices = {}\n")
    result = _run("--scripts-dir", str(tmp_path))
    assert result.returncode == 2
    assert "command_defs.lua" in result.stderr
