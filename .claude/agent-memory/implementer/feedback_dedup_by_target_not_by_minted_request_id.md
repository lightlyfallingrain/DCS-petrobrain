---
name: feedback-dedup-by-target-not-by-minted-request-id
description: when a plan says a new mechanism "mirrors" an existing trigger-keyed dedup (fire_trigger-style "no-op if already running") but the new mechanism is keyed by a caller-minted, always-fresh id instead, re-derive the dedup check from the plan's own test-list wording (what gets deduped), not from a literal transcription of the old key shape
metadata:
  type: feedback
---

`belief.effector_engine.request_write` (`[[BL-17]]` D20, `plans/speech-rules/plan.md` Stage 3d)
was described in the plan's main body as "mirrors `fire_trigger`'s own 'start if idle' shape."
`fire_trigger`'s dedup is a direct dict-key check: `EffectorRunState.runs` is keyed by
`EffectorTrigger`, so "fire while already running" is just `trigger in state.runs`. A literal
transcription of that shape onto `EffectorRunState.ad_hoc_runs` (keyed by a caller-minted
`request_id`, per D20's own text, "not an `EffectorTrigger`") would be `request_id in state.
ad_hoc_runs` — but every real call site mints a *fresh* id per dispatch (an `itertools.count()` in
`body.py`), so that check can essentially never fire, and does not implement what the mechanism is
actually supposed to prevent (two live requests piling up against the same physical switch).

**The plan's own Stage 3d test list said it more precisely than the main-body prose**: "a second
request for the *same effector* while one is pending is a no-op." That is the real spec — dedup
by the *target* (`.effector`), not by the wrapper key the new data structure happens to use.

**How to apply:** when a plan says a new mechanism "mirrors"/"same shape as" an existing one, and
the new mechanism's own key type differs from the old one's (here: opaque minted id vs. a closed
enum), do not transcribe the old dedup check literally onto the new key — ask what the dedup is
*for* (usually: don't let two logical requests collide on the same underlying resource), check the
plan's test list for a more specific statement of that, and implement against the resource/target
identity instead of the storage key. This is the same shape as root `CLAUDE.md`'s "a plan's
test-list example can contradict its own stated invariant" risk, one level further: here the test
list didn't contradict the prose, it was simply *more specific* about which axis the "same"
in "mirrors" refers to, and the prose's own analogy (same shape, different key) was the thing that
needed re-deriving rather than copying.
