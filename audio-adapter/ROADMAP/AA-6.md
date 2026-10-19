# AA-6 — OS-independent audio adapter (Piper TTS on Mac and Windows)

- [~] **The audio adapter's server runs on Windows as well as the Mac** (`feature/audio-adapter-os-independent`).
  #status/in-progress User direction, 2026-10-19:

  > *"Mac has been running the audio-adapter, but I want it to be OS independent. Everything must
  > be OS independent, except that we need Windows to run DCS. Let's first make the audio adapter
  > work with windows as well as mac."*

  Today only capture is OS-independent. The server's TTS engine is macOS `say` (`MacSayEngine`)
  and `--target local` plays through `afplay`, so on Windows every `/speak` answers `503`.

  **Decided (user, 2026-10-19): Piper on both OSes**, chosen over native-per-OS (`say` + Windows
  SAPI) and over keeping several engines behind a flag. Same voice and same behaviour on either
  machine. Piper is an external tool plus a voice-model file, kept outside the adapter's own code —
  as installed it is `piper-tts` in a venv of its own (no standalone Piper binary works on the Mac;
  see the recon's 2026-10-20 addenda), so the adapter itself stays stdlib-only. Petrovich's voice changes from `say`'s `Daniel` to
  a Piper voice the user picks.

  **Plan approved (user, 2026-10-20)**: `plans/audio-adapter-os-independent/plan.md`, with the
  user's addition that a Piper outage is announced once in the adapter's terminal and its recovery
  once (Decision 3's amendment) — otherwise Petrovich goes silent for the rest of the sortie with
  nothing saying why. Piper runs as its own process on port 7800. **Implementation to be done
  from a Mac session** (user direction); Stage 4 needs the user on both machines.

  Established before planning (originally open): (Piper was noted in
  `research/2026-09-17-tts-audio-transport-recon.md` from general knowledge only, never tested):
  how Piper is distributed for Windows and macOS today, its CLI/WAV contract, and its latency on the
  user's machines against `say`'s measured ~0.6–0.8 s.

  **Voice decided (user, 2026-10-19): `en_GB-northern_english_male-medium`**, chosen after the
  five-voice sample set (`alan` was the first favourite) and the official samples page. The user
  also named `ru_RU-ruslan-medium` as *"perfect"* for character — whether a Russian voice can speak
  English text intelligibly is an open, untested question, not part of this milestone's default.

  Out of scope here: the other subprojects' OS-independence (user: *"first"* the audio adapter),
  and a Russian-accented character voice.
