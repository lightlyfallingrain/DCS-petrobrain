# SRS Adapter — Roadmap

The process that turns Petrovich's text into sound the player actually hears. Everything audio
lives here: TTS synthesis, delivery to a playback target, and (next) injection into DCS-SRS's
intercom. Body-layer and the brain deal in text only and never see audio bytes — the split
`docs/concept/division-or-responsibility.md` settled and `plans/tts-voice-output/plan.md`
Decision 1 confirmed.

Why a separate subproject rather than part of aircraft-layer or body-layer: aircraft-layer's
contract is DCS I/O and body-layer's is belief state; neither should grow a TTS dependency. The
seam is HTTP end to end (body-layer → srs-adapter → aircraft-layer), so no new in-process
cross-subproject import exists — the body-layer↔world-model one remains the sole sanctioned
exception (root `CLAUDE.md`).

This subproject is BL-10's non-body half. See `body-layer/ROADMAP.md`'s BL-10 entry for the
body-side view and the slice numbering both files share.

## Status

- [~] **Slice 1 — outbound TTS.** **Stages 1-4 done 2026-09-17** (`plans/tts-voice-output/`,
  branch `feature/tts-voice-output`); stages 5-6 pending the user's hardware.

  - [x] **Stage 1 — synthesis + local playback.** `TTSEngine` protocol with one implementation,
    `MacSayEngine` (the `say` binary, an external CLI rather than a package dependency — this
    subproject is stdlib-only like its siblings), `POST /speak`, and `--target local` playing the
    result on the Mac via `afplay`. Runs with no other subproject, no Windows and no DCS, which is
    both the fastest way to audition voices and wording and the concrete answer to body-layer's
    "must be testable without a live sim" requirement applied to a feature whose whole payoff is
    hearing something.
  - [x] **Stage 2 — aircraft-layer playback channel.** `POST /audio/play` on the existing
    collector (JSON body, base64 WAV, matching the shape of `/text/push` rather than adding a
    second request-parsing path) and `AudioPlaybackSender`: one worker thread draining a queue,
    FIFO for routine lines, urgent lines clearing the queue and interrupting in-flight playback.
    The interrupt mechanism is isolated in a single function precisely because it is the part
    stage 5 is most likely to change.
  - [x] **Stage 3 — `--target aircraft-layer`.** POSTs synthesized WAV to a running collector.
    Verified against a real standalone collector on the Mac, including the expected non-Windows
    playback failure being logged and swallowed rather than crashing the chain.
  - [x] **Stage 4 — body-layer wiring.** `SrsAdapterClient` + `CrewConsole.speech_client` +
    `logger.py --speech-audio --srs-adapter-url`.
  - [ ] **Stage 5 — live Windows verification (needs the Windows box; does NOT need DCS).** Run
    the collector standalone on Windows with `srs-adapter --target aircraft-layer` on the Mac and
    confirm three things nothing so far can confirm: that `winsound.PlaySound` actually plays;
    that urgent preemption genuinely interrupts in-flight audio (the `SND_PURGE`/stop-then-play
    choice is this slice's main unverified bet); and whether the audio competes or ducks against
    other sound on the box.
  - [ ] **Stage 6 — live sortie acceptance (needs DCS).** Full `--crew-text --speech-audio` during
    a real flight. Judges what only a human can: whether ~0.6-0.8 s synthesis latency reads as
    crew-like rather than laggy, whether several callouts arriving in one poll queue acceptably,
    and whether the voice is tolerable. Acceptance, not a correctness gate — stage 5 already
    proves the pipeline.

- [ ] **Slice 2 — SRS ICS injection.** Not started. A second `AudioSink` invoking
  `DCS-SR-ExternalAudio.exe --modulations INTERCOM --unitId <player unit id>`, so Petrovich speaks
  on the intercom like a crew member instead of as a separate sound source.

  Groundwork is done: `research/2026-09-17-tts-audio-transport-recon.md` (**read its two addenda,
  which correct the main body**) establishes that stock SRS declares an Intercom radio for the
  Mi-24P at 100.0 MHz modulation 2, and that `--unitId` exists specifically to allow intercom over
  external audio.

  **ICS is the only acceptable target** (user constraint, 2026-09-17): the player must stay on the
  external mission frequency, and the Mi-24P's SPU-8 selects one audio source at a time, so a
  dedicated Petrovich frequency would compete with mission comms rather than layer beneath them.
  Frequency injection — the mechanism DATIS and MOOSE use, and the fallback the recon originally
  proposed — is therefore **rejected, not deferred**. If the live ICS test fails, this slice stops
  and slice 1's local playback is what ships.

  Open prerequisite: discovering the player's DCS unit ID at runtime. `--unitId` defaults to 1000
  and intercom scoping needs the real value, with no frequency-based escape hatch if it proves
  unobtainable. Likely already available through the aircraft layer's
  `LoGetWorldObjects`/`is_ownship` path — verify, do not assume.

  **Hard requirement (user, 2026-09-17): the player↔Petrovich channel must be available at all
  times, regardless of SPU-8 selector position.** Petrovich is the crew member sitting in front of
  the player; a crew intercom that goes silent because the pilot selected a radio is not a crew
  intercom. This is a *pass/fail property of the slice*, not a preference — if SRS can only deliver
  intercom audio when the selector happens to sit on an intercom position, SRS is the wrong
  transport for this and local playback (slice 1) remains the delivered capability.

  Reason for cautious optimism, unverified: in SRS, `_data.selected` governs *transmit*, not
  receive — a client normally hears every radio in its list. So intercom audio should reach the
  player irrespective of the SPU-8, but that must be confirmed live for this airframe rather than
  assumed from the general behaviour.

  Also unverified and worth a look at the same time: the Mi-24P's **intercom 1 / intercom 2 power
  switches**. The user's read is that one is likely the ground-crew intercom (the one the radio/ICS
  toggle selects) and the other an always-open pilot↔operator channel — which, if DCS models it and
  SRS exposes it, would be the natural home for this channel. Whether DCS models these switches at
  all, and whether SRS's Mi-24P export reads them, is unknown; `SR.exportRadioMI24P` as quoted in
  the recon reads only the selector at device 455 and the PTT at 738, which suggests it does not.

