<!-- split-roadmap: see ROADMAP/ -->

This backlog moved to per-entry files under `body-layer/ROADMAP/`, one file per item
(`<ID>.md`, e.g. `BL-B42.md`), beside this subproject's milestone entries and distinguished only by
the `-B` in the ID, with an index at `body-layer/ROADMAP/body-layer-backlog.md`. See
`docs/DOC_CONVENTIONS.md` for the convention this follows. **The reason the backlog was split out of
`ROADMAP.md` in the first place still holds and is why it is now split again**: every file here is
in the knowledge-graph corpus, whose semantic extraction cache is keyed per file on content, so any
edit re-extracts that whole file through an extraction subagent — one backlog line used to re-bill
11,700 words of stable milestone history, and now re-bills one item. This file is kept, not deleted,
so every existing reference to `body-layer/BACKLOG.md` across `plans/`, `audits/` and research notes
keeps resolving.
