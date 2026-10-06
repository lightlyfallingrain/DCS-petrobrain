# Obsidian links and tags, repo-wide — verdict, cost/benefit, migration plan

**Plan only.** Nothing was converted and no consumer was edited while writing this.
Spike under judgement: branch `obsidian-test`, tip `f99617f`, write-up
`todo/links-and-tags.md`, vocabulary `docs/TAGS.md`, converted subject `audio-adapter/`.

---

## Verdict — adopt partially, in that order, and stop early by default

**Adopt the convention. Convert three files, not seven. Convert nothing until the six
consumers are fixed first.**

| | file | lines | ~tokens | entries | verdict |
|---|---|---|---|---|---|
| ✅ keep | `audio-adapter/ROADMAP.md` | 577 | 10.5k | 22 | already converted by the spike — merge it |
| ✅ convert | `body-layer/ROADMAP.md` | 2303 | **46.5k** | 67 | the only file whose read cost is a real project cost |
| ✅ convert | `body-layer/BACKLOG.md` | 1304 | 24.7k | 43 | second-densest, same ID scheme, same churn |
| 🟡 optional | `world-model/ROADMAP.md` | 1381 | 29.2k | 42 | worth it, but a mature subproject — low churn, lower urgency |
| ❌ leave | `todo/backlog.md` | 1126 | 20.8k | 34 | cross-cutting and session-scoped; `X-B<n>` churn is lowest and the file is a working surface, not a reference |
| ❌ leave | root `ROADMAP.md` | 72 | 6.1k | 0 | **the one file that must not be split.** 20+ consumers read its status table *by name* for the subproject list. It has no checkbox entries to split. Splitting it breaks the most and buys the least |
| ❌ leave | `aircraft-layer/ROADMAP.md` | 131 | 2.7k | 12 | 12 files for 2.7k tokens is overhead, not navigation |
| ❌ leave | `mission-interpreter/ROADMAP.md` | 177 | 4.0k | 9 | subproject complete through MI-6; a frozen file does not need splitting |

**The load-bearing step:** the benefit is not spread across the repo, it is concentrated in
**two files**. `body-layer/ROADMAP.md` + `body-layer/BACKLOG.md` are 71.2k of the 144.7k
measured roadmap/backlog tokens (49%) and 110 of the 229 entries, and `body-layer/ROADMAP.md`
alone was touched by **130 commits in the last 30 days** — the highest-churn document in the
repo. The three small roadmaps together are 9.4k tokens (6.5%) and 33 entries: converting them
creates 33 files and 3 more indexes that can go stale, and saves a read nobody notices.
A partial adoption buys ~95% of the measured benefit for ~60% of the files.

**Why adopt at all, given it is not pilot-facing.** Two reasons survive the Effort/Value check,
and one does not. It survives because (1) the human who sets this project's direction says
navigation is materially easier, and his navigation cost *is* a project cost — this is not
developer ergonomics on a team of strangers; and (2) tags give a trustworthy `grep` **negative**
over a cross-cutting axis, which root `CLAUDE.md` states the knowledge graph explicitly cannot,
and the 5 Hz incident is the recorded price of not having one. It does **not** survive on
agent-token savings alone, which are real (below) but would not justify touching the config
surface on their own.

---

## Cost

### Files created

| stage | entry files | index files | running total |
|---|---|---|---|
| audio-adapter (done) | 22 | 1 | 23 |
| body-layer ROADMAP | 67 | 1 | 91 |
| body-layer BACKLOG | 43 | 1 | 135 |
| world-model (optional) | 42 | 1 | 178 |
| *full adoption, not recommended* | *+33* | *+3* | *236* |

Measured, not estimated: `grep -cE '^[[:space:]]*- \[[ x~?>]\]'` gives 22 for
`audio-adapter/ROADMAP.md`, and the spike produced exactly 22 entry files. The count is reliable.

### Consumers to update — the complete sweep

