---
name: security-fix-uniform-remedy-wrong-for-one-of-two-sites
description: when a Security required-fix prescribes the same remedy for two call sites sharing a crash shape, check each site against the player-facing failure contract separately -- the two sites are not guaranteed to be equivalent just because the crash they prevent is
metadata:
  type: feedback
---

Found reviewing BL-17's Security Required Fix 1 (`plans/speech-rules/security-stage0-2.md`,
`feature/speech-rules`, fix commit `f6304355`). Security flagged two Lua->Python `int()`
conversions in `body-layer/src/rules/engine.py` that could raise a bare `ValueError`/
`OverflowError` instead of a catchable `LuaError`/`RuleRuntimeError`, crashing the crew-text
main-thread REPL. Security's own required-fix text prescribed the *same* remedy for both --
degrade to the existing `render_unable` "Unable." graceful-degradation posture -- and the
implementer built exactly that, for both sites, correctly matching the fix text.

**One of the two was right, the other wasn't**, and the difference was invisible from the crash
shape alone:

- `_make_action_wrapper`'s reject branch already had an established, previously-reviewed contract
  (predating this fix): a bad call answers `{ok=false, reason=nil}`, and every rule that calls an
  action is written to check it explicitly (`if not r.ok then say(unable(r.reason)) end`). `nan`/
  `inf` joining that reject branch is the same failure class using the same mechanism the rule
  author already handles. Correct.
- `_digits_readback` (the `digits` global) had **no** prior contract at all -- it was a bare lambda
  with zero validation before this fix. There is no rule-visible check-and-handle point the way
  there is for actions; a rule just does `say(digits(n))`. Degrading silently to "Unable." here
  means no stderr log (the user's explicit decision requires one: *"Rule clash or lua error etc ->
  std error log and say aloud 'action file error'"*) and a spoken word this project's own
  "Unable." convention reserves for a legitimate precondition failure, not a rule-file bug. This
  one needed to **raise** (`RuleRuntimeError`, which `run_rule`'s existing `except` already
  catches and routes to D6's `ACTION_FILE_ERROR_LINE` + log + rollback), not degrade.

**How to apply:** Security's charter is crash prevention, not which failure the pilot is told
about -- per this project's current scope split (`security.md` "Scope", restated in `reviewer.md`
checklist item 1), player-facing correctness is Reviewer's alone to hold. When a security fix
touches two or more call sites with a uniform remedy, check each site **against the plan's own
failure-reporting contract (its `D<n>` decision, or the project's established "Unable." vs
"Action file error." vocabulary)** independently, not just that the remedy closes the crash for
both. A fix that is empirically correct (tests pass, mutation confirms they're real, the crash
path is genuinely closed) can still be the *wrong* fix for the player-experience half of the
problem, and nothing about the test suite passing will surface that -- it has to be read against
the decision record. Confirmed the alternative (raise instead of degrade) actually produces the
D6 shape by patching and probing `run_rule` directly, not just by reasoning about it -- see
`plans/speech-rules/review-security-fix.md` for the probe.

See [[feedback_architecture_decision_text_vs_scoped_down_build]] -- a related but distinct shape:
there a departure from a plan decision was honestly disclosed but the plan document itself went
stale; here the departure from the decision (D6) wasn't disclosed as a departure at all, because
the fix's author (Security) wrote the remedy without checking it against D6 in the first place.
