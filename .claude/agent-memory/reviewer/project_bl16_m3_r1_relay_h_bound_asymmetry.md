---
name: bl16-m3-r1-relay-h-bound-asymmetry
description: BL-16 M3 revision R1 review (APPROVED) -- applying "grep every sibling field" caught server.py's new _terrain_relay_passes_bounds checking h for finiteness only, not magnitude, while x/z got both; not exploitable (Lua still enforces |h|<1e5 independently) but implementation-m3.md's own prose overstated what the code checks
metadata:
  type: project
---

`plans/flight-lift-vector/security-m3.md` Finding 1 asked only that `x`/`z` get the magnitude
bound `h` already had on the Lua side (`|h| < 1e5`). The R1 fix (`74dfae71`) added
`_terrain_relay_passes_bounds` in `aircraft-layer/src/api/server.py` and did exactly that for
`x`/`z` (`_TERRAIN_POINTS_COORD_ABS_MAX`), but the function checks `math.isfinite(h)` with no
`abs(h)` ceiling at all -- `h`'s magnitude is still unbounded at the Python layer, only at the
Lua layer. Traced whether this was a real gap (applying
[[project_bl16_terrain_relay_xz_unbounded_magnitude]]'s own "grep every sibling field in the
parse function" lesson to the *fix*, not just the original finding): not exploitable, since Lua's
`parse_terrain_relay` still independently drops an out-of-range `h` before it reaches `run_
active_frame`'s projection -- the one place it could do anything. Filed as an Optional
Refinement, not a Required Fix, because the finding never asked for a *new* bound on `h` at this
layer, only for `x`/`z` to catch up to `h`.

**What is worth remembering**: `implementation-m3.md`'s own R1-c prose said the new function
"rejects on any non-finite or out-of-bound `x`/`z`/`h`" -- overstating what the code actually
checks for `h` (finite-only). This is the same shape as
[[feedback_plan_backfill_fixes_text_not_the_test_it_promised]] one level removed: not a backfilled
plan sentence this time, but an implementer's own prose describing a fix slightly more broadly
than the code delivers. Caught by reading the actual `if` conditions in the diff rather than
trusting the paragraph describing them -- the lesson generalizes: **when a fix's own writeup lists
several fields together ("x/z/h"), check each one actually got the stated treatment, not just that
the writeup reads as complete.**

See [[project_bl16_terrain_relay_xz_unbounded_magnitude]] (the security finding this fix responds
to) and [[feedback_sign_flip_must_grep_every_near_limit_guard]] (the general "grep every sibling"
habit this is one more instance of, now on review-of-a-fix rather than review-of-original-code).
