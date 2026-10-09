# BL-B36 — Speech-log retention, declined

- [x] **BL-B36 — DECLINED 2026-10-08 by user direction: the finding's premise was wrong.** #status/done The log
  is not a transcript of the room, it is a transcript of deliberate keyed transmissions into a
  close-talking microphone:

  > *"Audio only captures when I key the PTT. And the microphone is close to my mouth, does not pick
  > ambient that well. Ignore, keep as it is now."*

  So `"Peace."` / `"All right."` / `"Can I sell it?"` are the pilot speaking **on the intercom**,
  which is exactly what the log exists to record. No hashing, no opt-in, no change. Closed as
  declined-with-reason rather than deferred: the privacy exposure rests on ambient capture the
  hardware does not do. **The audit was right to raise it and wrong about the mechanism** — worth
  noting as a case where only the person holding the microphone could settle it.

  Original finding, kept for the record: **the speech log is a verbatim transcript of everything the
  microphone heard, including speech never addressed to Petrovich.** 2026-10-05 security audit. The 2026-10-05 sortie
  log contains `"Peace."`, `"All right."`, `"Can I sell it?"` — the pilot talking, not commanding.
  Harmless on this machine; this repo is **intended to go public open-source**, and a shared or
  committed log is a voice transcript of someone's living room. Wanted: either hash/omit
  non-command utterances, or make the log opt-in with that stated in `RUN.md`.
