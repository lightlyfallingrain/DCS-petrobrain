# Obsidian links and tags, repo-wide — revised verdict, cost at full scope, migration plan

**Plan only.** Nothing was converted, no consumer was edited, no file was renamed while writing
this. **Revised 2026-10-06** against four user decisions (below) that override the earlier
partial-adoption verdict.

Spike under judgement: branch `obsidian-test`, tip `f99617f`, write-up `todo/links-and-tags.md`,
vocabulary `docs/TAGS.md`, converted subject `audio-adapter/`. The spike is a **throwaway test**,
not a template — where its structure is kept below, that is a decision with a reason, and where it
is changed, the change says what the spike's version cost.

---

## Revised verdict — adopt repo-wide, in staged order, consumers first

**Every roadmap and backlog converts. Every entry gets a unique ID. `.obsidian` is gitignored
everywhere. Nothing is converted until the consumers are fixed.**

One earlier recommendation is superseded and does not recur below: filenames named by branch
instead of by a minted ID (rejected by decision 1 — IDs enable dependency tracking, and stale IDs
are grooming work the user has accepted).

### Scope — what converts and what does not

| file | entries | ~tokens | → | mint |
|---|---|---|---|---|
| `audio-adapter/ROADMAP.md` | 22 | 10.5k | `audio-adapter/ROADMAP/` | 0 — spike already minted `AA-1`…`AA-5` + stages |
| `aircraft-layer/ROADMAP.md` | 12 | 2.7k | `aircraft-layer/ROADMAP/` | 8 |
| `mission-interpreter/ROADMAP.md` | 9 | 4.0k | `mission-interpreter/ROADMAP/` | 0 — `MI-0`…`MI-6` complete |
| `world-model/ROADMAP.md` | 42 → **35** | 29.2k | `world-model/ROADMAP/` | 20 |
| `body-layer/ROADMAP.md` | 67 → **49** | 46.5k | `body-layer/ROADMAP/` | 27 |
| `body-layer/BACKLOG.md` | 43 | 24.7k | `body-layer/ROADMAP/` (same dir) | 1 |
| `todo/backlog.md` | 34 | 20.8k | `todo/backlog/` | 1 |
| **totals** | **204 entry files** | **138.4k** | **+7 indexes** | **57 new IDs** |

**Must not be split, each for its own reason:**

- **root `ROADMAP.md`** (72 lines, 6.1k tokens, **zero checkbox entries**). 20+ consumers read its
  status table *by name* for the subproject list — `check`, `test`, `compile`,
  `test-instructions`, `update-template`, `status-page`, every agent role file. It has nothing to
  split and splitting it breaks the most while buying the least. It is a cross-subproject index,
  which is the thing the per-subproject indexes point *up* to.
- **`todo/todo.md`** (24 entries, 0 IDs, 9.1k tokens). Not a roadmap and not a backlog: root
  `CLAUDE.md` defines it as "User priority tasks and session-scoped notes", and its entries are
  flight feedback in the user's own words that is *meant to migrate out* into a subproject's
  roadmap. Minting 24 permanent IDs for notes designed to leave would also collide with root
  `CLAUDE.md`'s own rule that an item moving between files **takes a new ID in its destination** —
  the ID would be born stale. Decision 2 scopes this to roadmaps and backlogs; `todo/todo.md` is
  neither.
- **Read-whole configuration documents** — `CLAUDE.md` (root and all six subprojects), `AGENTS.md`,
  `docs/PROCESS.md`, `docs/AGENT_ROLES.md`, `plans/*/plan.md`. These are loaded in full by design;
  splitting them converts an always-loaded file into a fan-out of reads nobody performs. Repo-wide
  means every roadmap and backlog, not every `.md`.

**`todo/backlog.md` converts, and it is the cheapest conversion in the table** — a reversal of the
earlier "leave it" call, on a measurement rather than a preference. It is entry-shaped, 33 of its
34 entries already carry `X-B<n>` IDs, it is read on **every** Session Start (root `CLAUDE.md`
step 2), and it needs **zero consumer changes**: `graph-corpus-files.sh:48` is already
`find todo -name '*.md'` (recursive, so `todo/backlog/*.md` is picked up for free),
`graphify-dirty-flag.sh` already matches `^todo/`, and the two `ROADMAP\.md` gate regexes do not
look at backlogs at all. 20.8k tokens off the common read for one directory and one pointer.

---

## Decisions taken

Recorded with the user's own words, because the wording carries the reasoning.

**D-1 — Mint unique IDs for every item.** *"item IDs - I'd rather have unique IDs for all items.
It's allright if they go stale later, that's backlog grooming work then. IDs allow tracking items
and dependencies, I'd rather use them."* → The branch-name filename alternative is dead. 57 new
IDs minted (not ~72 — see "The ID scheme" below for why the number dropped). Dependency tracking
is the stated purpose, which is what makes the `[[<ID>]]` links load-bearing rather than
decorative.

**D-2 — Repo-wide, every subproject.** *"graph benefit and limited sub-systems - true for you and
the agents, but a human reader benefits from all sub-systems following this convention and being
browsable via Obsidian."* → The partial verdict is overridden. A convention followed by three of
six subprojects is not browsable. The agent-token figures below stay as the honest *secondary*
benefit; they are not the argument.

**D-3 — Not bound by the spike's structure.** *"spike was a test - we do not have to follow it
strictly, we can use a better structure if there's one"* → Four structural changes below
(ID-only filenames, bare-ID links, tag spelling, index-per-file), each with the spike's cost named.
Four spike choices kept, also with reasons. The biggest change — filenames and links — was settled
by **two tests on the user's own install**, 2026-10-06, rather than by argument: frontmatter aliases
do not resolve here, but ID-only filenames plus the Front Matter Title plugin give the clean
`[[AA-4.7]]` link *and* a readable sidebar. Both tests are recorded below, including the one that
failed.

**D-4 — `.obsidian` gitignored everywhere.** *".obsidian needs to be gitignored, in all folders"*
→ Unanchored pattern, and the spike's five tracked files removed in the same change.

---

## The ID scheme as it has to be extended — the plan's one consequential decision

### What exists (verified, not recalled)

Root `CLAUDE.md` "Backlog Management" defines **`<prefix>-B<n>`** for backlog items and bare
**`<prefix>-<n>`** for milestones, both under **never-reuse, never-renumber**. Measured on disk:

