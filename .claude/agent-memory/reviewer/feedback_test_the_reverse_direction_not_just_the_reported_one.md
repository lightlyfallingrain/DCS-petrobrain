---
name: test-the-reverse-direction-not-just-the-reported-one
description: When a bug fix gates a transition (seat/mode/state A to B), check whether the reverse transition (B to A) that the fix relies on but that wasn't the user's reported symptom has its own test
metadata:
  type: feedback
---

On `fix/ai-wheel-pilot-seat-gate` (2026-11-16): the reported bug was pilot-seat → AI-wheel-flaps.
The implementer's fix (gate on camera-derived seat) also changes behaviour for the *other*
direction — pilot seat **to** operator seat, where arg 852 can transiently still read "stowed"
during the un-stow animation, producing a false rising edge that only the pre-existing 0.5 s
reference-toggle delay absorbs. The task brief itself flagged this direction explicitly ("is that
sound?"), and every *other* named scenario (seat-switch frame, `on_stop`, 5 Hz overlay path,
external-view hold-last-seat) had a passing test — only this one, the un-reported direction the
fix's own safety margin depends on, had none.

**Why:** a fix for a reported symptom naturally gets tests for the reported direction first, and
reasoning-through-the-code can make the untested reverse direction *feel* covered because the
logic is shared. It isn't the same as a demonstrated case, and this is precisely the gap this
project's "verify by mutation, per entry" standing check (reviewer.md) and "Show the red" (debugger/
implementer) exist to close — just applied to a direction instead of a set entry.

**How to apply:** whenever a fix introduces or changes a state-transition gate (parked/flying,
seat A/B, armed/safe), ask explicitly: does the fix's own reasoning rely on a *different*
transition than the one in the bug report (e.g., the reverse direction, or a race the delay is
supposed to absorb)? If so, and no test exercises it, that absence is a reportable gap even when
the production code looks correct by inspection — flag it as a required fix (test-only) rather than
silently approving on "the reasoning holds."
