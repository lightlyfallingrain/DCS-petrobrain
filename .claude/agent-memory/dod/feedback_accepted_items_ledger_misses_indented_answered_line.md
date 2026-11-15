---
name: accepted-items-ledger-misses-indented-answered-line
description: accepted-items-ledger.sh's grep for '^**Answered' at the Decisions section misses an Answered line that is indented (inside a bullet's continuation) -- false "not yet answered" even when the user has answered. Check the section by eye before trusting the script's verdict.
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
