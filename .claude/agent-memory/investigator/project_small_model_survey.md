---
name: project_small_model_survey
description: Small local LLM landscape (as of 2026-09) for brain-layer model choice, and how to tell architecturally-non-thinking models from default-off-toggle ones
metadata:
  type: project
---

Full findings: `body-layer/research/2026-09-25-small-local-model-survey.md`.

- **qwen2.5:7b-instruct (Sept 2024) is the current brain-layer default (plan D6); it is not stale
  in a way the survey found a clearly-better replacement for yet** — but `qwen3:4b-instruct-2507`
  (July 2025, Alibaba) is the strongest untested lead: it is **architecturally non-thinking** (no
  `<think>` capability exists in the weights at all, confirmed on its own HF model card), unlike
  plain `qwen3` whose thinking could not be reliably suppressed via `/no_think` (the project's own
  Measurement 1: `qwen3:4b` 32.7s vs `qwen3:14b` 16.0s — smaller model *slower* because the trace is
  the entire cost).
- **Two distinct categories of "thinking control" exist in 2025-2026 small models — treat them with
  different suspicion levels:**
  1. Architecturally non-thinking (Qwen3-4B-Instruct-2507, Gemma 3, Phi-4-mini base) — nothing to
     suppress, no flag to fail. Prefer these.
  2. Default-off, still-toggleable (Qwen3.5 small series, March 2026 — reasoning off by default per
     its own HF model-card discussion, but a flag re-enables it) — same class of switch that already
     failed on plain Qwen3. Don't trust "default off" language without measuring under adversarial
     prompts.
- **IBM Granite 4.0** (Oct 2025; `granite-4.0-micro`/`-h-micro`, ~3B, Apache-2.0) explicitly targets
  tool-calling/structured-JSON reliability as a stated design goal, not an incidental benchmark —
  worth prioritizing in any structured-output-reliability shootout. Its own reasoning-mode status
  (none vs. off-by-default) wasn't confirmed from primary source this pass — check the model card
  directly before relying on it.
- **Gemma 3** (March 2025) and **Phi-4-mini base** (Feb 2025) have no reasoning-toggle question at
  all as a family — good hedge candidates precisely because there's no switch to get wrong.
- **Mistral Small 3.x is 24B — not a "small model" for this project's purposes** despite the
  familiar name; don't reach for it reflexively. Ministral 3 (3B/8B/14B, Dec 2025) is a real but
  unverified-in-this-pass candidate — exact Ollama tags and reasoning-mode status unconfirmed.
- **Llama has had no small (<=8B) release since llama3.2 (Sept 2024)** — Llama 4 went straight to
  MoE with double-digit-billion active params; not a small-model lead going forward.
- Useful search pattern for this kind of survey: query per-family ("<family> ollama release date
  <year>") plus a targeted follow-up on the exact HF model-card discussion thread title (e.g.
  "Enabling or disabling reasoning (default is disabled)") — those discussion threads on the base
  model repo are more reliable primary-source evidence for thinking-mode defaults than blog
  aggregator summaries.