- [ ] **Slice 3 — inbound speech (STT + PTT).** Not started, and the larger half. Capture, PTT
  debounce, silence/noise gating and transcription all live here; body receives already-transcribed
  `PlayerUtterance` records and never sees audio. Signal-level gating is this subproject's;
  context-dependent suppression (e.g. tighter tolerance mid-engagement) is body's, acting on
  transcribed records (`plans/body-layer/plan.md` §1's responsibility table).

  **Hard requirement (user, 2026-09-17): a dedicated joystick PTT gates speech recognition.** STT
  must not run continuously — it listens only while the player deliberately holds a transmit
  button. Two reasons this is a requirement rather than an optimisation: an always-listening
  microphone turns every muttered word and every piece of room noise into a candidate command, and
  continuous transcription is the expensive part of the pipeline.

  Note the tension with the always-available requirement in slice 2 above, and resolve it
  deliberately rather than by accident: **outbound** (Petrovich → player) is always open, while
  **inbound** (player → Petrovich) is explicitly gated. They are not symmetric, and the PTT that
  gates inbound must be independent of the SPU-8 selector for the same reason the outbound channel
  is.

  Unresolved: where that PTT state is read from. Candidates, cheapest first — a DCS keybind whose
  state the aircraft layer already reads through its existing Export.lua channel (no new input
  stack, consistent with how F10 commands already arrive); SRS's own PTT (`_data.ptt`, device 738's
  two-stage trigger), which couples this to SRS and to the selector; or reading the joystick
  directly outside DCS, which is the most independent but needs an input library this project's
  stdlib-only rule does not currently allow. Decide during that slice's plan, with an Investigator
  pass if the DCS-keybind path's readability is not already established.

## Backlog

- [ ] **Voice character.** Currently a generic English voice. See `body-layer/ROADMAP.md`'s
  backlog entry for the full note — auditioning candidates costs one `--target local --voice <name>`
  command each.
- [ ] **Process supervision.** This is a third long-running process alongside body-layer's
  `logger.py` and aircraft-layer's collector, with no auto-start or health check — the same
  informal, manually-launched posture the other two already have. Worth revisiting once three
  processes become tedious to start by hand, not before.
- [ ] **`POST /audio/play` has no request-size cap** and, like every other endpoint on that LAN
  API, no auth. Same severity class as the existing overlay-text and search-trigger endpoints
  rather than a new category of exposure — recorded because the phase's security exemption may be
  revisited, not because anything here is newly wrong.

## Keeping this current

Same discipline as the sibling subprojects: this file is the source of truth for this
subproject's milestone status, and a merge is not finished until it reflects what merged (see
`.claude/skills/merge.md` and the root `ROADMAP.md`).
