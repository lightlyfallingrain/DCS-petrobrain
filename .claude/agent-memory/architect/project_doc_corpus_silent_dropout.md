---
name: doc-corpus-silent-dropout
description: Splitting or moving a documentation file drops it out of the knowledge-graph corpus silently — it has happened twice and is written into graph-corpus-files.sh's own comments
metadata:
  type: project
---

`.claude/scripts/graph-corpus-files.sh` builds the graph corpus as a **curated file list over
fixed filenames** (`for f in ROADMAP CLAUDE BACKLOG`). Any document split or move silently
removes content from the graph — **no error, only an answer that no longer mentions it.**

**Why:** it has already happened twice, and both incidents are recorded in that script's own
comments rather than anywhere a planner would look: the 2026-09-27 `body-layer/BACKLOG.md` split
"silently dropped 8,200 words of open items out of the corpus", and
`body-layer/docs/STRUCTURE.md` (84 KB of design rationale, moved out of `CLAUDE.md`) "would have
dropped out silently" had a `find "$sub/docs"` line not been added the same day.

**How to apply:** any plan that splits, moves or renames a `.md` file in the corpus must update
`graph-corpus-files.sh` **in the same change**, and prefer a `find` over a directory to a new
fixed filename — the comment's own conclusion is *"the corpus has to follow content rather than
enumerate filenames."*

Two companions worth knowing:
- **`graph-corpus-guard.sh` is an accidental safety net.** It refuses a rebuild whose corpus
  exceeds a file ceiling. A split that adds 100+ files **trips it loudly**, forcing a conscious
  decision. Do not pre-raise the ceiling in a migration plan — let it fire.
- **`graphify-dirty-flag.sh:41`** has the mirror-image bug: its regex
  (`[^/]+/(CLAUDE|ROADMAP)\.md`) decides whether a rebuild is *owed*. A new document path it does
  not match means edits stop flagging the graph dirty, so the graph launders staleness instead of
  merely lagging it (`docs/PROCESS.md`, "Documents before the graph").

See [[obsidian-doc-convention-verdict]].
