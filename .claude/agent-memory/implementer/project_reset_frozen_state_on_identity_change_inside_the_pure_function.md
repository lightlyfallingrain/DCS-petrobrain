---
name: reset-frozen-state-on-identity-change-inside-the-pure-function
description: when a (state_in, subject) -> state_out pure core is re-pointed to a new subject between calls, reset state inside the function on an identity-key mismatch, not at call sites
metadata:
  type: project
---

BL-14's `belief.attack_run.decide(state, *, contact, ...) -> (new_state, speech)` is modelled on
`belief.optic_policy.decide`'s shape: a frozen `AttackRunState` dataclass, replaced wholesale each
call, carried across ticks by the caller. The security-fix review (`plans/attack-run/review.md`
finding 5) found that every field on `AttackRunState` described "this contact's last look," but the
function had no contact identity attached to the carried state at all -- so a mid-run re-point to a
different contact (sanctioned by an earlier security fix) silently fed the *new* contact's tier-2
elevation guidance from the *old* contact's remembered altitude, and separately could suppress the
new contact's first callout entirely if its geometry happened to match the old contact's last-spoken
cadence baseline.

**Fix: add an identity field (`last_contact_id`) to the state, and at the top of the pure function,
reset the whole state to fresh defaults the moment `state.last_contact_id != <current subject>.id`.**
Chosen over resetting at every call site that can cause a re-point, because the call sites were not
all known to reset it -- `logger.py`'s own reset only fired on an explicit `engage` transition, never
on a bare mid-run reselection, which was exactly the gap the bug lived in. The pure function is the
one place that already sees both the carried state and the current subject on every call, so
resetting there makes the invariant ("this state describes this subject") hold regardless of which
caller produced the re-point, present or future.

**Why this generalizes**: any `(frozen_state, subject) -> frozen_state` core carried across ticks by
an external caller is vulnerable to this the moment "the subject can change between calls" becomes
true for *any* reason -- a reselect, a task handoff, a merge. If the state was designed assuming the
subject is constant for the state's whole lifetime, every per-subject field is latent run-level
leakage once that assumption breaks. Audit every field against "does this describe the run, or this
specific subject" before accepting a reselection/re-point feature, not after a review finds it.

**A secondary finding worth remembering**: not every field flagged by this audit needs a *reachable*
reproduction. `last_spoken_tier` looked equally suspect, but turned out structurally unable to carry
a wrong value across a re-point in this codebase, because the renderer's tier-2 text always carries
an appended qualifier that tier-1 text never has -- so the change-detection check that gates
re-emission (`text != last_spoken_text`) always fires whenever the two ticks' tiers actually differ,
forcing a fresh (correct) tier to be recorded. The only way that field goes stale is when old and new
tiers are the *same*, in which case the stale value is also the correct one. Write a documentation
test for this kind of case (asserting the structural property directly, e.g. "these two renders are
never equal") rather than forcing a reproduction that cannot exist -- see
[[verify-structural-guarantees-not-just-reproductions]] if that memory exists, otherwise this is the
worked example.
