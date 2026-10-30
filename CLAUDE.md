@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `docs/PROCESS.md` for generic engineering heuristics/protocols (decision heuristics, implementation strategy, debugging protocol, dependency policy, autonomy, `notes/` conventions) — not repeated here.

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
status and links to **every** subproject's own roadmap, which is that subproject's source of
truth for milestone status, decisions, and backlog — read those, don't infer status from this file.
**Each of those is a directory, `<subproject>/ROADMAP/`, one file per entry with an index at
`<subproject>/ROADMAP/<subproject>-roadmap.md`. `<subproject>/ROADMAP.md` is a four-line pointer**
whose first line is `<!-- split-roadmap: see ROADMAP/ -->`; reading it yields no entries and
writing to it puts the content where nothing reads it.
`.claude/scripts/roadmap-source.sh <path>` resolves either form (`--dir`, `--entries`,
`--is-pointer`) and passes a non-pointer straight through, so it is safe to run on whatever the
status table named. Same for `body-layer/BACKLOG.md`, `todo/todo.md` and `todo/backlog.md`.
**Never take the list of subprojects from a list written in a file — take it from that status table
or from `git ls-files '*/pyproject.toml'`.** This is the one enumeration rule, and it governs every
section of this file rather than being restated per section. A written list goes stale silently
while reading as an instruction — four skills inherited a stale three-subproject list and could
report PASS while never looking at half the repo. **A list in this file has now gone stale four
times** (`docs/PROCESS.md`). The mechanical check costs one command and cannot.
`todo/` no longer duplicates milestone narrative; it only holds items not yet assigned to
one subproject's roadmap (cross-cutting backlog, session-scoped notes) and User priority tasks —
in `todo/todo/` and `todo/backlog/`, indexed by `todo/todo/todo-tasks.md` and
`todo/backlog/todo-backlog.md`.
(Not restated here on purpose: two copies of one fact drift. The roadmap files' own "Keeping this
current" note has how that is enforced at merge time.)

## Subprojects

Each major component under this repo may carry its own `<subproject>/CLAUDE.md` with stack/testing/structure specifics that augment (and, where stated, override) this file — Claude Code loads nested `CLAUDE.md` files automatically when working inside that directory.

**The subproject list is not written here** — `git ls-files '*/CLAUDE.md'`, per the enumeration rule in "Current priority".

A few subproject-specific pointers worth having by name, because they are not derivable from a directory listing: `world-model/docs/CONVENTIONS.md` (DCS reconnaissance, provenance/confidence, cross-machine workflow, read-only DCS access), `aircraft-layer/WORKFLOW.md` (cross-machine deploy/run), and `plans/body-layer/plan.md` (the full BL milestone series, whose status lives in `body-layer/ROADMAP/`).

**Module independence**: each subproject should be able to run on its own, with its own venv/dependencies. **body-layer ↔ world-model is the sole exception** — body-layer imports world-model's `query`/`coordinates` packages in-process (not over HTTP), a deliberate coupling because the two are treated as a pair, at least for now (see `plans/body-layer/plan.md` "Seams" and `body-layer/CLAUDE.md` "Tech stack"). Do not introduce a similar in-process cross-subproject import elsewhere without the same explicit justification — the default is HTTP/JSON across a subproject boundary (as aircraft-layer ↔ body-layer already does), not a shared import.

Each subproject keeps its **own `.venv`**, and `ruff`/`mypy`/`pytest` are generally **not on `PATH`** — resolve `<subproject>/.venv/bin/<tool>` before concluding a check cannot run. `mypy`'s config discovery is **CWD-only**: run it from inside the subproject (`cd <subproject> && .venv/bin/mypy src`), never as `mypy <subproject>/src` from the repo root, which silently drops `strict` and the subproject's `mypy_path` and reports phantom import errors.

## Agents

The agent roles are whatever `.claude/agents/` currently holds — read that directory rather than a count written here. They are the template roles (architect, implementer, reviewer, debugger, performance-reviewer, security, dod — see `AGENTS.md` for role sequences) plus this project's own `investigator`. Each role's model is declared in its own file's frontmatter, which is the only place it is true; most are `claude-sonnet-5`. **`dod` runs on sonnet, not haiku** — raised 2026-09-20 (user
direction) after a cheap final gate reported work as verified when it was not; `docs/AGENT_ROLES.md`
has what that cost, for anyone tempted to downgrade the last gate to save money again. For
architecturally complex or high-risk planning (coordinate system design, spatial schema, cross-theatre generalization), re-invoke architect with an explicit opus model override rather than relying on its sonnet default.

