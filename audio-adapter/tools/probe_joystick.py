#!/usr/bin/env python3
"""Probe: does Windows' legacy joystick API see the HOTAS buttons?

Stage 4 of `plans/inbound-speech/plan.md` gates capture on a push-to-talk
control, and the first one is a physical joystick button read straight
from Windows -- the fallback path `aircraft-layer/research/
2026-09-19-ptt-gate-feasibility.md` named at the end of its "Possible
Approaches": `winmm.dll`'s `joyGetPosEx` through `ctypes`, no pip package
(this subproject is stdlib-only, `audio-adapter/CLAUDE.md`).

**That API is legacy, and this probe exists because of one specific
doubt.** `joyGetPosEx` predates DirectInput: it exposes at most 32
buttons per device and addresses devices by a small numeric id rather
than by name. A modern DCS pit is usually several separate USB devices
(stick, throttle, pedals), and whether every one of them appears under a
legacy id -- and whether the button the player would actually press falls
inside the first 32 -- is a property of the hardware, not something that
can be reasoned out from here. So: run this, press the button, read the
number back.

The winmm binding itself lives in `src/ptt_source.py`, which is also what
capture uses in flight. Sharing it is the point: a probe with its own
copy of the structs would drift from the thing it is supposed to be
vouching for.

    # Windows -- stdlib only, no venv needed
    set PYTHONPATH=src
    python tools\\probe_joystick.py

    # ...or watch one device only, once you know its id
    python tools\\probe_joystick.py --device 1

Prints every device the legacy API answers for, then the index of each
button as it goes down and up, with how long it was held. Ctrl-C to stop.
Nothing here touches DCS -- and since DCS does not take exclusive control
of joysticks, it working with the sim running is expected too.

The button number this prints is what `python -m audio_adapter.capture
--joystick-button N` wants. Note DCS's own binding UI numbers buttons
from 1, so button 7 here is "JOY_BTN8" there.
"""

from __future__ import annotations

import argparse
import sys
import time

from ptt_source import (
    MAX_BUTTONS,
    PTTError,
    enumerate_devices,
    load_winmm,
    pressed_buttons,
    read_button_mask,
)


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

    try:
        winmm = load_winmm()
    except PTTError as exc:
        print(exc)
        return 2

    print(
        f"Driver supports {int(winmm.joyGetNumDevs())} device ids (a ceiling, not a count).\n"
    )

    devices = enumerate_devices(winmm)
    for device in devices:
        print(
            f"  id {device.device_id}: {device.name} -- {device.button_count} buttons"
        )

    if not devices:
        print(
            "\nNo device answered a poll. The legacy API does not see this hardware, "
            "so joystick PTT is the wrong route for it -- report that back rather "
            "than reconfiguring anything."
        )
        return 1

    if args.device is not None:
        chosen = next((d for d in devices if d.device_id == args.device), None)
        if chosen is None:
            ids = [d.device_id for d in devices]
            print(f"\nDevice id {args.device} did not answer. Ids that did: {ids}")
            return 1
    else:
        chosen = devices[0]

    button_count = min(chosen.button_count, MAX_BUTTONS)
    print(
        f"\nWatching id {chosen.device_id} ({chosen.name}), {button_count} buttons. "
        "Press the button you would use for PTT. Ctrl-C to stop.\n"
    )

    previous: set[int] = set()
    down_at: dict[int, float] = {}
    interval = 1.0 / args.poll_hz if args.poll_hz > 0 else 0.0

    try:
        while True:
            try:
                mask = read_button_mask(chosen.device_id, winmm)
            except PTTError as exc:
                print(f"poll failed: {exc}")
                return 1
            now = set(pressed_buttons(mask, button_count))
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
