---
name: feedback_binocular_not_unaided_eye
description: A named ED tuning constant reused in this codebase can be reinterpreted by explicit user decision -- name/document the project's own meaning, not the source's
metadata:
  type: feedback
---

In PB-1.5 (`plans/pb1.5-naked-eye-detection/plan.md` Decision #6), the user affirmed that
`HelperAI.lua`'s `extra_eyesight_ratio = 4.0` should be used as a ×4 range multiplier, but
explicitly reframed *why*: the channel models a crew observer using handheld **binoculars**, not
DCS's own unaided-eye detection formula. The numeric value is identical to ED's constant, but its
justification is now a first-party project decision, independent of whatever `extra_eyesight_ratio`
actually multiplies in DCS's native (unreadable) detection code.

**Why:** the user's reasoning is stronger than the plan's own prior "consistency with ED's scan
radius" argument, and it changes what future maintenance should do with the constant: it must
never be "corrected" back toward an unaided-eye reading just because it shares a name/value with
an ED constant.

**How to apply:** when reusing a value sourced from an external/reverse-engineered constant (a
game's tuning file, a vendor's published spec, etc.) under an explicit user reinterpretation, name
and document the constant for *this project's own meaning* in the code that defines it (see
`body-layer/src/perception/visibility.py`'s `BINOCULAR_RANGE_MULTIPLIER` docstring) -- not as a
transcription of the source. State the premise plainly in every module that consumes it, so a
future reader (or a future implementer without this context) doesn't silently "fix" the value
by re-deriving it from the original source's assumptions. Flag the numeric coincidence (same
value, different justification) explicitly rather than letting it look like unexplained reuse.
