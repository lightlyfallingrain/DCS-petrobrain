---
name: bl-b47-air-defence-class-level-review
description: BL-B47 review — the implementer's "widens, not creates" hazard claim was true, and three oscillation probes proved it rather than arguing it
metadata:
  type: project
---

`fix/air-defence-class-level` (`eb11b7a`), APPROVED WITH MINOR FIXES — the only required fix was a
wrong count (`128` keyword entries, really 131) quoted in three places.

**What was worth the time: sizing a flagged hazard by executing it, in both directions.** The
implementer flagged that routing `_is_air_defence` through the classification lattice makes the
air-defence *repeat* clause fire in cases that were silent, and that clustering jitter could churn
it through a one-slot repetition guard — arguing it "widens a pre-existing mechanism rather than
creating one". Reading could not settle that. Three probes driving `render_group_disclosure` +
`mark_group_spoken` in `CalloutScheduler.tick`'s sequence, oscillating a contact in/out on
alternate ticks, did:

- one oscillating air-defence contact: **one** line, then silent. `mark_group_spoken` refreshes
  `last_spoken_member_contact_ids` *only when the group speaks*, so a contact announced once stays
  in the snapshot and a later rejoin is not an arrival. Single oscillators cannot churn.
- that contact **plus** a second out-of-phase oscillator: 10 lines in 10 ticks, indefinitely. Each
  speech refreshes the snapshot without the *other* oscillator and re-arms it. The one-slot
  signature guard is powerless against two alternating line shapes.
- **two oscillators of two distinct new classes, no air defence anywhere: the same 10/10, against
  the pre-fix predicate.** That is what settled it — the failure mode predates the commit, and the
  fix only lowers the ingredient count.

**The transferable move: when an author says "widens, not creates", construct the scenario with the
new mechanism removed entirely.** If it still fires, they are right and the fix ships; if it goes
quiet, the fix created it and "pre-existing" was a framing, not a fact. One probe decides a scope
argument that no amount of reading will.

Second finding, found by asking who guards the constant rather than reading the constant: three
copies of the air-defence class set exist, and only `crew_console`'s has a `<=` drift guard against
`object_model`. `belief.groups.AIR_DEFENSE_OP_CLASSES` — which this fix made the push path, the
pull path and the freshness marker all resolve against — has only a literal pin, i.e. a change
detector. Proven by injecting a fake `OP_XLRSAM` profile: `crew_console`'s test goes red,
`test_constants_are_the_stated_assumptions` stays green. Exposure unchanged by the diff, so an
observation, not a blocker. See [[feedback_a_literal_pin_is_not_a_drift_guard]].

Techniques reused and still earning their place: docstring-stripped AST diff to prove "no other
code changed" mechanically (it showed the predicate body was the *only* code change in a 644-line
file's diff); collecting the test count on an isolated `git archive` snapshot of the base commit to
confirm a `+21` delta; and widening the author's own enumeration (131 keyword entries + all 595
`reporting_names` mapping keys = 1060 candidates) rather than re-running theirs, which turned
"0 lost, 4 gained" from a claim into a far broader result.
