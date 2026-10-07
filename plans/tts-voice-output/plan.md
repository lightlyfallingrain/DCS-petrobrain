<!-- doc-provenance:start -->
**Decision for:** [[AA-1]]
<!-- doc-provenance:end -->

### Goal

Make Petrovich's already-generated `OutgoingSpeech`/`CrewConsole` text audible to the player via
local Windows playback (TTS on the Mac, WAV bytes shipped to the Windows box and played through
`winsound`) — the first BL-10 slice, with SRS ICS injection deliberately deferred to the slice
that follows.

### Effort/Value Check

The literal audio path (subprocess call to `say`, an HTTP POST of WAV bytes, `winsound.PlaySound`)
is genuinely small — well under a day of code. The overhead here is architectural, not
algorithmic: standing up a third subproject (`srs-adapter/`) with its own venv, lint/type/test
commands, and `CLAUDE.md` for what is currently ~150–250 lines of code. That overhead is not
gold-plating invented by this plan — `docs/concept/division-or-responsibility.md`'s "Speech /
audio (SRS ICS)" section already settled "an SRS adapter owns the audio boundary... proposed as
its own thin component, sibling to the aircraft layer" before this plan existed, and root
`CLAUDE.md`'s module-independence rule forecloses the cheaper alternative (importing a TTS helper
straight into body-layer) since body-layer↔world-model is the *sole* sanctioned in-process
exception. Given that, paying the scaffolding cost now is not disproportionate: the SRS-injection
slice that follows immediately reuses this exact process and its HTTP surface (swap/add one
downstream call), so the cost is paid once, not twice. The one place this plan actively resists
over-building is the sink abstraction (see Decision 3) — three known sinks does not justify a
generic `SpeechSink` registry/protocol; it stays three plain optional fields, matching the
`overlay_client` precedent already used twice in this codebase.

### Investigator Dependency

`srs-adapter/research/2026-09-17-tts-audio-transport-recon.md` (plus its two addenda) already
covers every DCS-internals-adjacent unknown this slice touches: the `winsound`/collector
transport shape, macOS `say` latency, and the (deferred) SRS/ICS mechanism. Nothing in this slice
depends on an unverified DCS-internals claim beyond what that recon already flagged as
"needs live test" — those stay open risks below, not blockers to planning. No further
Investigator pass is needed before implementation; the SRS-injection follow-on slice will need one
for `--unitId`/`INTERCOM` behavior specifically, per the recon's own "Unresolved" list.

### Decisions

**1. Where the adapter lives: a new `srs-adapter/` sibling subproject.** Confirms (does not
reopen) `division-or-responsibility.md`'s existing call. Body-layer stays text-only (no `say`
subprocess, no audio bytes ever touch it) and aircraft-layer stays DCS-I/O-only (it gains one more
small write endpoint, not a TTS dependency) — both are then free of the other project's concern.
The seam is HTTP end to end: body-layer → srs-adapter → aircraft-layer, mirroring the existing
body-layer→aircraft-layer client pattern exactly, so no new in-process-import precedent is set (the
world-model↔body-layer exception stays the only one). Cost: a fourth subproject to stand up
(venv, `CLAUDE.md`, `ruff`/`mypy`/`pytest` wiring) — real, but it is exactly the shape the
SRS-injection slice needs to exist anyway, so this is that cost paid once, at the point it's first
needed, not speculative infrastructure.

**2. Where TTS runs: Mac, by default, behind a swappable engine interface.** Measured macOS `say`
latency (~0.6–0.8s, dominated by process startup) is comfortably inside what a crew callout can
tolerate — call it **under ~1.5s from text-ready to audible** before a readback starts reading as
laggy rather than immediate; a contact report or lifecycle line has a looser budget since it's
already proactive, not a direct reply. Windows SAPI is unmeasured (the user's PowerShell snippet
from the recon has not been run yet), so the default must not be hardcoded past changing: `srs-adapter`
defines a small `TTSEngine` protocol (`synthesize(text: str) -> bytes` returning WAV bytes) with one
implementation this slice (`MacSayEngine`, subprocess `say -v Daniel -o <tmp>.wav
--data-format=LEI16@22050 <text>`, then read the bytes back). If the Windows number comes back
faster and process-count-on-Windows becomes a real constraint later (as the recon already flags —
SRS injection adds two more Windows processes anyway), a `WindowsSapiEngine` drops in beside it
with no HTTP-layer change; which engine runs is a deploy/CLI-flag choice on `srs-adapter`, not a
body-layer or aircraft-layer concern.

