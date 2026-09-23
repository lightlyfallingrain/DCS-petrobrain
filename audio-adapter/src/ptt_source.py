"""Push-to-talk: is the player holding the talk control down right now?

`plans/inbound-speech/plan.md` Stage 4/5. Capture needs one bit of state
and nothing else -- held or not -- and there are two ways to get it:

- **Now (Stage 4): a physical joystick button**, read straight from
  Windows through `winmm.dll`'s `joyGetPosEx` via `ctypes`. No DCS
  involved, which is the entire point of doing it first: the whole
  capture -> transit -> recognition -> command -> readback chain becomes
  testable on the Windows box with the sim closed.
- **Later (Stage 5): the real Mi-24P intercom trigger**, arg 738 read by
  `Export.lua` and published by the collector. `aircraft-layer/research/
  2026-09-19-ptt-gate-feasibility.md` settled the numbers first-party:
  1.0 full press (radio), **0.5 right-press (intercom)**, 0.0 released,
  `crew_member_access = {0}` so it is the pilot's own trigger.

`PTTSource` is what makes that second one a drop-in rather than a rewrite
-- the same shape `TTSEngine`/`STTEngine` already have in this
subproject, and for the same reason: the implementation is the part
expected to change, so the capture loop must not name it.

**`joyGetPosEx` is a legacy API and its limits are real.** It reports at
most 32 buttons per device and addresses devices by a small numeric id
rather than by name, so which of a multi-device pit's controllers it sees
is a property of the hardware. `tools/probe_joystick.py` answers that in
one minute on the actual box; run it before assuming a button number.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import platform
import select
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from ctypes import wintypes
from typing import Protocol, Self

# joyGetDevCaps / joyGetPosEx return codes worth telling apart. Anything
# else is reported by number rather than guessed at.
JOYERR_NOERROR = 0
MMSYSERR_BADDEVICEID = 2
MMSYSERR_NODRIVER = 6
JOYERR_PARMS = 165
JOYERR_UNPLUGGED = 167

# JOY_RETURNBUTTONS alone. The axes are deliberately not requested: this
# is a button gate, and asking for less means one fewer thing that can
# fail on an odd device.
JOY_RETURNBUTTONS = 0x00000080

MAXPNAMELEN = 32
MAX_JOYSTICKOEMVXDNAME = 260

#: The legacy API's device-id space. `joyGetNumDevs()` reports how many
#: ids the *driver* supports (16 on every current Windows), not how many
#: are plugged in -- a scan bound, not a device count.
MAX_DEVICE_IDS = 16

#: The API's own per-device button ceiling. A stick with more buttons
#: than this is not broken; its high buttons are simply invisible here,
#: which is exactly what the probe exists to reveal before anything is
#: built on a particular button number.
MAX_BUTTONS = 32


class PTTError(RuntimeError):
    """Raised when a PTT source cannot be read at all -- wrong platform,
    no driver, device unplugged mid-flight. Distinct from "not pressed":
    a source that answers `False` is working, one that raises is not."""


class PTTSource(Protocol):
    """One bit of state, polled. Implementations must be cheap enough to
    call at tens of hertz and must not block -- the capture loop's
    responsiveness is the difference between catching the first syllable
    and clipping it."""

    def is_down(self) -> bool:
        """True while the player holds the talk control. Raises
        `PTTError` if the source itself has failed."""
        ...


class JOYCAPSW(ctypes.Structure):
    """`JOYCAPSW` from mmsystem.h -- what one device can do."""

    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("szPname", wintypes.WCHAR * MAXPNAMELEN),
        ("wXmin", wintypes.UINT),
        ("wXmax", wintypes.UINT),
        ("wYmin", wintypes.UINT),
        ("wYmax", wintypes.UINT),
        ("wZmin", wintypes.UINT),
        ("wZmax", wintypes.UINT),
        ("wNumButtons", wintypes.UINT),
        ("wPeriodMin", wintypes.UINT),
        ("wPeriodMax", wintypes.UINT),
        ("wRmin", wintypes.UINT),
        ("wRmax", wintypes.UINT),
        ("wUmin", wintypes.UINT),
        ("wUmax", wintypes.UINT),
        ("wVmin", wintypes.UINT),
        ("wVmax", wintypes.UINT),
        ("wCaps", wintypes.UINT),
        ("wMaxAxes", wintypes.UINT),
        ("wNumAxes", wintypes.UINT),
        ("wMaxButtons", wintypes.UINT),
        ("szRegKey", wintypes.WCHAR * MAXPNAMELEN),
        ("szOEMVxD", wintypes.WCHAR * MAX_JOYSTICKOEMVXDNAME),
    ]


class JOYINFOEX(ctypes.Structure):
    """`JOYINFOEX` from mmsystem.h -- one poll's worth of state."""

    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("dwXpos", wintypes.DWORD),
        ("dwYpos", wintypes.DWORD),
        ("dwZpos", wintypes.DWORD),
        ("dwRpos", wintypes.DWORD),
        ("dwUpos", wintypes.DWORD),
        ("dwVpos", wintypes.DWORD),
        ("dwButtons", wintypes.DWORD),
        ("dwButtonNumber", wintypes.DWORD),
        ("dwPOV", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("dwReserved2", wintypes.DWORD),
    ]


