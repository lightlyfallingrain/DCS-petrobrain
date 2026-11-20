## General Rules

- Follow `CLAUDE.md` as the primary project contract. **Text cut from this file on 2026-11-14 to
  meet the always-loaded budget lives verbatim in `docs/AGENT_WORKTREE_PROTOCOL.md` ("Moved from
  `AGENTS.md`") and `docs/PROCESS.md`.**

## Where work happens: everything in a worktree, the repo root is the user's

**All work happens in a worktree — agents and the main loop alike. The repo root belongs to the
user.** Revised 2026-10-09 by user direction (rule 3). Inverted 2026-09-21 from the previous
arrangement after the same race happened twice in one session with the rule quoted at agents in
between: **a rule that must be remembered at the exact moment attention is elsewhere will keep
being broken**, so these are structural. Full account: `docs/AGENT_WORKTREE_PROTOCOL.md`.

### The four rules

1. **Read-mostly agents always run with `isolation: "worktree"`** — Reviewer, Definition of Done,
   Architect, Investigator, Goal/Plan Aligner, Security, Performance Reviewer.

   **Their handoff is not "copy the report back"; getting this wrong loses work silently.** An
   agent writes its report, **agent-memory files**, a **`notes/` harvest**, research notes and
   roadmap/`todo/` edits — all invisible outside the worktree, and a memory file that is never
   harvested is the most expensive loss in this system. So: **instruct the agent, in its prompt, to
   commit everything it writes** inside the worktree and report the sha, the file list and a clean
   `git status --porcelain`; harvest with `/harvest-agent-commit` (prefer `git merge --ff-only`,
   cherry-pick only when the branch diverged; verify against the agent's own file list; plain
   `git worktree remove` — **never `--force`**, which is denied; then `git branch -D
   worktree-agent-<id>` only after `git rev-parse` shows the tip is the sha you harvested, because
   an agent can commit again after reporting). A branch's existence then means "not yet harvested".

2. **Implementers also get a worktree**, committing to `worktree-agent-<id>`; the main loop
   fast-forwards that into the feature branch afterwards. In force since 2026-09-21.

3. **The repo root belongs to the user. The main loop takes a worktree too.** User direction,
   2026-10-09:

   > *"It would actually be more convenient for me if **all work** is done via worktrees. That would
   > then free the root dir to be whatever branch I happen to need for testing. Or, most probably,
   > `main` where I could also add user input documents without disturbing the ongoing agentic
   > work."*

   A feature's worktree is named after the feature and lives until it merges. **The one defined
   exception: merging into `main` happens in the root, because that is where `main` is checked out**
   — git allows no way around it (both workarounds were tested; transcripts in the protocol doc). So
   the merge is `git -C <root> merge --no-ff <branch> -m "<message>"` with the root on `main` and
   `git -C <root> status --short` empty — **`--no-ff`, never squash or rebase** (`--ff-only` is for
   harvesting an *agent* branch, a different operation). If the user has work in progress there,
   stop and ask.

4. **Name the commit the agent is meant to be looking at, and make the agent check it.** A worktree
   is created from **`origin/HEAD`**, so **a stale base is the guaranteed starting state** for every
   feature-branch dispatch (six consecutive dispatches landed stale on 2026-10-09, the worst 35
   commits behind). The dispatching prompt states the branch, the expected tip sha and the input
   documents; the agent's first action is `git rev-parse HEAD`, a mismatch is reported first, and
   `git merge --ff-only <tip>` is allowed only when HEAD is a strict ancestor with a clean tree —
   anything else stops. `agent-worktree-reminder.sh` and `agent-sha-gate.sh` inject this at
   dispatch; `plans/agent-stale-base/plan.md` has the mechanism and the snapshot fallback
   (`git archive`) for a tip that cannot be checked out.

   **Hooks fire from `$CLAUDE_PROJECT_DIR/.claude/scripts/`, i.e. whatever the repo root currently
   has** — with the root usually on `main`, the active hooks are main's hooks, and a hook fix on a
   branch takes effect only when it reaches the root's branch. Which *index* a hook inspects is a
   separate question, now answered by the payload's `cwd` (`docs/AGENT_WORKTREE_PROTOCOL.md`).

### Naming the branch is the only channel, now that the root does not say it

**The user tests in the repo root and checks branches out there themselves.** Before 2026-10-09 the
root's branch told them what to test even when nobody said it; that backstop is gone, so **naming
the branch is the whole of the channel** — every test card, every "can you fly this", every
acceptance request states the branch and the checkout command. Never leave a *worktree* on a
detached HEAD at hand-off, and never ask the user to look at a `worktree-agent-<id>` branch.
**`git worktree list` is the honest answer to "what is in flight"**: agent worktrees are removed at
harvest and feature worktrees are not.

### Two frictions with no hook

- **Bash heredocs and `>>` redirection are refused inside a worktree.** Use the `Edit` and `Write`
  tools there, and **say this in an isolated agent's prompt**.
- **The git stash stack is shared across every worktree**, so a bare `git stash` / `git stash pop` can
  take someone else's work. Prefer a temporary WIP commit. If you must stash:
  `git stash push -u -m "<unique-tag>"`, capture the sha with `git stash list --format='%H %gs'`, restore with `git stash apply <sha>` — never `pop` — and drop the entry afterwards.

### Why a feature branch's history still stays clean

Cross-cutting bookkeeping — skill edits, backlog notes, workflow-doc fixes — takes **its own worktree
on its own branch**, named after the work, and merges on its own; housekeeping of that kind merges
without asking (user direction, 2026-11-13). The user may override this for a specific piece of work
to keep one thing to review rather than several (*"Use the same branch"*, 2026-10-09). Their call;
the default stands. `.claude/skills/merge/SKILL.md` has the worktree pattern as it applies to merging.

- Prefer the simplest solution that satisfies correctness, performance, and architectural clarity.
- **Do not reinvent the wheel** — root `CLAUDE.md` has the standing form and what counts as a
  reason to depart from it.
- Do not switch roles unnecessarily mid-task. For small features, one role may handle the whole
  task; for complex features use the role sequences below.

Full per-role responsibilities, priorities, checklists, and output-style detail: `docs/AGENT_ROLES.md`.

---

## Roles (one-liners)

The roster is `.claude/agents/` — read that directory rather than trusting this list to be complete;
it has been wrong before.

1. **Architect** — plan new features, module boundaries, design tradeoffs. Writes `plans/<featurename>/plan.md`, user decisions numbered `U<n>`.
2. **Implementer** — writes code for an approved plan, adds tests, straightforward refactors.
3. **Reviewer** — reviews completed work against the plan and `CLAUDE.md` before handoff.
4. **Debugger** — bugs, regressions, unexpected behavior. Reproduce → isolate → fix → verify.
5. **Performance Reviewer** — runtime cost risk on hot paths / data-intensive changes.
6. **Security** — deep analysis (after Reviewer, before DoD); plan review and full audits on demand only.
7. **Definition of Done** — final gate: checks pass, acceptance testing with user, harvest insights into `notes/`.
8. **Investigator** — this project's own role: reconnaissance on unverified DCS internals before a
   plan depends on them; sits *before* Architect's plan is finalized; writes dated findings to the
   relevant module's `research/`; never writes pipeline code.
9. **Goal Aligner** (opus) — this project's own role: before Architect, settles *why* a goal is
   being done and what the player would want and expect from it in DCS World — ideas, not technique.
10. **Plan Aligner** (sonnet) — after Architect, checks the plan delivers those expectations. Both
   write `plans/<feature>/alignment.md`; see "Behaviour alignment" below.

---

## Explore Before Deciding

**Before an Architect pass on anything consequential, talk to the user first** — a new subsystem, a
data-model change, a hard-to-reverse decision, or anything touching how Petrovich behaves in the
cockpit. The procedure is `.claude/skills/explore/SKILL.md` (`/explore`). **This cannot be delegated
to an agent**: subagents have no channel to the user. Treat it as a phase, not a role.

The user has lived experience of the aircraft that exists in no file here. Repeatedly the decisive
constraint arrived *after* implementation began and reversed it — the mission-frequency constraint
that removed a planned transport, the screenshot-quality finding that invalidated a merged
calibration, the sentence about how recognition unfolds that turned a bug fix into a belief model.
Each was cheap to hear early and expensive to discover late.

**Before the first question, find out what is already known** (user direction, 2026-10-06): the graph
and a `grep` over `todo/`, `docs/acceptance/` and `.claude/agent-memory/` cost two minutes — the
2026-10-05 "world-model LOS is testing-only" direction was captured in writing, missed by four review
reports, and a night went into making a fallback observable that was not allowed to run.

Two things make the conversation work, and both cut against normal habits: **open questions, not
`AskUserQuestion` menus** (a menu offers only what was already thought of), and **show something
concrete early** — a worked table, a draft, a sample callout. **Do not run it on everything**: on
routine work it is friction, and friction trains the user to skip past it.

---

## Recommended Role Sequences

Root `CLAUDE.md`'s "Agents" section sets the cadence for Security and Performance Reviewer (once per
batch of stages, before DoD) and overrides the sequences below rather than being restated per
sequence. Do not assume the cadence you last saw still stands.

