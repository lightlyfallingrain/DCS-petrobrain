---
name: subject-discriminating-gate-breadth
description: A gate that discriminates on the subject rather than the event kind takes its breadth from a kinds set, not from its call sites — enumerate the set, and give any exemption an admission bar.
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

The user's own framing of the fix: an exclusion list has the same failure shape as the per-kind
list the widening removed, only in reverse — a kind that joins it exempts itself quietly. So the
exempt set's docstring states what a member must be (a cue derivable from already-held state,
never a claim about a fresh observation) rather than just listing one.

**How to apply:** whenever widening a per-case check into one general gate —
- Find the set that now defines its scope and enumerate it in the report *and* in the comment at
  the gate. Do not describe breadth from call sites.
- Ask of each member whether suppression is a *missed statement* or a *missed warning*. Those are
  not the same cost and may not want the same answer.
- Any exemption gets a named constant plus an admission bar, co-located with the gate.
- Verify a new test by counterfactual (empty the exempt set, disable the bound) — see
  [[project_object_permanence_continuity_fix]] for the verify-by-disabling-the-fix pattern, which
  is the same move. Related: [[feedback_dont_improvise_scope_to_satisfy_plan_framing]].
