"""Run the collector standalone and dump the latest sample to stdout.

This is the debug-dump path plan stage 2 calls for: before the Mac-facing
API exists (stage 4), the way to verify the Export.lua -> collector hop
works end-to-end is to run this on the Windows box and watch it print
telemetry while a Mi-24P mission is running (plan stage 3, live DCS test --
not exercised by this session's work).

Usage: python -m collector [--host HOST] [--port PORT] [--interval SECONDS] [--debug]
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

from collector.cache import DEFAULT_BUFFER_SIZE, TelemetryCache
from collector.server import DEFAULT_HOST, DEFAULT_PORT, CollectorServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--interval",
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
    server = CollectorServer(cache, host=args.host, port=args.port)
    server.open()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        while True:
            time.sleep(args.interval)
            sample = cache.latest()
            print(sample if sample is not None else "(no sample received yet)")
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
