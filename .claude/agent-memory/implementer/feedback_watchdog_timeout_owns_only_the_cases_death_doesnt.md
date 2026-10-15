---
name: watchdog-timeout-owns-only-the-cases-death-doesnt
description: when a timeout's docstring says "bounds X whose END never arrives," check whether a separate immediate-removal path (DEAD/CRASH, destroy, etc.) already owns one of the ways END can fail to arrive -- the timeout's real job and its stated job can differ
metadata:
  type: feedback
---

Found by Reviewer on `AC-B8`/`BL-B73` Stage B (`plans/emitter-visibility/review.md`), fixed by me
on the same branch (`feature/emitter-events`, commit after `031abd3`).

`EmitterTracker.FIRING_WATCHDOG_S` was documented as bounding "a START whose END never arrives."
That phrase covers two different causes with one mechanism, and only one of them was actually the
watchdog's job:

- unit destroyed mid-burst — already handled immediately and independently by the
  `S_EVENT_DEAD`/`_CRASH` removal path. The watchdog never fires for this case in practice because
  the death path always wins first.
- unit alive, still firing, burst running longer than the timeout — the watchdog's *only* real
  remaining case, and it was set (10.0s) against the wrong scenario: the old comment justified it
  as "generously above any plausible single burst duration," when the actual failure mode it
  risked was ending a sighting while the unit was still genuinely firing at the player mid-attack.

**Why this matters:** a constant's safe value depends on which case it actually protects, not on
the case its docstring names. When a review (or you, reviewing your own constant before shipping)
reads "bounds X whose Y never arrives," check whether a *different*, more specific mechanism
already handles one of the ways Y can fail to arrive. If so, the timeout's real justification is
narrower than its doc says, and the right value is "generous for the remaining case" not "generous
for the stated one" -- which can be a very different number (10.0 -> 180.0 here, not a small bump).

**How I fixed it:** raised the constant with a comment that explicitly says what it does NOT own
("this is NOT the backstop for destruction -- that's `_DEATH_KINDS`") before explaining what it
does own, so the next reader cannot re-derive the same conflation from the comment alone. Also
rewrote the module docstring's own summary table entry for the same reason -- the conflation was in
two places, not one, because the second was a paraphrase of the first written before the first was
known to be wrong.

**Test shape that pins this kind of distinction:** two tests, not one -- (1) the entry alive and
unattended past the *old* unsafe threshold stays visible (proves the fix), and (2) the same
sustained entry is still removed immediately the instant the death event arrives, at any point past
that old threshold (proves the *other* path still owns its case regardless of the new value). A
single test only proves one side.

Related: `.claude/agent-memory/reviewer/feedback_watchdog_backstop_conflates_failure_modes.md`
(the reviewer-side account of the same finding, commit `192957b` on `main`).
