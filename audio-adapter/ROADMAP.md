# Audio Adapter — Roadmap

The process that turns Petrovich's text into sound the player actually hears. Everything audio
lives here: TTS synthesis, delivery to a playback target, and (next) injection into DCS-SRS's
intercom. Body-layer and the brain deal in text only and never see audio bytes — the split
`docs/concept/division-or-responsibility.md` settled and `plans/tts-voice-output/plan.md`
Decision 1 confirmed.

**Renamed from `srs-adapter` on 2026-09-20** — DCS-SRS was dropped as a planned dependency for
outbound audio (Slice 1 already ships over `winsound` via the aircraft-layer collector, never a
DCS-SRS call), so the subproject name now matches what it actually does. See `CLAUDE.md`'s own
note for the full rationale; the "Next: SRS ICS injection" item below is unaffected — that is
still the plan for the real DCS-SRS product.

Why a separate subproject rather than part of aircraft-layer or body-layer: aircraft-layer's
contract is DCS I/O and body-layer's is belief state; neither should grow a TTS dependency. The
seam is HTTP end to end (body-layer → audio-adapter → aircraft-layer), so no new in-process
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
  - [x] **Stage 4 — body-layer wiring.** `AudioAdapterClient` + `CrewConsole.speech_client` +
    `logger.py --speech-audio --audio-adapter-url`.
  - [x] **Stage 5 — live Windows verification. Passed 2026-09-18**, after one real failure and a
    fix.
    - **Playback works.** `winsound` plays audio on the Windows box, cross-machine, end to end.
    - **Urgent preemption failed first time round.** A long routine line played stubbornly to its
      end, *then* the urgent line was heard, though the queue behind it was correctly discarded.
      Cause — and it is the exact bet the plan flagged: synchronous
      `PlaySound(path, SND_FILENAME)` blocks *inside* the Win32 call, and `SND_PURGE` from another
      thread cannot reach it, because Windows only purges sounds started asynchronously. The
      queue-clear appeared to work because it is pure Python and never touches the audio device,
      which is why the failure presented as partial rather than total.
    - **Fixed and re-tested green** (`fix/audio-urgent-interrupt`): the player starts the sound
      with `SND_ASYNC` and blocks on an interruptible `threading.Event` for the file's own duration
      (parsed from the WAV header) plus a margin; `stop` purges *and* sets that event. An urgent
      line now cuts a routine one off mid-word. The change stayed inside `_WinsoundPlayer` — no
      queue logic moved, which is the plan's decision to isolate the interrupt mechanism in one
      named function paying off exactly as intended.
    - **Still unobserved:** whether the audio ducks or competes against other sound on the box.
      Deferred rather than chased, because the SPU-8 volume argument below makes it largely an
      SRS-path question anyway.

  - [ ] **Stage 6 — live sortie acceptance (needs DCS).** Full `--crew-text --speech-audio` during
    a real flight. Judges what only a human can: whether ~0.6-0.8 s synthesis latency reads as
    crew-like rather than laggy, whether several callouts arriving in one poll queue acceptably,
    and whether the voice is tolerable. Acceptance, not a correctness gate — stage 5 already
    proves the pipeline.

