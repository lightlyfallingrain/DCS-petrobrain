---
name: status-page
description: Regenerate and republish the derived project status page from the roadmap files
type: user-invocable
---

Regenerate `docs/status/petrobrain-status.html` from the roadmap files and republish it to its
existing artifact URL. Usage: `/status-page`.

**The page is a view, never a source of truth.** Every fact on it is derived from the `ROADMAP.md`
files (root, `world-model/`, `aircraft-layer/`, `body-layer/`, `mission-interpreter/`,
`srs-adapter/`) plus `todo/todo.md`. If the page and a roadmap disagree, **the page is wrong** —
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
| The Mermaid dependency graph | The gating relationships stated in the roadmaps ("gated on", "needs a sortie", "deliberately last"). Node classes are `done`/`active`/`open`/`hold`/`block`. |
| "Waiting on you, not on code" (`.callout`) | Items that cannot advance without the user — hardware, a sortie, or a decision. This section is the page's most useful part; keep it honest and short. |
| Open work rows (`.row`) | Milestone-level open items. Not every backlog entry — the board stays legible by staying selective. |
| Drawer detail (`const DETAIL`) | The *reasoning* in each roadmap entry: why a constraint exists, what an earlier pass got wrong. **This is the part a kanban card cannot hold and the reason this format was chosen.** Do not reduce entries to status restatements. |

Each `.sys`, `.row` and blocker `<li>` carries `data-detail="<key>"` matching a key in the `DETAIL`
object. **Adding a card without its `DETAIL` entry makes it open an empty drawer** — check both
sides when adding or removing anything.

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
  inside a media or `[data-theme]` block.
- **Typography**: Barlow Semi Condensed (display), IBM Plex Sans (body), IBM Plex Mono (data).
- **Keep `<title>Petrobrain Milestones</title>` and the 🚁 favicon stable** — users find the page by
  its tab and its gallery entry.
- Wide content scrolls inside its own container; the body never scrolls sideways.

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

## Finishing

1. Commit the regenerated `docs/status/petrobrain-status.html` on `main`, with a commit message
   saying what changed in the *project*, not that the page was regenerated.
2. If a worktree was used, remove it and prune.
3. Give the user the URL.
