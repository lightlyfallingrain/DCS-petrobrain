---
name: project_brain_layer_small_model_measurements
description: qwen3:4b-instruct-2507 and granite4:micro measured on this machine for the brain layer's D6 model pick; both beat the incumbent qwen2.5:7b/llama3.2:3b pair.
metadata:
  type: project
---

`plans/brain-layer/plan.md` D6 was unsettled between `qwen2.5:7b-instruct` (default) and
`llama3.2:3b` (fallback). Following `body-layer/research/2026-09-25-small-local-model-survey.md`'s
shortlist, `qwen3:4b-instruct-2507-q4_K_M` and `granite4:micro` were pulled and measured on the
same M1 Max / 32GB / Ollama machine, reusing `plans/brain-layer/plan.md`'s own
`plans/brain-layer/probe-prompt.txt` for comparability. Full writeup:
`body-layer/research/2026-09-25-small-model-measurements.md`.

**Why:** the survey was hypothesis-only (no pulls); this pass tested those hypotheses against real
latency/reliability numbers before Architect commits a new D6 default.

**How to apply:** if a future session needs to re-check or extend this comparison, reuse
`probe-prompt.txt` unmodified for anything meant to be comparable to the plan's own table — a new
prompt makes the numbers incomparable. Key results: both candidates answered the plan's own
ambiguous-reference case (`ASK`) 5/5, correctly beating both incumbents (which guessed on that case
per Measurement 3); the bare tag `qwen3:4b-instruct-2507` does **not** resolve on Ollama, only
`-q4_K_M`/`-q8_0`/`-fp16` suffixed tags do; `granite4:micro` (no `ibm/` prefix) resolves directly.
Neither model ever emitted a `<think>` trace across ~20 runs including adversarial prompts, but
both will fabricate a plausible-sounding **non-verbatim** justification when a prompt invites
deliberation or drops the tight-format instruction — this is exactly the failure class D10's
verbatim-quote validator exists to catch, confirmed (not just assumed) working against both new
candidates. `ollama ps`'s resident-memory figure is at Ollama's default 32K context window, not the
workload's actual ~150-210 prompt tokens — treat any `ollama ps` reading as an overestimate of real
production footprint unless `num_ctx` was constrained to match.
