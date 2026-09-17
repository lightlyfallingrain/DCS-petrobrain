---
name: bl10-srs-tts-recon
description: BL-10 first-slice TTS/audio-transport recon findings (DCS-SR-ExternalAudio.exe, winsound, say latency)
metadata:
  type: project
---

Session 2026-09-17, finding at `srs-adapter/research/2026-09-17-tts-audio-transport-recon.md`
(new `srs-adapter/` module created this session — didn't exist before; judged appropriate per
`plans/body-layer/plan.md` §7's "sibling component" argument, but that placement decision itself
is still open, not mine to make).

Key facts:
- `DCS-SR-ExternalAudio.exe` (in `ciribob/DCS-SimpleRadioStandalone` releases) has a documented
  `--unitId` flag whose help text literally says it targets aircraft intercom ("communicate over
  intercom with that aircraft") — read from `Program.cs` source, not forum folklore.
- SRS's own wiki lists intercom support only for L-39/UH-1H/SA342 Gazelle — a short named list.
  Mi-24P is NOT on it. Real doubt whether Mi-24P (AI-only gunner seat, no human multicrew station
  in this project) has any SRS-visible ICS channel at all. Unresolved — blocked on
  `forum.dcs.world/topic/292935-mi-24p-spu-8-in-dcs-bios-and-srs-simple-radio-functionality/`
  (403s automated fetch, needs user to paste).
- Fallback if true ICS doesn't pan out: frequency-based SRS injection (tune a spare Mi-24P radio,
  ExternalAudio transmits on that freq) — same mechanism DATIS/MOOSE already use for AI ATC.
- `winsound` (Windows-only Python stdlib module) plays WAV with zero new dependency — satisfies
  aircraft-layer's stdlib-only policy for local audio playback. `POST /audio/play` on the
  collector, same shape as existing `POST /text/push`, is the recommended near-term transport.
- macOS `say` measured latency for short (3-10 word) callouts: ~0.6-0.8s wall-clock, flat across
  phrase length in that range (dominated by process-startup, not synthesis rate). `say -o out.wav
  --data-format=LEI16@22050 "..."` writes directly to 16-bit PCM WAV, no conversion needed before
  handing to `winsound`.
- No Russian-accented English voice exists in macOS `say` (only `Milena`, a Russian-*language*
  voice). Piper noted as a candidate but not tested. Honest near-term answer: generic voice now,
  character later.
- `DCS-SR-ExternalAudio.exe`'s TTS options include local Windows SAPI (no key) plus optional
  Google/Azure cloud TTS (opt-in credentials flags) — nothing in the SRS-native path *requires* a
  cloud key.

Still unverified / needs live Windows+DCS+SRS test: Mi-24P ICS-over-SRS itself, Windows-side SAPI
latency (gave user a PowerShell snippet), `--freqs`/`--modulations` requiredness alongside
`--unitId`, `winsound.PlaySound` behavior against DCS/SRS audio mixing.
