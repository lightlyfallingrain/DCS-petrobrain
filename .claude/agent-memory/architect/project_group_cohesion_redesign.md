---
name: group_cohesion_redesign
description: Group cohesion plan (2026-10-01) — op_class is the no-omniscience kind-coherence vocabulary; flat metres vs unit-widths currency choice; per-class EAGER/STRICT backstop policy.
metadata:
  type: project
---

Plan at `plans/group-cohesion-redesign/plan.md`, on `fix/group-undermerging` (tip `e0877e1` at
write time). Resolves two items `plans/group-undermerging/explore-notes.md`/`debug.md` left open.

**Key finding: size-relative spacing already existed.** `belief/groups.py`'s
`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (20.0, unit-widths of `object_model.profile_for`'s
`size_m`) was already the size-relative backstop the explore notes asked the architect to source.
Before concluding a size/dimension property is missing on the contact/object model, check
`belief/groups.py` and `perception/object_model.py` first — both already exist and are mature.

**Kind-coherence answer: `perception.object_model.ObjectTypeProfile.op_class` is the no-omniscience
vocabulary, not DCS group membership.** It's Petrovich's own recognized-type bucket
(`last_class_raw` -> `profile_for`), already used for the size/distinctiveness axes, never a DCS
`object_type` or group id. A hand-authored `AIR_DEFENSE_INSTALLATION_CLASSES` set over existing
`op_class` values (`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`/`OP_SPAAG`/`OP_ZU23`) relaxes the backstop for a
same-family pair, composed via the same `min(relative, backstop)` shape the module already uses —
it never replaces the relative/density test, so it doesn't become an unconditional merge rule.

**Currency choice matters and was explicit: flat metres for installation pairs, not unit-widths.**
Unit-widths is right when spacing scales with the thing's own size (convoy/formation); it's wrong
for an installation, whose footprint is a doctrine property unrelated to any one component's
physical size (confirmed against real debug-pass ground truth: S-300 components 236-838m apart,
no vehicle-size multiple gets there honestly). Watch for this distinction recurring — any future
"relate spacing to size" design should ask explicitly which currency the thing being grouped
actually varies with, rather than defaulting to whichever currency the adjacent code already uses.

**Asymmetric error tolerance: a per-op_class enum (`STRICT`/`EAGER`), default-plus-exception,** same
shape as `object_model._OP_CLASS_DISTINCTIVENESS`. Only `OP_INFANTRY` gets `EAGER` (no backstop at
all) per the user's own explicit, narrow statement — resisted the temptation to extend "eager" to
other low-threat classes since that would be the architect inventing a judgment, not implementing
one. See [[feedback_scope_only_whats_actually_said]] if that memory exists, else: a user statement
about one specific class is not a license to generalize the policy to a category.

**Revision (second pass, same day): `op_class` is a threat-bucket vocabulary, not a system-topology
one — don't key an installation/kind-coherence rule on it alone.** `OP_SRSAM` mixes a genuine
multi-component fixed site (`"s-125"`, SA-3: separate radar + launcher revetments) with four
single-vehicle systems (`"osa"` SA-8, `"strela-10"` SA-13, `"strela-1"` SA-9, `"tor 9a331"`/
`"chap_torm2"` SA-15, each its own radar+launcher on one vehicle). The first draft's
`AIR_DEFENSE_INSTALLATION_CLASSES: frozenset[str]` (an `op_class`-keyed set) would have merged an
Osa and an S-125 launcher 400m apart as "one installation" — found only by re-reading
`object_model.py`'s actual keyword table line-by-line, not by trusting the op_class names. Fix: a
second, orthogonal `installation_component: bool` field, authored per keyword entry, separate from
`op_class`. When a rule needs "is this a site-component" use the new field; when it needs "is this
air-defence at all" (e.g. a disclosure rule's "more air defence is always news"), `op_class` bucket
membership is still right — the lesson is which question is being asked, not which field to avoid.
S-75/SA-2 also has no keyword entry at all (falls back to `DEFAULT_OP_CLASS`) — a pre-existing gap,
not something to assume covered.

**Delta re-report: the redundancy is narrower than "any change re-speaks everything."**
`CONTACT_CLASSIFICATION_CHANGED` already fires per grouped member individually (confirmed from
`belief/callouts.py`'s own docstring — only `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are filtered for
grouped contacts). The actual noise is the group's *own* line re-speaking in full whenever the
whole-text diff changes for any reason, duplicating what an individual event already said. Fix:
move the trigger from whole-text-diff to a 3-field comparison on `Group` (`last_spoken_member_
contact_ids`, `last_spoken_leading_contact_id`, `last_spoken_differentiated`), with "full" reserved
for genuinely new framing (new group, leader change, first differentiation) and "delta" or "silent"
otherwise. Before assuming a user's "too much repetition" complaint needs a new diffing mechanism,
check what's already individually event-sourced — the fix may be narrowing an over-broad trigger,
not building a new comparator.