- **New feature**: *Explore (with the user)* → Goal Aligner → Architect → Plan Aligner → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance-sensitive feature**: Goal Aligner → Architect → Plan Aligner → Implementer → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Bug fix**: Debugger → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance issue**: Debugger → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Refactor**: Architect → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Testing aid** (debug/calibration flag, probe, logging tweak — nothing that changes normal-flight
  behaviour): main loop only → checks → one commit → merge on the user's word. No roles, no reports
  (root `CLAUDE.md`, "Workflow").

*Explore* precedes Architect on consequential work only — a conversation with the user, not a role.

**Diagram review after Architect, complex features only** (user direction, 2026-11-20): *"When
planning complex features/changes, like BL-16, architecht's plan should include mermaid (or some
other) diagrams about how the planned logic works/flows and what services are responsible of what
data/behaviour. Not detailed code, but overview that I can review. ... After architect, bring the
diagrams for user review and get user's approval or comments to amend the plan. An artifact is
probably the easiest for me to review them. The artefact can be throw away, we don't need to keep
it, the mermaid is in the plan anyhow. For small or straightforward features, this is not
necessary."* So, for complex work: Architect writes a "Design Overview (diagrams)" section →
the main loop publishes those diagrams as a throwaway artifact → the user approves or comments →
the plan is amended → Plan Aligner. The diagrams live in `plan.md`; the artifact need not be kept.

