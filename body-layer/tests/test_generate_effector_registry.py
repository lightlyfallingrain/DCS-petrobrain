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
import shutil
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


def test_parse_devices_duplicate_name_raises_not_silently_reassigns(
    gen: ModuleType,
) -> None:
    """A repeated `devices["X"] = counter()` must never silently restart
    the sequence and reassign the id -- found by mutation review,
    2026-10-23 (`plans/effector-sequences/review-stage0.md`)."""
    text = (
        'devices["A"] = counter()\ndevices["B"] = counter()\ndevices["A"] = counter()\n'
    )
    with pytest.raises(gen.DuplicateNameError):
        gen.parse_devices(text)


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


def test_parse_command_defs_duplicate_table_name_raises_not_silently_restarts(
    gen: ModuleType,
) -> None:
    """A second `count = start_command` / `foo_commands` reset must never
    silently restart that table's counter at 3001 and reassign a
    duplicate id -- found by mutation review, 2026-10-23
    (`plans/effector-sequences/review-stage0.md`)."""
    text = gen._strip_lua_comments(
        "start_command = 3000\n"
        "count = start_command\n"
        "foo_commands =\n{\n\tA = counter();\n\tB = counter();\n}\n"
        "count = start_command\n"
        "foo_commands =\n{\n\tC = counter();\n}\n"
    )
    with pytest.raises(gen.DuplicateNameError):
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
    heads, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 1 and not unhandled and patches == 0
    el = handled["X"]
    assert (el.device_id, el.device_symbol) == (3, "ASP_17V")
    assert (el.cmd_ids, el.cmd_symbols) == ([3001], ["asp_commands.Power"])
    assert el.args == [529]
    assert el.arg_values is None
    assert el.label == "Sight Power"
    assert el.shape == "default_2_position_tumb"
    assert (el.seat, el.seat_explicit) == ("operator", True)


