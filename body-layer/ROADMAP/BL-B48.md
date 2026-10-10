# BL-B48 — Infantry is an unbounded cohesion bridge between non-infantry contacts

- [ ] **BL-B48 — `belief.groups` drops the absolute cohesion backstop to `math.inf` for any pair where
  *either* member is infantry, so an infantry contact bridges non-infantry contacts without bound.** #status/open
  Found by the Reviewer during [[BL-13]], 2026-10-10. Pre-existing, **live on the push path today**,
  and nothing in BL-13 caused it.

  **It was first reported as "cohesion is erratic at fixture scales" and that was wrong.** It is
  deterministic, and the truth is worse than erratic — which is why this entry exists rather than a
  note about flaky fixtures. `OP_INFANTRY` is `EAGER`, and the eager path replaces the absolute
  distance backstop with `inf` for a pair where either member is infantry. Measured on the BL-13
  branch:

  ```
  armor@1km + truck@3km                 -> 0 groups
  armor@1km + infantry@7km              -> one group, 6 km across
  armor@1km + truck@3km + infantry@7km  -> one group of three
  ```

  So armour and a truck 2 km apart stay separate, but adding an infantry contact at 7 km merges all
  three into one group spanning 6 km.

  **Why this is wider than the direction that produced it.** The user's own words were *"ok to merge
  infantry too eagerly"* — a statement about **infantry**, and a reasonable one: a dismounted squad
  is not usefully counted individually. Merging **armour** across 6 km because an infantry contact
  sits between them is not what that grants, and a group 6 km across has no single believable
  bearing, range or disclosure line. The eagerness is being applied to the pair rather than to the
  infantry.

  **Bearing on [[BL-12]].** BL-12 is the milestone that redesigns group identity and continuity, so
  this should be read *before* that plan is finalised rather than fixed independently — it may be
  that BL-12's own model dissolves it, in which case this entry is the measurement BL-12 should cite
  rather than a separate fix. Flagging it here so the number exists and the measurements are not
  re-derived.

  **Answered 2026-10-11 by the [[BL-12]] Architect amendment** (`plans/group-contact-identity/
  plan.md`, amendment A2): **BL-12's model does not dissolve it — it amplifies it**, so this entry
  is a blocking prerequisite rather than a citation. Three reasons, measured: a 6 km cluster's
  remembered `centroid_uncertainty_m` is the members' own position RMS and says nothing about the
  cluster's extent, so one membership flip moves the centroid **1,667 m** in a tick against a
  displacement bound of ~15 m — every flip founds a new group, defeating BL-12's whole promise;
  BL-12's planned group heading derives from that same centroid displacement and would be
  fabricated; and the spoken-identity line is the pilot-facing form of this entry's own
  no-believable-bearing point. The amendment also records a **second, previously unrecorded fault**
  in the same function: with the absolute backstop at `inf`, the relative test
  (`3 × median(nearest-neighbour gap)`) cannot reject *any* pair at n = 2, which is why
  `armor + infantry` merges at any separation. Smallest correct fix measured there: require **both**
  members `EAGER` in `_pair_backstop_m` (mirroring rule 1's existing mixed-installation
  fall-through) — all three scenes above resolve, infantry-to-infantry thresholds bit-identical.
  Whether that reading of *"ok to merge infantry too eagerly"* is the intended one is queued for the
  user as the amendment's Q-A.

  **Why BL-13 was immune**, which is a point in favour of its Decision C: the summary renderer
  aggregates over the *filtered* contact set rather than over group rosters, so an over-wide group
  cannot drag out-of-scope contacts into a pull answer. The enumerated push path has no such
  protection.
