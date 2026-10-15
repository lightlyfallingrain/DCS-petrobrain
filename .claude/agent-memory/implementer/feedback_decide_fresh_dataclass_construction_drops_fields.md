---
name: feedback_decide_fresh_dataclass_construction_drops_fields
description: when a function has some branches using dataclasses.replace() and others constructing the dataclass fresh, adding a new persistent field requires auditing every fresh-construction branch, not just the replace() ones
metadata:
  type: feedback
---

Found implementing `BL-B64` Stage 1b/§15a (`plans/9k113-sight/plan.md`) in
`body-layer/src/belief/optic_policy.py`. `OpticState` is documented as "frozen and
replaced rather than mutated," which reads as if every transition goes through
`dataclasses.replace(state, ...)` and therefore automatically carries every field
forward. It does not: `decide()`'s two branches that *start* a new phase
(`SCANNING -> SEARCHING`, `SCANNING -> GLASSING`) construct `OpticState(...)` fresh,
naming only the fields that phase's own bookkeeping needs. Every other field silently
resets to its dataclass default.

Adding `actual_aim_azimuth_deg`/`actual_aim_elevation_deg` (persisted across polls,
not part of any phase's bookkeeping) would have been silently correct today — the
field is unconditionally overwritten with the *desired* value immediately after
`decide()` returns, in this stage — and silently *wrong* the day a real controller
needs the *previous* poll's actual value to converge from, because the two fresh-
construction branches would have been resetting it to `None` on every phase
transition.

**How to apply:** before adding a field meant to persist independently of a state
machine's own phase, `grep` every construction site of that dataclass (not just the
places you're about to touch) and classify each as `replace(state, ...)` (carries
everything forward automatically) or a fresh `ClassName(...)` call (carries forward
only what is named explicitly). A fresh construction is the one that needs the new
field added by hand, and it is invisible to a search for "does this feature work" if
the feature's own trivial-passthrough stage never exercises the gap. This is the same
"enumerate the containing unit, not the call site you were pointed at" lesson this
role's own standing instructions give for exception handlers, applied here to
dataclass construction sites instead.