- [>] **Slice 2 — cockpit state drives the audio. DEFERRED 2026-09-20** (user: *"Defer the SPU-8
  for now, let's come back to it later."*). Replaces the original SRS ICS injection, which is
  cancelled with the SRS dependency itself.

  **What it would do.** The intercom switch gates the crew channel in **both directions** — off
  means he cannot hear you and you cannot hear him, which is what the real switch does — and the
  SPU-8 volume knob sets how loud he is. One physical control turning Petrovich on and off, which
  is the cockpit-adjustable volume the SRS route was wanted for, reached by reading the controls
  instead of adding a dependency.

  **Two design notes worth keeping, so they are not re-derived:**
  - **`winsound` has no volume control.** `PlaySound` cannot attenuate, so the knob cannot be
    applied at playback — it has to scale the PCM samples before the WAV is played. That decides
    where it lives: the **collector**, which already holds the live cockpit state. The adapter
    should not need to know about knobs.
  - **Gating capture in the collector, not downstream.** With the intercom off, a push-to-talk press
    should not produce a clip at all, so neither the adapter nor the body layer has to reason about
    it.

  **Blocked on nothing but a decision to resume** — it needs device argument numbers for the switch
  and the knob, the same way push-to-talk needed arg 738, which is an investigator pass plus a probe
  on the Windows box.

  The original SRS groundwork is preserved in `research/2026-09-17-tts-audio-transport-recon.md`
  (read its two addenda, which correct the main body) — it established that stock SRS declares an
  Intercom radio for the Mi-24P at 100.0 MHz modulation 2. That finding stands as a record; it is
  simply no longer the route.

- [~] **Slice 3 — inbound speech (STT + PTT).** The larger half. **Next priority** (user,
  2026-09-19). Capture, PTT debounce, silence gating and transcription live here; body receives
  already-transcribed `PlayerUtterance` records and never sees audio. Full design:
  `plans/inbound-speech/plan.md`.

  - [x] **Stage 1 — the recognition bench. STOP/GO GATE: PASSED** (2026-09-19, user: *"this
    clears the gate"*). `stt_engine.py`, `vocabulary.py`, `tools/stt_bench.py`, plus
    `tools/record_corpus.py` for building the corpus.

    **99.2% top-1 on 252 clips of the user's own voice**, `ggml-small.en` with `--prompt`; the two
    remaining errors are both safe misses (no match → "say again"), not wrong commands.

    **Accent was never the limiting factor** — every gain came from tooling. 55.6% first run, but
    that was a recorder bug truncating 0.256s off every clip (sox's output buffer, discarded on
    terminate), which arrived at the bench dressed as an accent problem. 90.5% once recording was
    fixed, 98.4% with `--prompt`, 99.2% after collapsing whisper's repetition loops.

    Settled here, with full reasoning in `plans/inbound-speech/plan.md` and
    `research/2026-09-19-whisper-model-sweep.md`:
    - **`small.en`**, chosen on unsafe-error count rather than accuracy — lightest model with zero
      wrong-command errors (`tiny.en` seven, `base.en` two).
    - **`--prompt`, never `--grammar`**: a grammar cannot decline, so its failures are confident
      wrong commands (31.7%, including "watch nearest air defence" → "what do you see" at 0.82).
    - **Confidence bands are viable, but only prompted** — correct 0.82 vs both failures at 0.58
      and 0.66. This is what Stage 2's "say again" trigger should use.

    Vocabulary grew to 39 tokens during this stage: `report`/`stop`/`say again`, the wake word and
    `nevermind` for two-tier routing, and numeric bearings as a parsed slot with 5° resolution
    acting as a checksum on recognition.
  - [x] **Stage 2 — the matcher and the command path.** Merged 2026-09-20. The matcher moved to
    this subproject (plan's "Decision 4 REVISED"): body was going to hold a third hand-synced
    vocabulary copy, and whisper-specific normalisation — "180" for a spoken "one eight zero",
    repetition loops, "record" for "report" — is knowledge about the recogniser rather than about
    flying. Body keeps every decision with crew behaviour in it and still receives the raw
    transcript, so unmatched speech falls through to escalation unchanged.

    Review caught a real hole: whole-string scoring resolved "look at that" to a scan command at
    0.727, which would have executed. Fixed structurally rather than with a tighter floor —
    commands are word sequences, so score word sequences and count extra words against. Filler
    stripping followed, worth more than it looks because the ratio divides by the longer word
    count, so every unnecessary word depressed the score of the command meant.
  - [ ] Stage 3 — recognition as a service, and body-layer's inbound wiring.
  - [ ] Stage 4 — Windows capture.
  - [ ] Stage 5 — real PTT through DCS.
  - [ ] Stage 6 — live sortie acceptance.

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

## Backlog

- [ ] **Voice character — accent *and* prosody.** Currently a generic English voice. Two distinct
  problems, and the second was not obvious until it was heard aloud (user, 2026-09-18): no
  Russian-accented English voice exists in macOS `say`, **and the delivery is monotonous** — flat
  pitch and even stress regardless of whether the line is a routine contact report or "break
  right". Out of scope while the pipeline was being built; worth separating when picked up, since
  prosody may matter more for believability than accent does, and the two have different fixes
  (a different engine or voice for accent; SSML, per-line rate/pitch, or an urgency-aware
  template for prosody). Auditioning candidates costs one `--target local --voice <name>` command
  each. See `body-layer/ROADMAP.md`'s backlog entry.
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
