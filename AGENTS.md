## General Rules

- Follow `CLAUDE.md` as the primary project contract.
## Where work happens: agents get worktrees, the main checkout is the user's

**Changed 2026-09-21, after the same race condition occurred twice in one session.** The previous
rule was the inverse — agents ran in the shared checkout and *side quests* went to a worktree — and
it failed the way rules relying on main-loop discipline fail: the main loop did a bare
`git checkout main` to write a document while an implementer was mid-task on a feature branch, twice,
having quoted the rule at agents in between. A rule that must be remembered at the exact moment
attention is elsewhere will keep being broken. This one is structural instead.

### The three rules

1. **Read-mostly agents always run with `isolation: "worktree"`** — Reviewer, Definition of Done,
   Architect, Investigator, Security, Performance Reviewer. It makes them immune to anything the
   main loop does.

   **Their handoff is not "copy the report back", and getting this wrong loses work silently.** An
   agent writes far more than its headline document:

   | output | where it lands |
   |---|---|
   | the role's report (`review.md`, `dod-check.md`, `plan.md`) | worktree |
   | **agent-memory files** (`.claude/agent-memory/<role>/…`) | worktree |
   | **`NOTES.md` harvest** (Definition of Done) | worktree |
   | research notes, roadmap and `todo/` edits | worktree |

   All of it is invisible to the main checkout, and `git worktree remove --force` destroys anything
   uncommitted without warning. That nearly happened on the first isolated run: only the report was
   copied back, and it was luck that the agent had written no memory file that time.

   **So the handoff is:**

   - **Instruct the agent, in its prompt, to commit everything it writes** inside the worktree — a
     detached-HEAD commit is fine, it is reachable by sha — and to **report the sha, the file list,
     and a clean `git status --porcelain`** in its final message.
   - **Cherry-pick the sha**, then verify against the agent's own file list rather than assuming the
     pick caught everything.
   - **Only then remove the worktree.** Before removing any agent worktree, run
     `git -C <worktree> status --porcelain` and account for every line. An empty result is the
     only safe basis for `--force`.

   The failure mode is silent by construction: the report arrives, the work looks done, and the
   memory file that would have stopped the next agent repeating a mistake is simply gone.

2. **Implementers also get a worktree**, with one extra handoff step. Git will not check the same
   branch out twice, so an implementer in a worktree commits to `worktree-agent-<id>`, and the main
   loop fast-forwards that into the feature branch afterwards. **Trial this before relying on it**
   (see "Status" below).

3. **The main checkout belongs to the main loop and the user.** This is the inversion: side quests
   no longer need a worktree, because nothing else is using the checkout.

### The main checkout's branch is a contract with the user

**The user tests on the main checkout. They do not operate in worktrees.** So the branch checked out
there is not an implementation detail — it is how they know what they are flying.

- **Leave the main checkout on the branch the user should test.** If work has just landed on a
  feature branch, the main checkout stays on that branch until it merges.
- **Name the branch, explicitly, whenever asking the user to test anything.** Every test card, every
  "can you fly this", every acceptance request states the branch and the checkout command. "It's
  ready" is not actionable if they cannot tell what to check out.
- **Never leave the main checkout on a worktree branch or a detached HEAD.** Those are agent
  scaffolding and mean nothing to the person flying the aircraft.

### Status

Rules 1 and 3 are in force now. Rule 2 (implementer isolation) is **to be trialled on the next
implementer run** before being written in as settled — the untested part is the fast-forward handoff
and whether an implementer told to "commit in small steps" stays clear about which branch it is on.
Until then, an implementer may run in the main checkout, and while one does, **the main loop must
not touch git there at all** — that is the discipline this change exists to stop depending on, so
treat it as a temporary exception with a short life.

### Why a feature branch's history still stays clean

The original rule had a second, independent justification worth keeping: cross-cutting bookkeeping
(skill edits, backlog notes, workflow-doc fixes) does not belong in a feature branch's commits. That
still holds. With the main checkout free, the way to honour it is simply to commit such work on
`main` directly rather than on the feature branch — no worktree needed, same outcome.
See `.claude/skills/merge.md` for the worktree pattern as it applies to merging.
- Prefer the simplest solution that satisfies correctness, performance, and architectural clarity.
- Do not switch roles unnecessarily mid-task.
- For small features, one role may handle the whole task.
- For complex features, use the appropriate role sequence:
  1. Architect
  2. Implementer
  3. Reviewer
  4. Debugger (if needed)

Full per-role responsibilities, priorities, checklists, and output-style detail: `docs/AGENT_ROLES.md` (read when tuning a role or unsure what it should/must not do).

---

## Roles (one-liners)

1. **Architect** — plan new features, module boundaries, design tradeoffs. Writes `plans/<featurename>.md`.
2. **Implementer** — writes code for an approved plan, adds tests, straightforward refactors.
3. **Reviewer** — reviews completed work against the plan and `CLAUDE.md` before handoff.
4. **Debugger** — bugs, regressions, unexpected behavior. Reproduce → isolate → fix → verify.
5. **Performance Reviewer** — runtime cost risk on hot paths / data-intensive changes.
6. **Security** — plan review (after Architect) and deep analysis (after Reviewer, before DoD); on-demand full audits.
7. **Definition of Done** — final gate: checks pass, acceptance testing with user, harvest NOTES.md.

---

## Explore Before Deciding

