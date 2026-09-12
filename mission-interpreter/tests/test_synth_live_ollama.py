"""Real integration test: runs `synthesize_mission_understanding` against
the real sample mission end-to-end, using an actual local Ollama daemon.

Skip-guarded by a quick reachability probe -- mirrors this codebase's
`REAL_SAMPLE_MIZ_PATH.exists()` skip convention (`conftest.py`), adapted to
"can we reach Ollama, and is `qwen3:14b` present" instead of "does this
file exist". As of this implementation session, `qwen3:14b` is **not**
pulled locally (`ollama list` confirmed only `qwen3.6:27b`/`qwen3.5:9b`/
`gemma4:12b`/`gemma4:e4b`) and this session had no outbound network access
to run `ollama pull qwen3:14b` itself (per the plan's Prerequisite check
and this project's "never run real external-resource operations silently"
posture) -- so this test is expected to skip until a human runs that pull.

This test only asserts the call completes and produces a plausible
non-empty result -- output *quality* judgment (does the inferred purpose
actually match the real briefing) is a human pass, not something this test
asserts (plan stage 6).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from conftest import REAL_SAMPLE_MIZ_PATH

from filter.crew_available import filter_crew_available
from filter.threat_signals import derive_threat_signals
from miz.reader import read_miz
from schema.build import build_mission_understanding
from synth.ollama_client import OllamaClient
from synth.synthesize import synthesize_mission_understanding
from world_enrich.enrich import enrich_mission, enrich_threat_signals

_MODEL = "qwen3:14b"
_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


class _FakeWorldModelClient:
    """No real world-model instance is required for this test -- it's
    exercising the Ollama seam, not the world-model seam. Same canned-data
    double as `test_enrich.py`/`test_schema_understanding.py`."""

    def get_describe_position(self, x: float, z: float) -> dict[str, Any]:
        return {"x": x, "z": z, "nearest_settlement": None}

    def get_find_place_by_name(
        self, text: str, kinds: list[str] | None = None
    ) -> list[dict[str, Any]]:
        return [{"name": text, "kind": "settlement", "x": 0.0, "z": 0.0}]


def _ollama_has_model(model: str) -> bool:
    try:
        with urllib.request.urlopen(
            f"{_OLLAMA_BASE_URL}/api/tags", timeout=2.0
        ) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False
    models = body.get("models", []) if isinstance(body, dict) else []
    return any(
        isinstance(entry, dict) and entry.get("name") == model for entry in models
    )


@pytest.mark.skipif(
    not REAL_SAMPLE_MIZ_PATH.exists(),
    reason="real sample mission not present locally (gitignored, see conftest.py)",
)
@pytest.mark.skipif(
    not _ollama_has_model(_MODEL),
    reason=f"Ollama unreachable or {_MODEL!r} not pulled locally "
    f"(run `ollama pull {_MODEL}` to enable this test)",
)
def test_synthesize_against_real_sample_mission_and_live_model() -> None:
    raw = read_miz(REAL_SAMPLE_MIZ_PATH)
    crew_available = filter_crew_available(raw)
    world_client = _FakeWorldModelClient()
    enriched = enrich_mission(crew_available, world_client)
    understanding = build_mission_understanding(enriched)

    threat_signals = derive_threat_signals(raw)
    enriched_threats = enrich_threat_signals(threat_signals, world_client)

    ollama_client = OllamaClient(model=_MODEL)

    result = synthesize_mission_understanding(
        understanding, raw.briefing, enriched_threats, ollama_client
    )

    assert result.purpose is not None
    assert result.purpose.value.strip() != ""
    assert result.purpose.epistemic_status in ("INFERENCE", "ASSUMPTION")
    assert result.task is not None
    assert result.task.value.strip() != ""
