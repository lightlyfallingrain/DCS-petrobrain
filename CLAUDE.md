@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `docs/PROCESS.md` for generic engineering heuristics/protocols (decision heuristics, implementation strategy, debugging protocol, dependency policy, autonomy, `notes/` conventions) — not repeated here. **Text cut from this file on 2026-11-14 to meet the always-loaded budget lives there verbatim**, under "Moved from `CLAUDE.md`", so a rule here that reads terse has its full account one hop away.

## Project

Petrobrain: make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems. Guiding principle: **code owns truth, models own interpretation and language** — Petrovich must never be omniscient; his knowledge is bounded by what he could actually perceive.

**Context for every reader, agents included:** Petrobrain is a hobby add-on for the DCS World flight-simulation video game. Weapons (9K113 and others), targets and attack runs named anywhere in this repo are simulated game systems; nothing here controls real hardware.

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
however well it is built. Two of this project's own corrections were exactly that — a planned
transport removed once mission frequency was considered, and an F10 contact-list menu dropped because
the player would still have to click through it. The cost of asking is one paragraph in a plan.

Three-layer architecture, each a separate component with explicit interfaces:

1. **DCS World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads, settlements, terrain, ridges/valleys), built offline from DCS-derived data + OSM/DEM augmentation. DCS geometry is always authoritative; external GIS augments, never overrides.
2. **Mission Interpreter** — understands one specific mission (`.miz` + briefing + world model + player intent) using a capable model, offline/pre-mission. Produces a structured "Mission Understanding," not prose. Must filter out mission-author-only knowledge (hidden triggers, scripted ambushes) before it reaches the crew layer.
3. **Petrobrain Runtime** — low-latency runtime crew cognition (perception, episodic/working memory, attention, dialogue) using a small/fast local model. Memory is explicit application state, never LLM chat history.

