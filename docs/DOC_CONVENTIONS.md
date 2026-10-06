# Documentation conventions: split roadmaps/backlogs, IDs, Obsidian

How a subproject's `ROADMAP.md`/`BACKLOG.md` gets split into one file per entry, how entries are
identified and linked, and the one-time Obsidian setup that makes the result pleasant to browse.
Full rationale and the decision trail: `plans/obsidian-links-and-tags/plan.md`. This file states
the convention as it stands; the plan records why.

**Do not look here for which subprojects are converted.** `ls */ROADMAP/ 2>/dev/null` answers
that mechanically. A written list goes stale the moment a subproject converts and nobody remembers
to update this file — the exact failure root `CLAUDE.md`'s "Current priority" and "Subprojects"
sections warn about for the subproject list itself, applied to this one.

## Directory layout

- `<subproject>/ROADMAP/` holds one file per entry, named `<ID>.md` — the ID alone, nothing else
  (`AA-4.7.md`, not `AA-4.7-Press-to-readback-latency.md`).
- Backlog entries share the same directory, distinguished by their ID's `-B` (`AA-B1.md` sits
  beside `AA-4.7.md`). A second `BACKLOG/` directory would double the corpus-script and link-gate
  surface for one ID-prefix distinction the ID already carries.
- One index per source file, at `<subproject>/ROADMAP/<subproject>-roadmap.md` (and
  `<subproject>-backlog.md` where a subproject's backlog is split separately, e.g. a future
  `body-layer/ROADMAP/body-layer-backlog.md`) — never `index.md`, which would collide across
  subprojects in Obsidian's single-vault basename namespace.
- The original `<subproject>/ROADMAP.md` (and `BACKLOG.md`) stays in place as a 4-line pointer,
  carrying the sentinel `<!-- split-roadmap: see ROADMAP/ -->` on its own first line. **Never
  delete it** — every historical reference to that path, across `plans/`, `audits/` and research
  notes, depends on the path continuing to resolve to something. The sentinel is what lets a
  consumer script or agent tell a pointer apart from a real roadmap instead of reading four lines
  and reporting success against an empty one.
- `todo/backlog.md` is the one exception to "shares its subproject's ROADMAP/" — there is no
  `todo/ROADMAP.md`, so a split `todo/backlog.md` uses its own `todo/backlog/` directory.

## The ID scheme

Root `CLAUDE.md`'s "Backlog Management" already defines `<prefix>-B<n>` for backlog items and
bare `<prefix>-<n>` for milestones, both never-reuse, never-renumber. This convention adds one
more marker and one formatting rule:

- **`<prefix>-W<n>`** — a work item that is neither a milestone (the bare `<prefix>-<n>` space,
  which stays reserved for a subproject's own numbered plan stages, e.g. `BL-12`, `M12`) nor a
  backlog item (which means "not yet done", and most historical work items are done). Numbered
  from 1 per subproject, independent of both other spaces. Where a subproject has no declared
  milestone series consuming the bare space (audio-adapter, aircraft-layer), its Status entries
  mint into the bare space directly instead (`AA-1`…`AA-5`, `AC-1`…`AC-8`) — one rule, not a
  per-subproject exception list.
- **Dotted sub-IDs** (`AA-4.7`, not `AA-4-7`) for a milestone's own stages. The dot is load-bearing:
  it is the separator in hundreds of existing prose mentions across `plans/`, `audits/` and
  research notes, and the ID is now also the filename and the link text, so changing it would
  make every one of those mentions un-greppable against the file that carries the content.
- **World-model's `M<n>` stays irregular** — milestones are bare `M<n>`, backlog is `WM-B<n>`,
  work items are `WM-W<n>`. Fixing the mismatch would mean renaming `M5` → `WM-5` across several
  hundred prose mentions that `docs/PROCESS.md` ("Superseding a decision") forbids rewriting.
  Recorded, not fixed.
- **Numbers are assigned in document order, top to bottom of the file being converted** — so a
  rebase or a redone conversion produces the same numbers, rather than depending on whatever order
  a converter happened to work in.
- **The next unused number is read, never counted** (the same rule root `CLAUDE.md` states for
  backlog IDs, applied to files): `ls <sub>/ROADMAP/ | grep -oE '^[A-Z]+-W[0-9]+' | sort -t W -k2 -n | tail -1`.
- **No ID is minted outside a conversion.** While a subproject's roadmap is mid-split, an
  un-IDed entry in the not-yet-converted original file stays un-IDed, or an interleaved commit on
  the same file could claim a number the conversion branch already assumed was free.
- **One subproject per branch, one branch per subproject's conversion at a time.** Different
  subprojects' ID spaces (`BL-W*`, `WM-W*`, …) are disjoint by construction, so two sessions
  converting different subprojects cannot collide regardless — this rule is about not having two
  conversions of the *same* subproject's file in flight together.

## Entry file shape

```
# AA-4.7 — Press-to-readback latency

- [ ] **Press-to-readback is ~3 s, and that is the next real problem.** #status/open Measured on
  the 2026-09-23 sortie …
```

- **No frontmatter.** The H1 is the only title, and it is read by the Front Matter Title plugin's
  `#heading` template (see "Obsidian setup" below) for display — a frontmatter `title:` field
  would be a second copy of the same fact with nothing to keep the two in sync.
- **H1 first token is the ID, exactly matching the filename.** `AA-4.7.md` contains `# AA-4.7 — …`.
  This is also one of the two things the consistency gate checks (see "Gates" below).
- **The original checkbox-and-tag line is preserved**, now as the entry's own first content line.
  Status lives there, next to its checkbox marker, exactly as it did before the split — see
  `docs/TAGS.md` for the tag vocabulary and why status is tagged in place rather than elsewhere.
- **Cross-references to other entries are bare `[[<ID>]]` wikilinks** — `[[AA-1.6]]`, never
  `[[AA-1.6|Stage 6]]`. Measured on the user's own Obsidian install, 2026-10-06: frontmatter
  aliases do not resolve `[[wikilinks]]` here, so an alias-based link form was never viable in the
  first place; a plain filename link is also the only form that is simultaneously a working
  Obsidian link, a working `grep` target (identical spelling to the 441+ historical prose
  mentions of the same ID), and immune to a retitle ever breaking a referrer, since no referrer
  carries the title. A prose reference to an *unconverted* subproject's entry (e.g.
  "`body-layer/ROADMAP.md`'s BL-10 entry" from an audio-adapter file) stays plain prose — it only
  becomes a link once that subproject's own entry file exists to link to.
