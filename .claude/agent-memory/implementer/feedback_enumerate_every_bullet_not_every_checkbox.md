---
name: enumerate-every-bullet-not-every-checkbox
description: When converting or auditing an entry list, enumerate every top-level bullet and judge each — a count of checkbox-shaped lines cannot see an item nobody wrote as a checkbox.
metadata:
  type: feedback
---

When the unit of work is "every item in a list document", enumerate **every top-level bullet** and
make a per-bullet judgement. Do not count the lines that match the item shape you expect.

**Why:** two stages of the roadmap conversion were each handed a mint count by their task brief,
and both briefs were wrong in opposite directions, for the same underlying reason — the shape they
counted was not the set.

- Stage 3 budgeted two new IDs; the answer was **zero**. Both apparently-new `- [ ]` blocks were an
  existing entry's own superseded text, deliberately kept, with the tell in the line immediately
  above (*"Original item follows, kept because its reasoning is what the decision rests on."*).
  `grep -cE '^- \['` over-counted.
- Stages 4/5 were handed a mint list naming only the entries whose text said *"no M-number"*. It
  missed **three** top-level `- **…**` prose bullets in a Backlog section that were items in every
  respect except a checkbox — two real outstanding work items and one duplicate record of an
  entry elsewhere in the file. `grep -cE '^- \['` under-counted, and so did any scan for an
  ID-shaped bold lead.

So the same instrument failed both ways within a week. The fix is not a better regex for items; it
is to derive boundaries from **every** top-level bullet (`^- \[` *and* `^- \*\*`) plus the section
headings, then decide one at a time what each thing is.

**How to apply:** any conversion, audit or coverage sweep over a hand-maintained list document —
`ROADMAP.md`, `BACKLOG.md`, `todo/*`, an acceptance card's findings. Print the derived boundary
table and read it before writing anything; it is also what catches an entry whose range you have
mis-bounded. Under-counting is the dangerous direction here, because the never-renumber rule makes
a missed item's eventual ID permanent and a wrongly-minted duplicate ID permanent too.

Related: [[project_obsidian_links_stage4_5_final]],
[[project_obsidian_links_stage3_todo_split]].
