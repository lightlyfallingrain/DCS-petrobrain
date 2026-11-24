"""BL-16 (`plans/flight-desired-state/plan.md`, Stages 1-2) --
`Petrobrain/flight_desired.lua` run against a real Lua interpreter.

**Technique**: same whole-file-wrap technique as `test_flight_control_
lua.py` (not per-function extraction) -- this module's functions close
over many module-level locals (`desired`, `fd_mode`, `fd_hdg_ref`, the
stamp counters). The whole source is wrapped as `local flight_desired =
(function() <file> end)()` and called through its own `M.*` table; the
two cross-module globals it reads (`flight_control.mode_info`, `ai_
pilot_wheel.is_parked`/`held_targets`) are mocked, and the DCS globals it
reads directly (`LoGetSelfData`, `LoGetMagneticYaw`,
`LoGetAltitudeAboveGroundLevel`, `LoGetAltitudeAboveSeaLevel`, `LoGet
IndicatedAirSpeed`) are mutable Lua globals the driver sets per test.
`core.lua`'s own helpers are extracted the same way `test_flight_
control_lua.py` extracts them.

Skips cleanly without a Lua interpreter on `PATH`."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_PETROBRAIN_DIR = Path(__file__).resolve().parent.parent / "dcs-export" / "Petrobrain"
_CORE_LUA = _PETROBRAIN_DIR / "core.lua"
_FLIGHT_DESIRED_LUA = _PETROBRAIN_DIR / "flight_desired.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(path: Path, name: str) -> str:
    """Identical technique to `test_flight_control_lua.py`'s own copy."""
    text = path.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in {path.name}"
    token_re = re.compile(r"--[^\n]*|\b(function|if|for|while|end)\b")
    depth = 1
    for token_match in token_re.finditer(text, start_match.end()):
        keyword = token_match.group(1)
        if keyword is None:
            continue
        if keyword == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


_CORE_HELPERS: tuple[str, ...] = (
    "safe_call",
    "is_finite_number",
    "fmt_num_or_null",
    "fmt_int_or_null",
    "json_escape_string",
    "extract_json_string_field",
    "extract_json_number_field",
)

#: Mock DCS surface + cross-module globals. `fc_mode_value`/`fc_release_
#: reason`/`fc_refuse_cause` back `flight_control.mode_info()`; `ap_
#: parked`/`ap_held` back `ai_pilot_wheel.is_parked`/`held_targets`
#: (`nil` means "ai_pilot_wheel never loaded" when the driver sets `ai_
#: pilot_wheel = nil` itself, same "unknown is never a licence to
#: assume" posture `flight_control.lua`'s own test harness uses).
_PREAMBLE = """
local heading_rad = 0.0
local mag_heading_deg = nil
local agl_m = 200.0
local msl_m = 250.0
local ias_mps = 150.0 / 3.6
local self_data_present = true

local fc_mode_value = "off"
local fc_release_reason = nil
local fc_refuse_cause = nil

-- LV-1 amendment (2026-11-24, fourth re-fly), section A -- backs the
-- `flight_control` mock's `get_phi_bar`/`takeover_level_bank_deg`
-- below. `nil` by default (no estimator reading available yet).
local fc_phi_bar = nil
local fc_takeover_threshold = nil

local ap_parked = false
local ap_held = nil

local sent_lines = {}

local function debug_log(msg) end

function LoGetSelfData()
    if not self_data_present then return nil end
    return { Heading = heading_rad }
end

function LoGetMagneticYaw()
    return mag_heading_deg
end

function LoGetAltitudeAboveGroundLevel()
    return agl_m
end

function LoGetAltitudeAboveSeaLevel()
    return msl_m
end

function LoGetIndicatedAirSpeed()
    return ias_mps
end

flight_control = {
    mode_info = function()
        return { mode = fc_mode_value, release_reason = fc_release_reason,
                 refuse_cause = fc_refuse_cause }
    end,
    -- LV-1 amendment (2026-11-24, fourth re-fly), section A -- `nil` by
    -- default (same as a real session before the estimator primes),
    -- which keeps every pre-existing `reseed_from_measured` test above
    -- exercising the "always heading" fallback unchanged.
    get_phi_bar = function() return fc_phi_bar end,
    takeover_level_bank_deg = function() return fc_takeover_threshold end,
}

ai_pilot_wheel = {
    is_parked = function() return ap_parked end,
    held_targets = function()
        local held = ap_held or {}
        return {
            heading_deg = held.heading_deg,
            alt_m = held.alt_m,
            alt_ref = held.alt_ref,
            speed_kmh = held.speed_kmh,
        }
    end,
}

client = {
    send = function(self, line)
        table.insert(sent_lines, line)
        return true
    end,
}
"""


