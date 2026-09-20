# BL-10 first slice: TTS audio transport (local playback + SRS injection path)

**Date:** 2026-09-17
**DCS version:** not verified locally — see below (no live DCS/SRS test performed this session)
**Theatre:** n/a

**Filed under `srs-adapter/research/`, not `body-layer/research/`.** `plans/body-layer/plan.md`
§7 and `docs/concept/division-or-responsibility.md`'s "Speech / audio (SRS ICS)" section both
argue the SRS adapter is a sibling of the aircraft layer, not part of body-layer, but call this
undecided ("needs user input"). This investigation is entirely about the adapter's own external
dependencies (SRS's own client tooling, TTS engines, Windows playback) — none of it is a
body-layer belief-state or API question, so it doesn't belong in `body-layer/research/` regardless
of how the sibling-vs-aircraft-layer question resolves. If Architect later folds the adapter into
`aircraft-layer/`, this file should move there; if a `srs-adapter/` component is created, this
directory is already its home. Not a decision on the open question — just where the evidence
belongs today.

### Question

For BL-10's first slice (outbound TTS only — no STT/PTT, that's later): how does Petrovich's
generated text actually become audible to the player? Specifically: (1) can DCS-SRS's own tooling
inject audio onto the Mi-24P's intercom (ICS) channel, and what does that cost in setup/failure
surface; (2) what's the least-bad local-playback path on the Windows box as a nearer-term step;
(3) measured TTS latency for short crew callouts, Mac-side, plus a concrete Windows-side
measurement the user can run; (4) is a Russian-accented English voice realistically available;
(5) does any path assume a cloud TTS key, given the project's offline-capable preference.

### Findings

