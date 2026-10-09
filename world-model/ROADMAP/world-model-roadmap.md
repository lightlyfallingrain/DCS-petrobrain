# World Model Builder — Roadmap

Decisions locked in for this phase:

- **Theatre**: Syria (first).
- **Stack**: Python 3.11+, type-hinted, `mypy --strict`. Spatial libraries TBD during Milestone 1-2.
- **Machines**: DCS on Windows, dev on Mac, manual-copy workflow (`WORKFLOW.md`).

Milestones below are from `../docs/concept/WORLD_MODEL_BUILDER.md` — status tracked here as work proceeds.

This is the pointer's index — see `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; status lives on each entry.
Cross-subproject links resolve too, now that every subproject is split: the whole repo is one
Obsidian vault, so a wikilink here reaches `body-layer/ROADMAP/` and `todo/` entries as readily as
this directory's own.

**The ID space in this directory is regular**, like every other subproject's: milestones are
`WM-M<n>` (`WM-M0.md`…`WM-M11.md`), backlog items are `WM-B<n>`, and work items that are neither —
a bug fix, a cross-subproject refactor, an optimization, the entries whose own text says *"no
M-number"* — are `WM-W<n>`. All three share this subproject's prefix.

**One asymmetry to know about when searching.** Milestones were bare `M<n>` until 2026-10-09, and
the dated record was deliberately left alone: there are 422 bare `M5`/`M7` mentions across `plans/`
and `world-model/research/` and no `WM-M5`/`WM-M7` ones. `WM-M5` *contains* `M5`, so searching the
bare form finds both the historical mentions and the live ID, while searching `WM-M5` finds only
live documents. Search the bare form when you want the history. `docs/DOC_CONVENTIONS.md` has the
full rationale.

## Live acceptance

**Live acceptance debt.** A milestone or fix can pass DoD on fixture testing alone; this list is
for the kind whose live-DCS acceptance was *deferred*, not waived, and hasn't been confirmed since.
(This used to say it mirrored a `body-layer/ROADMAP.md` section of the same name. That list no
longer exists in any file: it was dissolved into a `#needs-flight` tag on each entry, which the
recipe below finds mechanically.) Clear an entry only once a real
sortie actually exercises it, and say which one.

A merged, correct change with no dedicated sortie yet carries `#needs-flight` on its entry rather
than living in a hand-kept prose list — the mechanical replacement this split exists to deliver
(`plans/obsidian-links-and-tags/plan.md`, "Trustworthy grep negatives over tags"). Find the
current set across every converted subproject with:

```sh
grep -rl '#needs-flight' --include='*.md' */ROADMAP/ todo/backlog/ todo/todo/ \
  | grep -vE -- '-(roadmap|backlog|tasks)\.md$'
```

Identical to the spelling in `docs/TAGS.md` and `body-layer/ROADMAP/body-layer-roadmap.md` on
purpose; the `grep -v` drops index files, which match because they discuss the tag rather than
carrying it.

Those records are now five entries in their own right, each folded together with the Status or
backlog entry it was paired with where it had one, so one piece of work has one file:

- [[WM-W1]] — LOS elevation-tolerance fix (folded with its own Status entry) — **ACCEPTED
  2026-10-09**
- [[WM-W2]] — `feature/dcs-driven-los` — flown 2026-10-05; the mechanism works, its availability
  does not
- [[WM-W3]] — `fix/landform-relief-gate` — cleared by the 2026-10-04 rebuild
- [[WM-W4]] — `feature/terrain-landform-features` — confirmed by the user's full-theatre build
- [[WM-W5]] — `feature/multi-theatre-afghanistan` — Afghanistan projection live-confirmed

Two of the seven were not separate items at all: `fix/latin-place-names` and
`feature/landform-geomorphons` name their own backlog IDs in their own text, so their records are
folded into `WM-B1` and `WM-B6` below rather than minted as new entries — the one-ID-per-piece-of-
work rule `plans/obsidian-links-and-tags/plan.md` sets out.

