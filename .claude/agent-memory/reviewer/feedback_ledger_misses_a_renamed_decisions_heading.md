---
name: ledger-misses-a-renamed-decisions-heading
description: accepted-items-ledger.sh only matches the literal heading "Decisions Requiring User Input" -- a plan revision that renames its own later decisions section (e.g. "Revision N's own open decisions (U19-U24)") is invisible to the script, which then reports nothing for that whole U-range rather than a gap. Third shape of the dod memory feedback_accepted_items_ledger_misses_indented_answered_line.md (first/second shapes: indented **Answered line, first-of-several same-named heading).
metadata:
  type: feedback
---

Found reviewing BL-17 Stage 4 (`plans/speech-rules/review-stage4.md`, 2026-11-17).
`plans/speech-rules/plan.md` has two decisions sections: `### Decisions Requiring User Input`
(U1-U18, the literal heading the script's `awk` anchors on) and, later, `### Revision 2's own
open decisions (U19-U24)` -- same shape (a `**Answered` line, `**U<n>` items), different wording
in the heading. `accepted-items-ledger.sh plans/speech-rules` ran clean and only printed U1-U18 --
it never saw U19-U24 at all, and said nothing about them, which reads as "nothing to check" rather
than "didn't look here."

**This is a third, distinct shape from `.claude/agent-memory/dod/feedback_accepted_items_ledger_
misses_indented_answered_line.md`'s two** (an indented `**Answered` continuation line; matching
only the *first* of several identically-named headings). That memory's "first vs. last heading"
framing does not cover this case, because the second section here is not named "Decisions
Requiring User Input" at all -- a wider regex or a "last match" fix would both still miss it.

**How to apply:** a plan with more than one place a user accepted numbered decisions -- whether by
a repeated heading or by a differently-worded one added in a later revision -- needs every such
section read by hand, not just the one(s) the script's exact heading string happens to match.
Treat "the ledger found no gap" as "the ledger found no gap *in the section it matched*," and
independently confirm, by reading the plan's own structure (grep for `### .*[Dd]ecision` /
`\*\*U[0-9]+` across the whole file, not just inside the script's own anchor), that no other
decisions section exists. In this case all six items (U19-U24) turned out to be correctly
accounted for in `implementation.md` once read by hand -- the gap was only in the mechanical
check's own coverage, not a real missed decision -- but that is exactly the silent-pass failure
mode the dod memory above already warns about: harmless this time, not guaranteed next time.

**Fix worth making** (not done from Reviewer -- doesn't edit `.claude/scripts/`): either rename a
later-revision decisions section to literally reuse "Decisions Requiring User Input" (the
Architect convention this script assumes), or widen the script to match any heading containing
"Decisions" and "User Input" case-insensitively, or any heading immediately followed by a
`**Answered` line and `**U<n>` items regardless of its exact wording.
