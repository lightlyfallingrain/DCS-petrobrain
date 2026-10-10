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

**Occurrence count: 2nd feature.** Filed on `feature/bl11-tick-cost` (five instances in one
branch); recurred on `feature/bl13-crew-query-path` (2026-10-10) with **three more**, each caught by
a Reviewer round rather than by the round that wrote it:

| claim | what the code/data says |
|---|---|
| `relative` resolves "via `belief.attention`'s re-export" | no such re-export; `crew_console.py` imports `perception.gaze`'s public alias directly. Conclusion (same object) survives |
| the legacy `report_*` tokens are "referenced by `LEGACY_F10_TOKENS` ordering" | that tuple holds seventeen `scan_*`/`watch_*`/`cancel_*` entries and **no** `report_*` — it never did. Retention still justified by four other consumers |
| *"'mostly' needs at least one unclassified contact, so the count is never one"* | both halves false and measured: two *classified* contacts of different classes fire the hedge, and a count of one is reachable |

The tell held exactly as predicted: all three cite a consumer, an importer, or a reachable state —
each one grep or one render away. **This is now the single most-repeated finding class in this
repo's reviews**, and it is being caught at Reviewer rather than prevented at Implementer. Worth
raising as an explicit Implementer-stage habit — *when you write "because X", say what would make X
false* — rather than a third branch's worth of rounds.
