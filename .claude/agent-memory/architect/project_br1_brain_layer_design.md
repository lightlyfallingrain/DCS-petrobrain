---
name: br1-brain-layer-design
description: BR-1 brain-layer design — measured finding that reasoning tokens, not model size, set local-LLM latency; the code-owns-ambiguity + quote-your-evidence validator; separate subproject over HTTP
metadata:
  type: project
---

BR-1 (`plans/brain-layer/plan.md`, 2026-09-25) established four things that outlive the slice.

**1. On this machine, local-LLM latency is set by output tokens, not parameter count.**
Measured on the user's M1 Max/32 GB: `qwen3:14b` 16 s and `qwen3:4b` **32 s** on a free-JSON prompt
(the smaller reasoning model was twice as slow), versus `llama3.2:3b` **0.13–0.17 s** warm and
`qwen2.5:7b-instruct` sub-second on a six-token closed-vocabulary answer.

**Why:** qwen3's thinking trace is not reliably suppressed by `/no_think`, and the trace is the
whole cost. Once output is closed and short, latency stops constraining model choice — memory
residency and reliability constrain it instead.

**How to apply:** never plan a runtime model call around free generation. Design the call so the
answer is a handful of tokens drawn from a list the code supplied, then pick the *largest*
non-reasoning instruct model that fits in memory, not the smallest one. Re-check any latency claim
with `cat plans/brain-layer/probe-prompt.txt | ollama run <model> --verbose`.

**2. Small models silently guess on genuine ambiguity, and a bigger model does not fix it.**
Both `llama3.2:3b` and `qwen2.5:7b-instruct` picked a contact when two candidates fitted equally.
That violates `belief/voice_commands.py`'s stated behaviour #2 ("ambiguous is never a silent best
guess").

**The fix, which worked on both:** the *code* owns the ambiguity finding (`parse_utterance` already
sets `reason_escalated="ambiguous_reference"`), and the model may only override it by **quoting
verbatim words from the transcript** as its evidence. A deterministic validator then rejects the
pick if those words are equally true of another candidate. The 3B's wrong `PICK CONTACT_7 BECAUSE
"tank"` was converted to a correct `ASK` by that test alone.

**How to apply:** whenever a plan gives a model a judgment call, ask what the code already knows
deterministically and make that the default the model must *argue against with quoted evidence* —
rather than the question the model is asked from scratch. The result is that model quality
determines how often Petrovich asks, never whether he acts wrongly, which is what makes the model
swappable.

**3. The `BrainClient` seam was already async-shaped and nobody had noticed.**
`handle(payload) -> None` plus a separate `awaiting_reply_id()` is fire-and-forget by construction.
The missing half was a reply path: `_handle_utterance` calls escalation then `return []`. The fix
follows `logger.py`'s established pattern (`_poll_f10_commands` / `_poll_transcripts`) — a
`drain_brain(now_sim)` in the same poll loop — rather than a callback or a thread touching `_print`,
which is not thread-safe and owns `CalloutScheduler`'s occupancy.

**4. `tool_api.py`'s `TOOL_SET` is transport-agnostic and there is no tool server.** Body-layer has
only ever been an HTTP *client*. So "put the brain in its own process" costs a tool server the
moment the brain needs tools — which BR-1 avoids entirely because all three behaviours are
answerable from `EscalationPayload` alone, and which BR-2 may also avoid, because `parse_utterance`
already runs `find_contact` body-side and puts narrowed candidates in the payload. Check that before
anyone concludes the brain must be in-process.

Related: [[bl5a-text-mode]] precedent for `PendingConfirmation` reuse; [[provenance-confidence-pattern]].
