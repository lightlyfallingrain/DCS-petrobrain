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

**A second instance (`BL-B104`, 2026-10-30): fuse two range cues in inverse distance, not metres.**
Combining a size/terrain-judgement range estimate with a depression-angle-derived one, the natural
observable for the second cue is `tan(depression) / height` (linear in the angle error), not metres
(`height / tan(depression)`, heavy-tailed toward long wherever the angle error is a sizeable
fraction of the angle itself). A Monte Carlo across five AGL/distance geometries showed metre-domain
fusion is up to **1.74× worse** than the simpler cue alone at some geometries, while 1/distance
fusion is never worse than either cue alone, anywhere in the grid — the same "state it in the space
the error is actually linear in" move as the angular-separation case above, this time for range
rather than position.
