"""MI-4's capable-model synthesis stage --
`plans/mi4-capable-model-synthesis/plan.md`. Fills in
`MissionUnderstanding.purpose`/`task`/`known_threats` (left `None`/`()` by
MI-3) using Ollama's `qwen3:14b` (non-thinking) over briefing text + an
`EnrichedMission`'s already-established facts + a sanitized threat-signal
summary (`filter.threat_signals`/`world_enrich.enrich.enrich_threat_signals`).

`ollama_client.py` -- stdlib-`urllib.request`-only HTTP client for a local
Ollama daemon's `/api/chat` endpoint, mirroring `world_enrich.
world_model_client`'s shape.
`prompts.py` -- builds the request messages and the structured-output JSON
schema.
`synthesize.py` -- `synthesize_mission_understanding`, the entry point that
calls the client and parses its response into `Tagged[...]` values.
"""

from __future__ import annotations