Swept mechanically across `.claude/scripts/*.sh`, `.claude/skills/**/SKILL.md`,
`.claude/agents/*.md`, `docs/*.md`, root and all six subproject `CLAUDE.md`, and the git hooks.
**The spike's list is incomplete** — it misses `commit-quality-gate.sh`, `graphify-dirty-flag.sh`
and `push-roadmap-gate.sh`, which are the three *mechanical* consumers, i.e. the ones that fail
without a human in the loop.

| consumer | what breaks | failure is | fix |
|---|---|---|---|
| `.claude/scripts/graphify-dirty-flag.sh:41` | regex `[^/]+/(CLAUDE\|ROADMAP)\.md` does not match `body-layer/ROADMAP/BL-12-*.md`. **Editing a roadmap entry stops recording that a semantic rebuild is owed** — the graph silently goes stale while reading as current | **SILENT · worst** | one-line regex: add `\|[^/]+/ROADMAP/[^/]+\.md` |
| `.claude/scripts/graph-corpus-files.sh:74` | corpus is a **file list** over fixed names `ROADMAP CLAUDE BACKLOG`. Entry files are never listed, so the roadmap content leaves the graph | **SILENT** | one line: `find "$sub/ROADMAP" -name '*.md'` |
| `.claude/scripts/status-page-refresh.sh:63-64` + `.claude/skills/status-page/SKILL.md:47,49,64` | derives subsystem status lines and the forward-only map from each subproject `ROADMAP.md`; reading a 4-line pointer yields an empty-but-plausible page and reports success | **SILENT · dominant** | prose + add an assertion (below) |
| `.claude/scripts/push-roadmap-gate.sh:59` | `grep -qE '(^\|/)ROADMAP\.md$'` on pushed paths. An entry-file-only roadmap update no longer matches, so the gate **blocks every legitimate feature merge push** | LOUD (safe direction) | one-line regex |
| `.claude/scripts/commit-quality-gate.sh:188` | same regex, emits a spurious "roadmap not updated alongside dod-check" warning | LOUD (safe direction) | one-line regex |
| `.claude/scripts/session-start.sh:66` | prose tells the session to read "the `ROADMAP.md` of whichever subproject"; it reads a stub and concludes nothing is next | SEMI-SILENT | prose |
| `.claude/skills/merge/SKILL.md:42,74` | "the merged branch's subproject `ROADMAP.md` is the source of truth" — now means the entry file + the index | SEMI-SILENT | prose |
| `.claude/agents/dod.md:105,193` | step 11 instructs the roadmap update in detail | SEMI-SILENT | prose |
| `.claude/skills/integrity-audit/SKILL.md:28,70`, `.claude/skills/retro/SKILL.md:139,161,187` | read subproject roadmaps as audit inputs | SEMI-SILENT | prose |
| `.claude/agents/{architect,implementer,debugger,investigator,reviewer,performance-reviewer}.md:37-40` | identical "Where things live" block naming `<subproject>/ROADMAP.md` | SEMI-SILENT | one line × 6, identical edit |
| root `CLAUDE.md:45-46, 90, 138-139, 365-368` | Session Start, Milestone Completion, the `AA-B<n>`/`WM-B<n>` ID-location table | SEMI-SILENT | prose |
| `body-layer/CLAUDE.md`, `audio-adapter/CLAUDE.md`, `world-model/CLAUDE.md`, `mission-interpreter/CLAUDE.md` | one roadmap mention each | trivial | prose |

**Not consumers, and this matters:** `check`, `test`, `compile`, `test-instructions`,
`update-template` and `status-page:14` all read root `ROADMAP.md`'s **status table for the
subproject list only**. Root `ROADMAP.md` stays whole, so these need no change at all. That
removes six files from the blast radius the raw grep suggests.

**Do not touch the 429 historical mentions.** `grep -o` finds 429 references to a
subproject roadmap path, but 390+ are in `plans/*/dod-check.md`, `audits/`, `reviews/` and
dated research notes — records of what was true then. `docs/PROCESS.md` "Superseding a decision"
forbids rewriting them. **This is why the pointer file must never be deleted**: a 4-line
`ROADMAP.md` pointing at the index is what keeps all 429 honest. Deleting it would break every
one of them at once.