**`performance-reviewer` and `security` run once per *batch of stages actually executed together*, immediately before DoD** — not once per stage, and never held back waiting for stages that are blocked. Enabled 2026-09-24 (user direction, from the 2026-09-22→2026-09-25 retro) as *"once per whole feature"*, replacing the previous blanket skip; **restated in these terms 2026-10-17**, after that day's retro measured ~19 performance-review passes in ten days against a rule that said one per feature.

The user's own words for the rule now in force:

> *"When stages are being done one right after the other, like stages 1-3, then perf and sec at the
> end, after stage 3. If there's, say, stage 4 and 5 left but they wait for something, then don't
> wait for them on perf and sec. → group into a single run when doing stages in a batch."*

So the unit is the **batch**, not the feature and not the stage:

- Stages 1–3 built back to back → **one** performance pass and **one** security pass, after stage 3.
- Stages 4–5 blocked on a sortie, a probe or a decision → **do not wait for them.** The batch that was
  built gets its passes and goes to DoD; stages 4–5 get their own passes when they are built.
- A single stage built alone is its own batch, so a one-stage feature still gets both passes. That is
  the rule, not a violation of it.

**Why the "whole feature" wording had to go**: it was unenforceable on this project's actual shape,
where a feature's stages routinely ship in separate merges days or weeks apart. Read strictly it
would hold both passes until the last stage of `BL-14` or the 9K113 series; read loosely it justifies
a pass per stage, which is what practice drifted into. Neither was intended. The drift was found by
*counting commits in a retro*, not by anyone noticing at the time: a cadence nobody re-checks
outlives its premise.

Scoping, in the user's own terms: this is for now a single-user, LAN-only project under active development, so this is one pass per feature rather than "both roles fully on everywhere" — deeper security and performance effort comes once the important milestones (brain and memory) are complete.

**A standing exemption needs a stated condition for ending, or it outlives its premise silently.** That is the transferable lesson from how this one was arrived at — the previous blanket skip was accurate when written, carried no lapse condition, and stayed in force unexamined after the project grew the surfaces it had assumed away (`docs/AGENT_ROLES.md`). Apply it to any exemption, not just these two.

**`investigator`** is this project's recon role, needed because much of the World Model Builder depends on unverified DCS internals (file formats, coordinate systems, scripting-API availability). It sits *before* Architect's plan is finalized, not in the Implementer→Reviewer→DoD chain: **Architect invokes it proactively whenever a plan would otherwise depend on an unverified DCS-internals claim** (see `.claude/agents/architect.md` step 2) — this is not a user-invocation-only role. It writes dated findings to the `research/` directory of whichever module the finding is about (e.g. `world-model/research/`, `aircraft-layer/research/`), per the format in `docs/concept/WORLD_MODEL_BUILDER.md`, and does not write pipeline code.

## Session Start

1. Read root `ROADMAP.md` for the cross-subproject picture, then the `ROADMAP/` index of whichever
   subproject looks most active — `<subproject>/ROADMAP/<subproject>-roadmap.md` (its Status table
   row says which subproject). **Not `<subproject>/ROADMAP.md`**, which is a four-line pointer.
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

Before marking a milestone done — on its own entry file under `<subproject>/ROADMAP/`, never in
`<subproject>/ROADMAP.md`, which is a pointer; whichever subproject owns it, root
`ROADMAP.md`'s status table lists them all — answer one question in the DoD report or the
roadmap update itself: does this milestone's completion change what the next milestone should be,
or invalidate an assumption downstream milestones rely on? One line is enough — this is the
project's inspect-and-adapt checkpoint, tied to milestone boundaries rather than a calendar.

## Knowledge graph

A queryable graph over the current-state design documentation lives in `graphify-out/` (gitignored,
built from a corpus that is **a file list, not a directory** — `.claude/scripts/graph-corpus-files.sh`
produces it). A copied `graphify-corpus/` mirror was tried and removed: it keyed cache lookups and
node names on the staging path, leaking the mirror directory into the graph's own vocabulary. **Do
not reintroduce a mirror** — `/graph-refresh` carries the full reasoning.

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