Full rationale: `docs/concept/PETROBRAIN_SYSTEM.md`. Per-layer draft designs (status: draft/provisional, revise as earlier layers mature): `docs/concept/WORLD_MODEL_BUILDER.md`, `docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Current priority

Root `ROADMAP.md` is the entry point for what's done and what's next: it gives the cross-subproject
status and links to **every** subproject's own roadmap, which is that subproject's source of truth
for milestone status, decisions, and backlog — read those, don't infer status from this file.
**Each of those is a directory, `<subproject>/ROADMAP/`, one file per entry with an index at
`<subproject>/ROADMAP/<subproject>-roadmap.md`; `<subproject>/ROADMAP.md` is a four-line pointer**
whose first line is `<!-- split-roadmap: see ROADMAP/ -->` — reading it yields no entries and
writing to it puts the content where nothing reads it. Same for `body-layer/BACKLOG.md`,
`todo/todo.md` and `todo/backlog.md`. `.claude/scripts/roadmap-source.sh <path>` resolves either
form (`--dir`, `--entries`, `--is-pointer`) and is safe to run on whatever the status table named.

**Never take the list of subprojects from a list written in a file — take it from that status table
or from `git ls-files '*/pyproject.toml'`.** This is the one enumeration rule and it governs every
section of this file. A written list goes stale silently while reading as an instruction; **a list
in this file has gone stale four times** (`docs/PROCESS.md`), and the mechanical check costs one
command and cannot.

`todo/` holds only what is not yet assigned to one subproject's roadmap — cross-cutting backlog,
session-scoped notes and User priority tasks — in `todo/todo/` and `todo/backlog/`, indexed by
`todo/todo/todo-tasks.md` and `todo/backlog/todo-backlog.md`.

## Subprojects

Each major component under this repo may carry its own `<subproject>/CLAUDE.md` with stack/testing/structure specifics that augment (and, where stated, override) this file — Claude Code loads nested `CLAUDE.md` files automatically when working inside that directory. **The subproject list is not written here** — `git ls-files '*/CLAUDE.md'`, per the enumeration rule above.

Pointers not derivable from a directory listing: `world-model/docs/CONVENTIONS.md` (DCS reconnaissance, provenance/confidence, cross-machine workflow, read-only DCS access), `aircraft-layer/WORKFLOW.md` (cross-machine deploy/run), and `plans/body-layer/plan.md` (the full BL milestone series, whose status lives in `body-layer/ROADMAP/`).

**Module independence**: each subproject runs on its own, with its own venv/dependencies. **body-layer ↔ world-model is the sole exception** — body-layer imports world-model's `query`/`coordinates` packages in-process, a deliberate coupling because the two are treated as a pair (see `plans/body-layer/plan.md` "Seams" and `body-layer/CLAUDE.md` "Tech stack"). Do not introduce a similar import elsewhere without the same explicit justification — the default across a subproject boundary is HTTP/JSON (as aircraft-layer ↔ body-layer already does).

Each subproject keeps its **own `.venv`**, and `ruff`/`mypy`/`pytest` are generally **not on `PATH`** — resolve `<subproject>/.venv/bin/<tool>` before concluding a check cannot run. `mypy`'s config discovery is **CWD-only**: run it from inside the subproject (`cd <subproject> && .venv/bin/mypy src`), never as `mypy <subproject>/src` from the repo root, which silently drops `strict` and the subproject's `mypy_path` and reports phantom import errors.

## Agents

The agent roles are whatever `.claude/agents/` currently holds — read that directory rather than a count written here: the template roles (architect, implementer, reviewer, debugger, performance-reviewer, security, dod — `AGENTS.md` has the sequences) plus this project's own `investigator`, `goal-aligner` and `plan-aligner` (`AGENTS.md`, "Roles" and "Behaviour alignment"). Each role's model is declared in its own file's frontmatter, which is the only place it is true; most are `claude-sonnet-5`. **`dod` runs on sonnet, not haiku** — raised 2026-09-20 (user direction) after a cheap final gate reported work as verified when it was not (`docs/AGENT_ROLES.md`). For architecturally complex or high-risk planning (coordinate system design, spatial schema, cross-theatre generalization), re-invoke architect with an explicit opus model override.

**`performance-reviewer` and `security` run once per *batch of stages actually executed together*, immediately before DoD** — not once per stage, and never held back waiting for stages that are blocked. Enabled 2026-09-24 (user direction, from the 2026-09-22→2026-09-25 retro) as *"once per whole feature"*, replacing a blanket skip; restated in these terms 2026-10-17 after a retro measured ~19 performance passes in ten days against a rule that said one per feature. The user's own words:

> *"When stages are being done one right after the other, like stages 1-3, then perf and sec at the
> end, after stage 3. If there's, say, stage 4 and 5 left but they wait for something, then don't
> wait for them on perf and sec. → group into a single run when doing stages in a batch."*

- Stages 1–3 built back to back → **one** performance pass and **one** security pass, after stage 3.
- Stages 4–5 blocked on a sortie, a probe or a decision → **do not wait for them.** They get their own
  passes when they are built.
- A single stage built alone is its own batch, so a one-stage feature still gets both passes.

Scoping, in the user's terms: a single-user, LAN-only project under active development, so one pass per batch rather than "both roles fully on everywhere"; deeper effort comes once brain and memory milestones are complete. **A standing exemption needs a stated condition for ending, or it outlives its premise silently** — the previous blanket skip had none and stayed in force after the project grew the surfaces it assumed away (`docs/AGENT_ROLES.md`; why the "whole feature" wording also had to go: `docs/PROCESS.md`).

**`investigator`** is this project's recon role for unverified DCS internals; Architect invokes it proactively (`.claude/agents/architect.md` step 3), it writes dated findings to the relevant module's `research/`, and it never writes pipeline code.

## Session Start

`.claude/scripts/session-start.sh` injects the five-step protocol on every prompt (roadmap → todo →
next milestone → **state check** → show and ask); it is the source for the steps. What it cannot
inject is the reason the state check is not optional after a context clear:

**Read the state, not only the account of it.** The roadmap says what is *next*; it does not say
what is *already underway*, because a branch that exists is not a milestone that is done and nothing
writes it down.

```sh
git branch -v --sort=-committerdate | grep -v 'worktree-agent-' | head -20
git worktree list
```

A branch whose name matches the milestone you are about to start means the work exists; read its
log and diff before writing a line of your own. The `grep -v` matters: 41 already-harvested
`worktree-agent-<id>` branches once buried the only live feature branch. **Then read that
milestone's `plans/<feature>/` directory in full** — `plan.md` and `explore-notes.md` where one
exists — because it carries decisions with the user's own words attached, later milestones that
constrain this one, and measurements already taken.

**This exists because it was skipped, 2026-09-25**: a cleared session built BR-1 Stage 2 while
`feature/br1-stage2` already held a near-identical implementation — two ~2000-line builds of one
milestone, with the roadmap correct and the instruction unambiguous. Clearing context between tasks
is the right habit; its cost is paid at session start by reading.

## Milestone Completion

Before marking a milestone done — on its own entry file under `<subproject>/ROADMAP/`, never in
`<subproject>/ROADMAP.md`, which is a pointer — answer one question in the DoD report or the
roadmap update itself: does this milestone's completion change what the next milestone should be,
or invalidate an assumption downstream milestones rely on? One line is enough — this is the
project's inspect-and-adapt checkpoint, tied to milestone boundaries rather than a calendar.

## Knowledge graph

A queryable graph over the current-state design documentation lives in `graphify-out/` (gitignored,
built from a corpus that is **a file list, not a directory** — `.claude/scripts/graph-corpus-files.sh`
produces it; `/graph-refresh` has why a copied mirror was tried and removed, and must not return).

### When to query it — observable moments, not "before concluding"

This project's recurring failure is not missing documentation but failing to find documentation that
already exists, and occasionally finding a superseded version instead. **The triggers are things that
visibly happen**, because the rule's previous trigger named an internal state and was followed zero
times across eight passes:

- **Before writing a plan**, a diagnosis, or a research note.
- **Before dispatching architect, debugger or investigator** — a `PreToolUse` hook on `Agent`
  (`graph-query-reminder.sh`) injects this at dispatch, and those role files carry it as a step.
- **When the user asks whether something exists, is documented, or was already decided.**
- **Before saying "there is no X" / "nothing covers Y" / "this has not been decided."** If you are
  about to write that sentence, you owe a query first.

**A miss means "not indexed yet", never "does not exist"** — the semantic layer lags the working
tree, and `GRAPH_REPORT.md`'s mtime says by how much.

**At every trigger above, search agent memory too — one rule, two stores** (user direction,
2026-10-12): `python3 .claude/scripts/memory-search.py <terms>` searches every role. The graph
covers the *documented design*; `.claude/agent-memory/` holds what a role **got wrong** and is
deliberately outside the corpus, so no graph query surfaces it. The tool derives its index from each
file's `description:` on demand, so it cannot drift (why the per-directory `MEMORY.md` indexes went:
`todo/todo/X-T25.md`).

### Graph to find it, `grep` to prove it is gone

**User direction, 2026-10-06.** The verb decides the instrument:

| question | instrument | why |
|---|---|---|
| *"Where is this discussed? Was this decided?"* | **graph first**, then read the sources | discovery; a hit is authoritative and a miss costs one `grep` |
| *"Does anywhere **still** assert X?"* | **`grep`**, authoritatively | completeness; needs a trustworthy **negative**, which the graph does not give |

A correction sweep is the second kind. `.claude/agent-memory/` is outside the corpus, so a memory
sweep is `grep`-only by construction — do not add memory to the corpus to fix that.

```sh
.claude/scripts/gq.sh "<question>"   # query, then list the sources to read
graphify path "<node A>" "<node B>"  # shortest path between two concepts
graphify explain "<node>"            # plain-language explanation
```

**Use `gq.sh`, not `graphify query` directly — a PreToolUse hook enforces this.** The graph says
*where* to look, not what the text says; the wrapper lists the sources and renders annotations as
`fragment@path` so they read as coordinates rather than claims.

Install the hooks once per clone: `.claude/scripts/install-git-hooks.sh` (AST refresh per commit,
and a flag that a semantic rebuild is owed when docs change). **Bring the documents current, then
rebuild with `/graph-refresh`** — a graph built from stale documents launders the staleness,
returning the outdated claim with a citation and a confidence score attached. Lapses and their cost:
`docs/PROCESS.md`, "Keeping the knowledge graph honest".

## Verification

Run the active subproject's format/lint/type/test commands after every code change and always before a commit — see that subproject's own `CLAUDE.md` "Commands" section (every subproject has one; ruff format/check + mypy --strict + pytest in each case, and the set of subprojects comes from root `ROADMAP.md`'s status table). A change touching more than one subproject needs each touched subproject's own commands run. `.claude/scripts/commit-quality-gate.sh` enforces the same sequence at commit time; stating it here prompts self-verification earlier.

**Tests: the fast set while working, the full suite once, at DoD** (user, 2026-11-16). `.claude/scripts/fast-tests.sh <subproject>` (smoke + tests touching the changes, `slow` skipped) is what the commit gate, Implementer and Reviewer run; `--full` is DoD's, in parallel via `pytest-xdist` (in every venv). Its header has the rest. Why: the harness backgrounds any command past ~3 min, and body-layer's serial suite took ~4:45.

### Behaviour-affecting constants are tunable — standard practice

**User direction, 2026-10-15**, once `X-T26` shipped the mechanism: *"X-T26 pattern must become
standard practice from now on."* A new constant that changes **what Petrovich does** — what he sees,
says, remembers, or how long he waits — is declared through `body-layer/src/tuning.py` with `lo`/`hi`
bounds and a `#:` comment, and appears in the generated `body-layer/config/defaults.toml`. One that
does not affect behaviour (buffer size, format width, protocol constant, internal epsilon) stays an
ordinary literal. Procedure and the three measured traps: `.claude/agents/implementer.md`; the
Reviewer's half: `.claude/agents/reviewer.md`; user-facing reference: `body-layer/CLAUDE.md`
"Tuning". **Outside body-layer the loader does not exist** — declare the constant normally and note
that it would want the mechanism, rather than improvising a second one.

