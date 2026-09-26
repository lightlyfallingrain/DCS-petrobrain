---
name: aircraft-hardening-accept-race-required-fix
description: aircraft-layer-hardening (6e821c9) accept() guard's shutdown-classification claim was false and empirically racy; verify "never re-reads the attribute" claims by running the shutdown path, not by reading the docstring
metadata:
  type: project
---

Reviewing `feature/aircraft-layer-hardening` (6e821c9 vs 4c73639, two RECOMMENDED fixes from the
2026-09-26 whole-subproject reviews: bounded `AudioPlaybackSender` queue with drop-oldest, and a
guarded `CollectorServer.serve_forever` `accept()` loop).

**The audio-queue bound (Fix 1) was clean** — verified independently (outside pytest) that the
drop-oldest overflow path really removes the dropped `.wav` from disk; the FIFO-survivors test is
a real proof, not decorative.

**The `accept()` guard (Fix 2) is where the interesting defect was**, and it is the same genre as
[[feedback_verify_pipeline_wiring_not_just_module]] and
[[feedback_transform_confidence_verification]]: a docstring/implementation-log/agent-memory claim
("`self._socket` is captured into a local once per iteration and never re-read after the
exception fires") that reads as done on inspection but is literally false in the code — the
`except OSError` block *does* re-read `self._socket` a second time, to classify the error as
real-failure vs. intended-shutdown. The unconditional crash the fix targeted (`.accept()` on
`None`) really is gone (a separate top-of-loop check protects every `.accept()` call site), so a
plain code read plus "does it still crash" would pass this. What it doesn't catch: `close()` does
`socket.close()` then `self._socket = None` as two separate statements, and the re-read in the
except block races that window. I ran the real shutdown path (real socket, real `close()`, real
`serve_forever`, no mocking) 300+ times outside pytest and got a false "accept() failed
unexpectedly" ERROR log on **161 of ~230** runs before stopping — not a rare edge case, the
*common* case on this platform. That directly defeats the fix's own stated purpose (an
operator-visible ERROR line for a real failure) by crying wolf on most ordinary shutdowns.

**Technique worth repeating**: when a fix's whole justification is "we distinguish condition A
from condition B by reading attribute X, and here's why that's safe," don't accept the reasoning
from the docstring — write a tiny script that drives the actual condition B (here: real `close()`
racing a blocked `accept()`) in a loop and count how often it's misclassified. A single manual run
or the shipped test (which doesn't assert on log content at all, despite its own docstring
claiming "ends the loop without logging it as a failure") will not surface a race that only fires
part of the time.

Also worth noting for future review of retry-adding changes to `serve_forever`-shaped loops in
this codebase: adding retry-on-failure to a previously fail-fast loop is exactly the change that
introduces this class of race, because a fail-fast loop has nothing to misclassify (any `OSError`
just returns). `F10CommandReceiver`/`UnitVelocityReceiver` don't have this problem for that
reason; any *future* retry-on-failure addition to one of those will need the same scrutiny.

Correct fix (recommended, not yet applied as of this review): a shutdown flag set as the *first*
statement of `close()`, before `self._socket.close()` — flag-write happens-before the syscall that
can trigger the exception, in the same thread, which removes the race deterministically rather
than narrowing it.
