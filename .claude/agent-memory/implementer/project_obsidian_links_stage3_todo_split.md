---
name: obsidian-links-stage3-todo-split
description: Stage 3 of the roadmap split (body-layer BACKLOG, todo/backlog, todo/todo) — un-IDed blocks are usually an entry's own history, and both link gates missed todo/todo/ entirely
metadata:
  type: project
---

Stage 3 of `plans/obsidian-links-and-tags/plan.md` converted `body-layer/BACKLOG.md` (46 entries),
`todo/backlog.md` (34) and `todo/todo.md` (24, new `X-T<n>` space). Three things generalise past
this stage.

**An un-IDed checkbox block in an entry-list document is usually an existing entry's own
superseded text, not a new item.** The plan budgeted one mint per backlog file; both candidates
turned out to be this. The tell is a sentence immediately *above* the block — *"Original item
follows"*, *"Original text follows"* — or an explicit `(original text)` inside the bold lead
(`BL-B34 (original text)`, the same ID twice on purpose). Each folds into the owning entry's file
as a second checkbox block, with its own state untouched.

**Why:** a naive `grep -cE '^- \['` against the ID list reports a mint owed, and root
`CLAUDE.md`'s never-renumber rule then makes the wrong ID permanent — an ID that silently means a
different thing is worse than no ID.

**How to apply:** before minting during a conversion, read the line above the un-IDed block.
Stages 4 and 5 (world-model, aircraft-layer, mission-interpreter) are known to carry duplicated
debt entries, so expect this again.

**Both link gates discovered split directories as `*/ROADMAP` next to a `pyproject.toml` plus a
hardcoded `todo/backlog` — so `todo/todo/` matched neither and they passed while never scanning
25 files.** Fixed in `roadmap-entry-consistency-gate.sh` and `roadmap-tag-vocabulary-gate.sh`;
the consistency gate's index glob also needed `*-tasks.md`, since it finds indexes by filename
pattern (`*-roadmap.md`/`*-backlog.md`) and an index named anything else makes every entry in its
directory report as linked from zero indexes.

**Why:** a green run from a gate that skips a directory is not evidence. Only the mutation was —
dangling link, deleted index row, unlisted tag, each reported and each restored by `shasum`.

**How to apply:** whenever a conversion creates a *new directory shape*, test each consumer
script's real glob against the real new path (`printf | grep -E '<the script's own regex>'`)
rather than reading the regex. `graph-corpus-files.sh` and `graphify-dirty-flag.sh` were already
recursive here; `push-roadmap-gate.sh` does not match `todo/` and correctly should not.

**A mostly-narrative document splits at ~70%, not 90%+.** `todo/todo.md`: 9,090 → 2,720 tokens,
against 93% and 90% for the two backlogs. Its index is 2,261 tokens — nine times its median entry
— because the orientation narrative that must stay in the index is a quarter of the document.
Related: [[project_obsidian_links_stage2_body_layer]].
