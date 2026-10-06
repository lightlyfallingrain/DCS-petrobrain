---
name: scope-by-the-right-benefit
description: Do not scope a change down using a cost/benefit measurement of a different benefit than the one the user actually asked for — some benefits only exist when complete
metadata:
  type: feedback
---

**Before recommending a stopping point, name which benefit the measurement is about, and check it is
the benefit the user wants.** Some benefits scale with coverage; others only exist at completion.

**Why:** 2026-10-06, the Obsidian doc-convention plan. The user's stated benefit was *human
navigation* — browsing all subprojects in one Obsidian vault. I measured *agent token cost*, found
49% of it concentrated in two files, and recommended converting those two and stopping. He overruled
it: *"a human reader benefits from all sub-systems following this convention and being browsable via
Obsidian."* A graph view and a tag pane covering three of six subprojects shows holes, not
structure — the navigation benefit was worth near-zero at 50% coverage, while the token benefit was
worth exactly 49%. The table was correct and answered the wrong question.

**How to apply:** when writing a cost/benefit table, label the benefit each column measures. If the
primary benefit is one the user named and it is *completeness-shaped* — navigation, a trustworthy
`grep` negative, a convention, an invariant, a vocabulary — a partial-adoption recommendation needs
an argument that partial coverage is actually worth its share, not just a cost figure. The same trap
in reverse: a cost that only appears at full scope (here, the corpus guard's file ceiling and the
single-vault requirement) is invisible in a per-file table.

See [[obsidian-doc-convention-verdict]].
