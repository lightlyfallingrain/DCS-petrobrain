---
name: bl16-bit-exact-take-pattern
description: BL-16 flight_control.lua's "bit-exact at take" invariant and the feed-forward/integrator-split pattern used to add a new non-integrated term without breaking it
metadata:
  type: feedback
---

`flight_control.lua`'s mode-1 law has a standing invariant (Decision 24): at the exact instant of
a take, `law_outputs(law_init_at_take(...))` must reproduce the captured axis command exactly
(`TestBitExactAtTake`). Every existing term already does this via a feed-forward/integrator split
backed out at take — e.g. collective: `u_c_ff = k_lift_ff*(n_d-1)`, and the integrator seed is
`u_c_i = command.collective - u_c_ff_at_take`, so `u_c_ff + u_c_i == command.collective` on the
take frame exactly.

**How to add a new non-integrated term (e.g. a proportional correction) without breaking this**:
compute the new term's take-instant value and subtract it from whatever existing integrator
state it will be added alongside at output time, so the sum still equals the captured command.
Added LV-1's `k_ball_pedal_p` proportional ball term this way: `t_y` stays the pure integral
accumulator, the proportional term `k_ball_pedal_p*(ball-centre)` is computed fresh every
`law_outputs` call (never integrated, same shape as the pre-existing `turn_coord_pedal` "position
overlay"), and `law_init_at_take` seeds `t_y = command.pedals - t_y_p_at_take` so the two cancel
back to `command.pedals` on the take frame.

**Why this matters**: a naive "just add the new term at output" breaks bit-exactness immediately
(the new term is nonzero on the take frame unless the physical quantity it reads happens to be at
its own centre/zero exactly then), and the breakage is silent unless a test specifically exercises
a non-default value of that quantity at take (the existing `_measured()` helper in
`test_flight_control_law.py` defaults `ball` to `profile.ball_centre`, so every pre-existing
bit-exact test passed even with the naive approach — only a new test with `measured.ball` set away
from centre at take would have caught it).

**Confirm with your own falsifiable test**: a bit-exact-at-take test with the relevant quantity
deliberately NOT at its default/centre value, not just the pre-existing ones (which may be
inert-by-default for the new term).

See: `plans/flight-lift-vector/implementation.md`, "LV-1 amendment" section.
