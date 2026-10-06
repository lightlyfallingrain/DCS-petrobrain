---
name: obsidian-doc-convention-verdict
description: The per-entry-roadmap/wikilink/tag conversion — REVISED 2026-10-06 to repo-wide adoption with IDs for every item; the ID-space design and the duplicate-entry finding that halved the minting job
metadata:
  type: project
---

Verdict on the `obsidian-test` spike (per-entry roadmap files, `[[wikilinks]]`, `docs/TAGS.md`).
Plan: `plans/obsidian-links-and-tags/plan.md`.

**REVISED 2026-10-06 by four user decisions.** My first pass recommended partial adoption
(audio-adapter + body-layer only) and branch-name filenames instead of minted IDs. **Both were
overridden.** The user's reasons, in his words: *"a human reader benefits from all sub-systems
following this convention and being browsable via Obsidian"* (partial adoption is not browsable —
a graph view with holes is what he rejected), and *"IDs allow tracking items and dependencies, I'd
rather use them"* with staleness accepted as grooming work. Also: the spike is *"a test — we do not
have to follow it strictly"*, and `.obsidian` gitignored in all folders.

**The lesson about my own reasoning:** I argued scope down on a token-cost measurement, when the
stated benefit was human navigation — for which *partial* coverage is close to worthless, not
proportionally valuable. A benefit that only exists when complete cannot be scoped by measuring
the per-file share of a *different* benefit. Check which benefit a cost/benefit table is actually
about before recommending a stopping point.

**The finding that made "IDs for every item" cheap instead of expensive.** 124 entries have no ID,
but they are two different things, and the measurement is what showed it:

- **~100 are real work items** in Status/Backlog sections (27 body-layer, 20 world-model, 8
  aircraft-layer, 19 audio-adapter already minted by the spike, 2 elsewhere) → mint.
- **24 are "Live acceptance debt" list entries** (18 body-layer, 7 world-model), branch-named — and
  **~6 of them are a second checkbox for a work item that already has its own Status entry.**
  `fix/contact-report-flood` is `[ ]` in the debt list and `[x]` in Status. Same for the `silence`
  command, `fix/redundant-group-disclosure`, position-belief-runaway, `feature/dcs-driven-los`,
  group-cohesion. **The debt list is a view over items, not a set of items** — so it becomes a
  `#needs-flight` tag plus a `grep`, never entry files. Minting per checkbox would have created two
  permanent IDs for one piece of work and frozen the disagreement.

**The ID-space design (the plan's load-bearing decision).** A third marker, `<prefix>-W<n>`, for
work items that are neither milestones nor backlog. Zero `-W<n>` collisions in the repo (verified).

- **Not the milestone space**, and this is the decisive argument: `BL-12` is a *live forward*
  resource and `plans/body-layer/plan.md` §6 is an external document that *defines* what each
  `BL-x` is. Minting 27 historical bug fixes into it would make §6 disagree with the roadmap.
- **Not the backlog space**: ~90% of these entries are `[x]` done; `BL-B47 — done` is false and
  breaks `grep -c 'BL-B'` as a measure of open work.
- **Where a subproject has no declared milestone series, its Status entries become that series** —
  aircraft-layer and audio-adapter have no §6 and no forward sequence, so `AC-1`…`AC-8` and the
  spike's `AA-1`…`AA-5` mint into the bare space. One rule, not a per-subproject exception list.
- Collision-proofing across sessions: spaces are per-subproject (disjoint by construction), one
  subproject per branch, **numbers assigned in document order** (so a rebase cannot renumber), next
  number *read* from `ls` not counted, and no W-number minted outside a conversion.

**Measurements worth not re-deriving** (`wc -c`/4 for tokens, `grep -cE '^[[:space:]]*- \[[ x~?>]\]'`
for entries):

- 204 entry files + 7 indexes repo-wide; 138.4k tokens across the 7 convertible files.
- **Corpus guard: 172 files today, ceiling 200, conversion takes it to ~383.** It refuses the
  rebuild loudly — by design. Do not pre-raise it.
- Session Start on body-layer: ~107k → ~23k (−78%).
- **441** historical `<sub>/(ROADMAP|BACKLOG).md` mentions (429 that morning — it grows). This is
  why the 4-line pointer file is never deleted.
- The graph **already** makes 185 nodes / 264 edges from these files; "one node per entry instead of
  one giant node" was always wrong.

**Two things to leave whole, with reasons that are not convenience:** root `ROADMAP.md` (zero
checkbox entries, 20+ consumers read its status table by name) and `todo/todo.md` (session-scoped
notes *meant to migrate out*, and root `CLAUDE.md`'s own rule says an item moving files takes a new
ID in its destination — so the ID would be born stale). Conversely `todo/backlog.md` **converts and
is the cheapest of all**: `graph-corpus-files.sh:48` is already `find todo -name '*.md'` (recursive)
and the dirty flag already matches `^todo/`, so it needs **zero** consumer changes.

**Live bug found while re-measuring, independent of this plan:** `graphify-dirty-flag.sh`'s regex is
`[^/]+/(CLAUDE|ROADMAP)\.md` — **no `BACKLOG`**. Editing `body-layer/BACKLOG.md` does not flag the
graph dirty today, although that file is in the corpus. Third instance of the
[[doc-corpus-silent-dropout]] class, in its mirror script.

**How to apply:** when a document-layout change is proposed, the cost is not the split — it is the
consumers, and the classifier is **loud vs silent failure**, not easy vs hard fix. Also: before
accepting a plan's framing of what is missing, count it. Both of this plan's shape-changing findings
(the debt-list duplication, the `BACKLOG` regex hole) came from one `grep -c` each.

See [[doc-corpus-silent-dropout]], [[verify-state-not-the-account-of-it]],
[[find-n-in-the-repo-before-accepting-n-is-more-than-we-need]].
