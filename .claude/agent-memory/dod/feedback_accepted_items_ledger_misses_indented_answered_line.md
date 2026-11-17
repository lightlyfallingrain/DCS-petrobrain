---
name: accepted-items-ledger-misses-indented-answered-line
description: accepted-items-ledger.sh has two independent false-negative shapes on a plan with revision history -- an indented Answered line, and matching only the FIRST "Decisions Requiring User Input" heading when a living plan has several. Both verified on plans/flight-control/plan.md across two DoD passes. Check the live section by eye before trusting the script's verdict.
metadata:
  type: feedback
---

`accepted-items-ledger.sh` (added after the 2026-11-13 retro, BR-2's U4) checks a plan's
"Decisions Requiring User Input" section for a `**Answered` line, anchored `^\*\*Answered` —
no leading whitespace allowed. `plans/flight-control/plan.md`'s U3 answer (`**Answered
2026-11-15 (user, verbatim):** ...`) is indented two spaces, because it sits inside U3's own
bullet as a continuation paragraph (the normal Architect style for "answered, folded in place"
rather than a new top-level line) — the script reported "decisions U1 U2 U3 not yet answered (no
**Answered line) -- nothing accepted to check," which is false: U3 was answered, and the plan's
own E-P traceability table and `alignment.md` both cite the answer as the production decision.

**Why this matters beyond one false negative:** the ledger's whole purpose is catching an
accepted decision that silently never gets built or deferred (BR-2's U4 shape). A false "not yet
answered" verdict causes the opposite failure mode — it tells the reader there is nothing to
check, so nobody follows through to verify the (actually-answered) decision landed somewhere. On
this pass it happened to be harmless because all three decisions (U1/U2/U3) turned out to be
correctly deferred to later stages (P2/P3) regardless of whether the script flagged them — but a
future case where the answered decision *should* have landed in the current batch and did not
would sail through silently, exactly the shape this script exists to prevent.

**How to apply:** don't trust the ledger's "not yet answered" verdict at face value when the plan
visibly contains an `**Answered` line in that section — read the section by eye. Report both: the
mechanical tool's verdict and the by-hand correction, so neither the script's false negative nor
a real gap goes unflagged in the DoD report.

**Fix worth making** (not done here — DoD doesn't edit `.claude/scripts/`): widen the regex to
`^[[:space:]]*\*\*Answered` so an indented continuation line still matches.

**Second shape, found at the Stage P2 DoD pass (2026-11-17) on the same plan file.** The script's
own `awk` matches only the *first* "Decisions Requiring User Input" heading in the file and exits
there — a living plan that has accumulated several such headings across its own revision history
(mode 2's original, the Stage P1 revision, the Stage P2 revision) is checked against the oldest
one, not the live one. On this pass that meant the script reported "U1 U2 U3 not yet answered,"
which are **Stage P3's own** decisions from the long-superseded first section — the actual live
section for the stage under DoD ("Decisions Requiring User Input (Stage P2) — answered
2026-11-16," containing U4 plus plan-aligner Q1/Q2) was never read by the script at all.
`review-p2.md`'s own "Optional Refinements" flagged this independently during the Reviewer pass
on this same branch.

**How to apply, updated:** on any plan with more than one "Decisions Requiring User Input"
heading, the ledger's report is not wrong so much as *about the wrong section* — find the section
nearest a "ready to build"/"answered"/the current stage's own name, read its `U<n>`/plan-aligner
`Q<n>` items by hand, and cross-check each against `implementation.md` yourself. Report the
script's literal output **and** which section it actually matched, so a reader doesn't mistake a
stale-section report for "nothing to check" on the stage actually shipping.

**Second fix worth making**: match the *last* "Decisions Requiring User Input" heading in the
file, or the one nearest a line containing "answered"/"ready to build", rather than the first.

**Third shape, reconfirmed at the BL-17 Stages 3a/3b/3d/4 DoD pass (2026-11-17), a different plan
file.** `plans/speech-rules/plan.md`'s Revision 2 renamed its own later section to "### Revision
2's own open decisions (U19–U24)" rather than reusing the literal heading "Decisions Requiring
User Input" — the script's `awk` never matches that string at all, so it silently reports zero
findings for U19–U24 rather than a false negative on a section it did find. This is exactly
`reviewer/feedback_ledger_misses_a_renamed_decisions_heading.md`'s own third shape, first caught
by Reviewer on this same plan file (`review-stage4.md`'s Optional Refinements), now independently
reconfirmed one stage later at DoD — the two roles hit the identical gap on the identical plan
without either reading the other's note first, which is itself a signal: this failure mode is
common enough (two shapes already on `flight-control/plan.md`, a third now hit on two different
roles' passes of `speech-rules/plan.md`) that fixing the script (match the *last* heading, or any
heading containing "Decisions Requiring User Input" as a substring rather than requiring an exact
match) is worth doing once, rather than each role re-discovering and re-describing it by hand on
every living plan with more than one such section.
