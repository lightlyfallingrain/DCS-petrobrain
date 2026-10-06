---
name: subject-discriminating-gate-breadth
description: A gate discriminating on the subject takes its breadth from a kinds set, not its call sites — enumerate the set by import, and test any exemption's admission bar against the non-members.
metadata:
  type: feedback
---

When a filter at a chokepoint discriminates on the **subject** (a contact, a user, a record)
rather than on the **kind** of thing being filtered, its breadth is defined by whatever set feeds
the chokepoint — not by its own call sites. Enumerate that set before claiming what the gate
covers. And if some member must be exempted, make the exemption a **named set with a stated
admission bar**, never an inline `!=`.

**Why:** on `fix/callout-observability-gate` (2026-10-06) the observability gate was deliberately
moved from per-kind emission sites to one speech-time chokepoint and made to discriminate on the
contact — correct, and the only way to cover a path that mints no event at all. But that made its
breadth equal `_TEMPLATED_KINDS`, a six-member set declared ~600 lines away and maintained for an
unrelated reason. `grep` of the gate's call sites showed two kinds; the real answer was six, and
the third unenumerated one (`CONTACT_ENGAGEMENT_CHANGED`) was the only safety-relevant member —
a threat warning, where the cost of suppression is a missed SAM rather than a missed
identification. The Reviewer caught it; the implementation, the plan, the inline comment and the
user-facing question had all described it as two kinds.

The framing of the fix (decided in the review loop on the Reviewer's recommendation — **not** by
the user, who was never consulted; an earlier version of this memory and of the branch's own prose
misattributed it): an exclusion list has the same failure shape as the per-kind list the widening
removed, only in reverse — a kind that joins it exempts itself quietly. So the exempt set's
docstring states what a member must *be*, rather than just listing one.

**The first bar written for it did not discriminate, and that is the sharper lesson** (round 3,
same branch). It read *"a cue derivable from already-held belief plus ownship state, and never a
claim about what Petrovich can see right now"*. Both clauses fail against the actual members:
"derivable from already-held belief plus ownship state" is **equally true of the kind that must
stay gated** (`CONTACT_RANGE_CROSSED` compares the same believed position against the same
ownship), and "never a claim about what he can see right now" **excludes the exempt kind itself**,
since its rendered line speaks a believed clock hour and range. A reader applying it literally gets
the wrong answer either way, so the set was as silently joinable as the list it replaced.

What actually separated the exempt kind was already in the docstring **as motivation rather than
as criterion**: the cost of silence is a *missed threat cue the pilot needs in order to evade*, not
a missed identification; and gating it costs the callout *permanently rather than late* (the grace
window equals the max age). Both required. Moving those two sentences from the rationale into the
bar was the whole round-3 fix — nothing had to be newly reasoned.

**How to apply:** whenever widening a per-case check into one general gate —
- Find the set that now defines its scope and enumerate it in the report *and* in the comment at
  the gate. Do not describe breadth from call sites.
- Ask of each member whether suppression is a *missed statement* or a *missed warning*. Those are
  not the same cost and may not want the same answer.
- Any exemption gets a named constant plus an admission bar, co-located with the gate — and
  **test the bar against the non-members before writing it down**. State it, then read it against
  each kind that must stay gated. If it admits one of them, or excludes the member you are
  exempting, it is not a bar. A property that is merely *true of* the exempt member is not a
  criterion; it has to be *false of* the others.
- **Derive counted claims about breadth by import, not by prose.** Round 2 of this same branch
  fixed "two kinds" to "four of six" in three places, each immediately above a correct list of
  five — a different wrong number is the same defect at smaller magnitude. `len(SET)` and
  `len(SET_A - SET_B)` take one line and cannot drift.
- Verify a new test by counterfactual (empty the exempt set, disable the bound) — but pick a lever
  the test does not itself import, per
  [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]]. See
  [[project_object_permanence_continuity_fix]] for the verify-by-disabling-the-fix pattern, which
  is the same move. Related: [[feedback_dont_improvise_scope_to_satisfy_plan_framing]].
