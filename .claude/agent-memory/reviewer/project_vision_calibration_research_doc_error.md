---
name: vision-calibration-research-doc-error
description: Pass 1 vision-range-calibration reviewed with one required fix — a "confirmed live" claim in the research doc that reproduction disproved.
metadata:
  type: project
---

`plans/vision-range-calibration/plan.md` Pass 1 (branch `feature/vision-range-calibration`,
`0c0b03a..af2f58b`) was a no-behaviour-change fixture/test/research-doc pass, reviewed and
approved with one required fix, 2026-09-17.

The implementer's research doc (`body-layer/research/2026-09-17-vision-range-calibration.md`)
stated `profile_for("BMD1")` "confirmed live" resolves correctly to `OP_ARMORED`/7.0 — this was
false. Direct reproduction (`.venv/bin/python -c "... object_model.profile_for('BMD1')"`) showed
it actually falls to the `5.0/OP_GROUPSOMETHING` default, the identical failure mode the same doc
correctly diagnosed for `"T-62"` (F10-label lookup misses the raw-type-keyed reporting-name table:
`reporting_name_for("BMD1")` is `None` because the raw key is hyphenated `"BMD-1"`). The doc's own
two-pass description of `profile_for` was accurate — only the specific claimed test result for
this one unit was wrong.

**Why this matters beyond this one milestone**: this project's research docs
(`body-layer/research/`, `world-model/research/`, `aircraft-layer/research/`) are meant to be the
durable, trusted record of claims verified against the actual code/DCS install — the project
invariant is "don't encode unverified claims as fact, verify and record." A "confirmed live"
claim that reproduction disproves undermines that record for whoever reads it next (here: a
future Pass 2 planner deciding whether BMD1 needs an `object_model.py` keyword-table fix). This
didn't affect test/fixture correctness (the tests use the fixture's recorded `size_m` ground
truth, not `profile_for`'s output), so it stayed a documentation-only required fix, not a code
reopen — see [[feedback_verify_mypy_cwd_claims_by_reproduction]] for the same "reproduce, don't
just re-read the log" discipline applied to a different claim type.

**Pattern for future reviews**: when a research doc claims "confirmed live" / "verified" for a
specific input, re-run that exact call yourself rather than trusting the doc's stated output —
even when the doc's *general* mechanism description (the two-pass lookup logic, in this case) is
itself correct and well-reasoned. Getting the mechanism right doesn't guarantee the specific
claimed output was actually checked against it correctly.
