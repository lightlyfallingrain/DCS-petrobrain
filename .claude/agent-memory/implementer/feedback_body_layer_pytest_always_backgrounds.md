---
name: body-layer-pytest-always-backgrounds
description: body-layer's full pytest run takes ~4.5-5 minutes -- the harness backgrounds it after ~180s even with an explicit longer timeout param, so expect a background+notification cycle and read the output file (not a bare tail pipe) once notified, rather than treating the background move as a problem to avoid.
metadata:
  type: feedback
---

`PYTHONPATH=src:../world-model/src .venv/bin/python -m pytest tests -q` for the whole body-layer
suite (~3300 tests as of 2026-11-16) consistently takes 4.5-5 minutes. The harness's own
foreground-command cap (observed at ~180s) moves it to a background task before it finishes, even
when the Bash call's own `timeout` parameter is set to 600000ms -- the cap applies regardless of
the requested timeout.

**Why:** this is a harness-level foreground/background policy, not something the command or its
flags can opt out of.

**How to apply:**
- Expect this for any body-layer full-suite run; it is not a sign something is wrong.
- Do not pipe the backgrounded command through `tail` expecting to read partial output while it
  runs -- `tail` only flushes once the pipe closes, so the output file reads empty until the
  command finishes regardless of buffering elsewhere.
- Wait for the one `[run_in_background]` completion notification, then read the output file
  directly (`cat`, not `Read` per the tool-use convention against peeking at fork transcripts --
  this is a plain background Bash task, not a fork, so reading its output file is the intended way
  to retrieve the result).
- If asked to avoid backgrounding entirely, the only way is to narrow the run (`-k`, a specific
  test file/path) so it finishes under the cap -- the full suite cannot be forced to stay foreground.