### Mechanical vs judgement

| work | volume | kind |
|---|---|---|
| the six consumer regex/list fixes | 6 one-line edits | **mechanical**, do first |
| prose updates in agents/skills/CLAUDE.md | ~22 lines across ~16 files | mechanical, tedious |
| splitting entries into files | 110-152 files | **mechanical** — median entry is 20 lines (body-layer) / 12 (world-model), largest *real* entry 79 lines |
| converting ID cross-references to wikilinks | 139 in body-layer, 87 in its BACKLOG, 69 in world-model | mechanical, but each must resolve (see risk D5) |
| **minting IDs for entries that have none** | **45 of 67 body-layer entries, 27 of 42 world-model entries** | **judgement, and permanent** |
| deciding where non-entry trailing sections go | body-layer has a 404-line tail (live-acceptance debt, "Keeping this current"); world-model 455 | judgement, one-off per file |
| `/graph-refresh`, documents first | 1 run, 60k in / 18k out per `graphify-out/cost.json` | mechanical |
| re-verify all six gates against the converted tree | 6 checks | mechanical |

### The cost the spike admits it does not know — and it is not what the spike expected

The spike names `body-layer` as "the honest stress test" and guesses the problem is
cross-reference density. **Measured, density is a non-problem** (~2 ID mentions per entry) and
**structure is a non-problem** (median entry 20 lines, splits cleanly).

The actual problem is that the spike's founding premise — *"every entry has a stable ID"* —
**is false for body-layer**. Of 67 entries, **45 carry no ID**: they are named by branch
(`feature/dcs-driven-los`, `fix/contact-report-flood`, `feature/sortie-refinements`) and are
mostly transient live-acceptance debt. World-model is 27 of 42. So converting the two dense
files means minting ~72 permanent IDs under root `CLAUDE.md`'s **never-reuse, never-renumber**
rule — for entries that will mostly be closed and gone within weeks. That is a judgement call
per entry and it is irreversible.

**Recommended answer, which keeps it mechanical:** the filename is the ID *when there is one*,
and the **branch name** when there is not —
`body-layer/ROADMAP/fix-contact-report-flood.md`. Branch names are already unique, already
bash-safe, already what the user and every plan call these items, and already used as the de
facto address. No permanent IDs are minted for transient debt; `#needs-flight` carries the
cross-cutting query that the hand-kept debt list carries today. State this in the convention
doc as an explicit second naming form, not as an exception.

---

## Benefit

### (a) Human navigation — real, primary, unquantifiable

User, 2026-10-06: *"this makes it a lot easier for me (as human) to read and navigate."* The
beneficiary is the product owner. Counted as the primary benefit and not discounted. No number
is available or needed.

### (b) Agent read cost — measured, and the strongest hard number

| | now | after converting body-layer | cut |
|---|---|---|---|
| Session Start on body-layer: root `ROADMAP.md` | 6.1k | 6.1k | — |
| + active subproject roadmap | **46.5k** | index ~2k + 3 relevant entries ~2k | **−42.5k** |
| + `todo/todo.md` + `todo/backlog.md` | ~24k | ~24k | — |
| **total** | **~77k** | **~34k** | **−56%** |

Converting `body-layer/BACKLOG.md` too takes the common "what is open" read from 24.7k to
~2k. This is the single most-repeated read in the project — root `CLAUDE.md` makes clearing
context between tasks a deliberate habit, so every clear pays it again.

### (c) Merge-conflict reduction — real but over-claimed

`body-layer/ROADMAP.md` took 130 commits in 30 days; per-entry files make same-file collisions
structurally rare, and that is a genuine win. **But** I did not verify that the 2026-10-05/06
pass's eight conflicts were in subproject roadmap prose, and the split does **not** help the two
places the cross-subproject narrative actually collides: the new index file and root
`ROADMAP.md`'s status table (whose cells run to ~1,500 words each). Treat this as a secondary
benefit, not a justification.

