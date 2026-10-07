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

## Topic tags

**None approved yet.** This section used to require a `#topic/*` tag to cross **at least two
subprojects** — the wrong axis. The user's own worked example (`AA-3` is about `#SPU-8`,
`#aircraft-manipulation`, and `#audio`) crosses two *document kinds* inside one subproject
(a roadmap entry and the research notes/acceptance cards that informed it), and no path lookup
relates those directories. `#topic/*` had zero members when this was rewritten, so nothing needed
renaming — the rule was replaced before its first real use. Full rationale and the measurements
behind the numbers below: `plans/obsidian-links-and-tags/plan-document-graph.md`, §2–§3, §8.

**Three rules, all load-bearing:**

1. **Crosses at least two document kinds** — roadmap entry / research note / acceptance card /
   plan. A tag confined to one kind in one directory is something `ls`/`grep` over that directory
   already answers, so it would just be a second spelling for a plain path lookup. This is the old
   rule's sound half, re-aimed at the axis that actually matters.
2. **Lands in the navigable band: 3–25 document units**, measured repo-wide at admission by
   `.claude/scripts/doc-tags-propose.sh` and recorded in the tag's own section with the date.
   Below 3 it connects almost nothing and is not a hub worth having. Above 25 it is a hub that
   means nothing — `#audio` alone would connect 80 documents repo-wide, which is exactly the
   undifferentiated fan the closed vocabulary exists to prevent — and it must be split into
   narrower tags instead (`#audio` → `#audio-playback`, `#audio-volume`, `#audio-transport`).
   Two cheaper fixes were measured and both failed before this rule was settled: requiring more
   mentions per document kills a good tag faster than it tames a bad one, and anchoring the match
   to titles/headings only drops the sketch's own centre (`AA-3`'s H1 never says "SPU-8"). The
   band is the only lever that works, which is why it is the admission rule rather than a
   judgement call.
3. **Flat spelling for topics** (`#SPU-8`, `#aircraft-manipulation`), never prefixed. The
   machine-read tags above (`#status/*`, `#needs-flight`) keep their prefix — they are a different
   kind of thing, read by a gate rather than clicked for navigation.

**Why the closed vocabulary still matters — kept verbatim in substance from before this
rewrite.** `grep -rl '#SPU-8'` is only a trustworthy *negative* — "nothing is tagged this" really
means nothing is — if nothing spells the same concept two ways. That benefit does not depend on
which axis admits a tag; it depends on every tag that exists being listed here and nowhere else.

**Format: one short section per tag, not a table row.** A match pattern needs alternation, and
`|` inside a markdown table cell has to be escaped — precisely the two-spellings footgun this file
exists to prevent, in the file that documents it. A section looks like this once a tag is
approved:

```markdown
### `#SPU-8`

- **Matches:** `SPU-?8`
- **Measured:** 18 units, 2026-10-07 (9 research · 4 acceptance · 3 plan · 2 roadmap)
- The Mi-24P intercom box: its cockpit arguments, its gating behaviour, and the audio path it owns.
```

## Adding a tag

1. Check it is not already covered by an ID or a path (the first rule at the top of this file).
2. Run `.claude/scripts/doc-tags-propose.sh` and check the candidate's measured repo-wide reach
   lands in the 3–25 band. A tag outside the band is reported `TOO BROAD` (split it first) or
   `TOO NARROW` (it is not a hub).
3. The user approves the candidate — the vocabulary is closed, so nothing here is minted without
   that approval (`plans/obsidian-links-and-tags/plan-document-graph.md`, §2).
4. Add the section here, in the same commit as the first document whose generated block emits
   that tag — never retroactively, so the gate never has to pass against a vocabulary that does
   not yet exist on disk. The generator (`.claude/scripts/doc-provenance-refresh.sh`) refuses to
   emit a tag with no approved section, so a document can never carry a tag this file does not
   list.

**Drift**: `doc-tags-propose.sh` also re-measures every already-approved tag's band each time it
runs and reports one that has grown out of band (e.g. admitted at 20 units, now 40) — the same
tool that proposes a tag is the one that grooms it, which is the standing tiebreak for anything
automatable in this convention (*"more automation is better"*, the user's own words).
