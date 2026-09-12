"""MI-5 entry point (`plans/mi5-player-questions/plan.md`, Implementation
Plan stage 4): wires MI-1 through MI-5 into one script -- parse a `.miz`,
filter author-only knowledge, enrich against world-model, build the
mechanical `MissionUnderstanding`, synthesize purpose/task/known_threats
against a local Ollama daemon, run the player-question console over real
stdin/stdout, and print the final `MissionUnderstanding` as JSON.

No committed MI-3->MI-4->MI-5 CLI chain existed before this stage
(`mission-interpreter/ROADMAP.md`), so this follows the exact same
construction sequence `tests/test_synth_live_ollama.py` already uses end
to end, rather than inventing a second loading convention -- a script,
not a new subcommand framework, per the plan's own framing.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from filter.crew_available import filter_crew_available
from filter.threat_signals import derive_threat_signals
from miz.reader import read_miz
from player_intent.console import PlayerIntentConsole
from schema.build import build_mission_understanding
from synth.ollama_client import OllamaClient
from synth.synthesize import synthesize_mission_understanding
from world_enrich.enrich import enrich_mission, enrich_threat_signals
from world_enrich.world_model_client import WorldModelClient

_DEFAULT_WORLD_MODEL_URL = "http://127.0.0.1:7792"
_DEFAULT_OLLAMA_MODEL = "qwen3:14b"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    raw = read_miz(args.miz_path)
    crew_available = filter_crew_available(raw)

    world_client = WorldModelClient(base_url=args.world_model_url, theatre=args.theatre)
    enriched = enrich_mission(crew_available, world_client)
    understanding = build_mission_understanding(enriched)

    threat_signals = derive_threat_signals(raw)
    enriched_threats = enrich_threat_signals(threat_signals, world_client)

    ollama_client = OllamaClient(model=args.ollama_model)
    understanding = synthesize_mission_understanding(
        understanding, raw.briefing, enriched_threats, ollama_client
    )

    console = PlayerIntentConsole(input_=sys.stdin, output=sys.stdout)
    understanding = console.run(understanding)

    json.dump(dataclasses.asdict(understanding), sys.stdout, indent=2)
    sys.stdout.write("\n")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MI-1 through MI-5 over a .miz file and print the "
        "resulting MissionUnderstanding as JSON."
    )
    parser.add_argument("miz_path", help="Path to the .miz mission file")
    parser.add_argument(
        "--theatre",
        required=True,
        help="Theatre name matching the running world-model instance",
    )
    parser.add_argument(
        "--world-model-url",
        default=_DEFAULT_WORLD_MODEL_URL,
        help=f"world-model API base URL (default: {_DEFAULT_WORLD_MODEL_URL})",
    )
    parser.add_argument(
        "--ollama-model",
        default=_DEFAULT_OLLAMA_MODEL,
        help=f"Ollama model name (default: {_DEFAULT_OLLAMA_MODEL})",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
