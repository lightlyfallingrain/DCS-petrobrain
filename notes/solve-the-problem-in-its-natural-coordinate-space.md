# Solve the problem in its natural coordinate space

Two full implement-review cycles were spent on a world-space model of a question that is purely
angular. The naked-eye channel's position uncertainty was first a scalar radius, then an anisotropic
ellipse (cross-range acuity, down-range bucket width) — both approximations of "what angle do these
two things subtend at the observer". Stating it directly in angular terms **deleted 144 net lines**
and removed a tuned constant, because the anisotropy then falls out of the geometry: an airborne
observer separates a down-range pair by *depression angle*, which no world-space radius can express
without being told to.

Two tells that a model is in the wrong space, both present here and both visible before the rework:

- **A term whose justification keeps getting replaced.** The down-range radius was first "reporting
  quantisation", then "depth perception is poor at range". A term that needs a new reason each time
  someone looks at it is usually standing in for something else.
- **Constants that cancel or turn out non-binding once restated.** In angular form the optic
  multiplier cancels out of the comparison entirely, and the acuity floor is provably non-binding
  for anything the channel detected at all. Both were load-bearing in world space and neither was
  real — and the second removed a planned calibration sortie's main purpose.

The correction came from the user's lived experience, not from analysis: *"two apples 20 cm apart at
50 cm are obviously two side by side, and may be one when one sits behind the other"*. Worth
pairing with `.claude/skills/explore/SKILL.md` — asking for the non-DCS analogue is what surfaced it.
