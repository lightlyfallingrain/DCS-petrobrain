---
name: project-relative-distance-grouping-clean-trace
description: relative-distance-grouping (BL-B106) plan check — traced cleanly, and the optic-ranging claim was verified against live code, not just plan prose
metadata:
  type: project
---

Plan check for `relative-distance-grouping` (BL-B106) came back ALIGNED. Every E1–E7 and every
Q1–Q4 answer in `explore-notes.md` landed on a named stage in `plan.md`, and the plan's own "How
each alignment item is answered" table matched what the code showed.

**Why this is worth recording:** the task specifically asked whether the 9K113's much-better
ranging (per the user's Q3 answer: binoculars > naked eye, 9K113 with stadimeter/magnification/
stabilisation much more accurate though not exact) was *actually delivered*, not just claimed. The
plan said sight range scale 0.5/0.3 was "unchanged" (pre-existing) and binocular 0.7 was "new." I
greped the actual `body-layer/src/perception/optics.py` and `estimation.py` and confirmed: the sight
scales do already exist (`BL-B64`), and — critically — a stale docstring in `optics.py` says
"Nothing selects either of them yet" about `SIGHT_WIDE_OPTIC`/`BINOCULAR_OPTIC`, which reads as if
the sight/binocular ranging is dead code. It is not: that sentence describes a *past* state,
superseded by `plans/binocular-optic/plan.md` and `plans/9k113-sight/plan.md`, both of which wire
the optics into live paths (`optic_policy.py`, `attack_run.py`, `sight_head.py`). Trusting the
docstring literally would have produced a false finding that the 9K113 ranging improvement is
unreachable in practice.

**Lesson:** when a plan claims something is already live/wired-in, grep the actual module rather
than trusting either the plan's "(unchanged)" annotation or a module's own docstring at face value
— docstrings describing "nothing selects this yet" can be historical narration left behind after a
later plan wired the thing in. Check call sites, not just the declaration site.

**Also noted, not as a finding:** the plan's own computed default for the user's stated "could
legitimately be either" case (2.0 vs 2.5 km) lands moderately on one side ("two"), needing roughly a
50% move in the tunable to flip. Not a contradiction — E6 only required adjustability, and the plan
never hard-codes a verdict in tests — but worth surfacing to the user as a one-line note rather than
silently signing off, since "adjustable" and "defaults near the ambiguity's center" are different
claims and only the latter was asked for implicitly by "could legitimately be either."
