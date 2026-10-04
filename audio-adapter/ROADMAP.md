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
    - ~~**Still unobserved:** whether the audio ducks or competes against other sound on the
      box.~~ **ANSWERED 2026-09-26 (user): it behaves well — "no, this is good."** Judged in the
      air, not on a bench, which is the only place the question was ever answerable. No work
      follows, and the Stage 6 card need not carry it.

  - [x] **Stage 6 — live sortie acceptance. ANSWERED 2026-09-26 (user), never flown as a
    dedicated flight.** All three questions it existed to ask were settled across the sorties that
    were actually flown, which is why no Stage 6 card was ever completed — see also
    `docs/acceptance/2026-09-18-stage6-sortie.md`, closed the same way.

    - **Synthesis latency: not laggy.** *"< 1s is not laggy."* The lag a pilot actually feels is
      upstream, in speech-to-text, and it has its own entry (press-to-readback ~3 s) — so the
      number this stage was written to judge turned out not to be the number that matters.
    - **Several callouts in one poll: fine now.** Not because the queue was judged acceptable as
      built, but because flight feedback changed it — callouts are decided at speech time rather
      than queued ahead, and repetitive ones aggregate (`plans/callout-scheduling/`). The
      behaviour this stage would have graded no longer exists.
    - **Voice: survives, but monotonous.** *"Fine for now."* The monotony is real and already
      carried by the voice-character entry below (accent and prosody), where the finding is that
      prosody probably matters more than accent.
    - **Ducking against other sound on the box:** answered the same day, behaves well (above).

    Acceptance, not a correctness gate — stage 5 already proved the pipeline, and nothing here
    changed that.

