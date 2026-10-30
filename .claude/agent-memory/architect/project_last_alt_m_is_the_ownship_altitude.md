---
name: last-alt-m-is-the-ownship-altitude
description: Contact.last_alt_m is the OWNSHIP's altitude at the last look, not the target's ground elevation, for AIR contacts only (narrowed by BL-B104, 2026-10-30) — any elevation angle or vertical-separation derivation read off Contact.last_position is garbage for an air contact; a surface contact (Contact.on_surface) now carries its own believed ground height in last_alt_m
metadata:
  type: project
---

> **Narrowed by `BL-B104` (2026-10-30,
> `plans/bl-b104-ground-contacts-on-ground/plan.md`).** This trap now applies to **air contacts
> only**. A surface contact (`Contact.on_surface`) has its own believed height written into
> `last_alt_m` from the look (the unit's own ground height, read from the wire's category/subcategory
> fields), and `attack_run.remembered_target_alt_m` returns it directly for a surface contact. Air
> contacts keep exactly the ownship-altitude behaviour this memory describes below — do not assume
> the narrowing applies to them.

**Found by reading, during the `BL-14` attack-run plan, 2026-10-14.** `Contact.last_position` is a
property, `GeoPosition(x=position.x, z=position.z, alt_m=self.last_alt_m)`, and `last_alt_m` is set
at `contacts.py:594` from `implied_position(percept)` — the flat projection
(`geometry.project_from_bearing_range`), whose altitude convention is literally
`percept.ownship_at_observation.alt_m`. The field's own docstring says it is **not fused** ("no
altitude uncertainty model exists").

**So `contact.last_position.alt_m` is the aircraft's own altitude when it last looked.** It is
*correct* for what it is used for today — the cockpit mask's `body_relative_direction` call needs an
observer-relative direction and both sides share the same altitude convention, so the error cancels.

**Why: it is wrong the moment anything wants a real vertical angle.** A boresight elevation computed
from it reports how much the aircraft has climbed or descended since the last look, not where the
target is. `BL-14`'s *"higher"/"lower"* word would have been pure noise, and the defect would have
looked like a tuning problem rather than a wrong input.

**How to apply — CORRECTED by the user, 2026-10-14** (`docs/acceptance/2026-10-14-attack-run-
guidance-direction.md` §17): *"No world elevation necessary since unit data has elevation."*

**The target's own altitude arrives with the unit.** `aircraft-layer/src/schema/world_objects.py`
carries a per-object `altitude_m` (MSL metres, `alt_m` on the wire), and `OwnshipState.alt_m`'s
docstring says MSL is the right frame for comparing against a contact's own altitude. Inside
body-layer it survives as far as `clustering.ClusterCandidate.alt_m` and is then **dropped**:
`Cluster` has no altitude field and `naked_eye_source._build_observation` substitutes
`ownship_state.alt_m` into the centroid. So the fix for any vertical derivation is to carry the
unit's own altitude through perception, not to query the world model.

> **Superseded.** This read: *take it from `perception.geometry.elevation_at(conn, theatre, x, z)`
> against `contact.position.x/z`, cached on the quantised `(x, z)`.* Two things wrong with it. (1)
> It is unnecessary — the unit's altitude is already in the feed. (2) It was **reinventing a cache
> that exists**: `belief/enrichment.py`'s `WorldEnrichmentCache`/`_terrain_aware_world_position`
> already caches a terrain-aware target position on a quantised key, and `relative_geometry` already
> computes `relative_alt_m` from it. Writing a second one into the same module would have been the
> duplication the no-new-abstractions rule is about.

What the superseded remedy got *right* and is worth keeping: whatever the source, decide the
fail-open/fail-closed direction explicitly (in `BL-14` the vertical half fails open — an absent
input omits a word and can never withhold *"lined up"*), and **never route an altitude lookup
through `describe_contact`/`_report_scope`** (`BL-B49` measured 63.25 ms/contact of enrichment that
path computes and discards).

**The transferable lesson, which is bigger than the altitude:** before planning a world-model query
to recover a quantity, check whether the quantity is already on the wire and merely discarded
downstream. Two layers of this codebase drop real data on the floor for good local reasons
(`Cluster` has no altitude because clustering did not need one), and that absence reads as "the data
does not exist" to anyone reading from the belief side.

See also [[project_three_projections_of_a_group_roster]] — same lesson shape: check the field's
actual provenance and resolver before building on its name.