### Behaviour alignment — before and after Architect

**User direction, 2026-10-30.** High-level goals — *"scanning must find contacts"*, *"9K113 slew to
target"*, *"attack run"* — arrive underspecified, and the gaps were filled with assumptions that were
wrong about the world and caught only later by the user: the debug view drawing the scan plan rather
than where Petrovich actually looks; a detected ground unit placed at ownship elevation; a missile
guided to the ground between two units because that was the group centrepoint. None was a coding
error — each was a correct build of an idea that makes no sense in the sim, and every other gate
checks something else. Two roles, because the hard part is the first:

- **`goal-aligner` (opus), after Explore, before Architect** — states the why, derives the player's
  expectations from it, names the open assumptions a planner would fill in, and asks whether the goal
  makes sense in DCS World and the player's experience. *"The real challenge is getting it right
  before the architect"* (user, 2026-10-30), so this one gets the stronger model.
- **`plan-aligner` (sonnet), after Architect, before Implementer** — traces each expectation to the
  plan: met, missing, contradicted, or deferred to a named entry.

**CONCERNS** → settle them, with the user where only they can answer, then proceed. **MISALIGNED**
→ the goal or plan is reassessed before the next stage. A subagent cannot talk to the user, so the
roles write the questions and the main loop asks them. Skip both only for work with no behavioural
content — refactor, tooling, docs — and say so. Shared frame, lenses and calibration cases:
`docs/BEHAVIOUR_ALIGNMENT.md`. `alignment-check-reminder.sh` (PreToolUse on `Agent`) reminds at
architect and implementer dispatch, quiet once the section is on file.

