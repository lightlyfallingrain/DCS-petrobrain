---
name: last-alt-m-is-the-ownship-altitude
description: Contact.last_alt_m is the OWNSHIP's altitude at the last look, not the target's ground elevation — so any elevation angle, depression or vertical-separation derivation read off Contact.last_position is garbage; use geometry.elevation_at instead
metadata:
  type: project
---

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

**How to apply.** Any plan needing the target's altitude — elevation angle, depression, vertical
separation between two contacts, slant-vs-ground range, loft geometry — must take it from
`perception.geometry.elevation_at(conn, theatre, x, z)` (terrain MSL at a point, `None` when
unavailable) against `contact.position.x/z`, with `conn`/`theatre` off `EnrichmentContext`. Cache on
the quantised `(x, z)` as `WorldEnrichmentCache` already does; it changes only when the target moves.
**Never route it through `describe_contact`/`_report_scope`** — `BL-B49` measured 63.25 ms/contact of
enrichment that path computes and discards.

Two honesty constraints that come with it: `elevation_at` returns `None` where the grid has no
coverage, and the coarse grid has been measured placing a real unit "underground"
(`debugger/project_terrain_los_grid_error_permanent_miss`). Decide the fail-open/fail-closed
direction explicitly — in `BL-14` the vertical half fails open, so a missing grid omits a word and
can never withhold *"lined up"*.

`enrichment.py`'s `project_terrain_aware` is a *different* thing: it re-projects bearing+range to a
terrain-aware ground point for world-model landmark lookup. It does not write `last_alt_m` back, and
it is the expensive iterative path. For "elevation at a position I already know", `elevation_at` is
the right call.

See also [[project_three_projections_of_a_group_roster]] — same lesson shape: check the field's
actual provenance and resolver before building on its name.