**At every trigger above, search agent memory too — one rule, two stores** (user direction,
2026-10-12):

```sh
python3 .claude/scripts/memory-search.py <terms>   # agent memory, every role
```

The two stores hold different things and the memory half was, until now, unreachable in practice.
The graph covers the *documented design*; `.claude/agent-memory/` holds what a role **got wrong**,
and it is deliberately outside the graph corpus (see the `grep` note below), so no graph query will
ever surface it. **Search every role, not only the one you are in** — the cross-role hit is the
one the old per-role indexes could not surface at all.

**Why a tool and not the `MEMORY.md` index that used to sit in each directory.** That index was
loaded on every agent dispatch while no role file ever told an agent to read it — unconditional
cost, optional benefit — and it drifted. The tool derives the same index on demand from each file's
`description:` frontmatter, so it cannot drift and cannot be asked to shrink. Full account, and why
the compaction it was repeatedly asked for was impossible as phrased: `todo/todo/X-T25.md`.

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

### Behaviour-affecting constants are tunable — standard practice

**User direction, 2026-10-15**, once `X-T26` shipped the mechanism: *"X-T26 pattern must become
standard practice from now on."* A new constant that changes **what Petrovich does** — what he sees,
says, remembers, or how long he waits — is declared through `body-layer/src/tuning.py` with `lo`/`hi`
bounds and a `#:` comment, and appears in the generated `body-layer/config/defaults.toml`. One that
does not affect behaviour (buffer size, format width, protocol constant, internal epsilon) stays an
ordinary literal.

The procedure, the three measured traps (constants bind by value at import; `lo`/`hi` must be AST
literals; per-key bounds cannot catch cross-key couplings) and the inclusion test live in
`.claude/agents/implementer.md`; the Reviewer's verification half is in `.claude/agents/reviewer.md`,
and `body-layer/CLAUDE.md`'s "Tuning" section is the user-facing reference. **Outside body-layer the
loader does not exist** — declare the constant normally and note that it would want the mechanism,
rather than improvising a second one.

**The one habit worth repeating here, because it is where every `X-T26` defect hid:** check the
**rendered** `defaults.toml`, not the `#:` comment it was generated from. The generator emits only
the first sentence, so a warning written second reaches nobody — and that survived three review
passes by readers reading the diff.

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

So the first question on any piece of work is what already exists for it — not what a good solution
would look like from scratch. All three of the user's categories count:

- **Code** — a helper, a client shape, a fixture pattern, a test harness. Reuse before declaring is
  already the rule for tuning constants ("Behaviour-affecting constants are tunable"); this
  generalises it.
- **Architecture** — the seams this project already has. HTTP/JSON across a subproject boundary, one
  in-process exception that is named and justified, `TOOL_SET` as the brain's only route into body
  state, `Percept` as the no-omniscience boundary. A new mechanism alongside one of those needs a
  stated reason, not just a clean design.
- **The system of working** — the role sequences, the worktree protocol, the `ROADMAP/` entry
  layout, the ID spaces, the skills in `.claude/skills/`. If a subproject does something one way,
  the next subproject does it that way too, and a convention gets changed rather than forked.

**Finding the existing thing is the work.** This project's recurring failure is not missing
documentation but failing to find documentation that already exists — which is why the knowledge
graph and `memory-search.py` have observable triggers rather than a "before concluding" rule. The
same applies here: *"I did not see one"* is not evidence there is none, and a skill, a script or a
convention you did not look for is the most expensive kind to duplicate.

**Departing is allowed; doing it silently is not.** If the existing thing genuinely does not fit,
say which thing and what breaks, in a line, and then build what fits. That line is the difference
between a deliberate exception — like the body-layer ↔ world-model in-process import, which carries
its justification everywhere it is mentioned — and a second way of doing something that nobody
decided on.

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
which repeatedly turns out to be wrong in a way that only a conversation surfaces — **four times
so far**, most sharply when *"still one clock hour at a time"* corrected a 90° cone that was about
to be built. Each arrived *after* a reading that looked obviously right, and each would have been
built wrong. (The four: `docs/PROCESS.md`.)

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
optional. **Five** of this project's important corrections came from the user reading *why*
something was believed and spotting the flaw — a slew limit read off the wrong instrument was one.
None of them was reachable from a status line. (The five: `docs/PROCESS.md`.)

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

