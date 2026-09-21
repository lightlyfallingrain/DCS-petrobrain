# Status page

`petrobrain-status.html` is a **derived view** of the project's roadmaps — subsystem status, the
milestone dependency graph, open work, and whatever is currently blocked on the user's hardware.

Published as a private artifact:
**https://claude.ai/code/artifact/922779a3-b18d-46be-bb14-6706c421e9e7**

## The one rule

**This page is never a source of truth.** Every status on it is derived from the `ROADMAP.md`
files (root, `world-model/`, `aircraft-layer/`, `body-layer/`, `mission-interpreter/`,
`audio-adapter/`) plus `todo/todo.md`. If this page and a roadmap disagree, **the page is wrong** —
fix the page, never the roadmap, and never treat the page as the record of what happened.

This is the same discipline the roadmaps already apply to each other (root `ROADMAP.md`: a
disagreement between roadmap files is "a bug in the update discipline, not ambiguity to guess
through"). A second source of truth is exactly what adopting a tracker like GitHub Projects would
have created, and it is the reason this is a rendered view instead.

## Keeping it current

Regenerate when a merge changes milestone status — the same moment the merge discipline already
requires a roadmap update (`.claude/skills/merge/SKILL.md` step 6). Updating this page is *optional* in a
way the roadmap update is not: a stale page is a cosmetic problem, a stale roadmap is a correctness
one. Do not let this file's existence add friction to merging.

To update: edit `petrobrain-status.html`, then republish it to the **same URL** (pass that URL as
`url` when publishing from a session that did not originally create it, or it forks into a
separate artifact).

## What lives where

- **Status, counts, next actions** — read from the roadmap files' checkbox states and prose.
- **The dependency graph** — a Mermaid `flowchart` block inside the page. Mermaid renders natively
  both in artifacts and in GitHub-flavoured markdown, so that block can be lifted into a committed
  `STATUS.md` unchanged if a zero-tooling in-repo version is ever wanted.
- **Drawer detail** — the `DETAIL` object in the page's script. Each entry carries the *reasoning*
  behind an item (why a constraint exists, what an earlier pass got wrong), which is the part a
  card on a kanban board structurally cannot hold and the main reason this format was chosen.

## Deliberately absent

No dates, no assignees, no burndown. Single developer, and the useful questions here are
structural ("what gates what", "what is blocked on hardware") rather than schedule-shaped. If
dates or assignees ever become genuinely needed, GitHub Projects does those better than this page
ever will — that would be the moment to revisit, not before.
