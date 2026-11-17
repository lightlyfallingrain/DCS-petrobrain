---
name: feedback-latent-unreachable-is-not-the-same-as-unexposed
description: when an implementer defers a known defect because "no shipped rule/caller exercises it yet," check whether the mechanism itself is already callable (documented in a README, registered in a namespace, loadable from a config file) before accepting "unreachable in practice" as a reason not to fix now
metadata:
  type: feedback
---

BL-17 Stage 3d (`plans/speech-rules/plan.md` D20, effector-write action surface) shipped a real
cross-thread data race (`body.py`'s `_request_effector_write` closure mutating
`crew_runner.effector_state` directly from rule dispatch, reachable from both the poll thread and
the REPL thread) and a dedup gap that silently drops a pilot's most recent command in favour of a
stale one. Both were flagged honestly by the implementer in `implementation.md`'s "Notable
Discoveries" and in persistent memory, and both were deferred with the same reasoning: "no shipped
rule calls `effector.write` yet, so this is latent and unreachable in practice."

**That reasoning is only sound if reachability actually requires the next planned stage.** Here it
did not: `effector.write` was already registered in `ACTION_NAMESPACES`, documented as a live call
in `config/rules/README.md`, and loadable from any `.lua` file dropped into `config/rules/` — none
of that is gated behind "Stage 5." A stray hand-written rule file, added at any point before Stage
5 is formally scheduled, reaches both defects immediately. "No shipped rule calls this *yet*" is a
claim about the current roadmap, not about what the code will let happen.

**How to apply:** when a plan or implementer note says a defect is deferred because nothing
currently exercises it, check three things before accepting that: (1) is the mechanism itself
already registered/exposed (a namespace table, an action registry, a README entry, a loader that
reads arbitrary files from a directory) rather than gated behind code that does not exist yet; (2)
does the next stage that's said to "need it first" actually touch the field/mechanism in question,
or is that just assumed; (3) is there an established pattern elsewhere in the codebase for exactly
this situation (here: every other cross-thread effector path already uses a one-shot
`CrewConsole` field drained on the poll thread) — if so, the fix is not "inventing new design under
schedule pressure," it is applying the existing one, which weakens the case for deferring.

See [[project_bl17_effector_write_repl_thread_race]] (implementer memory, same mechanism) and the
review itself: `plans/speech-rules/review-stage3d.md`.
