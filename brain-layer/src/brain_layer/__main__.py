"""Run the `brain-layer` process: `POST /escalate` -> a `Decider` -> `GET
/replies/poll` (`plans/brain-layer/plan.md` Stage 1/2).

`--decider stub` (**still the default**, preserving `run-scripts/
run-brain.sh`'s existing meaning unchanged -- switching the default
silently out from under an existing run-script is exactly the kind of
surprise this project's own "verify state, not the account of it" rule
warns about) wires `StubDecider`, `--stub-delay-s` reproducing the
plan's own worked scenario. `--decider ollama` wires `OllamaDecider`
(Stage 2, D6): a real local model behind `--brain-model` (default
`qwen3:4b-instruct-2507-q4_K_M`), with one throwaway warm-up generation
at startup (D8's mitigation) so the first real escalation never pays the
cold-load latency.

Usage: python -m brain_layer [--host HOST] [--port PORT]
           [--decider stub|ollama] [--stub-delay-s SECONDS]
           [--brain-model MODEL] [--ollama-url URL]
           [--decide-timeout-s SECONDS]
"""

from __future__ import annotations

import argparse
import logging

from decider import Decider, OllamaDecider, StubDecider
from ollama_client import OllamaClient, OllamaRequestError
from server import (
    DEFAULT_DECIDE_TIMEOUT_S,
    DEFAULT_HOST,
    DEFAULT_PORT,
    BrainLayerServer,
)

logger = logging.getLogger(__name__)

#: D6's default -- confirmed present in local ollama as of 2026-09-25.
#: Never compiled into any decision logic, only this flag's own default
#: (D6: "no model name is compiled into any logic").
DEFAULT_BRAIN_MODEL = "qwen3:4b-instruct-2507-q4_K_M"


def _build_decider(args: argparse.Namespace) -> Decider:
    if args.decider == "stub":
        return StubDecider(delay_s=args.stub_delay_s)
    ollama_client = OllamaClient(base_url=args.ollama_url)
    decider = OllamaDecider(model=args.brain_model, ollama_client=ollama_client)
    try:
        ollama_client.warm_up(model=args.brain_model, num_ctx=decider.num_ctx)
        logger.info("Ollama warm-up generation complete (model=%s)", args.brain_model)
    except OllamaRequestError:
        # D8: warm-up is a mitigation, not a precondition -- Ollama may
        # simply not be up yet. The first real escalation pays whatever
        # this call would have saved; it does not fail startup.
        logger.warning(
            "Ollama warm-up failed (model=%s, url=%s) -- continuing without it",
            args.brain_model,
            args.ollama_url,
            exc_info=True,
        )
    return decider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST, help="listener host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="listener port")
    parser.add_argument(
        "--decider",
        choices=("stub", "ollama"),
        default="stub",
        help="which Decider to run behind POST /escalate (default: stub)",
    )
    parser.add_argument(
        "--stub-delay-s",
        type=float,
        default=0.0,
        help=(
            "artificial delay (seconds) StubDecider.decide sleeps before "
            "answering -- only meaningful with --decider stub."
        ),
    )
    parser.add_argument(
        "--brain-model",
        default=DEFAULT_BRAIN_MODEL,
        help=f"Ollama model tag for OllamaDecider (default: {DEFAULT_BRAIN_MODEL})",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="base URL of the Ollama daemon (default: Ollama's own default)",
    )
    parser.add_argument(
        "--decide-timeout-s",
        type=float,
        default=DEFAULT_DECIDE_TIMEOUT_S,
        help="bound on one Decider.decide() call (see server.py's own docstring)",
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

    decider = _build_decider(args)
    server = BrainLayerServer(
        decider,
        host=args.host,
        port=args.port,
        decide_timeout_s=args.decide_timeout_s,
    )
    server.open()
    logger.info(
        "brain-layer ready (decider=%s)",
        type(decider).__name__,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
