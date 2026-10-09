# AC-B1 — Push-to-talk channel

- [x] **AC-B1 — Push-to-talk channel — implemented and ACCEPTED live 2026-09-23** #status/done (the voice sortie: the trigger works, and a radio call stays out of it).
  (`feature/inbound-speech-stage4`, `plans/inbound-speech/plan.md` Stage 5). `Export.lua` publishes
  the pilot stick trigger (arg 738) as its own line kind; `PttSample`/`PttCache`/`GET /ptt/state`
  carry it to the capture process. Wire version bumped to `2026-09-23a`.

  **Edge-driven at frame rate, not on the 5 Hz telemetry line.** A press behind that throttle could
  lose up to 200 ms off the front of an utterance, and the front is where the verb is. Sending only
  on change keeps a real trigger to two lines per press.

  **This layer decides nothing.** It reports the raw value; the predicates (`intercom`, `radio`)
  are conveniences on the sample, and the debounce that makes them usable lives in the consumer —
  because a full press *transits* the intercom stop for 19-32 ms, and a threshold that has to be
  tuned should not require copying a file into Saved Games to change.
