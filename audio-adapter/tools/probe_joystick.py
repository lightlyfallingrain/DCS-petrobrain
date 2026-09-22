#!/usr/bin/env python3
"""Probe: does Windows' legacy joystick API see the HOTAS buttons?

Stage 4 of `plans/inbound-speech/plan.md` needs a push-to-talk gate that
works *before* any DCS dependency exists, so the first PTT source is a
physical joystick button read directly from Windows -- the fallback path
`aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md` named at the
end of its "Possible Approaches": `winmm.dll`'s `joyGetPosEx`, reached
through `ctypes`, no pip package (this subproject is stdlib-only,
`audio-adapter/CLAUDE.md`).

**That API is legacy, and this probe exists because of one specific
doubt.** `joyGetPosEx` predates DirectInput: it exposes at most 32
buttons per device and addresses devices by a small numeric id rather
than by name. A modern DCS pit is usually several separate USB devices
(stick, throttle, pedals), and whether every one of them appears under a
legacy id -- and whether the button the user would actually press lands
inside the first 32 -- is a property of their hardware, not something
that can be reasoned out from here. So: run this, press the button, read
the number back. If the button never appears, the whole joystick-PTT
route is wrong for this hardware and Stage 4 should trigger some other
way; better to learn that in one minute than after the capture chain is
built on it.

Nothing here touches DCS. Run it with DCS closed -- although note DCS
does not take exclusive control of joysticks, so it working while DCS
runs is expected too.

    # Windows -- stdlib only, no venv needed
    python tools\\probe_joystick.py

    # ...or watch one device only, once you know its id
    python tools\\probe_joystick.py --device 1

It prints every device the legacy API answers for, then polls the chosen
one and prints the index of each button as it goes down and up. Ctrl-C
to stop.
"""

from __future__ import annotations

import argparse
import ctypes
import platform
import sys
import time
from ctypes import wintypes

# joyGetDevCaps / joyGetPosEx return codes we distinguish. Anything else
# is reported by number rather than guessed at.
JOYERR_NOERROR = 0
MMSYSERR_BADDEVICEID = 2
MMSYSERR_NODRIVER = 6
JOYERR_PARMS = 165
JOYERR_UNPLUGGED = 167

# JOY_RETURNBUTTONS alone. The axes are deliberately not requested: this
# probe is about buttons, and asking for less means one fewer thing that
# can fail on an odd device.
JOY_RETURNBUTTONS = 0x00000080

MAXPNAMELEN = 32
MAX_JOYSTICKOEMVXDNAME = 260

# The legacy API's device-id space. joyGetNumDevs() reports how many ids
# the *driver* supports (16 on every current Windows), not how many are
# plugged in, so it is a scan bound rather than a device count.
MAX_DEVICE_IDS = 16


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


def _err_name(code: int) -> str:
    """Name the return codes worth telling apart; number the rest."""
    known = {
        MMSYSERR_BADDEVICEID: "no such device id",
        MMSYSERR_NODRIVER: "no joystick driver",
        JOYERR_PARMS: "bad parameters",
        JOYERR_UNPLUGGED: "unplugged",
    }
    return known.get(code, f"error {code}")


def _pressed(mask: int, count: int) -> list[int]:
    """Button indices currently down, 0-based, as the API numbers them."""
    return [i for i in range(count) if mask & (1 << i)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="legacy device id to watch (default: the first that answers)",
    )
    parser.add_argument(
        "--poll-hz",
        type=float,
        default=60.0,
        help="poll rate while watching (default: 60)",
    )
    args = parser.parse_args(argv)

    if platform.system() != "Windows":
        # Not a soft warning: winmm does not exist here, so there is
        # nothing to degrade to.
        print("This probe only runs on Windows -- winmm.dll is the whole mechanism.")
        return 2

    winmm = ctypes.WinDLL("winmm")

    num_ids = int(winmm.joyGetNumDevs())
    print(f"Driver supports {num_ids} device ids (that is a ceiling, not a count).\n")

    found: list[tuple[int, JOYCAPSW]] = []
    for device_id in range(min(num_ids, MAX_DEVICE_IDS)):
        caps = JOYCAPSW()
        rc = int(
            winmm.joyGetDevCapsW(device_id, ctypes.byref(caps), ctypes.sizeof(caps))
        )
        if rc != JOYERR_NOERROR:
            continue
        # A driver-known id can still have nothing plugged into it; only
        # a successful poll proves a device is actually present.
        info = JOYINFOEX()
        info.dwSize = ctypes.sizeof(info)
        info.dwFlags = JOY_RETURNBUTTONS
        poll_rc = int(winmm.joyGetPosEx(device_id, ctypes.byref(info)))
        state = "connected" if poll_rc == JOYERR_NOERROR else _err_name(poll_rc)
        print(
            f"  id {device_id}: {caps.szPname or '(unnamed)'} -- "
            f"{caps.wNumButtons} buttons (max {caps.wMaxButtons}), {state}"
        )
        if poll_rc == JOYERR_NOERROR:
            found.append((device_id, caps))

    if not found:
        print(
            "\nNo device answered a poll. The legacy API does not see this hardware, "
            "so joystick PTT is the wrong route -- report this back rather than "
            "reconfiguring anything."
        )
        return 1

    if args.device is not None:
        chosen = next((entry for entry in found if entry[0] == args.device), None)
        if chosen is None:
            print(
                f"\nDevice id {args.device} did not answer. Ids that did: {[d for d, _ in found]}"
            )
            return 1
    else:
        chosen = found[0]

    device_id, caps = chosen
    button_count = min(int(caps.wNumButtons), 32)
    print(
        f"\nWatching id {device_id} ({caps.szPname or 'unnamed'}), "
        f"{button_count} buttons. Press the button you would use for PTT. Ctrl-C to stop.\n"
    )

    info = JOYINFOEX()
    info.dwSize = ctypes.sizeof(info)
    info.dwFlags = JOY_RETURNBUTTONS
    previous: set[int] = set()
    interval = 1.0 / args.poll_hz if args.poll_hz > 0 else 0.0
    down_at: dict[int, float] = {}

    try:
        while True:
            rc = int(winmm.joyGetPosEx(device_id, ctypes.byref(info)))
            if rc != JOYERR_NOERROR:
                print(f"poll failed: {_err_name(rc)}")
                return 1
            now = set(_pressed(int(info.dwButtons), button_count))
            timestamp = time.monotonic()
            for index in sorted(now - previous):
                down_at[index] = timestamp
                print(f"  button {index:>2}  DOWN")
            for index in sorted(previous - now):
                held_ms = (timestamp - down_at.pop(index, timestamp)) * 1000.0
                print(f"  button {index:>2}  UP    (held {held_ms:.0f} ms)")
            previous = now
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