def error_name(code: int) -> str:
    """Name the return codes worth telling apart; number the rest."""
    known = {
        MMSYSERR_BADDEVICEID: "no such device id",
        MMSYSERR_NODRIVER: "no joystick driver",
        JOYERR_PARMS: "bad parameters",
        JOYERR_UNPLUGGED: "unplugged",
    }
    return known.get(code, f"error {code}")


def pressed_buttons(mask: int, count: int) -> list[int]:
    """Button indices currently down, 0-based, as the API numbers them.

    Pure, so the bit arithmetic is testable off Windows -- which matters
    more than it looks: this is the one piece of the winmm path that can
    be wrong in a way no amount of running the probe would reveal, since
    a one-off in the numbering still produces plausible-looking output.
    """
    return [index for index in range(count) if mask & (1 << index)]


def load_winmm() -> ctypes.CDLL:
    """The `winmm.dll` handle every call below needs.

    Raises `PTTError` off Windows rather than returning a degraded
    object: there is nothing to fall back to, and a clear failure at
    startup beats a joystick that silently never fires.

    Typed and reached as `CDLL` -- which `WinDLL` subclasses -- because
    `ctypes.WinDLL` does not exist off Windows, so naming it directly
    makes this module fail to type-check on the Mac where the rest of
    the capture chain is developed. The `getattr` is doing the same job
    for the same reason, not hiding anything.
    """
    if platform.system() != "Windows":
        raise PTTError("joystick PTT needs Windows -- winmm.dll is the whole mechanism")
    # `ctypes.WinDLL` does not exist off Windows, so it is resolved at
    # call time rather than named at import time -- the `noqa` is that,
    # not a dodge.
    windll = getattr(ctypes, "WinDLL")  # noqa: B009
    loaded: ctypes.CDLL = windll("winmm")
    return loaded


class JoystickDevice:
    """One legacy joystick id, opened and pollable."""

    def __init__(self, device_id: int, name: str, button_count: int) -> None:
        self.device_id = device_id
        self.name = name
        self.button_count = button_count


def enumerate_devices(winmm: ctypes.CDLL | None = None) -> list[JoystickDevice]:
    """Every legacy device id that both reports caps *and* answers a poll.

    Both halves are needed: a driver-known id can have nothing plugged
    into it, and only a successful poll proves a device is really there.
    """
    library = winmm if winmm is not None else load_winmm()
    num_ids = min(int(library.joyGetNumDevs()), MAX_DEVICE_IDS)
    devices: list[JoystickDevice] = []
    for device_id in range(num_ids):
        caps = JOYCAPSW()
        if int(
            library.joyGetDevCapsW(device_id, ctypes.byref(caps), ctypes.sizeof(caps))
        ) != (JOYERR_NOERROR):
            continue
        info = JOYINFOEX()
        info.dwSize = ctypes.sizeof(info)
        info.dwFlags = JOY_RETURNBUTTONS
        if int(library.joyGetPosEx(device_id, ctypes.byref(info))) != JOYERR_NOERROR:
            continue
        devices.append(
            JoystickDevice(
                device_id=device_id,
                name=str(caps.szPname) or "(unnamed)",
                button_count=min(int(caps.wNumButtons), MAX_BUTTONS),
            )
        )
    return devices


