---
name: mi4-reviewed-minor-fixes
description: MI-4 capable-model synthesis review outcome and the two required fixes found.
metadata:
  type: project
---

Reviewed MI-4 (`feature/mi4-capable-model-synthesis`) 2026-09-12 — APPROVED WITH MINOR FIXES. Full
findings: `plans/mi4-capable-model-synthesis/review.md`.

Coordinate-leak boundary (`filter/threat_signals.py` → `enrich_threat_signals` → `synth/prompts.py`),
structural FACT-exclusion via JSON schema + defense-in-depth re-validation, and the two distinct
Ollama exceptions were all confirmed solid by tracing the actual data flow and reading the tests that
claim to guard them — not just trusting the docstrings/report. `test_prompt_never_contains_a_raw_coordinate`
is a genuine mechanism test (builds a `WorldRef` with a greppable coordinate alongside a real place
name, asserts the coordinate is absent from constructed prompt text).

Two required fixes sent back to Implementer:
1. `OllamaClient.chat_json` has no fail-closed guard before Ollama silently auto-pulls an absent model
   (~9.3GB) as a side effect of a routine call — needs a preflight `/api/tags` check + explicit error,
   not just a docstring caveat. See [[feedback_full_build_execution]] (same project posture: never run
   real external-resource operations silently) — this is the second occurrence of that class of risk.
2. `implementation.md` (and the implementer's own agent-memory file) quoted the plan as "explicitly"
   forbidding pulling the model, in text that does not exist anywhere in the plan — the plan actually
   says stage 6 is blocked "until the user *or Implementer* runs `ollama pull qwen3:14b`." A decision
   log misquoting the plan it answers to is a real accuracy defect even when the underlying behavior
   was reasonable — check quoted plan text against the actual plan file, don't take an Implementer's
   paraphrase of "the plan said X" at face value when X is in quotes.
