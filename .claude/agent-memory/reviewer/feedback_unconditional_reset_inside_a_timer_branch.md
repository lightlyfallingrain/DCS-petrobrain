---
name: unconditional-reset-inside-a-timer-branch
description: when reviewing a "stuck-since" timer/accumulator, check whether the reset line is inside the fired-only branch or runs every pass through the outer condition
metadata:
  type: feedback
---

A timer pattern of the shape "set `since = t` the first time a condition becomes true; fire once
`t - since >= TIMEOUT`; reset `since` afterwards" is only correct if the reset line sits **inside**
the fired branch. If it sits at the same indentation as the fired-check (i.e. runs every time the
outer condition is true, fired or not), the accumulator gets overwritten to the current time every
pass and `t - since` can never grow past one pass's own `dt` — the timeout becomes practically
unreachable (BL-B80's `Export.lua` AI-off detector: `ai_off_since = t` sat right after the inner
`if (t - ai_off_since) >= TIMEOUT ... end` block, at the same indentation, with a comment
("Reset either way") that read as intentional but was wrong — the detector could never fire except
across a frame stall ≥ the timeout itself).

**Why:** per-frame Lua state in `Export.lua` has no automated test reaching it at all
(`aircraft-layer/CLAUDE.md`'s own stated limitation), so this class of bug is caught only by
tracing the control flow by hand, frame by frame, across at least two consecutive passes through
the branch — reading it once (as the diff, or even the function in isolation) reads as correct
because the single-pass logic *is* correct; the bug only shows up on the second pass.

**How to apply:** whenever reviewing a timeout/stuck-since/debounce accumulator in a per-frame or
per-poll loop with no automated test reachable (any `Export.lua` function, or any Lua per-frame
state), manually trace two or three consecutive iterations by hand rather than reading the branch
once. Specifically check: does the reset line only execute on the branch that actually fired, or
does it also execute on every iteration that merely re-entered the outer condition?