- **A parent milestone with its own stages links down to them**, e.g. `Stages: [[AA-1.1]] [[AA-1.2]]
  …` — so opening the parent alone does not lose the stage breakdown that used to be nested
  bullets in the same file.

## Index shape

The index carries **links and titles only — never status**. Status lives on the entry, so the
index cannot drift out of sync with it. A grouped list (by milestone, with stages nested) is
enough; it is not a generated table of contents — see "TOC helper" below for that.

Non-entry prose that lived at the top or bottom of the original file (a subproject's "what this
is" preamble, a trailing "Keeping this current" note) moves into the index as its preamble —
it was never an entry and has nowhere else to go that keeps it next to the roadmap it describes.

## Tags

See `docs/TAGS.md` for the vocabulary. Two rules repeated here because they decide the entry file
shape above: tag only what the ID and path do not already say, and tag status on the same line as
its checkbox marker, never in frontmatter and never elsewhere in the entry.

## Gates

Two mechanical checks, run before committing a converted file (and available to run standalone):

- **Consistency** (`.claude/scripts/roadmap-entry-consistency-gate.sh`): every `[[ID]]` in a
  converted tree resolves to an existing `<ID>.md`; every entry file's name matches `<ID>.md` with
  an H1 whose first token is that same ID; every entry appears in exactly one index.
- **Tag vocabulary** (`.claude/scripts/roadmap-tag-vocabulary-gate.sh`): every inline `#tag` in a
  converted entry file appears in `docs/TAGS.md`.

Both fail loudly (non-zero exit, message naming the offending file) rather than silently —
a dangling link or an unlisted tag is exactly the kind of defect that looks fine until someone
clicks it or greps for it.

## TOC helper

`ls <subproject>/ROADMAP/` is a column of bare IDs, which costs a directory reader the ~200-token
table of contents a single large file used to give for free. `.claude/scripts/roadmap-toc.sh
<subproject>/ROADMAP/` restores it with standard bash tools (`awk` over each file's own H1 plus
its tag line) — one line per entry: ID, title, status tags. No index read needed.

## Obsidian

**Vault scope: one vault, rooted at the repo root.** `[[AA-4.7]]` resolving from inside
`body-layer/ROADMAP/` needs every entry across every subproject in the same vault — Obsidian
resolves wikilinks by basename within one vault, not per-directory.

**`.obsidian/` is gitignored, everywhere, unanchored** (`.gitignore`: `.obsidian/`) — per-user
editor state, and `workspace.json` rewrites on every pane move. This means **the vault
configuration is not recorded in the repo.** A fresh clone opens the repo root as a vault by hand
(Obsidian: "Open folder as vault") and gets working `[[links]]` immediately — plain filename links
resolve in stock Obsidian with no plugin and no configuration.

**What a reader does not get for free: a readable sidebar.** Without the setup below, the
explorer, graph and search show bare IDs (`AA-4.7`, not "Press-to-readback latency") — this is
not broken, it degrades safely, and every link still resolves and every file still reads. The one
thing worth doing once, by hand, per vault:

1. Install the community plugin **Front Matter Title** (`snezhig/obsidian-front-matter-title`).
2. Set its **Common main template to `#heading`** (a reserved word meaning "the file's first
   heading") and **Common fallback template to `_basename`**. No frontmatter is needed anywhere —
   `#heading` reads the entry's own H1, which is the file's only copy of its title.
3. Turn off Settings → Appearance → **"Show inline title"**, or every entry renders its title
   twice (once as the plugin's inline title, once as the literal H1 line).

This was measured, not assumed, on the user's own install 2026-10-06: four test notes of
different shapes (frontmatter title with an H1, frontmatter title with no H1, an H1 with no
frontmatter, an H1 with punctuation) all displayed correctly under this configuration, and a
frontmatter-alias approach to the link form itself was tried first and **failed** — aliases never
resolved `[[wikilinks]]` on this install, which is why the link form above is a plain filename
link rather than anything alias-based.

**What depends on the plugin, and what does not.** Only the *display* — explorer, graph, search,
backlinks — depends on it. The *links* depend on nothing beyond stock Obsidian: `[[AA-4.7]]`
resolves with no plugin installed, just with a bare ID instead of a title in every view. If the
plugin is ever abandoned or broken by an Obsidian update, the sidebar reverts to bare IDs and
nothing else changes — no broken link, no data loss, no migration.

**Rendered link text is not replaced.** Even with the plugin's own link-rendering feature
enabled, a `[[AA-4.7]]` link still displays as `AA-4.7`, not its title. Accepted: the raw text
says `AA-4.7` too, and so does every historical prose mention of the same ID, so this is
consistent rather than a regression.