def read_button_mask(device_id: int, winmm: ctypes.CDLL) -> int:
    """One `joyGetPosEx` poll, returning the raw button bitmask."""
    info = JOYINFOEX()
    info.dwSize = ctypes.sizeof(info)
    info.dwFlags = JOY_RETURNBUTTONS
    code = int(winmm.joyGetPosEx(device_id, ctypes.byref(info)))
    if code != JOYERR_NOERROR:
        raise PTTError(f"joystick {device_id} poll failed: {error_name(code)}")
    return int(info.dwButtons)


class JoystickPTT:
    """`PTTSource` over one physical joystick button (Stage 4).

    `button` is 0-based, as `joyGetPosEx` numbers them and as
    `tools/probe_joystick.py` prints them. Note DCS's own binding UI
    numbers buttons from 1, so a button the probe calls 7 appears as
    "JOY_BTN8" there -- read the number off the probe, not off DCS.
    """

    def __init__(
        self,
        device_id: int,
        button: int,
        winmm: ctypes.CDLL | None = None,
    ) -> None:
        if button < 0 or button >= MAX_BUTTONS:
            raise PTTError(
                f"button {button} is outside the legacy API's 0-{MAX_BUTTONS - 1} range"
            )
        self._device_id = device_id
        self._button = button
        self._winmm = winmm if winmm is not None else load_winmm()
        # Fail at construction rather than on the first press: a bad
        # device id discovered when the player presses to talk is a
        # failure in the worst place, mid-flight and hands-full.
        read_button_mask(self._device_id, self._winmm)

    def is_down(self) -> bool:
        mask = read_button_mask(self._device_id, self._winmm)
        return bool(mask & (1 << self._button))


class KeyTogglePTT:
    """`PTTSource` driven by a keypress, for development without a stick.

    **Press to start, press again to stop -- not a true hold.** A
    terminal receives no key-release event, so a held key is not
    detectable portably; `tools/record_corpus.py` hit the same wall and
    made the same choice, and its reasoning carries over unchanged: the
    boundaries are what matter, and they are the same either way, since
    the clip still starts and ends where the speaker decides rather than
    on a timer.

    This exists so the whole capture chain -- mic, gate, transit,
    recognition, match, readback -- can be exercised on the Mac with no
    Windows box and no joystick. `JoystickPTT` is the real gate, and
    `DcsPTT` (Stage 5) is the real one after that; all three answer the
    same single question, which is the point of the protocol.
    """

    def __init__(self, key: str = " ") -> None:
        self._key = key
        self._down = False

    def __enter__(self) -> Self:
        self._raw = _raw_key_mode()
        self._raw.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        self._raw.__exit__(None, None, None)

    def is_down(self) -> bool:
        while True:
            key = _read_key_nonblocking()
            if key is None:
                break
            if key == self._key:
                self._down = not self._down
            elif key in ("\x03", "q"):
                raise KeyboardInterrupt
        return self._down


@contextlib.contextmanager
def _raw_key_mode() -> Iterator[None]:
    """Read single keypresses without waiting for Enter.

    `cbreak` rather than `raw` deliberately: cbreak leaves signal
    generation on, so Ctrl-C still interrupts instead of arriving as an
    ordinary byte. Windows needs nothing -- `msvcrt.getch` already reads
    one key.
    """
    if sys.platform == "win32" or not sys.stdin.isatty():
        yield
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _read_key_nonblocking() -> str | None:
    """One pending keypress, or `None` if none is waiting.

    Non-blocking is the whole requirement: the capture loop polls this
    alongside everything else and must never stall waiting for a key.
    """
    if sys.platform == "win32":
        import msvcrt

        if not msvcrt.kbhit():
            return None
        return msvcrt.getch().decode("latin-1", "replace").lower()
    if not sys.stdin.isatty():
        return None
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    char = sys.stdin.read(1)
    return char.lower() if char else None


