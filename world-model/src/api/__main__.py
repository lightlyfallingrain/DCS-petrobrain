"""Process entrypoint for `WorldModelAPIServer` -- `python -m api --db
<theatre>.sqlite --theatre <name>`.

`--theatre` is a required, hand-typed flag rather than something read back
from the store: the store itself does not self-report which theatre it was
built for as a queryable string the same way `--theatre` needs to match for
`describe_position`'s coordinate transform, so this stays explicit (see the
plan's Risks & Unknowns note on this same risk already existing in
`describe_position`'s own signature).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

from api.server import DEFAULT_HOST, DEFAULT_PORT, WorldModelAPIServer


def main() -> None:
    parser = argparse.ArgumentParser(description="World-model read-only HTTP API")
    parser.add_argument(
        "--db", required=True, type=Path, help="path to the theatre's .sqlite store"
    )
    parser.add_argument(
        "--theatre",
        required=True,
        help="theatre name this store was built for (e.g. 'Syria')",
    )
    parser.add_argument(
        "--probe-db", type=Path, default=None, help="optional probe-store .sqlite path"
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # `check_same_thread=False`: see `api.server`'s module docstring --
    # `WorldModelAPIServer` uses a single-threaded `HTTPServer`, but a
    # caller may still run `serve_forever()` on a thread other than the
    # one that opened this connection (as `world-model/tests/test_api.py`
    # does).
    conn = sqlite3.connect(args.db, check_same_thread=False)
    server = WorldModelAPIServer(
        conn,
        args.theatre,
        host=args.host,
        port=args.port,
        probe_db_path=args.probe_db,
    )
    server.open()
    try:
        server.serve_forever()
    finally:
        server.close()
        conn.close()


if __name__ == "__main__":
    main()
