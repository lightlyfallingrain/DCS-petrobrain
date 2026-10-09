# BL-W7 — Binocular optic, voice command completeness, and precise position belief — sortie closure

- [x] **Binocular optic, voice command completeness, and precise position belief — FLOWN AND
  CLOSED 2026-09-25** #status/done (user direction). `docs/acceptance/2026-09-23-eyes-and-voice-sortie.md` is
  closed. **This sortie is where most of 2026-09-25's fixes came from** — the callout heard while
  scanning the other way (`plans/callout-outside-gaze/`, then `plans/scan-is-not-watch/`), cancel
  resurrecting a superseded scan, range crossings sounding like fresh sightings, and the outpost
  fragmenting into 18 contacts (`plans/contact-fragmentation-at-range/`). Original entry follows.

  ~~merged to `main` 2026-09-24 (`c398675`), still unflown.~~ All three passed DoD on fixtures/console only. **Merged
  before the sortie by user decision (2026-09-24)** — so any correction the flight produces now
  lands on `main` rather than on the branch. Precise position belief joined this list at merge:
  belief now carries a fused 2×2 covariance instead of quantised buckets, which changes what the
  pilot will hear for ranges and bearings and has never been heard in the air.
  The first two are deliberately batched onto one sortie because they are one cockpit
  loop (look, report, be told where to look): `docs/acceptance/2026-09-23-eyes-and-voice-sortie.md`.
  Clears when that sortie is flown and the card's "Bring back" items are answered — the nine
  unbenched `scan <clock>` tokens' recognition accuracy in particular has no measurement of any
  kind yet, benched or live. **Precise position belief's own debt item is superseded by the entry
  below** — the version merged here had the range-runaway defect the fix branch corrects; do not
  fly this card's position-belief items until that fix has merged. **It merged 2026-09-25 (`bfbcf8d`), so they are now judgeable.**


This sortie closes the live-acceptance debt that was open on three separate entries: [[BL-W32]] (precise position belief), [[BL-W33]] (binocular optic), [[BL-W34]] (voice command completeness). Each of those entries' own text still says "unflown as of merge" — that sentence is superseded by this closure and is kept in place anyway, unedited, because it was true when written and this project does not rewrite a superseded claim in place (see `docs/PROCESS.md`, "Superseding a decision"). Read this entry as the correction.