## Status

Milestones and the un-numbered work items that sit beside them, in the source document's own
order:

- [[WM-M0]] — Repo + research notebook
- [[WM-M1]] — One coordinate
- [[WM-M2]] — Raster understanding
- [[WM-M3]] — OSM overlay
- [[WM-M4]] — DCS elevation
- [[WM-M5]] — First persistent model
- [[WM-M6]] — Terrain semantics
- [[WM-M7]] — Full theatre pipeline
- [[WM-M8]] — Incremental probe store
- [[WM-W6]] — Line-of-sight query primitive
- [[WM-M10]] — Road-junction detection
- [[WM-W7]] — Road-junction detection memory fix
- [[WM-W8]] — Road-junction progress logging
- [[WM-W9]] — HTTP API server
- [[WM-M9]] — OSM augmentation (geofabrik)
- [[WM-W10]] — OSM streaming-ingest memory fix
- [[WM-W11]] — OSM classified-feature persistent cache
- [[WM-W12]] — OSM ingest optimization + landcover split

Ahead:

- [[WM-M11]] — Provenance out of the LOS primitive, and the fixes that must ride the forced rebuild

## Backlog (open, unscheduled)

Items here are `WM-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

- [[WM-B1]] — Prefer a Latin-script place name at OSM ingest (carries its own cleared
  live-acceptance record)
- [[WM-B2]] — Power lines from DCS data
- [[WM-B3]] — Measured data-quality figures need to reach their consumers
- [[WM-B4]] — Smooth the ridge/valley polylines into curves
- [[WM-B5]] — Valley boundary extraction
- [[WM-B6]] — Ridge/valley detection rebuilt on geomorphons (carries its own cleared
  live-acceptance record)
- [[WM-B7]] — A coarse elevation grid from the ridge/valley lines — REJECTED
- [[WM-B8]] — A fixture-scale fine elevation grid for offline LOS tests
- [[WM-B9]] — `find_place_by_name` scans ~49k rows
- [[WM-B10]] — `features_in_bbox` embeds one bind parameter per candidate id
- [[WM-B11]] — `mode=ro` is bypassable two ways
- [[WM-B12]] — `?x=nan` / `?x=inf` kill the request
- [[WM-B13]] — Two documented premises are stale by an order of magnitude
- [[WM-B14]] — A region-row-less store slips past body-layer's startup guard
- [[WM-B15]] — Multi-theatre support — Afghanistan, Caucasus, Kola
- [[WM-B16]] — Incremental per-layer pipeline builds

`WM-B15` and `WM-B16` were minted by the 2026-10-09 conversion. Both were prose bullets in this
section with no checkbox and no ID, and both are distinct outstanding actions rather than
orientation prose, so each took the next unused number in the space this section's own preamble
declares. Each entry says so in its own body, including which checkbox marker the conversion
minted and why. `WM-B7` holds two checkbox blocks — the rejection and the `WM-B7 (original text)`
block the source kept beneath it — in one file, in source order, states untouched: the same ID
twice in the source is one entry, not two.

## Not doing yet

Not doing yet (see concept doc "Things Not To Do Yet"): Petrovich dialogue, speech, embeddings, screenshot interpretation, full-theatre processing, elaborate distributed architecture. Threat-level-driven contact reporting/prioritization (`../docs/concept/threat-levels.md`) is deferred further still — runtime layer, needs contact memory + attention model (PB-2/PB-4) first.

## Keeping this current

Same discipline as the sibling subprojects: this index is the source of truth for this
subproject's milestone status, and a merge is not finished until it reflects what merged (see
`.claude/skills/merge/SKILL.md` and the root `ROADMAP.md`). Status lives on each entry file, not
here — update the entry, not this list, when a milestone's state changes; this file only needs a
new row when an entry is added or removed.
