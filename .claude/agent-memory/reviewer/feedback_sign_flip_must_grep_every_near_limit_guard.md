---
name: sign-flip-must-grep-every-near-limit-guard
description: when a fix flips a command-domain sign convention (e.g. "positive pedal = right" -> "positive = left") and swaps the two asymmetric limit magnitudes to match, grep for every place a *guard* compares state against one named limit specifically (pedal_limit_positive, not both) -- a guard written for the old scarce side silently starts protecting the new abundant side instead
metadata:
  type: feedback
---

BL-16 LV-1's pedal-sign fix (`plans/flight-lift-vector/debug-2026-11-24.md`,
`feature/bl16-lift-vector-law`, commit `844213f1`) flipped `k_ball_pedal`/`rotor_dir`/`k_turn_
coord_pedal` and swapped `pedal_limit_positive`/`pedal_limit_negative`'s magnitudes correctly and
with solid, independently-derived evidence. But `law_update`'s collective-near-pedal-limit guard
(`if state.t_y >= (profile.pedal_limit_positive - profile.pedal_near_limit_margin) then
u_c_rate = math.min(...)`) was never updated — it still names `pedal_limit_positive`
specifically, which used to be the scarce/right side and is now the generous/left side. The
torque feed-forward that drives this guard (`k_pedal_from_collective_rate * u_c_rate *
rotor_dir`) now pushes `t_y` *toward* `pedal_limit_negative` when `u_c_rate > 0`, so the guard
that exists specifically to cap collective increases near the scarce pedal limit now checks the
wrong side entirely — confirmed by direct mutation against the real law (not just reading): a
`t_y` near the new scarce limit got no cap at all, a `t_y` near the new abundant limit got capped
unnecessarily.

**Why:** the task brief's own stated main risk was "a flip that misses one consumer," and the
debug pass's "which term dominated" analysis (correctly) focused on the three gains that produce
the observed divergence, never widening to "every place a limit is referenced asymmetrically
nearby." A guard like this is easy to miss because it is not a *sign* on a gain — it's a
hard-coded reference to one named limit out of a pair, and nothing about reading the three flipped
gains' diffs would surface it.

**How to apply:** whenever a fix flips a command-domain sign convention and swaps two paired
asymmetric limit magnitudes (not just the sign of a gain), grep the whole consuming file for both
limit names individually (`pedal_limit_positive`/`pedal_limit_negative`, or whatever the pair is
called) and check every comparison that names only one of the two — not just the comparisons that
also reference the flipped gains. A guard that was correct when it was written can become
precisely backwards after the limits swap, with zero error, zero test failure, and the main
sign-fix tests still passing cleanly, because the guard's own test coverage was zero before and
after (confirm this with `grep` for the cap constant's name across every test file, not just by
reading the new tests that were added). See [[project_bl16_pedal_near_limit_guard_regression]] for
the specific review this came from.
