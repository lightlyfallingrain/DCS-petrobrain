---
name: resolution-vs-salience-split
description: The naked-eye presence threshold was split into resolution vs salience (2026-09-22 group-detectability plan), and clustering.py's floor (A) is silently coupled to whatever the loosest admission threshold is.
metadata:
  type: project
---

`perception/visibility.py`'s single presence threshold conflated two different questions, and the
2026-09-22 group-detectability plan (`plans/group-detectability/plan.md`) splits them:
**resolution** (can the eye register a mark at all — `RESOLUTION_ANGULAR_RADIUS_RAD`, ~0.0013,
anchored to dots seen at 5.44 km) versus **salience** (would a lone mark be noticed while scanning
— the existing `LOWRES_ANGULAR_RADIUS_RAD`, to be refitted to single-unit truth ~0.0024). Group
membership admits a candidate at the resolution threshold instead of the salience one.

**Why:** the pilot's "detection" of a twelve-unit group at 4.00 km and the model's 2333 m per-unit
figure looked like a 2x calibration error. It was not — against *single-unit* truth (2.8-3.1 km) the
model is short by only 1.2-1.3x. The apparent 2x was the group, and there was no term for it.

**How to apply:**
- Any future calibration ask about "presence being wrong" must first establish which of the two
  questions the observation answers. A lone-unit range and a group range are not the same
  measurement and must never be fitted to the same constant.
- **`clustering._separable`'s floor (A) is coupled to the loosest admission threshold the channel
  can use.** Its slack-by-construction proof assumes admission happens at the same constant (A)
  tests against. Any change that lets a candidate in below that constant — a group term, a new
  optic, a conditions multiplier — silently turns (A) into a binding constraint that merges
  genuinely separable contacts. This has now bitten once in design (caught before implementation);
  check it whenever an admission threshold moves. Same class of hazard as slice 2A's
  hardcoded-`BINOCULAR_RANGE_MULTIPLIER` fix.
- The one dataset behind group detectability is a single twelve-unit 200 m line. Count curves,
  extent curves and pattern/regularity terms are all n=1 inventions; the plan deliberately ships a
  binary cohesion+mass predicate instead. Resist requests to make it a curve without new data.

Related: [[project_cones_slice2_design]], [[project_bl2_contact_memory_design]].
