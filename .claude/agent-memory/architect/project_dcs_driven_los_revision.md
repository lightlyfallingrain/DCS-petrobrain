---
name: dcs-driven-los-revision
description: Revising dcs-driven-los plan after 3 user corrections — reciprocity argument for belief carrying LOS, and the movement-detection endpoint-separation precedent that resolves an apparent conflict between corrections.
metadata:
  type: project
---

`plans/dcs-driven-los/plan.md` was revised 2026-09-29 to fold three appended user corrections into
one coherent design (collector-side, true-to-true LOS; belief carries a last-known observed
property instead of calling anything). Two findings worth keeping:

1. **LOS is a symmetric ray test, so a fresh naked-eye admission is proof of mutual visibility.**
   `check_visibility` gate 4 only admits a candidate when LOS is clear, so any admitted observation
   already proves the ray was clear in both directions. This is why "belief stops calling a
   function" is safe rather than merely a delegation with a gap: a currently-observed contact
   carries a *true* LOS fact for free; a stale one decays to unknown, which the existing
   `LOS_MASK_CONFIRM_S` fail-open logic (`belief/decay.py`) already treats conservatively. Staleness
   for this kind of fast, transient carried fact should reuse `decay.OBSERVED_WINDOW_S` (the
   "currently being perceived" band) rather than inventing a sixth half-life constant — check
   `decay.py`'s existing constants before proposing a new one, per the standing "check existing
   half-life/expiry constants" rule; this case did have one waiting (indirectly, via the window)
   even though it wasn't a half-life per se.

2. **The user's phrase "bake X into unit data transmitted from collector" does not necessarily mean
   merge it into an existing endpoint's JSON payload — check for an existing endpoint-separation
   precedent before assuming a merge is wanted.** `plans/movement-detection/plan.md` Decision 2
   (documented in `aircraft-layer/src/api/server.py`'s own module docstring) already rejected
   merging `/unit_velocity/latest` into `/world_objects/latest` for exactly this shape of feed (a
   1 Hz Hook-script bridge value vs. a 5 Hz Export.lua-native one) — merging would either stall one
   feed on the other or destroy per-feed sim-clock provenance. LOS is the same shape (1 Hz
   Hook-script value joining onto a 5 Hz feed), so the same precedent applies: keep it a sibling
   endpoint (`/line_of_sight/latest`), joined client-side by `unit_name` exactly like velocity, and
   satisfy "baked into unit data" at the point where the *consumer* (`naked_eye_source.py`) has
   already joined it onto `WorldObjectCandidate` — not at the wire level. Worth generalizing: when a
   user's plain-language framing of "just attach this to X" seems to imply merging two feeds/
   endpoints, grep for whether this project already has a documented reason not to, before writing
   the plan around the literal reading.
