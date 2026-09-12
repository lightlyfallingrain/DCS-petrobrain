"""Test for `player_intent.main`'s `--emit-compact` flag (MI-6,
`plans/mi6-runtime-compilation/plan.md`, Implementation Plan stage 4).

`main()` itself constructs real `WorldModelClient`/`OllamaClient` instances
against live network endpoints with no injection point -- exercising it
end to end would need a live world-model server and Ollama daemon (see
`tests/test_synth_live_ollama.py`'s skip-guarded precedent for that class
of test). `write_compact` is factored out specifically so the
`--emit-compact` behavior itself -- compiling a `MissionUnderstanding` and
writing it as JSON -- is testable without either dependency; this is that
"light integration check" (plan stage 4), just built understanding-first
rather than by shelling out to `main()`.
"""

from __future__ import annotations

import json
from pathlib import Path

from player_intent.main import write_compact
from schema.tags import Tagged
from schema.understanding import SCHEMA_VERSION, MissionUnderstanding, Ownship


def _understanding() -> MissionUnderstanding:
    return MissionUnderstanding(
        schema_version=SCHEMA_VERSION,
        theatre=Tagged(
            value="Caucasus", epistemic_status="FACT", basis=("miz:mission.theatre",)
        ),
        ownship=Tagged(
            value=Ownship(aircraft="Mi-24P", flight="Hip-1", role=None),
            epistemic_status="FACT",
            basis=("miz:unit.skill",),
        ),
        route=Tagged(value=(), epistemic_status="FACT", basis=("miz:group.route",)),
    )


def test_emit_compact_writes_parseable_round_tripping_json(tmp_path: Path) -> None:
    understanding = _understanding()
    output_path = tmp_path / "compact.json"

    write_compact(understanding, output_path)

    parsed = json.loads(output_path.read_text())
    assert parsed["schema_version"] == SCHEMA_VERSION
    assert parsed["theatre"]["value"] == "Caucasus"
    assert parsed["ownship"]["value"] == "Mi-24P (Hip-1)"
    assert parsed["purpose"]["value"] is None
    assert parsed["task"]["value"] is None
    assert parsed["route"] == []
