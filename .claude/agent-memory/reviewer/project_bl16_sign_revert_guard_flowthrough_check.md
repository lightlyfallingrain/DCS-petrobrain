---
name: bl16-sign-revert-guard-flowthrough-check
description: when a debug pass reverts a sign flip, re-derive whether a guard fixed last time (made sign-agnostic) still lands on the correct side after the revert -- don't just trust that "derived from the coefficient" means "automatically correct"
metadata:
  type: project
---

BL-16 LV-1's second debug pass (`ebbbdcc5`, `plans/flight-lift-vector/debug-2026-11-24b.md`)
reverted the first pass's pedal-sign flip (`k_ball_pedal`/`rotor_dir`/`k_turn_coord_pedal`/the two
pedal limits) back to the original values. The first review
(`review-debug-1124.md`/`[[feedback_sign_flip_must_grep_every_near_limit_guard]]`) had required the
collective-near-pedal-limit guard to stop hard-coding `pedal_limit_positive` and instead derive its
side from `law_sign(k_pedal_from_collective_rate * rotor_dir)`. On this second pass I did not
assume that fix "just works" under the revert -- I traced it by hand: `rotor_dir` back to `+1` makes
`pedal_push_sign > 0`, so the guard checks `pedal_limit_positive` (now `0.5`, the scarce side again)
-- correct, matching the pre-first-pass behaviour. It would have been easy to wave this through on
"a derived-sign guard is sign-agnostic by construction," but a derived guard can still be wired to
the wrong constant, or a second un-derived consumer could exist elsewhere.

**How to apply:** whenever a review reverts or re-flips a sign-carrying constant that an earlier
review already made one consumer "sign-agnostic," re-derive that consumer's current behaviour by
hand against the new constant values rather than trusting the word "derived" to mean "still
correct." Then re-grep for every consumer of the flipped constant, the same as the first flip
required -- a revert is a second flip and can miss a consumer just as easily as the original did.

Also found, same session: a replaced test (`test_a_cross_fade_at_the_moment_of_take_uses_the_last_
steady_set` → `test_both_seats_live_captures_the_players_own_seat_not_a_snapshot`) was a justified
rewrite (the new seat-priority rule only reaches the old branch when the seat is unknown), but the
unknown-seat case itself ended up with zero test coverage after the replacement -- every test
driver in the file sets a known seat. A replaced test's justification can be sound while still
leaving the *specific* case the old test covered untested under the new code. Worth a grep across
all drivers for the literal value being varied (here, `ap_seat = `) whenever a test is replaced
rather than added alongside.