- [x] **Hardening: per-source `--poll-hz` default + `Content-Length` guard — done 2026-09-26, merged `1a8795d`**
  (`fix/audio-adapter-review-findings`, no `plan.md` — scoped directly from the 2026-09-26
  whole-subproject performance and security reviews, `docs/reviews/`). `--ptt dcs` now defaults to
  30 Hz (`ptt_source.DEFAULT_DCS_POLL_HZ`, which the perf review found defined but wired to
  nothing) instead of the undifferentiated 60 Hz; `/speak` and `/transcribe` reject a
  missing/non-numeric/negative `Content-Length` with a clean 400 before any body read.

  Two review rounds, and the second one is the part worth remembering: round 1's negative-length
  regression tests passed against the pre-fix code too, because a pre-existing
  `read(length) if length > 0 else b""` already prevented the hang the security audit claimed —
  so they proved nothing. Round 2 asserted the specific rejection-path error message instead, and
  the wrong claim was corrected in place in `docs/reviews/security-audit-audio-adapter.md` rather
  than deleted. The real defect was the unhandled `ValueError` on a non-numeric value.

  **Live-acceptance debt:** the poll-rate halving has no in-cockpit observable and no CPU or
  frame-time measurement was ever taken, so nothing was gated on a sortie. Optional confirmation
  whenever the collector next runs with `--debug`: count `GET /ptt/state` lines over a fixed
  window, expect ~30/s rather than ~60/s.

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

  ~~**Blocked on nothing but a decision to resume** — it needs device argument numbers for the
  switch and the knob, the same way push-to-talk needed arg 738, which is an investigator pass plus
  a probe on the Windows box.~~ **The investigator pass is done (2026-09-20, read from
  `clickabledata.lua` on the Windows box). The slice stays deferred; only its prerequisite is
  gone.**

  | Arg | Control | Seat |
  |---|---|---|
  | 456 | Radio/ICS switch | pilot |
  | 457 | SPU-8 main volume knob (axis 0-1, step 0.05) | pilot |
  | 453 | SPU-8 radio volume knob | pilot |
  | 455 | Radio source selector, 6 pos at 1/5 | pilot |
  | 452 / 454 | Network 1/2 switch, circular call button | pilot |
  | 376 / 377 | SPU-8 NET-2 / NET-1 ON-OFF | pilot |
  | 738 | stick trigger: **1.0 = RADIO (LMB), 0.5 = ICS (RMB)**, 0.0 released | pilot |
  | 656-661 | operator mirror of 452-457 | operator |
  | **664** | **SPU-8 intercom power ON/OFF** | operator |
  | 856 | operator stick trigger, same 1.0/0.5 encoding | operator |

  **One thing to know before designing "intercom off means he cannot hear you": 664 is the only
  actual intercom *power* switch, and it is on the operator's panel** (`crew_member_access = 1`) —
  the player flying as pilot cannot reach it. The pilot's equivalent gating is 456 (Radio/ICS
  select) plus the 376/377 network switches, which is a different thing. Source and the full
  extraction: `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` finding 11.

  Still genuinely needing a live probe: the *values* these args report in flight (the table gives
  their declared ranges, not what `get_argument_value` returns mid-sortie).

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
  - [x] **Stage 3 — recognition as a service, and body-layer's inbound wiring.** Merged
    2026-09-20. `POST /transcribe` and `GET /transcripts/poll` on the existing server, a bounded
    transcript queue, `AudioAdapterClient.get_transcripts()`, and `--speech-input` on the logger.
    The seam carries **seven fields**, all required: `token=None` alone cannot distinguish "not a
    command" from "verb-anchored but unresolved" from "ambiguous", and those demand three different
    responses.

    **Acceptance was performed, not described:** real corpus WAVs POSTed to a running adapter, real
    whisper recognition, real band routing — no Windows, no DCS. One honest limit found and
    recorded: `logger.py`'s `--crew-text` poll loop never reaches `_poll_transcripts` until real
    telemetry arrives (`ConsolePerceptionRunner.run_once` short-circuits on `None`), so the full CLI
    path cannot demonstrate that claim even though its components do. Pre-existing, not introduced
    here.

    Two changes rode along, both reviewed:

    - **`stop` speaks nothing** (Decision 5 REVISED). It previously said "Copy.", which was not a
      stylistic slip but architecturally forced — there was no interrupt-only call anywhere, so the
      only way to reach the queue-clear was to push new urgent audio. Building that path
      (`POST /audio/stop`, `AudioSink.interrupt()`) took the audio side of a stop to **~6 ms**,
      which also answers the latency question the reviewer had flagged for Stage 6: the delay is
      recognition and dispatch, not the audio mechanism. A concurrency race in the
      interrupted-versus-failed flag was found in review and fixed by tracking processes by
      identity.
    - **Confidence and match ratio are gated independently** (Decision 4 REVISED AGAIN).
      `ACT_FLOOR = 0.60` was measured against the *confidence* distribution and applied to
      `confidence × match_ratio` — a product whose range is systematically lower than either
      factor. Four real clips run end to end put two in the confirm band, both barely under their
      floor. The fix points the constant at the quantity it was measured on, and gives the brain
      layer its **second route in**: speech heard clearly that matches no command is free speech,
      not a failure.
  - [x] **Stage 4 — capture. FLOWN AND ACCEPTED 2026-09-23.** Built 2026-09-22
    (`feature/inbound-speech-stage4`). Voice through the live path works: the clip is captured,
    recognised, dispatched and read back.

    `ptt_source.py` (`PTTSource` protocol, `JoystickPTT` over winmm, `KeyTogglePTT` for the Mac),
    `audio_capture.py` (`SoxRecorder`, `ClipGate`), `capture_loop.py` (`CaptureLoop`),
    `transcribe_client.py`, and `python -m audio_adapter.capture`.

    **Two deviations from the plan, both narrowing it:**
    - **sox, not `ffmpeg -f dshow`.** Part of Stage 4's stated job was discovering the dshow device
      name for the user's headset — but `tools/record_corpus.py` already recorded 252 corpus clips
      through that exact headset with sox, so the driver name, input-argument order, buffer size
      and truncation repair are all already settled against the hardware that matters. A second
      audio binary would have re-learned them and added a dependency.
    - **A real PTT, not the planned manual `--capture-window-s` trigger.** The stub existed to
      avoid a DCS dependency; a joystick button avoids it just as completely while being the
      actual gesture, so the trigger never has to be replaced — only the source behind the
      protocol, which is what Stage 5 does.

    **The joystick doubt is closed — probed on the Windows box 2026-09-23.** `joyGetPosEx` reports
    **four devices (ids 0-3)**, so a multi-device pit does appear under legacy ids rather than only
    the first controller, and a real press-and-hold on **device 2, button 0** was read cleanly at
    **613 ms held**. Both halves of the doubt answered at once: the API sees the hardware, and it
    reports a *held* state rather than an edge. Windows therefore gets the real gesture — hold to
    talk — where the Mac's keyboard source can only offer press-to-start/press-to-stop.

    Capture on that box is `--ptt joystick --joystick-device 2 --joystick-button 0`. Note the button
    is 0-based as the API and the probe report it; DCS's own binding UI numbers from 1, so this is
    "JOY_BTN1" there.

    **The finding worth carrying forward: the first ~0.14 s after a press is not captured.** sox
    returns from `Popen` in ~2 ms but the audio device is not open yet, and the loss is a fixed
    open cost, not a proportional one — four runs at holds from 0.6 s to 2.0 s lost 0.134-0.144 s
    every time. `record_corpus.py` solved the same thing with a 0.35 s preroll before prompting,
    which a PTT gate cannot do because the press *is* the prompt. Left uncorrected on purpose: the
    natural press-then-speak gesture leaves more than that, and the fix (a permanently hot mic with
    the pressed interval trimmed out of a rolling recording) costs continuous capture and file
    rotation to buy something no evidence yet says is needed. If Stage 6 shows first words clipped,
    that is the fix, and the measurement is recorded so it is not re-derived.

  - [x] **Stage 5 — real PTT through DCS. FLOWN AND ACCEPTED 2026-09-23.** Built the same day on
    `feature/inbound-speech-stage4` (stacked on Stage 4 at user direction, tested as one).

    **The sortie's four verdicts:** the trigger works; a radio call stays out of it; the two-stage
    trigger *"is natural"*; and the audio path is right. The one item not exercised is endurance —
    false-fire and miss rates over a whole flight — which needs a real sortie rather than a systems
    check.

    **One bug was found and fixed between building and flying, and it is the interesting part.**
    `push_ptt_state` was defined above `safe_call` in `Export.lua`, and Lua has no hoisting: a name
    referenced before its `local` declaration compiles as a *global* lookup, nil at call time. Every
    frame called nil, the trigger published nothing, and from the capture process's side that is
    indistinguishable from a talk control nobody pressed. `luac5.1 -p` passes it — the syntax is
    valid — so the syntax check cannot see this class at all. `Export.probe-ptt.lua` was run and arg 738 returned 0.5 held and 0.0 released on the
    user's own bound trigger, a 209 ms press was captured, and the value held across frames rather
    than pulsing. Crucially the *binding* was confirmed too — a DCS binding can be a game action
    that never animates the cockpit control, which would have left the argument right and still
    dead. Full addendum: `aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`.

    **Gate on the intercom stop specifically, not SRS's `>= 0.1`.** The full press is the player
    talking on the radio to someone else, and Petrovich has no business hearing it; the half press
    routes to intercom regardless of the SPU-8 selector, so this is also what the real aircraft does.

    **But `abs(v - 0.5) < 0.1` alone is not enough, and a second probe run proved it.** A full press
    *transits* the half stop for 19–32 ms on its way to 1.0 — it is a two-stage mechanical trigger,
    so it must. That bare gate would therefore open a capture on every radio call. Two mitigations,
    covering different cases: **debounce the 0.5 state by ~100 ms** (three times the observed worst
    transit, still far below any deliberate press-and-speak), and **treat a rise to 1.0 as an abort**
    of any capture in flight, which catches a slow full press that dwells past the debounce. The
    failure this prevents is silent — a discarded sub-threshold clip per radio transmission, which
    presents as an audio problem rather than a trigger one.

    **What was built.** `Export.lua` reads arg 738 every frame and sends `{"t":…,"ptt":…}` **only
    when it changes** — deliberately not on the 5 Hz telemetry line, because a press waiting behind
    that throttle could lose up to 200 ms off the front of an utterance, on top of the ~140 ms the
    audio device already costs to open, and the front of an utterance is where the verb is. A real
    trigger produces two lines per press, not a stream. `PttSample`/`PttCache` carry it,
    `GET /ptt/state` serves it, and `DcsPTT` implements the same `PTTSource` protocol the joystick
    already does. Wire version `2026-09-22b` → **`2026-09-23a`**.

    **The layer boundary is doing real work here.** `Export.lua` and the collector carry the raw
    value and decide nothing; the two thresholds and both mitigations live in `DcsPTT`, where they
    can be tuned and tested without copying a file into Saved Games. The endpoint still serves the
    decided booleans alongside the raw value, so a consumer that wants them need not re-derive two
    thresholds.

    **`discard_if` is a hook on `CaptureLoop`, not a new `PTTSource` method.** Only `DcsPTT` has
    anything to say about radio presses; widening the protocol would have made the joystick and
    keyboard sources carry a method that always answers False.
  - [x] **The ~0.14 s device-open gap — CLOSED 2026-09-23, not felt, nothing built.** The sortie
    answered it: press-then-speak *"is the natural, normal way how aviation radios work"*, and
    press-while-speaking *"works surprisingly well"* — the verb survives. So none of the three
    candidate fixes gets built, and the measurement's whole purpose is served: it stopped a fix
    being paid for before there was evidence it was needed.

    The options are kept below rather than deleted, because the gap is real and a different
    microphone or a slower machine could make it matter. **Do not build any of them without a
    fresh observation that it is felt.**

    **A. Open the device speculatively, on any press.** Start recording the moment arg 738 leaves
    0.0, and discard the clip if the trigger never settles at the intercom stop. **This is the
    strongest of the three, and for a reason that is easy to miss: it makes the 100 ms debounce
    free.** Today the two delays *add* — 100 ms of debounce, then ~140 ms of device open, so ~240 ms
    before a word can be captured. Opened speculatively they *overlap*: the device is warming during
    the debounce window, and by the time the trigger is confirmed as intercom the channel is already
    live. The saving is therefore larger than the 0.14 s figure suggests.

    Costs, both real: a sox process is spawned and killed on **every radio call** as well, so a
    device open/close cycle per ATC transmission — worth listening for an audible artefact on the
    user's own hardware, since a device that clicks on open would be trading one annoyance for
    another. And it needs a second signal out of `DcsPTT`: the capture loop currently sees only
    `is_down()`, which is the *decided* state; speculative opening needs "something is happening",
    which means exposing the raw value or adding a `pending()` alongside it.

    **B. A radio click as the cue.** A short click played on the press, timed so that **it ends as
    the channel goes live**. It does not remove the delay, it removes the *uncertainty* — and it
    teaches the press-then-speak gesture rather than asking the pilot to remember it, which is a
    better solution to a human problem than a faster machine would be. Cheap, and in-fiction: real
    PTT systems click.

    The timing property is load-bearing rather than decorative: a click that ends exactly when
    capture starts cannot be recorded by the capture, so it needs no special handling in the gate.
    A click that overlapped would appear at the front of every clip and be handed to whisper.

    **A and B compose**, and the combination is better than either: with the device opened
    speculatively the click can be shorter, because it only has to cover what remains.

    **C. A permanently hot microphone** with the pressed interval trimmed out of a rolling
    recording. Removes the gap completely and costs continuous capture, continuous disk writes and
    file rotation. Listed last deliberately: it is the most thorough and the least proportionate,
    and A gets most of its benefit for none of its running cost.

    **The gate is block 3 of the voice sortie** (`docs/acceptance/2026-09-23-voice-command-sortie.md`):
    press-then-speak versus speaking into the press. If the gap is not felt, none of these gets
    built.

  - [ ] **Press-to-readback is ~3 s, and that is the next real problem.** Measured on the
    2026-09-23 sortie (user: *"time from release to feedback is about 3 s"*). A crew member answers
    in well under a second, so this is what will keep him feeling like a machine no matter how good
    the recognition is.

    **One component is certain rather than estimated: the logger polls `GET /transcripts/poll` once
    per `poll_interval_s`, default 1.0 s**, so a recognised command waits 0 to 1 s — half a second
    on average — purely to be noticed. It is the cheapest half-second in the chain to remove, and
    it costs nothing but loopback HTTP requests.

    The rest of the budget is estimated and should be **measured before anything is optimised**:
    the 0.4 s tail (deliberate), sox's stop and `--ignore-length` re-encode, the LAN hop, whisper
    itself, and `say`'s synthesis (previously measured at 0.6-0.8 s). Every hop already carries a
    wall-clock stamp, so instrumenting this is reading timestamps rather than adding machinery.

    **Two candidate fixes that need no accuracy trade:**
    - **Poll transcripts faster than the telemetry cadence.** They are different jobs on the same
      timer today.
    - **Cache synthesized readbacks.** The readback vocabulary is small and fixed (*"Scanning
      left."*, *"Copy, stop scan."*), so the same handful of WAVs are re-synthesized every flight.

    **Not a candidate: a smaller whisper model.** `small.en` was chosen on unsafe-error count, not
    accuracy — `tiny.en` produced seven confident wrong commands and `base.en` two, against
    `small.en`'s none. Trading that for latency would buy speed with the one failure the pilot
    cannot catch.

  - [x] Stage 6 — live sortie acceptance. **Answered 2026-09-26 without a dedicated flight** — see
    the Slice 1 entry above for what each of its three questions turned out to be.

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

- [x] **`silence` command phrase wiring — DONE, merged with body-layer's `feature/silence-
  command` (tip `de6c530`).** `"silence"`/`"be quiet"`/`"shut up"` added to
  `vocabulary.VOICE_ONLY_TOKENS`/`PHRASES`, reachable through the existing `match_transcript` →
  `classify_response` → `handle_transcript` pipeline — no new ingress path, no `command_matcher.py`
  change. Bare `"quiet"` was in the original four-candidate set and was dropped after actually
  running the matcher: at a 0.889 `difflib.SequenceMatcher` ratio from the ordinary word
  `"quite"`, it would have false-anchored `"quite a nice day for flying today"` as a command
  (`VERB_ANCHOR_WORDS` is derived from each phrase's first word; see `body-layer/ROADMAP.md`'s
  entry and `NOTES.md` for the generalised lesson). Marked unbenched in `vocabulary.py`'s own
  comment, same convention as `cancel_scan`/`cancel_watch`. 219 passed/1 skipped,
  `ruff`/`mypy --strict` clean. **No live acceptance yet** — see `body-layer/ROADMAP.md`'s
  live-acceptance debt list, since this is reached only via the body-layer dispatcher and the two
  halves share one sortie's worth of verification.

## Backlog

Items here are `AA-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

- [ ] **AA-B1 — Voice character — accent *and* prosody.** Currently a generic English voice. Two distinct
  problems, and the second was not obvious until it was heard aloud (user, 2026-09-18): no
  Russian-accented English voice exists in macOS `say`, **and the delivery is monotonous** — flat
  pitch and even stress regardless of whether the line is a routine contact report or "break
  right". Out of scope while the pipeline was being built; worth separating when picked up, since
  prosody may matter more for believability than accent does, and the two have different fixes
  (a different engine or voice for accent; SSML, per-line rate/pitch, or an urgency-aware
  template for prosody). Auditioning candidates costs one `--target local --voice <name>` command
  each. See `body-layer/ROADMAP.md`'s backlog entry.
- [ ] **AA-B2 — Process supervision.** This is a third long-running process alongside body-layer's
  `logger.py` and aircraft-layer's collector, with no auto-start or health check — the same
  informal, manually-launched posture the other two already have. Worth revisiting once three
  processes become tedious to start by hand, not before.
- [ ] **AA-B3 — `POST /audio/play` has no request-size cap** (and neither do audio-adapter's own
  `/speak`/`/transcribe`/`/stop`, per the 2026-09-26 security audit's RECOMMENDED #1 — the same
  standing exemption covers them explicitly rather than by assumption) and, like every other
  endpoint on that LAN API, no auth. Same severity class as the existing overlay-text and search-trigger endpoints
  rather than a new category of exposure — recorded because the phase's security exemption may be
  revisited, not because anything here is newly wrong.

## Keeping this current

Same discipline as the sibling subprojects: this file is the source of truth for this
subproject's milestone status, and a merge is not finished until it reflects what merged (see
`.claude/skills/merge/SKILL.md` and the root `ROADMAP.md`).
