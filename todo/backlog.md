<!-- split-roadmap: see ROADMAP/ -->

This backlog moved to per-entry files under `todo/backlog/`, one file per item (`<ID>.md`, e.g.
`X-B29.md`), with an index at `todo/backlog/todo-backlog.md`. See `docs/DOC_CONVENTIONS.md` for the
convention this follows. **The reason this backlog was split out of `todo/todo.md` in the first
place still holds and is why it is now split again**: every file here is in the knowledge-graph
corpus, whose semantic extraction cache is keyed per file on content, so any edit re-extracts that
whole file through an extraction subagent — editing one backlog item used to re-bill the other
thirty-odd, and now re-bills one. This file is kept, not deleted, so every existing reference to
`todo/backlog.md` across `CLAUDE.md`, `AGENTS.md`, `plans/`, `audits/` and research notes keeps
resolving.
