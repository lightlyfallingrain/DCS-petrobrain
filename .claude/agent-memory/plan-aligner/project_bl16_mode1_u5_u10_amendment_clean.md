---
name: project-bl16-mode1-u5-u10-amendment-clean
description: BL-16 mode-1 amendment (U5-U10, seat rule, 2026-11-18) closed the one prior CONCERNS item (U6) and traced ALIGNED; the pattern for checking a "silent state-machine change + spoken exception" design
metadata:
  type: project
---

The previous pass ([[project_bl16_mode1_recut_u6_reopens_settled_e9]]) flagged U6 as CONCERNS. The
user answered "yes" the same day, along with U5, U7, U8 (and, from U5, two new questions U9/U10
plus a seat rule). Re-checking the amendment: ALIGNED, no findings that change the verdict.

**What made this easy to verify, worth repeating:** every consequence the user's answers created
was disclosed in *two* independent places, not one — the plan's own "Risks & Unknowns" section
*and* the test card's step-by-step wording (Flight M-A steps 8/9/11), plus a third restatement in
`body-layer/ROADMAP/BL-16.md`'s "Mode 1" section for a future reader who never opens the plan. When
a task brief asks "is this disclosed to the player, and does the test card say so" — check the
Risks prose is not the only place it appears; a redundant trail across plan/test-card/roadmap is
the sign a decision was actually absorbed, not just logged once and left.

**The general shape worth naming:** U5 made "Petrovich has the controls" one state that persists
across park/unpark (silent, mode-only switches), with exactly one disclosed exception — a forced
handover when mode 1 physically cannot fly (hover, below the IAS floor) — where the plan's own
Risks section says, unprompted, "this is the only place 'player command only' is not met, and it
is physical, not a choice." A plan that names its own exception to a rule it just adopted, with
the physical reason, in the same breath, is not a finding; it is the plan doing the aligner's job
for it. Compare [[project_bl16_takeover_correction_transient_undisclosed]] (the negative case: a
transient was measured but never written up as expected behaviour) — the distinguishing test is
whether the exception is *named and explained*, not just present in the design.

**A related, narrower pattern: an old E can be legitimately narrowed by a brand-new answer to a
state the E's own goal check predates**, without that being a silent drop. E6 (2026-10-31, "'I
have controls' gives the aircraft back at once") predates mode 2 (the AI overlay) as a thing
Petrovich could be flying through. U9 answers the overlay-specific case directly and by the user's
own choice among two offered options ("unable", don't remember). Check: did the user answer this
specific new case themselves (not the architect filling a gap), and is the old E's wording about a
scope the new case could not have been under? If both hold, it is `met, narrowed`, not a Finding —
same test as [[project_bl17_user_decision_narrows_e5_and_grep_derisks_r7]].
