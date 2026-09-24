---
name: project-covariance2d-determinant-floor-scale
description: Covariance2D.inverse() in position_belief.py is called on both covariance-scale and information-scale matrices -- any absolute floor/epsilon there is wrong for one of the two regimes
metadata:
  type: project
---

`body-layer/src/belief/position_belief.py`'s `Covariance2D.inverse()` is used two ways inside
`fold_position`: once to turn each look's real covariance (metres^2, determinants ~1e7-1e12 for a
naked-eye look) into an information matrix, and again to turn the *summed* information matrix
back into a covariance (determinants ~1e-8 to 1e-12 -- roughly the reciprocal scale). An absolute
determinant floor calibrated against one regime silently corrupts the other. Found live:
`_MIN_DETERMINANT = 1e-9` (tuned for the covariance-scale case) clamped the information-scale
inversion for any same-bearing repeated naked-eye look beyond ~2.7km (well inside the 10km
envelope) -- not a corner case, an ordinary re-glassed look -- corrupting the fused *mean*, not
just its uncertainty, and making the new `FUSION_SANITY_SIGMA` residual guard misfire on
legitimate evidence. `plans/position-belief-runaway/debug.md`'s 2026-09-25 addendum has the full
repro numbers.

**Fix pattern, worth reusing anywhere else this module (or a future one) inverts a 2x2 SPD
matrix**: `determinant / trace^2` is the matrix's own eigenvalue ratio `ab / (a+b)^2` --
dimensionless, and *provably invariant under `.inverse()` itself* (inverting flips both
eigenvalues' sign in the exponent, leaving their ratio unchanged). A floor expressed as
`max(RATIO * trace**2, ABSOLUTE_BACKSTOP)` guards genuine near-singularity (one axis's variance
collapsed toward zero relative to the other) at any scale, in either form, with one constant. An
ordinary naked-eye covariance sits at ratio ~0.08 -- many orders of magnitude above any sane
`RATIO` floor (1e-9 was kept, just reinterpreted), so it never fires on real data.

**General lesson**: when a module's own docstring or a debugger's report calls something "should
never arise from any real declared sigma, but a defensive floor is cheaper than a
`ZeroDivisionError`," don't take that framing at face value if the surrounding function is called
at more than one scale. Check every call site's actual determinant magnitude before accepting
"pre-existing, unrelated, out of scope."
