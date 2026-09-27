@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `docs/PROCESS.md` for generic engineering heuristics/protocols (decision heuristics, implementation strategy, debugging protocol, dependency policy, autonomy, NOTES.md conventions) — not repeated here.

## Project

Petrobrain: make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems. Guiding principle: **code owns truth, models own interpretation and language** — Petrovich must never be omniscient; his knowledge is bounded by what he could actually perceive.

**Scope: single-player only.** Everything multiplayer (group/coalition scoping, server hosting, other clients) is out of scope until the user says otherwise — don't plan for it, list it as an open question, or add code paths for it. (User direction, 2026-09-13.)

### Whose job is whose — the test every plan and analysis has to pass

**Petrovich simulates the copilot** (for now), and his main responsibility is **contact detection and
identification**. The **pilot** — the player, for now — owns **flying, navigation and weapon
deployment**. Petrovich helps the pilot **evade dangerous units and align for attack runs**, and tells
the pilot about important observations so they can evade or attack as needed. **Transport operations
are out of current scope.** (User direction, 2026-09-26.)

**So when planning or analysing user input, the guiding question is: what would make sense and bring
value from the player's perspective — the pilot's — and from the crew interaction between them?** Not
what is elegant, not what the data model makes easy, not what is technically interesting. A feature
that does not help the pilot evade, attack, or understand what is out there is not earning its place,
however well it is built.

This is written down because the failure it prevents is silent and has happened: work that is
internally coherent and correct, aimed at nothing the pilot would notice or use. Two of this project's
own corrections were exactly that — a planned transport removed once mission frequency was considered,
and an F10 contact-list menu dropped because the player would still have to click through it. Both
were caught by asking this question, and the cost of asking it is one paragraph in a plan.

Three-layer architecture, each a separate component with explicit interfaces:

1. **DCS World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads, settlements, terrain, ridges/valleys), built offline from DCS-derived data + OSM/DEM augmentation. DCS geometry is always authoritative; external GIS augments, never overrides.
2. **Mission Interpreter** — understands one specific mission (`.miz` + briefing + world model + player intent) using a capable model, offline/pre-mission. Produces a structured "Mission Understanding," not prose. Must filter out mission-author-only knowledge (hidden triggers, scripted ambushes) before it reaches the crew layer.
3. **Petrobrain Runtime** — low-latency runtime crew cognition (perception, episodic/working memory, attention, dialogue) using a small/fast local model. Memory is explicit application state, never LLM chat history.