### (d) Trustworthy `grep` negatives over tags — the one genuinely new capability, and untested

This is the benefit nothing else in the repo provides. Root `CLAUDE.md` is explicit that the
graph's negatives are unreliable and that a completeness sweep must be `grep`. A closed tag
vocabulary makes `grep -l 'needs-flight' */ROADMAP/*.md` an authoritative answer to "what do I
owe a sortie" across every subproject — replacing a hand-kept prose list in
`body-layer/ROADMAP.md` that only discipline keeps current.

**Sceptically:** it has been applied to 22 entries of one subproject, the spike's own first
query of it returned a confident wrong answer (the `#`-in-frontmatter trap), and **nothing
enforces the closed vocabulary.** `docs/TAGS.md` says adding a tag is an edit to that file, but
no gate checks it — and the moment `#topic/speech` appears beside `#topic/stt`, the trustworthy
negative is gone and the whole benefit with it. This benefit is **conditional on a vocabulary
gate existing**, which is why one is in Stage 1 below rather than left to discipline.

### (e) Graph quality — modest, and the spike's framing is wrong

Measured against the live graph (`graphify-out/graph.json`, 9,487 nodes, built 2026-10-05): the
roadmap and backlog files **already** produce **185 nodes and 264 edges**, including per-entry
nodes such as `AC-B3 — Split The Export Throttle` and
`WM-B5 - valley boundary extraction`. The spike's "one node per entry instead of one giant
roadmap node" is not what the extractor does today.

The real gain is two things, both narrower: (1) it closes an extraction gap —
`body-layer/ROADMAP.md` yields only 54 nodes from 67 entries, so 13 entries are currently
invisible; and (2) `source_file` would point at a ~700-token entry instead of a 46.5k-token
file, which is what `gq.sh`'s "read these sources" list hands an agent. Provenance precision,
not size. Worth having; not a reason on its own.

---

## Risks & failure modes

Ordered by how silent each one is, because silence is the whole problem.

- **D1 — a consumer reads a stub and reports PASS (dominant).** The status page is derived from
  subproject roadmaps; pointed at a 4-line pointer it regenerates an empty-but-well-formed page
  and exits 0. `integrity-audit`, `retro` and `dod-check` have the same shape. *Caps the damage:*
  `status-page-refresh.sh`'s own header records (verified 2026-09-27) that the launchd job is
  **not installed**, so today it runs only by hand. That is luck, not a safeguard — the plist is
  committed and ready. **Make it detectable:** the pointer file must carry a machine-checkable
  sentinel line (`<!-- split-roadmap: see ROADMAP/ -->`) and the status-page skill must assert a
  non-zero item count before publishing. An assertion that fires is the difference between a
  wrong page and a refusal.
- **D2 — content silently leaves the graph corpus.** `graph-corpus-files.sh` is a curated file
  list, and **this exact failure has already happened twice**, documented in that script's own
  comments: the 2026-09-27 `BACKLOG.md` split "silently dropped 8,200 words of open items out of
  the corpus", and `body-layer/docs/STRUCTURE.md` "would have dropped 84KB of design rationale
  out of the corpus silently." A roadmap split is the third instance of a failure class the
  repo has already written down twice. *Detectable, and almost for free:* `graph-corpus-guard.sh`
  refuses a rebuild whose corpus exceeds a file ceiling — adding 110-152 files **trips that
  ceiling loudly**, forcing a conscious decision at exactly the right moment. Do not pre-raise
  the ceiling; let it fire.
- **D3 — the dirty flag stops firing.** `graphify-dirty-flag.sh`'s regex misses
  `*/ROADMAP/*.md`, so entry edits no longer record that a rebuild is owed. The graph then
  launders staleness rather than lagging it — precisely the failure `docs/PROCESS.md`
  "Documents before the graph" is about. Silent; detectable only by noticing
  `GRAPH_REPORT.md`'s mtime. One-line fix, and it is the single highest-value line in this plan.
- **D4 — the push and commit gates block or warn spuriously.** Both regexes stop matching.
  **Loud, and failing in the safe direction** — the push is refused rather than waved through.
  Fix in Stage 0 anyway; a gate that cries wolf gets bypassed.
