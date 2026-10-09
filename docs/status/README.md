# Status page

`petrobrain-status.html` is a **derived view** of the project's roadmaps — subsystem status, the
milestone dependency graph, open work, and whatever is currently blocked on the user's hardware.

Published as a private artifact:
**https://claude.ai/code/artifact/922779a3-b18d-46be-bb14-6706c421e9e7**

## The one rule

**This page is never a source of truth.** Every status on it is derived from the roadmap and
backlog files. If this page and a roadmap disagree, **the page is wrong** — fix the page, never the
roadmap, and never treat the page as the record of what happened.

**Take the list mechanically, not from this file**: `git ls-files '*ROADMAP.md'`. At
the time of writing that is root plus `world-model/`, `aircraft-layer/`, `body-layer/`,
`mission-interpreter/` and `audio-adapter/` — six files, and the same enumeration rule root
`CLAUDE.md` states for subprojects applies here for the same reason. Three things that list does
*not* contain, and all three have been missed before:

- **Five of those six files are four-line pointers, not roadmaps.** Only root `ROADMAP.md` still
  holds its own content; every subproject's was split into one file per entry under
  `<subproject>/ROADMAP/` on 2026-10-09, leaving a pointer carrying
  `<!-- split-roadmap: see ROADMAP/ -->`. So `git ls-files '*ROADMAP.md'` returns almost nothing
  readable, and reading its results yields a well-formed empty page.
  **Resolve each path first — `.claude/scripts/roadmap-source.sh --entries <path>`** lists the
  files that carry the items, and passes a non-pointer through unchanged.
- **`brain-layer/` has no roadmap file.** It is a real subproject with its own `pyproject.toml`,
  and its status is tracked inside `body-layer/ROADMAP/`. Looking for `brain-layer/ROADMAP.md`
  finds nothing and must not be read as "nothing to report".
- **Backlog and todo items are not in the roadmaps**, and `git ls-files '*ROADMAP.md'` does not
  name them at all. They are `body-layer/BACKLOG.md` → `body-layer/ROADMAP/` (`BL-B<n>`),
  `todo/backlog.md` → `todo/backlog/` (`X-B<n>`) and `todo/todo.md` → `todo/todo/` (`X-T<n>`, User
  priority tasks and session-scoped notes) — all three pointers too, and 104 of the page's items
  come only from them.

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

  **Line breaks in node labels are written `&lt;br/&gt;`, not `<br/>`.** The graphs sit in
  `<pre class="mermaid">`, so the browser parses a raw `<br/>` into a DOM element before Mermaid
  runs, and Mermaid reads `textContent` — which drops it and welds the two lines together
  (`"Group contactsstages 0–4a"`). Sixty labels were affected until 2026-09-25. The bug is
  invisible in the source and only appears in the rendered page.
- **Drawer detail** — the `DETAIL` object in the page's script. Each entry carries the *reasoning*
  behind an item (why a constraint exists, what an earlier pass got wrong), which is the part a
  card on a kanban board structurally cannot hold and the main reason this format was chosen.

## Deliberately absent

No dates, no assignees, no burndown. Single developer, and the useful questions here are
structural ("what gates what", "what is blocked on hardware") rather than schedule-shaped. If
dates or assignees ever become genuinely needed, GitHub Projects does those better than this page
ever will — that would be the moment to revisit, not before.
