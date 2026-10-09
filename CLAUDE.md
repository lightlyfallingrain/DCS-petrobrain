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
**Never take the list of subprojects from a list written in a file — take it from that status table
or from `git ls-files '*/pyproject.toml'`.** This is the one enumeration rule, and it governs every
section of this file rather than being restated per section. A written list goes stale silently
while reading as an instruction: three were named here long after six existed, four skills
inherited the same three and could report PASS while never looking at half the repo, and a list in
this file has now gone stale **four** times. The mechanical check costs one command and cannot.
`todo/todo.md` no longer duplicates milestone narrative; it only holds items not yet assigned to
one subproject's roadmap (cross-cutting backlog, session-scoped notes) and User priority tasks.
(Deliberately not restated here: two copies of the same fact drift out of sync as milestones
complete — see the roadmap files' own "Keeping this current" note for how that's enforced at merge
time.)

## Subprojects

Each major component under this repo may carry its own `<subproject>/CLAUDE.md` with stack/testing/structure specifics that augment (and, where stated, override) this file — Claude Code loads nested `CLAUDE.md` files automatically when working inside that directory.

**The subproject list is not written here** — `git ls-files '*/CLAUDE.md'`, per the enumeration rule in "Current priority".

A few subproject-specific pointers worth having by name, because they are not derivable from a directory listing: `world-model/docs/CONVENTIONS.md` (DCS reconnaissance, provenance/confidence, cross-machine workflow, read-only DCS access), `aircraft-layer/WORKFLOW.md` (cross-machine deploy/run), and `plans/body-layer/plan.md` (the full BL milestone series, whose status lives in `body-layer/ROADMAP.md`).

**Module independence**: each subproject should be able to run on its own, with its own venv/dependencies. **body-layer ↔ world-model is the sole exception** — body-layer imports world-model's `query`/`coordinates` packages in-process (not over HTTP), a deliberate coupling because the two are treated as a pair, at least for now (see `plans/body-layer/plan.md` "Seams" and `body-layer/CLAUDE.md` "Tech stack"). Do not introduce a similar in-process cross-subproject import elsewhere without the same explicit justification — the default is HTTP/JSON across a subproject boundary (as aircraft-layer ↔ body-layer already does), not a shared import.

Each subproject keeps its **own `.venv`**, and `ruff`/`mypy`/`pytest` are generally **not on `PATH`** — resolve `<subproject>/.venv/bin/<tool>` before concluding a check cannot run. `mypy`'s config discovery is **CWD-only**: run it from inside the subproject (`cd <subproject> && .venv/bin/mypy src`), never as `mypy <subproject>/src` from the repo root, which silently drops `strict` and the subproject's `mypy_path` and reports phantom import errors.

## Agents

The agent roles are whatever `.claude/agents/` currently holds — read that directory rather than a count written here. They are the template roles (architect, implementer, reviewer, debugger, performance-reviewer, security, dod — see `AGENTS.md` for role sequences) plus this project's own `investigator`. Each role's model is declared in its own file's frontmatter, which is the only place it is true; most are `claude-sonnet-5`. **`dod` runs on sonnet, not haiku** — raised 2026-09-20 (user
direction) after a cheap final gate reported work as verified when it was not; `docs/AGENT_ROLES.md`
has what that cost, for anyone tempted to downgrade the last gate to save money again. For
architecturally complex or high-risk planning (coordinate system design, spatial schema, cross-theatre generalization), re-invoke architect with an explicit opus model override rather than relying on its sonnet default.

**`performance-reviewer` and `security` run once per whole feature, immediately before DoD** — not mid-feature, and not once per stage of a multi-stage feature. Enabled 2026-09-24 (user direction, from the 2026-09-22→2026-09-25 retro), replacing the previous blanket skip.

Scoping, in the user's own terms: this is for now a single-user, LAN-only project under active development, so this is one pass per feature rather than "both roles fully on everywhere" — deeper security and performance effort comes once the important milestones (brain and memory) are complete.

**A standing exemption needs a stated condition for ending, or it outlives its premise silently.** That is the transferable lesson from how this one was arrived at — the previous blanket skip was accurate when written, carried no lapse condition, and stayed in force unexamined after the project grew the surfaces it had assumed away (`docs/AGENT_ROLES.md`). Apply it to any exemption, not just these two.