| space | occupied by |
|---|---|
| bare `<prefix>-<n>` | `BL-0`…`BL-11`, `MI-0`…`MI-6` (+ `MI-5b`), `BR-1`/`BR-2`, `PB-0`…`PB-9` (concept doc), `AA-1`…`AA-5` (minted by the spike), and **`M0`…`M11`** — world-model's milestones use the bare prefix `M`, *not* `WM-` |
| `<prefix>-<n>.<m>` | stages; spike-formalised, prose already said "BL-11 Stage 0" |
| `<prefix>-B<n>` | `AC-B1`…`B4`, `AA-B1`…`B3`, `WM-B1`…`B6`, `BL-B<n>`, `X-B1`…`X-B33` |
| `<prefix>-W<n>` | **nothing.** `grep -rnoE '\b[A-Z]+-W[0-9]+' --include='*.md' .` → zero hits |

### The ID-less entries are two different things, and that halves the job

124 entries carry no ID. Split by section, they are not one kind:

| | body-layer | world-model | aircraft-layer | audio-adapter | `todo/backlog.md` |
|---|---|---|---|---|---|
| in a **"Live acceptance debt"** list | 17 | 7 | — | — | — |
| in **Status / Backlog** proper | 27 (+1 in BACKLOG) | 20 | 8 | 19 (spike minted) | 1 |

**The debt-list entries are not items. They are a view over items, and today the two disagree.**
`fix/contact-report-flood` has a debt entry marked `[ ]` *and* a Status entry marked `[x]`
("Contact-report flood (merge-echo callout suppression)"). The same doubling exists for the
`silence` command, `fix/redundant-group-disclosure`, the position-belief-runaway fix,
`feature/dcs-driven-los` and the group-cohesion redesign. Minting an ID per checkbox would mint
**two permanent IDs for one piece of work**, under a never-reuse rule, and freeze the
disagreement into two files.

**So: the debt list does not become entry files.** Each merged-but-unflown work item keeps its one
entry file, carrying `#needs-flight` and its acceptance-card link; the debt list in the index
becomes four lines of prose plus `grep -rl '#needs-flight' */ROADMAP/ todo/backlog/`. This is
exactly the hand-kept-prose-list-to-tag replacement `docs/TAGS.md` was written for, it is the one
place benefit (d) pays for itself, and it removes 24 of the 124 mints and ~6 duplicate records.

### Recommendation — a third marker, `<prefix>-W<n>`

**One recommendation, not options: work items that are not milestones and not backlog take
`<prefix>-W<n>`, numbered from 1 per subproject, in a number space independent of both others.**

Why not the **milestone** space: `BL-12` is a live, contested resource — `BL-11` just shipped and
`plans/body-layer/plan.md` §6 is the external document that *defines* what each `BL-x` is. Minting
`BL-12`…`BL-38` for 27 historical bug fixes would retroactively claim milestone status for them,
make §6 disagree with the roadmap about what `BL-12` means, and consume the forward sequence. Same
for `M12` in world-model. This is the decisive argument and it is specific to these two
subprojects.

Why not the **backlog** space: "backlog" means not-yet-done, and ~90% of these entries are `[x]`.
`BL-B47 — Binocular optic, done 2026-09-23` is semantically false and makes
`grep -c 'BL-B'` useless as a measure of open work.

Why `W`: one letter, parallel in shape to `B`, zero collisions anywhere in the repo (verified
above), and `BL-12` / `BL-W12` coexist unambiguously because the spaces are independent.

**Against never-reuse:** it strengthens the rule rather than straining it. Never-reuse is violated
by *renumbering*, and a third space means nothing is renumbered: `M0`…`M11` keep their numbers,
`WM-B1`…`B6` keep theirs, and the 20 world-model work items become `WM-W1`…`WM-W20` without a
single existing mention changing. The retired/done entries keep their W-numbers forever, which is
the rule working as intended.

**Where a subproject has no declared milestone series, its Status entries become that series**, and
`-W` is simply unused there. `aircraft-layer` and `audio-adapter` have no `plans/*/plan.md` §6
equivalent and no forward series consuming the bare space, so their entries mint into it directly —
`AC-1`…`AC-8`, and the spike's `AA-1`…`AA-5` stand. That is one rule, stated once; it is not a
per-subproject exception list.

**World-model's prefix inconsistency is recorded, not fixed.** Its milestones are `M<n>` and its
backlog is `WM-B<n>`. Work items take `WM-W<n>` (aligning with the backlog prefix, since `M-W1`
reads as nothing). Renaming `M<n>` → `WM-<n>` would break several hundred bare `M5`/`M7` prose
mentions across `plans/` and `research/` that `docs/PROCESS.md` forbids rewriting. The convention
doc states the irregularity in one line. Likewise `MI-5b`'s letter suffix stays; new sub-items use
`.n`.

### Who assigns, and in what order

The spaces are **per subproject**, so two sessions converting *different* subprojects cannot
collide at all — `BL-W*` and `WM-W*` are disjoint. Four rules close the remaining windows:

1. **One subproject per branch; one branch per subproject at a time.** A subproject's conversion is
   a single atomic commit range. No second branch touches the same `ROADMAP/`.
2. **Numbers are assigned in document order, top to bottom of the file being converted** —
   deterministic, so a rebase or a redone conversion produces the same numbers. "Whatever order the
   converter worked in" is how a rebase silently renumbers.
3. **The next unused number is read, never counted** (root `CLAUDE.md`'s own rule, applied to
   files): `ls <sub>/ROADMAP/ | grep -oE '^[A-Z]+-W[0-9]+' | sort -t W -k2 -n | tail -1`.
4. **No W-number is minted outside a conversion.** During the migration window, an un-IDed entry in
   an unconverted file stays un-IDed — otherwise an interleaved `main` commit takes a number the
   conversion branch assumed free.

### Grooming — what "goes stale later" means mechanically

The user accepted staleness as grooming work. Concretely, done entries **keep their IDs and their
files, in place, forever.** Recommended, over an archive directory or deletion:

- **Moving or deleting an entry file breaks every `[[BL-W12]]` link and the 441 historical prose
  mentions** (measured today; it was 429 this morning and grows). An archive directory is a move,
  so it is the same breakage unless the corpus script, the link gate and the index all follow it —
  more machinery, no gain.
