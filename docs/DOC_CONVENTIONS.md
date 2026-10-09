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
- `todo/` is the exception to "shares its subproject's ROADMAP/" — there is no `todo/ROADMAP.md`,
  so each split file there uses its own directory named after itself: `todo/backlog.md` →
  `todo/backlog/`, `todo/todo.md` → `todo/todo/`.

### Index basenames have to be distinct spellings, and `todo/` is where that bites

Obsidian resolves wikilinks by basename within one vault, so **no two files anywhere in the repo
may share a basename** — which is the same reason an index is never `index.md`. Under `todo/` the
constraint is tight, because the pointer files are already called `backlog.md` and `todo.md`:

| source | entry directory | index |
|---|---|---|
| `todo/backlog.md` | `todo/backlog/` | `todo/backlog/todo-backlog.md` |
| `todo/todo.md` | `todo/todo/` | `todo/todo/todo-tasks.md` |

`todo-tasks.md` rather than `todo-todo.md`: both are free of collisions, and the first reads as a
name instead of a stutter. **An index whose name is neither `*-roadmap.md` nor `*-backlog.md`
needs its shape added to the consistency gate's index glob** —
`roadmap-entry-consistency-gate.sh` finds indexes by filename pattern, so an unrecognised one makes
every entry in that directory report as linked from zero indexes. `*-tasks.md` was added there for
this reason.

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
- **`X-T<n>`** — `todo/todo.md`'s own items, minted 2026-10-09 by that file's conversion.
  Deliberately not `X-B<n>`: `todo/backlog.md` already owns that space, and these are two files'
  sequences. One ID space may not span two files' numbering, because the next-unused-number rule is
  read per file and two readers would hand out the same number. `T` for todo; the entries are
  `todo/todo/X-T<n>.md`.
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

### Narrative orientation prose stays in the index. It is never shredded into entries

**Added 2026-10-09, from `todo/todo.md`'s conversion, and it is a genuine addition rather than a
restatement of the paragraph above.** That paragraph is about a preamble and a tail. This is about
prose *between* entries, which the earlier conversions happened not to have:

- **Section prose under a grouping heading** — *"Flown on `main` with the brain wired to Ollama …
  the confirm-band fix was not in this flight"*, *"First flight of the o'clock scan loop. Six
  findings; two share a root cause."* It says what the entries below it have in common, which is
  not a property of any one of them.
- **A dated state narrative** — a "where things stand" section, including items written as prose
  bullets rather than checkboxes.
- **The grouping headings themselves**, which carry provenance: *which* sortie produced *which*
  finding. A flat list of entries loses that, and no entry can hold it, because it is the relation
  between them.

All of it belongs in the index, **verbatim**, and the headings become the index's sections. The
reason is not tidiness: for a cleared session this prose is often the only thing in the repo that
says where things stand, and distributing it across 24 files destroys it while appearing to
preserve every word. A converter's instinct is to treat every bullet as an entry; resist it on
anything that describes the set rather than a member of it.

**The one case that does cross over, and it needs a decision rather than a rule**: a prose bullet
that is itself a distinct outstanding action. `todo/todo.md`'s two *"Owed by the user, nothing else
blocks them"* bullets were promoted to `[[X-T1]]`/`[[X-T2]]` with a `**USER**` flag, because they
are real work that benefits from being linkable and greppable — and the index then **links** to
them instead of repeating their text, so there is still exactly one copy. Promoting a bullet means
minting its checkbox marker, which is the only text a conversion may add to a source line; say so
in the entry.

### Priority has to survive the split

Where the source document's own job is to be read first — `todo/todo.md` is named by path in root
`CLAUDE.md`'s Session Start step 2 and its Backlog Management section — **the index must make the
prioritised items at least as prominent as they were.** A reader landing on the index must not have
to open every entry to find out what is prioritised. Put them first, marked, above the narrative.

## Tags

See `docs/TAGS.md` for the vocabulary. Two rules repeated here because they decide the entry file
shape above: tag only what the ID and path do not already say, and tag status on the same line as
its checkbox marker, never in frontmatter and never elsewhere in the entry.

## `**OPEN**` and `**USER**` — a contradiction found during a split is carried, not resolved

When two records being folded into one entry file disagree about whether the underlying work is
actually done — not merely using different checkbox conventions for the same fact, but asserting
different things — a converter does not pick a side. Carry both texts verbatim into the one entry
file and mark the disagreement with one of two prose markers, inline, not as a tag (there is no
`#status/*` spelling for "this is contested"):

- **`**USER**`** — blocked on the user: a judgement only they can make, such as which of two
  disagreeing records is right about what was actually flown. User direction, 2026-10-09: *"For
  items that are waiting on me, flag them **USER**. That makes it clear and a different
  subcategory of **OPEN**."*
