---
name: project_pb2_contactstore_thread_safety
description: How to judge ContactStore thread-safety when reviewing body-layer's --console REPL (poll thread vs REPL thread), reusable pattern for any future unlocked shared-store reviews.
metadata:
  type: project
---

`body-layer/src/belief/contacts.py`'s `ContactStore.contacts`/`.observations`/`.events` are
properties that return a **fresh copy** each call (`list(self._contacts.values())`,
`dict(self._observations)`, `list(self._events)`), not a live reference. This is why
`src/logger.py`'s Stage 4 `--console` REPL (poll thread mutates the store via `ingest`/`tick`,
REPL thread reads it via `belief.tools` with no lock) is safe from crashes/corruption under
CPython's GIL: the copy constructors run as a single atomic C call, so no "changed size during
iteration" or torn read is possible. The only real cross-thread hazard is two threads setting
different attributes on the *same* `Contact` object concurrently (e.g. `watch_contact` setting
`.attention` while `record()` sets `.last_position`) — at worst a stale/interleaved read, never a
crash, and defensible given the console's explicit "single dev-console user, best-effort" posture
documented in `logger.py`'s own module docstring.

**How to apply:** when reviewing any future stage that adds concurrent readers/writers to
`ContactStore` (or a similar in-memory store), check first whether the store's accessor methods
return copies vs. live references — that single fact usually resolves whether "no lock" is a
required fix or a defensible optional note. Don't flag unlocked concurrent access as a required
fix without checking this.
