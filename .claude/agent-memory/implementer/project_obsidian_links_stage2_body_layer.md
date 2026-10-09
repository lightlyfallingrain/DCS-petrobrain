---
name: obsidian-links-stage2-body-layer
description: body-layer/ROADMAP.md split (68 entries, 2431 lines) — fold strategy, ID count overrun, the one real contradiction found
metadata:
  type: project
---

Converted body-layer/ROADMAP.md (the repo's highest-churn doc, 2431 lines/68 checkbox entries)
into `body-layer/ROADMAP/*.md` per `plans/obsidian-links-and-tags/plan.md` Stage 2. Full record:
`plans/obsidian-links-and-tags/implementation.md`'s 2026-10-09 section.

**Script-assisted extraction, not hand-retyping, is the right move at this scale.** A Python
script reading verbatim line ranges from the source (via `git show`/plain `open()`) and writing
each entry file eliminates the transcription-error risk that dominates a 2431-line conversion —
far cheaper than manually copying 68 blocks via Edit/Write. Fold cases (two source blocks into one
entry) concatenate both texts verbatim with a connecting heading rather than editorially merging
prose — "nothing may be lost" beats "nothing may be redundant."

**The plan's "~27 new IDs" estimate was off by 11 (38 actual).** The plan's debt-list fold
analysis undercounted how many debt-list entries are self-contained historical records (sortie
closures, a vocabulary-closure note) with no Status-section counterpart to fold into — each of
those still needs its own ID. Don't trust a plan's own arithmetic on fold counts; re-derive by
actually reading every entry.

**A plan's named "known disagreement" example can turn out, on close reading, not to be one.**
The plan named `fix/contact-report-flood` as a disagreement case; both its debt-list and
Status-section records actually agree on every fact (the Status entry even says "see the debt
entry above"). The real disagreement I found was elsewhere and unnamed by the plan (`BL-W12`,
group cohesion redesign, self-contradicts within one entry about merge status — "Merged to main"
and "Not merged as of this entry" in the same paragraph). Lesson: read every entry's full text
rather than trusting a plan's pointer to where a contradiction supposedly is.

**`**OPEN**` vs `**USER**` markers**: added to `docs/DOC_CONVENTIONS.md`. `**USER**` is a
judgement only the user can make; `**OPEN**` is everything else unresolved, including a
contradiction a converter can privately verify (e.g. via `git merge-base --is-ancestor`) but is
instructed not to silently fix in place. `**USER**` is a subcategory of `**OPEN**`, never a
replacement.

**Checkbox vs. flight-status must be disentangled when folding a debt list.** The source used
`[ ]` to mean "not yet flown" even for code-complete work; the new convention's checkbox tracks
code-completion and `#needs-flight` carries flight status separately (matches `AA-2`/`AA-5`'s
established `#status/done #needs-flight` pattern). Converting a debt-list-style doc means
re-deriving the checkbox from actual code-completion state, not copying the old symbol.

**Corpus ceiling was already breached (204 vs 200) before this stage touched anything** — purely
from Stage 1 (audio-adapter). Raised to 300 (measured post-conversion: 263), with the pre-existing
breach recorded in the guard script's own comment so nobody reads the overrun as this stage's
fault.
