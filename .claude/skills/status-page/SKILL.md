---
name: status-page
description: Regenerate and republish the derived project status page from the roadmap files
type: user-invocable
---

Regenerate `docs/status/petrobrain-status.html` from the roadmap files and republish it to its
existing artifact URL. Usage: `/status-page`.

**The page is a view, never a source of truth.** Every fact on it is derived from the roadmap files
plus `todo/todo.md`. If the page and a roadmap disagree, **the page is wrong** — fix the page, never
the roadmap. `docs/status/README.md` states this contract; do not weaken it.

**Get the list of roadmaps from root `ROADMAP.md`'s status table, not from memory and not from this
file.** It names every subproject and links its roadmap, so it stays correct as subprojects are
added or retired — a hardcoded list here would silently omit a new subproject, which is exactly the
failure the page exists to prevent. A subproject with no roadmap file of its own is tracked
alongside another's; the table says which, and the page still needs a card for it.

**Regenerating is optional, and must stay that way.** A stale page is cosmetic; a stale roadmap is
a correctness problem. Never let this become a step that blocks or slows a merge.

**This file states method, never project state** (user direction, 2026-09-25). No milestone status,
no component inventory, no "X does not exist yet", no counts of subprojects or graphs — every one of
those is read from the sources at regeneration time. The reason is specific to a skill: unlike a
roadmap, nothing forces this file to be revisited when the project moves, so a fact written here
goes stale silently and is then *believed*, because it arrives as an instruction rather than as a
claim. That already happened once — this file told the regenerator to draw the brain layer as an
absent `hold` node, written when that was true, and it would have re-erased a shipped subproject at
the next run. A design rule ("five hues, one per class") is method and belongs here; "there are
three graphs" is state and does not.

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
| The five counters (`.count`) | Count `- [x]` / `- [~]` / `- [ ]` / `- [>]` across every roadmap. "Await hardware" is hand-identified: items a roadmap explicitly blocks on the user's own hardware or on a sortie. |
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

It answers a different question from the map above it: not *how did we get here* but *what is in
front of us, and what has to happen first*.

**Build it from the state markers**, not from prose: `- [ ]`, `- [~]` and `- [>]` across every
roadmap plus `todo/todo.md`. A done item appearing here is a bug — the whole point is that the eye
is not asked to filter.

**Group into subgraphs by chain.** Read the current page for the groups it last used, then ask
whether they still hold — a grouping earns its place only when the chains genuinely barely touch,
so that it carries information rather than tidying. Regroup whenever the work has moved; never
preserve a grouping out of habit.

**Bound the node count at roughly 20.** This is the constraint that keeps it useful. The roadmaps
already hold everything; a graph that holds everything is a worse roadmap. Collapse siblings into
one node (`Stage 4 / 5 / 6` as a chain, not twelve bug rows) and let the drawer-less nodes stay
coarse.

**Dashed edges carry the soft dependencies** — "can ride along", "judge after flying", "needs many
flights". These are where the real sequencing lives and they are exactly what a list cannot say.

**Write the closing note from what the drawing revealed.** Not a summary of the graph — something
the roadmap lists do not show. The shape worth writing about is structural: one item sitting
upstream of several branches, a whole chain gated behind something that does not exist yet, a group
whose membership stayed the same while its meaning changed. Those are only visible once drawn. If a
regeneration reveals nothing new, say less rather than padding.

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
  `classDef` fills, shared by **every** graph on the page:

  | Class | Fill | Stroke | Text |
  |---|---|---|---|
  | `done` | `#1E7A5E` green | `#0F4436` | white |
  | `active` | `#D98E1F` amber | `#8A5810` | `#231705` |
  | `open` | `#2C6E9B` blue | `#174761` | white |
  | `hold` | `#5E6673` slate, dashed | `#3A404A` | white |
  | `block` | `#B03A2E` red | `#72211A` | white |

  Five distinct hues, all legible on either theme's ground. **Keep every graph's `classDef` block
  identical** — a class that means one thing in one map and looks different in the other is worse
  than no colour at all.
- **Typography**: Barlow Semi Condensed (display), IBM Plex Sans (body), IBM Plex Mono (data).
- **Keep `<title>Petrobrain Milestones</title>` and the 🚁 favicon stable** — users find the page by
  its tab and its gallery entry.
- Wide content scrolls inside its own container; the body never scrolls sideways.

## The architecture diagram (at the foot of the page)

It answers the question neither other graph does: **what are the pieces, where does each one run,
and what flows between them.** The milestone graphs are about *time* — how we got here, what is
next. This one is about *shape*, and it is the only part of the page that stays useful when every
milestone is done.

**Derive it from the architecture that exists, not from the roadmaps.** Root `CLAUDE.md`'s
"Architecture" section and each subproject's own `CLAUDE.md` "What this is" are the sources. If the
diagram and the code disagree, the diagram is wrong — same contract as the rest of the page.

**The questions it must answer** — these are the things a newcomer gets wrong, and every answer is
read from the sources above, never from this file:

- **Which machine each process runs on**, and which are pinned there rather than merely deployed
  there. A machine split is never incidental: it is what forces a seam to be HTTP, and a process
  that *could* move should not be drawn as though it could not.
- **Which seams are which kind, distinguished visually.** Root `CLAUDE.md` names the default seam
  and the exceptions to it. Drawing every boundary the same way loses the single most important
  architectural rule in the repo, so read which exceptions currently stand rather than assuming
  the set is unchanged.
- **Direction of flow, including where it goes both ways.** An edge to a component that is read
  *and* written must show both; an arrow that only points outward is wrong.
- **What is offline versus in the runtime loop.** A component that produces an artifact before a
  sortie and takes no part in the loop must not be drawn as a participant in it.
- **Where a seam is deliberately asynchronous.** Where a layer hands work over and does not wait,
  the reply arrives on its own path — two edges, not one round trip. Drawing it as synchronous
  states the opposite of that layer's founding constraint, so check each seam's own design doc for
  which it is.
- **Anything that exists only as a plan.** Draw it with the `hold` class so its absence is visible
  rather than implied — and re-check each regeneration, because a component drawn as absent after
  it ships is the same error in the other direction.

**Keep it structural.** No milestone status, no percentages, no "next" markers — those belong to
the graphs above. If a reader cannot tell this diagram from the dependency map at a glance, it has
drifted into restating them.

Same `classDef` block as every other graph, an `id`, and an expand button carrying
`data-graph="#<id>"` — see the lightbox note immediately below, which is exactly the trap a third
graph walks into.

## Line breaks in Mermaid labels must be escaped — `&lt;br/&gt;`, never `<br/>`

**Found 2026-09-25 by the user, from the rendered page**, affecting every multi-line node label in
every graph at once. Each had lost its break *and* the space where the break had been, welding two
lines into one word — worst where a label ended in a date and the next line began with a digit, so
the join read as a single number.

**Why it happens:** the graphs live in `<pre class="mermaid">`, so the browser parses their contents
as HTML *before* Mermaid ever sees them. A literal `<br/>` becomes a real DOM element, and Mermaid
reads the block's `textContent` — which drops elements and leaves the surrounding words butted
together. The break is not merely lost; the two lines are welded.

**The fix, and the rule for every future label:** write the entity, `&lt;br/&gt;`. `textContent`
then yields the literal characters `<br/>`, which Mermaid's own parser turns into a line break.
This is invisible in the source diff and only shows up in the rendered page, so **check a rendered
label with a break in it** after any diagram edit — reading the HTML will not catch it.

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