**The one habit worth repeating here:** check the **rendered** `defaults.toml`, not the `#:` comment
it was generated from. The generator emits only the first sentence, and a warning written second
survived three review passes by readers reading the diff.

### Behaviour as actions and params — so behaviour scripting can come later

**User direction, 2026-10-23:** *"Future code should be structured so that refactoring to decision
trees can be easy."* (Re-aimed 2026-10-24 at event-driven Lua scripting, `[[BL-B95]]`, deferred;
the shaping rule is unchanged.) New behaviour code is shaped as
**actions** (do one thing, explicit params, report running/succeeded/failed, never decide *when*),
**state params** (named read-only queries over Petrovich's belief, never DCS truth, with a declared
type, `[[BL-B94]]`), and the **"when"** (priorities, interrupts, preconditions) kept in one
place per behaviour, apart from the actions, so it can later move into a file without touching them.
Existing hard-coded behaviour stays unless a change touches it anyway.

## Do not reinvent the wheel

**User direction, 2026-10-17**, in their own words:

> *"Use existing practices, structures, solutions where applicable. Be it code, architecture or the
> system of working."*

So the first question on any piece of work is what already exists for it. All three categories count:

- **Code** — a helper, a client shape, a fixture pattern, a test harness. (Tuning constants above
  are this rule applied.)
