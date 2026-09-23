---
name: status-page
description: Regenerate and republish the derived project status page from the roadmap files
type: user-invocable
---

Regenerate `docs/status/petrobrain-status.html` from the roadmap files and republish it to its
existing artifact URL. Usage: `/status-page`.

**The page is a view, never a source of truth.** Every fact on it is derived from the `ROADMAP.md`
files (root, `world-model/`, `aircraft-layer/`, `body-layer/`, `mission-interpreter/`,
`audio-adapter/`) plus `todo/todo.md`. If the page and a roadmap disagree, **the page is wrong** —
fix the page, never the roadmap. `docs/status/README.md` states this contract; do not weaken it.

**Regenerating is optional, and must stay that way.** A stale page is cosmetic; a stale roadmap is
a correctness problem. Never let this become a step that blocks or slows a merge.

## Before touching anything

1. **Is a feature branch mid-flight, or is an agent running in the working directory?** If so, do
   this in a disposable worktree on `main` (see `merge.md`'s worktree pattern) — the status page is
   bookkeeping and must not land in a feature branch's history, and editing in a shared checkout
   races any background agent.
2. **Read the roadmaps before the HTML.** The page's job is to reflect them; reading the page first
   biases you toward patching what is already there rather than noticing what changed.

## What to read, and what each part of the page comes from

| Page element | Source |
|---|---|
| The five counters (`.count`) | Count `- [x]` / `- [~]` / `- [ ]` / `- [>]` across every roadmap. "Await hardware" is hand-identified: items explicitly blocked on the user's Windows box or a sortie. |
| Subsystem cards (`.sys`, one per subproject) | That subproject's `ROADMAP.md` — its status line, its next actionable item, and a progress fraction that is a judgement call, not a computed ratio. |
| The Mermaid dependency map (`#graph-deps`) | The gating relationships stated in the roadmaps ("gated on", "needs a sortie", "deliberately last"). Node classes are `done`/`active`/`open`/`hold`/`block`. Shows *how the project got here* — it includes done work. |
| The forward-only map (`#graph-upcoming`) | Every `- [ ]` / `- [~]` / `- [>]` across all roadmaps plus `todo/todo.md`. **Nothing done appears.** See "The forward-only map" below. |
| "Waiting on you, not on code" (`.callout`) | Items that cannot advance without the user — hardware, a sortie, or a decision. This section is the page's most useful part; keep it honest and short. |
| Open work rows (`.row`) | Milestone-level open items. Not every backlog entry — the board stays legible by staying selective. |
| Drawer detail (`const DETAIL`) | The *reasoning* in each roadmap entry: why a constraint exists, what an earlier pass got wrong. **This is the part a kanban card cannot hold and the reason this format was chosen.** Do not reduce entries to status restatements. |

Each `.sys`, `.row` and blocker `<li>` carries `data-detail="<key>"` matching a key in the `DETAIL`
object. **Adding a card without its `DETAIL` entry makes it open an empty drawer** — check both
sides when adding or removing anything.

## The forward-only map

Added 2026-09-20 on user request ("all upcoming work as a graph with dependencies"), then kept.
It answers a different question from the map above it: not *how did we get here* but *what is in
front of us, and what has to happen first*.

**Build it from the state markers**, not from prose: `- [ ]`, `- [~]` and `- [>]` across every
roadmap plus `todo/todo.md`. A done item appearing here is a bug — the whole point is that the eye
is not asked to filter.

**Group into subgraphs by chain.** Today: Perception, Speech, Reporting — chosen because they
genuinely barely touch, so the grouping carries information rather than tidying. If a future state
has different natural chains, regroup; do not preserve these three out of habit.

**Bound the node count at roughly 20.** This is the constraint that keeps it useful. The roadmaps
already hold everything; a graph that holds everything is a worse roadmap. Collapse siblings into
one node (`Stage 4 / 5 / 6` as a chain, not twelve bug rows) and let the drawer-less nodes stay
coarse.

**Dashed edges carry the soft dependencies** — "can ride along", "judge after flying", "needs many
flights". These are where the real sequencing lives and they are exactly what a list cannot say.

**Write the closing note from what the drawing revealed.** Not a summary of the graph — something
the roadmap lists do not show. The first version's note came from two things only visible once
drawn: a single sortie sitting upstream of four branches, and the reporting chain being almost
entirely gated behind terrain control that does not exist. If a regeneration reveals nothing new,
say less rather than padding.

## Rules for the content

- **Derived facts only.** If a claim is not in a roadmap, either it does not belong on the page or
  the roadmap is missing something — in which case fix the roadmap first, then regenerate.
- **Prefer the correction over the conclusion.** Where a roadmap records that an earlier pass was
  wrong, the drawer should say so. That history is why the entries are worth reading.
- **Keep it selective.** Roughly 25 cards and rows. The page's value is being legible at a glance;
  the roadmaps already hold everything.
- **Update the date** in the masthead eyebrow.

## Design constraints — do not drift from these

The page was designed once; regeneration is a content update, not a redesign.

- **Palette comes from the Mi-24P cockpit** — panel teal, instrument amber, switch-guard red — and
  is defined as tokens on `:root` with dark-mode variants. Never add a colour that is only defined
  inside a media or `[data-theme]` block. The user's own read: the cockpit palette "works reasonably
  well outside the diagrams" — so keep it for the page chrome, cards and chips.
- **Diagram nodes are the exception and use saturated fills, not the pale palette.** The first
  version tinted node fills from the page palette and the result was unreadable: `done` (#CFE6DF),
  `open` (#E3E7E4) and `hold` (#DCE3E9) differed by a few percent of lightness and almost no hue, so
  light green, grey and light blue could not be told apart (user, 2026-09-20). Mermaid nodes are
  small, adjacent and carry no other cue — a category colour there must survive being seen at
  thumbnail size next to its neighbours, which a page-chrome tint does not have to. Current
  `classDef` fills, shared by **both** graphs:

  | Class | Fill | Stroke | Text |
  |---|---|---|---|
  | `done` | `#1E7A5E` green | `#0F4436` | white |
  | `active` | `#D98E1F` amber | `#8A5810` | `#231705` |
  | `open` | `#2C6E9B` blue | `#174761` | white |
  | `hold` | `#5E6673` slate, dashed | `#3A404A` | white |
  | `block` | `#B03A2E` red | `#72211A` | white |

  Five distinct hues, all legible on either theme's ground. **Keep the two graphs' `classDef` blocks
  identical** — a class that means one thing in one map and looks different in the other is worse
  than no colour at all.
- **Typography**: Barlow Semi Condensed (display), IBM Plex Sans (body), IBM Plex Mono (data).
- **Keep `<title>Petrobrain Milestones</title>` and the 🚁 favicon stable** — users find the page by
  its tab and its gallery entry.
- Wide content scrolls inside its own container; the body never scrolls sideways.

## The architecture diagram (third graph, at the foot of the page)

Added 2026-09-24 on user request. It answers the question neither other graph does: **what are the
pieces, where does each one run, and what flows between them.** The two milestone graphs are about
*time* — how we got here, what is next. This one is about *shape*, and it is the only part of the
page that stays useful when every milestone is done.

**Derive it from the architecture that exists, not from the roadmaps.** Root `CLAUDE.md`'s
"Architecture" section and each subproject's own `CLAUDE.md` "What this is" are the sources. If the
diagram and the code disagree, the diagram is wrong — same contract as the rest of the page.

**What it must show**, because these are the facts a newcomer gets wrong:

- **Which machine each process runs on.** The Windows/Mac split is not incidental — it is why the
  aircraft layer exists as a separate subproject and why the seams are HTTP.
- **The two seam kinds, distinguished visually.** `body-layer ↔ world-model` is an **in-process
  Python import**, the sole sanctioned exception to module independence; everything else is
  **HTTP/JSON** across a subproject boundary. Drawing those the same way loses the single most
  important architectural rule in the repo.
- **Direction of flow.** DCS is read *and* written (telemetry and world objects out; text overlay,
  commands and audio in). An arrow that only points outward is wrong.
- **What is offline versus in the loop.** The Mission Interpreter runs pre-mission and produces an
  artifact; it is not a runtime participant.
- **The brain layer as absent.** It is the point of the whole project and does not exist — draw it
  as a `hold` node so its absence is visible rather than implied.

**Keep it structural.** No milestone status, no percentages, no "next" markers — those belong to
the graphs above. If a reader cannot tell this diagram from the dependency map at a glance, it has
drifted into restating them.

Same `classDef` block as the other two graphs, an `id`, and an expand button carrying
`data-graph="#<id>"` — see the lightbox note immediately below, which is exactly the trap a third
graph walks into.

## The graph lightbox

Every graph gets an expand button, and the button must carry `data-graph="#<diagram-id>"`. The
lightbox's `open()` originally hardcoded `document.querySelector(".diagram svg")` — with one graph
that worked, and with two the second button silently expanded the *first* graph. Binding is now
`document.querySelectorAll(".expand[data-graph]")`. **Adding a graph without the attribute gives it
a dead button**, so add the id and the attribute together.

## Publishing

The artifact already exists. **Republish to the same URL** rather than creating a second one:

```
https://claude.ai/code/artifact/922779a3-b18d-46be-bb14-6706c421e9e7
```

**Always pass the URL as `url`, from every session, without exception.** Artifact identity follows
the *file path*, not the page — so "republishing the same file keeps the URL" only holds while the
file stays exactly where it was. It does not survive the file moving.

This failed exactly once, and instructively: the page was first published from a session scratchpad,
then committed to `docs/status/` and republished from its new home. Same content, same title, same
session — and a **second artifact** appeared, leaving the user's existing link pointing at a stale
page. Passing `url` unconditionally costs nothing and removes the whole class of mistake; relying on
path stability means remembering a precondition that is invisible at the moment it matters.
- Keep the `description` and `favicon` unchanged; pass a short `label` describing the update.

## Automatic daily refresh

A launchd agent runs `.claude/scripts/status-page-refresh.sh` at 05:00 local, daily. The plist
template and its install/remove commands are in `.claude/scripts/com.petrobrain.status-page.plist`.

The script does nothing unless there is something to do, and logs which guard stopped it so a quiet
morning is distinguishable from a broken one: no commits in 24 hours, a dirty working tree or a
non-main branch (someone is mid-task — never run an agent in a checkout in use), or a missing
`claude` binary. Output lands in `~/Library/Logs/petrobrain-status-page.log`.

**launchd, not the cloud-routine mechanism**, for three reasons worth keeping: `StartCalendarInterval`
is local wall-clock, so 05:00 survives DST without intervention where a UTC cron would have drifted
an hour in October; a job missed while the Mac slept fires on wake; and it runs as the user, which
is what allows republishing the artifact to the existing URL at all.

Running by hand is still the normal path during a working session — the scheduled job is for days
nobody regenerates it.

## Finishing

1. Commit the regenerated `docs/status/petrobrain-status.html` on `main`, with a commit message
   saying what changed in the *project*, not that the page was regenerated.
2. If a worktree was used, remove it and prune.
3. Give the user the URL.
