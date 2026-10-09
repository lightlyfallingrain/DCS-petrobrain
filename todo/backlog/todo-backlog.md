# Cross-cutting / unscoped backlog

The index for the cross-cutting backlog — items that do not yet belong to one subproject's
roadmap. Split out of `todo/todo.md` on 2026-09-27 and converted to one file per entry on
2026-10-09. **`todo/todo.md` remains the source of truth for User priority tasks and
session-scoped notes** (itself now split, to `todo/todo/todo-tasks.md`); this list holds the
cross-cutting backlog and nothing else.

The reason for the 2026-09-27 split is the same reason this one happened, one level further
down: both files are in the knowledge-graph corpus, whose semantic extraction cache is keyed per
file on content, so editing the priority section re-extracted 21 backlog items along with it and
vice versa. The two sections change on different rhythms — the priority list most sessions, the
backlog when something is found and parked — which is exactly the case where one file costs twice.
Per-entry files take that to its conclusion: editing one item now re-extracts one item.

**This directory is `todo/backlog/`, not `todo/ROADMAP/`** — the one stated exception in
`docs/DOC_CONVENTIONS.md`'s directory layout, because there is no `todo/ROADMAP.md` for these
entries to sit beside. **And this index is `todo-backlog.md`, not `backlog.md`**: Obsidian resolves
wikilinks by basename within one vault, so an index named `backlog.md` would collide with the
`todo/backlog.md` pointer that still has to exist for historical references — the same collision
the convention's "never `index.md`" rule exists to prevent, arrived at from the other direction.

States are the same as `todo/todo.md`'s: `[ ]` open · `[~]` in progress · `[x]` done · `[?]`
decision needed · `[>]` deferred, now also carried as a `#status/*` tag on each entry's own
checkbox line (see `docs/TAGS.md`). Item ids are `X-B<n>` and are never reused or renumbered (root
`CLAUDE.md`, "Backlog Management"). A new one takes the next unused number — **read the highest
existing number rather than counting items**:

```sh
ls todo/backlog/ | grep -oE '^X-B[0-9]+' | sort -t B -k2 -n | tail -1
```

Entry files are `todo/backlog/<ID>.md`; see `docs/DOC_CONVENTIONS.md` for the ID scheme and link
form. The index carries links and titles only; status lives on each entry, so this list cannot
drift out of sync with it.

**Grouped by the "Added" headings the source file used, and in that file's own order within each
group**, because those headings carry provenance — which session or sortie produced which item —
that a flat numeric list would lose. One consequence worth naming: `X-B31` is listed under
2026-09-25 although it was filed on 2026-09-29, because the source file placed it immediately
after `X-B4`, the item it falls out of. That placement is information, so it is preserved rather
than normalised.

## Added 2026-09-26

- [[X-B1]] — Unhandled thread exception should fail the test suite
- [[X-B2]] — `CollectorServer.open()` never resets `_shutting_down`
- [[X-B3]] — A shutdown test that never calls `close()`

## Added 2026-09-25 (user)

- [[X-B4]] — Does DCS's `land.isVisible` test trees, and what does a call cost
- [[X-B31]] — Build the occluder layer: buildings from DCS, trees from OSM
- [[X-B5]] — Review this repo's Claude configuration itself
- [[X-B6]] — An outpost fragments into 18 contacts at range
- [[X-B7]] — A real-time ASCII view of what Petrovich is looking at
- [[X-B8]] — Per-module performance review
- [[X-B9]] — Per-module security review
- [[X-B10]] — End-to-end latency measurement
- [[X-B11]] — The graph was rebuilt under the old node-ID format
- [[X-B12]] — Re-enable performance-reviewer and security, and catch up
- [[X-B13]] — `console.py`'s typed `scan-area` still drives the 9K113
- [[X-B14]] — Scan commands should drive naked-eye perception
- [[X-B15]] — Ownship-relative o'clock scan tokens
- [[X-B16]] — Road junctions: pathological single-chunk stalls
- [[X-B17]] — `syria-full` pipeline logs only 6 of 8 stages
- [[X-B18]] — SRTM voids and unused staged tiles
- [[X-B19]] — Pin `CLASSIFIER_VERSION` bump discipline with a test
- [[X-B20]] — Landmark references must be LOS- and knowledge-gated
- [[X-B21]] — "Wingman brain"
- [[X-B22]] — Two red tests on `main` — an unmerged branch, not regressions
- [[X-B23]] — 41 `worktree-agent-*` branches of unknowable harvest state
- [[X-B24]] — Status page's daily launchd refresh

## Added 2026-09-28

- [[X-B25]] — Destructive tokens share the ordinary confirm window
- [[X-B26]] — Can DCS terrain elevation be read from its own files
- [[X-B27]] — Topology: body-layer and world-model stay together
- [[X-B28]] — LOS must read the probe grid; SRTM stays the floor
- [[X-B29]] — Compute line of sight in the aircraft layer, batched
- [[X-B30]] — Building occlusion is not gated on the Windows move
- [[X-B32]] — DCS's per-tree placement is behind the payload-addressing wall
- [[X-B33]] — `/invariant-check` cannot see `contextlib.suppress(...)`
- [[X-B34]] — Two agent-memory indexes have outgrown their read cap
- [[X-B35]] — Provenance path resolution is hardcoded to audio-adapter, and the gate it feeds is red

## One entry carries two checkbox blocks

**`X-B27` holds its own superseded text as a second block.** The source file had the decided item
followed by an un-IDed checkbox block introduced with *"Original item follows, kept because its
reasoning is what the decision rests on."* That block is not a separate item — it is `X-B27`'s own
earlier form, which is why the conversion minted **no** new ID for it and folded it into
`X-B27.md`, in source order, with its original `[ ]` state untouched. The split itself therefore
minted nothing, leaving the highest at `X-B34`; `X-B35` was filed afterwards, by the 2026-10-09 DoD
gate. Read the current highest with the recipe in `docs/DOC_CONVENTIONS.md` rather than from this
sentence:

```sh
ls todo/backlog/ | grep -oE '^X-B[0-9]+' | sort -V | tail -1
```
