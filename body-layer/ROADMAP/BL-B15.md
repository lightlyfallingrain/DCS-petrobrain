# BL-B15 — Petrovich's voice has no character

- [ ] **BL-B15 — Petrovich's voice has no character — generic English TTS, and monotonous with it.** #status/open Deferred deliberately at
  [[BL-10]] slice 1 (`plans/tts-voice-output/plan.md` Decision 7) rather than forgotten. macOS `say`
  ships no Russian-accented English voice (`Milena` is Russian-*language*, a different thing), and
  solving it would have expanded a slice whose point was "audible at all". Options when picked up:
  a different local engine with a suitable voice, a trained/cloned voice, or accepting a generic
  one permanently. **Delivery is a separate problem from accent** (user, 2026-09-18, on first
  hearing it): the voice is flat and evenly stressed whether it is reading a routine contact
  report or an urgent break call. Prosody may matter more for believability than the accent does,
  and it has different fixes — SSML, per-line rate and pitch, or urgency-aware templates. Cheap to try in isolation — `audio-adapter --target local --voice <name>` plays a
  line on the Mac with nothing else running, so voice auditioning costs one command per candidate.
