---
name: project-bl16-p3p4-snapshot-and-midflight-direction
description: BL-16 P3+P4 (CBTM align/break/recovery, 2026-11-18) traced CONCERNS -- a settled open assumption (re-snapshot on second align-for-launch) had no mechanism, and a standing direction landed mid-check overruling the plan's own U11
metadata:
  type: project
---

Two independent lessons from one pass, both worth repeating.

**1. A goal check's open assumption can be answered by the user, restated correctly in the plan's
prose, and still have no code path that implements it.** The goal check named the exact failure
mode up front: "serves the why: re-enter `launch_aligned` and keep the *first* pre-align snapshot
... would not: re-snapshotting a recovery's half-restored altitude and speed." The user answered
directly ("command align for launch" — a fresh one, not ignored). But `cbtm_align_for_launch()`'s
snapshot capture is unconditional ("current goal/held values"), with no branch for
`align_phase == "recovering"` — so a second align-for-launch mid-recovery does exactly the "would
not" case, silently. **The tell:** the goal check spelled out a "would not" in enough detail to be
checkable against the plan's actual mechanism (not just its prose elsewhere), and nothing in the
plan's Co-moving table or action-body text carries a conditional for that specific state. Check
every "would not" in a goal check's open assumptions against the plan's state machine, not just
against whether the topic is mentioned somewhere.

**2. A standing direction can land between Architect's commit and the Plan Aligner's check, same
day, and directly overrule one of that plan's own `U<n>` recommendations.** `1659a54d` ("mode 1
carries mode 2's command set except 9K113 align") landed after `959af986` (Architect) but before
this check ran, and flatly contradicts U11 ("recommend: not in this batch" for mode-1 break-away).
This is not a flaw in the Architect pass — U11 was reasonable against what was known when written.
**How to apply:** when a coordinator message arrives mid-task citing a new committed decision, `git
merge --ff-only` it into the same check rather than treating it as out of scope, then re-read every
`U<n>`/Decision in the plan under review for a contradiction, not just the newest one named —
here it was exactly one (U11), but the check should scan all of them whenever a cross-cutting
"all mode-2 commands also in mode-1" rule lands, because any mode-2-only action in the plan is a
candidate.

See also [[project_bl16_mode1_recut_u6_reopens_settled_e9]] (a different shape: a `U<n>`
reopening something already settled, rather than a later direction overruling a `U<n>`) and
[[project_bl16_mode1_u5_u10_amendment_clean]] (the positive case: an answer that legitimately
narrows an old E rather than silently dropping it — contrast with how E-P16/E-P20 here *did*
narrow cleanly while E-P22/the snapshot case did not trace at all).