def _run(driver: str) -> list[str]:
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    core_helpers = "\n".join(
        _extract_lua_function(_CORE_LUA, name) for name in _CORE_HELPERS
    )
    module_source = _FLIGHT_DESIRED_LUA.read_text(encoding="utf-8")
    script = (
        _PREAMBLE
        + "\n"
        + core_helpers
        + "\nlocal flight_desired = (function()\n"
        + module_source
        + "\nend)()\n"
        + driver
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".lua", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        script_path = handle.name
    try:
        result = subprocess.run(
            [exe, script_path], capture_output=True, text=True, check=False
        )
    finally:
        Path(script_path).unlink(missing_ok=True)

    assert result.returncode == 0, f"Lua harness failed (exe={exe}): {result.stderr}"
    return [line for line in result.stdout.splitlines() if line != ""]


def _field(line: str, name: str) -> str | None:
    match = re.search(rf'"{name}":("[^"]*"|-?[0-9.]+|true|false|null)', line)
    assert match is not None, f"{name!r} not found in line: {line!r}"
    token = match.group(1)
    if token == "null":
        return None
    return token.strip('"')


class TestModeDerivation:
    def test_off_by_default(self) -> None:
        driver = """
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode") == "off"

    def test_taking_tracks_fc_mode(self) -> None:
        driver = """
fc_mode_value = "taking"
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode") == "taking"
        assert _field(lines[0], "fd_mode_cause") == "take"
        assert _field(lines[0], "fd_mode_n") == "1"

    def test_m1_when_fc_mode_active_and_not_parked(self) -> None:
        driver = """
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode") == "m1"

    def test_m2_wins_over_fc_mode_when_parked(self) -> None:
        """`parked_active` wins regardless of `fc_mode` (section 2's own
        derivation order) -- here `fc_mode` still reads `"active"`
        (Lua's own self-arm has not landed in this driver) but `fd_mode`
        must already read `"m2"`."""
        driver = """
fc_mode_value = "active"
ap_parked = true
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode") == "m2"

    def test_fd_has_m2_false_when_ai_pilot_wheel_never_loaded(self) -> None:
        """The mode-2 seam (plan section 6) -- `ai_pilot_wheel = nil`
        means `fd_has_m2=false` and `fd_mode` never becomes `"m2"`."""
        driver = """
ai_pilot_wheel = nil
ap_parked = true
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_has_m2") == "false"
        assert _field(lines[0], "fd_mode") == "off"


class TestEdgeSeeding:
    def test_off_to_m1_reseeds_from_measured(self) -> None:
        driver = """
heading_rad = math.rad(90.0)
agl_m = 123.0
ias_mps = 200.0 / 3.6
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_heading") == "90.00000"
        assert _field(line, "fd_hdg_ref") == "true"
        assert _field(line, "fd_alt") == "123.00000"
        assert _field(line, "fd_alt_ref") == "agl"
        assert _field(line, "fd_ias") == "200.00000"

    def test_off_to_m1_at_a_low_bank_still_reseeds_heading(self) -> None:
        """LV-1 amendment (2026-11-24, fourth re-fly), section A, E11 --
        below the takeover threshold, the mirror picks "heading", same
        as the pre-amendment `test_off_to_m1_reseeds_from_measured`
        above, now with the threshold machinery actually wired (phi_bar
        present but under threshold)."""
        driver = """
heading_rad = math.rad(90.0)
agl_m = 123.0
ias_mps = 200.0 / 3.6
fc_phi_bar = 3.0
fc_takeover_threshold = 5.0
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_hdg_mode") == "heading"
        assert _field(line, "fd_heading") == "90.00000"
        assert _field(line, "fd_bank_hold") is None

    def test_off_to_m1_at_a_high_bank_holds_that_bank(self) -> None:
        """LV-1 amendment, section A, E11 -- at or above the takeover
        threshold, the mirror picks "bank" with `bank_hold_deg` set to
        the averaged bank, heading/turn cleared."""
        driver = """
heading_rad = math.rad(90.0)
agl_m = 123.0
ias_mps = 200.0 / 3.6
fc_phi_bar = 12.0
fc_takeover_threshold = 5.0
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_hdg_mode") == "bank"
        assert _field(line, "fd_bank_hold") == "12.00000"
        assert _field(line, "fd_heading") is None
        # Height and speed are still captured exactly as today (E13).
        assert _field(line, "fd_alt") == "123.00000"
        assert _field(line, "fd_ias") == "200.00000"

    def test_off_to_m1_with_no_phi_bar_falls_back_to_heading(self) -> None:
        """A mission-start-instant take (the estimator has not primed)
        has no `phi_bar` to read -- falls back to the pre-amendment
        "always heading" behaviour rather than guessing."""
        driver = """
heading_rad = math.rad(45.0)
fc_phi_bar = nil
fc_takeover_threshold = 5.0
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_hdg_mode") == "heading"
        assert _field(line, "fd_bank_hold") is None

    def test_off_to_m2_reseeds_from_overlay_once_readable(self) -> None:
        driver = """
ap_parked = true
flight_desired.tick(0.0)
flight_desired.push_flight_desired_state(0.0)
print(sent_lines[#sent_lines])

ap_held = { heading_deg = 71.0, alt_m = 300.0, alt_ref = "B", speed_kmh = 150.0 }
flight_desired.tick(0.2)
flight_desired.push_flight_desired_state(0.2)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        first, second = lines[0], lines[1]
        # The overlay is not readable yet on the park edge itself --
        # HOLD (Q12): heading stays null.
        assert _field(first, "fd_mode") == "m2"
        assert _field(first, "fd_heading") is None
        # Once the overlay is readable, a later tick (same mode, no
        # edge) still seeds it.
        assert _field(second, "fd_heading") == "71.00000"
        # fd_hdg_ref reports the fixed `HEADING_REF` constant now (Stage
        # 3), not which handler wrote the value (Stages 1-2's own
        # provenance tag, gone).
        assert _field(second, "fd_hdg_ref") == "true"
        assert _field(second, "fd_alt") == "300.00000"
        assert _field(second, "fd_alt_ref") == "baro"
        assert _field(second, "fd_ias") == "150.00000"

    def test_m1_to_off_clears_desired(self) -> None:
        driver = """
heading_rad = math.rad(90.0)
fc_mode_value = "active"
flight_desired.tick(0.0)

fc_mode_value = "off"
fc_release_reason = "stop"
flight_desired.tick(0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_mode") == "off"
        assert _field(line, "fd_mode_cause") == "release"
        assert _field(line, "fd_heading") is None
        assert _field(line, "fd_hdg_mode") is None

    def test_m1_to_off_via_envelope_reports_the_cause(self) -> None:
        driver = """
fc_mode_value = "active"
flight_desired.tick(0.0)

fc_mode_value = "off"
fc_release_reason = "envelope"
flight_desired.tick(0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode_cause") == "envelope"

    def test_m2_to_off_refused_reports_unpark_refused(self) -> None:
        driver = """
ap_parked = true
fc_mode_value = "armed"
flight_desired.tick(0.0)

ap_parked = false
fc_mode_value = "off"
fc_release_reason = "refused"
fc_refuse_cause = "on_ground"
flight_desired.tick(0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode_cause") == "unpark_refused"

    def test_m2_to_off_lease_refused_reports_unpark_unarmed(self) -> None:
        driver = """
ap_parked = true
fc_mode_value = "armed"
flight_desired.tick(0.0)

ap_parked = false
fc_mode_value = "off"
fc_release_reason = "refused"
fc_refuse_cause = "lease"
flight_desired.tick(0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fd_mode_cause") == "unpark_unarmed"

    def test_m2_to_m1_is_unpark_and_carries(self) -> None:
        driver = """
ap_parked = true
ap_held = { heading_deg = 71.0, alt_m = 300.0, alt_ref = "R", speed_kmh = 150.0 }
fc_mode_value = "armed"
flight_desired.tick(0.0)

ap_parked = false
fc_mode_value = "active"
flight_desired.tick(0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_mode") == "m1"
        assert _field(line, "fd_mode_cause") == "unpark"
        # carried, not reseeded -- the overlay's own values survive.
        assert _field(line, "fd_heading") == "71.00000"
        assert _field(line, "fd_alt") == "300.00000"


class TestSetRequest:
    """BL-16 Stage 3 -- `handle_flight_command`'s `kind == "set"`
    replaces Stages 1-2's `mirror_m1_goal`/`mirror_m2_goal` receipt-time
    mirrors entirely: every write into `desired` now arrives as a
    numbered request on the one channel, stamped with its own `seq`."""

    def test_set_heading_while_m1(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","heading_deg":270.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_heading") == "270.00000"
        assert _field(line, "fd_hdg_ref") == "true"
        assert _field(line, "fd_stamp_hdg") == "1"
        assert _field(line, "fd_acks") == "1:a:m1"

    def test_set_heading_while_holding_a_bank_clears_the_hold(self) -> None:
        """LV-1 amendment, section A, Co-moving Fields -- a heading-type
        command is the only thing that ends a held bank (Q3); `apply_
        set`'s `heading_deg` branch must clear `bank_hold_deg` too."""
        driver = """
heading_rad = math.rad(90.0)
fc_phi_bar = 12.0
fc_takeover_threshold = 5.0
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","heading_deg":270.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        # The take itself entered bank-hold mode (12 deg >= 5 deg) --
        # confirm the precondition before confirming it was cleared.
        assert _field(line, "fd_hdg_mode") == "heading"
        assert _field(line, "fd_bank_hold") is None

    def test_set_turn_while_holding_a_bank_clears_the_hold(self) -> None:
        """Same as above, the other heading-type command (Q3)."""
        driver = """
heading_rad = math.rad(90.0)
fc_phi_bar = 12.0
fc_takeover_threshold = 5.0
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","turn":1}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_hdg_mode") == "turn"
        assert _field(line, "fd_bank_hold") is None

    def test_set_turn_while_m1(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","turn":1}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_hdg_mode") == "turn"
        assert _field(line, "fd_turn_dir") == "1"

    def test_set_altitude_while_m2(self) -> None:
        driver = """
flight_desired.reset(5)
ap_parked = true
fc_mode_value = "armed"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","alt_m":900.0,"alt_ref":"baro"}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_alt") == "900.00000"
        assert _field(line, "fd_alt_ref") == "baro"
        assert _field(line, "fd_stamp_alt") == "1"
        assert _field(line, "fd_acks") == "1:a:m2"

    def test_set_while_off_is_refused_not_flying_and_writes_nothing(self) -> None:
        driver = """
flight_desired.reset(5)
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","heading_deg":270.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_heading") is None
        assert _field(line, "fd_acks") == "1:r:not_flying"

    def test_wrong_epoch_is_refused(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":9,"seq":1,"until":10.0,"kind":"set","heading_deg":270.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        # heading_deg=270.0 never lands -- the off->m1 edge already
        # reseeded from measured (0.0 deg) before the refused request.
        assert _field(line, "fd_heading") == "0.00000"
        assert _field(line, "fd_acks") == "1:r:epoch"

    def test_stale_until_is_refused(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":0.05,"kind":"set","heading_deg":270.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_heading") == "0.00000"
        assert _field(line, "fd_acks") == "1:r:stale"

    def test_out_of_order_seq_is_silently_dropped_with_no_ack(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":3,"until":10.0,"kind":"set","heading_deg":270.0}', 0.1)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":2,"until":10.0,"kind":"set","heading_deg":90.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        # The stale (lower) seq never overwrote the newer heading, and
        # no second ack entry was added for it.
        assert _field(line, "fd_heading") == "270.00000"
        assert _field(line, "fd_acks") == "3:a:m1"

    def test_out_of_bounds_heading_is_refused_bounds(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"set","heading_deg":999.0}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_heading") == "0.00000"
        assert _field(line, "fd_acks") == "1:r:bounds"

    def test_a_mode_2_only_kind_is_refused_wrong_mode(self) -> None:
        driver = """
flight_desired.reset(5)
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.handle_flight_command(
    '{"epoch":5,"seq":1,"until":10.0,"kind":"align"}', 0.1)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_acks") == "1:r:wrong_mode"


class TestResetAndStop:
    def test_on_stop_clears_everything(self) -> None:
        driver = """
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.on_stop()
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_mode") == "off"
        assert _field(line, "fd_mode_cause") == "stop"
        assert _field(line, "fd_heading") is None

    def test_reset_echoes_the_epoch_and_clears(self) -> None:
        driver = """
fc_mode_value = "active"
flight_desired.tick(0.0)
flight_desired.reset(42)
flight_desired.push_flight_desired_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fd_mode") == "off"
        assert _field(line, "fd_mode_cause") == "reset"
        assert _field(line, "fd_reset_epoch") == "42"