- **The read-cost benefit is already delivered by the split, not by archiving.** A 46.5k file forced
  you to read its history; 204 separate files do not. A done entry's file is simply never opened,
  so an agent cannot tell an archive from a `#status/done` tag.
- **So grooming is narrow and real:** flip the `#status/*` tag, move the row from the index's Open
  table to its Done table, and fold any debt-list duplicate into the one surviving entry. No file
  surgery, no ID retirement.
- **The honest cost:** `<sub>/ROADMAP/` grows monotonically — ~204 files today, perhaps +50/year.
  `ls` output gets long and the corpus grows (see below). Accepted, stated, not mitigated.

---

## Cost at full scope

### Files and the corpus ceiling — the one hard new cost

`graph-corpus-files.sh` currently emits **172 files**; `graph-corpus-guard.sh`'s ceiling is
**200**. Repo-wide conversion adds **204 entry files + 7 indexes = 211**, taking the corpus to
**~383**. The guard **refuses the rebuild, loudly** — which is the design working, and it must then
be raised deliberately (to ~450, leaving headroom), not pre-raised in anticipation. Corpus *word*
count is roughly unchanged: content moves, it does not duplicate.

### Work, by kind

| work | volume | kind |
|---|---|---|
| consumer regex/list fixes (Stage 0) | 7 one-line edits | **mechanical, do first** |
| prose updates in agents/skills/`CLAUDE.md` | ~22 lines across ~16 files | mechanical, tedious |
| splitting entries into files | **204** files; median entry 20 lines (body-layer) / 12 (world-model), largest real entry 79 | mechanical |
| converting ID cross-references to `[[links]]` | 139 (body-layer) + 87 (its BACKLOG) + 69 (world-model) + the smaller files | mechanical, each must resolve (R5) |
| **minting 57 IDs** | 57 | **judgement, permanent** — but now rule-bound (document order, per-subproject space) rather than per-entry |
| folding ~6 duplicate debt records into their Status entry | ~6 | **judgement** — two records disagree; one is right |
| placing non-entry trailing sections | body-layer ~365-line debt preamble + "Keeping this current"; world-model ~160 | judgement, one-off per file |
| raise the corpus ceiling, `/graph-refresh` | 1 + 1 | mechanical; 60k in / 18k out per `graphify-out/cost.json` |
| re-verify every gate against the converted tree | 7 | mechanical |

### Consumers — the complete sweep, unchanged in substance

| consumer | what breaks | failure is | fix |
|---|---|---|---|
| `.claude/scripts/graphify-dirty-flag.sh:41` | regex `[^/]+/(CLAUDE\|ROADMAP)\.md` misses `body-layer/ROADMAP/BL-12-*.md`. **Editing a roadmap entry stops recording that a semantic rebuild is owed** — the graph goes stale while reading as current | **SILENT · worst** | one line: add `\|[^/]+/ROADMAP/[^/]+\.md`, **and `BACKLOG` — see the pre-existing bug below** |
| `.claude/scripts/graph-corpus-files.sh:74` | corpus is a file list over fixed names `ROADMAP CLAUDE BACKLOG`; entry files are never listed, so roadmap content leaves the graph | **SILENT** | one line: `find "$sub/ROADMAP" -name '*.md' 2>/dev/null` beside the existing `docs` find. The enclosing loop is `for d in */pyproject.toml` — mechanical, no stale subproject list, so it is correct at full scope |
| `.claude/scripts/status-page-refresh.sh:63-64` + `.claude/skills/status-page/SKILL.md:47,49,64` | derives subsystem status and the forward-only map from each subproject `ROADMAP.md`; a 4-line pointer yields an empty-but-plausible page and exits 0 | **SILENT · dominant** | prose + a non-zero-item assertion |
| `.claude/scripts/push-roadmap-gate.sh:59` | `grep -qE '(^\|/)ROADMAP\.md$'` on pushed paths; an entry-only update stops matching and the gate **blocks every legitimate feature merge push** | LOUD (safe direction) | one-line regex |
| `.claude/scripts/commit-quality-gate.sh:188` | same regex; spurious "roadmap not updated alongside dod-check" warning | LOUD (safe direction) | one-line regex |
| `.claude/scripts/session-start.sh:66` | prose tells the session to read "the `ROADMAP.md` of whichever subproject"; it reads a stub and concludes nothing is next | SEMI-SILENT | prose |
| `.claude/skills/merge/SKILL.md:42,74` · `.claude/agents/dod.md:105,193` · `integrity-audit/SKILL.md:28,70` · `retro/SKILL.md:139,161,187` | read subproject roadmaps as the source of truth or as audit inputs | SEMI-SILENT | prose |
| `.claude/agents/{architect,implementer,debugger,investigator,reviewer,performance-reviewer}.md:37-40` | identical "Where things live" block naming `<subproject>/ROADMAP.md` | SEMI-SILENT | one line × 6, identical edit |
| root `CLAUDE.md:45-46, 90, 138-139, 365-368` | Session Start, Milestone Completion, the `<prefix>-B<n>` ID table (**now also the home of the `-W<n>` rule**) | SEMI-SILENT | prose |
| four subproject `CLAUDE.md` | one roadmap mention each | trivial | prose |

**Found while re-measuring, and it is a live bug independent of this plan:**
`graphify-dirty-flag.sh`'s regex covers `[^/]+/(CLAUDE|ROADMAP)\.md` but **not `BACKLOG`** — so
editing `body-layer/BACKLOG.md` does **not** flag the graph dirty today, although that file *is* in
the corpus. Third instance of the `graph-corpus-files.sh` failure class, in its mirror script. Fix
it in Stage 0 whatever happens to the rest of this plan.

**Not consumers:** `check`, `test`, `compile`, `test-instructions`, `update-template` and
`status-page:14` read root `ROADMAP.md`'s status table for the subproject list only. Root stays
whole, so these need no change — six files out of the blast radius the raw grep suggests.

**Do not touch the 441 historical mentions.** Most are in `plans/*/dod-check.md`, `audits/`,
`reviews/` and dated research notes — records of what was true then, which `docs/PROCESS.md`
"Superseding a decision" forbids rewriting. **This is why the pointer file is never deleted:** a
4-line `ROADMAP.md` pointing at the index keeps all 441 honest.

### New costs that appear only at full scope

