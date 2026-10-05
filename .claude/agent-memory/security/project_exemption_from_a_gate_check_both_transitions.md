---
name: exemption-from-a-gate-check-both-transitions
description: An exemption keyed on event *kind* admits every transition of that kind; check each one against the exemption's own stated bar, not just the motivating one.
metadata:
  type: project
---

When a no-omniscience (or any disclosure) gate carries an exemption set keyed on `EventKind`,
the exemption admits **every** transition that kind can carry — not only the one that motivated
it. Check each direction separately against the bar the exemption writes down for itself.

**Why:** on `fix/callout-observability-gate` (2026-10-06), `_OBSERVABILITY_EXEMPT_KINDS` exempted
`CONTACT_ENGAGEMENT_CHANGED` from the callout observability gate, justified by *"the cost of
silence is a missed threat cue the pilot needs in order to evade"*. That reaches
`engaged=True` (`"Danger, ZU-23-3, six o'clock, 1.0 km."`) and does not reach `engaged=False`
(`"Safe from …"`), which is a comfort rather than a threat cue — yet both passed, because the
gate tested `event.kind`. The docstring's own rule said *"either property alone admits something
that should stay gated"*, and the "safe" direction was admitted on property (2) alone. Nobody
noticed through three review rounds and a DoD, because every test and every piece of prose was
written about the motivating direction.

**How to apply:** at any `event.kind in _SOME_EXEMPT_SET` check, enumerate the kind's payload
states (`engaged` True/False, `previous_*` vs current, closing vs opening) and ask the
exemption's stated bar of each. If one fails, the fix is a per-transition condition at the gate,
not a wider docstring. The same reasoning applies in reverse to a *gating* set: adding a kind to
the gated set is the safe direction, adding one to the exempt set is silent — so an exempt set
deserves a test asserting its exact membership.

Related: the disclosure analysis itself is in
[[project_callout_observability_gate_exemption_disclosure_traced]].
