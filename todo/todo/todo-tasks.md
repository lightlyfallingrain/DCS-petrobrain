# Todo — User priority tasks

**Milestone status, backlog, and deferred items live in `../../ROADMAP.md` (cross-subproject) and
each subproject's own `ROADMAP.md`** — not here. **Take the subproject list from root `ROADMAP.md`'s
status table, never from a list written in this file**: three were named here long after six
existed, which is the same enumeration defect root `CLAUDE.md` warns about and which has now
recurred four times in this repo. This file only holds User priority tasks and cross-cutting
items that don't yet belong to one subproject's roadmap. See root `ROADMAP.md`'s "Keeping this
current" note for how staleness is prevented: the `/merge` skill and the DoD agent both require
the relevant roadmap to be updated in the same push as any merge.

This is the index for `todo/todo.md`, converted to one file per entry on 2026-10-09 (the file
itself is now a pointer). Entry files are `todo/todo/<ID>.md`, with IDs in the **`X-T<n>`** space —
`T` for todo, deliberately distinct from `todo/backlog/`'s `X-B<n>`, because those are two files'
sequences and one ID space may not span two files' numbering. See `docs/DOC_CONVENTIONS.md` for
the directory layout, ID scheme and link form. The index carries links and titles only; status
lives on each entry.

