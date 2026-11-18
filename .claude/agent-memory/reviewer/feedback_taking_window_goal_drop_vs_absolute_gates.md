---
name: taking-window-goal-drop-vs-absolute-gates
description: a plan's own HOLD-until-held_* reasoning only covers the relative flight-control actions; the absolute-set ones gate on has_controls alone, which is already true during "taking" -- check every action routed through a category's gate, not the category's name
type: feedback
---

BL-16 mode 1 Stage M2 review (`plans/flight-control/review-m2.md`). The implementer's own
`implementation.md` named a real gap ("a goal commanded during `taking` is not applied to the law
at all") but dismissed it as unreachable because "body-layer's own `held_*` HOLD-until-known gates
block a goal action before `active` is confirmed." That reasoning is correct for exactly the
**relative** actions (`turn_heading_relative`/`level_off`, gated by `_flight_control_heading`/
`_flight_control_speed`/`_flight_control_altitude`/`_flight_control_any`, which all check
`held_* is not None`) and silently wrong for the **absolute**-set ones (`axes_set_heading`/
`axes_set_speed`/`axes_set_altitude`), which route through the coarser `_flight_control` gate that
only checks `has_controls` -- already `True` the instant `phase` becomes `"TAKING"`. Found by
reading `rules/gates.py`'s own four gate functions side by side rather than trusting the single
category name ("flight_control") the implementer's prose referred to.

**Why this matters beyond this one case:** a design note that says "gate X blocks this" is a claim
about *every* action routed through that name, and this project splits one conceptual category into
several gate functions precisely because they need different preconditions (`_require_controls`'s
own docstring: "once a single `flight_control` category split into several, each needing this same
base check first"). A reviewer who checks only the gate the author named, rather than every gate an
action in the same family could route through, will miss exactly this kind of split.

**How to apply:** when a plan or implementation note claims "gate/precondition G blocks reaching
this state," grep every action that could produce the state and check *each one's own* gate
function, not just the one example the author walked through. This caught a real, reachable
silent-loss-plus-false-readback bug (the goal is recorded in the wire echo and read back to the
pilot, but never reaches the control law) that no test exercised.

Related: [[feedback_claimed_gate_order_mirroring_needs_checking_against_source]],
[[feedback_decide_by_calling_the_pure_function_directly]].