- **Architecture** — the seams this project already has: HTTP/JSON across a subproject boundary, one
  named in-process exception, `TOOL_SET` as the brain's only route into body state, `Percept` as the
  no-omniscience boundary. A new mechanism alongside one of those needs a stated reason.
- **The system of working** — the role sequences, the worktree protocol, the `ROADMAP/` entry
  layout, the ID spaces, the skills in `.claude/skills/`. A convention gets changed rather than forked.

**Finding the existing thing is the work** — *"I did not see one"* is not evidence there is none
(the Knowledge graph triggers above are how to look). **Departing is allowed; doing it silently is
not.** If the existing thing genuinely does not fit, say which thing and what breaks, in a line, and
then build what fits — the body-layer ↔ world-model import carries its justification everywhere it
is mentioned, and that line is what separates a deliberate exception from a second way nobody decided on.

## Direction before speed

**Moving in the correct direction beats moving fast.** User direction, 2026-10-05, and the project's
standing tiebreak whenever the two compete. Not a counsel of slowness: it is a rule about *one
moment* — when new information arrives and the obvious next move is to act on the first reading of it.

### Flight feedback is captured, then explored, then planned — in that order

The user's own words:

> *"Often when I provide feedback or observations from flight, we jump straight into fixing them.
> That's actually not a very good strategy. Instead, write down the provided feedback so that it is
> not lost. Then use the explore skill to investigate with user what the behaviour should be."*

1. **Write it down first**, verbatim where the wording carries the reasoning, in
   `docs/acceptance/<date>-sortie-feedback.md`. The user's own words are the specification.