#: How long the trigger must sit at its intercom stop before it counts as
#: held. **This is not a tuning knob, it is a measurement.** A full press
#: transits the intercom stop on its way to the radio stop -- 19 ms and
#: 32 ms in the two presses the live probe captured (2026-09-23,
#: `aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`, third
#: addendum) -- because a two-stage mechanical trigger must pass through
#: its first stop to reach its second. Without a debounce, every radio call
#: to ATC would open a capture for ~20 ms. 100 ms is three times the worst
#: observed transit and still an order of magnitude below any deliberate
#: press-and-speak gesture.
INTERCOM_DEBOUNCE_S = 0.1

#: Poll rate for `GET /ptt/state`. Fast enough that a press is noticed well
#: inside the audio device's own ~140 ms open time (so the poll is never the
#: thing that clips a first syllable), slow enough not to hammer a
#: `ThreadingHTTPServer` sharing a box with DCS.
DEFAULT_DCS_POLL_HZ = 30.0


class DcsPTT:
    """`PTTSource` over the aircraft's own intercom trigger (Stage 5).

    Reads `GET /ptt/state` on a running collector, which publishes arg 738
    as `Export.lua` reports it. The collector is on the same machine as the
    capture process, so this is an HTTP hop over loopback -- deliberately,
    because it keeps the subproject boundary the project already uses rather
    than importing across it. (If capture ever moves *into* the collector,
    which `audio-adapter/ROADMAP.md` argues it should at this stage, this
    class is what disappears.)

    **Two behaviours beyond "is it pressed", both from measurement:**

    - **The intercom stop is debounced** (`INTERCOM_DEBOUNCE_S`), because a
      full press transits it.
    - **A full press latches a discard.** Debouncing stops a capture
      *starting* on a fast radio press; it cannot help a slow one that
      dwells past the window. So if the trigger ever reaches the radio stop
      while a capture is running, `discard_requested()` returns True and the
      clip is dropped -- the player moved to the radio, and what they said
      was not addressed to the crew.

    A failed read raises `PTTError` rather than reporting "not pressed":
    a dead collector and a released trigger must not look the same.
    """

    def __init__(
        self,
        collector_url: str,
        timeout_s: float = 1.0,
        debounce_s: float = INTERCOM_DEBOUNCE_S,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = f"{collector_url.rstrip('/')}/ptt/state"
        self._timeout_s = timeout_s
        self._debounce_s = debounce_s
        self._monotonic = monotonic
        self._intercom_since: float | None = None
        self._radio_latched = False

    def _read(self) -> dict[str, object] | None:
        try:
            with urllib.request.urlopen(self._url, timeout=self._timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise PTTError(f"could not read {self._url}: {exc}") from exc
        if payload is None:
            # The trigger has not moved since the collector started. That is
            # the ordinary state at startup, not a failure -- Export.lua
            # sends a line only on change -- and it means "not pressed".
            return None
        if not isinstance(payload, dict):
            raise PTTError(
                f"{self._url} returned {type(payload).__name__}, not an object"
            )
        return payload

    def is_down(self) -> bool:
        payload = self._read()
        if payload is None:
            self._intercom_since = None
            return False

        if bool(payload.get("radio")):
            # Latched, not returned: the discard is consumed at release, by
            # which time the trigger has usually passed back through 0.
            self._radio_latched = True
            self._intercom_since = None
            return False

        if not bool(payload.get("intercom")):
            self._intercom_since = None
            return False

        now = self._monotonic()
        if self._intercom_since is None:
            self._intercom_since = now
        return (now - self._intercom_since) >= self._debounce_s

    def discard_requested(self) -> bool:
        """True once if the trigger reached the radio stop since the last
        call. Consumed by reading it -- the capture loop asks exactly once,
        at release."""
        latched = self._radio_latched
        self._radio_latched = False
        return latched