- **Vault scope is now a hard requirement, and its configuration became untracked.** `[[AA-4.5]]`
  resolving from a body-layer entry needs **one vault rooted at the repo root** (Obsidian resolves
  basenames within a single vault). **Confirmed in fact, not assumed:**
  `/Users/sg/Code/DCS-petrobrain/.obsidian/` already exists and was written today — the user has
  already opened the repo root as a vault. But decision 4 makes that config untracked, so **nothing
  in the repo can record that it was done**, and a fresh clone (including the public-open-source
  intent) gets a vault that must be configured by hand. This is a genuine tension between decisions
  2 and 4, and the only mitigation is one prose paragraph in `docs/DOC_CONVENTIONS.md`. The spike's
  nested `audio-adapter/` vault becomes actively harmful and its config directory should be
  **deleted, not merely untracked** — it would resolve `[[AA-4.5]]` but not `[[BL-12]]`, producing a
  half-working vault that looks fine.
- **Repo-wide basename uniqueness stops being theoretical.** 204 entry files + 7 indexes join every
  other `.md` in one namespace. `README.md` already exists several times (`docs/status/README.md`,
  `plans/archive/`), so `[[README]]` is meaningless. Rule: **only IDs are linked; nothing is ever
  linked by title.** Index filenames stay `<scope>-roadmap.md` (the spike's choice) precisely
  because seven `index.md` files would collide.
- **Tag-vocabulary drift across six subprojects.** `docs/TAGS.md` is one closed vocabulary for all
  of them, and the pressure to add a subproject-local `#topic/*` rises with scope. Two rules:
  the gate checks every converted file against `docs/TAGS.md`, and **a `#topic/*` tag must cross at
  least two subprojects** — a tag used in one directory is a search `ls` already answers.
- **Seven indexes instead of one.** Seven more files that can disagree with what they index. The
  no-status rule removes the part that drifts, and the gate removes orphans and dangling links; the
  residual is each index's prose preamble, which can go stale exactly as today.

---

## Benefit

### (a) Human navigation across all six subprojects — primary, and the reason for decision 2

User: *"a human reader benefits from all sub-systems following this convention and being browsable
via Obsidian."* The beneficiary is the product owner, and his navigation cost is a project cost.
Not discounted, not quantified, and the thing partial adoption could not deliver — a graph view
and a tag pane over three of six subprojects shows holes, not structure.

### (b) Agent read cost — measured, and the honest secondary benefit

Session Start with body-layer active, `wc -c`/4:

| | now | after | cut |
|---|---|---|---|
| root `ROADMAP.md` | 6.1k | 6.1k | — |
| `body-layer/ROADMAP.md` | 46.5k | index ~2.5k | |
| `body-layer/BACKLOG.md` | 24.7k | index ~2.0k | |
| `todo/backlog.md` | 20.8k | index ~1.5k | |
| `todo/todo.md` | 9.1k | 9.1k | — |
| + 2-4 relevant entries | — | ~2k | |
| **total** | **~107k** | **~23k** | **−78%** |

Root `CLAUDE.md` makes clearing context between tasks a deliberate habit, so this read is paid
again on every clear. `/graph-refresh`'s own `gq.sh` source lists also sharpen: `source_file` points
at a ~700-token entry instead of a 46.5k file.

### (c) Merge-conflict reduction — real, secondary, still over-claimed if leaned on

`body-layer/ROADMAP.md` took 130 commits in 30 days; per-entry files make same-file collisions
structurally rare. It does **not** help the two places the cross-subproject narrative actually
collides — the index files and root `ROADMAP.md`'s status table.

### (d) Trustworthy `grep` negatives over tags — the one genuinely new capability

Root `CLAUDE.md` is explicit that the graph's negatives are unreliable and a completeness sweep must
be `grep`. A closed vocabulary makes `grep -rl 'needs-flight' */ROADMAP/ todo/backlog/` an
authoritative answer to "what do I owe a sortie" across every subproject at once — replacing two
hand-kept prose debt lists that only discipline keeps current, and that this plan has just shown
disagree with their own Status entries in ~6 places. **Conditional on the vocabulary gate existing**
(Stage 1), because nothing currently enforces `docs/TAGS.md` and one `#topic/speech` beside
`#topic/stt` destroys the whole benefit.

### (e) Graph quality — modest, narrower than the spike claims

Measured against the live graph (9,487 nodes, built 2026-10-05): the roadmap and backlog files
**already** produce **185 nodes / 264 edges**, including per-entry nodes (`AC-B3 — Split The Export
Throttle`). "One node per entry instead of one giant node" is already true. Real gains: closes a
13-entry extraction gap in body-layer (54 nodes from 67 entries) and sharpens `source_file`
provenance. Re-measure after Stage 2 against the 185/264 baseline.

---

## Structure — re-examined, not inherited

### Changed from the spike

1. **Filename is the ID alone — `AA-4.7.md`** — not `AA-4.7-Press_to_readback_latency.md`. The
   entry's title lives in its H1 (`# AA-4.7 — Press-to-readback latency`) and nowhere else. This
   follows from the link form below and from a plugin test (see "Tested and settled"); it is the
   single change the rest of the structure hangs on.
2. **Link form: the bare ID, `[[AA-4.7]]`** — not the spike's
   `[[AA-4.7-Press_to_readback_latency\|AA-4.7]]`. With an ID-only filename this is a *plain
   filename link*, which needs no plugin, no alias and no frontmatter. What it buys over the spike's
   form, each of which was a named cost:
   - **One spelling.** No `\|`, so the in-table and out-of-table forms are identical and the
     two-spellings trap — the same class as the `#`-in-frontmatter trap the spike itself hit —
     does not exist.
   - **9 characters, not ~56**, in the text an agent reads. The spike's form spent back part of the
     split's own token saving.
   - **Identical to the 441 historical prose mentions**, so one `grep -rn 'AA-4\.7'` finds links and
     prose together rather than needing two patterns.
   - **A retitle edits one H1 line** and touches no referring file, because no referrer carries the
     title. The spike's form made every referrer carry it.
3. **Tags: inline `#tag` only, nowhere else.** The spike puts topics in frontmatter (no `#`) and
   `#status/...` inline — the two-spellings trap its own `docs/TAGS.md` warns about, in the file
   that warns about it. Keep the *better* half: `docs/TAGS.md` Rule 2's argument is sound (status
   lives next to its checkbox marker so the two cannot diverge unnoticed), so put **every** tag
   there: `- [x] **AA-4.5 — Stage 5 …** #status/done #topic/ptt #topic/cockpit-io`. One spelling,
   one location, every `grep` recipe identical, Obsidian's tag pane works on inline tags.