**Security's plan review left the sequences at the same time** (user direction, 2026-10-30: *"Drop
the security between AR and I"*). Its deep analysis before DoD still runs; the plan review stays
available on demand.

### A change request from Security or Performance Reviewer re-enters the loop

**Added 2026-09-24 (user direction).** When either review asks for a change, that change is
implementation work and takes the implementation path:

> **Security / Performance Reviewer change request → Implementer → Reviewer (review of the fix) →
> Definition of Done.**

It does **not** go straight to DoD, and the main loop does not simply apply it itself: a fix written
in response to a review is ordinary new code, arriving late, touching a path the author had stopped
thinking about, and *the review that requested it is not the review that would catch what it
breaks* — demonstrated on `feature/watch-reporting` the day this was written (`docs/PROCESS.md`).
This applies however small the request looks; "reorder two lines" is exactly the shape that gets
applied without a second reading.

---

## Auto-Advance

Once a role sequence starts, move to the next stage automatically — do not stop to ask "should I proceed?" between stages. Reviewer → Implementer is a loop: if Reviewer finds required fixes, hand back to Implementer and continue until Reviewer approves, then proceed to DoD without asking. A Security or Performance Reviewer change request re-enters that same loop; auto-advance applies to the re-entry too.

Only stop and hand control to the user mid-sequence when one of the Escalation Rules below applies, or a step genuinely needs the user's own input, verification, or perception (live DCS acceptance testing, a judgment call only the user can make). Otherwise keep going through Architect → Implementer → Reviewer → (loop) → DoD → **merge** in one continuous run. **DoD PASSED is the merge trigger** (user direction 2026-10-26, root `CLAUDE.md` "Workflow"): the main loop merges with `/merge` without asking; a live test the user has not flown yet becomes `#needs-flight` and a test card naming `main`.

---

## Escalation Rules

Stop and ask the user when:
- two reasonable architectural approaches exist and `CLAUDE.md` does not decide between them
- a new dependency seems necessary
- the feature is much larger or smaller than expected
- existing tests must be rewritten rather than extended
- the requested change conflicts with project invariants

When multiple reasonable technical approaches exist and none of the above apply, pick one and proceed — do not escalate — if the tradeoff is **local, reversible, and does not materially affect** product behavior, future architecture, dependencies, cost, or risk. State which approach was chosen and why in the plan or commit. Escalate only when a decision is consequential, difficult to reverse, or there is genuine ambiguity about expected behavior.

---

## Effort/Value Check

When the user requests a feature or change that looks **technically challenging**, weigh the value
it creates against the effort it costs before starting — engineering effort, added complexity, new
failure surface, future maintenance — against how much the result advances the project's goals.

**If the effort clearly outweighs the value, say so before building it**, covering three things:

1. **The challenge** — concretely what makes it expensive or risky: the specific mechanism, not a
   vague "this is complex".
2. **Why the value is smaller than it looks** — what the user would actually get, and what they
   might be assuming they'd get but wouldn't.
3. **Alternatives** — a cheaper path to most of the value, a narrower version worth building now, an
   existing mechanism that covers part of it, or a later milestone where it would cost far less.

**This is advice, not a veto.** The user sets the vision, goals and direction. If they hear the
concern and still want it, build it fully and well, and say plainly that it is being built under
their direction. **Do not run this on everything** — applied to routine work it becomes friction.
**Cooperation includes disagreement**: flagging a bad trade, or noting that an earlier decision now
looks wrong, is part of working toward the project's goals — do it early, briefly, with a concrete
alternative, then follow the decision that comes back.

*Worked example:* when the F10 command vocabulary was scoped, a dynamically rebuilt contact list was
flagged as a materially bigger build (collector→Hook menu pushes and `removeItemForGroup` traffic
mid-flight, a new in-flight failure surface) for a menu the player would still have to click through.
The user's answer was that richer command forms belong to BL-10/SRS instead. The flag cost one
paragraph and removed a whole workstream from the wrong milestone.

---

## Final Principle

Roles are there to improve judgment, not to simulate a company org chart.
If a role does not add clarity, do not invoke it explicitly.