**3. Sink interface: plain text, not `OutgoingSpeech`, mirroring `overlay_client` exactly — no new
abstraction.** `CrewConsole._print` is already the funnel every spoken line passes through as a
flat `str`, and it already carries one optional sink (`overlay_client: AircraftLayerClient | None`)
in exactly this shape. This slice adds a second, symmetric field:
`speech_client: SrsAdapterClient | None`, pushed from the same `_print` loop, wrapped in its own
`try/except` (see Decision 5) — same pattern as `overlay_client`, not a new plugin/registry
concept. `SrsAdapterClient.push_speech(text: str, urgent: bool)` is the one call; `urgent` is
threaded from `_print`'s existing `bypass_gate` parameter (already computed for the overlay `"!! "`
prefix), so no new signal has to be invented — an `UrgentCall`-sourced line is the only line that
ever sets it. **`bypass_gate` semantics for audio: preempt, not queue-jump-and-wait.** An urgent
line clears whatever routine lines are queued and interrupts whatever routine line is currently
playing, then plays immediately (see Decision 4) — anything weaker (queue-jump but let current
audio finish) means "missile launch, break right" can still be sitting behind a contact report,
which defeats the point of `bypass_gate` existing at all.

**4. Queueing: FIFO for routine lines, single-flight urgent preemption — decided in the
aircraft-layer's playback sender, not in `srs-adapter` or body-layer.** `drain_events` can emit
several lines in one poll, and `winsound` (or any audio API) plays one sound at a time — garbled
overlapping speech is worse than a short queue delay, so routine lines queue and play in order
rather than dropping or talking over each other. The queue has to live wherever playback actually
happens sequentially, which is the **aircraft-layer side** (`collector/audio_sender.py`'s new
`AudioPlaybackSender`): a single background worker thread draining a `queue.Queue`, calling
`winsound.PlaySound(path, winsound.SND_FILENAME)` (blocking, so the thread naturally serializes).
An urgent push clears the queue and stops in-flight playback (`winsound.PlaySound(None, 0)` or the
`SND_PURGE` flag — **unverified which actually works as expected on the box, live-test item**)
before playing its own file immediately. `srs-adapter` itself stays queue-free — it synthesizes and
forwards each line as it arrives, one HTTP POST per line; ordering/interruption is entirely
the receiving side's job, which keeps `srs-adapter` a stateless pass-through and puts the
stateful bit where the actual audio device contention lives.

**5. Failure posture: mirrors `/text/push`'s swallow-and-200 shape at every hop, not
`/command/petrovich_search`'s propagate-500 shape.** Audio is best-effort display-equivalent
output (like the overlay), not a verifiable command with its own completion contract — there is no
analogue to `/petrovich_wheel/latest` confirming a search happened, and building one is out of
scope for this slice. Three failure points, three swallow points:
- **TTS synthesis fails** (`say` binary missing, non-zero exit, unreadable output) inside
  `srs-adapter`: log, respond `503`/`500` to the body-layer caller depending on cause, but
  `CrewConsole._print`'s `try/except` around `speech_client.push_speech` catches it and continues
  — a failed line never stops the rest of the batch or the poll loop, exactly like `overlay_client`
  today.
- **The HTTP hop to aircraft-layer fails** (Windows box/collector down) inside `srs-adapter`: log,
  drop the line, still respond `200` to body-layer (the same "attempted the call" contract
  `/text/push` and `/command/petrovich_search` already use) — body-layer never learns or needs to
  learn that a specific line was never heard.
- **Playback fails** (`winsound.PlaySound` raises, e.g. malformed WAV, device error) inside
  aircraft-layer's `AudioPlaybackSender`: log and continue the worker loop, same as
  `TextOverlaySender.send_line`'s existing never-raises posture — one bad line must not kill the
  playback thread for every subsequent line.