**`investigator`** is this project's recon role, needed because much of the World Model Builder depends on unverified DCS internals (file formats, coordinate systems, scripting-API availability). It sits *before* Architect's plan is finalized, not in the Implementer→Reviewer→DoD chain: **Architect invokes it proactively whenever a plan would otherwise depend on an unverified DCS-internals claim** (see `.claude/agents/architect.md` step 2) — this is not a user-invocation-only role. It writes dated findings to the `research/` directory of whichever module the finding is about (e.g. `world-model/research/`, `aircraft-layer/research/`), per the format in `docs/concept/WORLD_MODEL_BUILDER.md`, and does not write pipeline code.

## Session Start

1. Read root `ROADMAP.md` for the cross-subproject picture, then the `ROADMAP.md` of whichever
   subproject looks most active (its Status table row is the pointer).
2. Read `todo/todo/todo-tasks.md` for any User priority tasks, and `todo/backlog/todo-backlog.md`
   for cross-cutting/unscoped backlog items. (`todo/todo.md` and `todo/backlog.md` are now pointers
   to those; both were split into one file per item on 2026-10-09 — `docs/DOC_CONVENTIONS.md`.)
3. Identify the next actionable milestone (first non-done, non-deferred/blocked item in the
   relevant subproject's roadmap).
4. Show that milestone and its subitems to the user.
5. Ask what they want to work on.

**Before starting work on a milestone — and this is not optional after a context clear — read the
state, not only the account of it.** The roadmap says what is *next*; it does not say what is
*already underway*, because a branch that exists is not a milestone that is done and nothing writes
it down.

- **Always, and filter the scaffolding out:**

  ```sh
  git branch -v --sort=-committerdate | grep -v 'worktree-agent-' | head -20
  git worktree list
  ```

  A branch whose name matches the milestone you are about to start means the work exists. Read its
  log and diff before writing a line of your own.

  **The `grep -v` is not cosmetic.** 41 already-cherry-picked `worktree-agent-<id>` branches cannot
  be told apart from unharvested work, so they stay; without the filter an unfiltered `head -20`
  buried the only live feature branch among them. The handoff now deletes each one at harvest
  (`AGENTS.md`, rule 1), so the backlog does not grow — see `docs/AGENT_WORKTREE_PROTOCOL.md`.
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
already exists, and occasionally finding a superseded version instead. **The triggers below are all
things that visibly happen**, because the rule's previous trigger named an internal state, nothing
could observe it failing, and it was followed zero times across eight separate passes on
2026-09-26/27.

- **Before writing a plan**, or a diagnosis, or a research note.
- **Before dispatching architect, debugger or investigator.** A `PreToolUse` hook on `Agent`
  (`.claude/scripts/graph-query-reminder.sh`) injects this at dispatch, and those three role files
  carry it as a numbered procedure step rather than a closing note.
- **When the user asks whether something exists, is documented, or was already decided.**
- **Before saying "there is no X" / "nothing covers Y" / "this has not been decided."** That
  sentence is the observable form of the old trigger — if you are about to write it, you owe a
  query first.

**A miss means "not indexed yet", never "does not exist"** — the semantic layer lags the working
tree, and `GRAPH_REPORT.md`'s mtime says by how much.

### Graph to find it, `grep` to prove it is gone

**User direction, 2026-10-06.** The graph goes first — that is what the section above is for. But
the sentence immediately above decides a second case against it, and the distinction is the verb:

| question | instrument | why |
|---|---|---|
| *"Where is this discussed? Was this decided?"* | **graph first**, then read the sources | discovery; a hit is authoritative and a miss costs one `grep` |
| *"Does anywhere **still** assert X?"* | **`grep`**, authoritatively | completeness; needs a trustworthy **negative**, which the graph explicitly does not give |

A correction sweep is the second kind, so *"the graph found no remaining mention"* is not evidence
the claim is gone. **`.claude/agent-memory/` is deliberately outside the corpus**, so a memory sweep
is `grep`-only by construction — do not add memory to the corpus to fix that.

```sh
.claude/scripts/gq.sh "<question>"   # query, then list the sources to read
graphify path "<node A>" "<node B>"  # shortest path between two concepts
graphify explain "<node>"            # plain-language explanation
```

**Use `gq.sh`, not `graphify query` directly — a PreToolUse hook enforces this.** The graph says
*where* to look, not what the text says: edge annotations quote fragments, and a fragment can lose
its tense. The wrapper assembles the sources and re-renders annotations as `fragment@path` so they
read as coordinates rather than claims.

Install the hooks once per clone: `.claude/scripts/install-git-hooks.sh`. They keep the graph's
structural spine current per commit (AST over changed `.py`, ~1.5s) and record that a semantic
rebuild is owed when docs change. **Bring the documents current, then rebuild** — a graph built from
stale documents launders the staleness rather than merely lagging it, returning the outdated claim
with a citation and a confidence score attached. The merge can sit anywhere around those two; what
must not happen is the rebuild being skipped. Rebuild with `/graph-refresh`.

Why each of those earns a rule, and what the lapses cost: `docs/PROCESS.md`, "Keeping the knowledge
graph honest".

## Verification

Run the active subproject's format/lint/type/test commands after every code change and always before a commit — see that subproject's own `CLAUDE.md` "Commands" section for the current list — every subproject has one, each equally canonical, ruff format/check + mypy --strict + pytest in each case, and the set of subprojects comes from root `ROADMAP.md`'s status table rather than from a list here. A change touching more than one subproject needs each touched subproject's own commands run, not just one. This is the same sequence `.claude/scripts/commit-quality-gate.sh` enforces mechanically per-subproject at commit time — stating it here prompts self-verification earlier, during implementation, instead of only at commit time.

## Direction before speed

**Moving in the correct direction beats moving fast.** User direction, 2026-10-05, and it is the
project's standing tiebreak whenever the two compete.

This is not a counsel of slowness. Most of what this project does is ordinary work that should be
done briskly and merged. It is a rule about *one specific moment*: when new information arrives
and the obvious next move is to act on the first reading of it.

### Flight feedback is captured, then explored, then planned — in that order

The user's own words:

> *"Often when I provide feedback or observations from flight, we jump straight into fixing them.
> That's actually not a very good strategy. Instead, write down the provided feedback so that it is
> not lost. Then use the explore skill to investigate with user what the behaviour should be."*

1. **Write it down first**, verbatim where the wording carries the reasoning, in
   `docs/acceptance/<date>-sortie-feedback.md`. The user's own words are the specification —
   paraphrasing them loses the part that decides the design.
2. **`/explore` it with them** before an Architect pass. Cannot be delegated: a subagent has no
   channel to the user. This is `AGENTS.md`'s "Explore Before Deciding" applied to the case it most
   obviously covers.
3. **Then** plan and build.

**The failure this prevents is not losing the feedback. It is acting on the first reading of it**,
which repeatedly turns out to be wrong in a way that only a conversation surfaces — the Bekaa
reversal, the water-flow analogue replacing rooms-and-doorways, *"still one clock hour at a time"*
correcting a 90° cone that was about to be built, and the direction word turning out to be per-kind
rather than universal. Every one of those arrived *after* a reading that looked obviously right,
and each would have been built wrong.

### It is enforced structurally, because remembering it does not work

Three hooks, because a rule that must be recalled at the exact moment attention is elsewhere will
keep being broken — the same reasoning `AGENTS.md` applies to the worktree rule:

| hook | when | what it does |
|---|---|---|
| `flight-feedback-gate.sh` | UserPromptSubmit | recognises feedback-shaped input, sets a marker, says capture-then-explore |
| `flight-feedback-dispatch-gate.sh` | PreToolUse on `Agent` | fires when dispatching **architect or implementer** while the marker is up — the moment the step would be skipped |
| `flight-feedback-clear.sh` | PostToolUse on `Write`/`Edit` | clears the marker when a file lands under `docs/acceptance/` |

**None of them block.** The user sets direction; a hook that refused to dispatch would be the hook
overruling them. If the feedback is unambiguous, or already explored, or they say "just fix it" —
proceed, and say that is what you are doing.

The hooks were written the same day the failure happened: five observations arrived from a sortie
and an Architect was dispatched on all five within one turn. Nothing was lost, but only because the
user separately asked for the feedback to be written down.

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
| `AA-B<n>` | `audio-adapter/ROADMAP/` (split; `audio-adapter/ROADMAP.md` is now a pointer) |
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

**A third marker, `<prefix>-W<n>`, is for work items that are neither a milestone nor a backlog
item** — numbered from 1 per subproject, independent of both other spaces. A subproject's
`ROADMAP.md` may also be split into one file per entry under `<subproject>/ROADMAP/`, with the
original left as a 4-line pointer. Full scheme, the ID-only filename, the `[[ID]]` link form and
the one-time Obsidian setup: `docs/DOC_CONVENTIONS.md`.
