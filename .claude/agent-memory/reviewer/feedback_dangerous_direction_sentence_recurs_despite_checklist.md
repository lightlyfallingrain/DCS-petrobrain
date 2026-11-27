---
name: feedback_dangerous_direction_sentence_recurs_despite_checklist
description: BL-B124 shipped two new tuning constants whose "dangerous direction" warning sentence was the SECOND sentence of the #: block and was silently dropped from defaults.toml, even though reviewer.md's checklist already names this exact trap by name
metadata:
  type: feedback
---

`body-layer/src/perception/light_level.py`'s two new tunables
(`SIGHT_FULL_DARK_SUN_ELEV_DEG`, `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`) each wrote the "which direction
is dangerous" sentence as the *second* sentence of their `#:` comment block — the implementer
clearly knew the convention existed (every other dangerous-direction constant in `visibility.py`,
e.g. `LOWRES_ANGULAR_RADIUS_RAD`, packs the warning into one long first sentence specifically so it
survives `generate_defaults.py`'s first-sentence-only render) but did not apply it to these two new
declarations. `test_tuning_comment_renders.py` did not catch it because that test is deliberately
scoped to *cross-key* couplings only, not generic dangerous-direction prose — correctly so, per its
own docstring's "a test that cries wolf is worse than no test" reasoning, but it means this class of
defect has no automated net at all, only the Reviewer's own habit of reading the rendered file.

**Why this matters beyond this one PR:** [[feedback_verify_the_rendered_artifact_not_the_source_comment]]
already records the mechanism (read the rendered file, not the diff) and root `CLAUDE.md`'s
tuning-pattern section names this exact trap in its own text ("a warning written as a second
sentence reaches nobody"). The checklist existing and being followed by *this* reviewer pass did
not stop the defect from being written in the first place — it only caught it after the fact. A
pattern this well-documented still needs a human (or future reviewer) to actually open
`config/defaults.toml` and read line-by-line; skimming the diff because "the implementer clearly
knows the X-T26 story" is exactly how the first three instances of this bug got through.

**How to apply:** when a new tuning constant's docstring states a dangerous-direction warning,
check — every time, not just when the diff "looks suspicious" — whether that sentence is before or
after the first `.` the `#:` block's prose would split on. If after, it is a required fix: fold it
into the first sentence (the existing convention in this codebase already shows the pattern to
copy), regenerate, and re-read the rendered output.
