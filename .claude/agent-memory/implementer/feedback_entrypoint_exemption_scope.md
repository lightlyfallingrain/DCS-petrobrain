---
name: entrypoint-exemption-scope
description: an entrypoint's "no automated test" exemption covers the CLI wiring, not every class merely co-located with it
metadata:
  type: feedback
---

`__main__.py`/`main()`-style "no automated test, live-process entrypoint" exemptions
(`aircraft-layer/src/collector/__main__.py`, `body-layer/src/logger.py`, `audio-adapter/src/
audio_adapter/__main__.py`) cover the argparse/server-boot wiring that genuinely can't run without
a live process. They do **not** automatically cover every class defined in the same file.

**Why:** `audio-adapter`'s `LocalPlaybackSink` (interrupted-vs-failed subprocess-kill bookkeeping)
lived inside `__main__.py` and inherited the exemption by co-location. It was ordinary
deterministic class logic — the same shape as aircraft-layer's tested `AudioPlaybackSender.
interrupt()` — and it shipped with a real concurrency bug (a single-slot "last interrupted
process" field that a second interrupt could clobber before the first was read) that a direct unit
test would have caught immediately. Reviewer found it live; the fix was to extract the class to its
own module and test it directly (`plans/inbound-speech/plan.md` Stage 3 follow-up, 2026-09-20).

**How to apply:** when a class in an entrypoint file has real branching/state logic (not just
argparse/wiring calls), ask whether it's actually untestable or just sitting next to something
that is. If it's testable, extract it to its own module and write the test — don't let it inherit
an exemption meant for something else. [[verify_full_suite_not_just_new_files]]
