# BL-B25 — Merge-echo predicate evaluated at the wrong tick

- [ ] **BL-B25 — `_already_reported_member_ids` evaluates its merge-echo predicate at the current
  tick, not the tick the original suppression happened.** #status/open Found by Reviewer during
  `fix/redundant-group-disclosure` review (2026-10-05); recorded, not fixed — judged bounded and
  not a correctness issue.

  `CalloutScheduler._already_reported_member_ids` (`body-layer/src/belief/callouts.py`) decides
  whether a group member was merge-echo-suppressed by re-running `_is_merge_echo_of_earlier_
  contact` against the *current* belief state, not the state at the moment the original
  `CONTACT_DETECTED` was actually suppressed. If the earlier, plausibly-same contact has since
  gone `lost`, or the two contacts have since drifted far enough apart that
  `contacts_plausibly_same` now reads `false`, a member that *was* genuinely suppressed stops
  counting as "already reported" — and a group's first disclosure can then re-speak content that,
  strictly, already reached the pilot.

  This pushes in the opposite direction from the user's "prioritize less speaking" instruction for
  this fix (it risks one extra spoken line, never a missed one), and is scoped to the
  first-disclosure window only — it cannot cause a contact to go permanently unreported, and it is
  not a no-omniscience violation. Worth fixing only if it is ever actually heard as a real
  duplicate on a live sortie; until then, the fix would require either snapshotting the
  suppression decision at the moment it happens (a new piece of per-contact state this project has
  so far avoided adding) or accepting the current, cheaper, re-evaluated-each-tick approximation.
