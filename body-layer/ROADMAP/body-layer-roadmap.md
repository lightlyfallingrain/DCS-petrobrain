# Body Layer — Roadmap

Petrovich's belief-state process: contacts, attention, perception ingestion, the brain-facing API.
Full architecture/design (scope boundaries, tool-set design, data model, open questions, decisions):
`plans/body-layer/plan.md` — that doc's §6 "Milestones (BL-x)" describes what each milestone below
*is*; this file tracks what's actually *done*. PB-x in the descriptions below cross-references
`docs/concept/PETROBRAIN_RUNTIME.md`'s runtime milestone numbering — BL-x is the body-owned slice
of it. Update this index (not `../todo/todo.md`) whenever a body-layer branch merges — see
`../.claude/skills/merge/SKILL.md`.

This is the pointer's index — see `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; status lives on each entry.

**`BR-1`/`BR-2` live in this directory too** (`[[BR-1.1]]`, `[[BR-1.2]]`), not in a
`brain-layer/ROADMAP.md`, because brain-layer has no roadmap of its own yet — root `ROADMAP.md`'s
status table already documents this arrangement; `ls */ROADMAP/` showing five subprojects plus
this one extra pair is the visible consequence, not an oversight.

## Live acceptance

A merged, correct change with no in-cockpit observable and no dedicated sortie yet carries
`#needs-flight` on its entry, rather than living in a hand-kept prose list (the mechanical
replacement this split exists to deliver — `plans/obsidian-links-and-tags/plan.md`, "Trustworthy
grep negatives over tags"). Find the current set with:

```sh
grep -rl '#needs-flight' body-layer/ROADMAP/ todo/backlog/ world-model/ROADMAP.md aircraft-layer/ROADMAP.md
```

Two items from the former debt list point outside this subproject entirely and were never
body-layer's own entries — kept here as plain pointers so a reader of this subproject's debt
history doesn't lose them:

- **`feature/dcs-driven-los`** (`X-B29`/`X-B30`) touches this subproject's gate 4
  (`perception/visibility.py`, `perception/naked_eye_source.py`, `belief/contacts.py`'s engagement
  term), merged 2026-10-05, not yet flown — but its own roadmap entry and acceptance card live in
  `world-model/ROADMAP.md`'s live-acceptance debt list (world-model is not yet split, so this stays
  plain prose rather than a wikilink); the owning backlog item is `X-B29` in `todo/backlog.md`.
- **`feature/spu8-intercom`** (audio-adapter Slice 2) — CLEARED 2026-10-05, flown and accepted
  (user: *"SPU-8 feature works, tested and accepted."*). Its roadmap entry is audio-adapter's
  [[AA-3]], not a body-layer entry; gates Petrovich's capture/playback on the cockpit's real SPU-8
  switches.

## Status

Group contact/perception/belief core:

