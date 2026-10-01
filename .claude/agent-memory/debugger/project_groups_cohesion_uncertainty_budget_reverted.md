---
name: groups-cohesion-uncertainty-budget-reverted
description: budgeting Contact.position.radius_m() into belief.groups' pairwise cohesion test over-merges at close range; a single naked-eye look already carries ~300m RMS uncertainty even at 500m
metadata:
  type: project
---

Do not budget `Contact.position.radius_m()` (RMS position uncertainty) into
`belief.groups._cluster_contacts`'s pairwise gap test as a flat subtraction
(`effective_gap = max(0, raw_gap - (unc_i + unc_j))`) without also revisiting
`belief.position_belief`'s single-look covariance calibration first.

**Why it looked right:** a real sortie showed two members of one SAM site reading as noisy,
hundreds-of-metres-apart believed positions for the first ~15s after detection (position
uncertainty 400-900m against a true ~14-157m site footprint), correlating with the user's report
that "grouping works better the closer I get" (uncertainty shrinks as more looks accumulate).

**Why it's wrong as a fix:** a single naked-eye look's fused-position covariance is already
~300m RMS at just 500m range in this codebase's `position_belief` model (confirmed by printing
`contact.position.radius_m()` after one `ContactStore.tick`). Budgeting that fully regresses
`tests/test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven` -- two infantry
genuinely 260m apart at 500m range (deliberately pinned to stay ungrouped, 36m backstop) now
merge, because 600m of combined budget swallows a 260m gap.

**What actually mattered:** replaying the real sortie trace with the *unmodified* algorithm showed
it already converges to the correct multi-member group once enough looks accumulate (confirmed
against the real spoken output). The "better closer" symptom did not need a mechanism fix here --
see [[group-disclosure-range-retrigger]] for the defect that actually explained the user's
complaint once he supplied real spoken-line evidence.

If this needs revisiting later: either fix it at the position_belief calibration layer (a single
look's covariance is plausibly too loose to begin with) or use hysteresis that favours an
*already-formed* group's continuity rather than loosening first-contact formation, not a flat
subtraction applied uniformly to every pairwise test.
