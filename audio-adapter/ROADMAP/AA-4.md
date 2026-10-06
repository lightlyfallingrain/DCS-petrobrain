# AA-4 — Slice 3 — inbound speech (STT + PTT)

- [~] **Slice 3 — inbound speech (STT + PTT).** #status/in-progress The larger half. **Next priority** (user,
2026-09-19). Capture, PTT debounce, silence gating and transcription live here; body receives
already-transcribed `PlayerUtterance` records and never sees audio. Full design:
`plans/inbound-speech/plan.md`.


Stages: [[AA-4.1]] [[AA-4.2]] [[AA-4.3]] [[AA-4.4]] [[AA-4.5]] [[AA-4.6]] [[AA-4.7]] [[AA-4.8]]

**Settled before design (user, 2026-09-19):**

1. **Capture is on Windows, and that is not a choice.** The headset boom mic plugs into the
   Windows box only. So audio capture happens there regardless of where recognition runs.
2. **Recognition uses whatever the host it runs on offers — Mac preferred, Windows required.**
   *"When on windows, use windows tools. When on mac, use Mac tools. I will prefer Mac, but it
   must work on windows as well."* This is the same shape `audio-adapter`'s `TTSEngine` protocol
   already has (`MacSayEngine` today, a `WindowsSapiEngine` droppable beside it), so an
   `STTEngine` protocol mirrors a pattern this subproject already proved.
3. **Therefore a transit is needed** — *"A transit is needed"* — carrying captured audio from the
   Windows box to the Mac. This is the **inverse of a path that already exists**: WAV already
   travels Mac → Windows over `POST /audio/play`. The return direction should look like it rather
   than inventing a second audio-transport idiom.
4. **Start with the constrained command set; free-form comes with the brain layer.** Design must
   not foreclose it, but nothing should be built for it yet.
5. **Readback is the confirmation mechanism**, because *"readback is standard in aviation for
   exactly this reason"* — short, but carrying enough to catch a mishearing. Note this is
   **already built**: `speech.render_readback`, `render_scan_readback`,
   `render_cancel_readback` and `render_watch_nearest_readback` exist from BL-5a and the F10
   work. Slice 3 wires recognition into an existing confirmation loop rather than designing one.

**The accent constraint, and why it is tractable here.** The user has a Finnish accent, and
Windows speech recognition has consistently failed it — *"wrong words that made the whole service
not very useful"* (with Intentions AI ATC). Note the failure mode: **wrong words, not silence.**
The recogniser heard speech and produced the wrong tokens, which is the failure open dictation
makes and a closed vocabulary largely does not. The existing F10 set is **15 tokens**
(`scan_ahead`, `scan_left`, `scan_right`, `scan_full`, eight `scan_bearing_*`, `watch_nearest`,
`watch_nearest_air_defence`, `cancel_task`), which makes this a *classification over a tiny
closed set*, not transcription. Two cheap mitigations follow from that and should be evaluated
in design: biasing the recogniser toward the command vocabulary, and fuzzy-matching whatever
comes back to the nearest known token, so *"scan lift"* resolves to `scan_left` rather than
failing. Neither helps free-form later, which is another reason to keep the two phases distinct.

**Unchanged from earlier decisions:** a dedicated joystick PTT gates recognition so it never runs
continuously (user, 2026-09-18), read through the aircraft layer's existing Export.lua channel;
and **inbound bypasses SRS entirely** — this slice does not depend on intercom injection ever
working.