**6. Windows side: `POST /audio/play` on the existing collector, JSON body, base64 WAV — confirms
the recon's proposal with one refinement.** Every existing write endpoint
(`/text/push`, `/command/petrovich_search`) uses a small JSON body, not a raw-binary POST — staying
consistent, `POST /audio/play` takes `{"audio_b64": "<base64 WAV bytes>", "urgent": bool}` rather
than a raw-bytes body, so it reuses `server.py`'s existing `_respond_json`/JSON-parsing scaffolding
verbatim instead of adding a second request-parsing code path. A short callout's WAV
(`say`'s `LEI16@22050` output, a few seconds at most) is trivially small for this. The
`AudioPlaybackSender` writes the decoded bytes to a temp `.wav` and enqueues it (see Decision 4).
**Security note (flagged, not escalated — CLAUDE.md currently exempts the security role for this
phase):** this is a second LAN-facing write path with a real side effect (audible sound on the
Windows box) and, like every existing endpoint, no auth — anyone on the LAN can already push
arbitrary overlay text or trigger a search; this adds "make Petrovich's voice channel say anything"
to that list. Same severity class as what already exists, not a new category of exposure, but
worth a line in case the phase's security exemption is revisited.

**7. Voice character: generic English voice now, Russian-accented character voice is an explicit
future item, not scoped here.** Matches the recon's finding — no ready Russian-accented English
voice exists in macOS `say` (`Milena` is Russian-*language*, unverified for quality, not the same
thing) — and does not block this slice on solving it. Backlog note for `ROADMAP.md`, not a task
here.

**8. Local dev path without DCS: `srs-adapter` gets a `--target local` mode.** Every other
body-layer surface is testable without a live DCS session (`body-layer/CLAUDE.md`'s hard
requirement); this slice's user-facing payoff is *hearing a voice*, so the dev path must let the
user hear one without Windows or DCS running at all. `srs-adapter --target local` skips the
aircraft-layer HTTP hop entirely and plays the synthesized WAV directly on the Mac (`afplay`,
already-present macOS CLI, no new dependency — same "external binary, not a package" rule the TTS
engine itself follows). `--target aircraft-layer --aircraft-layer-url URL` is the production mode
that does the real POST. This also happens to be the fastest way to iterate on voice/wording
quality, independent of the Windows round trip.

### Affected Modules / Files

- `srs-adapter/` (new subproject) — `src/tts_engine.py` (`TTSEngine` protocol +
  `MacSayEngine`), `src/server.py` (small stdlib `http.server` accepting `POST /speak`
  `{"text": str, "urgent": bool}` from body-layer), `src/aircraft_client.py` (thin HTTP client
  posting `{"audio_b64", "urgent"}` to aircraft-layer's `/audio/play`, mirroring body-layer's own
  `aircraft_client.py` shape), `src/__main__.py` (`--target local|aircraft-layer`,
  `--aircraft-layer-url`), own `pyproject.toml`/`CLAUDE.md`/`tests/`, stdlib-only.
- `aircraft-layer/src/collector/audio_sender.py` (new) — `AudioPlaybackSender`: worker thread +
  `queue.Queue`, `winsound.PlaySound` playback, urgent-preempt via queue-clear + stop-in-flight.
  Windows-only import guarded the same way any Windows-specific module in this codebase must be
  (mypy/tests run on the Mac too, per `aircraft-layer/CLAUDE.md`'s tech stack) — needs a
  conditional-import/platform-guard pattern check against how `winsound` is already referenced
  elsewhere in this codebase, if anywhere.
- `aircraft-layer/src/api/server.py` — add `POST /audio/play`, `_handle_audio_play`, wired the
  same optional-dependency way `text_sender`/`command_sender` already are (`503` when
  unconfigured).
- `aircraft-layer/src/collector/__main__.py` — construct and pass the new `AudioPlaybackSender`
  into `TelemetryAPIServer`, mirroring how `text_sender`/`command_sender` are already wired.
- `aircraft-layer/tests/test_audio_play_api.py` (new) — direct structural copy of
  `test_text_push_api.py`'s pattern, against a recording `AudioPlaybackSender` double (no real
  `winsound` call in automated tests).
- `body-layer/src/belief/srs_client.py` (new, or folded into a similarly-named module) —
  `SrsAdapterClient`, one method `push_speech(text: str, urgent: bool) -> None`, raising on
  transport failure (mirroring `aircraft_client.AircraftLayerClient.push_text_line`'s
  raise-and-let-the-caller-catch contract, not swallow-internally).
- `body-layer/src/belief/crew_console.py` — new field `speech_client: SrsAdapterClient | None`,
  pushed from `_print` alongside `overlay_client`, same `try/except`-log-and-continue shape.
- `body-layer/src/logger.py` — new `--speech-audio` flag (only meaningful with `--crew-text`,
  true no-op when absent) + `--srs-adapter-url`, wiring `speech_client` the same way `--overlay`
  wires `overlay_client` today.
- `body-layer/ROADMAP.md` / `body-layer/CLAUDE.md` — update the BL-10 entry once this slice lands;
  note the Russian-accent-voice backlog item (Decision 7).
- `srs-adapter/research/2026-09-17-tts-audio-transport-recon.md` — no change needed; already
  filed at the right home per its own note.

### Implementation Plan

1. **`srs-adapter` scaffold + local dev path (no aircraft-layer, no Windows, no DCS).**
   `TTSEngine`/`MacSayEngine`, the `POST /speak` server, `--target local` (`afplay` playback).
   Gives an immediately testable, audible path: `curl -X POST localhost:<port>/speak -d
   '{"text": "Watching Charlie one seven.", "urgent": false}'` should produce audible speech on the
   Mac with no other subproject running. This is the milestone's minimal working version — it
   proves synthesis + playback end to end before any cross-machine transport exists.

2. **aircraft-layer: `AudioPlaybackSender` + `POST /audio/play`, tested with a recording double.**
   No live Windows box needed to write/test this stage — same posture as every other collector
   sender's unit tests. Confirms the JSON contract (Decision 6) and the queue/preempt mechanism
   (Decision 4) against fakes.

3. **Wire `srs-adapter --target aircraft-layer`** so it POSTs synthesized WAV bytes to a running
   aircraft-layer instance's `/audio/play`. Testable on the Mac against a locally-run
   aircraft-layer collector (no DCS needed — the collector's `TelemetryAPIServer` runs standalone;
   only the `winsound` call itself needs Windows).

4. **body-layer: `SrsAdapterClient`, `CrewConsole.speech_client`, `logger.py --speech-audio`.**
   Unit-testable with a fake `SrsAdapterClient` double, same shape as existing `overlay_client`
   tests.

5. **Live Windows verification (needs the user's Windows box; does not need DCS running).**
   Run aircraft-layer's collector standalone on Windows, `srs-adapter --target aircraft-layer` on
   the Mac, and manually POST/trigger a few speech lines — confirm `winsound.PlaySound` actually
   plays, confirm the urgent-preempt mechanism (Decision 4's unverified `SND_PURGE`/stop-then-play
   behavior) does what's expected, listen for any device contention against other audio on the
   box.

6. **Live DCS/sortie verification (needs DCS running).** Run the full `--crew-text --speech-audio`
   path during an actual flight: judge whether the ~0.6–0.8s Mac latency feels crew-like in
   practice, whether overlapping callouts under load (multiple lifecycle events in one poll) queue
   acceptably, and whether the generic voice (Decision 7) is tolerable. This is the acceptance
   test, not a correctness gate — the pipeline is already proven working by stage 5.

### Risks & Unknowns

- **`SND_PURGE`/stop-then-play interrupt behavior for `winsound` is unverified** (Decision 4) —
  first real test is stage 5. If it doesn't work as expected, the fallback is closing and
  reopening the audio device or accepting a brief overlap on interrupt; not a blocker to building
  the rest, but the exact mechanism may need to change after a live test.
- **`winsound.PlaySound` blocking-call-per-thread behavior in practice** (does it duck/compete
  with DCS's own game audio or SRS's mixer once that exists) — unverified, flagged in the recon
  itself, first real signal at stage 5/6.
- **Windows SAPI latency is still unmeasured** — the default (Mac) could change once that number
  exists; the `TTSEngine` seam (Decision 2) is built so that doesn't require redesign, only a new
  implementation + a deploy choice.
- **`srs-adapter` process supervision is unspecified** — this adds a third long-running process
  (alongside body-layer's `logger.py` and aircraft-layer's collector) that someone has to start;
  no plan here for auto-start/health-check, same informal posture the other two processes already
  have (manually launched by the user per `aircraft-layer/WORKFLOW.md`).
- **No confirmation yet that a Windows-side `winsound` import needs guarding for Mac-run
  tests/mypy** — flagged as an Affected Modules note; needs checking against how this codebase
  already handles (or doesn't yet need to handle) any other Windows-only stdlib import, since none
  has existed in this codebase before this slice.
- **Voice acceptability is genuinely unknown** (recall the recon: "no ears here") — stage 6 is the
  first time anyone actually judges whether `say -v Daniel` sounds acceptable for this purpose.

### Second-Order Effect

This slice stands up `srs-adapter/` as a real sibling subproject and settles its HTTP contract
with both body-layer and aircraft-layer — the SRS-ICS-injection follow-on slice (BL-10's other
half) then only has to add one more downstream call inside `srs-adapter` (`DCS-SR-ExternalAudio.exe
--modulations INTERCOM --unitId <player unit id>`) rather than design the process/transport
question from scratch. It also makes local playback the permanent guaranteed-deliverable path per
the user's frequency-injection rejection (recon addendum): if the SRS slice's live ICS test fails,
this slice's local-playback capability is what ships, not a stepping stone that gets discarded.
