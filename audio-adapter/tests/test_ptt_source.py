"""The winmm PTT path, as far as it can be tested off Windows.

The button bitmask arithmetic is the piece worth testing hardest, and
not because it is subtle: it is the one part of this path that can be
wrong while *looking* right. A one-off in the numbering still produces
a probe printout full of plausible button numbers, and the error only
surfaces as "the button I bound does nothing", on the Windows box, in
flight. So the bit decode and the `JoystickPTT` selection logic are
driven here against a fake winmm, and only the library load itself is
left to the real platform.
"""

from __future__ import annotations

import ctypes
import platform

import pytest

from ptt_source import (
    JOYERR_NOERROR,
    JOYERR_UNPLUGGED,
    MAX_BUTTONS,
    JoystickPTT,
    KeyTogglePTT,
    PTTError,
    error_name,
    load_winmm,
    pressed_buttons,
)


class FakeWinmm:
    """Stands in for `winmm.dll`: only `joyGetPosEx` is reached by the
    code under test, and it writes its result into the caller's struct
    exactly as the real one does."""

    def __init__(self, mask: int = 0, code: int = JOYERR_NOERROR) -> None:
        self.mask = mask
        self.code = code
        self.polls = 0

    def joyGetPosEx(self, device_id: int, info_ref: object) -> int:
        self.polls += 1
        if self.code == JOYERR_NOERROR:
            info = ctypes.cast(
                info_ref,
                ctypes.POINTER(type(info_ref._obj)),  # type: ignore[attr-defined]
            ).contents
            info.dwButtons = self.mask
        return self.code


def test_no_buttons_pressed() -> None:
    assert pressed_buttons(0b0, 8) == []


def test_single_button_is_zero_based() -> None:
    """Bit 0 is button 0. DCS's own binding UI numbers from 1, which is
    exactly the off-by-one this asserts against."""
    assert pressed_buttons(0b1, 8) == [0]
    assert pressed_buttons(0b1000_0000, 8) == [7]


def test_several_buttons_at_once() -> None:
    assert pressed_buttons(0b0000_1001, 8) == [0, 3]


def test_buttons_beyond_the_count_are_not_reported() -> None:
    """A device reporting 4 buttons must not surface bit 5 as button 5,
    whatever the driver leaves in the high bits."""
    assert pressed_buttons(0b1111_1111, 4) == [0, 1, 2, 3]


def test_the_highest_legacy_button_is_still_reachable() -> None:
    assert pressed_buttons(1 << 31, MAX_BUTTONS) == [31]


def test_error_names_the_codes_worth_distinguishing() -> None:
    assert "unplugged" in error_name(JOYERR_UNPLUGGED)


def test_error_numbers_the_rest_rather_than_guessing() -> None:
    assert error_name(4242) == "error 4242"


def test_joystick_ptt_reports_its_own_button_only() -> None:
    winmm = FakeWinmm(mask=0b0000_1000)
    ptt = JoystickPTT(device_id=0, button=3, winmm=winmm)  # type: ignore[arg-type]
    assert ptt.is_down()

    other = JoystickPTT(device_id=0, button=2, winmm=winmm)  # type: ignore[arg-type]
    assert not other.is_down()


def test_joystick_ptt_follows_the_mask_between_polls() -> None:
    winmm = FakeWinmm(mask=0)
    ptt = JoystickPTT(device_id=0, button=5, winmm=winmm)  # type: ignore[arg-type]
    assert not ptt.is_down()
    winmm.mask = 1 << 5
    assert ptt.is_down()
    winmm.mask = 0
    assert not ptt.is_down()


def test_joystick_ptt_polls_the_device_at_construction() -> None:
    """Failing at startup rather than on the first press is deliberate:
    a bad device id discovered when the player presses to talk is a
    failure in the worst possible place."""
    winmm = FakeWinmm(code=JOYERR_UNPLUGGED)
    with pytest.raises(PTTError, match="unplugged"):
        JoystickPTT(device_id=3, button=0, winmm=winmm)  # type: ignore[arg-type]


def test_joystick_ptt_rejects_a_button_outside_the_legacy_range() -> None:
    winmm = FakeWinmm()
    with pytest.raises(PTTError, match="outside"):
        JoystickPTT(device_id=0, button=MAX_BUTTONS, winmm=winmm)  # type: ignore[arg-type]
    with pytest.raises(PTTError, match="outside"):
        JoystickPTT(device_id=0, button=-1, winmm=winmm)  # type: ignore[arg-type]


def test_a_device_that_dies_mid_flight_raises_rather_than_reading_false() -> None:
    """ "Not pressed" and "the stick is gone" must not look the same --
    a dead device silently reporting False is a talk control that never
    fires and never explains itself."""
    winmm = FakeWinmm(mask=0)
    ptt = JoystickPTT(device_id=0, button=0, winmm=winmm)  # type: ignore[arg-type]
    winmm.code = JOYERR_UNPLUGGED
    with pytest.raises(PTTError):
        ptt.is_down()


@pytest.mark.skipif(platform.system() == "Windows", reason="winmm exists here")
def test_load_winmm_refuses_off_windows() -> None:
    with pytest.raises(PTTError, match="Windows"):
        load_winmm()


def test_key_toggle_starts_up() -> None:
    """Press-to-start/press-to-stop, so the initial state is 'not
    talking' -- the opposite would record from launch."""
    assert not KeyTogglePTT()._down