- **D5 — dangling wikilinks.** Obsidian colours an unresolved `[[link]]`; `grep` does not, and
  neither does any gate. With 295 cross-references to convert across the three files, some will
  be wrong. *Make detectable:* a ~15-line pre-commit check that every `[[target]]` resolves to
  an existing basename and every `ROADMAP/*.md` appears in its index. This is also the answer to
  the generated-vs-hand-kept index question (below).
- **D6 — committed editor state.** The spike commits `audio-adapter/.obsidian/` — 276 lines
  including `workspace.json` (220 lines of pane geometry) that rewrites on every pane move.
  Per-user, high-churn, conflict-prone, and `.gitignore` currently has no `.obsidian` entry
  (root `.obsidian/` is untracked and showing in `git status` today). **Add `.obsidian/` to
  `.gitignore` and drop those five files from the spike before merging.**
- **D7 — vault scope, which the write-up does not raise.** The spike made `audio-adapter/` the
  vault. A repo-wide convention needs `[[AA-4.5]]` to resolve from a `body-layer` entry, and
  Obsidian resolves basenames **within one vault** — so the vault root must be the **repo root**,
  not per-subproject. Per-subproject vaults would break the cross-subproject `#topic/*` axis that
  is the tags' stated reason to exist. Decide before Stage 2; the repo-wide-unique-basename rule
  (spike rule 3) already assumes repo-root scope without saying so.
- **D8 — this touches the config surface the project has been burned by twice** (stale
  subproject lists producing silent PASS, root `CLAUDE.md`'s own warning). Mitigation is the
  same one the repo already uses: **never write a list of which subprojects are converted.**
  `ls */ROADMAP/ 2>/dev/null` answers it mechanically and cannot go stale.
- **D9 — it competes with brain/memory milestones.** Honest statement, no mitigation offered:
  this is documentation work during the phase where the brain layer is the named bottleneck. The
  staged plan below exists so it can be abandoned after any stage without leaving the repo
  half-broken, which is the only real answer to this.

---

## The spike's open questions — recommendations

1. **Generated or hand-kept index? → Hand-kept, plus a mechanical consistency gate.**
   A generator is a build step in a repo that deliberately has almost none, and the no-status
   rule already removes the only part that drifts. But "hand-kept" fails the way this project
   always fails — by being forgotten — so pair it with the ~15-line pre-commit check from D5:
   every entry file appears in its index, every `[[link]]` resolves. Cheaper than a generator,
   and it catches the two failures a generator would not (dangling links, orphan files).
2. **`AA-4.1` or `AA-4-1`? → Keep the dot.** Root `CLAUDE.md` already defines the dotted form,
   and 400+ existing prose mentions across `plans/`, `audits/` and research notes use it.
   Changing the separator makes every historical mention un-greppable for the sake of
   readability in a filename the alias form hides anyway. Dots are fine for bash and Obsidian;
   the spike verified that.
3. **Does `body-layer` survive it? → Yes, but not for the reason asked.** Measured: structure
   splits cleanly (median entry 20 lines) and cross-reference density is low (~2 per entry).
   What does *not* survive is the premise that every entry has an ID — 45 of 67 do not. Adopt
   the branch-name filename form above and body-layer converts mechanically. Without that
   decision, converting body-layer means minting 45 permanent IDs for transient debt, and I
   would recommend against it.
4. **Does the graph get better or just bigger? → Better, narrowly; not bigger.** Measured above:
   185 roadmap/backlog nodes already exist. The split closes a 13-entry extraction gap in
   body-layer and sharpens `source_file` from a 46.5k-token file to a 700-token entry. Real,
   provenance-shaped, and smaller than the spike claims. Re-measure after Stage 2 — it is one
   `/graph-refresh` and a node count, which is the test the spike itself proposed.
5. **`AA-3`'s accepted-versus-debt contradiction → the user's call, flagged not decided.**
   `AA-3` asserts both *"FLOWN, TESTED AND ACCEPTED 2026-10-05"* and *"Live acceptance is tracked
   as debt, not waived."* One of those sentences has to go. If accepted, delete the debt
   sentence; if debt is real, `#needs-flight` belongs on `AA-3` and the acceptance claim needs
   qualifying. **Resolve this before merging the spike** — it is a correctness question about
   what has actually been flown, not a convention question, and it will be read as fact by the
   next session either way.

---

## Staged migration plan

Every stage ends at a state where the repo is fully working and the convention is coherent, so
the whole thing is abandonable after any stage. Nothing is converted before Stage 0.

### Stage 0 — fix the consumers first, on `main`, with nothing converted

Six edits, all one-line, all safe while only `audio-adapter` is converted (a `find` over a
directory that does not exist yet returns nothing; a widened regex still matches
`ROADMAP.md`):

1. `graphify-dirty-flag.sh:41` — add `*/ROADMAP/*.md` to the dirty-flag regex.
2. `graph-corpus-files.sh:74` — `find "$sub/ROADMAP" -name '*.md'` inside the existing loop.
3. `push-roadmap-gate.sh:59` — widen to `(^|/)ROADMAP(\.md|/[^/]+\.md)$`.
4. `commit-quality-gate.sh:188` — same widening.
5. `status-page/SKILL.md` + `status-page-refresh.sh` — read the index when a pointer sentinel is
   present, and **assert a non-zero forward-item count before publishing**.
6. `session-start.sh:66` — "the subproject's roadmap (`ROADMAP.md`, or its `ROADMAP/` index where
   split)".

