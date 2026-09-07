---
name: body-layer-api-decisions
description: Draft body-layer plan's load-bearing decisions — fixed tool set for the brain, pre-digested responses, async commands, single process.
metadata:
  type: project
---

`plans/body-layer/plan.md` (drafted 2026-09-07, non-final) fixes four decisions that later brain-layer work inherits:

1. Brain gets a **fixed enumerable tool set**, no open-ended query language. Alternative (JSON filter DSL) rejected — small models compose poorly and open queries let invented premises through.
2. Every fact response ships `facts` + `summary` (English-ready, hedging already correct for confidence) + `phrasing_hints`. Heavy pre-digestion; `facts` is the escape hatch.
3. Aircraft commands are **async with a task lifecycle**, but completions surface through the same event stream the brain already polls — the brain never tracks task state.
4. **Single body process**, sharding deferred; the natural future shard is per-agent (wingman/JTAC), not per-concern. Replay determinism (BL-0) is what forbids sharding cheaply.

5. **Speech is SRS on Petrovich's ICS channel** (added 2026-09-07). An SRS adapter — proposed as a sibling of the aircraft layer, placement not settled — owns audio, PTT debounce, silence gating, STT and TTS; body deals in text only. Body runs a deterministic intent parser and routing gate: matched utterances get a direct action plus a templated readback with no brain call; unmatched/ambiguous ones escalate via `handle_player_utterance`, which carries the *partial parse*, never raw transcript. Urgent reactive calls ("missile launch, break right") are body-templated, bypass cooldown/relevance gating, and never reach the brain at all.

Milestones are BL-0..BL-5a..BL-10, explicitly reconciled against `PETROBRAIN_RUNTIME.md`'s PB-x (PB-6/7/8 = LLM/TTS/STT have no BL equivalent, they're brain-layer).

**Why:** these are the seams between deterministic code and the LLM — the hardest things to change later, and the mechanical enforcement of "code owns truth, models own interpretation."

**How to apply:** when planning brain-layer or body-layer work, start from these rather than re-deriving. Items 1 and 2 were flagged to the user as decisions needing explicit sign-off — check whether they were accepted before treating them as settled. Related: [[project_aircraft_layer_architecture]].
