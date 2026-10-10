# BL-B47 — `_is_air_defence` cannot recognise a class-level SAM

- [x] **BL-B47 — `speech._is_air_defence` resolved through `object_model.profile_for`, which keyword-matches
  *type* names, so a believed classification held at class level was never recognised as air defence.
  FIXED, DoD-PASSED, merged 2026-10-11 — UNFLOWN.** #status/done #needs-flight
  Branch `fix/air-defence-class-level`, merge commit `1063f2a`. Reports:
  `plans/air-defence-class-level/{implementation,review,security,dod-check}.md`. Acceptance rides
  [[BL-13]]'s card, `docs/acceptance/2026-10-10-crew-query-path-sortie.md` (one sortie, both
  changes) — the thing to listen for is **repetition, not silence**.

  **The fix is one line**: `_summary_op_class(facts) in AIR_DEFENSE_OP_CLASSES`, the
  classification/lattice side of the boundary, reusing the mechanism BL-13's pull path already used
  — so push and pull now agree on what air defence is by construction rather than by coincidence.
  Three parties independently enumerated it over 1060 unique candidates (10 declared `op_class`
  values + 131 keyword entries, being `_KEYWORD_PROFILES` 70 plus
  `_REPORTING_NAME_KEYWORD_PROFILES` 61, + 595 real DCS type names): **0 air-defence verdicts lost,
  exactly 4 gained** — `OP_SRSAM`, `OP_MRSAM`, `OP_LRSAM`, `OP_SPAAG`.

  **`OP_ZU23` was already covered by accident**, its literal string matching that table's own
  `"zu23"` keyword — so 4 of 5 classes were broken and one was not, and a test sampling only
  `OP_ZU23` would have found nothing. That coincidence is what hid this.

  **Two arguments Security added that the enumeration cannot give**, and they are why this shipped
  without a flight first: the candidate space is **closed** (for any value not starting `OP_`,
  `_op_class_of` delegates straight to `profile_for`, identical by construction), so *"0 lost"* is
  total rather than a sample; and both call sites compute `if is_new_class or
  is_air_defence_repeat`, so a predicate only ever OR'd into a speech decision is **monotone in
  speech** — it structurally cannot silence a contact that previously spoke.

  **Filed consequences, not fixed here:** [[BL-B50]] (this lowers the callout ratchet's ingredient
  count, though the same 10-lines-in-10-ticks churn is reachable today with no air defence, and in
  steady state this adds zero lines) and [[BL-B51]] (three copies of the air-defence class set, only
  one with a guard that can notice `object_model` growing — `_op_class_of`'s early return on any
  non-default `OP_*` string is the mechanism that would make a future omission a silent miss).

  **Security's lapse condition, carried verbatim** because a standing exemption without a stated end
  condition outlives its premise silently:

  > Recompute this rating, and treat `BL-B50` as blocking-priority rather than backlog, if either
  > holds: (a) a sortie log shows group membership flipping on consecutive ticks, or (b)
  > [[BL-B48]]'s `EAGER` infantry cohesion ships or persists into a flown build — a 6 km-wide group
  > is precisely the input that makes membership flip, which is the ratchet's only missing
  > ingredient.

  The first sortie that produces logs is the trigger.

  ---

  ## As originally filed, 2026-10-10

  Found by the Reviewer during [[BL-13]], 2026-10-10, and **confirmed by measurement** on that
  branch. Pre-existing on the **push** path; nothing in BL-13 caused it and BL-13 deliberately did
  not touch it (the milestone's own summary renderer uses the believed classification directly, so
  the pull path is unaffected).

  **Measured:**

  ```
  profile_for("SA-6 Kub LN")  -> resolves correctly
  profile_for("OP_SRSAM")     -> default bucket
  profile_for("OP_LRSAM")     -> default bucket
  ```

  `profile_for` matches against DCS *type* designations. A class-level belief — which is exactly
  what a contact holds before it is identified to type, i.e. most of the time at range — carries an
  `OP_*` class string, and that string hits nothing. Two callers compute `is_air_defence_repeat` on
  the push path off this predicate.

  **Why it earns an entry rather than a note.** This is a silent gap on the one callout path the
  project says matters most. `_OP_CLASS_DISPLAY`'s own comment states the governing judgement —
  *"the difference between a short-range and a long-range SAM is the difference between a threat you
  can fly around and one you cannot"* — and D6 already treats air defence as the standing exception
  elsewhere (threat envelopes key on believed classification). A contact believed to be a SAM at
  class level is precisely the case the exception exists for, and it is the case that falls through.
  The failure is silent: no warning is suppressed visibly, the call simply never carries the
  air-defence treatment.

  **The fix is not "add the `OP_*` strings to `profile_for`."** `classification.parent_class_of` is
  the function that resolves a believed classification to its parent class, and `profile_for` is the
  function that resolves a DCS type name to a profile; they are not interchangeable, which is the
  actual root of this. Whoever takes it should decide which side of that boundary `_is_air_defence`
  belongs on rather than widening a keyword table. Related and smaller:
  `parent_class_of("ZSU-23-4")` is `None` while `parent_class_of("ZSU-23-4 Shilka")` is `OP_SPAAG` —
  the bare designation is fixture-authored and the real DCS type carries the suffix, so that one is
  a note, not a defect.
