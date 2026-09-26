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
from collections.abc import Callable

from audio_capture import (
    DEFAULT_MAX_CLIP_S,
    DEFAULT_MIN_CLIP_S,
    DEFAULT_MIN_PEAK,
    DEFAULT_SOX_BINARY,
    DEFAULT_TAIL_S,
    ClipGate,
    SoxRecorder,
    sox_available,
)
from capture_loop import CaptureLoop
from ptt_source import (
    DEFAULT_DCS_POLL_HZ,
    DcsPTT,
    JoystickPTT,
    KeyTogglePTT,
    PTTError,
    PTTSource,
)
from transcribe_client import TranscribeClient

DEFAULT_ADAPTER_URL = "http://127.0.0.1:7795"
#: The collector's own LAN API, on this same box when --ptt dcs is used.
DEFAULT_COLLECTOR_URL = "http://127.0.0.1:7791"
#: Default poll rate for the local PTT sources (`key`/`joystick`) -- a local
#: read with no network hop, so there is no cost tradeoff to make. `--ptt dcs`
#: gets its own, slower default (`ptt_source.DEFAULT_DCS_POLL_HZ`) because it
#: is an HTTP round trip to a collector sharing a box with DCS; see that
#: constant's docstring for why 30 Hz was chosen there. An explicit
#: `--poll-hz` from the user always overrides whichever default applies.
DEFAULT_LOCAL_POLL_HZ = 60.0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m audio_adapter.capture",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument(
        "--ptt",
        choices=("key", "joystick", "dcs"),
        default="key",
        help=(
            "talk control: a keypress (dev), a joystick button (Windows), "
            "or the aircraft's own intercom trigger (needs a running collector)"
        ),
    )
    parser.add_argument(
        "--collector-url",
        default=DEFAULT_COLLECTOR_URL,
        help="collector to read GET /ptt/state from, for --ptt dcs",
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
    parser.add_argument(
        "--sox-binary",
        default=DEFAULT_SOX_BINARY,
        help=(
            "sox executable, by name on PATH or as a full path. Needed when "
            "PATH cannot be trusted -- notably a Windows Python launched "
            "from WSL, which inherits WSL's PATH: "
            '--sox-binary "C:\\Program Files (x86)\\sox-14-4-2\\sox.exe"'
        ),
    )
    parser.add_argument("--tail-s", type=float, default=DEFAULT_TAIL_S)
    parser.add_argument("--max-clip-s", type=float, default=DEFAULT_MAX_CLIP_S)
    parser.add_argument("--min-clip-s", type=float, default=DEFAULT_MIN_CLIP_S)
    parser.add_argument("--min-peak", type=float, default=DEFAULT_MIN_PEAK)
    parser.add_argument(
        "--poll-hz",
        type=float,
        default=None,
        help=(
            "talk-control poll rate; default depends on --ptt: "
            f"{DEFAULT_DCS_POLL_HZ:g} Hz for dcs (an HTTP round trip to a collector "
            f"sharing a box with DCS), {DEFAULT_LOCAL_POLL_HZ:g} Hz for key/joystick "
            "(a local read, no network hop)"
        ),
    )
    return parser


def _resolve_poll_hz(ptt: str, poll_hz: float | None) -> float:
    """The default poll rate depends on the PTT source; an explicit
    `--poll-hz` always wins. `--ptt dcs` is an HTTP round trip to a
    collector sharing a box with DCS, so it defaults to the slower,
    deliberately-chosen `DEFAULT_DCS_POLL_HZ` rather than the local sources'
    flat default.
    """
    if poll_hz is not None:
        return poll_hz
    return DEFAULT_DCS_POLL_HZ if ptt == "dcs" else DEFAULT_LOCAL_POLL_HZ


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not sox_available(args.sox_binary):
        print(
            f"`{args.sox_binary}` not found. macOS: brew install sox. "
            "Windows: the installer from sox.sourceforge.net.",
            file=sys.stderr,
        )
        if args.sox_binary == DEFAULT_SOX_BINARY:
            print(
                "Running a Windows Python from WSL? The PATH it inherits is "
                "WSL's, which Windows cannot use. Pass the full Windows path "
                "with --sox-binary.",
                file=sys.stderr,
            )
        return 1

    recorder = SoxRecorder(
        driver=args.input_driver,
        device=args.input_device,
        max_clip_s=args.max_clip_s,
        sox_binary=args.sox_binary,
    )
    gate = ClipGate(min_duration_s=args.min_clip_s, min_peak=args.min_peak)
    client = TranscribeClient(args.adapter_url)

    key_ptt: KeyTogglePTT | None = None
    discard_if: Callable[[], bool] | None = None
    ptt: PTTSource
    if args.ptt == "dcs":
        dcs_ptt = DcsPTT(args.collector_url)
        ptt = dcs_ptt
        # Only this source can say a clip was for the radio, so only this
        # branch wires the hook.
        discard_if = dcs_ptt.discard_requested
        print(
            f"PTT: the aircraft's intercom trigger, via {args.collector_url}/ptt/state.\n"
            "  Right-press the stick trigger (the intercom stop) and hold.\n"
            "  A full press is the radio -- it will not talk to Petrovich, and\n"
            "  reaching it mid-utterance discards the clip."
        )
    elif args.ptt == "joystick":
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
        discard_if=discard_if,
    )
    poll_hz = _resolve_poll_hz(args.ptt, args.poll_hz)
    interval = 1.0 / poll_hz if poll_hz > 0 else 0.0

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


#: How long to wait before retrying after the talk control stops
#: answering. Long enough that a collector restart (or DCS reloading a
#: mission) does not produce a screenful, short enough that the trigger is
#: usable again within a breath of the feed coming back.
_PTT_RETRY_S = 1.0


def _run(loop: CaptureLoop, interval: float) -> None:
    """Poll until interrupted, surviving a talk control that stops
    answering.

    **A dead feed used to kill this process.** `CaptureLoop` raises on a
    `PTTError` deliberately -- a dead trigger must not look like silence --
    but propagating that all the way out meant a collector restart, a DCS
    crash or a mission reload left the pilot with no capture at all and a
    traceback they could not act on mid-flight. The right handling is here
    rather than in the loop: report it, drop any in-flight clip, and keep
    trying. The loop keeps its loud failure; the process keeps running.
    """
    complaining = False
    while True:
        try:
            events = loop.tick()
        except PTTError as exc:
            if not complaining:
                print(f"  talk control unreachable: {exc}", file=sys.stderr)
                print(
                    "  retrying -- capture is paused until it answers", file=sys.stderr
                )
                complaining = True
            # Whatever was being recorded cannot be finished by a release
            # that will never arrive.
            loop.shutdown()
            time.sleep(_PTT_RETRY_S)
            continue
        if complaining:
            print("  talk control back.", file=sys.stderr)
            complaining = False
        for event in events:
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
