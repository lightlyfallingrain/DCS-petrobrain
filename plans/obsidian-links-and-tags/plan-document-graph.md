# Stage 1b — the document graph: tying research, plans and acceptance docs into the roadmap

**Plan only. Nothing was generated, no document was edited, no tag was minted while writing this.**
Primary inputs: `plans/obsidian-links-and-tags/explore-notes.md` (the user's own words) and
`plans/obsidian-links-and-tags/sketch-document-graph.jpg` (the specification). Parent plan:
`plans/obsidian-links-and-tags/plan.md`.

---

## Verdict

**Build it — but in a different shape than the brief assumes, and stop after Stage B.**

Two measurements taken while planning change the design, and both are the kind that are invisible
until someone counts:

**1. graphify cannot write these links, and the gap is ~10×.** For the sketch's own example, the
live graph (9,487 nodes, built 2026-10-05) surfaces `SPU-8` in **3 documents**. `grep -rl 'SPU-8'`
finds **31**. Across the whole corpus, graphify's document-to-document edges are **231 distinct file
pairs over 543 document files** — median degree 3, max 10. That is far too sparse to draw the
sketch. Worse, `graph-corpus-files.sh` excludes `plans/*` except the one active plan, so graphify
**cannot see 92 of the 243 document units** at all.

So the decision *"graphify writes the links"* is honoured in the part that matters — **no human
authors a link** — but the mechanism changes: **graphify proposes the vocabulary; a deterministic
pattern matcher writes the links.** This is also the project's own rule, applied to its own
documentation: *graph to find it, `grep` to prove it* (root `CLAUDE.md`). Discovery is graphify's
job; completeness is `grep`'s.

**2. The hub the user fears is real, it is in their own sketch, and no amount of matching cleverness
fixes it.** Measured over the 243 document units in scope today:

| candidate tag | documents it would connect |
|---|---|
| `#SPU-8` | **18** |
| `#aircraft-manipulation` | **22** |
| `#coordinates` | 43 |
| `#los` | 70 |
| `#audio` | **80** |
| `#perception` | 86 |
| `#speech` | 93 |
| `#terrain` | **146** |

`#SPU-8` and `#aircraft-manipulation` draw exactly the graph in the sketch. `#audio` — also in the
sketch — draws the 80-edge hub that means nothing.

Two obvious fixes were tested and both fail. **Requiring more mentions** destroys the good tag
faster than it tames the bad one (`#SPU-8` 18→9→3 while `#audio` only goes 80→46→18). **Matching
only titles and headings** drops `#SPU-8` to 5 documents and loses `AA-3` itself — the sketch's
centre — because `AA-3`'s H1 is *"Slice 2 — cockpit state drives the audio"* and never says SPU-8.

**The only lever that works is the vocabulary's own specificity**, which means the admission rule
must be a *measured size band*, not a human judgement call. And the user's sketch already knew
this: *"volume"* and *"playback"* hanging off `#audio` are not documents — they are the narrower
tags `#audio` has to become.

### Cost / benefit

| | |
|---|---|
| **Effort** | Stage A ~half a session, Stage B ~one session, Stage C ~1 hour. Stage D is open-ended and deferred. |
| **New files** | 3 scripts, 0 documents. **The graph corpus does not grow** (198 files, unchanged) — this adds blocks to files already in it. |
| **Buys** | The sketch, rendered, over 151 documents: every research note and acceptance doc reachable from the roadmap entry it belongs to, by clicking a tag. A `grep` negative that is finally trustworthy across document *kinds*, not just inside one roadmap. |
| **Does not buy** | Anything pilot-facing. This is navigation for the product owner — a real beneficiary stated in their own words, but it competes with the brain layer, which is the named bottleneck. |
| **Recommendation** | **Stages A + B, then stop and look at the actual Obsidian graph.** Stage B ends with the exact example the user drew rendering for real; that is the only honest test of whether Stages C and D are worth anything. Everything after it is deferrable without leaving the repo half-converted. |

---

## Goal

Generate, from a human-approved closed vocabulary, the tag and roadmap-link blocks that let the
user navigate from a roadmap entry to the research, plans and acceptance documents about the same
topic — in Obsidian, by clicking, without a human authoring a single link.

---

## Affected modules / files

| file | change |
|---|---|
| `docs/TAGS.md` | **rewritten.** The two-subprojects rule replaced; per-tag sections carrying the match pattern and the measured hub size; the closed-vocabulary argument kept |
| `docs/DOC_CONVENTIONS.md` | new sections: the generated block, where topic tags live vs. status tags, the typed-edge convention, which document kinds are in scope |
| `.claude/scripts/doc-graph-refresh.sh` | **new.** The generator. Writes the delimited block into every in-scope document |
| `.claude/scripts/doc-graph-gate.sh` | **new.** Verifies only, never writes. Pre-commit |
| `.claude/scripts/doc-tags-propose.sh` | **new.** Reads graphify, measures hub sizes, emits a batch of proposals for the user |
| `.claude/scripts/roadmap-entry-consistency-gate.sh` | **fixed** (union of IDs across directories — see R1) and extended to the new document kinds |
| `audio-adapter/ROADMAP/*.md` (23) | generated block added; topic tags move off the checkbox line |
| `*/research/*.md` (96), `docs/acceptance/*.md` (32) | generated block added after the H1 |
| `plans/*/` (92) | **Stage D only** |

---

## 1. The generator

**`.claude/scripts/doc-graph-refresh.sh`** — deterministic, reads only the repo, never the graph.

- **Input:** `docs/TAGS.md` (approved tags and their match patterns) + the in-scope document list.
- **Unit of matching is the *document unit*, not the file.** A plan directory is one unit (all its
  `.md` files matched together, block written to `plan.md`); every other kind is one file.
- **Match is over the whole unit's text**, case-insensitive. Recall over precision, deliberately: a
  missing edge is invisible, a spurious edge is one click to dismiss. Heading-anchoring was tested
  and loses the sketch's own centre.
- **Output is one delimited block, idempotent, byte-stable** — so the gate can verify by
  regenerating and comparing.

### The block

Same delimiters everywhere, **placed immediately after the H1** (not at the end — Obsidian shows
the reader where they land, and on a dated record a header reads as metadata rather than as a
revision of the findings):

```markdown
<!-- doc-graph:start -->
**Topics:** #SPU-8 #aircraft-manipulation
**Roadmap:** [[AA-3]]
<!-- doc-graph:end -->
```

Per kind:

| kind | `Topics:` | `Roadmap:` | notes |
|---|---|---|---|
| roadmap entry (`*/ROADMAP/<ID>.md`) | yes | **no** — it *is* one | hand-written `**Depends on:**` sits outside the block |
| research note | yes | yes | |
| acceptance doc | yes | yes | |
| plan (`plans/<f>/plan.md`) | yes | yes | Stage D |

- **`Roadmap:` is generated from IDs the document already names in its own text** — zero inference,
  pure `grep`, and it is exactly what D-1 said IDs are for. A document naming no ID gets no
  `Roadmap:` line, not an empty one.
- **A line with no values is omitted entirely.** A document matching no approved tag gets **no
  block at all** — not an empty one. Silence, never a placeholder.

### Where topic tags live — this revises the parent plan

The parent plan put *every* tag inline on the checkbox line. **Revised: `#status/*` and
`#needs-flight` stay on the checkbox line (hand-written, gate-read, must not move); topic tags live
only in the generated block.** The reason is the parent plan's own: *generated regions carry
delimiters so regeneration never touches hand-written prose*. A generator that edits the checkbox
line is editing prose it does not own, on the one line in the file whose exact shape two gates
depend on. Each concept is still spelled in exactly one place, so the two-spellings trap the parent
plan warned about does not reappear — the split is by *kind of tag*, not by location of the same
tag.

### The asymmetry — which end states the relation

**The document states it. The roadmap entry never does.** Three reasons:

1. **Obsidian's backlinks pane supplies the reverse for free**, so stating it twice buys nothing and
   costs a second thing to keep current.
2. **Roadmap entries are the churn.** `body-layer/ROADMAP.md` took 130 commits in 30 days. Research
   notes and acceptance docs are dated, append-only records nobody edits after writing — the
   cheapest possible place for a regenerated region.
3. **The reverse list is the 80-edge hub**, by construction: an entry's list of related documents
   grows forever and is never read whole.

A roadmap entry states only *its own* topics. It never lists other documents.

---

## 2. The vocabulary loop

Three steps, and the user's part is the third.

**(a) Propose — `doc-tags-propose.sh`, run on demand.** Candidates come from graphify (community
labels, concept nodes), from capitalised multi-word terms, and from IDs already in prose. For each
candidate the tool runs the *matcher* and reports the number it is actually about:

```
CANDIDATE   #spu-8                 18 units  (9 research, 4 acceptance, 3 plan, 2 roadmap)
            aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md
            docs/acceptance/2026-10-05-spu8-intercom-sortie.md
            audio-adapter/ROADMAP/AA-3.md
TOO BROAD   #audio                 80 units  -- split before proposing
TOO NARROW  #ptt-latency            2 units
```

**(b) Batch — at most 10 in-band proposals per run**, sorted by how many *currently untagged*
documents they would connect. The user will not grind through 200 proposals, so the tool never
shows 200: out-of-band candidates are summarised in one line each, not expanded.

**(c) Approve.** The tool writes `docs/TAGS.proposals.md`. The user deletes the rows they do not
want; one command promotes what remains into `docs/TAGS.md`. **Only then** may the generator emit
that tag — the gate enforces it, as it does today.

**What the generator does with an unapproved topic: nothing.** No tag, no block line, no
`#topic/unknown` placeholder. A placeholder would be a second spelling for an unnamed concept and
would destroy the trustworthy-`grep`-negative benefit that is the whole point of a closed
vocabulary.

**Drift is handled by the same tool.** `doc-tags-propose.sh` also re-measures every *already
approved* tag and reports any that has grown out of band — a tag admitted at 20 units is 40 next
year. That is the grooming step, and it is automatic, which is the standing tiebreak (*"more
automation is better"*).

---

## 3. `docs/TAGS.md` — the rewritten rule

**Out:** *"a `#topic/*` must cross at least two subprojects."* It picked the wrong axis — the user's
own example crosses two *document kinds* inside one subproject. `#topic/*` has zero members, so
nothing is renamed.

**In, three rules:**

1. **Crosses at least two document kinds** (roadmap / research / acceptance / plan). A tag confined
   to one kind in one directory is something `ls` and `grep` already answer — the sound half of the
   old rule, re-aimed.
2. **Lands in the navigable band: 3–25 document units**, measured at admission by
   `doc-tags-propose.sh` and recorded in the tag's row with the date. Below 3 it is not a hub; above
   25 it is a hub that means nothing and must be split (`#audio` → `#audio-playback`,
   `#audio-volume`, `#audio-transport`).
3. **Flat spelling for topics** (`#SPU-8`), prefixed for the machine-read ones (`#status/*`,
   `#needs-flight`).

**Kept verbatim in substance:** the closed-vocabulary argument. It is benefit (d) of the parent plan
and the reason the gate exists.

**Format change: one short section per tag, not a table row.** A match pattern needs alternation,
and `|` inside a markdown table cell must be escaped — which is precisely the two-spellings footgun
this file warns about, in the file that warns about it.

```markdown
### `#SPU-8`

- **Matches:** `SPU-?8`
- **Measured:** 18 units, 2026-10-07 (9 research · 4 acceptance · 3 plan · 2 roadmap)
- The Mi-24P intercom box: its cockpit arguments, its gating behaviour, and the audio path it owns.
```

---

## 4. Typed edges — the one hand-written thing, and why

**Convention: `**Depends on:** [[AA-3]]`, stated on the *dependent* entry only, outside the
generated block. `**Blocks:**` is never written** — Obsidian's backlinks pane is the reverse
direction, and the same asymmetry rule applies.

**graphify cannot infer these and neither can the matcher.** Dependency is *intent*; co-occurrence
is not dependency. Two entries can mention each other constantly and depend on neither, and the
dependency that matters most is usually the one not yet written about at all.

**Justified against "more automation is better"** on the rule's own terms: automation wins when a
generator can *know* the fact. Here it cannot — and this is the one relation D-1 named as the reason
for having IDs at all (*"IDs allow tracking items and dependencies"*). It is also one line, written
once, by whoever creates the entry, in the file they are already editing. The gate covers it:
`[[ID]]` inside a `**Depends on:**` line must resolve, like every other link.

---

## 5. Rot and renames — and one gate bug that must be fixed first

**The tag-hub structure is itself the rot defence, and it is free.** Documents are *never linked by
basename*. Only roadmap IDs are ever link targets. So **renaming or deleting a research note breaks
nothing**, because nothing points at it — the tag is the hub, exactly as drawn. This is the single
strongest argument for the sketch's shape over a document-to-document link mesh.

What can still rot, and how it fails loudly:

| failure | detection |
|---|---|
| `**Roadmap:** [[AA-3]]` after `AA-3.md` is deleted | consistency gate, extended to the new kinds |
| generated block edited by hand | gate regenerates and compares; **exact mismatch fails with a diff** |
| `start` without `end`, `end` without `start`, nested, or two blocks in one file | gate fails naming the file |
| a tag in a block that is not in `docs/TAGS.md` | existing vocabulary gate, extended past `*/ROADMAP/` |

**R1 — the existing consistency gate has a bug that blocks this feature, and it is live today.**
`roadmap-entry-consistency-gate.sh` computes its known-ID set **per directory**: a
`[[BL-10]]` link written from an `audio-adapter/ROADMAP/` entry is reported dangling, because
`BL-10.md` is not in that directory. It has not fired yet only because audio-adapter is the sole
converted subproject. The moment a research note links to a roadmap ID — which is this whole feature
— it fires on correct links. **Fix first: build the ID set as the union across every converted
directory.** A gate that cries wolf is a gate that gets bypassed (the parent plan's R4, verbatim).

**No `|| true`, no "nothing to check, exit 0" path, no state that can silently carry past a
malformed file.** Three separate review rounds on this feature found guards degrading quietly — an
unterminated fence swallowing a whole file, a dirty working tree turning one bad run into a
permanent silent outage. The delimiter scan is the same shape and gets the same treatment: an
unbalanced block is a hard failure, never a skip.

---

## 6. When it runs

| | |
|---|---|
| **`doc-graph-refresh.sh`** (writes) | **on demand only**, and as a step in `/graph-refresh` |
| **`doc-graph-gate.sh`** (verifies) | **pre-commit**, never writes, fails naming the refresh command |
| **`doc-tags-propose.sh`** | on demand, human in the loop |

**Nothing that writes runs in a hook.** The status-page precedent in `review.md` is exact: a
regenerator that trips its own working-tree guard turns one bad run into a permanent silent outage.
A hook that rewrites files mid-commit has the same shape.

**The ordering hazard the brief worried about does not exist here, and that is a direct consequence
of choosing the matcher over graphify.** The generator reads `docs/TAGS.md` and the documents —
never `graphify-out/`. So it is order-independent with respect to `/graph-refresh`, cannot launder
graph staleness, and is exactly reproducible, which is also what makes the verify-only gate
possible. Only the *proposal* tool reads the graph, and a stale graph there costs at most a missed
candidate the next run finds.

---

## 7. The `**Roadmap:**` line

**Subsumed by the generator.** The parent plan called for it on every research note and plan and
zero exist, which is the right outcome of a hand-written convention: it was never going to be kept.
It is now one generated line, derived from the roadmap IDs the document already names in its own
text.

**The sketch settles the harder half.** The dashed line from `AA-3` to the research document is
*implied via the tag*, not drawn directly — so the generator does **not** emit a roadmap link for
every document that merely shares a tag. That would be the fan-out the user is afraid of. The tag
carries the topical relation; `**Roadmap:**` carries only the explicit one.

---

## 8. Scale and the corpus ceiling

Measured today (`.claude/scripts/graph-corpus-files.sh | wc -l` = **198**, ceiling **200**):

| scope | units |
|---|---|
| roadmap entries, converted | 23 |
| research notes | 96 |
| acceptance docs | 32 |
| plan directories | 92 |
| **total in scope today** | **243** |
| roadmap entries if repo-wide | 211 → total ~431 |

**This feature adds zero files to the corpus.** Research and acceptance documents are already in it;
plans are already excluded; roadmap entries are already counted. The blocks add a line or two of
*words*, not files.

**The interaction, stated and not settled:** the 198/200 figure already blocks the next
subproject's roadmap conversion, and therefore blocks **Stage D**, not Stages A–C. Whether to raise
the ceiling, or to stop treating each entry file as its own corpus node, is the user's decision and
belongs to the parent plan's Stage 2, not here.

**Edge count at Stage B scope** (151 units, ~8 in-band tags): roughly 150–250 tag edges plus ~80
roadmap links. Every hub is 3–25 by construction — that is what the band is for.

---

## Implementation plan

Every stage leaves the repo working and the convention coherent.

### Stage A0 — provenance first, from citations that already exist (2026-10-07)

**Inserted ahead of Stage A, and it reorders the feature.** The user named the question the whole
Obsidian effort is actually for:

> *"The underlying question in all this obsidian work is 'how did we get here?' And 'what
> information brought us here?' The 'here' most often being a roadmap item. Similarly for
> not-yet-done items, what gets us there and based on what information."*

**Topic tags are a weak proxy for that.** `#SPU-8` says *related to*; it does not say *this recon is
why AA-3 exists*. Provenance is a typed, directional, causal relation, and tags cannot express it.

**And it is already written down, in prose, for a third of the entries.** Measured over the 22
converted entries: **7 cite a plan, research note or acceptance card; 15 cite nothing.** `AA-3` is
the rich case and every path it names is a real answer — the recon that found the cockpit args, the
probe that confirmed them, the sortie that accepted it, the plan that decided it. Lifting an
existing prose mention into a structured link **infers nothing**, which is why this goes first: it
is the highest-confidence, lowest-risk part of the feature, and it answers the question directly.

**Scope (user, 2026-10-07): the entry set is audio-adapter's 22; the document set is whatever those
entries already cite.** No sweep of other subprojects, no judgement about relevance — the entries
nominate their own evidence. This is ~8–10 external documents, and **they are mostly outside
`audio-adapter/`** (AA-3's five citations are two in `aircraft-layer/research/`, two in
`docs/acceptance/`, one plan directory). That is not a scope violation: "stay in audio-adapter" and
"how did we get here" pull against each other, because the evidence for an audio-adapter entry is
simply not stored in audio-adapter, and the entry nominating it is what keeps the set bounded.

1. **Fix R1 first** — the consistency gate's per-directory ID set. No longer theoretical: this stage
   creates exactly the cross-subproject `[[AA-3]]` links that trip it.
2. **The cited document states the relation**, not the entry — §1's rule, and it survives here.
   Backlinks give `AA-3` its reverse list for free, documents stay off the link-target side so
   renames and deletions stay free, and the entry files (the churn) are not edited at all.
3. **Typed by the citing document's kind**, since the type is what makes this answer the question:
   a research note is evidence, an acceptance card is a flight, a plan is a decision. Exact wording
   is the implementer's, inside the delimited block.
4. **Stop point, and the user asked for it explicitly** — *"Do this stage first, then let's stop and
   inspect."* Open `AA-3` in Obsidian and read its backlinks: is the provenance chain there, and does
   it answer *how did we get here*? Stage A's vocabulary work is judged on what that looks like.

**The honest limit: 15 of 22 entries have no citation at all**, so for them this stage produces
nothing and the answer is not in the documents. Those entries do name branches
(`feature/spu8-intercom`), so git history could supply a weaker, inferred answer later — that is not
this stage, and it should not be attempted until the citation-based version has been judged.

### Stage A — the vocabulary, with nothing generated
1. Fix R1 (union-of-IDs in the consistency gate). Independent of everything else here.
2. Rewrite `docs/TAGS.md`: new rule, per-tag section format, the closed-vocabulary argument kept.
3. Build `doc-tags-propose.sh`; run it; admit the first ~6–10 in-band tags with the user.
4. **Stop point:** a vocabulary that is specific enough to be navigable, and `grep -rl '#SPU-8'` as a
   trustworthy answer. No document edited. Abandonable with zero cleanup.

### Stage B — the generator and the gate, over 151 units
1. `doc-graph-refresh.sh` + `doc-graph-gate.sh`; extend the vocabulary gate past `*/ROADMAP/`.
2. Run over `*/research/`, `docs/acceptance/`, `audio-adapter/ROADMAP/`. Commit the blocks.
3. Write the `docs/DOC_CONVENTIONS.md` sections.
4. **Stop point and the real decision point:** open Obsidian, click `#SPU-8`, and see whether the
   sketch is actually there. Stages C and D are judged on what that looks like, not on this plan.

### Stage C — typed edges
1. Convention in `docs/DOC_CONVENTIONS.md`; gate coverage; author the handful that matter now.
2. **Stop point:** directional dependencies exist where they are known.

### Stage D — plans, and repo-wide roadmap conversion (deferred)
Blocked on the corpus-ceiling decision and on Stage B's observed value. 92 plan units, mostly
historical and already reachable from the roadmap — the weakest value in the feature.

---

## Risks & unknowns

- **The 3–25 band is a judgement from one measurement set.** It will need adjusting. Cheap and loud:
  the proposal tool reports the number, so a wrong band is visible immediately.
- **Whole-body matching produces false positives** — a document mentioning SPU-8 once gets the tag.
  Accepted deliberately (recall over precision), but it is a real cost and it grows with the corpus.
- **128 dated research and acceptance records get edited.** The block is delimited, machine-owned,
  additive and placed after the H1, so it is metadata rather than a revision — but
  `docs/PROCESS.md` forbids rewriting records of what was true then, so this needs the user's
  explicit nod (decision 3 below).
- **A second generated surface in a repo that has almost none.** After the status page, this is the
  second thing that can be stale while looking current. The verify-only pre-commit gate is the
  answer, and it only works because the generator is deterministic.
- **Front Matter Title is a single-maintainer plugin** (parent plan R7b). Unchanged by this feature:
  tags and links work in stock Obsidian; only the display degrades.
- **R9 stands.** This is documentation work while the brain layer is the named bottleneck. The
  staged shape is the only mitigation, and Stage B's stop point is a deliberate off-ramp.

---

## Second-order effect

The tag-hub shape means **no document in this repo is ever a link target** — only roadmap IDs are.
That makes the entire documentation tree renameable and archivable without link rot, which turns two
things the parent plan listed as expensive-later into cheap: a `plans/archive/` sweep, and the
`NOTES.md`-per-insight split it flagged as "maybe later". Against that, it commits the project to a
second generated surface and to a vocabulary whose size band has to be re-measured as the corpus
grows — in a project whose recurring failure is a convention outliving the file that records it.

---

## Decisions taken — user, 2026-10-07

All five answered. **Each is settled; do not re-open them.** The originals are kept below so the
reasoning that produced each answer stays attached to it.

| # | decision | answer |
|---|---|---|
| 1 | split `#audio` | **yes** |
| 2 | topic tags move into the generated block | **yes** (revises the parent plan) |
| 3 | generator may write into 128 dated records | **yes** |
| 4 | typed edges hand-written | **yes**, Stage C happens |
| 5 | stop after Stage B | **yes** — stop and look at the real graph |

**And one correction that outranks the sketch:** *"The drawing is example, not final truth."* So
`sketch-document-graph.jpg` is an illustration of the shape wanted, **not a specification to satisfy
literally**. Do not treat its particular tags, nodes or edges as requirements — `#audio` splitting
into `#audio-playback`/`#audio-volume` is a correction *of* the drawing, and that is allowed and
expected. The explore notes' framing of the sketch as "the specification" is superseded by this.

**Scope: audio-adapter only, again.** *"Still limit to audio adapter, I want to see it in small
scale before using the effort on whole repo."* Same reasoning as Stage 1's limited-scale test — the
22-file conversion is what surfaced the tag-regex bug and the stale corpus baseline, and 151 units
is not a small-scale test.

---

## Decisions requiring user input

**Answered above, 2026-10-07. Retained for the reasoning.**

1. **`#audio` has to be split, and it is in your sketch.** It would connect 80 documents, which is
   the hub you were worried about. Measured alternatives: `#audio-playback`, `#audio-volume`,
   `#audio-transport` — which is what the "volume" and "playback" nodes in your own drawing already
   are. Confirm, or overrule the band and accept the 80-edge hub.
2. **Topic tags move off the checkbox line into the generated block**, revising the parent plan's
   "every tag inline". Status tags do not move. Reason: a generator must not edit the one line two
   gates parse.
3. **The generator writes a block into 128 dated research and acceptance records.** Additive,
   delimited, after the H1. `docs/PROCESS.md` forbids rewriting such records, so this is yours to
   approve — the alternative is scoping Stage B to roadmap entries only, which renders about a third
   of the sketch.
4. **Typed edges are hand-written**, the one exception to *"more automation is better"*. The
   reasoning is in §4; if you would rather have no dependency arrows than a hand-written one, Stage C
   simply does not happen.
5. **Scope: Stage B's stop point.** The recommendation is to stop there and look at the real graph
   before committing to plans or to repo-wide conversion. Say if you would rather run straight
   through.
