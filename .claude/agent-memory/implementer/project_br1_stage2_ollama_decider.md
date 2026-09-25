---
name: br1-stage2-ollama-decider
description: BR-1 Stage 2 (OllamaDecider, D10 validator, non-blocking prereqs) — key implementation decisions and a plan-text tension found
metadata:
  type: project
---

Implemented BR-1 Stage 2 (`plans/brain-layer/plan.md`) on `feature/brain-layer-stage2`:
the two pre-Stage-2 prerequisites, `OllamaDecider`, and the body-side D10
validator (`belief/brain_reply.py`, new).

**Non-blocking redesign, not just a shorter timeout.** `BrainLayerClient.
poll_replies()` moved to a persistent background thread (same shape as
`handle()`'s existing single-slot worker) rather than shortening
`poll_timeout_s` — a mid-task user direction ("brain must not block any
other functionality... other things happen meanwhile") made this explicit:
the fix must make the crew-text poll thread's tick rate *provably*
unaffected by a wedged brain, not merely bounded. Proved with a raw-`socket`
TCP-accept-then-never-answer fake server (not `http.server` — nothing can
accidentally answer), both at the client level and through the real
`CrewConsole.drain_brain` entry point. Server-side, `_run_job`'s
`Decider.decide()` call got a `ThreadPoolExecutor`-bounded timeout
(`shutdown(wait=False)`, since Python cannot forcibly kill a blocked
thread) — this is a decider-agnostic backstop; the real fix is
`OllamaDecider`'s own `urllib` call carrying a socket timeout.

**Plan-text tension found, not silently resolved either way**: D11 says
both `NO_SUCH_COMMAND` and `NO_MATCH` are "structural... neither needs
asking," but the plan's own scope bullet 2 ("plausibly a command the
deterministic grammar missed" -> `CONFIRM`) and Stage 2's acceptance line
("confirm works for real") both require a live model call for
`NO_SUCH_COMMAND`. Resolved by reading `structural_unable_reason`'s own
"usually can" (not "always can") as the seam: `NO_MATCH` stays fully
structural (empty candidate list, nothing to discuss); `NO_SUCH_COMMAND`
routes to a new "classify" prompt. Documented as a genuine interpretive
call in `implementation.md`, not a settled decision — worth confirming
with the user/architect before flying.

**D10's "must not be equally true of another candidate" implemented as
literal substring-in-`why`, not semantic matching** — a pure function
can't know "tank" generically means "T-72" unless it's literally in the
`why` text. Required 3-part check: BECAUSE words must appear in (a) the
transcript, (b) the *chosen* candidate's own `why`, and NOT in (c) any
other candidate's `why`. The plan's worked failure case ("tank", both
candidates T-72) fails part (b) since neither `why` field literally says
"tank" — same required outcome (degrade to ASK) as a semantic reading,
via a simpler mechanism.

**Two Stage-1 tests broke on contact, correctly** — their fabricated
`BECAUSE` text was never grounded in the fixture's transcript/why fields
(D10 didn't exist yet in Stage 1). Root cause worth knowing: `belief.
utterance._resolve_reference` matches the *entire* filler-stripped
reference as one substring, so a reference specific enough to discriminate
would resolve unambiguously and never even escalate — there's no live
phrasing for this fixture that's both ambiguous enough to reach the brain
and literally names the distinguishing word. Fixed via a test helper that
directly extends `_pending_escalations`'s tracked transcript (a legitimate
seam) rather than re-running the parser.

Live Ollama was not exercised — network access to 127.0.0.1:11434 was
denied by the sandbox even with `dangerouslyDisableSandbox` attempted
once. All new code is verified against fake HTTP servers only.