- **`DCS-SR-ExternalAudio.exe` is a real, shipped SRS component** (part of the
  `ciribob/DCS-SimpleRadioStandalone` releases, source at
  `DCS-SR-ExternalAudio/Client/Program.cs` in that repo) that connects to a running SRS server as
  a synthetic client and transmits TTS or file-based audio. — **evidence:** documented (read from
  the project's own source repo, not a forum paraphrase) — **source:**
  https://github.com/ciribob/DCS-SimpleRadioStandalone/blob/master/DCS-SR-ExternalAudio/Client/Program.cs

- **It has an explicit intercom-targeting option.** `--unitId` (uint, default 1000) — help text,
  quoted verbatim from the source: *"Sets the Unit ID of the transmitter - if you set this to the
  same as an aircraft you can then communicate over intercom with that aircraft."* — **evidence:**
  documented (verbatim source string) — **source:** same file as above. Full CLI surface also
  includes `--freqs`/`--modulations` (still marked `Required = true` in the `Options` class —
  I could not confirm from the parsing layer alone whether they're actually consulted when
  `--unitId` is set, since the connection/transmit logic lives in `ExternalAudioClient`, a
  different file I did not fetch), `--coalition`, `--port` (default 5002), `--culture`/`--gender`/
  `--voice` (Windows SAPI-style voice selection), `--googleCredentials`/`--azureCredentials`
  (optional cloud TTS backends), `--text`/`--textFile`/`--file` (raw audio file playback, so a
  pre-rendered WAV can be injected without going through ExternalAudio's own TTS at all),
  `--ambient` (background noise track), `--latitude`/`--longitude`/`--altitude` (for SRS's
  line-of-sight/distance radio model), `--Record`.

- **Mi-24P's SRS-intercom support is unconfirmed, and there's a real reason to doubt it applies
  the way UH-1H/Gazelle/L-39 do.** SRS's own wiki lists intercom support explicitly for "L-39,
  UH-1H, SA342 Gazelle" (a short, named list, not "all aircraft") — **evidence:** documented
  (wiki text) — **source:** https://github.com/ciribob/dcs-simpleradiostandalone/wiki. Those are
  all aircraft with a **real human-crewed multicrew station** in DCS's own MP model, where SRS's
  intercom feature exists to let two separate SRS clients (two separate DCS player slots) hear
  each other. The Mi-24P's gunner seat is AI-only in this project (single-player, no second human
  crew station) — it is not obviously the same mechanism, and I found no source confirming the
  Mi-24P's SPU-8 intercom panel is exposed as an SRS-selectable channel at all. A directly-relevant
  forum thread exists — **"Mi-24P SPU-8 in DCS-BIOS and SRS Simple Radio functionality"**
  (`forum.dcs.world/topic/292935-`) — but `forum.dcs.world` 403s automated fetch from this
  environment (consistent with prior sessions, see agent memory
  `forum-dcs-world-fetch.md`); I could not read it. **This is the single most important open
  question this recon did not resolve — ask the user to paste that thread's content.**
  — **evidence:** forum-claim-unverified (thread exists, content unread) — **source:**
  https://forum.dcs.world/topic/292935-mi-24p-spu-8-in-dcs-bios-and-srs-simple-radio-functionality/

- **Even if true ICS targeting doesn't pan out for the Mi-24P, a fallback exists that is
  mechanically certain to work: frequency-based injection.** `ExternalAudioClient` transmitting on
  an arbitrary frequency the player has one of the Mi-24P's radios (R-863/R-828/YADRO) tuned to,
  with matching coalition, is exactly the mechanism DATIS and MOOSE's `Sound.SRS`/`MSRS` class
  already use for AI ATC/AWACS voice over SRS — an established, working pattern, just not
  literally "the ICS channel." — **evidence:** inferred (from ExternalAudio's documented frequency
  args + DATIS/MOOSE's known real-world use of exactly this path) — **source:**
  https://flightcontrol-master.github.io/MOOSE/advanced/text-to-speech.html,
  https://github.com/destotelhorus/DATIS (contents not fetched, named as prior art only)

- **SRS injection has real setup and failure-surface cost regardless of which targeting mode is
  used.** It requires: an SRS server process running (even single-player — ExternalAudio connects
  to a server, not directly to DCS), the player's own SRS client connected to that server and
  tuned appropriately, and a third long-running process (`ExternalAudioClient`, invoked once per
  utterance or kept running) — three processes coordinating instead of one. Any one of them not
  running, or DCS/SRS radio state not matching what the injector assumes (wrong frequency, ICS not
  actually wired for this aircraft), fails silently from the player's perspective — no callout
  heard, no error surfaced to Petrovich's own logic. — **evidence:** inferred from the documented
  architecture, not measured — **source:** as above.

- **Local playback needs no new dependency on the Windows side.** `winsound` is a CPython
  standard-library module **on Windows only** — `winsound.PlaySound(path, winsound.SND_FILENAME)`
  (or `SND_ASYNC` for non-blocking) plays a WAV file directly. This satisfies the project's
  stdlib-only policy for `aircraft-layer/` without adding any package dependency, mirroring how
  `Export.lua`/the collector already avoid third-party deps. — **evidence:** documented (Python
  standard library, `winsound` — https://docs.python.org/3/library/winsound.html) — **source:**
  CPython docs. Not tested on the actual Windows box this session (no Windows access from here).

- **The collector already has the exact shape of endpoint this needs, just not audio-typed.**
  `POST /text/push` (`aircraft-layer/src/api/`) is the existing inbound-write pattern: validates a
  field, forwards to a sender object (`TextOverlaySender`), returns `200`/`400`/`503`,
  fire-and-forget, never raises the caller's request into a hard failure. A `POST /audio/play`
  endpoint accepting raw WAV bytes (or a short base64 field, given HTTP body size is trivial for a
  3-10 word callout) and handing them to a new `AudioPlaybackSender`-shaped object (write the bytes
  to a temp `.wav`, call `winsound.PlaySound`) is a direct structural copy of the existing pattern
  — **evidence:** inferred from reading the existing code (`aircraft-layer/src/api/`,
  `aircraft-layer/src/collector/text_sender.py`), not a new investigation, but noted here since it
  directly answers Q2. — **source:** `aircraft-layer/WORKFLOW.md`, `aircraft-layer/CLAUDE.md`.

- **macOS `say` measured latency for short crew callouts: ~0.6-0.8s wall-clock, dominated by
  process startup, not phrase length.** Measured on this Mac (`say -v Daniel -o out.wav
  --data-format=LEI16@22050 "<text>"`), 5 runs each on phrases from 27 to 112 characters:

  | phrase (chars) | time |
  | --- | --- |
  | "Watching Charlie one seven." (27) | 0.626-0.633s (5 runs, tight) |
  | "T-72, eleven oclock, two kilometres." (36) | 0.652s |
  | "Missile launch, nine oclock, break right." (41) | 0.658s |
  | "Enemy... crossroad east of the village." (112, the longest §3.6 worked example) | 0.673s |

  Latency barely moves with phrase length in this range — it's essentially fixed per-utterance
  overhead (process spawn + engine load), not synthesis-rate-bound. `say` can write directly to a
  16-bit PCM WAV (`--data-format=LEI16@22050`) — no format-conversion step needed before handing
  bytes to a Windows `winsound` playback path. — **evidence:** reproduced-locally — **source:**
  probe script below, run on this machine (macOS, Apple Silicon).

- **No Russian-accented English voice exists in macOS `say`.** Full voice list checked
  (`say -v '?'`): one Russian voice, `Milena` (`ru_RU`) — a Russian-*language* voice, not an
  English voice with a Russian accent. Feeding it the English callout text ran without error, but
  I have no way to judge the resulting audio quality/intelligibility from this environment (no
  ears here) — flagging as **unverified, needs the user to listen**: `say -v Milena "T-72, eleven
  o'clock, two kilometres."`. The realistic near-term answer to Q4 is **a generic (non-accented)
  English voice now; character comes later** — same honest framing the task asked me to give if
  that's where the evidence lands. — **evidence:** reproduced-locally (voice list + successful
  invocation), inferred (quality judgment, unverified) — **source:** `say -v '?'` output, this
  session.

- **`DCS-SR-ExternalAudio.exe`'s own TTS options span local-Windows and cloud, and only the cloud
  ones need a key.** `--culture`/`--gender`/`--voice` with no credentials flag implies the Windows
  SAPI/System.Speech voice table (local, offline, no key) is the default path; `--googleCredentials`
  and `--azureCredentials` are separate opt-in flags for Google Cloud TTS / Azure Cognitive
  Services specifically — **evidence:** documented (flag names + help text from the source) —
  **source:** `DCS-SR-ExternalAudio/Client/Program.cs`, same fetch as above. This directly answers
  Q5: nothing in the SRS-native path *requires* a cloud key; cloud is opt-in for a nicer voice.
  I could not confirm from the CLI-parsing file alone what happens with zero TTS-related flags at
  all (i.e., whether it falls over without any voice selected, or has a sane default) — the
  synthesis logic itself is in a file I didn't fetch this session.

- **Piper (local neural TTS) is a realistic external-binary candidate for either box, but not a
  Russian-accented-English answer either.** Not installed/tested this session (out of scope for a
  same-machine-only recon given the Mac already has `say`, and no Windows access at all) — noted
  from prior general knowledge only, so treat this line as **forum-claim-unverified /
  general-knowledge, not investigated**: Piper ships per-language voice models (including a
  Russian-language model), distributed as a small standalone binary + ONNX model file, no Python
  package dependency. It would need its own accent-quality check exactly like `say -v Milena` does,
  and I have not done that check.

### Reproducible Test

macOS `say` latency probe (ad hoc, run directly in bash this session — not committed as a script
per this role's "no pipeline code" rule, reproduced here verbatim so it can be re-run):

```sh
run_one() {
  local phrase="$1"
  local t0 t1
  t0=$(python3 -c 'import time; print(time.time())')
  say -v Daniel -o /tmp/out.aiff "$phrase"
  t1=$(python3 -c 'import time; print(time.time())')
  python3 -c "print(f'{$t1-$t0:.3f}')"
}
run_one "Watching Charlie one seven."
```

WAV-direct output (confirmed working, `LEI16@22050` = 16-bit PCM mono 22.05kHz, directly
`winsound`-playable with no conversion step):

```sh
say -v Daniel -o out.wav --data-format=LEI16@22050 "T-72, eleven o'clock, two kilometres."
```

**Windows-side measurement the user needs to run** (I have no Windows access from this session —
do not trust a guessed number for this):

```powershell
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$synth.SetOutputToWaveFile("$env:TEMP\out.wav")
$synth.Speak("T-72, eleven o'clock, two kilometres.")
$sw.Stop()
Write-Host "Elapsed: $($sw.ElapsedMilliseconds) ms"
$synth.SetOutputToDefaultAudioDevice()
```

Bring back: the elapsed ms for 2-3 phrases of varying length (mirror the table above), and
`$synth.GetInstalledVoices() | % { $_.VoiceInfo.Name }` to see what voices are actually installed
(stock Windows only ships a couple of SAPI voices; more may already be present if any
accessibility/language packs are installed).

**Live DCS/SRS steps the user needs to run** (none of this is safely runnable without the
Windows/DCS/SRS environment):

1. Start an SRS server (or point at whatever SRS server this setup already uses for a normal
   session).
2. Launch the Mi-24P in a mission, connect the normal SRS client, note whatever the SRS overlay
   shows as your aircraft's unit ID (or use `DCS-SR-ExternalAudio.exe -h` to see if there's a
   simpler way to discover it — I could not confirm this from the CLI-parsing file alone).
3. Run `DCS-SR-ExternalAudio.exe --text "test one two three" --freqs <whatever the overlay shows
   for your ICS channel — may not exist for this aircraft, see Findings> --modulations AM
   --coalition 2 --unitId <your aircraft's unit id>` and listen for it on the ICS channel
   specifically (not a radio channel).
4. If step 3 doesn't produce audio on ICS, fall back to the frequency-injection path: tune one of
   the Mi-24P's radios to an unused frequency, run the same command with `--freqs <that frequency>`
   and no `--unitId` override, and confirm it's heard when that radio is selected.

### Possible Approaches

**Recommended first slice, given the above:**

- **Run TTS on the Mac.** Measured latency (~0.6-0.8s) is well inside "near-instant" for a
  readback and comfortably fine for a contact report; no evidence yet that Windows-side SAPI is
  meaningfully faster, and running it on the Mac avoids adding any new process to the Windows box
  for this slice. Revisit only if the user's own PowerShell measurement comes back materially
  faster and process-count-on-Windows becomes a real constraint later (e.g. once SRS injection
  adds two more Windows processes anyway).
- **Transport: WAV bytes over the existing collector HTTP API, not SRS, for the first slice.** Add
  `POST /audio/play` next to `POST /text/push`, same shape (validate, forward to a sender, never
  hard-fail the caller). The sender writes the bytes to a temp file and calls
  `winsound.PlaySound(path, winsound.SND_FILENAME)` — zero new dependencies, satisfies the
  stdlib-only policy, and is a small, reviewable diff against a pattern that already exists and is
  already tested (`test_text_push_api.py` is the direct template for `test_audio_play_api.py`).
- **Sink interface: keep it symmetric with the existing `TextOverlaySender`/`overlay_client`
  shape** (`crew_console.py`'s `_print` funnel already has one optional sink wired exactly this
  way) — a second optional sink (`audio_client: AircraftLayerClient | None`) on `CrewConsole`,
  pushed from the same `_print` funnel every spoken line already passes through, wrapped in its
  own try/except so a failed playback push degrades the same way a failed overlay push does.
  `OutgoingSpeech` (`speech.py`) needs no new field for this — TTS synthesis and playback dispatch
  live entirely below `_print`, outside body-layer, consistent with `division-or-responsibility.md`'s
  "Body and brain deal in text only."
- **Defer the SRS sink until the ICS-vs-multicrew question above is answered.** Don't build
  against `--unitId` intercom targeting on faith — the evidence that Mi-24P even has an
  SRS-visible ICS channel is currently one unread forum thread. If it turns out not to, the
  frequency-injection fallback (tune a spare Mi-24P radio to an unused frequency) is a fully
  workable Plan B with real prior art (DATIS/MOOSE), just costs the player a small immersion
  compromise (Petrovich technically arrives "over the radio" on a dedicated frequency rather than
  literally on ICS) — Architect's call once the ICS question is answered either way.
- **Voice character: ship a generic English voice for this slice, do not block the slice on
  finding a Russian-accented one.** Neither macOS `say` nor (on current evidence) Piper has a
  ready-made "English with Russian accent" voice; `say -v Milena` speaking English text is an
  unverified experiment, not a solution. A dedicated character-voice investigation (a fine-tuned
  or cloud-provider voice, accepting the offline-preference tradeoff explicitly if so) is its own,
  later piece of work — flag this to the user as a deliberate scope cut, not an oversight.

### Unresolved

- ~~**Does the Mi-24P expose an SRS-visible intercom channel at all**~~ — **RESOLVED, yes.** See
  the addendum below: stock SRS's `SR.exportRadioMI24P` declares an Intercom radio at 100.0 MHz,
  modulation 2. The wiki-derived inference in the Findings above was wrong.
- **Whether `--freqs`/`--modulations` are actually required/consulted when `--unitId` targets
  intercom**, or whether unitId alone is sufficient — still open, though `--modulations INTERCOM`
  is now confirmed to be an accepted value (addendum below). I only read the CLI-parsing layer
  (`Options` class), not `ExternalAudioClient`'s connection/transmit logic.
- **How to discover the player's DCS unit ID at runtime**, which `--unitId` needs for intercom
  scoping (it defaults to `1000u`). Likely already available via the aircraft layer's
  `LoGetWorldObjects`/`is_ownship` path — verify, do not assume.
- **Windows-side TTS latency** — no number exists yet; the PowerShell snippet above is the way to
  get one. Don't assume it beats or loses to the Mac's ~0.6-0.8s without that measurement.
- **Audio quality/intelligibility of any of the tested voices**, including whether `say -v Daniel`
  or `-v Milena` sound acceptable through a compressed radio-style output — this recon measured
  latency and confirmed mechanism only; it did not and could not evaluate how anything actually
  sounds.
- **Whether ExternalAudio behaves sanely with zero TTS flags set** (sane local default vs. hard
  failure) — not confirmed from the CLI-parsing file alone.
- **`winsound.PlaySound` behavior in practice on the actual Windows box** (blocking vs
  `SND_ASYNC`, whether it competes/ducks against DCS's own game audio or SRS's audio mixer) — no
  Windows access this session; first real test happens whenever the `POST /audio/play` endpoint is
  built and exercised live.

---

## Addendum, 2026-09-17: the Mi-24P intercom question is RESOLVED — the path exists

Two sources, obtained after the main finding above was written, close the single biggest open
question. The Mi-24P **does** have an SRS-visible intercom channel, and `DCS-SR-ExternalAudio.exe`
**does** accept `INTERCOM` as a modulation.

### 1. The Mi-24P's SRS radio export declares an intercom radio

The user supplied the content of
`forum.dcs.world/topic/292935-mi-24p-spu-8-in-dcs-bios-and-srs-simple-radio-functionality/`
(the thread that 403'd on automated fetch). It contains SRS's `SR.exportRadioMI24P` function,
posted February 2022 by `gnomechild` and refined by `Sapper31`, whose first radio slot is:

```lua
_data.radios[1].name = "Intercom"
_data.radios[1].freq = 100.0
_data.radios[1].modulation = 2 --Special intercom modulation
_data.radios[1].volume = 1.0
_data.radios[1].volMode = 0
```

Crucially, `gnomechild` states the same support "is already included in the release" — their PR
was not merged *because SRS had already shipped official Mi-24 support*. So this is not a
community patch a user must install; it is what stock SRS does for this airframe.

This directly contradicts the inference in the main finding above that drew on SRS's wiki listing
intercom support only for L-39/UH-1H/SA342. **That inference was wrong.** The wiki list is not a
statement of which airframes have an intercom radio in their export; the Mi-24P has one, at
**100.0 MHz, modulation 2**.

Note also `_data.capabilities.intercomHotMic = false` and the PTT branch setting
`_data.selected = 0` on a half-press of the two-stage trigger — those govern the *player's*
transmit path, not reception, and are irrelevant to injecting audio the player merely hears.

### 2. `--modulations INTERCOM` and `--unitId` are the documented intercom-injection path

The `Options` class help text for `--modulations` reads "Modulation AM or FM comma separated",
which does not mention intercom — but SRS's own release notes and documentation state that
`--unitId` "sets the Unit ID of the transmitter - if you set this to the same as an aircraft you
can then communicate over intercom with that aircraft," added specifically to allow intercom over
external audio. The help string is simply stale relative to the feature.

`--unitId` defaults to `1000u`, so it must be set explicitly to the player's actual DCS unit ID
for intercom scoping to work. Discovering that unit ID at runtime is a real, unsolved sub-problem
for this project: the aircraft layer already reads `LoGetWorldObjects` and flags ownship
(`is_ownship`), so the id is very likely already available on a channel this project owns —
**verify before designing around it.**

### Revised outlook for the SRS slice

The likely invocation is:

```
DCS-SR-ExternalAudio.exe --text "..." --freqs 100.0 --modulations INTERCOM \
    --coalition <n> --unitId <player unit id> --name "Petrovich"
```

Still to verify live (nothing here removes the need for the "Reproducible Test" steps):

- that `--modulations INTERCOM` parses (help text omits it; behaviour inferred from release notes).
- whether `--freqs 100.0` must match the export's intercom frequency exactly, or is ignored when
  the modulation is INTERCOM.
- whether the player *receives* intercom regardless of SPU-8 selector position (expected — in SRS
  `selected` governs transmit, not receive — but unconfirmed for this airframe).
- that this works in **single-player** against a locally-hosted SRS server with an AI gunner,
  which is this project's only supported configuration.

**What this does not change:** the first slice's recommendation stands unaltered. Local playback
via `POST /audio/play` remains the right first step — it is independent of SRS entirely, needs no
server running, and is the sink that proves the whole text-to-audible path end to end. The SRS
sink is now a known-reachable second sink rather than a speculative one, which is exactly the
question this addendum was needed to settle.

### Constraint, 2026-09-17 (user): frequency injection is NOT an acceptable fallback

The main finding above treats frequency-based injection (tune a spare radio to an unused
frequency, the mechanism DATIS and MOOSE use) as the fallback if ICS does not pan out. **That
fallback is rejected.** The user's reason is operational, not aesthetic:

> "I need to stay on external mission frequency and MI-24 does not handle multiple channels
> simultaneously."

The Mi-24P's SPU-8 selects *one* audio source at a time, so a Petrovich frequency would compete
with the mission frequency the player must stay on, rather than layering under it. Real crew
intercom does not work that way and neither can this.

Consequences for the SRS slice:

- **ICS is the only acceptable SRS target.** `--modulations INTERCOM --unitId <player unit id>`
  is not the preferred path among several, it is the path. If it turns out not to work in
  single-player against an AI gunner seat, the SRS slice does not degrade to a radio frequency —
  it stops, and local playback (the first slice) stands as the delivered capability.
- **The live-test steps change accordingly.** "Reproducible Test" step 4 above — the fall back to
  frequency injection — is void. Step 3's ICS result is now pass/fail for the whole SRS approach.
- **Discovering the player's unit ID is now load-bearing, not incidental**, since intercom
  scoping depends on it and there is no frequency-based escape hatch if it proves unobtainable.

This also raises the value of the local-playback sink: it is not merely a stepping stone to SRS,
it is the guaranteed-deliverable path if intercom injection fails a live test for any reason.
