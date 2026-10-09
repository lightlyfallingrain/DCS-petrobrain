# BL-2.6 — Classification refinement

- [x] **BL-2.6 — Classification refinement (interim, no PB- equivalent; done, merged 2026-09-09).** #status/done
  `feature/classification-refinement`. Replaces BL-2's last-writer-wins classification fusion with a
  four-level specificity lattice (`unknown → presence → class → type`, `belief/classification.py`)
  and a fold rule so identity refines monotonically instead of oscillating; fires
  `CONTACT_CLASSIFICATION_CHANGED` on refinement/contradiction only. User decisions departing from
  the architect's recommendation: naked-eye reaches `type` at close range (not capped at `class`),
  gating tier moved `medres → lowres`. **Live-acceptance-found bug, fixed**: a single real object
  was producing 8–20 `Contact` records — the spatial gate budgeted only the incoming percept's own
  position uncertainty and treated `Contact.last_position` as exact; naked-eye's clock-bucket
  requantisation re-anchors to current heading every poll, so a stationary object's implied position
  can jump a full bucket-width between polls. Fixed with a symmetric gate
  (`Contact.last_position_uncertainty_m`, budgeted both sides). Watch-item carried forward: the
  wider symmetric gate roughly doubles the close-range floor, raising false-merge risk for two
  distinct objects at ~300–600 m — this is exactly what the object-permanence fix below closed.
  Full history: `plans/classification-refinement/`.

