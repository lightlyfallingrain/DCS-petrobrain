---
name: feedback_accepted_items_ledger_only_checks_first_decisions_section
description: accepted-items-ledger.sh's awk only reads the FIRST "Decisions Requiring User Input" heading in plan.md; a re-cut plan with several such sections (mode 2's U1-U4, then mode 1's U5-U10) gets everything after the first one silently unchecked
metadata:
  type: feedback
---

`accepted-items-ledger.sh`'s section-extraction awk (`/^#+ *Decisions Requiring User
Input/{on=1; ...} on && /^#+ /{if (length($1) <= lvl) exit}`) starts at the *first* matching
heading and stops at the next heading of equal-or-higher level. A plan file that has been revised
in place and now carries several "Decisions Requiring User Input" sections (e.g.
`plans/flight-control/plan.md`, which has one for mode 2 at line ~571 and another for the mode-1
re-cut at line ~3290, with U1-U4 and U5-U10 respectively) only ever has its *first* section's
ids checked. Running the script standalone on BL-16 M1+M2 printed "decisions U1 U2 U3 not yet
answered -- nothing accepted to check" and said nothing about U5-U10, even though U5-U10 were the
decisions this pass actually needed to verify, all answered and all built.

**How to apply:** when a plan has been re-cut and carries more than one "Decisions Requiring User
Input" heading, run the mechanical ledger for awareness but do not trust its silence about a
later section -- read every such section in the plan by hand and check each `U<n>` against
`implementation.md` yourself, the same way the script would if it covered the whole file. Named
by its `Decision <n>` cross-reference, not the bare `U<n>` token, is still "mentioned" in the
sense the ledger wants, so grep for both. Worth a fix to the script itself (loop over every
matching heading, not just the first) if this recurs on another re-cut plan.
