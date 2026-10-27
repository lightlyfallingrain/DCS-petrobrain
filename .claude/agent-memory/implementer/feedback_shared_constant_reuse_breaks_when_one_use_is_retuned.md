---
name: shared-constant-reuse-breaks-when-one-use-is-retuned
description: Before raising a tuning constant to fix one concern, grep every other use of that same constant in the file -- an earlier "reuse by coincidence" note becomes a real bug the moment the value changes
metadata:
  type: feedback
---

On `probe/9k113-hud-elevation-limits` (required fix, 2026-10-27), the reviewer's Optional
Refinements flagged that `MARGIN_S` was reused for two unrelated purposes in
`Export.probe-9k113-hud-elevation-limits.lua`: the stall-vs-clip discrimination hold, and the final
RETURN phase's centring-nudge duration -- called "a minor conflation... not a bug" because at the
original value (3.0 s) the nudge's small overshoot was harmless.

The required fix was to raise that same constant (3.0 -> 20.0) to exceed a documented 4-18 s
AI-axis command-gate window. Raising it in place would have made the RETURN nudge run for 20 s
instead of 3 s -- several degrees of real elevation travel, overshooting well past centre, not the
"not a precise re-centre, just don't leave the sight parked at the edge" behaviour the nudge was
designed for.

**So: before retuning any constant flagged (even as "not a bug") as reused across more than one
concern, grep every read site of that constant in the file, not just the one the fix targets.**
Decoupling it into two named constants (one per concern) at that point is cheap and turns a latent
coincidence into an explicit, independently-tunable value each. Doing this after raising the value
rather than before would have shipped a correct-looking fix with a new, silent side effect in a
part of the probe nobody was looking at.

See also [[feedback_9k113_stall_vs_clip_margin_too_short]] (reviewer memory) for the margin-vs-
documented-gate-window check this fix was answering, and the sibling lesson it names: a plateau's
travel from its own seek-start value, checked against elapsed time and commanded rate, is a more
robust discriminator than any fixed time margin against an AI-axis gate whose duration is itself
documented as variable (4-18 s typical, up to flight-duration once).
