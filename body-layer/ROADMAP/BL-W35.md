# BL-W35 — Watch reporting — Stages 1 through 5

- [x] **Watch reporting — Stages 1 through 5, merged 2026-09-24 (merge `9b16c3b`,
  `feature/watch-reporting`). Merged before flying, deliberately, so any correction the sortie
  produces lands on `main` rather than a branch — live acceptance is still outstanding
  (`docs/acceptance/2026-09-25-crew-behaviour-sortie.md`, which superseded the
  `2026-09-24-watch-reporting-sortie.md` written for this stage).** #status/done #needs-flight A watched contact now reports itself unprompted on three new
  triggers, plus `follow` becomes both a `watch` synonym and a new best-match way to *name* which
  contact to watch. Correctness review APPROVED (full read), performance review flagged a real
  finding (LOS called before the range/altitude gate) which was fixed and the fix re-reviewed
  APPROVED, security review APPROVED with three non-blocking hardening recommendations carried to
  backlog below. DoD gate run 2026-09-24: format/lint/type/test all green in both touched
  subprojects (body-layer 1177 passed/4 xfailed, audio-adapter 198 passed/1 skipped). **Live
  acceptance outstanding** — a real sortie has still not exercised it; card at
  `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`, which **superseded** this stage's own
  `2026-09-24-watch-reporting-sortie.md`. That card went stale before it could be flown: it was
  written while a commanded `scan` still conferred watched-ness, so its watch blocks would have
  tested the wrong thing.

  **Stage 1 — movement.** `CONTACT_MOTION_CHANGED` has fired since `movement-detection` and was
  never spoken; `belief.callouts._WATCHED_ONLY_KINDS` gates it at the speech layer (not at
  emission), so a contact watched *after* its motion event already fired still gets the callout.
  `_contact_report_text` gained `lead`/`event_clause` affixes reused by every later stage.
  `WATCH_REPORT_MIN_GAP_S` bounds how often one contact can interrupt with watched-only speech,
  independent of `EVENT_COOLDOWN_S`.

  **Stage 2 — kilometre range crossings.** `CONTACT_RANGE_CROSSED`, gated and bookkept *at
  emission* in `ContactStore.tick`'s new sixth block (the opposite placement from Stage 1's
  events, since the bookkeeping — `Contact.last_announced_range_km` — only means anything for a
  watched contact). Seeds silently on first watch. Gated on `certainty_of` so a decayed position
  never manufactures a crossing nobody observed. The trigger's deadband is derived from
  `PositionEstimate.range_uncertainty_m` (new, `bearing_uncertainty_deg`'s down-range mirror) —
  floored/ceilinged rather than a bare tuned constant, forced by `precise-position-belief`
  landing underneath this plan mid-design and turning the input from a step function into a
  continuous, noisy one.

  **Stage 3 — `follow`.** 3a: `follow nearest`/`follow nearest air defence`/`stop following`/
  `cancel follow` as free phrasings on the existing `watch_nearest`/`watch_nearest_air_defence`/
  `cancel_watch` tokens (`audio-adapter`, zero body-layer change). 3b: `MatchResult`/
  `TranscriptEvent`/`PendingConfirmation`/`handle_command`/`handle_transcript` all migrate their
  single-purpose `bearing_degrees` field to a generic `slots: dict[str, int | str] | None` — a
  breaking wire change between `audio-adapter` and `body-layer`, cheap because both are Mac-local
  processes restarted together, done while there was exactly one slot in flight rather than
  after `follow` added three more. 3c: `follow [<descriptor>] [<clock> o'clock] [<n> km]` — a new
  `follow` token whose three qualifiers are parsed slots, not enumerated phrases (the
  cross-product is in the hundreds); resolved by `_resolve_follow_target`, a scored best-match
  over the qualifiers, explicitly framed in its own docstring as a stopgap for the brain layer
  (user's own words) to be deleted, not extended, once free-text targeting exists.

  **Stage 4 — engagement envelopes.** `belief/threat.py` (new module) reads
  `body-layer/data/threat_envelopes.json` (28 Hoggit-derived entries, committed with its saved
  source page as provenance) and exposes `envelope_for(ClassificationBelief)` — the structural
  no-omniscience guard, since the signature cannot accept the type that would carry ground
  truth. Class-level envelopes are *derived* at import by joining the table through
  `perception.object_model.profile_for`, not hand-written (though the join rate against this
  particular table turned out low — see Notable Discoveries in `plans/watch-reporting/
  implementation.md`). `ContactStore.tick`'s seventh block ANDs three independent ways to be
  safe (out of range / under the altitude floor / behind a ridge), a 1.5x Schmitt trigger on the
  leaving side, and a fail-open, uncertainty-swept LOS term with an asymmetric dwell
  (`LOS_MASK_CONFIRM_S`) — a masked verdict needs to hold before it clears a danger call; a clear
  verdict takes effect immediately. Engagement is the one watched-only kind that does **not**
  silently seed: a contact recognised already inside its envelope fires immediately, since that
  is exactly the late-recognition warning this trigger exists for. Speech: `"Danger, <unit>..."`/
  `"Safe from <unit>..."` via `_contact_report_text`'s `lead` affix, `STATE_TRANSITIONS.md`'s own
  wording. **The practical value of this trigger is gated on an optic that does not exist yet**
  (the 9K113) — see the deferred-9K113 backlog entry below, un-deferred in reasoning but not in
  scope by this plan.

  Full design and every measured/decided number: `plans/watch-reporting/plan.md`,
  `plans/watch-reporting/implementation.md`.


Live acceptance is tracked on [[BL-W9]]'s consolidated 2026-09-25 crew-behaviour sortie card, which supersedes this stage's own `docs/acceptance/2026-09-24-watch-reporting-sortie.md` card.
