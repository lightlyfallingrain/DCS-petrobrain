---
name: shared-gate-precondition-claim-vs-per-handler-checks
description: when a plan promotes several handlers' individual precondition checks into one shared gate/state field and claims "they all already check the same thing", verify that against each handler's actual existing check before approving -- BL-17 Stage 3b's CrewState.settling (held_heading-only) was claimed to be "the same proxy every flight handler already checks today" and is false for most of them
metadata:
  type: feedback
---

BL-17 Stage 3b (`plans/speech-rules/plan.md` D16) introduced `CrewState.settling = has_controls and
held_heading is None` as the one shared `flight_control` category gate's `HOLD` condition, with the
plan's own text (line 307) justifying it as "the takeover-settle window, the same proxy every
flight handler already checks today." Stage 4's plan (not yet built) explicitly plans to delete
every individual handler's own `held_* is None -> NOT_READY` branch once this shared gate ships,
on the premise the gate already guarantees it.

**Checked against the actual shipped handlers in `crew_console.py` rather than taking the claim at
face value, and it is false for most of them:**
- `_handle_speed_step` checks `held_speed is None`.
- `_handle_altitude_step`/`_handle_hold_altitude` check `held_altitude is None`.
- `_handle_level_flight` checks "all three of held_heading/held_altitude/held_speed are None" (a
  weaker, OR-shaped condition, not any single field).
- `_handle_set_speed`/`_handle_set_altitude`/`_handle_turn_heading` (absolute forms) have **no**
  precondition check at all.
- Only `increment_ai_heading` (the one rule actually ported in this stage) and `_handle_level_off`
  use `held_heading` as their own gate.

Only the rule this stage actually migrated (`turn_heading_relative`, via `increment_ai_heading`)
happens to match the shared gate's chosen field, so Stage 3b's own shipped code is correct. But if
a later stage removes the other handlers' own checks on the strength of this claim, the result is
a real bug either direction: gated `HOLD` on an irrelevant field (needless delay, possible false
timeout) or gated `PASS` while the handler's own needed field is still `None` (the deleted check
was the only thing stopping it reaching arithmetic). The four `held_*` fields are independently
optional (parsed per-field from one telemetry sample, `ai_pilot_wheel.py`), which is presumably why
the original per-handler authors each checked their own field rather than sharing one.

**How to apply.** Whenever a plan promotes several existing handlers' own precondition checks into
one shared gate/state field and asserts they were "already checking the same thing" (a
simplification claim, not a decision the user made) — read each handler's actual existing check
before approving the shared field's definition, not just the one or two handlers the current stage
actually touches. This is the same habit as `project_bl17_test_list_claims_a_fix_its_own_exclusion_
rules_out.md` (grep the shipped parser instead of trusting the plan's prose) applied to a different
shape: there the plan over-claimed what a *mechanism* covered; here it over-claims that several
*existing checks* were already equivalent. Catch it early, while the shared primitive is freshly
built and still cheap to widen (e.g. one field per command family, or an OR-shaped "nothing known
yet" condition like `_handle_level_flight` already uses) — not at the later stage's own Reviewer
pass, after handlers have already had their own checks deleted on the strength of the claim.
