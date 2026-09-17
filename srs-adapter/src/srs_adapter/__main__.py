"""Run the `srs-adapter` process: `POST /speak` -> TTS synthesis -> one of
two delivery targets (`plans/tts-voice-output/plan.md` Decision 8).

`--target local` (this stage's payoff, no other subproject required) plays
the synthesized WAV directly on the Mac via `afplay` (an already-present
macOS CLI, no new dependency -- the same "external binary, not a package"
rule `tts_engine.MacSayEngine` follows for `say`). This is both the fastest
way to iterate on voice/wording quality and the permanent guaranteed-
deliverable local-dev path body-layer's `--speech-audio` flag needs to be
testable without a live Windows/DCS session, per `body-layer/CLAUDE.md`'s
"testable without a live DCS session" requirement.

`--target aircraft-layer` (wired once `aircraft_client.py` exists) instead
POSTs the WAV to a running aircraft-layer collector's `POST /audio/play`,
which plays it through `winsound` on the Windows box.

Usage: python -m server [--host HOST] [--port PORT] [--target local]
       [--voice VOICE]
   or: python -m server --target aircraft-layer --aircraft-layer-url URL
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import tempfile

from server import DEFAULT_HOST, DEFAULT_PORT, AudioDeliveryError, TTSAdapterServer
from tts_engine import DEFAULT_VOICE, MacSayEngine

logger = logging.getLogger(__name__)

#: `afplay` should never hang the process indefinitely on a malformed file
#: -- generous headroom over the longest callout this project speaks.
_PLAYBACK_TIMEOUT_S = 30.0


class LocalPlaybackSink:
    """`server.AudioSink` that plays synthesized WAV bytes directly on this
    machine via `afplay` -- `--target local`'s delivery mechanism (plan
    Decision 8). `urgent` is accepted but unused here: preemption (plan
    Decision 4) is decided in the aircraft-layer's queueing sender, which
    this dev-only local path deliberately has none of -- a second `/speak`
    call while one is still playing simply plays after it via `afplay`'s
    own process serialization, not a design this path optimizes for."""

    def deliver(self, audio: bytes, urgent: bool) -> None:
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="srs-adapter-play-")
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio)
            result = subprocess.run(
                ["afplay", tmp_path],
                capture_output=True,
                timeout=_PLAYBACK_TIMEOUT_S,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise AudioDeliveryError(
                    f"'afplay' exited {result.returncode}: {stderr.strip()}"
                )
        except FileNotFoundError as exc:
            raise AudioDeliveryError(
                "'afplay' binary not found (not on macOS?)"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioDeliveryError(
                f"'afplay' timed out after {_PLAYBACK_TIMEOUT_S}s"
            ) from exc
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("could not remove temp file %s", tmp_path, exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="POST /speak listener host"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="POST /speak listener port"
    )
    parser.add_argument(
        "--target",
        choices=("local", "aircraft-layer"),
        default="local",
        help=(
            "delivery target for synthesized audio -- 'local' (default) "
            "plays via afplay on this machine, no other subproject needed; "
            "'aircraft-layer' POSTs the WAV to a running aircraft-layer "
            "collector's /audio/play (requires --aircraft-layer-url)"
        ),
    )
    parser.add_argument(
        "--aircraft-layer-url",
        default=None,
        help=(
            "aircraft-layer LAN API base URL, e.g. http://192.168.1.50:7791 "
            "-- required when --target aircraft-layer"
        ),
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help="macOS 'say' voice name (see 'say -v ?' for the installed list)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="log every request at DEBUG level",
    )
    args = parser.parse_args()

    if args.target == "aircraft-layer" and args.aircraft_layer_url is None:
        parser.error("--target aircraft-layer requires --aircraft-layer-url")

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    engine = MacSayEngine(voice=args.voice)

    if args.target == "aircraft-layer":
        from aircraft_client import AircraftLayerAudioSink

        sink: LocalPlaybackSink | AircraftLayerAudioSink = AircraftLayerAudioSink(
            base_url=args.aircraft_layer_url
        )
    else:
        sink = LocalPlaybackSink()

    server = TTSAdapterServer(engine, sink, host=args.host, port=args.port)
    server.open()
    logger.info("srs-adapter ready (target=%s)", args.target)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
