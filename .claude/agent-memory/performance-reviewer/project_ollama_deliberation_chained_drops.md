---
name: ollama-deliberation-chained-drops
description: a per-call Ollama timeout bounds one client's cost but not Ollama's own serialized queue — a genuinely deliberating model can chain-drop several utterances, not just one
metadata:
  type: project
---

`OllamaDecider`/`OllamaClient` (`brain-layer/src/ollama_client.py`,
`decider.py`) use `stream: false` and a per-call 5.0 s socket timeout
(`OllamaClient.DEFAULT_TIMEOUT_S`) — confirmed by direct measurement to
reliably bound the *client's own* cost of a hung/slow far side (see
[[brain-layer-stage2-decider-timeout]]).

What that timeout does **not** bound: a real local Ollama daemon serializes
generation (one model, one GPU/CPU budget). If a model actually deliberates
the way D6 measured `qwen3:4b` doing (32.7 s, chain-of-thought before its
answer), the client abandons that call at 5 s but Ollama keeps computing it
server-side. A second utterance arriving during that window queues behind
the first on Ollama's side and is itself likely to time out at 5 s too — for
as long as the original slow generation runs, i.e. several consecutive
dropped utterances from one deliberation, not one bounded cost.

**Why this matters for future review:** the current mitigation
(`qwen3:4b-instruct-2507-q4_K_M`, "architecturally non-thinking", plus
prompt discipline) is a runtime assumption about model behaviour, not
something code enforces or detects — nothing in this codebase notices if a
future model swap regresses into "thinking" mode; the parser degrading a
chain-of-thought preamble to `ASK` is a *correctness* safety net (never a
wrong pick), not a *cost* one. `live_stage2_decider_check.py` as written
drives one utterance at a time (waits for each reply before sending the
next) — it would show one slow/timed-out reply, not the chained-drop
pattern. Worth adding an overlapping-utterance scenario to that tool before
trusting this mitigation past a single-user sortie — flagged MONITOR, not
NOW, in the Stage 2 review since it's not observed (no live Ollama reachable
in-sandbox) and speculative to build without a daemon to validate against.
