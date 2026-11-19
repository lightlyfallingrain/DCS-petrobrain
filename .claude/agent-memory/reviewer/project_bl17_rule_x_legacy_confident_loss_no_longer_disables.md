---
name: bl17-rule-x-legacy-confident-loss-no-longer-disables
description: audio-adapter rule-collision check now treats rule x rule and rule x legacy confident losses differently (2026-11-19) -- check which pass a future change touches
metadata:
  type: project
---

`audio-adapter/src/rule_patterns.py`'s `_is_genuine_collision` gained a keyword-only
`confident_loss_disables` param (`fix/rule-collision-misheard`, 763d4288, reviewed/approved
2026-11-19). **The two collision passes now disagree on purpose:**

- **Rule x rule** (`_rules_collide`) keeps the original behaviour: a confident loss on a
  perturbed sample (`other_ratio` beats `own_ratio` by >= `SEPARATION_MIN`) still disables both
  rules. This is U10's actual case ("two rules claiming the same wording").
- **Rule x legacy** (`_collides_with_legacy`) no longer disables on a confident loss -- only an
  exact tie on the clean wording (`own_ratio == other_ratio == 1.0`) still rejects. Reason,
  verified independently against `command_matcher.match_transcript`'s rule/legacy merge
  (`src/command_matcher.py:1166-1182`): the higher-ratio side always wins regardless of whether a
  rule exists, so disabling the rule for a mis-hearing it cannot affect only cost a working
  command on the clean wording (measured: `cbtm_align`/`cbtm_break` from
  `body-layer/config/rules/flight.lua`, both silently rejected before this fix).

**Why this matters for review**: `plans/speech-rules/plan.md`'s D9 "Recalibrated 2026-11-17"
paragraph still describes one shared criterion for both passes -- it is now stale for rule x
legacy and nobody has gone back to amend it (flagged as an optional refinement, not required, in
`plans/rule-collision-misheard/review.md`, since this fix had no plan directory of its own). If a
later change touches `_is_genuine_collision` or either collision pass again, check which of the
two call sites it's meant to affect -- the asymmetry is easy to miss on a skim because both passes
call the same shared function, and a change that "fixes" one pass's docstring language without
reading the other's call site could silently re-couple them or leave the plan text pointing at
behaviour neither pass has any more.

See also [[project_bl17_collision_check_recalibration_exact_tie_rule]] (implementer's memory,
2026-11-17 recalibration this one builds on) for the exact-tie clause's own history.
