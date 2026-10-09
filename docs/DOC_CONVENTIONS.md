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
  `<subproject>-backlog.md` where a subproject's backlog is split separately, as
  `body-layer/ROADMAP/body-layer-backlog.md` is) — never `index.md`, which would collide across
  subprojects in Obsidian's single-vault basename namespace.
- The original `<subproject>/ROADMAP.md` (and `BACKLOG.md`) stays in place as a 4-line pointer,
  carrying the sentinel `<!-- split-roadmap: see ROADMAP/ -->` on its own first line. **Never
  delete it** — every historical reference to that path, across `plans/`, `audits/` and research
  notes, depends on the path continuing to resolve to something. The sentinel is what lets a
  consumer script or agent tell a pointer apart from a real roadmap instead of reading four lines
  and reporting success against an empty one.
- **The sentinel's literal text is `<!-- split-roadmap: see ROADMAP/ -->` in all eight pointers,
  including the two under `todo/`, where there is no `ROADMAP/` directory at all. That is correct
  and must not be "adapted" to `see todo/`.** It is a machine-readable marker, matched as a fixed
  string by every consumer that knows about it; making it descriptive per location would break all
  of those at once and buy nothing a reader needs, since the four lines underneath say in prose
  where the content went. Do not derive the destination directory from the sentinel's text —
  derive it the way `roadmap-source.sh` does, from the pointer's own path.
- **Resolve a pointer with `.claude/scripts/roadmap-source.sh <path>`** rather than by carrying a
  prose caveat about the sentinel. It prints the index file that replaced the pointer (`--dir` for
  the directory, `--entries` for every entry file, `--is-pointer` for a silent test) and passes a
  non-pointer path straight through, so a consumer can pipe every roadmap path through it
  unconditionally. This exists because the prose-caveat approach was tried and measurably failed:
  eleven consumers each carried their own wording, and review round 4 found roughly half of every
  such pair had been missed — a counting consumer reporting success off an empty read, and a
  writing one told to record a merge into a file nothing reads.
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
  which stays reserved for a subproject's own numbered plan stages, e.g. `BL-12`) nor a
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
- **World-model's milestones are `WM-M<n>` — REVISED 2026-10-09, by user direction.** *"for the
  world model `M<n>`, rename them `WM-M<n>`. Then it fits the pattern used elsewhere."* So
  world-model is now regular: milestones `WM-M0`…`WM-M11`, work items `WM-W<n>`, backlog
  `WM-B<n>`, all three sharing the subproject's own prefix. **There is no irregular ID shape left
  anywhere in the repo**, and the three consumers that had been widened to recognise one were
  simplified back to `^[A-Z]+-[A-Za-z0-9.]+$` the same day.

  **Why this was affordable when the version below judged it was not.** That judgement priced the
  rename as `M5` → `WM-5`, which destroys the `M5` substring and strands every historical mention.
  `WM-M5` **contains** `M5`, so a `grep M5` over the repo still finds the new ID *and* the ~2,100
  untouched mentions in research notes, plans, audits, agent memory and source. The rename
  therefore only had to touch documents that assert **current** state — 185 mentions across 34
  files (world-model's own entries and index, `world-model/CLAUDE.md`, root `ROADMAP.md`,
  `world-model/docs/`, `docs/concept/`) — and could leave the dated record alone, which is what
  `docs/PROCESS.md` ("Superseding a decision") actually requires.

  **The asymmetry that remains, stated because it is the cost that was accepted:** a `grep WM-M5`
  does **not** find the bare `M5` mentions in historical documents. When searching for a
  world-model milestone's history, search the bare form; the new form finds only live documents.
  File *names* outside `world-model/ROADMAP/` keep the bare form too, deliberately —
  `world-model/docs/M7_RUN_INSTRUCTIONS.md`, `M8_PROBE_STORE.md`, `M9_OSM_RUN_INSTRUCTIONS.md` are
  cited by path, and renaming them would break citations to buy nothing the convention asks for.

  **Which documents the rename reaches, stated as a rule rather than as the list that was swept.**
  A document is rewritten to `WM-M<n>` if it asserts what is true **now**; it keeps the bare form if
  it records what was true **then**. By that test:

  | rewritten (live) | left bare (dated record) |
  |---|---|
  | every `*/ROADMAP/` entry and index, every `CLAUDE.md`, `AGENTS.md`, root `ROADMAP.md`, `docs/` (excluding the two directories opposite), `world-model/docs/`, `world-model/RUN.md`, `todo/` | `plans/`, `audits/`, `*/research/`, `.claude/agent-memory/`, `docs/acceptance/`, `docs/handoff/`, `NOTES.md` and every subproject `NOTES.md`, source, tests and tools |

  `world-model/RUN.md` and `NOTES.md` were named on neither side when the rename was done, and the
  rule places them on opposite sides, which is the useful part of writing it down. `RUN.md` tells
  you which flags the pipeline has today, so a stale ID there is a stale instruction (it had one
  bare `M3`, now `WM-M3`). `NOTES.md` is a harvest whose bullets cite the milestone each insight was
  *earned in* — "Finding 1 of `M1` verification note" — so its 40 bare mentions are dated citations
  and rewriting them would falsify the record, which is exactly what `docs/PROCESS.md`
  ("Superseding a decision") forbids.

  **Sweep with `(^|[^-A-Za-z0-9_])M[0-9]+([^A-Za-z0-9_]|$)`, not `\bM[0-9]+\b`.** Excluding `-` is
  load-bearing: a word-boundary match hits the `M7` inside `WM-M7` and buries the dozen real
  findings in some two hundred false ones. Expect two standing false positives the pattern cannot
  avoid — a mission filename (`MI24-outpost-M03.miz`) and a weapon name (`Soldier M4 GRG`).

  > **The bullet immediately BELOW this note is superseded by the entry above it, and is kept only
  > for its tooling-tax argument. `M<n>` is not a live ID shape; nothing in the repo uses it.**
  > That bullet recorded `M<n>` as an accepted irregularity on a cost
  > estimate that assumed the only available rename was `WM-5`. The user's `WM-M<n>` form was not
  > considered, and it is an order of magnitude cheaper for the reason given above. Kept because
  > the tooling-tax paragraph under it is the live argument against any *future* irregular ID.

