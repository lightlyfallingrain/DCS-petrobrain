# Agent memory — this is not an index

Your memories are the `feedback_<topic>.md` / `project_<topic>.md` files beside this one.
**There is no index to read or to maintain.** Search them — and every other role's, which you
could never see before — with:

    python3 .claude/scripts/memory-search.py <terms>

No query lists everything, newest first. Exit status 1 means no match, which means *not indexed
yet*, never *does not exist*. Each file's `description:` frontmatter is its index entry, so write
that line as the hook a future reader needs.

A pointer rather than an index because the harness injects this file into every agent's system
prompt whether or not anything reads it. Why that changed: root `CLAUDE.md`, "When to query it".
