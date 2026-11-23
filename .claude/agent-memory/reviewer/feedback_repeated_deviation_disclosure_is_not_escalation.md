---
name: repeated-deviation-disclosure-is-not-escalation
description: an Implementer's "flagged for the architect's own review" note in a Deviations section, repeated stage after stage for the same requirement, is a disclosure habit, not an actual escalation -- check whether the architect/user was ever actually asked before accepting a second or third deferral of a specific, twice-stated user instruction.
metadata:
  type: feedback
---

Found reviewing BL-16 lift-vector LV-1 (`plans/flight-lift-vector/review-lv1.md`, 2026-11-23).

The user's own words (plan.md, section A, verbatim) were specific and repeated: run the law at
30 Hz, interleaved, with only the axis write staying every frame ("the axis write itself may have
to stay every frame -> this is true" -- confirming everything *else* should move off per-frame).
LV-0's implementation deferred moving `law_update` itself to this cadence, with a Deviations note
saying this was LV-1's own job ("the first stage that actually changes what the law does"). The
LV-0 Reviewer accepted that, explicitly on those grounds.

LV-1 deferred it *again*, with a near-identical Deviations note ("flagged for the architect's own
review, same posture as LV-0's own analogous deviation"). Reading `implementation.md` alone, this
reads as a conscientious, disclosed judgment call -- it names the plan section it departs from, it
gives a risk-based reason (splitting the law's bit-exact-take/anti-windup state machine across
interleaved phases is materially riskier), and it says it's "flagged." But there is no evidence
anywhere in the record (plan.md, explore-notes.md, no new amendment section) that the architect or
the user was actually asked a second time. "Flagged for the architect's own review" is the
Implementer's own phrase, not confirmation that a review happened -- and a plan amendment section
(the kind `plan.md`'s own "Amended (2026-11-20...)" header shows this project uses when the user
*does* re-decide something) would be the written evidence, and none exists.

**The tell**: the Implementer's own counter-argument doesn't fully address what the user actually
said. The user complained about "flight control calculations" running every frame generally (the
trig-heavy lift-vector math, the priority chain, the integrators); the Implementer's reasoning
("the estimator's own `LoGet*` reads are already gated to `LAW_HZ`... `law_update` itself makes no
`LoGet*` call at all") answers a narrower claim about per-frame *I/O* cost, not the CPU cost of the
calculations themselves, which was never measured or compared at 140 Hz vs 30 Hz anywhere in this
pass or the perf review that preceded it (`perf-plan-review.md` predates this finding and never
addresses law-rate interleaving). A disclosed deviation whose own stated reasoning quietly narrows
the scope of what it's answering is a second tell worth checking for, independent of whether it's
been deferred before.

**How to apply:** when a Deviations section defers the same specific, verbatim-quoted user
instruction for a second (or later) stage in a row, do not treat the disclosure itself as
sufficient -- check (a) whether a plan amendment or explore-notes entry shows the user/architect
was actually asked again (this project's own pattern for a genuine re-decision), and (b) whether
the Implementer's own counter-argument actually answers what the user said, or a narrower
restatement of it. Absent both, default to a required fix: send it back for an explicit sign-off
(architect or user) before accepting a repeated deferral as the stage's final shape. This is the
same family as [[accepted-decision-dropped-with-no-disclosure]] but the opposite failure mode --
that one was silently dropped with no disclosure at all; this one is disclosed every time, which
makes it easier to wave through, not harder.