- [[BL-0]] — Harness and replay
- [[BL-1]] — Observation ingestion (≈ PB-1)
- [[BL-W14]] — PB-1.5 — Naked-eye visual detection channel
- [[BL-2]] — Contact memory and association (= PB-2)
- [[BL-2.5]] — In-cockpit text mirror
- [[BL-2.6]] — Classification refinement
- [[BL-W15]] — Object-permanence continuity
- [[BL-3]] — World enrichment (= PB-3)
- [[BL-W16]] — Overlay clock/range summary
- [[BL-4]] — Attention and events (= PB-4)
- [[BL-5]] — Deterministic tool API (= PB-5)
- [[BL-W17]] — Scope-channel type-namespace mismatch, re-verified
- [[BL-W18]] — Deterministic mock-flight test fixture
- [[BL-5a]] — Text-mode crew interaction
- [[BL-6]] — Commands and inspect-and-adapt
- [[BL-W19]] — BL-7's phase data is unreachable in a sortie
- [[BL-7]] — Mission phase and relevance (≈ PB-9's deterministic half)
- [[BL-W20]] — Vision range calibration
- [[BL-W21]] — Group contacts: cardinality and composition as refinable beliefs
- [[BL-8]] — Memory layer interfaces

Detection cones, perception calibration and the sortie-driven fixes that followed:

- [[BL-W22]] — Cones slice 2C — the o'clock scan loop
- [[BL-W23]] — Cones slice 2B — gaze as a filter
- [[BL-W24]] — Cones slice 2A + 2A.5
- [[BL-W25]] — Aspect-aware object profiles
- [[BL-9]] — Debug visualization
- [[BL-10]] — Audio transport wiring (= PB-7 + PB-8, body's half only)
- [[BL-W26]] — Cockpit visibility limits for the naked-eye channel
- [[BL-W27]] — Group detectability — resolution vs. salience
- [[BL-W28]] — Five-fix sortie
- [[BL-W29]] — Internal identifiers were being read aloud
- [[BL-W30]] — Radio brevity, and cancel became three commands
- [[BL-W31]] — Repetition is better but not gone
- [[BL-W11]] — F10 command vocabulary
- [[BL-W3]] — Sortie refinements (2026-10-05 debrief, items 2/3/4)
- [[BL-W4]] — Terrain callout, Stages 3-4-5
- [[BL-W5]] — Confirm-band affirmatives
- [[BL-W6]] — Sortie 2026-09-26 fixes (Fix A/B1/B2/C)

Position belief, voice, watch/report and the brain seam:

- [[BL-W32]] — Precise position belief — Stages 1 through 5
- [[BL-W33]] — Binocular optic — Stages 1 through 3b
- [[BL-W34]] — Voice command completeness — Stages 1 through 5
- [[BL-W35]] — Watch reporting — Stages 1 through 5
- [[BL-W8]] — Position-belief-runaway fix
- [[BL-W7]] — Binocular optic, voice command completeness, and precise position belief — sortie closure
- [[BR-1.1]] — Brain layer, Stage 1 — first working slice
- [[BR-1.2]] — Brain layer, Stage 2 — OllamaDecider
- [[BL-W9]] — 2026-09-25 crew-behaviour sortie card
- [[BL-W10]] — Two items waiting on the user's own machines

Group model, contact-report flood and the tick-cost/LOS workstream:

- [[BL-W36]] — Group reporting — the disclosure ladder
- [[BL-W12]] — Group cohesion redesign
- [[BL-W37]] — Player bubble — 10 km computation-scope limit
- `BL-B23` — `ContactStore` never pruned — a backlog item, so it is linked from
  `body-layer-backlog.md` rather than from here (an entry belongs to exactly one index); named in
  plain prose at its place in this sequence because it is part of this workstream's story
- [[BL-W13]] — `silence` command
- [[BL-W1]] — Contact-report flood (merge-echo callout suppression)
- [[BL-W2]] — Redundant group disclosure
- [[BL-11]] — Tick cost, and making silent degradation visible

Ahead:

- [[BL-12]] — Group-level contact identity and continuity
- [[BL-13]] — The crew query path

## Backlog (body-layer)

**Split 2026-09-27 out of this roadmap, converted to per-entry files 2026-10-09** — items keep
their `BL-B<n>` ids. The entry files now sit in this same directory, distinguished only by the `-B`
in their ID, with their own index at `body-layer/ROADMAP/body-layer-backlog.md`; the per-file
knowledge-graph extraction cost that motivated the original split is what the per-entry split takes
further. `body-layer/BACKLOG.md` remains as a pointer so historical references keep resolving.

## Rejected

- [[BL-W38]] — Rejected: persistent omniscient mission-memory store

## Keeping this current

Same discipline as the sibling subprojects: this index is the source of truth for this
subproject's milestone status, and a merge is not finished until it reflects what merged (see
`.claude/skills/merge/SKILL.md` and the root `ROADMAP.md`). Status lives on each entry file, not
here — update the entry, not this list, when a milestone's state changes; this file only needs a
new row when an entry is added or removed.