**Prefer a picture where it replaces prose.** User direction, 2026-10-17, raised as his own retro
item:

> *"We should use visualisations. I'm a visual thinker, so graphs, diagrams, mock views of cockpit or
> map (=svg), all those help me understand and think. Visual representation can often replace lengthy
> textual representation."*

Note the last clause: a visual **replaces** the text rather than decorating it. A diagram followed by
the same explanation in prose misses the point and costs more to read than either alone. Reach for
one whenever the subject is geometry, layout, state over time, a pipeline, or a comparison of options
— which here is most of it:

| medium | for |
|---|---|
| **SVG** | scale geometry: cockpit layout, sightlines, angular separation, a map extract with the numbers on it |
| **Mermaid** | state machines, flow, dependency, a mechanism before and after |
| **HTML artifact** | anything worth interacting with or keeping — the status page and the test cards are the precedent |
| inline ASCII | a quick table only; not a substitute for a drawing |

**Rough and early beats polished and late**, for the same reason `/explore` asks for mock output:
something concrete is what cues recall, and several of this project's largest corrections arrived
from the user reading a mock rather than answering a question — an o'clock bearing missing from a
mock callout, spotted 2026-10-17, is one. **Honest limit, to be stated rather than promised
around:** there is no image-generation model here, so "visual" means SVG, Canvas, HTML or Mermaid —
geometry, charts, mock interfaces and diagrams, not photographic or artistic renderings.

**This direction already existed and was scoped too narrowly to fire.** The 2026-09-18 version lives
in `.claude/skills/explore/SKILL.md`, which only runs during an `/explore` conversation; this
restatement is general and applies to any answer.

**Still say the uncomfortable thing.** Brevity is not the same as smoothing. A real risk, a wrong
earlier claim, or a disagreement with a request gets said plainly — in a sentence, not a section.

## Workflow

- One feature at a time. Commit in small logical steps.
- **Always create a feature branch before starting any implementation task.** Name the branch after the feature using kebab-case (e.g., `feature/hyg-data-pipeline`, `fix/floating-origin-precision`). Never implement directly on `main`. **Always branch from local `main`** — do not use `origin/main` as the branch point. **Create it as a worktree, not a checkout:** `git worktree add -b <branch> ../<repo>-<short-name> main` branches from local `main` without moving the root's own checkout, which is what the bullet below requires. (This bullet read *"checkout `main` first, then create the branch"* until 2026-10-09 — the pre-worktree procedure, and the one action the next-but-one bullet and `AGENTS.md` rule 3 now forbid. A `PreToolUse` hook refuses `git checkout -b` while the root is parked off `main` and names the worktree form instead; the stale wording and the hook that enforced it were found together by the 2026-10-09 integrity audit, findings 2 and 3.)
- **A feature branch merges automatically when DoD passes** — no separate approval, and live
  acceptance does not gate it. User direction, 2026-10-26: *"I notice I test features in batches.
  Change so that when DoD passes, feature branch is merged automatically. I'm the only user and only
  dev, so merging features I have not tested is acceptable for now."* The main loop runs `/merge`
  right after the DoD report says PASSED; untested live behaviour is carried as `#needs-flight` on
  the entry and in the test card, which names `main` as the branch to fly. **Still stop and ask** if
  the root is dirty (`AGENTS.md` rule 3), if the merge conflicts in a way that is not clear-cut, or if
  DoD did not pass. Branches that are not DoD-gated features (plans, docs, config) still merge on the
  user's word. **Lapses when there is a second user or developer** — then merges go back to explicit
  approval.
- **Testing aids take the light path.** User direction, 2026-10-30, after a ~20-line debug flag
  went through the full role sequence and came out as ~1000 added lines of plans, reviews, DoD
  reports and notes: *"That seems rather heavy and time consuming for something that is essentially
  just a helper tool to debug a problem."* A **testing aid** is anything that does not change what
  Petrovich does in normal flight: a debug or calibration flag, a probe script, a logging tweak, a
  test card, a log-analysis script. The main loop does it itself in its own worktree: write it, run
  the touched subproject's checks (see "Verification"), one commit, and merge on the user's word.
  **No subagents, no `plans/` directory, no review/DoD/security/performance reports, no notes
  harvest, no agent-memory files.** A short code comment saying what it is for is enough. If the aid
  ever becomes part of normal flight behaviour, it takes the full sequence then. If unsure which
  side of the line a change is on, say which you are assuming in one line and proceed.
