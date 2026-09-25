"""Run the `brain-layer` process: `POST /escalate` -> a `Decider` -> `GET
/replies/poll` (`plans/brain-layer/plan.md` Stage 1).

Stage 1 wires only `StubDecider` -- `--stub-delay-s` reproduces the plan's
own worked scenario (`--stub-delay-s 8` proves the async round trip with
zero model risk). `OllamaDecider` (Stage 2) is not wired here yet.

Usage: python -m brain_layer [--host HOST] [--port PORT]
           [--stub-delay-s SECONDS]
"""

from __future__ import annotations

import argparse
import logging

from decider import StubDecider
from server import DEFAULT_HOST, DEFAULT_PORT, BrainLayerServer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST, help="listener host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="listener port")
    parser.add_argument(
        "--stub-delay-s",
        type=float,
        default=0.0,
        help=(
            "artificial delay (seconds) StubDecider.decide sleeps before "
            "answering -- 0 (default) for immediate replies, 8 to "
            "reproduce plans/brain-layer/plan.md Stage 1's own worked "
            "scenario (stand-by fires once at 2s, tick rate unaffected)."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="log every request at DEBUG level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    decider = StubDecider(delay_s=args.stub_delay_s)
    server = BrainLayerServer(decider, host=args.host, port=args.port)
    server.open()
    logger.info(
        "brain-layer ready (decider=StubDecider, delay_s=%.1f)",
        args.stub_delay_s,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
