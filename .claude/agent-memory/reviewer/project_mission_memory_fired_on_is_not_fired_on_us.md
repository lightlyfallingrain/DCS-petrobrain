---
name: mission-memory-fired-on-is-not-fired-on-us
description: body-layer's mission_memory "fired_on" entry kind means "a shooter was observed firing at anyone", not "fired on ownship" -- its own targets_ownship payload field disambiguates; don't assume a name like "fired_on" implies the narrower reading without checking plans/bl8-mission-memory/plan.md Decision 2/3 directly
metadata:
  type: project
---

When reviewing `fix/taking-fire-visible-shooter`'s second half (2026-10-20), the dispatch itself
flagged a plausible defect: `mission_memory/admission.py::_write_fired_on_entries` writes one
`fired_on` entry per `CONTACT_FIRING_SEEN` event regardless of `targets_ownship`, and the
implementer claimed this "already covers the new case for free." The suspicion was that `fired_on`
as a name implies "fired on us," so writing one for a unit firing at someone else would be a false
entry.

**Checked against the plan directly, not the implementer's account**: `plans/bl8-mission-memory/
plan.md` Decision 2's schema table gives `fired_on`'s payload as `{shooter_seq, shooter_ref,
targets_ownship: bool}` and Decision 3's admission-rule table says it writes on "a
`CONTACT_FIRING_SEEN` event, suppressed per shooter" -- kind-generic, no `targets_ownship`
condition anywhere in the rule. The payload's own boolean field exists specifically so one entry
kind can represent both cases. So `fired_on` was designed from the start to mean "this shooter was
observed firing" (at anyone), not "fired on ownship specifically" -- the name is a bit
misleading on its own, but the schema disambiguates it correctly, and no defect exists here.

**How to apply**: when a mission-memory (or any named-entry-kind) semantics question comes up,
read that kind's own schema/admission-rule entry in `plans/bl8-mission-memory/plan.md` (Decisions
2 and 3) rather than inferring meaning from the kind's string name or trusting the implementer's
summary of it. A field like `targets_ownship: bool` sitting inside a payload is often there
*because* the entry kind is intentionally broader than its name suggests.
