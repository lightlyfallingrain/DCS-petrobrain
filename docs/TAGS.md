# Tag vocabulary

A closed vocabulary for the inline `#tag`s used in split roadmap/backlog entries (see
`docs/DOC_CONVENTIONS.md`). Closed on purpose: `grep -rl '#needs-flight' */ROADMAP/ todo/backlog/`
is only a trustworthy *negative* — "nothing is tagged this" really means nothing is — if nothing
spells the same concept two ways. The gate in `.claude/scripts/` (added alongside the first
conversion) checks every inline tag in a converted entry file against this list; an unlisted tag
fails the gate rather than silently expanding the vocabulary.

**Two rules, both load-bearing:**

1. **Tag only what the entry's path and ID do not already say.** The ID tells you which
   subproject and whether it is a milestone or a backlog item (`<prefix>-<n>` vs `<prefix>-B<n>`);
   the directory tells you which repo area. Do not add a tag that restates either.
2. **Status is tagged on the same line as its checkbox marker**, never in frontmatter and never
   elsewhere in the entry — so the two cannot drift apart unnoticed. `docs/DOC_CONVENTIONS.md`
   has the full entry-file shape this implies.

## Status tags

One of these per entry, matching its checkbox marker (root `CLAUDE.md`, "Backlog Management":
`[ ]` open, `[~]` in progress, `[x]` done, `[?]` decision needed, `[>]` deferred):

| Tag | Checkbox | Meaning |
|---|---|---|
| `#status/open` | `[ ]` | Not started. |
| `#status/in-progress` | `[~]` | Underway; some sub-items done, others not. |
| `#status/done` | `[x]` | Complete as specified. |

`#status/decision-needed` (`[?]`) and `#status/deferred` (`[>]`) are reserved for when an entry in
that state is first split — not pre-minted here, so a converter adds exactly the tag a real entry
needs rather than guessing the set in advance.

## Cross-cutting tags

| Tag | Meaning |
|---|---|
| `#needs-flight` | A shipped, merged change with no in-cockpit observable and no dedicated
sortie yet — the mechanical replacement for a hand-kept "live acceptance debt" list
(`plans/obsidian-links-and-tags/plan.md`, "Trustworthy grep negatives over tags"). Means the code
is correct and merged; it does not mean anything is wrong. |

## `#topic/*` tags

**None exist yet.** A `#topic/*` tag must cross at least two subprojects to earn a place here — a
tag used in only one directory is a search `ls`/`grep` over that one directory already answers,
so it would just be a second spelling for something a plain path lookup already does. Add one here
the first time a second subproject's conversion actually needs to say the same cross-cutting thing
as the first.

## Adding a tag

1. Check it is not already covered by an ID or a path (rule 1 above).
2. Check it would be used in at least two subprojects if it is a `#topic/*` tag.
3. Add the row here, in the same commit as the first entry that uses it — never retroactively, so
   the gate never has to pass against a vocabulary that does not yet exist on disk.
