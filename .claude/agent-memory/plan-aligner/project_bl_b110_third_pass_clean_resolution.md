---
name: bl-b110-third-pass-clean-resolution
description: BL-B110 third pass resolved both prior plan-check CONCERNS (scan order, glass budget) because the architect went back to the user with the exact arithmetic rather than re-guessing — check the resolution against live code, not just that a question was answered
metadata:
  type: project
---

BL-B110 (expected-area check)'s third architect pass answered the two open questions from
[[project_scan_reshape_ahead_latency_vs_decay_revisit]] (scan order, ahead-detection latency) and
Decision 5 (glass budget). Both landed cleanly:

- The user's "always start from ahead and sweep to left/right alternating" turned out to describe
  the **unchanged default `SCAN_PLAN`** exactly — `(12, 11, 10, 9, 12, 1, 2, 3)` already is that
  path. The architect verified this against `perception/gaze.py` rather than asserting it, which
  made the whole reshape (and its test churn) unnecessary. The prior "~14s ahead latency" finding
  became moot because its premise (ahead swept once per cycle) stopped applying once the table
  reverted to the original.
- "12 s sounds ok, don't limit the time too tightly" was built as a **start-gated, rolling, no
  per-step-cap** budget — a literal reading, not a rounded one. A new `GLASS_STALL_COOLDOWN_S`
  tunable closed a real, separately-discovered gap (`GLASSING` retrying a failed look at the same
  range every 64 s) by reusing `BL-B85`'s existing `SIGHT_STALL_COOLDOWN_S` pattern rather than
  inventing one.

**How to apply:** when a revision claims a prior concern is resolved by reverting to "no change,"
verify the literal claim against the actual constant/table in source, not the plan's restatement
of it — here `SCAN_PLAN`'s tuple and `GLASSING`'s `is_worth_a_look` call site both checked out on
one grep each, and that's what let the verdict go to ALIGNED instead of another conditional CONCERNS.
A new stall/cooldown constant reusing an existing sibling mechanism (not inventing a second one) is
the "do not reinvent the wheel" pattern working correctly — worth recognizing as a pass, not just
checking for violations of it.