4. **One index per source file, not per directory.** `body-layer/ROADMAP/` holds both roadmap and
   backlog entries but gets two indexes (`body-layer-roadmap.md`, `body-layer-backlog.md`) so each
   pointer file has exactly one destination and the 441 historical mentions of
   `body-layer/BACKLOG.md` resolve to the right list.

### Kept from the spike, with reasons

- **`<subproject>/ROADMAP/` per subproject** — not a flat repo-wide `docs/roadmap/`. A flat
  directory would break root `CLAUDE.md`'s "each subproject's `ROADMAP.md` is that subproject's own
  source of truth", break per-subproject `grep`, make `graph-corpus-files.sh`'s
  `for d in */pyproject.toml` loop the wrong shape, and break `ls */ROADMAP/` — which is the
  mechanical answer to "which subprojects are converted" that keeps a stale list out of the config
  (R8). Per-subproject is *more* right at repo-wide scope, not less.
- **Backlog entries share the `ROADMAP/` directory** rather than getting a `BACKLOG/`. The ID
  distinguishes kind (`BL-B4` vs `BL-12`), the indexes are already separate, and a second directory
  doubles the corpus-script and link-gate surface for nothing. The directory name is mildly a lie
  for backlog entries; renaming it to `entries/` would break the `*/ROADMAP/*` regex fixes and every
  historical mention, which is a much worse trade. (`todo/backlog/` is the exception, because there
  is no `todo/ROADMAP.md`.)
- **The 4-line pointer `ROADMAP.md`, with a machine-checkable sentinel**
  (`<!-- split-roadmap: see ROADMAP/ -->`). 441 historical mentions depend on the path existing;
  the sentinel is what lets a consumer tell a pointer from a real roadmap instead of silently
  reading four lines and reporting success.
- **Dotted sub-IDs (`AA-4.7`)**, not `AA-4-7`. Hundreds of prose mentions across `plans/`,
  `audits/` and research notes use the dotted form; changing the separator makes every one of them
  un-greppable — and the ID is now the filename *and* the link text, so the separator is load-bearing
  in a way it was not under the spike's form.
- **Hand-kept indexes plus a mechanical consistency gate**, not a generator — even at seven
  indexes. A generator is a build step in a repo that deliberately has almost none, and it would
  have to preserve each index's irreplaceable prose preamble. The ~15-line pre-commit gate catches
  the two failures a generator would not: a dangling `[[link]]`, and an entry file absent from its
  index. Its cost rises linearly with indexes, which is fine.

### Tested and rejected: the bare-ID link form

**Measured on the user's own Obsidian install, 2026-10-06. Frontmatter aliases do not resolve
`[[wikilinks]]` here, so the clean `[[AA-4.7]]` form is not available.** This was the plan's one
structural claim about third-party software and it is now settled by test rather than carried as a
documented-behaviour assumption. The planned Stage 1 verification step is therefore already
discharged.

What was run — four target notes at the vault root, one linking note, each link clicked:

| form | result |
|---|---|
| `aliases: [ZZ-1]` (inline list) → `[[ZZ-1]]` | **FAIL** — unresolved, Obsidian offers to create a new note |
| `aliases:` + `- ZZ-2` (block list) → `[[ZZ-2]]` | **FAIL** |
| `alias: ZZ-3` (deprecated singular key) → `[[ZZ-3]]` | **FAIL** |
| plain filename → `[[zz-target-inline]]` | PASS |
| escaped pipe → `[[zz-target-block\|ZZ-2 via pipe]]` | PASS, in prose and inside a table |

Every resolving link is filename-based; every alias-based link fails. A vault reload
("Reload app without saving") was performed and the three alias forms still failed, which rules out
metadata-cache lag from a branch switch — the explanation that best fit the symptom. Cause not
diagnosed further: an unavailable mechanism does not need a root cause to be unavailable, and the
fallback was already specified.

**What this ruled out, and what it then opened.** Filename-is-the-ID was initially rejected with it,
on the grounds that Obsidian labels the explorer and graph by filename, so a sidebar of `AA-4.7.md`
would be a column of bare IDs — a direct hit on the human-browsability benefit behind D-2. That
objection was correct about stock Obsidian and is answered by the plugin below.

### Tested and settled: ID-only filenames with Front Matter Title

**Measured on the user's own install, 2026-10-06. Obsidian 1.14.4, Front Matter Title 4.2.1
(`snezhig/obsidian-front-matter-title`, 75k downloads, updated within the month).** The plugin
*"shows a friendly title from your note's frontmatter everywhere in the app — without renaming the
file"*: explorer, search, quick switcher, bookmarks, backlinks, tabs, note header, inline title,
graph and canvas.

The decisive setting is **Common main template = `#heading`** with **Common fallback template =
`_basename`**. `#heading` is a documented reserved word meaning "first heading in the file", so the
displayed title comes from the entry's own H1 and **no frontmatter is needed at all**.

Four notes, each a different shape:

| note | file contents | displayed as |
|---|---|---|
| `AA-9.1` | frontmatter `title:` **and** an H1 | **"AA-9.1 — Press-to-readback latency"** — the H1 wins under `#heading` |
| `AA-9.2` | frontmatter `title:`, **no H1** | **"AA-9.2"** — `_basename` fallback, as designed |
| `AA-9.3` | an H1, **no frontmatter at all** | **"AA-9.3 — a heading but no frontma…"** — this is the one that matters |
| `AA-9.4` | H1 with an em dash and a comma | **"AA-9.4 — Stage 5, real PTT through…"** — punctuation fine |

**So the frontmatter `title:` field is dead, and with it the duplicate-title problem** that the
earlier Option C carried: there is one copy of the title, in the H1, and no gate is needed to keep
two in sync. An entry file is `AA-4.7.md` containing `# AA-4.7 — Press-to-readback latency`.

**Link text is not replaced.** The plugin's link feature was enabled and rendered links still read
`AA-4.7`. Accepted by the user (*"I can live with that"*), and the cost is small: the raw text says
`AA-4.7` anyway, and so do all 441 historical prose mentions. Navigation — the thing D-2 is about —
is fixed in every other surface.

