---
name: project_brain_layer_pb6_planning
description: Brain-layer prototype plan (2026-09-12) — new subproject, PB-6 scope, bidirectional HTTP design, grounding-check invariant, open decisions.
metadata:
  type: project
---

Plan written 2026-09-12: `plans/brain-layer/plan.md`, new subproject `brain-layer/` (not yet
implemented — plan only). Scope is exactly `docs/concept/PETROBRAIN_RUNTIME.md`'s **PB-6 — Small
LLM interface** slot ("add natural-language reference resolution and response generation"),
confirmed unclaimed by grepping the doc's own PB-x list — PB-1..PB-5 map 1:1 to BL-1..BL-5 (all
done), PB-7/PB-8 are TTS/STT, PB-9 is mission-aware proactive behavior. Scoped to the **reactive
escalated-utterance path only** (the seam BL-5a already built: `belief/escalation.py`'s
`BrainClient` Protocol/`EscalationPayload`, `belief/crew_console.py`'s `_handle_utterance`) —
explicitly not proactive speech (PB-9), not SRS/TTS/STT (PB-7/PB-8), not multi-turn
`ask_player` round trips (protocol has `awaiting_reply_id()` but no stand-in ever returns
non-None; this plan leaves it unimplemented too).

**Key existing-code findings that drove the design** (read before touching any of these files):
- `BrainClient.handle()` currently returns `None` — no stand-in produces speech. A real brain
  needs a return value; plan widens it to `str | None` (reply text or "no answer/timeout"). This
  is a protocol edit to already-shipped BL-5a code, not new code in a vacuum — flagged as a risk
  (existing tests need updating too).
- `belief/tools.py`'s `TOOL_SET` functions take server-side context (`store`, `enrichment`,
  `tasks`, `now_sim`) as **leading params**, ahead of brain-facing args. A brain-facing HTTP
  wrapper must bind context server-side and never accept it from the client — letting a client
  supply its own `now_sim` would let it manufacture staleness. No existing metadata on `ToolSpec`
  distinguishes context-vs-brain-facing params; plan says hand-write ~12-15 small route handlers
  rather than build a reflection dispatcher for a first prototype (no duplication to remove yet).
- body-layer has never run an HTTP *server* before (only ever a client, of aircraft-layer).
  `aircraft-layer/src/api/server.py`'s `TelemetryAPIServer` (stdlib `ThreadingHTTPServer`, no
  framework) is the one precedent for "a Petrobrain subproject serving HTTP" — body-layer's new
  tool-server follows the same stdlib-only shape.
- `speech.py`'s `OutgoingSpeech.author` is a closed `Literal["body_template"]` specifically
  because "the brain-written class... not built by this milestone" — that milestone is this one;
  plan widens the literal.

**Design/invariant worth reusing**: no-omniscience enforcement is concrete, not restated
principle — a **grounding check** in brain-layer's `reasoning.py` extracts every contact-id-shaped
token from the model's candidate reply and diffs it against ids actually returned by a tool call
*that turn*; any reply referencing an ungrounded id is treated the same as a timeout (silence, per
`escalation.py`'s own existing "silence is honest; a guessed response is not" language) — chosen
fail-closed deliberately, flagged to the user as a decision anyway since it trades reply-frequency
for safety.

**Four decisions surfaced to the user, not resolved silently**: (1) synchronous blocking HTTP
round trip (chosen, for prototype simplicity) vs. async reply-delivery via a third inbound
body-layer endpoint (better matches `awaiting_reply_id()`'s implied future, not built now) — this
is called out as the one choice with a real second-order effect: it sets the latency ceiling
PB-7/PB-8 (TTS/STT) inherit; (2) model hosting — local Ollama (stdlib-only, matches project's
local-first posture, unverified tool-calling quality) vs. cloud API for this prototype only
(new-dependency-class, `AGENTS.md` escalation rule); (3) grounding-check strictness (chosen
fail-closed/silence, flagged anyway); (4) whether the brain reply becomes a real
`OutgoingSpeech(author="brain")` object or a plain string (marked reversible/local, not escalated
per AGENTS.md's own carve-out — Implementer's call).

**Recommended re-invoking this role with an opus override** before implementation — this plan
stacks four separately-risky axes at once (new subproject/dependency choice, bidirectional HTTP
protocol design, LLM hallucination boundary, editing an already-shipped protocol's method
signature) and was produced at sonnet depth per the task's own instruction, not silently.

See [[project_bl6_command_channel_design]] for the sibling pattern (split an uncertain premise
into a small buildable core + a gated later stage) — not directly reused here since PB-6 has no
DCS-internals unknown, but the same "don't block the whole milestone on the hardest unresolved
piece" instinct shaped the PB-6a/b/c staging.