def test_helper_call_crew_absent_defaults_to_pilot_not_explicit(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (handled["X"].seat, handled["X"].seat_explicit) == ("pilot", False)


def test_helper_call_crew_nil_is_not_explicit(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529, nil, nil)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (handled["X"].seat, handled["X"].seat_explicit) == ("pilot", False)


def test_helper_with_no_crew_parameter_defaults_pilot(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_square_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529, nil)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert (handled["X"].seat, handled["X"].seat_explicit) == ("pilot", False)


def test_helper_call_crew_value_outside_known_set_is_unhandled(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 529, nil, 2)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert "unrecognised crew_member_access" in unhandled[0].reason


def test_two_command_helper_records_both_commands(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_button_tumb(_("Hint"), devices.SPU_8, '
        "spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_O_ICS_RADIO, 702, nil, 1)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    el = handled["X"]
    assert el.cmd_ids == [3001, 3002]
    assert el.cmd_symbols == [
        "spu8_commands.CMD_SPU8_TRIGGER_P",
        "spu8_commands.CMD_SPU8_O_ICS_RADIO",
    ]


# --- _HELPER_SIGNATURES: every one of the 22 entries, by position ----------

# Transcribed independently from `aircraft-layer/research/
# 2026-10-23-mi24p-clickabledata-forms.md` Q3's own parameter-list table --
# deliberately NOT read from `gen._HELPER_SIGNATURES` itself, so a wrong
# entry in the shipped table (a typo'd `crew_idx`, a dropped/added
# command slot) disagrees with this dict and fails the test below, rather
# than the test trivially re-confirming whatever the code already says.
# Found by mutation review (2026-10-23, `plans/effector-sequences/
# review-stage0.md`): only 3 of the 22 entries were exercised by any test
# before this one; mutating an untested entry's `crew_idx` left the whole
# suite green.
_EXPECTED_HELPER_SIGNATURES: dict[str, tuple[int, int | None]] = {
    "default_button": (1, 5),
    "default_spring_button": (1, 7),
    "default_square_button": (1, None),
    "default_tumb_button": (1, 5),
    "default_position_tumb": (1, 7),
    "default_1_position_tumb": (1, 7),
    "default_2_position_tumb": (1, 5),
    "default_2_position_small_tumb": (1, 5),
    "default_2_position_flares_tumb": (1, 5),
    "default_3_position_tumb": (1, 9),
    "triple_switch": (1, 4),
    "multiposition_switch": (1, 10),
    "default_button_tumb": (2, 6),
    "springloaded_2_pos_tumb": (1, 5),
    "springloaded_3_pos_tumb": (2, 9),
    "default_animated_lever": (1, 6),
    "default_axis": (1, 11),
    "default_axis_limited": (1, 11),
    "default_CB_button": (1, 4),
    "default_blue_cover": (1, 5),
    "radio_wheel_1": (1, 7),
    "stick_button": (1, None),
}


def test_helper_signatures_table_has_exactly_the_22_recon_entries(
    gen: ModuleType,
) -> None:
    assert len(gen._HELPER_SIGNATURES) == 22
    assert set(gen._HELPER_SIGNATURES) == set(_EXPECTED_HELPER_SIGNATURES)


def _build_helper_call_text(
    name: str, helper: str, n_commands: int, crew_idx: int | None
) -> str:
    """One synthetic call exercising `helper` with the crew argument (and
    the second command, where present) at its *real* positional index --
    a one-off index mutation (e.g. `multiposition_switch`'s `crew_idx`
    10 -> 9) must fail this, not pass silently."""
    if n_commands == 1:
        device_ref, cmd_refs = "devices.ASP_17V", ["asp_commands.Power"]
    else:
        device_ref = "devices.SPU_8"
        cmd_refs = [
            "spu8_commands.CMD_SPU8_TRIGGER_P",
            "spu8_commands.CMD_SPU8_O_ICS_RADIO",
        ]
    args = ['_("Test Hint")', device_ref, *cmd_refs]
    arg_idx = 2 + n_commands
    assert len(args) == arg_idx
    args.append("42")
    if crew_idx is not None:
        while len(args) < crew_idx:
            args.append("nil")
        args.append("1")  # crew_member_access = {1} -> "operator"
    return f'elements["{name}"] = {helper}({", ".join(args)})\n'


def test_helper_signatures_positional_crew_and_command_count(
    gen: ModuleType,
) -> None:
    for helper, (n_commands, crew_idx) in _EXPECTED_HELPER_SIGNATURES.items():
        text = _build_helper_call_text("X", helper, n_commands, crew_idx)
        _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
        assert not unhandled, f"{helper}: unexpectedly unhandled: {unhandled}"
        el = handled["X"]
        assert len(el.cmd_ids) == n_commands, f"{helper}: wrong command count"
        assert el.args == [42], f"{helper}: wrong draw argument"
        if crew_idx is None:
            assert (el.seat, el.seat_explicit) == (
                "pilot",
                False,
            ), f"{helper}: expected default pilot seat with no crew parameter"
        else:
            assert (el.seat, el.seat_explicit) == (
                "operator",
                True,
            ), f"{helper}: crew_idx positioned wrong -- expected explicit operator seat"


def test_label_with_internal_comma_and_parens_is_not_split(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_button(_("Radio Source Selector Switch, '
        'R-863/NF/R-828(Eucalypt)/JADRO-1A"), devices.ASP_17V, asp_commands.Power, 1, nil)\n'
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
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
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
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
    _, handled, unhandled, _, _ = gen.scan_clickabledata(stripped, _DEVICES, _COMMANDS)
    assert not unhandled
    assert handled["X"].args == [83]


def test_hint_containing_a_literal_double_dash_is_kept_verbatim(
    gen: ModuleType,
) -> None:
    """A `--` inside a quoted hint string is not a comment start --
    `_strip_lua_comments` must leave it alone. (The `dirty` fixture's
    `"broken -- no action field"` happens to touch this too, but for an
    unrelated reason: that element is unhandled anyway because it is
    missing `action`, so a comment-stripping regression there would not
    be caught -- plan.md's own Tests paragraph calls this gap out by
    name.)"""
    text = (
        'elements["X"] = default_button(_("Fuel Pump -- Main Tank"), '
        "devices.ASP_17V, asp_commands.Power, 1, nil)\n"
    )
    stripped = gen._strip_lua_comments(text)
    _, handled, unhandled, _, _ = gen.scan_clickabledata(stripped, _DEVICES, _COMMANDS)
    assert not unhandled
    assert handled["X"].label == "Fuel Pump -- Main Tank"


def test_block_comment_hides_a_fake_elements_line(gen: ModuleType) -> None:
    """A `--[[ ... ]]` block comment containing a line that looks exactly
    like an `elements[...]` assignment must not be counted at all -- not
    as a head, not as "ignored"."""
    text = (
        "--[[\n"
        'elements["FAKE"] = default_button(_("Fake"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        "]]\n"
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
    )
    stripped = gen._strip_lua_comments(text)
    heads, handled, unhandled, patches, ignored = gen.scan_clickabledata(
        stripped, _DEVICES, _COMMANDS
    )
    assert heads == 1 and not unhandled and patches == 0
    assert set(handled) == {"X"}
    assert not any("FAKE" in snippet for _, snippet in ignored)


def test_crlf_line_endings_parse_identically_to_lf(gen: ModuleType) -> None:
    """All four real Mi-24P cockpit script files are CRLF on every line
    (2026-10-23 recon, Q0). `Path.read_text()`'s universal-newline
    translation makes this a non-issue for the file-reading CLI path,
    but `scan_clickabledata` itself must also parse a CRLF string
    correctly for any caller that does not go through `Path.read_text()`
    -- written with explicit `\\r\\n` from this test, not relying on
    git's own line-ending handling of a committed fixture."""
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\r\n"
        'elements["X"].crew_member_access  = {1}\r\n'
    )
    assert "\r\n" in text
    heads, handled, unhandled, patches, ignored = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 2 and not unhandled and patches == 1 and ignored == []
    assert (handled["X"].seat, handled["X"].seat_explicit) == ("operator", True)


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
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    el = handled["STICK-PTT-PTR"]
    assert (el.device_id, el.device_symbol) == (4, "SPU_8")
    assert el.cmd_ids == [3001, 3001]
    assert el.cmd_symbols == [
        "spu8_commands.CMD_SPU8_TRIGGER_P",
        "spu8_commands.CMD_SPU8_TRIGGER_P",
    ]
    assert el.args == [738, 738]
    assert el.arg_values == [1.0, 0.5]
    assert el.label == "Trigger Button"
    assert el.shape == "raw_table_literal"
    assert (el.seat, el.seat_explicit) == ("pilot", True)


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
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert len(unhandled) == 1


def test_post_assignment_patches_crew_member_access(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        'elements["X"].crew_member_access  = {1}\n'
    )
    heads, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 2 and not unhandled and patches == 1
    assert (handled["X"].seat, handled["X"].seat_explicit) == ("operator", True)


def test_post_assignment_crew_member_access_outside_known_set_is_unhandled(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        'elements["X"].crew_member_access  = {2}\n'
    )
    heads, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 2 and patches == 1
    assert "X" not in handled
    assert len(unhandled) == 1
    assert "unrecognised crew_member_access" in unhandled[0].reason


def test_post_assignment_to_other_fields_is_counted_but_not_applied(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        'elements["X"].turn_box = true\n'
    )
    heads, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 2 and not unhandled and patches == 1
    assert (handled["X"].seat, handled["X"].seat_explicit) == ("pilot", False)


def test_unrecognised_helper_is_unhandled_not_a_crash(gen: ModuleType) -> None:
    text = 'elements["X"] = some_other_helper(_("Hint"), devices.ASP_17V, asp_commands.Power, 1)\n'
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert len(unhandled) == 1
    assert "unrecognised helper call" in unhandled[0].reason


def test_unknown_device_symbol_is_unhandled(gen: ModuleType) -> None:
    text = 'elements["X"] = default_button(_("Hint"), devices.NOT_REAL, asp_commands.Power, 1, nil)\n'
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert "unknown device symbol" in unhandled[0].reason


def test_unknown_command_symbol_is_unhandled(gen: ModuleType) -> None:
    text = 'elements["X"] = default_button(_("Hint"), devices.ASP_17V, asp_commands.NotReal, 1, nil)\n'
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not handled
    assert "unknown command symbol" in unhandled[0].reason


def test_ambiguous_reference_neither_def_nor_patch_is_unhandled(
    gen: ModuleType,
) -> None:
    text = 'local x = elements["X"]\n'
    heads, handled, unhandled, patches, _ = gen.scan_clickabledata(
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
    heads, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == len(handled) + len(unhandled) + patches == 4


# --- dynamic elements[ keys / "statements ignored" -------------------------


def test_dynamic_elements_key_is_unhandled_not_invisible(gen: ModuleType) -> None:
    """`elements[key..i] = ...` -- a computed key, not a literal string --
    must never silently fall through the scanner uncounted. `plan.md`
    point 6 and the Stage 0 review both call this out by name: the
    quoted-literal regex alone would never even see this head at all."""
    text = (
        "for gen_i = 1, 2 do\n"
        '\telements["GEN_"..gen_i] = default_button(_("Generated"), '
        "devices.ASP_17V, asp_commands.Power, 600, nil)\n"
        "end\n"
    )
    heads, handled, unhandled, patches, ignored = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 1
    assert not handled
    assert patches == 0
    assert len(unhandled) == 1
    assert "dynamic/computed key" in unhandled[0].reason
    # the `for`/`end` lines around it are genuine top-level statements,
    # not part of the dynamic elements[ head itself
    assert any("for gen_i" in snippet for _, snippet in ignored)
    assert any(snippet == "end" for _, snippet in ignored)


def test_statements_ignored_counts_top_level_non_element_lines(
    gen: ModuleType,
) -> None:
    """The file's own preamble (`dofile`/`local`/plain-assignment lines,
    confirmed by the 2026-10-23 recon's Q4 to precede every real
    `elements[...]` assignment) is counted as "statements ignored" --
    present in the report and the completeness arithmetic untouched by
    it."""
    text = (
        'dofile(LockOn_Options.script_path.."clickable_defs.lua")\n'
        'local gettext = require("i_18n")\n'
        "elements = {}\n"
        'elements["A"] = default_button(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
    )
    heads, handled, unhandled, patches, ignored = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert heads == 1 and len(handled) == 1 and not unhandled and patches == 0
    ignored_lines = {snippet for _, snippet in ignored}
    assert 'dofile(LockOn_Options.script_path.."clickable_defs.lua")' in ignored_lines
    assert 'local gettext = require("i_18n")' in ignored_lines
    assert "elements = {}" in ignored_lines
    # the handled element's own line is never double-counted as ignored
    assert not any("default_button" in snippet for snippet in ignored_lines)


def test_statements_ignored_does_not_flag_lines_inside_a_multiline_literal(
    gen: ModuleType,
) -> None:
    """A raw table literal spanning several lines must be blanked out in
    full -- its interior field lines (`hint = ...`, `device = ...`, ...)
    are part of the one element definition, not separate ignored
    statements."""
    text = (
        'elements["X"] = {\n'
        '\thint = _("Hint"),\n'
        "\tdevice = devices.ASP_17V,\n"
        "\taction = {asp_commands.Power},\n"
        "\targ = {1}\n"
        "}\n"
    )
    _, handled, unhandled, _, ignored = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert not unhandled and "X" in handled
    assert ignored == []


# --- TOML escaping (BL-B91: control characters in ED-sourced free text) ---


def _round_trip_string(gen: ModuleType, value: str) -> str:
    """Render `value` through `_toml_string`, parse the single-key
    document that produces, and return what comes back -- the
    byte-identical round trip `BL-B91` asks for."""
    toml_text = f"v = {gen._toml_string(value)}\n"
    parsed = tomllib.loads(toml_text)
    result = parsed["v"]
    assert isinstance(result, str)
    return result


@pytest.mark.parametrize(
    "value",
    [
        "plain label",
        'has a "quote" in it',
        "has a \\backslash\\ in it",
        "backspace\bhere",
        "tab\there",
        "newline\nhere",
        "form feed\fhere",
        "carriage\rreturn",
        "bell\x07and\x01other\x1fC0 controls",
        "\x7fDEL at the front",
        'mixed: \\"\n\t\x00\x7f end',
    ],
)
def test_toml_string_round_trips_every_control_class(
    gen: ModuleType, value: str
) -> None:
    assert _round_trip_string(gen, value) == value


def test_toml_string_injection_payload_stays_a_plain_string(
    gen: ModuleType,
) -> None:
    """The security report's demonstration payload (`BL-B91`): before the
    fix this produced a raw multi-line TOML value that `tomllib` refused
    to parse at all. Escaped, it must round-trip as one scalar string and
    must not create the `label`/`[elements.pwn]` keys it tries to
    inject."""
    payload = 'evil\nlabel = "INJECTED"\n[elements.pwn]\nx=1'
    toml_text = f"v = {gen._toml_string(payload)}\n"
    parsed = tomllib.loads(toml_text)
    assert parsed == {"v": payload}


def test_toml_key_escapes_control_characters_in_a_quoted_key(
    gen: ModuleType,
) -> None:
    name = "weird\nname"
    toml_text = f"[elements.{gen._toml_key(name)}]\nx = 1\n"
    parsed = tomllib.loads(toml_text)
    assert parsed == {"elements": {name: {"x": 1}}}


def test_render_toml_control_character_in_label_round_trips(
    gen: ModuleType,
) -> None:
    """End-to-end through `render_toml`, not just the escaping helper
    directly -- a `label` carrying a raw newline (the case `BL-B91`
    demonstrated) must still produce a document `tomllib` can load, with
    the control character preserved in the parsed value."""
    el = gen.RawElement(
        name="X",
        device_id=1,
        device_symbol="SOME_DEVICE",
        cmd_ids=[3001],
        cmd_symbols=["Power"],
        args=[1],
        label="line one\nline two",
        shape="tumb",
        seat="pilot",
        seat_explicit=True,
    )
    rendered = gen.render_toml(
        {"X": el},
        "dcs-build",
        {},
        heads=1,
        n_unhandled=0,
        n_post_assigns=0,
        n_ignored=0,
    )
    parsed = tomllib.loads(rendered)
    assert parsed["elements"]["X"]["label"] == "line one\nline two"


# --- end-to-end CLI, against the fixture directories -----------------------


def test_clean_fixture_report_mode_exits_zero_and_writes_nothing(
    tmp_path: Path,
) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run("--scripts-dir", str(_FIXTURES / "clean"), "--output", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    assert not out.exists()
    assert "9 emitted, 0 unhandled" in result.stdout


def test_clean_fixture_write_mode_produces_loadable_toml(tmp_path: Path) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir",
        str(_FIXTURES / "clean"),
        "--write",
        "--output",
        str(out),
        "--dcs-build",
        "2.9.30.28738",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.exists()
    rendered = out.read_text()
    assert "Source: Mods/aircraft/Mi-24P/Cockpit/Scripts, DCS 2.9.30.28738" in rendered
    assert "Inputs (sha256):" in rendered
    assert "devices.lua " in rendered
    assert "Statements ignored: 1 (see the run report)." in rendered
    assert "1 statements ignored" in result.stdout
    data = tomllib.loads(rendered)
    assert len(data["elements"]) == 9
    stick_ptt = data["elements"]["STICK-PTT-PTR"]
    assert stick_ptt["shape"] == "raw_table_literal"
    assert stick_ptt["seat_explicit"] is True
    assert stick_ptt["seat"] == "pilot"
    assert stick_ptt["cmds"] == [3001, 3001]
    assert stick_ptt["args"] == [738, 738]
    assert stick_ptt["arg_values"] == [1.0, 0.5]
    double_cmd = data["elements"]["DOUBLE-CMD-PTR"]
    assert double_cmd["cmds"] == [3001, 3002]
    assert double_cmd["cmd_names"] == [
        "spu8_commands.CMD_SPU8_TRIGGER_P",
        "spu8_commands.CMD_SPU8_O_ICS_RADIO",
    ]
    sight_power = data["elements"]["WEAP-SIGHT-ON-PFF-PTR"]
    assert sight_power["device_name"] == "ASP_17V"
    assert sight_power["seat"] == "operator"
    assert "arg_values" not in sight_power


def test_dirty_fixture_fails_closed_without_allow_unhandled(tmp_path: Path) -> None:
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir", str(_FIXTURES / "dirty"), "--write", "--output", str(out)
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
        "--output",
        str(out),
        "--dcs-build",
        "test",
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
        "--output",
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
    assert result.returncode == 1
    assert "DCS_INSTALL_PATH" in result.stderr


def test_missing_required_file_is_a_clear_startup_error(tmp_path: Path) -> None:
    (tmp_path / "devices.lua").write_text("devices = {}\n")
    result = _run("--scripts-dir", str(tmp_path))
    assert result.returncode == 1
    assert "command_defs.lua" in result.stderr


def test_write_without_dcs_build_and_no_env_var_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DCS_INSTALL_PATH", raising=False)
    out = tmp_path / "effectors-raw.toml"
    result = _run(
        "--scripts-dir", str(_FIXTURES / "clean"), "--write", "--output", str(out)
    )
    assert result.returncode == 1
    assert not out.exists()
    assert "--dcs-build" in result.stderr


def test_report_mode_needs_no_dcs_build(tmp_path: Path) -> None:
    """Report mode never writes the header, so it never needs a build
    string -- only `--write` triggers the autoupdate.cfg/`--dcs-build`
    resolution."""
    out = tmp_path / "effectors-raw.toml"
    result = _run("--scripts-dir", str(_FIXTURES / "clean"), "--output", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    assert not out.exists()


def test_dcs_install_path_resolves_scripts_dir_and_reads_autoupdate_cfg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_root = tmp_path / "install"
    install_root.mkdir()
    (install_root / "autoupdate.cfg").write_text(
        '{\n    "version": "2.9.30.28738",\n}\n'
    )
    scripts_dir = install_root / "Mods" / "aircraft" / "Mi-24P" / "Cockpit" / "Scripts"
    scripts_dir.mkdir(parents=True)
    for name in ("devices.lua", "command_defs.lua", "clickabledata.lua"):
        shutil.copyfile(_FIXTURES / "clean" / name, scripts_dir / name)
    monkeypatch.setenv("DCS_INSTALL_PATH", str(install_root))
    out = tmp_path / "effectors-raw.toml"
    result = _run("--write", "--output", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = out.read_text()
    assert "DCS 2.9.30.28738" in rendered


# --- value ranges (2026-10-23 follow-up) -----------------------------------
#
# Source of truth for every expected number below:
# `aircraft-layer/research/2026-10-23-mi24p-clickable-value-ranges.md`.


def _values_of(gen: ModuleType, text: str) -> list[object]:
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled, unhandled
    return list(handled["X"].value_ranges)


def test_default_button_is_momentary_discrete_0_1(gen: ModuleType) -> None:
    text = 'elements["X"] = default_button(_("Hint"), devices.ASP_17V, asp_commands.Power, 1, nil)\n'
    (vr,) = _values_of(gen, text)
    assert (vr.kind, vr.values, vr.momentary) == ("discrete", (0.0, 1.0), True)


def test_default_2_position_tumb_is_latching_discrete_0_1(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil, 1)\n"
    )
    (vr,) = _values_of(gen, text)
    assert (vr.kind, vr.values, vr.momentary) == ("discrete", (0.0, 1.0), False)


def test_default_3_position_tumb_default_is_minus_one_zero_one(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_3_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, false, nil, false, nil, nil)\n"
    )
    (vr,) = _values_of(gen, text)
    assert vr.kind == "discrete"
    assert vr.values == (-1.0, 0.0, 1.0)


def test_default_3_position_tumb_custom_arg_limit_changes_endpoints(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_3_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, false, nil, false, nil, {0, 0.3})\n"
    )
    (vr,) = _values_of(gen, text)
    assert vr.values == (0.0, 0.3)


def test_default_3_position_tumb_unresolvable_arg_limit_is_unknown(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = default_3_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, false, nil, false, nil, some_expr)\n"
    )
    (vr,) = _values_of(gen, text)
    assert vr.kind == "unknown"
    assert "arg_limit_" in vr.reason


def test_multiposition_switch_steps_from_count_delta_min(gen: ModuleType) -> None:
    text = (
        'elements["X"] = multiposition_switch(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 148, 11, 0.1, false, 0.0, anim_speed_default, false)\n"
    )
    (vr,) = _values_of(gen, text)
    assert vr.kind == "discrete"
    assert len(vr.values) == 11
    assert vr.values[0] == 0.0
    assert abs(vr.values[-1] - 1.0) < 1e-9


def test_multiposition_switch_missing_count_is_unknown(gen: ModuleType) -> None:
    text = (
        'elements["X"] = multiposition_switch(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 148)\n"
    )
    (vr,) = _values_of(gen, text)
    assert vr.kind == "unknown"
    assert "count_" in vr.reason


def test_triple_switch_is_fixed_four_discrete_values(gen: ModuleType) -> None:
    text = 'elements["X"] = triple_switch(_("Hint"), devices.ASP_17V, asp_commands.Power, 1)\n'
    (vr,) = _values_of(gen, text)
    assert vr.values == (0.0, 0.1, 0.2, 0.3)
    assert vr.momentary is False


def test_default_axis_is_continuous_0_1_with_gain(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_axis(_("Hint"), devices.ASP_17V, asp_commands.Power, '
        "1, 0, 0.05, true, false, false, nil, nil)\n"
    )
    (vr,) = _values_of(gen, text)
    assert (vr.kind, vr.min, vr.max, vr.gain) == ("continuous", 0.0, 1.0, 0.05)


def test_default_axis_limited_custom_range(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_axis_limited(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, 0, 0.1, nil, nil, {-0.15, 0.15})\n"
    )
    (vr,) = _values_of(gen, text)
    assert (vr.kind, vr.min, vr.max, vr.gain) == ("continuous", -0.15, 0.15, 0.1)


def test_default_animated_lever_ignores_its_own_arg_lim_typo(gen: ModuleType) -> None:
    """DCS's own `arg_lim__` typo makes the parameter dead code in the
    real helper -- the generator must not apply it either, even though
    it is a syntactically valid literal pair."""
    text = (
        'elements["X"] = default_animated_lever(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, 2, {5, 9})\n"
    )
    (vr,) = _values_of(gen, text)
    assert vr.values == (0.0, 1.0)


def test_springloaded_3_pos_tumb_default_and_custom(gen: ModuleType) -> None:
    text = (
        'elements["X"] = springloaded_3_pos_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, device_commands.Button_1, 1, nil)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(
        text, _DEVICES, {**_COMMANDS, "device_commands": {"Button_1": 9001}}
    )
    assert not unhandled
    (vr,) = handled["X"].value_ranges
    assert vr.values == (-1.0, 0.0, 1.0) and vr.momentary is True


def test_helper_args_captures_trailing_positional_text(gen: ModuleType) -> None:
    text = (
        'elements["X"] = default_axis(_("Hint"), devices.ASP_17V, asp_commands.Power, '
        "1, 0, 0.05, true, false, false, nil, nil)\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert handled["X"].helper_args == (
        "0",
        "0.05",
        "true",
        "false",
        "false",
        "nil",
        "nil",
    )


def test_helper_args_absent_when_nothing_follows_the_draw_argument(
    gen: ModuleType,
) -> None:
    text = 'elements["X"] = stick_button(_("Hint"), devices.ASP_17V, asp_commands.Power, 1)\n'
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    assert handled["X"].helper_args is None


def test_raw_table_literal_value_ranges_per_action_btn_and_lev(
    gen: ModuleType,
) -> None:
    """`STICK-PTT-PTR`'s own shape: two `BTN` actions, each its own
    `arg_lim` pair -- the second control point (`0.0, 0.5`) from the
    recon, confirmed via the already-committed clean fixture's own
    element."""
    text = (
        'elements["STICK-PTT-PTR"]	= {\n'
        "\tclass 				= {class_type.BTN, class_type.BTN},\n"
        '\thint  				= _("Trigger Button"),\n'
        "\tdevice 				= devices.SPU_8,\n"
        "\taction 				= {spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_TRIGGER_P},\n"
        "\targ 				= {738, 738},\n"
        "\targ_value			= {1.0, 0.5},\n"
        "\targ_lim 			= {{0.0, 1.0}, {0.0, 0.5}},\n"
        "\tcrew_member_access  = {0}\n"
        "}\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    vr0, vr1 = handled["STICK-PTT-PTR"].value_ranges
    assert (vr0.kind, vr0.values, vr0.momentary) == ("discrete", (0.0, 1.0), True)
    assert (vr1.kind, vr1.values, vr1.momentary) == ("discrete", (0.0, 0.5), True)


def test_raw_table_literal_lev_class_is_continuous_with_gain(gen: ModuleType) -> None:
    text = (
        'elements["COLLECTIVE-CORR-PTR"] = {\n'
        "\tclass = {class_type.LEV, class_type.LEV},\n"
        '\thint = _("Collective"),\n'
        "\tdevice = devices.ASP_17V,\n"
        "\taction = {asp_commands.Power, asp_commands.Power},\n"
        "\targ = {40, 41},\n"
        "\targ_value = {0.0, 0.0},\n"
        "\targ_lim = {{-1, 1}, {-1, 1}},\n"
        "\tgain = {0.1, 0.1}\n"
        "}\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    vr0, vr1 = handled["COLLECTIVE-CORR-PTR"].value_ranges
    assert (vr0.kind, vr0.min, vr0.max, vr0.gain) == ("continuous", -1.0, 1.0, 0.1)
    assert (vr1.kind, vr1.min, vr1.max, vr1.gain) == ("continuous", -1.0, 1.0, 0.1)


def test_raw_table_literal_null_class_action_is_unknown(gen: ModuleType) -> None:
    """`BRAKE-LEVEL-OP-PTR`'s own shape: a bare `0` (`class_type.NULL`)
    third action -- never guessed at, reported unknown by name."""
    text = (
        'elements["BRAKE-LEVEL-OP-PTR"] = {\n'
        "\tclass = {class_type.TUMB, class_type.LEV, 0},\n"
        '\thint = _("PKI control"),\n'
        "\tdevice = devices.ASP_17V,\n"
        "\taction = {asp_commands.Power, asp_commands.Power, asp_commands.Power},\n"
        "\targ = {15, 846, 846},\n"
        "\targ_value = {0, 0, 0},\n"
        "\targ_lim = {{0, 1}, {0, 1}, {0, 1}}\n"
        "}\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    vr0, vr1, vr2 = handled["BRAKE-LEVEL-OP-PTR"].value_ranges
    assert vr0.kind == "discrete" and vr0.momentary is False
    assert vr1.kind == "continuous"
    assert vr2.kind == "unknown"
    assert "NULL" in vr2.reason


def test_raw_table_literal_missing_class_field_is_unknown_for_every_action(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = {\n'
        '\thint = _("Hint"),\n'
        "\tdevice = devices.ASP_17V,\n"
        "\taction = {asp_commands.Power},\n"
        "\targ = {1},\n"
        "\targ_lim = {{0, 1}}\n"
        "}\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    (vr,) = handled["X"].value_ranges
    assert vr.kind == "unknown"
    assert "class" in vr.reason


def test_raw_table_literal_missing_arg_lim_field_is_unknown_for_every_action(
    gen: ModuleType,
) -> None:
    text = (
        'elements["X"] = {\n'
        "\tclass = {class_type.BTN},\n"
        '\thint = _("Hint"),\n'
        "\tdevice = devices.ASP_17V,\n"
        "\taction = {asp_commands.Power},\n"
        "\targ = {1}\n"
        "}\n"
    )
    _, handled, unhandled, _, _ = gen.scan_clickabledata(text, _DEVICES, _COMMANDS)
    assert not unhandled
    (vr,) = handled["X"].value_ranges
    assert vr.kind == "unknown"
    assert "arg_lim" in vr.reason


def test_post_assignment_arg_lim_patch_overrides_the_endpoints(
    gen: ModuleType,
) -> None:
    """The two ASP-17 sight switches are patched from the
    `default_2_position_tumb` call's own 0/1 to 0.0/0.5 after the fact --
    `aircraft-layer/research/2026-10-23-mi24p-clickable-value-ranges.md`,
    "Post-assignment patches that change values"."""
    text = (
        'elements["SIGHT-MAN-AUTO-PTR"] = default_2_position_tumb(_("Sight mode"), '
        "devices.ASP_17V, asp_commands.Power, 553, nil)\n"
        'elements["SIGHT-MAN-AUTO-PTR"].arg_value = {0.5,-0.5}\n'
        'elements["SIGHT-MAN-AUTO-PTR"].arg_lim = {{0,0.5},{0,0.5}}\n'
    )
    _, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert not unhandled and patches == 2
    (vr,) = handled["SIGHT-MAN-AUTO-PTR"].value_ranges
    assert vr.kind == "discrete"
    assert vr.values == (0.0, 0.5)
    assert vr.momentary is False


def test_unresolved_arg_value_patch_is_counted_but_not_applied_to_values(
    gen: ModuleType,
) -> None:
    """`arg_value` is the step per click, never a position (the recon's
    own "Reading rule") -- a post-assignment patch to it must not change
    `values` at all."""
    text = (
        'elements["X"] = default_2_position_tumb(_("Hint"), devices.ASP_17V, '
        "asp_commands.Power, 1, nil)\n"
        'elements["X"].arg_value = {0.5,-0.5}\n'
    )
    _, handled, unhandled, patches, _ = gen.scan_clickabledata(
        text, _DEVICES, _COMMANDS
    )
    assert not unhandled and patches == 1
    (vr,) = handled["X"].value_ranges
    assert vr.values == (0.0, 1.0)


def test_render_toml_round_trips_discrete_continuous_and_unknown_value_ranges(
    gen: ModuleType,
) -> None:
    el = gen.RawElement(
        name="X",
        device_id=1,
        device_symbol="SOME_DEVICE",
        cmd_ids=[3001],
        cmd_symbols=["Power"],
        args=[1],
        label="A label",
        shape="tumb",
        seat="pilot",
        seat_explicit=True,
        helper_args=("nil", "1"),
        value_ranges=(
            gen._discrete([0.0, 1.0], momentary=True),
            gen._continuous(0.0, 1.0, gain=0.1),
            gen._unknown_value("no parseable arg_lim"),
        ),
    )
    rendered = gen.render_toml(
        {"X": el},
        "dcs-build",
        {},
        heads=1,
        n_unhandled=0,
        n_post_assigns=0,
        n_ignored=0,
    )
    parsed = tomllib.loads(rendered)
    entry = parsed["elements"]["X"]
    assert entry["helper_args"] == ["nil", "1"]
    values = entry["values"]
    assert values[0] == {"kind": "discrete", "values": [0.0, 1.0], "momentary": True}
    assert values[1] == {"kind": "continuous", "min": 0.0, "max": 1.0, "gain": 0.1}
    assert values[2] == {"kind": "unknown", "reason": "no parseable arg_lim"}


def test_dcs_install_path_set_but_autoupdate_cfg_missing_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_root = tmp_path / "install"
    scripts_dir = install_root / "Mods" / "aircraft" / "Mi-24P" / "Cockpit" / "Scripts"
    scripts_dir.mkdir(parents=True)
    for name in ("devices.lua", "command_defs.lua", "clickabledata.lua"):
        shutil.copyfile(_FIXTURES / "clean" / name, scripts_dir / name)
    monkeypatch.setenv("DCS_INSTALL_PATH", str(install_root))
    out = tmp_path / "effectors-raw.toml"
    result = _run("--write", "--output", str(out))
    assert result.returncode == 1
    assert not out.exists()
    assert "--dcs-build" in result.stderr
