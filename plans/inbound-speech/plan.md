### Goal

Let the player speak Petrovich's existing 15-token command vocabulary into a PTT-gated microphone
on the Windows box and have it drive the command dispatch and readback path that already exists —
audio captured on Windows, recognised on the Mac, delivered to body-layer as text only.

This is `srs-adapter` Slice 3. The brief is `srs-adapter/ROADMAP.md`'s Slice 3 entry; its five
settled points are taken as given and not re-argued here.

---

### Effort/value check — read this before the stages

This is the largest remaining piece of BL-10 and it is worth building, but **only in the order
below**, and with two things explicitly refused.

**The single assumption everything rests on:** that a recogniser can map this user's
Finnish-accented English onto a 15-token closed set reliably. Nothing else in this slice matters
if that is false — no transit, no PTT, no capture process. It is also, uniquely, the assumption
that is *cheapest* to test: it needs a folder of recorded WAVs and a binary on the Mac. No
Windows, no DCS, no HTTP, no body-layer change.

**So Stage 1 is a bench, and it is a stop/go gate.** If top-1 token accuracy on the user's own
voice is not good enough for him to want to fly with it, this slice stops there having cost one
tool script and a recording session, and F10 remains the command surface. Every later stage
assumes Stage 1 passed. Building transit or PTT before that number exists would be building the
plumbing for a tap that may not turn on.

**Why the value is real despite the risk:** the failure mode the user hit before (Intentions AI
ATC) was *open dictation* — an unbounded language model picking wrong words from a vocabulary of
tens of thousands. This is classification over 15 tokens with three legal first words. Both the
recogniser's own constrained-decoding support and a post-hoc nearest-token matcher attack exactly
that. It is a materially different problem from the one that failed, and that is the reason to
expect a different outcome — not optimism.