- **World-model's `M<n>` stays irregular** — milestones are bare `M<n>` (`M0`…`M11`), backlog is
  `WM-B<n>`, work items are `WM-W<n>` (`WM-W1`…`WM-W12`, minted 2026-10-09 by that file's
  conversion; all three shapes are now live on disk). Fixing the mismatch would mean renaming
  `M5` → `WM-5` across several hundred prose mentions that `docs/PROCESS.md` ("Superseding a
  decision") forbids rewriting. Recorded, not fixed.

  **It is not free, and the cost landed in the tooling rather than the documents.** An ID shape is
  what every consumer uses to tell an entry file from an index file, and all of them spelled it
  `^[A-Z]+-[A-Za-z0-9.]+$` — which `M5` does not match. Converting world-model therefore needed
  `roadmap-entry-consistency-gate.sh`, `roadmap-tag-vocabulary-gate.sh` and `roadmap-toc.sh` all
  widened to `^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$`. Before that widening the
  dangling-link check reported all twelve `[[M<n>]]` links as unresolvable — loud, and caught at
  once — while the filename-matches-H1 and appears-in-exactly-one-index checks **skipped all
  twelve files silently**, so a wrong H1 or an entry missing from its index would have passed.
  Verified by running the pre-fix regex against both defects deliberately introduced: zero
  findings each. **So an irregular ID shape is a standing tax on every future consumer that has
  to recognise one** — if another subproject ever wants one, that is the argument against.
  Enumerate the alternatives explicitly rather than loosening to `^[A-Z]`, which would also match
  a stray `README.md` or `RUN.md` and start checking it as an entry.

  **The loud half was the trap, and that is the part worth carrying forward.** Twelve false
  dangling-link findings invite exactly one response — delete the twelve links — which would have
  looked like a clean fix while leaving the two silent checks skipping those same twelve files
  indefinitely. Widening the regex fixed that one instance. **The class is now closed instead:**
  `roadmap-entry-consistency-gate.sh` fails on any file in a split directory whose name is neither
  ID-shaped nor a known index shape (`*-roadmap.md`, `*-backlog.md`, `*-tasks.md`), so an
  unanticipated filename can no longer vanish from the gate that is supposed to be reading it.
  Proven by reintroducing a bare `M99.md`: reported, exit 1.
- **A short basename is fine, but check it.** `M5.md` was as short as an entry filename got, and
  Obsidian resolves wikilinks by basename across the *whole* vault, so a two-character name is
  where a collision is most likely. Checked mechanically before writing them (every `*.md`
  basename in the repo, against `M0`…`M11`): no collision, and the repo's existing duplicate
  basenames are all structural (`plan.md`, `review.md`, `CLAUDE.md`, …), none of them entry-shaped.
  Those files are `WM-M<n>.md` now, so the two-character case no longer exists on disk — the check
  is kept because the next convention change could reintroduce one.
  Run that check rather than assuming, and run it over the repo rather than over `*/ROADMAP/`.
- **Numbers are assigned in document order, top to bottom of the file being converted** — so a
  rebase or a redone conversion produces the same numbers, rather than depending on whatever order
  a converter happened to work in.
- **The next unused number is read, never counted** (the same rule root `CLAUDE.md` states for
  backlog IDs, applied to files):

  ```sh
  ls <sub>/ROADMAP/ | grep -oE '^BL-W[0-9]+' | sort -V | tail -1   # the FULL prefix, not [A-Z]+
  ```

  **Spell the prefix out.** `'^[A-Z]+-W[0-9]+'` was the published form and it is wrong for the same
  structural reason the delimiter forms below are: one `ROADMAP/` directory holds more than one
  prefix. `body-layer/ROADMAP/` holds `BL-`, `BL-B`, `BL-W` **and** `BR-` — brain-layer has no
  directory of its own — so a prefix-agnostic pattern returns the maximum across all of them and
  mints from the wrong sequence. Found 2026-10-09 (`audits/system-integrity/`, finding 5); it had
  not fired yet only because no `BR-W` or `BR-B` item exists.

  **`sort -V`, not `sort -t W -k2 -n`, and this is not a style preference — the delimiter form was
  written here first and it is wrong.** `-t W` splits on the literal `W`, which the `WM-` prefix
  contains, so every `WM-W*.md` has the same empty second field and the tie falls back to a
  lexicographic comparison: the recipe as published returned `WM-W9` against a real `WM-W12`, and
  minting from it would have handed out `WM-W10`, colliding with an existing item. The `-B` form in
  root `CLAUDE.md` had the same defect through `BL-` (`BL-B9` against a real `BL-B46`). Both
  measured 2026-10-09, by running them rather than reading them. `sort -V` compares the digit runs
  numerically wherever they sit in the string, so it is correct for every prefix and every one of
  the three ID spaces.
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
- **Cross-subproject links are now ordinary, and that caveat above has no remaining instances.**
  Every subproject's roadmap and backlog is split, so an ID mentioned anywhere resolves: a
  world-model entry links `[[BL-11]]`, `[[X-B29]]` and `[[X-B30]]`, an aircraft-layer entry links
  `[[WM-W2]]`. The consistency gate resolves against the union of every converted directory, so
  these are checked, not merely tolerated. **Make them in the file you are writing; do not sweep
  already-converted directories to add them.** A retroactive link sweep is a separate change, and
  bundling one into a conversion makes the conversion's diff unreviewable — which defeats the only
  mechanism anyone has for checking that a conversion carried its text verbatim.
- **Convert a backticked ID mention, not a bare one.** `` `WM-M7` `` becomes `[[WM-M7]]`;
  "WM-M7's baseline" in running prose stays as it is. The restraint is not stylistic: world-model's
  roadmap carried several hundred bare `M5`/`M7` mentions, inside file paths, SQL and code
  examples, and a bare-word rewrite would corrupt them. (That was written when the IDs were bare
  `M<n>`, where the hazard was acute. The 2026-10-09 rename to `WM-M<n>` reduced it — `WM-M7` is
  not a substring of anything — but the rule stands for every other prefix, and the rename itself
  still had to exclude `M8_PROBE_STORE.md` by lookahead to avoid exactly this corruption.) One scripted pass over backtick spans
  whose *entire* content is a resolvable ID, skipping fenced blocks and self-references, is both
  safe and enough — it found 56 real links across the three files converted on 2026-10-09.
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

### Two blocks in one entry: the entry's own record leads, and that is not cosmetic

An entry file can end up holding more than one checkbox block — an item plus its own superseded
text (`BL-B34`, `WM-B7`, `X-B27`), or an item plus the live-acceptance-debt record that was about
it (`WM-B1`, `WM-B6`, `WM-W1`). **The first checkbox line in the file is the entry's state**, for
every reader and every tool: `roadmap-toc.sh` reports that block's tag, and `grep '#status/done'`
finds the entry on it. So block order decides what the entry appears to be.

- **An item and its own superseded text go in source order**, which puts the current form first
  because that is how these are written (`WM-B7`'s rejection above `WM-B7 (original text)`).
- **A folded debt record goes *after* the entry it was about, regardless of source order.** The
  debt list sits at the head of a roadmap, far above the entries it refers to, so source order
  would put a `[x]` clearance note on top of its entry — and on `WM-B6` it did, making the TOC and
  a status grep report an in-progress item as done. Found by reading the TOC's real output after
  the conversion, not by inspection. The entry is the record; the debt line is a note about it.

## Tags

See `docs/TAGS.md` for the vocabulary. Two rules repeated here because they decide the entry file
shape above: tag only what the ID and path do not already say, and tag status on the same line as
its checkbox marker, never in frontmatter and never elsewhere in the entry.

**"On the same line as its checkbox marker" means after the leading bold span, which is sometimes
a later line** — a bold lead often wraps, and several entries put the tag on the entry's second or
third physical line as a result (`BL-W12` and `WM-B6` both do). That is the established placement.
Where the bold span is followed immediately by sentence punctuation, put the tag after the
punctuation, not before it, or the entry reads `… was parked** #status/in-progress, because …`.

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

Three mechanical checks. **Two of them run automatically before a commit; the third is standalone
only, and the difference matters because this section asserted all three were enforced while none
of them was wired to anything.** `grep` for the three script names across `.claude/settings.json`,
`install-git-hooks.sh` and `commit-quality-gate.sh` returned nothing until 2026-10-09: a dangling
`[[ID]]`, an orphaned entry or an unlisted tag committed clean across 245 entry files for as long
as this paragraph had been claiming otherwise (review round 4, RF4-2). A stated mechanical
guarantee that does not exist is worse than no guarantee, because it is relied on instead of
checked.

As wired now, in `.claude/scripts/commit-quality-gate.sh`, conditioned on the staged diff matching
`(^|/)ROADMAP/|^todo/(backlog|todo)/|^docs/TAGS\.md$` — so a commit touching none of those paths is
unaffected, and each gate scans the whole tree rather than only the staged paths, because a
dangling link and an orphaned entry are relational and a staged-paths-only check would miss the
half of each pair that did not change:

- **Consistency** (`.claude/scripts/roadmap-entry-consistency-gate.sh`): every `[[ID]]` in a
  converted tree resolves to an existing `<ID>.md`, across the union of every converted directory
  (not just the one the link was written from — a research note or a plan citing a roadmap ID
  from outside any `*/ROADMAP/` directory is a normal, correct link); every entry file's name
  matches `<ID>.md` with an H1 whose first token is that same ID; every entry appears in exactly
  one index. **Wired.**
- **Tag vocabulary** (`.claude/scripts/roadmap-tag-vocabulary-gate.sh`): every inline `#tag` in a
  converted entry file appears in `docs/TAGS.md`. **Wired.**
- **Document provenance** (`.claude/scripts/doc-provenance-gate.sh`): see "Document provenance"
  above. **Standalone only, deliberately, and this is a temporary state with a stated exit.** Its
  own discovery bug was fixed on 2026-10-09 (it had hardcoded `audio-adapter/ROADMAP`, seeing 22
  entries of 245 and so rejecting a correct `[[BL-11]]` citation). Fixing it revealed that **127
  documents' provenance blocks are stale** — the generator can now see the cross-subproject
  entries it previously could not, so it wants citations the existing blocks do not carry.
  Regenerating those is the paused document-graph work. Wiring the gate meanwhile would refuse
  every commit touching any `ROADMAP/` path repo-wide, which is the cry-wolf failure that gets a
  gate bypassed. **Wire it once `.claude/scripts/doc-provenance-refresh.sh` has been run and its
  output reviewed.**

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
