---
name: project_recurring_tuning_comment_second_sentence_dropped
description: generate_defaults.py's first-sentence-only render has now recurred 4+ times (most recently BL-16 M1+M2's ARM_LEASE_S) -- a generator-level fix or lint, not another Reviewer catch, is the next right move
metadata:
  type: project
---

`body-layer/tools/generate_defaults.py` renders only a `#:` tuning comment's *first sentence*
into `config/defaults.toml`. This has now produced a real, shipped defect at least four times
(reviewer memory `feedback_arm_lease_s_second_sentence_recurrence.md` calls BL-16 M1+M2's own
`ARM_LEASE_S` case the fourth; `feedback_generator_abbreviation_period_truncates_sentence.md` and
siblings name several more sentence-splitter bugs in the same function on top of that), every
single time caught only by a human-equivalent read of the *rendered* file, never by the
generator itself or by a mechanical test.

**Why:** an implementer adds the explanatory second sentence (often the most load-bearing part —
why a bound is tighter than its siblings, a cross-layer coupling, a safety-margin rationale) to a
tuning comment, runs the generator, confirms the *number* changed, and stops — the checklist step
"read the rendered file" exists precisely because the generator's own "ran successfully" signal
says nothing about whether the explanation reached the file. Every instance so far has been
caught at Reviewer (occasionally DoD), never earlier, and never by the generator refusing or
warning.

**How to apply:** this is process debt, not code debt, and the "read it by hand" checklist step
has now proven itself an unreliable backstop across four-plus occurrences on the same mechanism.
Worth raising to Architect/Implementer level: either (a) `generate_defaults.py` warns (or the
staleness test fails) whenever a `#:` block's *source* comment has more than one sentence but the
rendered output's own sentence differs from the full first paragraph (a cheap self-consistency
check: does the committed file's comment equal `_first_sentence(source)` exactly, for every key),
or (b) the convention changes so the explanatory material is required to fit in the first
sentence by construction (a style rule enforced at the point of writing, not caught after the
fact). Catching it at Reviewer/DoD every time is strictly more expensive than either of those
one-time fixes, and the recurrence count is now high enough that "just remember to check" has
already been shown not to work as the standing mitigation.