**Gate:** make a trivial commit touching `audio-adapter/ROADMAP.md` and confirm the dirty flag
fires and the push gate passes; run `graph-corpus-files.sh | wc -l` before and after and confirm
the count is unchanged. **Stop point:** repo working, spike unmerged, zero conversions. This
stage is worth doing even if everything below is dropped — fixes 3 and 4 are latent bugs the
moment anyone splits anything, and fix 1 is one line against a documented failure class.

### Stage 1 — merge the spike as the reference conversion, and write the convention down

Order matters: the convention must exist before the second subproject is converted, or the
second converter re-derives it.

1. Add `.obsidian/` to `.gitignore`; drop `audio-adapter/.obsidian/` from the spike (D6).
2. Resolve `AA-3` with the user (open question 5).
3. Write **`docs/DOC_CONVENTIONS.md`** — per-entry file layout, the two filename forms (ID, or
   branch name for un-IDed debt), the escaped-pipe alias link form, the pointer-file sentinel,
   the index's no-status rule, the repo-root vault decision (D7). `docs/TAGS.md` stays as the
   tag vocabulary and is linked, not duplicated. **It must not list which subprojects are
   converted** (D8) — `ls */ROADMAP/` answers that.
4. One line each pointing at it: root `CLAUDE.md` "Backlog Management" (which already owns the ID
   scheme — this is its natural home), and one sentence in `docs/PROCESS.md` "Keeping the
   knowledge graph honest" recording that the corpus script follows `ROADMAP/` directories.
5. Add the index/link consistency pre-commit check (D5) **and** a vocabulary check that every
   `#topic/*` or frontmatter tag in a converted file appears in `docs/TAGS.md` (benefit (d) is
   conditional on this).
6. Update the ~22 prose lines in the six agent role files, `merge`/`integrity-audit`/`retro`
   skills, `dod.md`, root `CLAUDE.md` and the four subproject `CLAUDE.md`s.
7. `/graph-refresh`, **documents first, graph second** (`docs/PROCESS.md`).

**Gate:** all six Stage 0 consumers re-verified against the converted `audio-adapter/`; the
corpus guard fires on the file-count rise and is raised deliberately; a fresh Session Start run
reads `audio-adapter`'s index and finds the next actionable item. **Stop point:** one subproject
converted, convention documented and gated, 429 historical references still valid via the
pointer. A perfectly coherent end state — this is the honest "keep as audio-adapter-only"
outcome, reached deliberately rather than by abandonment.

