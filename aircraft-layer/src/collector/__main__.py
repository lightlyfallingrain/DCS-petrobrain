"""Run the collector process: Export.lua listener + Mac-facing LAN API.

Both `CollectorServer` (loopback push from Export.lua) and `TelemetryAPIServer`
(LAN-reachable poll API, plan stage 4) run in this one process, sharing a
single `TelemetryCache` instance. Before stage 4, this only dumped the latest
sample to stdout for manual verification (plan stage 2); that dump is kept
(`--dump-interval`) since it's still useful for watching the pipeline without
a separate HTTP client.

Usage: python -m collector [--host HOST] [--port PORT] [--api-host HOST]
       [--api-port PORT] [--dump-interval SECONDS] [--debug]
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

from api.server import DEFAULT_HOST as API_DEFAULT_HOST
from api.server import DEFAULT_PORT as API_DEFAULT_PORT
from api.server import TelemetryAPIServer
from collector.cache import DEFAULT_BUFFER_SIZE, TelemetryCache
from collector.server import DEFAULT_HOST, DEFAULT_PORT, CollectorServer


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

    cache = TelemetryCache(buffer_size=DEFAULT_BUFFER_SIZE)

    collector = CollectorServer(cache, host=args.host, port=args.port)
    collector.open()
    collector_thread = threading.Thread(target=collector.serve_forever, daemon=True)
    collector_thread.start()

    api = TelemetryAPIServer(cache, host=args.api_host, port=args.api_port)
    api.open()
    api_thread = threading.Thread(target=api.serve_forever, daemon=True)
    api_thread.start()

    try:
        while True:
            time.sleep(args.dump_interval)
            sample = cache.latest()
            print(sample if sample is not None else "(no sample received yet)")
    except KeyboardInterrupt:
        pass
    finally:
        api.close()
        collector.close()


if __name__ == "__main__":
    main()