**Refused now, deliberately:** free-form speech and multi-slot commands ("watch that Shilka by the
road"), wake-word/always-on listening, barge-in (interrupting Petrovich mid-sentence), and any
speaker-adaptation/fine-tuning workstream. The first belongs to the brain layer; the rest are
their own milestones. See "Deferred to the brain layer" at the end for what must not be foreclosed.

---

### Affected Modules / Files

**New — `srs-adapter` (recognition, Mac side):**

- `srs-adapter/src/stt_engine.py` — `STTEngine` protocol (`transcribe(wav: bytes) -> Transcript`)
  plus `WhisperCliEngine` and `WindowsSpeechEngine`. Mirrors `tts_engine.py` exactly: a `Protocol`
  with one method, one exception type (`STTRecognitionError`), implementations that shell out to an
  **external binary, never a package** (`srs-adapter/CLAUDE.md` "Tech stack", binding here).
  `Transcript` is a frozen dataclass: `text: str`, `confidence: float`, `engine: str`.
- `srs-adapter/src/transcript_queue.py` — bounded FIFO of `Transcript` records awaiting body-layer
  collection. Structural copy of `aircraft-layer`'s `collector/cache.py::F10CommandQueue`.
- `srs-adapter/tools/stt_bench.py` — Stage 1's offline bench (a `tools/` script, not pipeline code;
  this is the first `tools/` dir in this subproject, matching `world-model/tools/`'s role).
- `srs-adapter/src/vocabulary.py` — the recogniser **bias hint list**: the spoken phrases the
  engines steer toward. Adapter-local by necessity (module independence: `srs-adapter` cannot
  import body-layer). Hand-synced with body-layer's phrase table, the same documented hand-sync
  `aircraft-layer`'s `ALLOWED_COMMANDS` already has with the Hook script's menu — cite that
  precedent rather than inventing a shared-constants mechanism.

**New — `srs-adapter` (capture, Windows side):**

- `srs-adapter/src/srs_adapter/capture/__main__.py` — `python -m srs_adapter.capture`, the
  Windows-side capture process. Owns the microphone, PTT gating, debounce and the silence/energy
  gate. Never talks to body-layer.
- `srs-adapter/src/audio_capture.py` — `AudioCapture` protocol + `FfmpegCapture` (external binary,
  `ffmpeg -f dshow` on Windows / `-f avfoundation` on the Mac for dev), `ClipGate` (duration
  debounce + RMS energy floor), `CaptureClipQueue` (bounded, drain-one-on-GET).
- `srs-adapter/src/capture_server.py` — `GET /capture/poll` on the Windows capture process.
- `srs-adapter/src/capture_client.py` — Mac-side poller that drains `/capture/poll` and feeds the
  `STTEngine`. Sibling of `aircraft_client.py` in the same subproject.

**Changed — `srs-adapter`:**

- `srs-adapter/src/server.py` — two new routes beside `POST /speak`: `POST /transcribe` (base64 WAV
  in, transcript out — the direct, testable recognition entry point) and `GET /transcripts/poll`
  (drain-on-GET, body-layer's inbound channel). Same request-parsing and error shape as `/speak`.
- `srs-adapter/src/srs_adapter/__main__.py` — new flags: `--stt-engine whisper|windows`,
  `--whisper-binary`, `--whisper-model`, `--capture-url`, `--speech-input`.
- `srs-adapter/CLAUDE.md`, `srs-adapter/ROADMAP.md` — structure/status updates.

**Changed — `body-layer` (text only, never audio):**

- `body-layer/src/belief/voice_commands.py` (new) — the transcript→token matcher. Owns the phrase
  table, normalisation, fuzzy matching, the confidence bands and the pending-confirmation state.
  This is body's job, not the adapter's: `plans/body-layer/plan.md` §1 gives the adapter
  *signal-level* gating (duration, energy) and body everything semantic.
- `body-layer/src/belief/crew_console.py` — one new public method, `handle_transcript(text,
  confidence, now_sim) -> list[str]`, a sibling of `handle_line`/`handle_f10_command`. It routes;
  it does not reimplement. (`plans/f10-crew-commands/plan.md`'s own second-order note predicted
  exactly this third entry point and is why `handle_f10_command` was made a sibling rather than
  folded into `handle_line`.)
- `body-layer/src/belief/speech.py` — two new renders: `render_say_again()` and
  `render_confirm_request(description)`. The four existing `render_*_readback` functions are
  **reused unchanged**.
- `body-layer/src/belief/srs_client.py` — `get_transcripts()`, mirroring
  `aircraft_client.get_f10_commands()`.
- `body-layer/src/logger.py` — `--speech-input`, and a `_poll_transcripts` sibling of
  `_poll_f10_commands` inside the existing `--crew-text` background poll thread.

**Changed — `aircraft-layer` (PTT signal only, no audio):**

- `aircraft-layer/dcs-export/Export.lua` — publish PTT state (`get_argument_value(738)`) in the
  telemetry sample. `aircraft-layer/dcs-export/Export.probe-ptt.lua` already exists, written by the
  investigator, and is Stage 5's first step — run it before editing `Export.lua`.
- `aircraft-layer/src/schema.py`, `src/collector/cache.py`, `src/api/server.py` — carry that field
  and expose `GET /ptt/state`. **Stage 5 only** (see Decision 3).

**Not changed:** `body-layer/src/belief/utterance.py` and `escalation.py`. `parse_utterance` stays
exactly as it is and keeps serving the typed path; `PlayerUtterance.source` already has a
`"srs_ics"` literal and `ReasonEscalated` already has `low_stt_confidence` — both were written for
this slice and are used, not redefined. **Implementer: verify both still read that way before
relying on it.**

---

### Decision 1 — the `STTEngine` protocol and its two implementations

```python
class STTEngine(Protocol):
    def transcribe(self, wav: bytes) -> Transcript: ...
```

One method, WAV bytes in, `Transcript` out, `STTRecognitionError` on failure. Deliberately the
mirror image of `TTSEngine.synthesize(text) -> bytes`. Engines write their input to a temp file and
shell out, exactly as `MacSayEngine` does — neither candidate binary reads WAV from stdin reliably.

**`WhisperCliEngine` — the preferred implementation, on both hosts.**

Shells out to whisper.cpp's `whisper-cli` binary with a GGUF/GGML model file:

```
whisper-cli -m <model.bin> -f <clip.wav> -l en -oj -of <out> --grammar <vocab.gbnf> --no-timestamps
```

Chosen over macOS's own on-device recognition for three concrete reasons, not a general preference:

1. **It is a binary; Apple's is not.** macOS on-device recognition is `SFSpeechRecognizer` in the
   Speech framework — an Objective-C/Swift API with no shipped CLI. Driving it from a subprocess
   means writing and compiling a Swift helper and carrying a Cocoa build step in a stdlib-only
   subproject. That is a worse dependency than a downloaded binary, not a better one, and it
   violates the external-binary rule in spirit (we would be the ones building the binary).
2. **Accent robustness is the whole point, and Whisper's training set is the argument.** It is
   trained on large volumes of accented, non-native English; Apple's dictation is tuned for
   native-speaker locales and exposes no knob beyond `contextualStrings`. Given the user's specific
   history this is the deciding factor.
3. **It supports constrained decoding.** whisper.cpp accepts `--grammar` (GBNF) with
   `--grammar-penalty`, which restricts the decoder to a generated grammar of exactly our phrase
   set. That converts the task from transcription to classification *inside the recogniser* — the
   strongest form of the vocabulary-biasing mitigation the roadmap asks for. `SFSpeechRecognizer`
   has no equivalent; `contextualStrings` is a soft hint only.

The same binary has Windows builds (CPU, and Vulkan/CUDA), so `WhisperCliEngine` is one class
serving both hosts — the engine-per-host split in the roadmap's point 2 is honoured by *binary
availability*, not by needing two Python classes. `--whisper-binary`/`--whisper-model` are paths,
supplied by whoever starts the process.

**Stage 1 must record whether `--grammar` actually helps or hurts.** Constrained decoding can force
a confident wrong answer where free decoding would have produced obvious garbage, which is worse
for a confidence floor. Bench both modes and pick from the numbers, don't assume.

**`WindowsSpeechEngine` — the required Windows baseline, zero install.**

Shells out to `powershell.exe -NoProfile -Command <script>` driving
`System.Speech.Recognition.SpeechRecognitionEngine`: `SetInputToWaveFile(clip)`, a grammar built as
`new Grammar(new GrammarBuilder(new Choices(<our phrases>)))`, `Recognize()`, emitting
`RecognitionResult.Text` and `.Confidence` as JSON. `powershell.exe` is an OS-shipped external
binary — no download, no package, consistent with the rule.

**Is this better than what already failed the user? Yes, and for a specific reason.** Intentions AI
ATC used open dictation. `System.Speech` with a `Choices` grammar is a different mode of the same
stack: the recogniser can only emit strings the grammar admits, and `.Confidence` is then a
meaningful posterior over 15 options rather than over the language. It is a genuinely different
configuration, not the same thing retried. It is still the *fallback*, because whisper.cpp's
acoustic model is the stronger one for accented speech and because the bench will have numbers for
both.

**Not used: `System.Speech`'s dictation grammar, Azure/cloud speech, or any pip package.** The
first is the known failure; the second breaks offline operation and adds per-utterance latency on
a path that must feel like an intercom.

---

### Decision 2 — the audio transit: Windows captures, Mac recognises, **the Mac polls**

Direction: Windows → Mac. Format: **16 kHz mono 16-bit PCM WAV**, base64 in a JSON body — whisper's
native input rate, converted by `ffmpeg` at capture time so no resampling code exists anywhere in
Python. This mirrors `POST /audio/play`'s `{"audio_b64", ...}` shape rather than inventing a second
audio-transport idiom, as the roadmap requires.

**Who initiates: the Mac polls `GET /capture/poll`, oldest clip first, draining one clip per call.**

- Every cross-machine flow in this project already has **Mac as client, Windows as server** —
  body-layer polls `/telemetry/latest` and `/f10_commands/poll`, `srs-adapter` POSTs `/audio/play`.
  A push from Windows would be the first flow requiring the Windows box to know and hold the Mac's
  address, and the first that breaks when the Mac process restarts mid-sortie. Polling degrades to
  "nothing happened for a while"; pushing degrades to lost clips and a dead socket.
- `GET /f10_commands/poll` is the established **inbound** idiom and is the exact precedent:
  drain-on-GET, bounded queue, one documented poller, `[]`/`null` when empty rather than `503`.
  Copy its contract including the single-poller caveat.
- Latency cost is one poll interval. Poll at 250 ms (the same order as the F10 loop) and it is
  invisible next to ~1 s of speech plus recognition.

**Where capture lives: a second `srs-adapter` process on Windows, not inside the collector.**

The collector is the tempting host — it already runs on Windows, already has an HTTP server, a
queue pattern, and an audio precedent in `audio_sender.py`. It is rejected because
`docs/concept/division-or-responsibility.md` is explicit that the **SRS adapter owns the audio
boundary** and that **raw audio never leaves it**, while the aircraft layer's contract is DCS I/O.
A microphone is not DCS, and shipping raw microphone audio across the aircraft layer's public LAN
API would put raw audio on a seam the concept doc says it must never cross. Keeping capture inside
`srs-adapter` means the raw audio hop is adapter→adapter, which is internal to the component that
is defined to own it. `audio_sender.py`'s playback-in-the-collector precedent is a weaker case
(synthesised output, not a live mic) and should not be extended.

The cost is honest and should be stated: **a fourth long-running process to start by hand**, which
sharpens `srs-adapter/ROADMAP.md`'s existing "Process supervision" backlog item. That item becomes
worth doing after this slice, not before.

**Why not recognise on Windows and ship only text (no transit at all)?** It is the simplest option
and worth naming, but the Windows GPU is saturated by DCS during a sortie — recognition there is
either CPU-bound or stealing frames from the sim, while the Mac sits idle. That, plus the user's
stated Mac preference, is why the transit exists. The architecture still permits it: pointing
`--capture-url` at a local capture process and running the engine in the same box is a
configuration, not a rewrite. Keep that true.

---

### Decision 3 — PTT

A dedicated joystick button, held while speaking, read through Export.lua. Never always-on. Already
settled by the user (2026-09-18); this plan does not reopen it.

**The open question the earlier work recorded — now resolved.** Every player-input signal this
project reads today is a **discrete event** (the F10 menu, via `petrobrain-f10-commands-hook.lua` →
UDP → `collector/f10_command_receiver.py`), and whether Export state could read a **held button
state** at all had never been verified. An investigator pass run during this planning session
answers **yes**:
`aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`. The three findings that matter:

1. **The read mechanism is already proven in this codebase.**
   `GetDevice(0):get_argument_value(<arg>)` is the exact call already used live for the 9K113 sight
   azimuth readback (arg 874). No new capability is needed — this is an additional argument on a
   call that already works.
2. **Arg 738 is the pilot PTT trigger and reads as a graduated held value**, not an edge pulse:
   `0.0` released, `~0.5` half-press, higher on full press. Sourced from DCS-SRS's own shipped
   `Mi24P.lua` exporter (`SR.getButtonPosition(738)` *is* that same call), cross-validated because
   two other args in that file (455 SPU-8 selector, 456 hot-mic) match this project's own
   primary-source clickabledata dump from the installed 2.9.29.27278 tree.
3. **Tick rate is per-frame, not the 5 Hz telemetry rate.** `LuaExportAfterNextFrame` runs every
   DCS frame (~8 ms measured previously). A press would have to be shorter than one frame to be
   missed, which a deliberate press-and-speak gesture never is.

**Still unconfirmed:** arg 738's actual values on this specific install. The investigator left a
ready-to-run probe, `aircraft-layer/dcs-export/Export.probe-ptt.lua` — deploy as `Export.lua`, fly
its six header steps, return `Logs\aircraft_layer_probe_ptt.log`. **That probe is Stage 5's first
step**, and it is a ten-minute sortie task, not a research project.

**A design option this opened, worth weighing (Decision list item 3).** Arg 738's *half-press*
selects intercom specifically, independent of the SPU-8 selector — so the trigger the player
already has could serve as the Petrovich PTT with **no new joystick binding at all**, and without
reopening the settled "must stay on mission frequency" constraint. That is cheaper than binding a
spare control, but it overloads a control that also transmits on SRS. The user's call.

**The fallback, retained but now unlikely to be needed:** one `listen` F10 token opening a fixed
listening window, reusing the event path that already works end to end. Keep it in mind only if the
live probe falsifies arg 738. (The investigator also confirmed a stdlib-only Windows joystick read
via `ctypes`/`winmm.dll`'s `joyGetPosEx` exists as a genuine non-package option — but it bypasses
DCS's own half-press-vs-full-press modelling and duplicates what arg 738 gives for free. Not
recommended.)

**No pre-roll buffer.** The per-frame tick rate makes leading-edge clipping a non-issue anyway, but
the rule stands for a second reason: a rolling always-filling audio buffer is a hot mic, which the
"never always-on" constraint forbids. Press, *then* speak — standard radio discipline. Document it
in `RUN.md`; do not build the buffer.

---

### Decision 4 — how recognition output becomes a command

Three layers, each attacking "wrong words, not silence" at a different point.

**Layer 1 — bias the recogniser (adapter side).** whisper.cpp `--grammar` generated from
`vocabulary.py`'s phrase list; `System.Speech` `Choices` grammar from the same list. Where this
works the recogniser cannot emit a non-vocabulary string at all.

**Layer 2 — the matcher (body side, `belief/voice_commands.py`).** Concretely:

1. **Normalise.** Lowercase; strip punctuation; collapse whitespace; apply a small explicit
   substitution table for number/direction words the recogniser garbles predictably (populated
   from Stage 1's *observed* confusions, not guessed — an empty table on day one is correct).
2. **Verb anchor, and it fires first.** The first normalised word must match one of
   `{scan, watch, cancel}` (plus the affirmative/negative words below) at a `difflib.SequenceMatcher`
   ratio ≥ `VERB_FLOOR`. **If no verb anchors, nothing matches — full stop, no scoring of the
   rest.** This is the single most important line of defence: it is what stops arbitrary
   misrecognised speech from resolving to *some* command. Same posture as
   `belief/utterance.py`'s documented "fails loudly and cheaply, never guesses", and deliberately
   the same shape so the two paths behave alike.
3. **Phrase match.** A flat `dict[str, str]` of spoken phrase → F10 token, several phrasings per
   token (`"scan left"`, `"look left"`, `"scan to the left"` → `scan_left`; `"scan northeast"`,
   `"scan zero four five"` → `scan_bearing_ne`). Exact hit ⇒ ratio 1.0. Otherwise
   `difflib.get_close_matches(normalised, table.keys(), n=3, cutoff=MATCH_FLOOR)` — stdlib, no
   dependency, and its ratio is inspectable and explainable in a log line, which matters when the
   user is diagnosing a mishearing mid-session.
4. **Separation check.** If the best and second-best candidates map to **different tokens** and
   their ratios differ by less than `SEPARATION_MIN`, the result is *ambiguous* regardless of how
   high either ratio is. "Scan left" vs "scan right" landing 0.88/0.85 must not silently pick one.
   Ambiguous is treated as the confirm band, never as a match.
5. **Combine:** `combined = stt_confidence * phrase_ratio`.

**Layer 3 — the confidence bands. What happens at the floor is different in each band, and none of
them is a silent best guess:**

| Band | Behaviour |
| --- | --- |
| `combined ≥ ACT_FLOOR` | Execute, then read back (Decision 5). |
| `CONFIRM_FLOOR ≤ combined < ACT_FLOOR`, or ambiguous | **Do not execute.** Speak an interrogative readback — `render_confirm_request("scan left")` → *"Scan left, confirm?"* — and hold the pending command for `CONFIRM_WINDOW_S`. The next utterance resolving to affirm/negative commits or discards it; anything else, or the timeout, discards silently. |
| `combined < CONFIRM_FLOOR` | Nothing fires. Speak `render_say_again()` — *"Say again?"* — once. Never a guess. |

`"affirm"`/`"affirmative"`/`"yes"`/`"roger"` and `"negative"`/`"no"`/`"disregard"` join the phrase
table as two pseudo-tokens, valid **only** while a confirmation is pending — outside that window
they resolve to nothing, so a stray "yes" never does anything.

**Silence and "say again" are different answers to different questions.** A clip the adapter's gate
rejected (too short, too quiet) never reaches body at all and produces **no speech whatsoever** —
the player did not speak, so Petrovich has nothing to answer. "Say again" is only for a clip that
*was* speech and *was not* understood. Conflating them would make Petrovich chatter at every
accidental trigger-brush.

**All five constants live together, named, at the top of `voice_commands.py`** — `VERB_FLOOR`,
`MATCH_FLOOR`, `SEPARATION_MIN`, `CONFIRM_FLOOR`, `ACT_FLOOR` (plus `ACT_FLOOR_CANCEL`,
`CONFIRM_WINDOW_S`) — **and every one of them is set from Stage 1's measured distribution, not
guessed.** That is the bench's second deliverable and the reason it must come first. The
implementer should ship Stage 2 with the bench's numbers in a comment next to each constant.

---

### Decision 5 — where readback fits, and what happens when it is wrong

**Above `ACT_FLOOR`: execute, then read back.** Reasons: it is what `handle_f10_command` already
does (the readback lines are its return value), so one code path serves both input surfaces; and
every command in this vocabulary is *constructive and reversible* — a scan or a watch that was
misheard is corrected by saying the right one, at the cost of a few seconds of Petrovich looking
the wrong way. Confirm-before-act on every command would add a round trip to every single
interaction and would quickly feel like arguing with a machine rather than talking to a crewman.

**The readback already carries enough to catch a mishearing** — this is a property of the existing
renders, not something to add: `render_scan_readback` speaks the sector (*"Scanning to the left"*,
audibly distinct from *"...to the right"*), `render_watch_nearest_readback` names unit type, clock
and range, `render_cancel_readback` names *what* was cancelled. Nothing speaks a bare token id.
That satisfies the user's "short, but enough to catch a mishearing" steer with zero new speech.

**`cancel_task` is the one exception, and it gets a higher bar, not a different mechanism.** It is
the only token that **destroys** state rather than creating it: mishearing *into* it silently kills
a standing task, and its readback naming what was cancelled arrives *after* the task is already
gone — the one case where execute-then-readback tells you about a loss instead of letting you
correct it. So `cancel_task` uses `ACT_FLOOR_CANCEL > ACT_FLOOR`, which simply routes marginal
cancels into the confirm band that already exists. One extra constant, no second code path, and the
asymmetry is justified by the direction of the damage rather than by aviation analogy.

---

### Decision 6 — module boundaries: exactly what crosses each seam

| Seam | Direction | Payload | Notes |
| --- | --- | --- | --- |
| DCS Export.lua → collector | in-process/loopback | `ptt_down: bool` on the existing telemetry sample | One boolean. No audio ever. Stage 5. |
| collector → capture process | loopback HTTP | `GET /ptt/state` → `{"ptt_down": bool, "t": float}` | Windows-local. The capture process does its own edge detection and debounce. |
| capture process → `srs-adapter` | LAN HTTP, **Mac polls** | `GET /capture/poll` → `{"clip": {"audio_b64", "duration_s", "t_wall"}}` or `{"clip": null}` | The only raw-audio hop, and it is adapter-internal. |
| `srs-adapter` → body-layer | LAN HTTP, **body polls** | `GET /transcripts/poll` → `[{"transcript": str, "confidence": float, "t_wall": float}]` | **Text only.** Body-layer never sees audio bytes, never sees a WAV path, never learns which engine ran. |
| body-layer internal | — | `CrewConsole.handle_transcript(text, confidence, now_sim)` → `list[str]` | Routes to `handle_f10_command` on a match; otherwise the existing `handle_line`/`parse_utterance`/escalation path, unchanged. |

**The gating split follows `plans/body-layer/plan.md` §1 exactly.** Signal-level (clip shorter than
`MIN_CLIP_S`, RMS below `ENERGY_FLOOR`) is the **adapter's** and happens before anything crosses to
body. Anything context-dependent — suppressing a command mid-engagement, say — is **body's**, acts
on already-transcribed text, and is **not built now**.

**The unmatched branch deliberately falls through to the existing text path.** A transcript that
anchors no verb is handed to `handle_line`, which runs `parse_utterance` and escalates exactly as
a typed line does. That costs nothing, keeps one behaviour for text regardless of how it arrived,
and is the hook the brain layer plugs into later.

---

### Implementation Plan

Each stage is independently mergeable and leaves the system working. **[Mac]** = verifiable on the
Mac alone. **[Win]** = needs the user's Windows box. **[Sortie]** = needs DCS flying.

**Stage 1 — the recognition bench. [Mac] — STOP/GO GATE.**
`stt_engine.py` (`STTEngine` + `WhisperCliEngine` + `WindowsSpeechEngine`), `vocabulary.py`, and
`tools/stt_bench.py`. The user records a corpus of his own voice — every one of the 15 tokens
several times, in a few phrasings, ideally with headset and some background noise. The bench runs
each engine over the corpus and reports: top-1 token accuracy, the confusion pairs, and the
confidence distribution split by correct/incorrect. Run whisper.cpp both with and without
`--grammar`. **Deliverables: a go/no-go read from the user, and the numbers that set every
constant in Decision 4.** Requires the user to record the corpus (the only human step); the
comparison itself is mechanical.

**Stage 2 — the matcher and the command path, driven by typed text. [Mac]**
`belief/voice_commands.py`, `speech.render_say_again`/`render_confirm_request`,
`CrewConsole.handle_transcript`, the confirm-band pending state. No audio anywhere. Fully unit
testable, and mergeable on its own: `--crew-text` gains a voice-shaped command path you can drive
by typing. This is where the slice's actual behaviour lives, and it is provable without hardware.

**Stage 3 — recognition as a service, and body-layer's inbound wiring. [Mac]**
`POST /transcribe` and `GET /transcripts/poll` on the existing `TTSAdapterServer`;
`transcript_queue.py`; `srs_client.get_transcripts()`; `logger.py --speech-input` and
`_poll_transcripts` in the existing `--crew-text` poll thread. Verified by POSTing a Stage 1
recording and watching Petrovich act and read back. **End-to-end from a WAV file to a spoken
readback, with no Windows and no DCS in the loop.**

**Stage 4 — Windows capture. [Win]** (no DCS needed)
`audio_capture.py` (`FfmpegCapture`, `ClipGate`, `CaptureClipQueue`), `capture_server.py`,
`capture_client.py`, `python -m srs_adapter.capture`. PTT stubbed: a `--capture-window-s` manual
trigger (Enter key or an HTTP poke) opens a fixed recording window, so the full chain
mic → gate → LAN → recognise → command → readback runs before any DCS dependency exists. Also the
stage that proves `ffmpeg -f dshow` names the user's actual headset device.

**Stage 5 — real PTT through DCS. [Win] + [Sortie].**
Read `aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md` first, then run its probe
(`Export.probe-ptt.lua` deployed as `Export.lua`, six steps in its header, return
`Logs\aircraft_layer_probe_ptt.log`) to pin arg 738's actual values on this install. Then:
`Export.lua` publishes `ptt_down` derived from `GetDevice(0):get_argument_value(738)` against the
probed threshold, `schema.py`/`cache.py`/`api/server.py` carry it, `GET /ptt/state` exposes it as a
pure idempotent read, and the capture process gates on its edges. Only if the probe *falsifies* arg
738 does the `listen` F10 token fallback from Decision 3 come into play — a one-token addition to
`ALLOWED_COMMANDS` and the Hook menu, nothing else in this plan changing.

**Stage 6 — live sortie acceptance. [Sortie]**
A real flight commanding Petrovich by voice. Judges what only the user can: end-to-end latency
(press → readback), false-fire rate, whether "say again" lands at the right frequency or becomes
nagging, and whether the confirm band is a safety net or an irritation. Acceptance, not a
correctness gate — Stages 1–4 already prove the mechanism. Expect the constants from Decision 4 to
move once after this.

---

### Tests

**Implementer: verify this list against the tree before relying on it.** Files named as *existing*
were confirmed present during planning; the *contents* of each (whether a given helper or fixture
exists inside it) were **not** read and must be checked.

New:
- `srs-adapter/tests/test_stt_engine.py` — `WhisperCliEngine` against the **real** binary and a
  committed short WAV fixture, following `test_tts_engine.py`'s real-binary posture. **Must skip
  cleanly when the binary or model file is absent** — unlike `say`, whisper.cpp is not guaranteed
  present on every dev machine, so this is *not* a pure copy of that pattern.
- `srs-adapter/tests/test_transcribe_api.py` — `POST /transcribe` / `GET /transcripts/poll` with a
  recording `STTEngine` double. Structural copy of `tests/test_server.py`.
- `srs-adapter/tests/test_audio_capture.py` — `ClipGate` (too short, too quiet, accepted) and
  `CaptureClipQueue` against a fake `AudioCapture`, never the real `ffmpeg`. Same posture as
  `aircraft-layer/tests/test_audio_sender.py`'s fake-`WavPlayer` approach.
- `body-layer/tests/test_voice_commands.py` — the matcher: exact hits, each fuzzy case Stage 1
  actually observed, **verb-anchor rejection of non-command speech**, the separation check on
  left/right, each of the three bands, the confirm→affirm/negative/timeout paths, and
  `cancel_task`'s higher floor.

Extend (all confirmed to exist):
- `body-layer/tests/test_crew_console.py` — `handle_transcript` routing: match → `handle_f10_command`
  effects and readback; no match → the existing `handle_line` path, unchanged.
- `body-layer/tests/test_speech.py` — the two new renders.
- `body-layer/tests/test_srs_client.py` — `get_transcripts()` against its real loopback server.
- `body-layer/tests/test_logger.py` — `--speech-input` polling.
- `aircraft-layer/tests/test_api.py`, `test_schema.py`, `test_cache.py` — `ptt_down`/`GET
  /ptt/state`, **Stage 5 only**.

---

### Risks & Unknowns

- **Accent/recognition quality is the whole slice.** Unresolved until Stage 1 produces a number.
  Staged first for exactly this reason; nothing downstream should start before it reads.
- **PTT held-state readability — resolved yes** (Decision 3,
  `aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`). What remains is narrow and
  concrete: arg 738's actual values on this install are unconfirmed (no DCS access that session),
  and the arg itself was not in this project's own clickabledata dump — plausibly because it is
  HOTAS-bound rather than mouse-clickable, but that is inference. The shipped probe closes both in
  one sortie. The `listen`-token fallback stays parked against that small chance.
- **Constrained decoding may manufacture confident wrong answers.** `--grammar` forces output into
  the vocabulary, which can convert "obvious garbage" into "wrong command at high confidence" —
  actively harmful to the confidence floor. Bench both modes; decide from data.
- **`ffmpeg -f dshow` device naming on Windows is fiddly** and enumeration differs per machine. The
  capture process must log the available device list at startup (this project's own
  "build flag-gated debug logging into DCS-interfacing code upfront" lesson applies to any
  hardware-facing code, not just DCS).
- **A fourth hand-started process.** Accepted cost of the boundary decision; it makes the existing
  "Process supervision" backlog item materially more attractive afterwards.
- **`ffmpeg` and `whisper-cli` are new external binaries** the user must install on specific
  machines. Consistent with the external-binary rule, but it is a real setup burden and belongs in
  each subproject's `RUN.md`/`WORKFLOW.md`, not discovered live.
- **The two-poller load on the collector** (body-layer + capture process on loopback). Different
  endpoints, so `/f10_commands/poll`'s single-poller caveat is not violated — but `GET /ptt/state`
  must be a pure idempotent read, *not* drain-on-GET, or the same trap reappears.
- **Whisper hallucination on near-silence.** Whisper is known to emit plausible text for empty
  audio. The adapter's energy gate is the primary defence and must be tuned before, not after, the
  engine sees a clip.
- **Scope creep toward free-form.** Once voice works at all, "just let me say anything" is one
  small step that is actually a different system. The verb anchor and the closed phrase table are
  the structural barrier; keep them.

---

### Second-Order Effect

This **unblocks the brain layer's inbound half** by making the last piece of BL-10's plumbing real:
after Stage 3, a `PlayerUtterance` from live speech reaches the same escalation seam a typed line
does, so the brain milestone becomes "add a model behind an existing call" rather than "build
speech first". It correspondingly **narrows** the F10 menu's future — once voice is reliable the
menu is a fallback input surface, which argues against ever growing it further (consistent with the
user's 2026-09-16 direction that richer command forms belong to SRS, not F10). And it **complicates**
the process-supervision question, which four hand-started processes turn from tidy-up into
friction the user feels at the start of every session.

---

### Two-tier routing (user direction, 2026-09-19) — DESIGN NOTE, NOT YET PLANNED

A later direction changes the shape of everything after recognition, though not Stage 1 itself.
Speech is no longer one thing:

- **"(hey,) Petrovich ..."** — free speech, routed to the brain layer for interpretation.
- **Anything else** — a command, matched against this vocabulary.
- **"... nevermind"** at the end — retract the whole transmission.
- **"say again"** — bidirectional, standard aviation practice.

**The decode strategy is already settled by evidence, not preference.** A constrained grammar
cannot transcribe free speech, so routing cannot happen after a grammar decode. Of the three ways
out — free-decode then route, decode twice, or a grammar with a permissive free-text branch — the
last two are ruled out by `research/2026-09-19-whisper-contract-and-grammar-probe.md`: grammar at
whisper's default penalty scored 50% on a synthetic corpus and collapsed long phrases into
fragments, so a permissive branch would be worse, and double-decoding doubles latency on a
push-to-talk path. **Free decode always, route on the transcript, fuzzy-match commands from text**
— which is what `tools/stt_bench.py` already measures, so Stage 1's numbers apply to the tiered
design unchanged.

Four consequences, each with a reason:

1. **Wake-word detection must lean toward waking.** The failure modes are not symmetric. A false
   wake sends a command to the brain, which can interpret a command phrasing perfectly well — the
   cost is latency. A missed wake sends free speech to the command matcher, which fuzzy-matches it
   onto *something* and executes a wrong action. Bias the threshold accordingly.

2. **Match the wake word fuzzily, never by equality.** Probed on synthetic speech, `ggml-base.en`
   returns "Petrovitch" where `ggml-small.en` returns "Petrovich" — and that is before any accent
   is involved. An equality test would fail open on the more common model.

3. **Nothing executes before the transmission closes. One rule, no exceptions.** "Nevermind" can
   retract everything said before it, so every decision waits for PTT release. This forbids
   incremental execution outright.

4. **`stop` counts only when the whole transmission is the single word "stop"** (user direction,
   2026-09-19). A "stop" inside a sentence — "stop scanning north", or any ordinary use — is not
   the stop rule.

   An earlier draft made `stop` an exception to (3), firing the moment it was recognised so
   barge-in would not wait for release. This rule removes that exception and is better for two
   reasons. It deletes a whole mechanism: recognising a word mid-stream needs partial decoding of
   an open transmission, which is a different and harder problem than decoding a closed one. And
   it removes a false-positive class that would have been genuinely bad — an interrupt that can
   fire from the middle of a sentence will eventually fire from a sentence that merely contains
   the word. The latency cost is one PTT release, which is roughly the time it takes to stop
   speaking anyway.

   `stop_talking` therefore carries exactly one phrasing. Admitting "stop talking" or "quiet" as
   command phrasings while routing only on a bare "stop" would contradict itself — the longer
   forms would reach the same behaviour through the command matcher by the back door.

   **Known risk, accepted deliberately:** with no alternates there is no fallback word, and this
   is the token likeliest to fail. It is one short syllable, and on clean synthetic speech it
   already returned as "cloud" and "stock". If Stage 1's bench shows it unreliable on the user's
   own voice, this decision needs revisiting rather than tuning around — which is cheap, since
   adding a phrasing is a handful of clips rather than a re-recorded corpus.

### Transmission segmentation: PTT delimits clips (user, 2026-09-19)

*"Natural use is to hold PTT while I say a command and question and then release. So that
different commands/questions arrive as separate audio clips. Second may arrive while first is
being processed, but they're separate."*

**This is a larger simplification than it appears.** Live speech systems normally have to solve
endpointing — deciding where one utterance ends and the next begins, usually with voice-activity
detection, and usually badly in a noisy cockpit. Push-to-talk supplies that boundary exactly:
press to release is one clip, one transmission, one decision. No VAD, no silence thresholds, no
partial decoding of an open stream. It is also what makes rule (3) natural rather than a
restriction — the transmission closes on release because that is literally when the player stops
speaking.

Consequences for the design:

- **Capture produces discrete, complete WAV clips**, not a stream. This matches what the corpus
  already is, so Stage 1's measurements transfer to live operation without reinterpretation.
- **Transmissions queue, and may overlap in processing.** A second clip can arrive while the
  first is still being recognised or answered. Recognition of separate clips is independent and
  can run concurrently; what needs ordering is the *response*, since two crew answers talking over
  each other is worse than one arriving late.
- **Responses should default to the order asked**, the way a crew member answers questions in the
  order they were put. A fast command queued behind a slow free-text request waits; that reads as
  someone working through what was asked rather than as a bug.
- **`stop` is the one transmission that jumps the queue** — it aborts current speech and clears
  what is pending, which is the whole point of it. Note this is a *queue-priority* exception, not
  a resurrection of the mid-stream timing exception removed in (4): it is still recognised only
  from a closed transmission, and it is now unambiguous by construction, since the entire clip
  must be that single word.

`say again` in the Petrovich→player direction is where Stage 1's confidence distribution is spent:
below the band, ask instead of guessing or sitting silent. That makes the bench's confidence column
a source for a real constant rather than a report decoration.

**Not planned here.** The vocabulary and corpus coverage for all of this exist as of Stage 1
(`wake_petrovich`, `cancel_nevermind`, `say_again`), because re-recording a corpus is the expensive
part and adding tokens to it now is nearly free. The routing itself, the brain-layer handoff, the
transmission buffer and the repeat-last-utterance store are Stage 2-and-later work and need their
own architect pass.

### Settled Decisions (user, 2026-09-19)

**1. Capture lives in the collector, behind a flag.** Overrules this plan's recommendation of a
separate Windows-side adapter process. The user's reasoning: *"conceptually voice capture is DCS
interface, though technically we use a workaround and skip DCS. Collector should still do the
collecting, audio as well as others."* The collector's contract is everything arriving from the
player-and-aircraft side, and the player's voice is that, even though the audio path bypasses DCS
for technical reasons. Enabled by a command-line flag, defaulting off — the same additive posture
`--overlay`, `--f10-commands` and `--speech-audio` already use, so a collector started without it
behaves exactly as today.

Note this does **not** breach the invariant that matters. `division-or-responsibility.md`'s rule is
that raw audio never crosses into **body**, and it still does not: audio goes collector → adapter,
recognition happens in the adapter, and body receives text. What moves is where capture sits, not
where audio stops.

**2. The Stage 1 pass bar is deliberately not set in advance.** The user cannot know what accuracy
will feel acceptable until the numbers exist. Recorded as a known risk rather than a gap: judging a
threshold after seeing results invites rationalising a disappointing number into an acceptable one.
The mitigation is to report the bench's output in a form that makes the judgement concrete rather
than statistical — not just top-1 accuracy, but **the actual confusion pairs** and a sample of what
was heard, so the question becomes *"would I fly with this?"* rather than *"is 91% enough?"*.

**3. PTT binds to the VOIP half-trigger, not the radio-menu one.** The user: *"DCS has half trigger
radio menu and half trigger voip events. We should bind to the voip one."* These are distinct
bindable input commands on the Mi-24P, and the distinction matters — the radio-menu half-trigger
is already spoken for by the F10 command path this project built, so binding there would collide
with an existing input surface. VOIP is also semantically right: it is the control the player
already uses to *talk to someone*, which is exactly what talking to Petrovich is. Single-player
only, so DCS's own VOIP transmission is moot.

**This refines the investigator's finding rather than replacing it.** Its evidence that a held
state is readable through `GetDevice(0):get_argument_value` stands, along with the per-frame tick
rate that kills the missed-press concern. What changes is *which* signal to read: the probe must
now establish which device argument (or other readable state) corresponds to the **VOIP**
half-trigger specifically, rather than assuming arg 738's graduated value is the right source.
Since 738 was already absent from this project's own clickabledata dump, and the VOIP/radio-menu
split was not considered when it was identified, **the probe's scope widens slightly**: capture
both, and label which is which by pressing each binding in turn.

### Decisions Requiring User Input

All three are answered — see "Settled Decisions (user, 2026-09-19)" above. Kept as a heading so the
plan's shape stays readable against the sign-off commit that resolved them; nothing here is open.