### Stage 2 — `body-layer/ROADMAP.md` (why this one first)

It is first among the unconverted because it is the only file where the cost is measurable:
46.5k tokens, 67 entries, 130 commits in 30 days, and it is the file Session Start reads on
almost every session. `world-model` is bigger-than-average but its subproject is mature and
read far less often; converting it first would be converting the easier file, not the expensive
one, and would leave the stress test unproven.

1. Decide the un-IDed-entry naming (open question 3) and record it in `docs/DOC_CONVENTIONS.md`
   before splitting a single file.
2. Split 67 entries; the 404-line trailing block (live-acceptance debt, "Keeping this current")
   goes to the **index**, not to an entry.
3. Decide where `BR-1` entries live — body-layer's roadmap currently hosts brain-layer's two
   milestones and `brain-layer/` has no `ROADMAP.md` at all. Either keep them in
   `body-layer/ROADMAP/` (status quo, one line in the index saying so) or give brain-layer its
   own file. **Recommend status quo**: creating a roadmap for a subproject mid-migration is
   scope creep, and root `ROADMAP.md`'s status table already documents the arrangement.
4. Convert 139 cross-references; tag; `/graph-refresh`; re-measure the node count against the
   185/264 baseline in this plan to answer open question 4 with a number.

**Gate:** the link/index check passes; a Session Start run on body-layer is measurably cheaper;
graph node count for body-layer rises from 54 toward 67. **Stop point:** two subprojects
converted, which is where 49% of the token cost and the entire human-navigation complaint lives.
**This is the recommended place to stop by default.**

### Stage 3 — optional: `body-layer/BACKLOG.md`, then `world-model/ROADMAP.md`

Same procedure, no new decisions, 85 more entry files. Do it only if Stage 2 demonstrably paid
off in practice — specifically if the pilot says navigation improved *and* the index did not go
stale over a few weeks of real merges.

### Stage 4 — do not do

`aircraft-layer`, `mission-interpreter`, `todo/backlog.md`, root `ROADMAP.md`. If a later session
proposes completing the set for consistency, the reason not to is in the verdict table: 33 files
and 3 indexes for 6.5% of the tokens, and root `ROADMAP.md`'s status table is load-bearing to
20+ consumers that currently need no change at all.

---

## Second-order effect

Converting `body-layer/ROADMAP.md` makes the forward-looking debt list a `grep` over tags instead
of hand-kept prose, which directly helps the live-acceptance backlog that currently spans ten-plus
unflown features across three subprojects — the project's largest accumulated bookkeeping load.
It also narrows a future choice: once `ROADMAP/` directories exist, `graph-corpus-files.sh`
follows directories rather than filenames, which makes any *further* document split (the spike's
"maybe later: `NOTES.md` per insight") cheap rather than another third-instance-of-a-known-failure.
Against that, it adds a permanent naming contract that every future roadmap entry must satisfy,
in a repo whose recurring failure is exactly a convention outliving the file that records it —
which is why Stage 1's convention doc and gates are not optional and come before Stage 2.

---

## Decisions requiring user input

1. **`AA-3` — flown-and-accepted, or live-acceptance debt?** Not a convention question. One of
   the two sentences is wrong about what has actually been flown.
2. **How far to go: Stage 1, Stage 2, or Stage 3?** The recommendation is Stage 2 (audio-adapter
   + body-layer's roadmap) with Stage 3 conditional. Stage 0 should happen regardless.
3. **Minting IDs for the 45 un-IDed body-layer entries, or the branch-name filename form?** The
   recommendation is branch names, because the never-reuse rule makes minted IDs permanent and
   these entries are transient — but it introduces a second filename form into the convention,
   which is a real cost and the user may prefer uniformity.
4. **Is documentation-convention work worth a slot now, with brain/memory named as the
   bottleneck?** Stage 0 is ~30 minutes and fixes latent bugs. Stage 2 is a working session.
   Flagged under the Effort/Value check because it is not pilot-facing; the staged shape exists
   so the answer can be "Stage 0 only, for now."