**Before an Architect pass on anything consequential, talk to the user first** — a new subsystem, a
data-model change, a hard-to-reverse decision, or anything touching how Petrovich behaves in the
cockpit. The procedure is `.claude/skills/explore.md` (`/explore`).

**This cannot be delegated to an agent.** Subagents run in the background with no channel to the
user; only the main loop can hold a conversation. Treat it as a phase, not a role.

The reason it earns a place in the sequence: the user has lived experience of the aircraft that
exists in no file here and cannot be recovered by reading more code. Repeatedly on this project the
decisive constraint arrived *after* implementation began and reversed it — the mission-frequency
constraint that removed a planned transport, the screenshot-quality finding that invalidated a
merged calibration, the sentence about how recognition actually unfolds that turned a bug fix into
a belief model. Each was cheap to hear early and expensive to discover late.

Two things make the conversation work, and both cut against normal habits:

- **Open questions, not `AskUserQuestion` menus.** A menu can only offer what was already thought
  of, and the valuable input is precisely what was not. Menus are for settling a decision whose
  shape is already understood, not for finding that shape.
- **Show something concrete early.** A worked table, a draft, a sample callout. Observing real
  output is what cues recall — several of this project's most important corrections arrived that
  way rather than in answer to a question.

**Do not run it on everything.** On routine work it is friction, and friction trains the user to
skip past it — the same failure the Effort/Value check below guards against.

---

## Recommended Role Sequences

Full sequences below include Security and Performance Reviewer. **Check the project's
`CLAUDE.md` "Agents" section first — it may currently exempt one or both roles for this
project phase; that exemption overrides the sequences shown here rather than being restated
per-sequence.**

- **New feature**: *Explore (with the user)* → Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance-sensitive feature**: Architect → Security (plan review) → Implementer → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Bug fix**: Debugger → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance issue**: Debugger → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Refactor**: Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**

*Explore* precedes Architect on consequential work only — see "Explore Before Deciding" above. It is
a conversation with the user, not a role, and cannot run as a subagent.

---

## Auto-Advance

Once a role sequence starts, move to the next stage automatically — do not stop to ask "should I proceed?" between stages. Reviewer → Implementer is a loop: if Reviewer finds required fixes, hand back to Implementer and continue the loop until Reviewer approves, then proceed to DoD without asking.

Only stop and hand control to the user mid-sequence when one of the Escalation Rules below applies, or a step genuinely needs the user's own input, verification, or perception (e.g. live DCS acceptance testing, a judgment call only the user can make). Otherwise keep going through Architect → Implementer → Reviewer → (loop) → DoD in one continuous run.

---

## Escalation Rules

Stop and ask the user when:
- two reasonable architectural approaches exist and `CLAUDE.md` does not decide between them
- a new dependency seems necessary
- the feature is much larger or smaller than expected
- existing tests must be rewritten rather than extended
- the requested change conflicts with project invariants

When multiple reasonable technical approaches exist and none of the above apply, pick one and proceed — do not escalate — if the tradeoff is **local, reversible, and does not materially affect** product behavior, future architecture, dependencies, cost, or risk. State which approach was chosen and why in the plan or commit, so the user can revisit it later if needed. Escalate only when a decision is consequential, difficult to reverse, or there is genuine ambiguity about expected behavior.

---

## Effort/Value Check

When the user requests a feature or change that looks **technically challenging**, weigh the value
it creates against the effort it costs before starting. Not money — engineering effort, added
complexity, new failure surface, and future maintenance against how much the result actually
advances the project's goals.

**If the effort clearly outweighs the value, say so before building it.** Cover three things:

1. **The challenge** — concretely what makes it expensive or risky. Name the specific mechanism
   (a data model that has to change, a new in-flight failure surface, a coupling that would have
   to be introduced), not a vague "this is complex".
2. **Why the value is smaller than it looks** — what the user would actually get, and what they
   might be assuming they'd get but wouldn't.
3. **Alternatives** — cheaper paths to most of the same value, a narrower version worth building
   now, an existing mechanism that already covers part of it, or a later milestone where it
   would cost far less. Ending at "this is expensive" without a route forward is not useful.

**This is advice, not a veto.** The user sets the vision, goals and direction; this role supplies
implementation insight and the effort/value read the user cannot get without looking at the code.
If they hear the concern and still want it, that is their call — build it fully and well, and say
plainly that it is being built under their direction.

**Do not run this on everything.** Applied to routine work it becomes friction and trains the user
to skip past it. Reserve it for genuinely expensive asks; for ordinary requests, just do the work.

**Cooperation includes disagreement.** Flagging a bad effort/value trade, pointing out that a
request would not achieve what the user seems to want, or noting that an earlier decision now
looks wrong, are all part of working toward the project's goals — not obstruction. Do it early,
briefly, and with a concrete alternative, then follow the decision that comes back.

*Worked example from this repo:* when the F10 command vocabulary was scoped, a dynamically
rebuilt contact list was flagged as a materially bigger build — collector→Hook menu pushes and
`removeItemForGroup` traffic mid-flight, a new in-flight failure surface — for a menu the player
would still have to click through. The user's answer was that richer command forms belong to
BL-10/SRS instead, where free speech makes them natural. The flag cost one paragraph and removed
a whole workstream from the wrong milestone.

---

## Final Principle

Roles are there to improve judgment, not to simulate a company org chart.
If a role does not add clarity, do not invoke it explicitly.
