---
name: new-exception-type-feeding-an-existing-boolean-gated-mechanism
description: When a refactor adds a new failure/outcome type that flows into an existing commit-or-discard (or similarly boolean-gated) mechanism, verify by direct execution that the flag lands the way the decision intends, and check specifically whether a test exercises that new-type x existing-mechanism combination -- don't assume coverage is symmetric with the old type's.
metadata:
  type: feedback
---

Found reviewing `refactor/rule-action-unable-throw` (BL-17, 2026-11-18): a failed rule action now
raises `RuleUnable` instead of returning `{ok=false}`, and `run_rule` catches it with
`error=False` (an ordinary outcome, not a dispatch error). `CrewConsole._dispatch_rule`'s
pre-existing buffer-then-commit mechanism (built across three earlier review rounds --
[[bl17-d6-rollback-does-not-cover-queued-effector-writes]],
[[bl17-fix4-rollback-races-fix1-drain]]) decides whether to commit or discard a dispatch's
buffered `effector.write` calls purely by reading that same `error` boolean. The refactor never
touches `_dispatch_rule` at all, and correctly so -- but that means the one place proving "an
`unable` commits its buffered writes, a genuine bug still rolls them back" is *inference from two
separate pieces of code*, not a single piece of evidence.

**What I did, and why it was the right amount of checking:** read both halves (where `RuleUnable`
sets `error`, where `_dispatch_rule` reads it), then actually ran the combination end to end --
built a tiny rule file calling `effector.write` then a second action returning `ok=false`,
dispatched it through the real `handle_command`/`_dispatch_rule` path, and printed
`pending_effector_writes` afterward. It committed, as the user's own direction said it should.
Reading alone would have been a defensible verdict; running it converted "should be true given
the code" into "is true."

**The actual finding:** zero tests in the diff exercise this specific combination. The symmetric
case -- write then a genuine `RuleRuntimeError` -- has three dedicated tests in
`test_rules_effector_action.py`, inherited from the three earlier review rounds on this exact
field. The new case this refactor introduces has none. Flagged as a required fix (add one test
mirroring the existing "success commits" test but with the second action answering `ok=false`),
not because the behaviour is wrong -- it isn't -- but because the thing that makes it correct
today is an interaction between two files that no test pins, and a future edit to either side
(e.g. someone deciding `RuleUnable` should also set `error=True`) would have nothing to catch it.

**How to apply:** when a diff adds a new case into an existing union of outcomes that already
feeds a shared boolean-gated mechanism (commit/discard, retry/fail, rollback/keep), (1) find every
place that boolean is set and every place it's read -- not just the new code's own tests, (2)
run the new case through the existing mechanism directly rather than trusting that "the flag is
False, and False already means commit" is self-evidently fine, and (3) check whether a test pins
the *combination*, not just each side separately. A mechanism this heavily fought-over across
three prior review rounds (see the two linked memories) is exactly the kind of thing a fourth,
unrelated refactor can silently misalign with much later.
