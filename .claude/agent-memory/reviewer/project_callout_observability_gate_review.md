---
name: callout-observability-gate-review
description: A "total gate" review needs the full list of newly-covered kinds derived from the gate's own predicate, not from the fix's own prose — found a third kind the writeup never named.
metadata:
  type: project
---

`fix/callout-observability-gate` (2026-10-06, `61edc58`). The fix moved the no-omniscience gate from
event *emission* to the speech choke point (`CalloutScheduler.tick`), deliberately covering **every**
spontaneous candidate rather than a per-kind list.

**The finding, and the technique that produced it.** The writeup, the module docstring, the inline
comment and the user-facing question all described the widening as two kinds —
`CONTACT_DETECTED`/`CONTACT_REACQUIRED`. It was three. The way to see it is not to read the fix's
prose but to **compute the delta yourself**: grep the *old* gate's variable (`observable_or_grace`)
for its call sites — two, motion and range-crossed — then intersect the new gate's reach
(`_TEMPLATED_KINDS`, because the new gate discriminates on the contact and not on the kind) against
that. The set difference contained `CONTACT_ENGAGEMENT_CHANGED`, whose emission block had never been
gated and which nothing in the writeup mentioned.

**Why it mattered rather than being pedantry:** the third kind was the only safety-relevant one — a
watched SAM/ZSU astern whose engagement envelope starts covering the aircraft now goes silent, and
permanently rather than late, because the grace window equals `CALLOUT_MAX_AGE_S`. The user was
being asked to approve a two-kind widening and would have been approving a three-kind one.

**Generalisable:** when a fix replaces a per-kind list with a "total" gate, the fix's own account of
what newly falls under it is a *claim about a set difference*, and set differences are the thing
authors get wrong. Derive it from the two predicates. This is the same failure shape as the standing
"grep for the new mechanism's own call site" check, inverted: there the file list looked complete
while the mechanism was missing; here the mechanism was complete while the list of what it caught
was short.

**Two probes worth reusing on any defer-rather-than-consume gate:**

- **Does the deferred candidate retire?** Hold the suppressing condition true across many ticks and
  watch the scheduler's `_consumed` set, then release the condition far past the age bound and
  assert silence. Here it flipped at age 11 against a 10 s bound, and did not resurrect.
- **Run the counterfactual ordering.** Moving the gate above the `CALLOUT_MAX_AGE_S` check made
  `_consumed` never fill through 60 s of ticks — which is what justified the ordering the author
  claimed. Reading the two `continue`s would have told me the same thing, but the probe is what made
  it a fact rather than a reading, and it cost one edit.

**Pull-path independence is checkable mechanically and should be.** The claim "`_handle_report` can
never reach this gate" was verified by extracting every `self.*` attribute its body touches
(`enrichment`, `store` — nothing else) and by counting `callout_observable`'s call sites tree-wide
(exactly two, both inside one function with one caller). "I read it and it looked fine" and "it is
structurally impossible" differ in value exactly here, and the crew query path depends on the latter.

See also [[feedback_verify_pipeline_wiring_not_just_module]],
[[project_watch_reporting_approved]], [[project_sortie_0926_fixes_observability_gate_review]].
