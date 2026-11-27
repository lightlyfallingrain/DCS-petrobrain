---
name: flight-control-rate-vs-value-bias
description: BL-16 flight_control.lua -- a per-frame "bias" added into c_dot_nominal (a rate) integrates for the whole duration of its trigger condition, unlike a bias added into u_c_ff (a value, recomputed fresh every frame)
metadata:
  type: project
---

`flight_control.lua`'s collective loop (BL-16 lift-vector law) has two structurally different places
to add a correction, and they behave very differently even though a profile comment can describe
both the same way ("biased by this gain"):

- **`u_c_ff`** (and now `u_c_ff_total`) is a **value**, recomputed fresh every frame from the current
  desired state. A bias added here is bounded by construction -- it can never grow past whatever the
  current inputs produce, and it vanishes the instant its trigger condition clears.
- **`c_dot_nominal`** is a **rate** (1/s), multiplied by `dt` and folded into `state.u_c_i` (the
  integrator). A bias added here **integrates for as long as its trigger condition holds** -- if the
  trigger is "a commanded deceleration is still in progress", that can be several seconds, during
  which the bias accumulates with nothing to bound its total.

Found 2026-11-27 (`plans/flight-lift-vector/debug-2026-11-27.md`): the "slowing down is always less
collective" rule was implemented as a `c_dot_nominal` bias and pinned `u_c` at -1.00 for ~9 s during
a real decel, losing ~100 m of altitude the vertical loop's own `e_u` integrator could not catch up
to in time. Fixed by moving it to a bounded, capped value added alongside `u_c_ff` instead.

**When reviewing or adding a "bias"/"nudge" to this loop (or any similar feed-forward-plus-
integrator law in this codebase): ask which of the two categories it lands in before trusting a
profile comment's wording.** A rate-side addition needs its own explicit bound or decay; a
value-side addition is self-bounding as long as its own inputs are. See also [[bounded-feed-forward-vs-integrated-bias]] if that gets written up more generally.
