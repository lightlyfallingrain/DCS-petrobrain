---
name: narrative-prose-stays-in-the-index
description: When splitting a document into per-entry files, prose that describes the set — section narrative, a dated state account, the headings themselves — goes into the index verbatim, never into entries
metadata:
  type: feedback
---

**When converting a document to per-entry files, anything that describes the *set* rather than a
*member* of it belongs in the index, verbatim — section prose under a grouping heading, a dated
"where things stand" narrative, and the grouping headings themselves.** Only items become entries.

**Why:** for a cleared session this prose is often the only thing in the repo that says where
things stand, and distributing it across two dozen files destroys it *while appearing to preserve
every word* — nothing is deleted, so nothing looks wrong. The headings specifically carry a
relation (which sortie produced which finding) that no single entry can hold. `todo/todo.md`'s
conversion, 2026-10-09: 68 of 399 non-blank lines were this material. The rule is now in
`docs/DOC_CONVENTIONS.md` under "Narrative orientation prose stays in the index".

**How to apply:** a converter's instinct is to treat every bullet as an entry — resist it on
anything describing the set. Two corollaries that cost real thought:

- **The one crossover case is a decision, not a rule.** A prose bullet that is itself a distinct
  outstanding action can be promoted to an entry (two were, as `X-T1`/`X-T2` with `**USER**`),
  but then the narrative must **link** to it rather than repeat its text, so there is still one
  copy. Promoting means minting its checkbox marker — the only text a conversion may add to a
  source line. Say so in the entry.
- **Where the source document's own job is to be read first, priority has to survive the split.**
  `todo/todo.md` is named by path in root `CLAUDE.md`'s Session Start step 2, so its index opens
  with the prioritised items, marked, above the narrative. A reader must not have to open every
  entry to learn what is prioritised.

Related: [[project_obsidian_links_stage3_todo_split]].
