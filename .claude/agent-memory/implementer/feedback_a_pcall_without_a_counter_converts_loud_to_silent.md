---
name: a-pcall-without-a-counter-converts-loud-to-silent
description: Wrapping a call in pcall/try is only half a fix — without a counter it turns a logged failure into silence, and check the sibling population for the asymmetry
metadata:
  type: feedback
---

**Adding a `pcall` (or `try`) around a previously unprotected call is not a safety improvement on its
own. It is a trade: a loud failure for a quiet degradation. The counter is the other half, and it is
not optional.**

**Why:** `fix/los-hook-statics` (2026-10-06) wrapped four unit-enumeration calls in the LOS Hook's
bridged chunk in `pcall`. Before, such an error propagated out of the chunk and `pollAndSend` logged
`poll failed:`. After, a whole coalition side's units silently vanished from the candidate list. The
*same commit* correctly added `staticEnumFailures` for the statics side — so the file ended with
`staticEnumFailures` appearing 3× and `unitEnumFailures` 0×. The reviewer caught it; the counts were
the proof.

**The bias direction is what made it expensive.** The sortie existed to measure whether a 128
sightline cap binds. A silent enumeration failure yields *fewer* candidates, which *understates* cap
pressure — so the failure would have made `cap_hit=0` read as good news, and the flight would have
been wasted rather than merely noisy. **Always ask which way an unreported failure biases the number
the change exists to produce.** If it biases toward "fine", it must be counted.

**How to apply:**

- When adding error suppression, ask what used to happen on failure. If the answer is "it was
  logged", you are removing a log line and owe a replacement.
- **Check the sibling population.** The asymmetry is the tell: if one of two parallel loops /
  branches / sides got a counter in the same change, the other needs one. Grep both names and
  compare the hit counts — `grep -c` on each is faster and more honest than reading.
- **Enumerate the guarded sites in a comment at the counter's declaration**, naming which are counted
  and why, and that a new call needs a bump or its own counter. A reader who only greps call sites
  gets the wrong count; see [[feedback_guard_every_statement_not_the_one_that_raised]] and
  [[feedback_subject_discriminating_gate_breadth]].
- **Prefer a field on an existing log/metric line** over a new log call when the condition is rare
  and the code path is re-entered at a fixed rate — a 1 Hz loop with no cross-iteration state cannot
  log "once" without new shared state, so a dedicated warning becomes a flight's worth of noise.

Related: [[project_degrade_guard_exception_breadth]], [[project_los_hook_statics]].
