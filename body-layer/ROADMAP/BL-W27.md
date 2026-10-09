# BL-W27 — Group detectability — resolution vs. salience

- [x] **Group detectability — presence split into resolution vs. salience.** #status/done The dots-off ladder
  and the single-unit sortie only looked contradictory because one constant (`LOWRES_ANGULAR_
  RADIUS_RAD`) was answering two questions: can the eye register a mark at all (resolution), and
  would a lone mark be noticed while scanning (salience). Split into two: `RESOLUTION_ANGULAR_
  RADIUS_RAD` (0.00128, looser) alongside the unchanged `LOWRES_ANGULAR_RADIUS_RAD` (salience). A
  member of a cohesive, resolvable group of at least `GROUP_MIN_MEMBERS` (3, stated assumption) is
  admitted at the looser resolution threshold instead of the tighter salience one — the group
  supplies the salience a lone dot at that range does not have. New `perception/group_salience.py`
  (pure, no state, single-link union-find over `GROUP_COHESION_GAP_UNIT_WIDTHS`, 10.0, stated
  assumption), wired into `naked_eye_source.poll` once per poll ahead of the per-candidate
  `check_visibility` loop. `clustering.py`'s floor (A) — the constant's own correctness condition —
  now points at `RESOLUTION_ANGULAR_RADIUS_RAD`, the loosest threshold any admission path can use,
  not `LOWRES_ANGULAR_RADIUS_RAD`: a group-admitted candidate could otherwise satisfy (A) at
  `RESOLUTION` while failing it at `LOWRES`, silently merging two genuinely separable contacts —
  the third time this floor has needed attention.

  **The model predicts a rung it wasn't fitted to.** Infantry's group-admitted ceiling
  (`1.8 / 0.00128 = 1406 m`) sits below the 1.91 km rung where the pilot reports "detection + unit
  count (no infantry)" on the same twelve-unit complex — infantry isn't rescued by its conspicuous
  neighbours because it isn't *resolvable* at that range, exactly what the ladder shows. Checked
  directly in `test_vision_calibration.py`, not just asserted.

  **A real discrepancy the 5.44 km rung's own test found — and fixed in this same feature.** The
  plan specified `RESOLUTION_ANGULAR_RADIUS_RAD = 0.0013`, which is `7 / 5440 = 0.0012868` rounded
  *up* — the opposite direction from `LOWRES_ANGULAR_RADIUS_RAD`'s own precedent of rounding down so
  the calibration point it derives from stays admitted. That put the boundary at 5384.6 m, ~55 m
  short of the photographed 5440 m rung the plan's own prose calls "admitted (marginal)"; the plan's
  worked table already showed the contradiction (`"5385 m"` against a `"5.44 km"` rung).

  **Corrected to `0.00128`**, boundary 5469 m, and the rung clears. The principle is the reason: a
  threshold derived from an observation must admit that observation, or the derivation cannot be
  reproduced from the data it cites. Three tests had been written to *document* the wrong-way value
  and now assert the property instead.

  **`LOWRES_ANGULAR_RADIUS_RAD` deliberately not recalibrated** — it stays conservatively short for
  lone units (2333 m vs. 2.8–3.1 km observed) so the next sortie validates the group term uncoupled
  from a threshold change; fitting the group's reach into a per-unit constant would silently
  re-merge the two questions this work just separated. Counting/individuation on newly-admitted
  distant groups will over-claim (angularly-separable-but-not-salient dots each report as their own
  singleton cluster) — a stated, accepted assumption, not fixed here (would need a new
  `belief.cardinality` uncertainty state).

  See `plans/group-detectability/plan.md`.

