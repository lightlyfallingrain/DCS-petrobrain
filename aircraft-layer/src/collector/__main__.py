"""Run the collector process: Export.lua listener + Mac-facing LAN API.

Both `CollectorServer` (loopback push from Export.lua) and `TelemetryAPIServer`
(LAN-reachable poll API, plan stage 4) run in this one process, sharing a
single `TelemetryCache` instance. Before stage 4, this only dumped the latest
sample to stdout for manual verification (plan stage 2); that dump is kept
(`--dump-interval`) since it's still useful for watching the pipeline without
a separate HTTP client.

A `TextOverlaySender` (`plans/dcs-text-panel-output/plan.md`, BL-2.5) is also
constructed here and handed to `TelemetryAPIServer` so `POST /text/push` can
forward lines to the in-cockpit overlay Hook script over loopback UDP -- the
one inbound/write path on this otherwise read-only pipeline. A
`CommandSender` (BL-6, `plans/bl6-commands-inspect-adapt/plan.md`) is
constructed the same way for `POST /command/petrovich_search`, this
pipeline's second inbound/write path.

An `F10CommandReceiver` (`plans/f10-crew-commands/plan.md`) is also opened
here and run on its own background thread, feeding an `F10CommandQueue`
that `GET /f10_commands/poll` drains -- the first channel running the
opposite direction (Hook script -> collector, not collector -> Hook/
Export.lua) alongside the two write paths above.

An `AudioPlaybackSender` (BL-10 first slice, `plans/tts-voice-output/
plan.md`) is constructed the same way as `text_sender`/`command_sender`
for `POST /audio/play`, this pipeline's third inbound/write path -- unlike
those two, it has no host/port (it plays audio directly on this box via
`winsound`, no loopback UDP peer involved).

A `UnitVelocityReceiver` (`plans/movement-detection/plan.md` Stage 1) is
opened and run on its own background thread the same way, feeding a
`UnitVelocityCache` that `GET /unit_velocity/latest` reads -- the second
channel running the Hook-to-collector direction (after the F10 one above).

Usage: python -m collector [--host HOST] [--port PORT] [--api-host HOST]
       [--api-port PORT] [--text-overlay-host HOST] [--text-overlay-port PORT]
       [--command-host HOST] [--command-port PORT]
       [--f10-host HOST] [--f10-port PORT]
       [--unit-velocity-host HOST] [--unit-velocity-port PORT]
       [--dump-interval SECONDS] [--debug]
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

from api.server import DEFAULT_HOST as API_DEFAULT_HOST
from api.server import DEFAULT_PORT as API_DEFAULT_PORT
from api.server import TelemetryAPIServer
from collector.audio_sender import AudioPlaybackSender
from collector.cache import (
    F10CommandQueue,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    PttCache,
    TelemetryCache,
    UnitVelocityCache,
    WorldObjectsCache,
)
from collector.command_sender import DEFAULT_HOST as COMMAND_DEFAULT_HOST
from collector.command_sender import DEFAULT_PORT as COMMAND_DEFAULT_PORT
from collector.command_sender import CommandSender
from collector.f10_command_receiver import DEFAULT_HOST as F10_DEFAULT_HOST
from collector.f10_command_receiver import DEFAULT_PORT as F10_DEFAULT_PORT
from collector.f10_command_receiver import F10CommandReceiver
from collector.server import DEFAULT_HOST, DEFAULT_PORT, CollectorServer
from collector.text_sender import DEFAULT_HOST as TEXT_OVERLAY_DEFAULT_HOST
from collector.text_sender import DEFAULT_PORT as TEXT_OVERLAY_DEFAULT_PORT
from collector.text_sender import TextOverlaySender
from collector.unit_velocity_receiver import DEFAULT_HOST as UNIT_VELOCITY_DEFAULT_HOST
from collector.unit_velocity_receiver import DEFAULT_PORT as UNIT_VELOCITY_DEFAULT_PORT
from collector.unit_velocity_receiver import UnitVelocityReceiver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="Export.lua listener host (loopback)"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Export.lua listener port"
    )
    parser.add_argument(
        "--api-host", default=API_DEFAULT_HOST, help="Mac-facing LAN API host"
    )
    parser.add_argument(
        "--api-port", type=int, default=API_DEFAULT_PORT, help="Mac-facing LAN API port"
    )
    parser.add_argument(
        "--text-overlay-host",
        default=TEXT_OVERLAY_DEFAULT_HOST,
        help="in-cockpit overlay Hook script listener host (loopback)",
    )
    parser.add_argument(
        "--text-overlay-port",
        type=int,
        default=TEXT_OVERLAY_DEFAULT_PORT,
        help="in-cockpit overlay Hook script listener port",
    )
    parser.add_argument(
        "--command-host",
        default=COMMAND_DEFAULT_HOST,
        help="Export.lua's inbound command listener host (loopback)",
    )
    parser.add_argument(
        "--command-port",
        type=int,
        default=COMMAND_DEFAULT_PORT,
        help="Export.lua's inbound command listener port",
    )
    parser.add_argument(
        "--f10-host",
        default=F10_DEFAULT_HOST,
        help="F10 radio-menu Hook script's UDP sender host (loopback)",
    )
    parser.add_argument(
        "--f10-port",
        type=int,
        default=F10_DEFAULT_PORT,
        help="F10 radio-menu Hook script's UDP sender port",
    )
    parser.add_argument(
        "--unit-velocity-host",
        default=UNIT_VELOCITY_DEFAULT_HOST,
        help="mission-telemetry Hook script's UDP sender host (loopback)",
    )
    parser.add_argument(
        "--unit-velocity-port",
        type=int,
        default=UNIT_VELOCITY_DEFAULT_PORT,
        help="mission-telemetry Hook script's UDP sender port",
    )
    parser.add_argument(
        "--dump-interval",
        type=float,
        default=1.0,
        help="seconds between stdout dumps of the latest sample",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="log every received line and parse result (DEBUG level)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    cache = TelemetryCache()
    world_objects_cache = WorldObjectsCache()
    petrovich_indication_cache = PetrovichIndicationCache()
    petrovich_wheel_cache = PetrovichWheelCache()
    text_sender = TextOverlaySender(
        host=args.text_overlay_host, port=args.text_overlay_port
    )
    text_sender.open()
    command_sender = CommandSender(host=args.command_host, port=args.command_port)
    command_sender.open()
    f10_command_queue = F10CommandQueue()
    f10_command_receiver = F10CommandReceiver(
        f10_command_queue, host=args.f10_host, port=args.f10_port
    )
    f10_command_receiver.open()
    f10_command_receiver_thread = threading.Thread(
        target=f10_command_receiver.serve_forever, daemon=True
    )
    f10_command_receiver_thread.start()
    audio_sender = AudioPlaybackSender()
    audio_sender.open()
    unit_velocity_cache = UnitVelocityCache()
    unit_velocity_receiver = UnitVelocityReceiver(
        unit_velocity_cache, host=args.unit_velocity_host, port=args.unit_velocity_port
    )
    unit_velocity_receiver.open()
    unit_velocity_receiver_thread = threading.Thread(
        target=unit_velocity_receiver.serve_forever, daemon=True
    )
    unit_velocity_receiver_thread.start()

    # One cache, handed to both halves: the collector fills it from
    # Export.lua's ptt lines and the API serves it to the capture process.
    ptt_cache = PttCache()

    collector = CollectorServer(
        cache,
        world_objects_cache,
        petrovich_indication_cache,
        petrovich_wheel_cache,
        ptt_cache=ptt_cache,
        host=args.host,
        port=args.port,
    )
    collector.open()
    collector_thread = threading.Thread(target=collector.serve_forever, daemon=True)
    collector_thread.start()

    api = TelemetryAPIServer(
        cache,
        world_objects_cache,
        host=args.api_host,
        port=args.api_port,
        petrovich_indication_cache=petrovich_indication_cache,
        text_sender=text_sender,
        petrovich_wheel_cache=petrovich_wheel_cache,
        command_sender=command_sender,
        f10_command_queue=f10_command_queue,
        audio_sender=audio_sender,
        unit_velocity_cache=unit_velocity_cache,
        ptt_cache=ptt_cache,
    )
    api.open()
    api_thread = threading.Thread(target=api.serve_forever, daemon=True)
    api_thread.start()

    try:
        while True:
            time.sleep(args.dump_interval)
            sample = cache.latest()
            logger.debug(sample if sample is not None else "(no sample received yet)")
    except KeyboardInterrupt:
        pass
    finally:
        api.close()
        collector.close()
        text_sender.close()
        command_sender.close()
        f10_command_receiver.close()
        audio_sender.close()
        unit_velocity_receiver.close()


if __name__ == "__main__":
    main()
