---
name: group-contact-identity-design
description: Group-level re-identification plan (2026-10-06) — the churn is in GroupStore.reconcile not ingest; three of four asked-for mechanisms already existed; D9's road corridor is a world-model milestone in disguise
metadata:
  type: project
---

The 2026-10-06 `plans/group-contact-identity/plan.md` pass, and the four findings that changed
the design away from what the task's framing implied.

**Why:** the explore conversation's decisions (D4/D5 of `plans/post-review-fixes/explore-notes.md`)
read as "change `ContactStore.ingest`". Reading the code says the dominant mechanism is one level
up, and that three of the mechanisms D3/D4/D8 appear to request are already in the tree.

**How to apply:** before planning anything in body-layer's belief layer, check these four first.

1. **Contact churn becomes *group* churn in `GroupStore.reconcile`, not in `ingest`.**
   `reconcile` (`belief/groups.py:553`) matches clusters to persisted groups by **majority
   member-contact-id overlap** and then *replaces the whole store* — "a persisted group with no
   matching cluster is simply dropped." So when `ingest` re-founds the same vehicles under fresh
   contact ids (`BL-B24`: 554 contacts / 444 objects), the next reconcile sees **zero** overlap,
   founds a brand-new `Group`, and loses `established_sim` + the whole `last_spoken_*` disclosure
   snapshot. Persistent spoken group identity is unreachable through that path *regardless* of
   what the contact layer does. Fixing group identity is cheaper and more pilot-visible than
   fixing contact identity.

2. **Cluster-level object permanence already exists and already uses DCS object ids.**
   `naked_eye_source._object_id_to_last_observation_id` + majority-object-overlap voting
   (`naked_eye_source.py:675-740`) resolves `continues_observation_id`; the spatial gate is already
   "the exception path, not the common case". So a decision reading "DCS unit IDs may now be used"
   needs **no new permission** — the id stays inside `perception/`, only an `observation_id`-shaped
   reference crosses `percept.py`. What such a decision actually changes is the *bound*:
   `OBJECT_ID_MEMORY_S = IDENTITY_HALF_LIFE_S = 600.0` is 10 minutes of object-id trust, which is
   precisely the "oracle across occlusion and long gaps" the bound forbids.

3. **`Covariance2D.inflated(elapsed_s, growth_rate_mps=GATE_GROWTH_RATE_MPS)` is already
   parameterised** (`position_belief.py:256`), with only three call sites. "Make uncertainty growth
   per-classification" is a threading change, not a new mechanism. **But** `POSITION_HALF_LIFE_S`'s
   docstring *derives* 30 s from the 20 m/s rate, and two `assert`s in `decay.py:174/188` bind
   `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` — move the rate and that derivation silently goes
   stale while still reading as evidence.

4. **"A directional corridor along the road graph, branching at junctions" is a world-model
   milestone wearing a belief-layer costume.** `world-model` exposes `nearest_road` /
   `nearest_junction` only as **point** facts inside `describe_position`
   (`query/describe.py:414/537`) — there is no traversal API — and `describe_position` is 51.6 ms
   median on `syria-full` (`BL-11` Stage 3). Worse, at a belief-layer horizon of 60 s the corridor
   narrows a region that is not the thing failing: 60 s × 8 m/s ≈ 480 m against a **measured**
   median cluster-to-cluster separation of 236-625 m. It pays for itself at `BL-8`'s 10-minute
   horizon (≈4.8 km), not here. Cheap stand-in that captures "units follow roads" at ~zero cost:
   elongate the existing displacement bound along a per-group **cached**
   `nearest_road.orientation_deg`.

**Two smaller things worth not re-deriving:**

- **There is no direction belief anywhere.** `MotionBelief` is `"moving"`/`"stopped"` only. The one
  direction in the codebase is `enrichment.motion_when_seen` (`enrichment.py:728`), derived from two
  raw implied percept positions with "no smoothing — a single noisy percept can flip the reported
  direction" (its own docstring), bypassing the fused `PositionEstimate`. Any spoken direction needs
  a new, fused-centroid-derived, smoothed one — do not wire speech to `motion_when_seen`.
- **The honest reason a within-group ambiguity tiebreak is not the "best-match guess"
  `pb2-contact-memory` Stage 1 refused.** That invariant protected against collapsing two things the
  pilot cares about *separately*. Group membership is the test for whether he does. Inside one group,
  founding a third contact does not preserve information — it destroys the **count**, which is the
  thing he actually hears. The measurement (16 m median spacing vs a ±600 m 30 s gate) is what makes
  the per-unit question unanswerable rather than merely hard.

See also [[project_contact_dup_continuity_of_track]], [[project_group_cohesion_redesign]],
[[project_resolution_vs_salience_split]], [[project_movement_detection_design]].