**Two consequences the user has to act on once, by hand:**

- **Turn off Settings → Appearance → "Show inline title"**, or every entry renders its title twice
  (once as the plugin's inline title, once as the literal H1). Observed in the test.
- **The explorer truncates.** A leading ID in the H1 spends ~10 characters of sidebar width before
  the title starts ("AA-9.4 — Stage 5, real PTT through…"). The alternative — `# Press-to-readback
  latency`, ID only in the filename — reads cleaner but makes the ID invisible in every surface the
  plugin touches, and the ID is what carries the dependency tracking D-1 asked for. **Recommend
  keeping the ID in the H1 and accepting truncation**; it is the user's reading surface, so it is
  his to overrule.

**What now depends on a third-party plugin, and what does not.** This is the right split and is why
the dependency is acceptable: the **links** depend on nothing — `[[AA-4.7]]` is a plain filename
link that resolves in stock Obsidian, in `grep`, and in the knowledge graph. Only the **display**
depends on the plugin, and its absence degrades to bare IDs rather than breaking anything. A fresh
clone of a public repo gets working links and an ugly sidebar until the reader installs one plugin
and sets two fields — which is what `docs/DOC_CONVENTIONS.md` has to say in prose, since `.obsidian`
is gitignored (R7).

---

## Risks & failure modes

Ordered by how silent each is, because silence is the whole problem.

- **R1 — a consumer reads a stub and reports PASS (dominant).** The status page is derived from
  subproject roadmaps; pointed at a pointer it regenerates an empty-but-well-formed page and exits
  0. `integrity-audit`, `retro` and `dod-check` have the same shape. *Capping the damage is luck,
  not design:* `status-page-refresh.sh`'s header records (2026-09-27) that the launchd job is not
  installed, so it runs only by hand — but the plist is committed and ready. **Make it detectable:**
  the sentinel line, plus a non-zero-item assertion before publishing. An assertion that fires is
  the difference between a wrong page and a refusal.
- **R2 — content silently leaves the graph corpus.** `graph-corpus-files.sh` is a curated file list,
  and **this has already happened twice**, recorded in that script's own comments: the 2026-09-27
  `BACKLOG.md` split "silently dropped 8,200 words of open items out of the corpus", and
  `body-layer/docs/STRUCTURE.md` "would have dropped 84KB of design rationale out of the corpus
  silently". A roadmap split is the third instance. *Almost free to detect:* the corpus guard's
  200-file ceiling **trips loudly** at ~383, forcing a conscious decision at exactly the right
  moment. Do not pre-raise it.
- **R3 — the dirty flag stops firing.** `graphify-dirty-flag.sh`'s regex misses `*/ROADMAP/*.md`,
  so entry edits stop recording that a rebuild is owed and the graph *launders* staleness instead of
  lagging it (`docs/PROCESS.md`, "Documents before the graph"). Detectable only by noticing
  `GRAPH_REPORT.md`'s mtime. One line, and **the same regex already has the `BACKLOG` hole today** —
  the single highest-value line in this plan.
- **R4 — the push and commit gates block or warn spuriously.** Both regexes stop matching. Loud,
  failing in the safe direction. Fix in Stage 0 anyway: a gate that cries wolf gets bypassed.
- **R5 — dangling wikilinks, now across ~300+ conversions.** Obsidian colours an unresolved
  `[[link]]`; `grep` does not, and no gate does. The bare-ID form makes this **much smaller** than
  either alternative would have: a link carries only the ID, so there is no title inside it to go
  stale, and a retitle cannot break a referrer at all. What remains is a link to an ID that does not
  exist — a typo, or an entry deleted rather than closed. The Stage 1 gate checks: every `[[target]]`
  resolves to an existing entry file, every entry file's name matches `<ID>.md` with an H1 whose
  first token is that same ID (so the displayed title cannot drift from the file it names), and
  every entry appears in exactly one index.
- **R6 — committed editor state.** The spike commits five `audio-adapter/.obsidian/` files, 276
  lines, including 220 lines of `workspace.json` pane geometry that rewrites on every pane move.
  Resolved by decision 4; see Stage 1 for the exact pattern and removal.
- **R7 — vault configuration is now unrecorded, and it grew.** Covered under "new costs" above;
  decisions 2 and 4 pull in opposite directions and prose is the only bridge. The structure test
  added to it: the readable sidebar now needs the **Front Matter Title** plugin installed, with
  main template `#heading`, fallback `_basename`, and Obsidian's own "Show inline title" turned
  off. None of that can live in the repo. **It degrades safely** — without the plugin every link
  still resolves and every file still reads; only the explorer and graph show bare IDs. So this is
  a first-run instruction in `docs/DOC_CONVENTIONS.md`, not a dependency, and it must say what the
  repo looks like *without* the plugin so a public cloner is not left thinking it is broken.
- **R7b — a display plugin is a single-maintainer third-party component.** Front Matter Title 4.2.1,
  one author, 75k downloads, last updated within the month. If it is abandoned or broken by an
  Obsidian update, the sidebar reverts to bare IDs and nothing else changes — no data loss, no
  broken link, no migration. That is the whole reason the *links* were kept plugin-independent
  rather than routed through the plugin's own link-rewriting feature (which does not work here
  anyway).
- **R8 — this touches the config surface the project has been burned by twice** (stale subproject
  lists producing silent PASS). Mitigation is the repo's own: **never write a list of which
  subprojects are converted.** `ls */ROADMAP/ 2>/dev/null` answers it and cannot go stale.
- **R9 — it competes with brain/memory milestones.** Stated without mitigation: this is
  documentation work while the brain layer is the named bottleneck, and decision 2 made it roughly
  2.5× the earlier scope. The staged shape below is the only real answer — every stage is
  abandonable.

---

## Staged migration plan

Every stage ends with the repo fully working and the convention coherent, so the work is
abandonable after any stage. **The intent is to finish; the abandonable property is kept anyway**,
because a stage that cannot be stopped at is a stage that must be rushed. Nothing is converted
before Stage 0.

### Stage 0 — fix the consumers, on `main`, with nothing converted

Seven one-line edits, all safe while nothing is split (a `find` over a directory that does not
exist returns nothing; a widened regex still matches `ROADMAP.md`):

