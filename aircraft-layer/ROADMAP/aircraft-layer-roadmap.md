# Aircraft Layer — Roadmap

Live, LAN-reachable DCS I/O pipeline: `Export.lua` → Windows collector → LAN API, plus one narrow
write-back channel (`POST /text/push`) for in-cockpit text display. See `CLAUDE.md` for stack/API
details and `WORKFLOW.md` for the cross-machine deploy/run workflow. Full design/stage history:
`plans/aircraft-layer/plan.md`, `plans/aircraft-layer/implementation.md`.

This is the pointer's index — see `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; status lives on each entry.
Cross-subproject links resolve too, now that every subproject is split: the whole repo is one
Obsidian vault, so a wikilink here reaches `body-layer/ROADMAP/` and `todo/` entries as readily as
this directory's own.

**Status entries mint into the bare `AC-<n>` space, not `AC-W<n>`.** aircraft-layer has no
declared milestone series consuming the bare space — no `plans/*/plan.md` §6 equivalent, no
forward-numbered sequence — so per `docs/DOC_CONVENTIONS.md` its own entries take `AC-1`…`AC-8`
directly, the same rule audio-adapter's `AA-1`…`AA-5` follow. Backlog items keep `AC-B<n>` and
share this directory, distinguished only by the `-B` in their ID.

## Status

- [[AC-1]] — Core telemetry pipeline
- [[AC-2]] — `/world_objects/latest`
- [[AC-3]] — `/petrovich_indication/latest`
- [[AC-4]] — Text-overlay write channel
- [[AC-5]] — F10 command inbound channel
- [[AC-6]] — Unit-velocity channel
- [[AC-7]] — Hardening — bounded audio queue and a guarded collector `accept()`
- [[AC-8]] — DCS-driven line of sight, Stages 1-3 — **OPEN**, its own merge/flight claim disagrees
  with [[WM-W2]]; see the entry

## Backlog

Items here are `AC-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

- [[AC-B1]] — Push-to-talk channel
- [[AC-B2]] — Regenerate the command-surface reference with a raw-table parser
- [[AC-B3]] — Split the export throttle
- [[AC-B4]] — Measure `LoGetWorldObjects` FPS cost live
- [[AC-B5]] — A probe Hook left deployed taxes every sortie

## Keeping this current

Same discipline as the sibling subprojects: this index is the source of truth for this
subproject's milestone status, and a merge is not finished until it reflects what merged (see
`.claude/skills/merge/SKILL.md` and the root `ROADMAP.md`). Status lives on each entry file, not
here — update the entry, not this list, when a milestone's state changes; this file only needs a
new row when an entry is added or removed.
