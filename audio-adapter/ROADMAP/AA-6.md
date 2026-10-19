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
  machine. Piper is an external binary plus a voice-model file, the same "binary, never a package"
  rule `say` and `whisper-cli` already follow. Petrovich's voice changes from `say`'s `Daniel` to
  a Piper voice the user picks.

  Still to establish before planning (Piper was noted in
  `research/2026-09-17-tts-audio-transport-recon.md` from general knowledge only, never tested):
  how Piper is distributed for Windows and macOS today, its CLI/WAV contract, and its latency on the
  user's machines against `say`'s measured ~0.6–0.8 s.

  **Voice decided (user, 2026-10-19): `en_GB-northern_english_male-medium`**, chosen after the
  five-voice sample set (`alan` was the first favourite) and the official samples page. The user
  also named `ru_RU-ruslan-medium` as *"perfect"* for character — whether a Russian voice can speak
  English text intelligibly is an open, untested question, not part of this milestone's default.

  Out of scope here: the other subprojects' OS-independence (user: *"first"* the audio adapter),
  and a Russian-accented character voice.
