# AA-1.1 — Stage 1 — synthesis + local playback

- [x] **Stage 1 — synthesis + local playback.** #status/done `TTSEngine` protocol with one implementation,
  `MacSayEngine` (the `say` binary, an external CLI rather than a package dependency — this
  subproject is stdlib-only like its siblings), `POST /speak`, and `--target local` playing the
  result on the Mac via `afplay`. Runs with no other subproject, no Windows and no DCS, which is
  both the fastest way to audition voices and wording and the concrete answer to body-layer's
  "must be testable without a live sim" requirement applied to a feature whose whole payoff is
  hearing something.
