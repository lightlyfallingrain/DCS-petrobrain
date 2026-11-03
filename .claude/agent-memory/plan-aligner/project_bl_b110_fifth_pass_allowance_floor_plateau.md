---
name: bl-b110-fifth-pass-allowance-floor-plateau
description: a test-fence allowance with a floor can satisfy "the closer, the more specific" at every measured range today while not literally encoding that relationship below the floor's own breakpoint
metadata:
  type: project
---

BL-B110 (expected-area check) fifth pass built a rough-location allowance,
`max(250 m, 0.2 · R)` down-range, to fence the claim that a naked-eye look is always good enough
for "priority 1" position (no binocular look needed). The user's own wording was continuous —
"the further away we are, the more imprecise the location is allowed to be. At close distances a
more specific location can and should be obtained" — but the built fence plateaus flat at 250 m
for any `R` under 1.25 km, rather than continuing to tighten toward zero range.

This cost nothing today: the actual naked-eye model (`RANGE_FRACTIONAL_SIGMA = 0.17`) delivers far
tighter numbers than the floor at every range checked (81–85 m at 500 m, against a 250 m
allowance), so the pilot hears the tight real figure, not the loose fence value. The fence is a
regression guard (Decision 10, already named as such), and a floor that plateaus is a weaker guard
*specifically in the range band the user called out as mattering most* — a future regression could
degrade close-range precision to 250 m (80% of a 300 m range) and still pass.

**How to apply:** when a plan builds an allowance/fence from "tighter as X decreases," check
whether the formula's own shape (a `max(constant, k·X)`) actually keeps tightening all the way
down, or flattens at a floor below some breakpoint. A floor chosen for an unrelated reason (here:
"half the spoken range step," a UX granularity argument) can silently cap the fence's protective
power exactly where the user's own wording cared most. Not a blocker if the real delivered values
already clear the fence with margin — but worth flagging as a cheap tightening (drop the floor,
use the pure proportional form) rather than leaving the gap unexamined. See
[[project_bl_b110_third_pass_clean_resolution]] and [[project_scan_reshape_ahead_latency_vs_decay_revisit]]
for the sibling pattern: a plan's own arithmetic answering an adjacent question, not the one asked.
