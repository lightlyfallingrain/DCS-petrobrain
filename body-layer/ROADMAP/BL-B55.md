# BL-B55 — Position uncertainty is optic-blind, and the 9K113 slice depends on it

- [x] **BL-B55 — `naked_eye_sigma_m` takes range only, so every look gets naked-eye-grade position
  error regardless of which optic made it.** #status/done #needs-flight
  **Closed as `[[BL-B64]]`'s own Stage 1b, merged 2026-10-15 in `ec39c0e`** — the two could not be
  separated, because a sight seeing to 8 km while every look carried naked-eye range error would
  report a confident range wrong by ~1.4 km, which is worse than having no sight. `naked_eye_sigma_m`
  is now `look_sigma_m` with a mandatory optic parameter. The per-optic scales are **stated
  assumptions, not measurements**, so the acceptance sortie is what confirms them. Identified by the user, 2026-10-11, from
  the pilot's side rather than the code's — see
  `docs/acceptance/2026-10-11-infantry-detectability-feedback.md` for his words and the arithmetic.

  His reasoning, which is the whole item:

  > *"The 9K113 case is different because it can detect any units much further away, but then with
  > the tighter FOV, also real and believed location should be fairly close even at distance."*

  **A magnified, narrow-FOV sight localises better.** That is not modelled:
  `perception/estimation.py:98`'s `naked_eye_sigma_m(true_range_m)` returns
  `(BEARING_SIGMA_DEG × range, RANGE_FRACTIONAL_SIGMA × range)` with `RANGE_FRACTIONAL_SIGMA = 0.17`
  and no optic parameter. Its single call site is
  `perception/naked_eye_source.py:949`, inside `_build_observation`.

  **This is live today, not only a 9K113 concern.** `BINOCULAR_OPTIC` already multiplies the
  *detection* thresholds (`presence_range_mult = 2.42`) while the position error stays naked-eye —
  so a binocular look sees further and is believed no more precisely. `visibility.py` is optic-aware
  (`check_visibility(..., optic=self.optic)` at `naked_eye_source.py:583-588`) and `estimation.py`
  is not, which is the asymmetry.

  **The fix is cheap, and the first reading of it was wrong.** `self.optic` is already an attribute
  of the source (`naked_eye_source.py:553`, `:588`), in scope at the call site — so this is a
  parameter added to one function and threaded at one call, not a trip across the perception/belief
  seam as initially assumed. Checked before filing, because "structural" and "one parameter" lead to
  very different scheduling.

  **Why it earns an entry rather than a note.** It is a **prerequisite for the 9K113 slice**, not a
  tidy-up. The 9K113's whole value is seeing units much further away; give those looks naked-eye
  position error and every one of them lands with `σ_down ≈ 0.17·R` — at 8 km that is 1.4 km of
  down-range error on a contact the sight resolved precisely. The pilot would be told a precise-
  sounding range that is wrong by a kilometre, which is the *"precision is not omniscience"*
  property `plans/precise-position-belief/` established, pointed the wrong way.

  It also bears on [[BL-12]] Stage 0's `GROUP_REPORTING_EAGER_COHESION_CAP_M`: the Stage 0 review's
  one required fix is that the cap is calibrated on true spacing and applied to believed spacing,
  with `σ_Δ ≈ 0.24·R` the omitted term. That term is exactly what a per-optic model would shrink for
  a magnified look — so this item is what would make the cap behave at range once the 9K113 exists.
  **Do not retune the cap for this**; fix the error model instead.

  What is not decided here: whether the per-optic figures are derived from the 9K113's own
  magnification/FOV numbers (`optics.py:19` records wide 3.55/7.00/6.50, narrow — sourced but
  unused) or measured in-game the way the 2026-09-17 vision-range calibration was. The calibration
  precedent argues for measurement; that is the 9K113 slice's own call.
