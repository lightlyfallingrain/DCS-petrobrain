# Agent memory — this is not an index

Your memories are the `feedback_<topic>.md` / `project_<topic>.md` files beside this one.
**There is no index to read or to maintain.** Search them — and every other role's, which you
could never see before — with:

    python3 .claude/scripts/memory-search.py <terms>

No query lists everything, newest first. Exit status 1 means no match, which means *not indexed
yet*, never *does not exist*. Each file's `description:` frontmatter is its index entry, so write
that line as the hook a future reader needs.

This file is a pointer because the harness injects it into every agent's system prompt whether or
not anything reads it. It used to be a hand-kept index: it drifted, outgrew its read limit, and a
hook asked six agents in one session to compact it. Full account: `todo/todo/X-T25.md`.