2. **`/explore` it with them** before an Architect pass. Cannot be delegated: a subagent has no
   channel to the user.
3. **Then** plan and build.

**The failure this prevents is acting on the first reading**, which has turned out wrong in a way
only a conversation surfaces **four times so far** — most sharply when *"still one clock hour at a
time"* corrected a 90° cone that was about to be built (the four: `docs/PROCESS.md`).

### It is enforced structurally, because remembering it does not work

| hook | when | what it does |
|---|---|---|
| `flight-feedback-gate.sh` | UserPromptSubmit | recognises feedback-shaped input, sets a marker, says capture-then-explore |
| `flight-feedback-dispatch-gate.sh` | PreToolUse on `Agent` | fires when dispatching **architect or implementer** while the marker is up |
| `flight-feedback-clear.sh` | PostToolUse on `Write`/`Edit` | clears the marker when a file lands under `docs/acceptance/` |

**None of them block.** The user sets direction; if the feedback is unambiguous, already explored,
or they say "just fix it" — proceed, and say that is what you are doing.

## Talking to the user

The user is the **product owner**, not the orchestrator. Write for someone who sets direction and
flies the aircraft, not for someone tracking the build.

**Default to a short answer.** Lead with the thing they have to act on. Surface, in roughly this order:

- **Decisions needed** — a real fork, with a recommendation.
- **Findings that change direction** — a measurement that contradicts the model, a defect with
  consequences, something that invalidates an earlier assumption.
- **What they must do** — fly it, run it on Windows, check a branch. Name the branch.
- **Status, in one line** — done / in review / blocked on X.

**Show the reasoning — compressed, not hidden.** This is the exception to brevity and it is not
optional: **five** of this project's important corrections came from the user reading *why*
something was believed and spotting the flaw — a slew limit read off the wrong instrument was one
(the five: `docs/PROCESS.md`). State **the inference and what it rests on**, in a line or two: "X,
because Y — which assumes Z" is checkable; three paragraphs deriving X are not.

**Keep internal** unless it changes their decision: how something was verified, which agent did
what, commit hashes, test counts beyond pass/fail, procedure followed. These live in commits, plans
and research notes. This is about mechanics, not reasoning — do not use it to drop the "why".
**Detail is earned, not default**; a number that changes their mind is signal, one that shows the
work is not. **Do not narrate process.** Say what came back and what it means.

**Prefer a picture where it replaces prose.** User direction, 2026-10-17:

> *"We should use visualisations. I'm a visual thinker, so graphs, diagrams, mock views of cockpit or
> map (=svg), all those help me understand and think. Visual representation can often replace lengthy
> textual representation."*

A visual **replaces** the text rather than decorating it; a diagram followed by the same prose costs
more than either alone. Reach for one whenever the subject is geometry, layout, state over time, a
pipeline, or a comparison of options:

| medium | for |
|---|---|
| **SVG** | scale geometry: cockpit layout, sightlines, angular separation, a map extract with the numbers on it |
| **Mermaid** | state machines, flow, dependency, a mechanism before and after |
| **HTML artifact** | anything worth interacting with or keeping — the status page and the test cards are the precedent |
| inline ASCII | a quick table only; not a substitute for a drawing |

**Rough and early beats polished and late**: something concrete is what cues recall, and several of
this project's largest corrections arrived from the user reading a mock rather than answering a
question. There is no image-generation model here, so "visual" means SVG, Canvas, HTML or Mermaid.

**Still say the uncomfortable thing.** A real risk, a wrong earlier claim, or a disagreement with a
request gets said plainly — in a sentence, not a section.

## Workflow

- One feature at a time. Commit in small logical steps.
- **Always create a feature branch before any implementation**, kebab-case after the feature
  (`feature/hyg-data-pipeline`, `fix/floating-origin-precision`), **from local `main`, as a
  worktree**: `git worktree add -b <branch> ../<repo>-<short-name> main`. Never implement directly
  on `main`; never branch from `origin/main`. A `PreToolUse` hook refuses `git checkout -b` while
  the root is parked off `main` and names the worktree form.
