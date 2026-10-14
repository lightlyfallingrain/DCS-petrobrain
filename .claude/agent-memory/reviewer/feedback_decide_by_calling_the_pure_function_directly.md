---
name: decide-by-calling-the-pure-function-directly
description: when a per-tick `decide(state, ...)` state carries a value whose fail-open condition is described per-entity but implemented per-run, call the pure function directly with a carried-forward state rather than only exercising the public method -- a scheduler/occupancy gate in the public path can mask exactly the tick where the bug shows
metadata:
  type: feedback
---

On BL-14's security-fix review (`plans/attack-run/review.md`, "Security fix review" section,
finding 5), calling `console.drain_attack_run(carried_state, ...)` through the public method did
*not* reproduce a real staleness bug in `AttackRunState.last_known_target_alt_m` on the tick I
picked, because `CalloutScheduler.busy_until_sim` happened to still be in the future and the
"occupancy suppressed" branch returns the *input* state unchanged -- which looks exactly like "no
change happened" when actually the underlying `decide()` computed something wrong and was simply
never surfaced that tick.

Calling `belief.attack_run.decide(carried_state, ..., contact=new_contact, group=...)` directly,
bypassing the scheduler, showed the real tier-2 elevation computed from the *previous* target's
remembered altitude.

**Why:** `AttackRunState`'s own docstring claimed the fail-open field ("`None` only before the
first tier-1 look *this contact* has ever had") was per-contact, but the dataclass has no contact
identity in it at all -- it is per-*run*. A mid-run reselection (which this same security fix
turned into a sanctioned re-point rather than a refusal) carries the old target's value into the
new target's first tier-2 tick. The bug was real and reachable from an ordinary command sequence,
but invisible through the public method at the specific `now_sim` I first tried, because an
unrelated occupancy gate sits between `decide()` and the caller.

**How to apply:** whenever a module has both a pure `decide(state, ...)`-shaped core and a stateful
wrapper with its own gating (scheduler busy-time, debounce, cooldown), verify a stale-carry-over
claim against the pure function directly with a hand-built state, not only through the wrapper --
the wrapper's own gate can make "nothing printed" mean either "nothing changed" or "something wrong
happened but was suppressed," and those are indistinguishable from the outside. This generalizes
`[[feedback_check_the_premise_not_just_the_mechanism]]` and
`[[feedback_insertion_order_task_lookup_hides_reselection]]` -- a third shape of "the reader resolves
through a path the writer didn't update," this time timing-gated rather than ordering-gated.
