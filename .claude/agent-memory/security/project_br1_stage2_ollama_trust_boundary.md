---
name: br1-stage2-ollama-trust-boundary
description: BR-1 Stage 2 (OllamaDecider) deep security analysis findings and the confirm-token validator gap to watch for elsewhere
metadata:
  type: project
---

BR-1 Stage 2 (`feature/brain-layer-stage2` @ cdb8c7f) put a real local model (OllamaDecider) behind
the brain-layer wire for the first time — first place in this project where model-generated text
crosses a process boundary and is acted on. Full findings: `plans/brain-layer/security-review.md`'s
Stage 2 section. Verdict: APPROVED, two RECOMMENDED (non-blocking) fixes, no REQUIRED fixes.

**The pattern worth remembering: D10's validator (`body-layer/src/belief/brain_reply.py`) checks
PICK against the exact candidate list offered, but checks CONFIRM against the *full* dispatchable
token set rather than the narrower vocabulary the model was actually shown**
(`brain-layer/src/prompts.py`'s `CLASSIFY_COMMAND_VOCABULARY`, 7 tokens, vs.
`crew_console.DISPATCHED_COMMAND_TOKENS`, ~30 tokens including slot-taking ones). A hallucinated
`CONFIRM <token>` naming a token outside the offered vocabulary currently fails safe (confusing
confirm prompt, then a documented "say again" degrade if affirmed) because `_describe_token_for_
confirm`/`handle_command` both gracefully degrade slot-taking tokens called with no slots — but this
is incidental, not designed-in. **When reviewing any future validator that checks "is this reply
legal" against a broader set than "what was this specific call offered," check whether the two sets
can diverge** — PICK got this right (checks the payload's own offered list), CONFIRM did not (checks
body's global capability set). [[project_brain_layer_wide_bind_no_benefit]]

**`_unquote` (decider.py) was added specifically to fix a live-observed defect** (model wraps
BECAUSE evidence in quote characters, which then fails D10's literal-substring check since the
transcript never contains the quote char) — reviewed this stage for a smuggling bypass and found
none: it strips exactly one matched pair only when the *whole* string is bracketed by it, an
unbalanced quote is left for D10 to reject rather than repaired. Confirmed no rewrite/injection
path.

**`because` (the PICK justification) is validation-only, never spoken** — grepped confirmed it's
read only inside `brain_reply.py`. This bounds the impact of D10 having no minimum length on the
discriminating quote: worst case from a degenerate 1-2 char match is picking the wrong *but real,
currently-tracked* contact, not a data leak or spoken fabrication.

**No-omniscience held**: traced every value in `prompts.py`'s two templates — only `transcript` and
candidate `(id, why)` pairs (belief-derived, never raw DCS ids/positions) reach the model;
`situational_header` crosses the wire but `OllamaDecider` never reads it.

Sandbox denies live Ollama network access for every agent on this feature — all analysis here is
static (code reading), not a live run, except where explicitly noted otherwise in the security-review.md text.