- **A feature branch merges automatically when DoD passes** — no separate approval, and live
  acceptance does not gate it. User direction, 2026-10-26: *"I notice I test features in batches.
  Change so that when DoD passes, feature branch is merged automatically. I'm the only user and only
  dev, so merging features I have not tested is acceptable for now."* The main loop runs `/merge`
  right after the DoD report says PASSED; untested live behaviour is carried as `#needs-flight` on
  the entry and in the test card, which names `main` as the branch to fly. **Still stop and ask** if
  the root is dirty (`AGENTS.md` rule 3), if the merge conflicts in a way that is not clear-cut, or if
  DoD did not pass. Housekeeping branches (docs currency, retro and audit changes, skill/hook edits)
  also merge without asking (user direction, 2026-11-13). **Lapses when there is a second user or
  developer.**
- **Testing aids take the light path.** User direction, 2026-10-30, after a ~20-line debug flag
  came out as ~1000 lines of plans, reviews and reports: *"That seems rather heavy and time consuming
  for something that is essentially just a helper tool to debug a problem."* A **testing aid** is
  anything that does not change what Petrovich does in normal flight: a debug or calibration flag, a
  probe script, a logging tweak, a test card, a log-analysis script. The main loop does it itself in
  its own worktree: write it, run the touched subproject's checks, one commit, merge on the user's
  word. **No subagents, no `plans/` directory, no reports, no notes harvest, no agent-memory files.**
  If the aid ever becomes normal flight behaviour, it takes the full sequence then. If unsure which
  side of the line a change is on, say which you are assuming in one line and proceed.
- Before starting, surface any ambiguous, contradicting, or missing information and ask for clarification.
- **All work happens in a worktree — agents and the main loop alike — and the repo root belongs to
  the user** (`AGENTS.md`, "Where work happens", rule 3). Read-mostly roles always take
  `isolation: "worktree"`; a feature's own worktree is named after the feature and lives until it
  merges. The user parks the root wherever they like, usually `main` — **so naming the branch is the
  only way they learn what to test.** Name it in every test card and every acceptance request.
- **Non-code, cross-cutting updates that aren't part of the current milestone** (skill/config edits,
  backlog notes, bookkeeping) take **their own worktree on their own branch**, not a feature branch's
  commits and not `main` from the root. The user may override this for a given piece of work and has.

## Definition of Done

- Feature implemented as planned
- All checks pass (format, lint, type check, test — see Verification)
- Core logic tested, no regressions
- All Reviewer required fixes addressed
- **All new/modified files staged and committed** — run `git status` and confirm a clean working tree before declaring any task, bug, or feature complete. Stage new files immediately after creating them; never stage build artifacts, generated output, or `.gitignore`d files.

## Backlog Management

`todo/todo/` holds User priority tasks and session-scoped notes, indexed by
`todo/todo/todo-tasks.md`; `todo/backlog/` holds the cross-cutting backlog, indexed by
`todo/backlog/todo-backlog.md`. Between them they are the source of truth; `todo/todo.md` and
`todo/backlog.md` are four-line pointers. States: `[ ]` open · `[~]` in progress · `[x]` done ·
`[?]` decision needed · `[>]` deferred.

- Read before starting work; prefer the User priority tasks, which the index lists first
- Do not start `[?]` or `[>]` tasks without instruction
- Update state as work progresses; do not delete tasks; do not exceed task scope

### Backlog items carry IDs, like milestones do

**Every item in a Backlog section has a stable ID** (user direction, 2026-09-27): `<prefix>-B<n>`,
where the prefix is the subproject's own and `B` distinguishes a backlog item from a milestone —
`BL-4` is a body-layer milestone, `BL-B4` a body-layer backlog item; `<prefix>-W<n>` is for work
items that are neither. Each space is a split directory, one file per item, and that directory is
the only place an ID exists.

**Mint with the script. Do not read a number off a document, do not count items, and do not
hand-roll the command** — both hand-rolled forms have been got wrong silently, and the script's
header carries the account:

```sh
.claude/scripts/mint-id.sh BL-B      # next unused ID, and the file path to write
.claude/scripts/mint-id.sh --list    # every prefix in use, its highest number, and its directory
```

`docs/DOC_CONVENTIONS.md` has the full scheme, the ID-only filename and the `[[ID]]` link form.
**Numbers are never reused and never renumbered**, including for done or rejected items — an ID
that silently comes to mean a different item is worse than no ID. An item moving between spaces
takes a **new** ID in its destination, with the old entry saying where it went.
