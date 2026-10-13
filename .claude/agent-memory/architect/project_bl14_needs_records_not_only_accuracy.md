---
name: bl14-needs-records-not-only-accuracy
description: BL-14 attack run needs per-unit positions; bounding BL-12 Stage 3's fold fixes their accuracy (40 m, inside the perception channel's own bearing sigma) but cannot fix their existence — two real units have no contact at all, before or after.
metadata:
  type: project
---

User direction, 2026-10-13: *"Attack run does need individual unit positions. That is the whole
premise of attack run."* Position accuracy is a **first-class acceptance criterion**, not a
confirming check.

Measured against incident 2 scored over **all six real units**, not only the four with contacts
(`plans/bounded-fold-displacement/scratchpad/probe_o2_accuracy.py`):

| | per-unit position error | records |
|---|---|---|
| fold, unbounded (merged today) | 72–95 m (4.1–5.3° at ~1 km) | 4 contacts / 6 units, 2 invisible |
| fold, bounded at `plausible_speed × elapsed` | **40 m (2.29°)** | 4 / 6, **still 2 invisible** |
| no fold at all (reverses `D5` at contact grain) | 0.0 m, every unit visible | **18 / 6**; and **82 / 2** in a moving-pair scene |

**The finding, which is the transferable part:** the fold's *magnitude* is what makes a held
position wrong; the fold's *existence* is what makes a unit absent. Different defects, different
fixes. 40 m at 1 km is **below the naked-eye channel's own `BEARING_SIGMA_DEG = 3.0`**, so after
the bound the fold is no longer the limiting error in aiming — that is a real and checkable
acceptance bar, and the right one to use again. But completeness is untouched.

**Why it matters beyond that plan:** `BL-12` Stage 3's accepted failure modes (unreliable
`contributing_observation_ids`/`sighting_spans` at within-group grain, undercount replacing
overcount) were accepted **on the explicit reasoning that the group-level answer stays correct**.
BL-14 changes the product that reasoning was about, so the trade needs re-deciding — and
*reversing* D5 is not the answer, because 82 contacts for 2 real units is worse for the pilot than
an undercount. The missing third option is resolving a within-group ambiguity by **splitting**
(found the member and keep the group's cardinality honest) rather than folding or founding freely.

**How to apply:** do not plan BL-14 assuming member positions are available per unit. Settle the
fold-versus-split question first; it is decision 1 of
`plans/bounded-fold-displacement/plan.md` §12. Related:
[[project_fold_displacement_never_retires]], [[project_group_contact_identity_design]].
