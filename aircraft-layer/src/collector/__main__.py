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

Usage: python -m collector [--host HOST] [--port PORT] [--api-host HOST]
       [--api-port PORT] [--text-overlay-host HOST] [--text-overlay-port PORT]
       [--command-host HOST] [--command-port PORT]
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
from collector.cache import (
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.command_sender import DEFAULT_HOST as COMMAND_DEFAULT_HOST
from collector.command_sender import DEFAULT_PORT as COMMAND_DEFAULT_PORT
from collector.command_sender import CommandSender
from collector.server import DEFAULT_HOST, DEFAULT_PORT, CollectorServer
from collector.text_sender import DEFAULT_HOST as TEXT_OVERLAY_DEFAULT_HOST
from collector.text_sender import DEFAULT_PORT as TEXT_OVERLAY_DEFAULT_PORT
from collector.text_sender import TextOverlaySender


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

    collector = CollectorServer(
        cache,
        world_objects_cache,
        petrovich_indication_cache,
        petrovich_wheel_cache,
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


if __name__ == "__main__":
    main()