1. `graphify-dirty-flag.sh:41` — add `*/ROADMAP/*.md` **and the missing `BACKLOG`** to the regex.
2. `graph-corpus-files.sh:74` — `find "$sub/ROADMAP" -name '*.md' 2>/dev/null` inside the existing
   `*/pyproject.toml` loop.
3. `push-roadmap-gate.sh:59` — widen to `(^|/)ROADMAP(\.md|/[^/]+\.md)$`.
4. `commit-quality-gate.sh:188` — same widening.
5. `status-page/SKILL.md` + `status-page-refresh.sh` — read the index when the sentinel is present,
   and **assert a non-zero forward-item count before publishing**.
6. `session-start.sh:66` — "the subproject's roadmap (`ROADMAP.md`, or its `ROADMAP/` index where
   split)".
7. Add `.obsidian/` to root `.gitignore` (decision 4) — see Stage 1 step 1 for the untracking.

**Gate:** commit a trivial touch to `audio-adapter/ROADMAP.md` and to `body-layer/BACKLOG.md`,
confirm the dirty flag fires for both and the push gate passes; `graph-corpus-files.sh | wc -l`
unchanged at 172. **Stop point:** repo working, spike unmerged, zero conversions — and fix 1 is a
one-line repair of a *live* bug independent of everything else here.

### Stage 1 — decision 4, then the reference conversion and the written convention

The convention must exist before a second subproject is converted, or the second converter
re-derives it.

1. **`.obsidian` everywhere (decision 4), exactly:**
   - Pattern in root `.gitignore` — unanchored, directory-only, matches at any depth:
     ```gitignore
     # Obsidian vault configuration — per-user, and workspace.json rewrites on
     # every pane move. The vault is rooted at the repo root; see docs/DOC_CONVENTIONS.md.
     .obsidian/
     ```
     Not `/.obsidian/`, which would anchor to the repo root and leave
     `audio-adapter/.obsidian/` tracked.
   - Removal from tracking, in the same change (on `obsidian-test` before merging, so the spike
     never lands them): `git rm -r --cached audio-adapter/.obsidian` then commit. Five files:
     `app.json`, `appearance.json`, `core-plugins.json`, `graph.json`, `workspace.json`.
   - **Then delete `audio-adapter/.obsidian/` from disk**, not just from the index — a nested vault
     resolves `[[AA-4.5]]` but not `[[BL-12]]`, which is a half-working vault that looks fine (R7).
   - **Vault scope, confirmed:** the single vault is the **repo root**, and
     `/Users/sg/Code/DCS-petrobrain/.obsidian/` already exists, so the user has already configured
     it. Nothing to do now; the one thing he must do *by hand* is re-add the repo root as a vault
     after any fresh clone, since the config is untracked from here on. One paragraph in
     `docs/DOC_CONVENTIONS.md` is the only record that will exist.
   - Adjacent and free, flagged not assumed: `.DS_Store` is also untracked and showing in
     `git status`. Outside decision 4's wording — add it only if the user says so.
2. ~~Verify the link form in Obsidian.~~ **Done, 2026-10-06, and it settled the structure.**
   Frontmatter aliases do not resolve here; ID-only filenames plus Front Matter Title with
   `#heading` do. See "Tested and rejected" and "Tested and settled" above. No work left in this
   step; it is kept numbered so the stage's shape matches the record. **The user's one-time Obsidian
   setup** (install the plugin, main template `#heading`, fallback `_basename`, "Show inline title"
   off) belongs in step 5's prose, not here — it is a reader instruction, not a migration step.
3. **Resolve `AA-3`** with the user (open decision 1 below) — a correctness question, not a
   convention one.
4. **Re-form the merged spike to the revised structure:** rename its 22 entry files to `<ID>.md`,
   move each title into an H1 of the form `# <ID> — <Title>`, rewrite its escaped-pipe links to bare
   `[[<ID>]]`, inline-only tags, `AA-*` IDs unchanged. This is now a real conversion of the spike
   rather than a cosmetic pass — the spike's filenames and link form are both superseded. It is also
   the cheapest place to find out whether the convention is actually pleasant to write, on 22 files
   instead of 204.
5. **Write `docs/DOC_CONVENTIONS.md`** — the directory layout, the `<prefix>-W<n>` scheme and its
   four assignment rules, the grooming rule, the `<ID>.md` filename and `# <ID> — <Title>` H1 rule,
   the bare `[[<ID>]]` link form, the pointer sentinel, the index's no-status rule, the repo-root
   vault and the one-time Obsidian setup (Front Matter Title, `#heading`/`_basename`, inline title
   off) **with a sentence saying what the repo looks like without it**, world-model's `M<n>`
   irregularity, `MI-5b`'s letter suffix. `docs/TAGS.md` stays as the vocabulary and is linked, not
   duplicated. **It must not list which subprojects are converted** (R8).
6. **One line each** pointing at it from: root `CLAUDE.md` "Backlog Management" (the natural home —
   it already owns the ID scheme, and the `-W<n>` space belongs there), and `docs/PROCESS.md`
   "Keeping the knowledge graph honest" (the corpus now follows `ROADMAP/` directories).
7. **Add the two gates:** the index/link/H1 consistency check (R5 — every `[[ID]]` resolves, every
   entry file is `<ID>.md` with an H1 whose first token is that ID, every entry in exactly one
   index), and a vocabulary check that every inline tag in a converted file appears in
   `docs/TAGS.md` — benefit (d) is conditional on the second one existing.
