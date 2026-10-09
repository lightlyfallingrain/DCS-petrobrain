---
name: doc-graph-tag-hub-sizing
description: Measured facts behind plans/obsidian-links-and-tags/plan-document-graph.md — graphify under-recalls ~10x for doc tagging, and tag hub size is the only working lever
metadata:
  type: project
---

**Three measurements taken 2026-10-07 while planning Stage 1b (the document graph), each of which
reversed a design assumption.** Re-measure before trusting the numbers; the method is what lasts.

**1. graphify cannot write document links — it under-recalls by ~10×.** For `SPU-8`, the live graph
(9,487 nodes, built 2026-10-05) surfaced it in **3 documents**; `grep -rl 'SPU-8'` found **31**.
Repo-wide, graphify's doc-to-doc edges are **231 distinct file pairs over 543 doc files**, median
degree 3, max 10. And `graph-corpus-files.sh` excludes `plans/*` except the one active plan, so
graphify **cannot see 92 of 243 document units at all**.

**Why: graphify is a discovery instrument, not a completeness one** — which is exactly what root
`CLAUDE.md`'s own "graph to find it, `grep` to prove it" rule already says. Applying it to the
repo's *own documentation* was the step nobody had taken. So: graphify proposes vocabulary, a
deterministic matcher writes links. A deterministic generator is also the only kind a verify-only
pre-commit gate can check by regenerating and diffing.

**2. Tag hub size is the only lever that works, and the obvious knobs make it worse.** Measured over
243 document units: `#SPU-8` 18, `#aircraft-manipulation` 22, `#coordinates` 43, `#los` 70,
`#audio` **80**, `#perception` 86, `#speech` 93, `#terrain` **146**.

- **Raising the mention threshold fails**: `#SPU-8` 18→9→3 while `#audio` only 80→46→18. It kills
  the good tag faster than the bad one.
- **Anchoring to titles/headings fails**: `#SPU-8` drops to 5 and loses `AA-3` itself, whose H1 is
  *"Slice 2 — cockpit state drives the audio"* and never says SPU-8.

**So vocabulary specificity is the knob, and it belongs in the admission rule as a measured band
(3–25 units), not a human judgement.** `docs/TAGS.md`'s old "must cross two subprojects" rule had
the wrong axis (should be two document *kinds*) and no size test at all.

**How to apply:** whenever a design proposes tagging, clustering or linking documents, *count the
hub before agreeing to it*. One 20-line script answered in minutes what three design arguments
could not. And check whether the thing you plan to generate from is even in
`graph-corpus-files.sh`'s selection — `plans/*` is not.

**3. A live gate bug that blocks the feature:** `roadmap-entry-consistency-gate.sh` builds its
known-ID set **per directory**, so a cross-subproject `[[BL-10]]` link from `audio-adapter/ROADMAP/`
reports as dangling. Dormant only because audio-adapter is the sole converted subproject. Fix to a
union across directories before anything outside `*/ROADMAP/` links to a roadmap ID.

Related: [[project_obsidian_doc_convention_verdict]], [[project_doc_corpus_silent_dropout]].
