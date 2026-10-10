# BL-B47 — `_is_air_defence` cannot recognise a class-level SAM

- [ ] **BL-B47 — `speech._is_air_defence` resolves through `object_model.profile_for`, which keyword-matches
  *type* names, so a believed classification held at class level is never recognised as air defence.** #status/open
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