Full rationale: `docs/concept/PETROBRAIN_SYSTEM.md`. Per-layer draft designs (status: draft/provisional, revise as earlier layers mature): `docs/concept/WORLD_MODEL_BUILDER.md`, `docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Current priority

Root `ROADMAP.md` is the entry point for what's done and what's next: it gives the cross-subproject
status and links to **every** subproject's own `ROADMAP.md`, which is that subproject's source of
truth for milestone status, decisions, and backlog — read those, don't infer status from this file.
**Take the list of subprojects from that status table, never from this file**: subprojects are added
as the architecture grows (`git ls-files '*/pyproject.toml'` is the mechanical check), and a list
written here goes stale silently while reading as an instruction. That already happened — three were
named here long after six existed, and four skills inherited the same three and could report PASS
while never looking at half the repo.
`todo/todo.md` no longer duplicates milestone narrative; it only holds items not yet assigned to
one subproject's roadmap (cross-cutting backlog, session-scoped notes) and User priority tasks.
(Deliberately not restated here: two copies of the same fact drift out of sync as milestones
complete — see the roadmap files' own "Keeping this current" note for how that's enforced at merge
time.)

## Subprojects

Each major component under this repo may carry its own `<subproject>/CLAUDE.md` with stack/testing/structure specifics that augment (and, where stated, override) this file — Claude Code loads nested `CLAUDE.md` files automatically when working inside that directory. Currently:

**Module independence**: each subproject should be able to run on its own, with its own venv/dependencies. **body-layer ↔ world-model is the sole exception** — body-layer imports world-model's `query`/`coordinates` packages in-process (not over HTTP), a deliberate coupling because the two are treated as a pair, at least for now (see `plans/body-layer/plan.md` "Seams" and `body-layer/CLAUDE.md` "Tech stack"). Do not introduce a similar in-process cross-subproject import elsewhere without the same explicit justification — the default is HTTP/JSON across a subproject boundary (as aircraft-layer ↔ body-layer already does), not a shared import.
- `world-model/CLAUDE.md` (see also `world-model/docs/CONVENTIONS.md` for its working rules: DCS reconnaissance, provenance/confidence, cross-machine workflow, read-only DCS access).
- `aircraft-layer/CLAUDE.md` — live DCS I/O pipeline (Export.lua → Windows collector → LAN API). See also `aircraft-layer/WORKFLOW.md` for the cross-machine deploy/run workflow.
- `body-layer/CLAUDE.md` — Petrovich's belief-state process (contacts, attention, perception ingestion, the brain-facing API). BL-x milestone status: `body-layer/ROADMAP.md`, which is its source of truth — `plans/body-layer/plan.md` has the full milestone series.

## Agents

The agent roles are whatever `.claude/agents/` currently holds — read that directory rather than a count written here. They are the template roles (architect, implementer, reviewer, debugger, performance-reviewer, security, dod — see `AGENTS.md` for role sequences) plus this project's own `investigator`. Each role's model is declared in its own file's frontmatter, which is the only place it is true; most are `claude-sonnet-5`. **`dod` was raised from `claude-haiku-4-5-20251001` to sonnet on
2026-09-20** (user direction) after a run of errors in its acceptance cards — commands that had
never been executed, a card with no commands in it at all, and twice a fabricated example. The
cheap-final-gate saving was not worth a gate that reports work as verified when it was not; its own
role file now carries the run-it-before-you-write-it rule alongside the model change, since the
model was only half the problem. For architecturally complex or high-risk planning (coordinate system design, spatial schema, cross-theatre generalization), re-invoke architect with an explicit opus model override rather than relying on its sonnet default.

**`performance-reviewer` and `security` run once per whole feature, immediately before DoD** — not mid-feature, and not once per stage of a multi-stage feature. Enabled 2026-09-24 (user direction, from the 2026-09-22→2026-09-25 retro), replacing the previous blanket skip.

Scoping, in the user's own terms: this is for now a single-user, LAN-only project under active development, so this is one pass per feature rather than "both roles fully on everywhere" — deeper security and performance effort comes once the important milestones (brain and memory) are complete.

The previous rule ("skip both for now — an offline single-user local pipeline with no hot path and no untrusted-input surface") was written when that description was true and carried **no lapse condition**, which is the gap the retro actually found: it stayed in force unexamined after the project grew a live 5 Hz DCS I/O pipeline, a LAN HTTP surface between subprojects, and inbound speech capture. A standing exemption needs a stated condition for ending, or it outlives its premise silently.

**`investigator`** is this project's recon role, needed because much of the World Model Builder depends on unverified DCS internals (file formats, coordinate systems, scripting-API availability). It sits *before* Architect's plan is finalized, not in the Implementer→Reviewer→DoD chain: **Architect invokes it proactively whenever a plan would otherwise depend on an unverified DCS-internals claim** (see `.claude/agents/architect.md` step 2) — this is not a user-invocation-only role. It writes dated findings to the `research/` directory of whichever module the finding is about (e.g. `world-model/research/`, `aircraft-layer/research/`), per the format in `docs/concept/WORLD_MODEL_BUILDER.md`, and does not write pipeline code.

## Session Start

1. Read root `ROADMAP.md` for the cross-subproject picture, then the `ROADMAP.md` of whichever
   subproject looks most active (its Status table row is the pointer).
2. Read `todo/todo.md` for any User priority tasks, and `todo/backlog.md` for cross-cutting/unscoped
   backlog items (split 2026-09-27).
3. Identify the next actionable milestone (first non-done, non-deferred/blocked item in the
   relevant subproject's roadmap).
4. Show that milestone and its subitems to the user.
5. Ask what they want to work on.

**Before starting work on a milestone — and this is not optional after a context clear — read the
state, not only the account of it.** The roadmap says what is *next*; it does not say what is
*already underway*, because a branch that exists is not a milestone that is done and nothing writes
it down.

- **`git branch -v --sort=-committerdate | head -20` and `git worktree list`, always.** A branch
  whose name matches the milestone you are about to start means the work exists. Read its log and
  diff before writing a line of your own.
- **Read that milestone's own `plans/<feature>/` directory in full** — `plan.md`, and `explore-notes.md`
  where one exists. The plan carries decisions with the user's own words attached, later milestones
  that constrain this one, and measurements already taken. A cleared session that skips this
  re-derives, re-decides, or contradicts them.
- **Clearing context between tasks is the right habit** (it is what keeps long sessions affordable),
  and it is safe *only* because this repo records its decisions. The cost of a clear is paid at
  session start by reading, not avoided by remembering.

**This step exists because it was skipped, 2026-09-25.** A cleared session was told "continue with
brain layer work", read the roadmap, saw BR-1 Stage 2 as next, and built it — while
`feature/br1-stage2` already held a near-identical implementation from earlier the same day, and
`feature/d10-structured-candidates` held the follow-on. Two implementations of one milestone,
~2000 lines each. The roadmap was not wrong and the user's instruction was not ambiguous; the state
was simply never checked. `git branch` costs one second and would have caught it.

## Milestone Completion

Before marking a milestone done in a subproject's `ROADMAP.md` (whichever one owns it — root
`ROADMAP.md`'s status table lists them all), answer one question in the DoD report or the
roadmap update itself: does this milestone's completion change what the next milestone should be,
or invalidate an assumption downstream milestones rely on? One line is enough — this is the
project's inspect-and-adapt checkpoint, tied to milestone boundaries rather than a calendar.

## Knowledge graph

A queryable graph over the current-state design documentation lives in `graphify-out/` (gitignored,
built from a corpus that is **a file list, not a directory** — `.claude/scripts/graph-corpus-files.sh`
produces it). A copied `graphify-corpus/` mirror was tried and removed: it broke cache lookups keyed
on mirror paths, and files at the mirror root were keyed `graphify_corpus_*`, leaking a staging
directory into the graph's own vocabulary. **Do not reintroduce a mirror** — `/graph-refresh` carries
the full reasoning.

### When to query it — observable moments, not "before concluding"

This project's recurring failure is not missing documentation but failing to find documentation that
already exists, and occasionally finding a superseded version instead.

**The rule used to read "query it before concluding something is undocumented", and it was followed
zero times on 2026-09-26/27** — across two whole-subproject audits, a four-finding sortie diagnosis,
an architect pass, two review rounds, a DoD gate and a performance pass. The last real query predated
the previous rebuild. The rule was not the problem. Its **trigger** was: "before concluding" names an
internal state, so nothing can observe it failing, and a rule nobody can see being broken stays
broken. `AGENTS.md` had already reached exactly this conclusion about the worktree rule — *"a rule
that must be remembered at the exact moment attention is elsewhere will keep being broken. This one
is structural instead."*

So query it at these moments, each of which is a thing that visibly happens:

- **Before writing a plan**, or a diagnosis, or a research note.
- **Before dispatching architect, debugger or investigator.** A `PreToolUse` hook on `Agent`
  (`.claude/scripts/graph-query-reminder.sh`) injects this at dispatch, and those three role files
  carry it as a numbered procedure step rather than a closing note — it was a closing note before,
  in two of the three, and that is part of why it never fired.
- **When the user asks whether something exists, is documented, or was already decided.**
- **Before saying "there is no X" / "nothing covers Y" / "this has not been decided."** That sentence
  is the observable form of the old trigger — if you are about to write it, you owe a query first.

What went wrong concretely, so the cost is legible: a debugger dispatched onto the crossing-callout
defect re-derived a mechanism that `plans/callout-outside-gaze/debug.md` had already diagnosed *and
partly fixed*, finding it eventually by reading plans. One query would have opened with it.

**A miss means "not indexed yet", never "does not exist"** — the semantic layer lags the working
tree, and `GRAPH_REPORT.md`'s mtime says by how much.

```sh
.claude/scripts/gq.sh "<question>"   # query, then list the sources to read
graphify path "<node A>" "<node B>"  # shortest path between two concepts
graphify explain "<node>"            # plain-language explanation
```

**Use `gq.sh`, not `graphify query` directly — a PreToolUse hook enforces this.** The graph says *where* to look; it does not say what
the text says. Edge annotations quote fragments, and a fragment can lose its tense — the first build
cited "a standing no-omniscience violation" from a passage whose next sentence records the fix. The
wrapper ends every answer with the source files already assembled, so reading them is one step
rather than a decision, and re-renders annotations as `fragment@path` so they stop reading as
claims. That is the mechanism; the rule on its own was forgotten within the hour it was written.

Install the hooks once per clone: `.claude/scripts/install-git-hooks.sh`. They keep the graph's
structural spine current per commit (AST over changed `.py`, ~1.5s, captures docstrings) and record
that a semantic rebuild is owed when docs change. **The rebuild order at merge is load-bearing —
documents first, graph second, merge third** — because a graph built from stale documents launders
the staleness rather than merely lagging it. Rebuild after a merge with `/graph-refresh`. Full reasoning: `docs/PROCESS.md`, "Keeping the
knowledge graph honest".

## Verification

Run the active subproject's format/lint/type/test commands after every code change and always before a commit — see that subproject's own `CLAUDE.md` "Commands" section for the current list — every subproject has one, each equally canonical, ruff format/check + mypy --strict + pytest in each case, and the set of subprojects comes from root `ROADMAP.md`'s status table rather than from a list here. A change touching more than one subproject needs each touched subproject's own commands run, not just one. This is the same sequence `.claude/scripts/commit-quality-gate.sh` enforces mechanically per-subproject at commit time — stating it here prompts self-verification earlier, during implementation, instead of only at commit time.

## Talking to the user

The user is the **product owner**, not the orchestrator. Write for someone who sets direction and
flies the aircraft, not for someone tracking the build.

**Default to a short answer.** Lead with the thing they have to act on. Most turns need a few lines.

**Surface, in roughly this order:**
- **Decisions needed** — a real fork, with a recommendation.
- **Findings that change direction** — a measurement that contradicts the model, a defect with
  consequences, something that invalidates an earlier assumption.
- **What they must do** — fly it, run it on Windows, check a branch. Name the branch.
- **Status, in one line** — done / in review / blocked on X.

**Show the reasoning — compressed, not hidden.** This is the exception to brevity and it is not
optional. Most of this project's important corrections came from the user reading *why* something
was believed and spotting the flaw: a slew limit read off the wrong instrument, a "no velocity
anywhere" finding refuted by naming a tool that gets velocity, aspect angle mattering to
recognition, ten trucks in one glance being one perceptual event, the naked eye belonging as the
default optic. None of those could have come from a status line.

So state **the inference and what it rests on**, in a line or two — enough that a wrong premise is
visible. Drop the walkthrough, keep the load-bearing step. "X, because Y — which assumes Z" is
checkable; three paragraphs deriving X are not, and are *less* likely to be read.

**Keep internal** unless it changes their decision: how something was verified, which agent did
what, commit hashes, test counts beyond pass/fail, procedure followed, self-corrections about
process. These are recorded in commits, plans and research notes — which is where they belong.
Repeating them in chat is noise that buries the line that mattered. **This is about mechanics, not
about reasoning** — do not use it to justify dropping the "why".

**Detail is earned, not default.** Give it when the user asks, when a finding genuinely rests on
it, or when they cannot judge a recommendation without it. A number that changes their mind is
signal; a number that shows the work is not.

**Do not narrate process.** "I'll dispatch a reviewer, then DoD" tells them nothing they can use.
Say what came back and what it means.

**Still say the uncomfortable thing.** Brevity is not the same as smoothing. A real risk, a wrong
earlier claim, or a disagreement with a request gets said plainly — in a sentence, not a section.

## Workflow

- One feature at a time. Commit in small logical steps.
- **Always create and checkout a feature branch before starting any implementation task.** Name the branch after the feature using kebab-case (e.g., `feature/hyg-data-pipeline`, `fix/floating-origin-precision`). Never implement directly on `main`. **Always branch from local `main`** — checkout `main` first, then create the branch. Do not use `origin/main` as the branch point.
- Do not merge without user approval.
- Before starting, surface any ambiguous, contradicting, or missing information and ask for clarification.
- **Agents run in worktrees; the main checkout belongs to the main loop and the user.** Inverted 2026-09-21 after the same race occurred twice in one session — see `AGENTS.md`, "Where work happens". Read-mostly roles (Reviewer, DoD, Architect, Investigator) always take `isolation: "worktree"`. **The branch checked out in the main working directory is a contract with the user**: they test there, they do not use worktrees, so leave it on the branch they should test and name that branch explicitly whenever asking them to test anything.
- **Non-code, cross-cutting updates that aren't part of the current milestone** (skill/config edits, backlog notes, cross-milestone bookkeeping) still do not belong in a feature branch's commits — commit them on `main` instead. With the main checkout no longer shared with agents, that no longer needs a worktree.

## Definition of Done

- Feature implemented as planned
- All checks pass (format, lint, type check, test — see Verification)
- Core logic tested, no regressions
- All Reviewer required fixes addressed
- **All new/modified files staged and committed** — run `git status` and confirm a clean working tree before declaring any task, bug, or feature complete. Stage new files immediately after creating them; never stage build artifacts, generated output, or `.gitignore`d files.

## Backlog Management

`todo/todo.md` holds User priority tasks and session-scoped notes; `todo/backlog.md` holds the
cross-cutting backlog (split 2026-09-27 — each edit used to re-extract the other into the
knowledge graph). Between them they are the source of truth. States: `[ ]` open · `[~]` in progress · `[x]` done · `[?]` decision needed · `[>]` deferred.

- Read before starting work; prefer the User priority tasks at the top of the file
- Do not start `[?]` or `[>]` tasks without instruction
- Update state as work progresses; do not delete tasks; do not exceed task scope

### Backlog items carry IDs, like milestones do

**Every item in a Backlog section has a stable ID** (user direction, 2026-09-27), so one can be named
in conversation, a commit, or a plan without quoting its first sentence. The form is
`<prefix>-B<n>`, where the prefix is the subproject's own and `B` distinguishes a backlog item from a
milestone — `BL-4` is a body-layer milestone, `BL-B4` a body-layer backlog item.

| prefix | where |
|---|---|
| `BL-B<n>` | `body-layer/BACKLOG.md` |
| `AC-B<n>` | `aircraft-layer/ROADMAP.md` |
| `AA-B<n>` | `audio-adapter/ROADMAP.md` |
| `WM-B<n>` | `world-model/ROADMAP.md` |
| `X-B<n>` | `todo/backlog.md`, cross-cutting / unscoped |

`MI-B<n>` and `BR-B<n>` are reserved for mission-interpreter and brain-layer, neither of which has a
Backlog section yet.

**Two rules, and the second is the one that makes IDs worth having:**

- **A new item takes the next unused number in its file.** Read the highest existing one rather than
  counting items — the two differ as soon as anything is removed.
- **Numbers are never reused and never renumbered**, including for items that are `[x]` done or
  rejected. An ID that silently comes to mean a different item is worse than no ID, because a commit
  message or plan citing the old meaning now reads as evidence for the new one. Done items keep their
  IDs in place for exactly this reason.

An item that moves from a subproject's backlog to `todo/backlog.md` (or the reverse) takes a **new** ID
in its destination and the old entry says where it went — the same reason: an ID belongs to one file's
sequence, so carrying one across files would make two files' numbering collide.
