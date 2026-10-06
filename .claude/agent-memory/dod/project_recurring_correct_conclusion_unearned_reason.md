---
name: recurring-correct-conclusion-unearned-reason
description: This repo's reviews keep approving a correct conclusion carrying a reason the code/data does not support; five rounds on one branch, and the prose is what later misleads
metadata:
  type: project
---

**The dominant defect class on `feature/bl11-tick-cost` (2026-10-06) was not wrong code — it was
right code with a wrong explanation attached.** The branch's own implementation log named it by
round 5: *"Fifth round, fifth correct-conclusion-wrong-reason."* Five instances, every one approved
by a reviewer before being caught by the next round or by the performance pass:

| round | conclusion (correct) | reason (wrong) |
|---|---|---|
| 1 | keep the `None`-omission exemption for the join keys | "consumers distinguish omitted from null" — none do; all read via `.get` with a truthiness guard |
| 2 | keep `_cohesive`/`_resolvable` | "they are the reference implementation" — the very fix being applied stopped the reference using them, leaving both uncalled |
| 3 | the equivalence file shares only tuning constants | it shared more than that |
| 4 | parametrising over `.`, `/`, `""` is adequate | "every other spelling normalises onto one of them" — `Path("//")` is a *distinct* path; the real reason is that behaviour depends only on the final component being empty |
| 5 (perf pass) | Stage 2's speedup is real | "the ratio rises with pair count, so a flight sees ~8×" — it **saturates at 5.1×** from ~2,500 pairs and is still 5.1× at 169,071 |

**Why this is a DoD-stage concern and not pedantry.** Code is held by tests; prose is held by
nothing. Every one of these would have survived indefinitely, and two had already done measurable
damage before this branch: the stale "5 Hz" docstrings produced `BL-B30`'s entire wrong premise
(a "7× slow loop" that was ~5× a constant nobody had read) *and* a wrong budget figure in an agent's
own memory. The round-5 case is the sharpest: the performance pass's single required change was a
**docstring**, on the grounds that the next person reconciling a flight measurement against the plan
would otherwise re-derive it from scratch — which is exactly what that pass had just had to do.

**How to apply.** When a review approves something, read the *reason* as a separate claim from the
conclusion and ask what would falsify it. The tell is a reason that cites consumers, callers,
scaling behaviour, or normalisation — i.e. something checkable with one grep or one measurement that
nobody ran. Three of the five above were one grep away.

**A dangerous corollary for this role specifically:** a correct number with an unearned reason reads
exactly like a verified one in an acceptance card. This is the same failure as naming a command that
was never executed — see [[feedback_verify_roadmap_prose_claims]], which is the narrower
grep-the-"filed in X"-claims version of this pattern.

**Occurrence count: 1st time filed as a pattern, but five instances within one branch**, which is
why it is filed now rather than waiting for a second feature. If it appears on another branch,
consider raising it at Architect/Reviewer stage as an explicit "state what would falsify this
reason" step rather than catching it round by round.