**This index is `todo-tasks.md`.** It cannot be `todo.md` (that is the pointer's own basename) and
should not be `todo-todo.md` (which reads as a stutter); `todo-backlog.md` is taken by the sibling
backlog index. Obsidian resolves wikilinks by basename within one vault, so all three have to be
distinct spellings, which is the same constraint behind the convention's "never `index.md`" rule.

## User priority tasks

Prioritize any open task here over any other task in this file or roadmap files.

**The two items below are owed by the user and nothing else blocks them.** They are listed first,
and marked, because root `CLAUDE.md`'s Session Start step 2 and its Backlog Management section both
send every session to this file for User priority tasks — so the priority items have to be visible
on the index without opening anything.

- [[X-T1]] — Fly the contact/terrain sortie — **USER**
- [[X-T2]] — `/explore` the location-fragment rewrite — **USER**

Next open items, not blocked on the user: [[X-T4]] (grouping is the priority), [[X-T5]] (free text
comes back "Unable"), [[X-T23]] (no identification on a very close pass), [[X-T24]] (16 s flank
revisit), and the three in-progress crew-behaviour findings [[X-T6]], [[X-T7]], [[X-T8]].

**Questions waiting on you live in `todo/questions.md`** (new 2026-10-06) — created when you asked
for input to be queued rather than asked. Two open as of this writing, neither blocking.

### Where things stand, 2026-10-05 end of day

A long day: seven features merged, two sorties flown. Written here because a cleared session needs
the *state*, not the account of it — and because two of these are waiting on the user, not on code.

**Owed by the user, nothing else blocks them:** [[X-T1]] and [[X-T2]], above. Both were prose
bullets in this spot before the split; they are entries now, so their text lives in their own
files rather than being repeated here.

**In flight, mid-sequence:**

- **`feature/sortie-refinements`** (pushed) — items 2/3/4 of the refinements: `describe` synonym,
  group watch, `scan ahead` sweeping 11-12-1. Reviewer APPROVED. **Next: Security deep analysis,
  then DoD, then merge.** Item 1 is deliberately *not* on this branch.

**The two findings that matter most, both filed, both unstarted:**

- **[[BL-B30]]** — the poll loop runs at ~0.7 Hz against a specified 5 Hz. Largest finding of the
  2026-10-05 sortie, pre-existing, and it means every cadence constant in the belief layer was
  calibrated against a tick seven times faster than the real one.
- **[[BL-B31]]** — 77 % of admissions silently used the offline LOS fallback and nothing noticed.

**Also new today and unstarted:** [[BL-B26]] (group tick gathers member facts 3×), [[BL-B27]]
(`say again` fires on ordinary cockpit speech), [[BL-B28]] (`report right` unrecognised while
`report left` works), [[BL-B29]] (`cancel all` missing), `WM-B8` (fixture-scale fine elevation grid,
gated on nothing now that [[X-B29]] has landed).

**Process change, 2026-10-05**: flight feedback is **captured, then explored, then planned** — see
root `CLAUDE.md`'s "Direction before speed" and the three `flight-feedback-*.sh` hooks that make it
structural rather than remembered.

### Player bubble: 10 km, settled 2026-09-28

- [[X-T3]] — Player bubble: unit detection bounded to 10 km

### Sortie 2026-09-28 — user-flown, two findings

Flown on `main` with the brain wired to Ollama (the user's own `run-scripts/` edits: `--decider
ollama`, `--brain-client http`). **The confirm-band fix was not in this flight** — it is unmerged
on `fix/confirm-band-affirmatives`.

- [[X-T4]] — Grouping is the priority — every unit gets its own callout
- [[X-T5]] — Free text reaches the brain and comes back "Unable"

### Sortie 2026-09-26 — crew behaviour findings (user-flown, unfixed)

Flown on `main` after the audio-adapter hardening merge (`1a8795d`). **Passed:** scan-is-not-watch,
cancel-means-cancel, orange-means-watched. **Not testable:** free speech — the decider is still a
stub, so there is nothing that could answer; untestable before LLM wiring, not a defect.

Four findings, in the user's own words plus what each implies:

- [[X-T6]] — Crossings are announced for contacts he cannot see
- [[X-T7]] — Binoculars are barely used
- [[X-T8]] — The confirm band asks a question nothing can answer
- [[X-T9]] — "full scan" vs "scan full" — no defect

### Where the state of play lives — not here

**A dated "state of play" narrative used to sit in this spot, headed "read this first after a
context clear". It was removed 2026-09-27 because it had gone wrong in every particular**, while
still instructing a cleared session to trust it first: it named `main` at `c912478` (~30 commits
behind), called three milestones unflown and pointed at
`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md` as the outstanding card — root `ROADMAP.md`
records all three as flown and closed 2026-09-25 — and said the brain layer was "the only component
with no plan file" after `plans/brain-layer/plan.md` landed and BR-1 Stages 1–2 merged.

That is not an update that was forgotten; it is a second source of truth, which drifts by
construction. Root `ROADMAP.md`'s own "Keeping this current" note already says a disagreement
between a roadmap and this file is a bug in the update discipline, not ambiguity to guess through.
The 2026-09-10 restructure removed one of these narratives for the same reason; this was the second.

**So after a context clear, follow `CLAUDE.md`'s Session Start protocol** — the subproject
`ROADMAP.md` files for status, this file for User priority tasks, `todo/backlog.md` for
cross-cutting items, and `git branch -v --sort=-committerdate` plus `git worktree list` for what is
actually underway. Nothing in this file is a substitute for that last step.

### Done — process and workflow items

**No heading of their own in the source file**, which left them sitting under the section above
with a blank-line gap and no label; grouped here so the index is navigable. All five are `[x]`
done, dating from 2026-09-08 to 2026-09-24, and all are process or workflow work rather than
cockpit behaviour.

- [[X-T10]] — Route crew-text speech callouts to the in-game overlay
- [[X-T11]] — Create the integrity audit skill
- [[X-T12]] — Claude workflow changes — auto-advance and autonomy criteria
- [[X-T13]] — Roadmap restructure, 2026-09-10
- [[X-T14]] — Enable `performance-reviewer` and `security` in the sequence

### Model the 9K113 sight as an optic (deferred, 2026-09-20)

- [[X-T15]] — Model the 9K113 Raduga-Sh as a selectable optic

### Probe the mission-sandbox bridge (Investigator + Windows box)

- [[X-T16]] — Probe the mission-sandbox bridge

### Scan geometry: drop the invented radius (user direction, 2026-09-21)

- [[X-T17]] — Remove `F10_SCAN_RADIUS_M` and make a sector scan unbounded
- [[X-T18]] — Anchored limited scan

### Cones 2C sortie findings (flown 2026-09-21)

First flight of the o'clock scan loop. Six findings; two share a root cause.

- [[X-T19]] — Show where Petrovich is looking
- [[X-T20]] — Scan and Watch must be standing modes
- [[X-T21]] — Callouts must not be backlogged
- [[X-T22]] — Aggregate repetitive callouts
- [[X-T23]] — No identification on a very close pass
- [[X-T24]] — 16 s flank revisit

## Cross-cutting / unscoped backlog

**Moved to `todo/backlog.md` on 2026-09-27** — items keep their `X-B<n>` ids. This file stays the
source of truth for User priority tasks and session-scoped notes. The two changed on different
rhythms and shared one knowledge-graph cache entry, so each edit re-extracted the other. That
backlog is itself now split: its index is `todo/backlog/todo-backlog.md`.