- **`**OPEN**`** — unresolved but not waiting on them; a later stage or a measurement can settle
  it (including a converter's own mechanical check, such as `git merge-base --is-ancestor`, that
  resolves the *fact* without being authorized to resolve the *document* — the point of not
  silently fixing it in place is that the next reader sees the disagreement existed, not just its
  resolution).

**`**USER**` is a subcategory of `**OPEN**`, not a replacement.** Every `**USER**` item is also
open; not every open item is waiting on the user. Do not apply `#needs-flight` to a contradicted
entry while it carries either marker — tagging it picks a side before the contradiction is
resolved. This is distinct from `#status/decision-needed` (`[?]`), which marks an entry wholly
blocked on a decision from the outset, not a contradiction a conversion surfaced between two
pre-existing records.

## Document provenance

**The underlying question this answers: "how did we get here?"** — which document brought a
roadmap entry to the state it is in, or is expected to bring it there. Full rationale and the
measurements behind the design: `plans/obsidian-links-and-tags/plan-document-graph.md`, Stage A0.

**Generated, delimited, and cited what already exists in prose — nothing inferred.** A roadmap
entry's own text already names the research notes, acceptance cards and plans that brought it to
its current state (`[[AA-3]]`'s own entry cites five of them, in plain prose). The generator
(`.claude/scripts/doc-provenance-refresh.sh`) lifts exactly those citations into a block on the
**cited document**, never on the entry — Obsidian's backlinks pane supplies the reverse list
(every document that answers "how did we get to `AA-3`") for free, and the entry files, which
churn constantly, stay untouched.

```markdown
<!-- doc-provenance:start -->
**Evidence for:** [[AA-3]]
<!-- doc-provenance:end -->
```

Placed immediately after the document's H1 (or at the very top, for a `plans/*/plan.md` that
opens straight into `### Goal` with no H1 at all — true of every plan in this corpus today).
One line per citing entry, so a document cited by more than one entry gains a second line inside
the same block rather than a second block.

**The label states which kind of relation it is, by the citing document's own kind** — not a
human judgement call per document:

| document kind | label | meaning |
|---|---|---|
| a research note (`*/research/*.md`) | `**Evidence for:**` | recon or a measurement that informed the entry |
| an acceptance card (`docs/acceptance/*.md`) | `**Flight for:**` | an in-cockpit test of the entry |
| a plan (`plans/<name>/plan.md`) | `**Decision for:**` | the design decision behind the entry |

**A plan directory is one unit — the block always lands on `plan.md`**, regardless of which
sibling file (`implementation.md`, `review.md`, `security-deep-analysis.md`, …) the citing prose
actually names, or whether it names the bare directory with no file at all. `plan.md` is the
directory's designated representative for this purpose, the same convention Stage B's own
document-unit rule uses for a plan.

**Scope is exactly what the entries cite — nothing swept, nothing inferred.** This stage covers
only `audio-adapter/ROADMAP/AA-*.md`'s own citations; a roadmap entry with no citation in its
prose gets no block for anyone, and inferring one from git history (a branch name, a commit) is a
later, separate decision this stage deliberately does not make.

**Regenerate on demand** with `.claude/scripts/doc-provenance-refresh.sh` — deterministic and
idempotent; running it twice in a row changes nothing. **Never runs in a hook**, the same rule as
every other generator in this convention: a regenerator that trips its own guard mid-commit turns
one bad run into a permanent silent outage.
`.claude/scripts/doc-provenance-gate.sh` is **verify-only** — it never writes, it regenerates
every cited document into a temporary directory and diffs the result against the real file, and
it fails loudly (naming the file and printing the diff) on a stale block, a hand-edit inside the
delimited region, a malformed or duplicated delimiter pair, or a generated `[[ID]]` that does not
resolve to a real entry file.

## Gates

Three mechanical checks, run before committing a converted file (and available to run standalone):

- **Consistency** (`.claude/scripts/roadmap-entry-consistency-gate.sh`): every `[[ID]]` in a
  converted tree resolves to an existing `<ID>.md`, across the union of every converted directory
  (not just the one the link was written from — a research note or a plan citing a roadmap ID
  from outside any `*/ROADMAP/` directory is a normal, correct link); every entry file's name
  matches `<ID>.md` with an H1 whose first token is that same ID; every entry appears in exactly
  one index.
- **Document provenance** (`.claude/scripts/doc-provenance-gate.sh`): see "Document provenance"
  above.
- **Tag vocabulary** (`.claude/scripts/roadmap-tag-vocabulary-gate.sh`): every inline `#tag` in a
  converted entry file appears in `docs/TAGS.md`.

All three fail loudly (non-zero exit, message naming the offending file) rather than silently —
a dangling link, a stale or hand-edited provenance block, or an unlisted tag is exactly the kind
of defect that looks fine until someone clicks it or greps for it.

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
