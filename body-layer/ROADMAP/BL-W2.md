# BL-W2 — Redundant group disclosure

- [x] **`fix/redundant-group-disclosure` — ACCEPTED 2026-10-09.** User, reviewing the status
  page: *"Group lines stop restating known members -> accepted"*. The accepted cost named in its
  own plan stands and was not separately judged: a genuine split immediately after a merge is
  indistinguishable from a merge echo at the speech layer and also goes quiet. If that is ever
  heard, it reopens as a defect rather than as this entry.

  Original entry, kept for the record:

  - [ ] **`fix/redundant-group-disclosure` — DoD PASSED on fixtures 2026-10-05, merged the same day (`2ae34cc`), not
  yet flown.** Silences a `belief.groups.Group`'s first disclosure when every member was already
  individually reported (directly or via the flood fix's merge-echo above), and speaks only the
  unreported delta otherwise. **Rides the same sortie as `fix/contact-report-flood` above rather
  than needing a separate flight** — both fixes change what the pilot hears about the same
  contact/group stream, on the same cockpit, so one flight settles both: does the stream read as
  signal rather than noise, and does anything go unreported that should have been (the
  over-suppression risk direction both fixes share). Acceptance card published alongside DoD
  sign-off; add its ask to the already-pending contact-report-flood sortie rather than scheduling
  a second one.


**Status-section record, kept for the record (overlaps with the above):**

- [x] **Redundant group disclosure — Reviewer, Security and DoD all APPROVED 2026-10-05, merged
  the same day (`2ae34cc`); live acceptance still outstanding.** `fix/redundant-group-disclosure`. A second, speech-layer duplicate-report path one
  level above the merge-echo fix above: a `belief.groups.Group`'s **first** disclosure used to
  always speak the full roster the instant two-plus members first clustered, even when every one
  of those members had already been announced individually — directly, or via a merge-echo the
  fix above already silences. User direction (2026-10-05) settled the design: no "those are
  together" acknowledgement, prioritize less speaking. `render_group_disclosure` gains a
  keyword-only `already_reported_contact_ids` parameter that splits the first-disclosure branch
  three ways — silent (every member already reported), a delta clause naming only the unreported
  members (partial), or unchanged full disclosure (none reported) — reusing the existing
  branch-4 delta taxonomy rather than inventing a second "new at time zero" rule. Scoped to the
  first disclosure only; every later branch (leader change, first differentiation, arrival delta,
  otherwise-silent) is untouched. New `CalloutScheduler._already_reported_member_ids` computes the
  set per tick from the scheduler's own `_last_spoken_signature` plus the same merge-echo
  predicate the flood fix's `CONTACT_DETECTED` suppression uses — now factored into one shared
  `_is_merge_echo_of_earlier_contact` helper so the two call sites cannot drift apart silently
  (Reviewer's optional finding; sharing was possible after all, despite the two call sites asking
  the question from an event vs. from group membership). Real sortie-1004 evidence: 1 of 5
  group-level spoken lines in the sortie confirmed suppressed by object id (`t_sim=730.9`), 1 more
  strongly suspected (`t_sim≈1021.9`), 3 unaffected. 5 new tests, zero regressions: 1414
  passed/4 xfailed (up from 1409/4). `ruff`/`mypy --strict` clean. Does **not** touch the settled
  delta taxonomy for later arrivals, and does **not** close `BL-B24` or
  `plans/contact-duplication-ambiguity-runaway/plan.md` — the root `ContactStore.ingest`
  "2+ candidates → always a new contact" policy is still open; both items now carry a note saying
  this fix doesn't close them either, same as the flood fix before it.

  **Known residual, recorded not fixed**: `_already_reported_member_ids` evaluates the merge-echo
  predicate at the *current* tick, not at the tick the original suppression happened. If the echo
  source has since gone `lost` or drifted apart enough that `contacts_plausibly_same` now reads
  false, a genuinely-already-suppressed member stops counting as reported and the group's first
  disclosure could re-speak content that, strictly, already reached the pilot. This errs toward
  speaking (the opposite of "prioritize less speaking"), but is bounded to the first-disclosure
  window only and is not a correctness or no-omniscience issue. See
  `plans/redundant-group-disclosure/implementation.md`.

  **Milestone completion question**: does not change what's next or invalidate a downstream
  assumption — a self-contained addition to one existing branch of `render_group_disclosure`,
  gated by a new optional parameter that defaults to the old always-full behaviour.