8. **Write the TOC helper** (user direction, 2026-10-06: *"you can create a tool that using standard
   bash tools combines filename and title into a TOC"*). ID-only filenames mean `ls ROADMAP/` is a
   column of IDs rather than the ~200-token table of contents the spike measured, which costs a
   *reader of the directory* — me — one extra read. A few lines of `awk` over each file's first H1
   restores it: `<ID>  <title>  <status tags>`, one line per entry, no index read needed. Cheap, and
   it removes the only cost the ID-only filename introduced.
8. **Update the ~22 prose lines** across the six agent role files, `merge`/`integrity-audit`/`retro`
   skills, `dod.md`, root `CLAUDE.md` and the four subproject `CLAUDE.md`s.
9. **Raise the corpus ceiling** by the measured amount, then `/graph-refresh` — **documents first,
   graph second** (`docs/PROCESS.md`).

**Gate:** all Stage 0 consumers re-verified against the converted `audio-adapter/`; the corpus guard
fires and is raised deliberately; a fresh Session Start reads the index and finds the next
actionable item. **Stop point:** one subproject converted, convention written and gated, 441
historical references still valid through the pointer.

### Stage 2 — `body-layer/ROADMAP.md`, the stress test and the whole of the measured cost

First among the unconverted because it is where the cost is: 46.5k tokens, 67 entries, 130 commits
in 30 days, read on almost every session.

1. **Fold the 18 debt entries into their Status entries** before splitting anything. ~6 are genuine
   duplicates and two of those disagree with each other about whether the work is done — each needs
   a one-line judgement about which record is right. The rest become `#needs-flight` on their
   entry. The ~365-line debt preamble becomes four lines of prose plus the `grep` recipe, in the
   index.
2. **Mint `BL-W1`…`BL-W27`** in document order, top to bottom (assignment rule 2).
3. Split 49 entries; "Keeping this current" goes to the **index**, not an entry.
4. Decide where `BR-1`/`BR-2` live — body-layer's roadmap currently hosts brain-layer's two
   milestones and `brain-layer/` has no `ROADMAP.md` at all. **Recommend status quo**: keep them in
   `body-layer/ROADMAP/` with one line in the index saying so. Creating a roadmap for a subproject
   mid-migration is scope creep, and root `ROADMAP.md`'s status table already documents the
   arrangement. (At repo-wide scope this is now a visible oddity — `ls */ROADMAP/` shows five, not
   six — hence the index line.)
5. Convert 139 cross-references; tag; `/graph-refresh`; re-measure node count against the 185/264
   baseline to answer the spike's open question 4 with a number.

**Gate:** the link/index check passes; a Session Start on body-layer is measurably cheaper;
body-layer's graph node count rises from 54 toward 49+. **Stop point:** two subprojects converted —
49% of the token cost and the whole of the stress test.

### Stage 3 — `body-layer/BACKLOG.md` and `todo/backlog.md`

The two cheapest remaining wins, 77 entry files, **two new IDs total** (`BL-B<next>`, `X-B34`), and
`todo/backlog.md` needs **zero consumer changes** (its corpus and dirty-flag coverage are already
recursive). Together they take another 45.5k tokens off the common read. No new decisions.

**Stop point:** every high-churn, high-token surface converted.

### Stage 4 — `world-model/ROADMAP.md`

35 entries, 20 mints (`WM-W1`…`WM-W20`), 7 debt entries folded, 69 cross-references, ~160-line tail
to the index. One judgement carried from Stage 2's pattern: world-model's debt list also duplicates
Status entries (`fix/los-elevation-tolerance`, `feature/dcs-driven-los`). Mature subproject, low
churn — last among the dense files, not first.

### Stage 5 — `aircraft-layer/ROADMAP.md` and `mission-interpreter/ROADMAP.md`

21 entry files, 2 indexes, 8 mints (`AC-1`…`AC-8`; mission-interpreter needs none), 6.7k tokens.
**The token case for these two is weak and this stage is here on decision 2's browsability ground
alone** — stated plainly so a later session does not re-derive the earlier "leave them" verdict and
think it found something. `mission-interpreter` is complete through `MI-6`, so its conversion is
pure navigation. Finishing the set is the point: a graph view with two holes in it is the thing
decision 2 rejected.

**Stop point:** complete. `ls */ROADMAP/` shows five subprojects plus `todo/backlog/`, and no file
anywhere lists which.

---

## Second-order effect

Repo-wide adoption turns the two hand-kept live-acceptance debt lists into one `grep` over tags,
which directly serves the project's largest accumulated bookkeeping load — ten-plus unflown
features across three subprojects — and this plan has already shown those lists disagree with their
own Status entries in ~6 places, so the conversion *fixes* a correctness problem rather than only
reorganising one. It also narrows a future choice: once `graph-corpus-files.sh` follows
directories rather than filenames, any further document split (the spike's "maybe later: `NOTES.md`
per insight") becomes cheap instead of a fourth instance of a known silent-dropout failure.
Against that, it adds a permanent naming contract — a `-W<n>` space, 204 files, 7 indexes, 2 gates —
that every future roadmap entry in the repo must satisfy, in a project whose recurring failure is a
convention outliving the file that records it. That is why Stage 1's convention doc and both gates
are not optional and come before Stage 2, and why `docs/DOC_CONVENTIONS.md` is forbidden from
listing what is converted.

---

## Decisions requiring user input

1. **`AA-3` — flown-and-accepted, or live-acceptance debt?** Carried forward undecided. The entry
   asserts both *"FLOWN, TESTED AND ACCEPTED 2026-10-05"* and *"Live acceptance is tracked as debt,
   not waived."* One of those sentences has to go. If accepted, delete the debt sentence; if debt is
   real, `#needs-flight` belongs on `AA-3` and the acceptance claim needs qualifying. **Not a
   convention question** — it is about what has actually been flown, and the next session will read
   whichever survives as fact. Resolve before merging the spike.
2. **The debt list stops being a list.** This plan replaces the two "Live acceptance debt" prose
   lists with `#needs-flight` tags plus a `grep`, because keeping them as entry files would mint two
   permanent IDs per item and freeze ~6 existing disagreements. But that list is a surface *you*
   read to decide what to fly next, and a `grep` recipe in an index is not the same reading
   experience as a hand-written list with a paragraph of context per item. If you want the narrative
   list kept, say so — it then stays as prose in the index (not as entry files), and the ~6
   duplicates still have to be reconciled either way.
3. **World-model's `M<n>` milestone prefix stays irregular.** Its milestones are `M0`…`M11` while
   its backlog is `WM-B<n>` and its work items would be `WM-W<n>` — three shapes in one subproject.
   Fixing it means renaming `M5` → `WM-5` across several hundred prose mentions in `plans/` and
   `research/`, which never-renumber and `docs/PROCESS.md` both forbid. Recommendation: accept the
   irregularity and record it. Confirm, because it is permanent.
4. **Scheduling.** Stage 0 is ~30 minutes and repairs a live bug (`BACKLOG` missing from the
   dirty-flag regex) regardless of everything else. Stages 1-5 are roughly 2.5× the earlier scope —
   several working sessions — while the brain layer is the named bottleneck. The staged shape means
   the answer can be "Stage 0 and 1 now, the rest later" without leaving anything half-broken.
