---
name: bl16-lv2-rework-bank-easing-exception
description: LV-2 rework (2026-11-28) plan check — bank-easing reserved for an exception path can't deliver "slower turn" the expectation names as normal
metadata:
  type: project
---

BL-16 LV-2 rework amendment (break as attitude manoeuvre, `plans/flight-lift-vector/plan.md` "LV-2
rework amendment (2026-11-28)") held bank fixed at 30° "full stop... not scaled by margin," and
reserved the only bank-easing mechanism (`phi_scale`/`effective_shortfall`) for a case its own
text calls "the exception path, not the common one." The goal check's BE6 ("approaching the
floor... the turn finishes more slowly") requires the turn's rate to actually drop near the
floor — but turn rate is `g·tanφ/V`, so with bank fixed and speed held (BE2), rate cannot change;
only the plan's normal path (collective fading back to height-tracking) moved, which arrests sink
without slowing the turn. Caught by doing the arithmetic on the goal check's own rate formula
against the plan's "not scaled by margin" sentence, not by reading the prose alone.

**Why:** the plan's own words ("most breaks... never reach this," "the exception path") were the
tell — a mechanism explicitly described as rare cannot be the normal mechanism said to deliver an
expectation.

**How to apply:** when a plan assigns an expectation to a stage, check whether that stage's own
prose calls itself the common path or a rare/exception path — a stage can be "met" on paper while
quietly being the fallback, not the default. For a turn-rate expectation specifically, check it
against bank and speed holding constant: if neither changes, rate cannot change either, however
much a *different* channel (collective) visibly reacts. Related: [[project_bl16_p3p4_snapshot_and_midflight_direction]], [[project_bl16_mode1_recut_u6_reopens_settled_e9]].