- Before starting, surface any ambiguous, contradicting, or missing information and ask for clarification.
- **All work happens in a worktree — agents and the main loop alike — and the repo root belongs to the user.** Revised 2026-10-09 by user direction; see `AGENTS.md`, "Where work happens", rule 3. Read-mostly roles (Reviewer, DoD, Architect, Investigator) always take `isolation: "worktree"`; a feature's own worktree is named after the feature and lives until it merges. **The user parks the root wherever they like** — usually `main`, so they can add input documents or check out a branch to fly without colliding with anything running. **So naming the branch is the only way they learn what to test**: the root's branch no longer tells them, and that former backstop is gone. Name it in every test card and every acceptance request.
- **Non-code, cross-cutting updates that aren't part of the current milestone** (skill/config edits, backlog notes, cross-milestone bookkeeping) still do not belong in a feature branch's commits — they take **their own worktree on their own branch**. Committing them on `main` from the root is no longer the way: the root is the user's, and moving its branch under them is what rule 3 now forbids. The user may override this for a given piece of work and has done, to keep one thing to review instead of several.

## Definition of Done

- Feature implemented as planned
- All checks pass (format, lint, type check, test — see Verification)
- Core logic tested, no regressions
- All Reviewer required fixes addressed
- **All new/modified files staged and committed** — run `git status` and confirm a clean working tree before declaring any task, bug, or feature complete. Stage new files immediately after creating them; never stage build artifacts, generated output, or `.gitignore`d files.

## Backlog Management

`todo/todo/` holds User priority tasks and session-scoped notes, indexed by
`todo/todo/todo-tasks.md`; `todo/backlog/` holds the cross-cutting backlog, indexed by
`todo/backlog/todo-backlog.md` (separated 2026-09-27 — each edit used to re-extract the other into
the knowledge graph — and split to one file per item on 2026-10-09). Between them they are the
source of truth. `todo/todo.md` and `todo/backlog.md` still exist but are four-line pointers:
reading one yields no items at all. States: `[ ]` open · `[~]` in progress · `[x]` done · `[?]` decision needed · `[>]` deferred.

- Read before starting work; prefer the User priority tasks, which the `todo/todo/todo-tasks.md`
  index lists first and marks as such
- Do not start `[?]` or `[>]` tasks without instruction
- Update state as work progresses; do not delete tasks; do not exceed task scope

### Backlog items carry IDs, like milestones do

**Every item in a Backlog section has a stable ID** (user direction, 2026-09-27), so one can be named
in conversation, a commit, or a plan without quoting its first sentence. The form is
`<prefix>-B<n>`, where the prefix is the subproject's own and `B` distinguishes a backlog item from a
milestone — `BL-4` is a body-layer milestone, `BL-B4` a body-layer backlog item. A third marker,
`<prefix>-W<n>`, is for work items that are neither. Each space lives in a split directory, one file
per item, and that directory is the only place an ID exists.

**Mint with the script. Do not read a number off a document, do not count items, and do not
hand-roll the command:**

```sh
.claude/scripts/mint-id.sh BL-B      # next unused ID, and the file path to write
.claude/scripts/mint-id.sh --list    # every prefix in use, its highest number, and its directory
```

`--list` is why no prefix-to-directory table is written here: it derives the map from where each
prefix's files actually are. The two ways the hand-rolled command has been got wrong — a
prefix-agnostic pattern reading another space's maximum, and `sort -t B -k2 -n` returning `BL-B9`
against a real `BL-B46` — are both measured, both silent, and both impossible in the script, which
carries the account in its header. `docs/DOC_CONVENTIONS.md` has the full scheme, the ID-only
filename and the `[[ID]]` link form.

**Numbers are never reused and never renumbered**, including for items that are `[x]` done or
rejected — an ID that silently comes to mean a different item is worse than no ID, because a commit
message or plan citing the old meaning now reads as evidence for the new one. For the same reason an
item moving between spaces takes a **new** ID in its destination, with the old entry saying where it
went: an ID belongs to one directory's sequence, and carrying one across would make two sequences
collide.
