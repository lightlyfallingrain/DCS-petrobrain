# AA-6 — OS-independent audio adapter (Piper TTS on Mac and Windows)

- [x] **The audio adapter's server runs on Windows as well as the Mac** (`feature/audio-adapter-os-independent`).
  #status/done **Merged to `main` 2026-10-20 (`a5c61abf`)**, at user direction, after Stage 4 passed on both
  machines. Flown the same day with the whole stack except brain on Windows (Piper + whisper.cpp
  `b5454` CPU build); Piper read `~` aloud, fixed by `fix/speech-tilde-about`
  (`docs/acceptance/2026-10-20-sortie-feedback.md`, F3). User direction, 2026-10-19:

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

  **Stages 1-3 landed (DoD passed, 2026-10-20)**: `plans/audio-adapter-os-independent/{implementation.md,
  review.md,performance-review.md,security-review.md,dod-check.md}` — Reviewer APPROVED (one fix
  loop: a concurrency-test assertion gap and a stale `--voice` doc reference, both fixed and
  re-reviewed), Performance Reviewer APPROVED/MONITOR, Security deep-analysis APPROVED, and a
  retroactive Security plan review (missed in sequence, closed at DoD — see "Process note" below)
  also APPROVED. All mechanical checks (ruff format/check, mypy --strict, pytest: 318 passed/2
  skipped) pass on tip `6e200483b714d00f86b607e8aa59af59a7a6491d`. `#needs-flight`: **Stage 4
  (live verification on Mac and Windows) is explicit scope, not done** — it needs the user's own
  hands on both machines and was never claimed as covered by any automated check. The milestone
  stays `[~]`, not `[x]`, until Stage 4 runs. Acceptance checklist for Stage 4:
  `plans/audio-adapter-os-independent/dod-check.md`.

  **Stage 4 PASS on both machines (user, 2026-10-20)**: Mac — *"works on mac, very good audio"*,
  live pytest 0 skipped, outage/recovery lines once each, warm latency *"practically
  instantanous"*; Windows — *"Piper Windows test done. Pass. works very well."* (reported as one
  overall pass, blocks not itemised). Results: `docs/acceptance/2026-10-20-aa6-stage4-piper.md`.
  The server's own per-request `TTS synthesis failed` WARNING still repeats during an outage — left
  as is by user decision (*"leave as is, not important"*). `audio-adapter/RUN.md` rewritten for
  Piper. Ready to merge.

  **Process note**: this batch's Security **plan** review (the Architect→Implementer gate, distinct
  from the deep-analysis pass above) never ran in sequence — found and closed retroactively at DoD.
  Second occurrence of this exact gap (`.claude/agent-memory/dod/
  project_security_plan_review_skipped_by_collapsed_turn.md`); a dispatch-time hook is now warranted.

  **Milestone-completion question (root `CLAUDE.md`)**: does landing Stages 1-3 change what the
  next milestone should be, or invalidate a downstream assumption? No, for the code itself — the
  plan's own "Second-order effect" already anticipated this: AA-B1 (voice character/accent) is
  unblocked at near-zero marginal cost once this lands, since Piper's `"voice"` field is a free
  per-request parameter. But **AA-B1 cannot be live-verified either until Stage 4 runs** on this
  milestone first — Stage 4 is also where the decided voice (`en_GB-northern_english_male-medium`)
  gets its first real cross-machine hearing, which AA-B1's own voice auditioning depends on.

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
