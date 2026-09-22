"""`python -m audio_adapter.capture` -- the push-to-talk capture process.

`plans/inbound-speech/plan.md` Stage 4. Runs where the microphone is:
the Windows box in flight, or the Mac while developing. It records while
the talk control is held, gates the clip, and POSTs it to a running
adapter's `POST /transcribe`; body-layer picks the result up from
`GET /transcripts/poll` as it already does.

**Two PTT sources, same protocol.**

- `--ptt key` (default off Windows): space starts, space stops. Press to
  start / press to stop rather than a true hold, because a terminal gets
  no key-release event -- `tools/record_corpus.py` hit the same wall and
  made the same choice. This is what makes the whole chain runnable on
  the Mac with no joystick and no sim.
- `--ptt joystick --joystick-button N`: a real held button, read through
  `winmm` on Windows. Run `tools/probe_joystick.py` first to get the
  device id and the button number -- and note it numbers from 0 while
  DCS's binding UI numbers from 1, so the probe's button 7 is DCS's
  "JOY_BTN8".

Stage 5 adds a third (the real Mi-24P intercom trigger, arg 738 via the
collector) and nothing else in this file changes.

    # Mac, everything local: adapter in one terminal, capture in another
    PYTHONPATH=src .venv/bin/python -m audio_adapter --whisper-model <model.bin>
    PYTHONPATH=src .venv/bin/python -m audio_adapter.capture

    # Windows, adapter on the Mac
    set PYTHONPATH=src
    python -m audio_adapter.capture --adapter-url http://<mac-ip>:7795 ^
        --ptt joystick --joystick-device 0 --joystick-button 7 ^
        --input-device Headset
"""

from __future__ import annotations

import argparse
import sys
import time

from audio_capture import (
    DEFAULT_MAX_CLIP_S,
    DEFAULT_MIN_CLIP_S,
    DEFAULT_MIN_PEAK,
    DEFAULT_TAIL_S,
    ClipGate,
    SoxRecorder,
    sox_available,
)
from capture_loop import CaptureLoop
from ptt_source import JoystickPTT, KeyTogglePTT, PTTError, PTTSource
from transcribe_client import TranscribeClient

DEFAULT_ADAPTER_URL = "http://127.0.0.1:7795"
DEFAULT_POLL_HZ = 60.0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m audio_adapter.capture",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument(
        "--ptt",
        choices=("key", "joystick"),
        default="key",
        help="talk control: a keypress (dev) or a joystick button (Windows)",
    )
    parser.add_argument("--joystick-device", type=int, default=0)
    parser.add_argument(
        "--joystick-button",
        type=int,
        default=0,
        help="0-based, as tools/probe_joystick.py prints it (DCS numbers from 1)",
    )
    parser.add_argument(
        "--input-driver",
        default=None,
        help="sox input driver; defaults to waveaudio on Windows, sox's own default elsewhere",
    )
    parser.add_argument(
        "--input-device",
        default=None,
        help="sox input device (index or name substring) -- the system default is rarely the headset",
    )
    parser.add_argument("--tail-s", type=float, default=DEFAULT_TAIL_S)
    parser.add_argument("--max-clip-s", type=float, default=DEFAULT_MAX_CLIP_S)
    parser.add_argument("--min-clip-s", type=float, default=DEFAULT_MIN_CLIP_S)
    parser.add_argument("--min-peak", type=float, default=DEFAULT_MIN_PEAK)
    parser.add_argument("--poll-hz", type=float, default=DEFAULT_POLL_HZ)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not sox_available():
        print(
            "`sox` not found. macOS: brew install sox. "
            "Windows: the installer from sox.sourceforge.net.",
            file=sys.stderr,
        )
        return 1

    recorder = SoxRecorder(
        driver=args.input_driver,
        device=args.input_device,
        max_clip_s=args.max_clip_s,
    )
    gate = ClipGate(min_duration_s=args.min_clip_s, min_peak=args.min_peak)
    client = TranscribeClient(args.adapter_url)

    key_ptt: KeyTogglePTT | None = None
    ptt: PTTSource
    if args.ptt == "joystick":
        try:
            ptt = JoystickPTT(args.joystick_device, args.joystick_button)
        except PTTError as exc:
            print(f"joystick PTT unavailable: {exc}", file=sys.stderr)
            print(
                "Run tools/probe_joystick.py to see what the API sees.", file=sys.stderr
            )
            return 1
        print(
            f"PTT: joystick {args.joystick_device} button {args.joystick_button} "
            "(hold to talk). Ctrl-C to stop."
        )
    else:
        key_ptt = KeyTogglePTT()
        ptt = key_ptt
        print("PTT: SPACE starts, SPACE stops. `q` or Ctrl-C to quit.")

    print(f"Posting clips to {args.adapter_url}/transcribe")
    print(
        "Press, then speak -- the first ~0.14 s after a press is the audio "
        "device opening and is not captured.\n"
    )

    loop = CaptureLoop(
        ptt=ptt,
        recorder=recorder,
        gate=gate,
        sink=client.transcribe,
        tail_s=args.tail_s,
    )
    interval = 1.0 / args.poll_hz if args.poll_hz > 0 else 0.0

    try:
        if key_ptt is not None:
            with key_ptt:
                _run(loop, interval)
        else:
            _run(loop, interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        loop.shutdown()
    return 0


def _run(loop: CaptureLoop, interval: float) -> None:
    while True:
        for event in loop.tick():
            if event.kind == "press":
                print("  ● REC")
            elif event.kind == "sent":
                print(f"  sent   ({event.detail})")
            elif event.kind == "dropped":
                print(f"  dropped: {event.detail}")
            else:
                print(f"  ERROR: {event.detail}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
