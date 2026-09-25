---
name: br1-stage2-because-quote-bug
description: BR-1 Stage 2 (OllamaDecider/D10 validator) APPROVED WITH MINOR FIXES — found a real quote-character bug in D10's BECAUSE check by tracing a test's own expected value, not by reading alone
metadata:
  type: project
---

Reviewed `feature/brain-layer-stage2` @ `35e6de0` (diff vs parent `6b8a86e`). Verdict: APPROVED
WITH MINOR FIXES. Full write-up: `plans/brain-layer/review.md`, "Stage 2 review" section.

**The required fix, and how it was found.** `brain-layer/tests/test_decider.py::
test_ollama_decider_candidates_present_calls_discriminate_prompt` scripts a fake Ollama response of
`PICK CONTACT_7 BECAUSE "near Gemerek"` (model wraps its quoted evidence in literal quote marks —
a very natural completion given the prompt says "quote... verbatim") and asserts the parsed
`because` field is `'"near Gemerek"'`, quote characters included, as the *correct* expected value.
Nobody had piped that value through `belief.brain_reply._validate_pick`'s substring check. Doing so
by hand showed the literal quote characters make the substring check fail against the plain
transcript, degrading a correct `PICK` to a spurious `ASK`. A fix for exactly this defect class
exists elsewhere in this repo's history (commit `bee408b`, "Unquote the model's BECAUSE evidence")
but is not an ancestor of `35e6de0` — confirmed via `git merge-base --is-ancestor` — so it was not
carried into this branch.

**Technique worth repeating: when two test suites each cover one half of a pipeline (syntactic
parse vs. semantic validation) but neither composes them, manually compose their own fixture/
expected values and check the seam.** `test_decider.py` tests parsing in isolation; `test_brain_
reply.py` tests validation in isolation with hand-written `because` values that never contain
quote characters. Reading each file alone looks clean. Only running the parser's *own asserted
output* through the validator surfaces the gap. This is the same "grep for the new mechanism's own
call site, not the file list" family of check from the role file's standing instructions, applied
one level down — here it was "compose the two halves the test suites individually cover, don't
trust that covering each half separately covers the seam."

**D11's `NO_SUCH_COMMAND` routing judgment call — independently verified, agreed.** The task asked
for an independent read on whether routing `NO_SUCH_COMMAND` to a live classify-prompt call (while
keeping `NO_MATCH` structural) was consistent with the plan. D11's own text is self-contradictory
("neither needs asking" vs. scope item 2's explicit need for a model judgement call on near-miss
verbs) — the implementation's reading (`structural_unable_reason`'s own "usually" as the seam) is
the only one that satisfies both, was already flagged by the implementer in `implementation.md`'s
own "Notable Discoveries", and does not violate any invariant (the model is still only classifying
against a closed, code-owned vocabulary — `CLASSIFY_COMMAND_VOCABULARY` — with the full
`DISPATCHED_COMMAND_TOKENS` set as the real body-side safety authority regardless of what the model
was offered). Logged as a SUGGESTION (get explicit user/architect sign-off before Stage 4), not a
required fix — the code does the only workable thing given contradictory plan text.

**Non-blocking invariant (poll_replies off the shared thread, decide() under a bounded
ThreadPoolExecutor timeout) — both prerequisites genuinely fixed, not timeout-value tweaks.**
Re-ran the wedge tests directly against real raw-socket TCP-accept-then-never-answer listeners
(not mocked) at both the client level and through `CrewConsole.drain_brain` — confirmed the fix
holds, not just documented. One accepted residual: a permanently-hung `decide()` call (ignoring its
own Ollama client timeout entirely) still leaks one `ThreadPoolExecutor` worker forever, since
Python cannot preempt a blocked thread — documented in three places by the implementer, correctly
scoped as accepted risk rather than hidden.
