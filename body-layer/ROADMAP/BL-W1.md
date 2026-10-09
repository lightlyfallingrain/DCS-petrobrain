# BL-W1 — Contact-report flood (merge-echo callout suppression)

- [x] **`fix/contact-report-flood` — DoD PASSED on fixtures, merged 2026-10-05 (`3fe93fd`), not yet flown
  (2026-10-05).** #status/done #needs-flight Suppresses the spoken `CONTACT_DETECTED` callout for a freshly-founded contact
  when an existing, not-yet-`lost` contact is spatially/class-plausibly the same real thing — the
  speech-layer fix for the naked-eye gaze sweep's merge-direction continuity loss (the user's own
  complaint, mid-flight 2026-10-04: *"it feels like many of those reports were about the same
  units"*). Retrospective reconstruction against sortie-1004: 17 of 34 contact-id foundings would
  now be suppressed; the named six-vehicle cluster's four genuinely-simultaneous sightings each
  speak once and the one later re-founding echo goes silent. `CONTACT_REACQUIRED` and group lines
  are untouched. Known, accepted cost: a genuine split immediately after a merge is
  indistinguishable from a merge-echo at this layer and also goes quiet (see
  `plans/contact-report-flood/plan.md`, "The honest cost of the chosen fix"); suppression is
  one-shot and permanent per sortie (belief stays queryable via `report`). Reviewer APPROVED WITH
  MINOR FIXES (since applied); Security deep analysis APPROVED, no Performance pass (Security
  examined the O(n)-per-`CONTACT_DETECTED`-event cost directly — ~34 events per sortie, not per
  tick — and judged none warranted). Does **not** close `BL-B24` or
  `plans/contact-duplication-ambiguity-runaway/plan.md` — both carry a note saying so. Acceptance
  card: `docs/acceptance/2026-10-05-contact-report-flood-sortie.md`. **What the next sortie has to
  settle, because the 17/34 figure is a retrospective reconstruction from pipeline outputs, not a
  byte-for-byte replay**: whether the real cockpit experience is quieter without losing a
  genuinely-distinct contact, and whether the occasional silenced genuine split is ever actually
  noticed. Also flyable on the same sortie: `feature/silence-command` (merged, already on `main`)
  — the manual half of quieting the cockpit, this fix being the automatic half.


**Status-section record, kept for the record (overlaps with the above):**

- [x] **Contact-report flood (merge-echo callout suppression) — DoD PASSED on fixtures 2026-10-05,
  merged the same day (`3fe93fd`); live acceptance still outstanding.** `fix/contact-report-flood`. See the "Live acceptance debt" entry above for the
  full writeup — not duplicated here. Debug → Architect → Implementer → Reviewer → Security(deep)
  → DoD sequence (bug-fix path; no plan-review stage, matching this project's current
  once-per-feature security cadence). 1399 passed/4 xfailed (up from the branch's own 1389/4,
  +10 new tests), `ruff`/`mypy --strict` clean.

  **Milestone completion question**: narrows, slightly, what a future resolution of the
  `ContactStore.ingest` candidate-ambiguity root policy (`BL-B24` /
  `contact-duplication-ambiguity-runaway`) needs to additionally consider — the *audible* symptom
  of that unresolved policy goes quiet for the merge-driven case specifically, which could make the
  underlying belief-store duplication easier to leave unaddressed for longer simply because nobody
  hears it anymore (recorded in the plan's own "Second-order effect" section). Does not invalidate
  any downstream assumption and does not change what the next milestone should be.

