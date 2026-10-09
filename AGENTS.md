## General Rules

- Follow `CLAUDE.md` as the primary project contract.
## Where work happens: everything in a worktree, the repo root is the user's

**All work happens in a worktree — agents and the main loop alike. The repo root belongs to the
user.** Revised 2026-10-09 by user direction; see rule 3 for what changed and why.

**Inverted 2026-09-21**, after the previous arrangement — agents in the shared checkout, side
quests in a worktree — failed the way rules relying on main-loop discipline fail: the same race
happened twice in one session, with the rule quoted at agents in between. **A rule that must be
remembered at the exact moment attention is elsewhere will keep being broken**, so these are
structural instead. Full account: `docs/AGENT_WORKTREE_PROTOCOL.md`.

### The four rules

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

   All of it is invisible outside that worktree, and `git worktree remove --force` destroys anything
   uncommitted without warning. That nearly happened on the first isolated run: only the report was
   copied back, and it was luck that the agent had written no memory file that time.

   **So the handoff is:**

   - **Instruct the agent, in its prompt, to commit everything it writes** inside the worktree — a
     detached-HEAD commit is fine, it is reachable by sha — and to **report the sha, the file list,
     and a clean `git status --porcelain`** in its final message.
   - **Prefer `git merge --ff-only worktree-agent-<id>`; cherry-pick only when that refuses.**
     Agents fast-forward to the named tip before working (rule 4), so their branch is normally a
     **descendant** of the feature branch and a fast-forward is available. Check it:

     ```sh
     git merge-base --is-ancestor <feature-branch> worktree-agent-<id>   # true => ff available
     ```

     **Why this is not a style choice.** A fast-forward preserves the agent's shas, so the branch
     registers as merged and `git branch -d` works — which answers "has this been harvested?" with
     git instead of bookkeeping. A cherry-pick rewrites the shas, the branch never registers as
     merged, and that unanswerable question is what left 67 agent branches against 58 real ones in
     September. Revised 2026-10-09; the whole of this session's harvests were cherry-picks under the
     old wording, which was written when agents started at `origin/main` and a cherry-pick was the
     only option.

     **A fast-forward is only available if the main loop has not advanced the branch while the agent
     held it.** If it has, the branch has diverged and cherry-pick is correct — that is a fallback,
     not a failure. Prefer not to commit to a branch an agent is working on; check with
     `git merge-base --is-ancestor` before you do.
   - **Verify against the agent's own file list** rather than assuming the harvest caught everything.
   - **Only then remove the worktree**, with a plain `git worktree remove` — **never `--force`,
     which is now in the deny list** (`.claude/settings.json`).
   - **Then delete the agent's branch**, `git branch -D worktree-agent-<id>`, so that a branch's
     existence means "not yet harvested". They never register as merged, because the harvest is a
     cherry-pick, so nothing else retires them.

     **The check before `git branch -D` is not "did I cherry-pick its report's sha" but "is the
     branch tip the sha I harvested".** One command:

     ```sh
     git rev-parse worktree-agent-<id>   # must equal the sha you picked
     ```

     **A mismatch means there is work you have not taken.** An agent can commit *again* after
     reporting — one did, and the branch was deleted on the strength of the first harvest, the
     second commit surviving only because `gc` had not run. Nothing announces a second commit
     except the agent choosing to say so, and messaging an agent mid-run makes it likelier.

     If a plain `git worktree remove` ever refuses, **read what it names** and fix that rather than
     reaching for `--force`: the refusal fires in exactly the case where something unaccounted-for
     would be destroyed. Why it is denied, and the `*.egg-info/` case that once seemed to need it:
     `docs/AGENT_WORKTREE_PROTOCOL.md`.

   The failure mode is silent by construction: the report arrives, the work looks done, and the
   memory file that would have stopped the next agent repeating a mistake is simply gone.

2. **Implementers also get a worktree**, with one extra handoff step. Git will not check the same
   branch out twice, so an implementer in a worktree commits to `worktree-agent-<id>`, and the main
   loop fast-forwards that into the feature branch afterwards. Trialled 2026-09-21 and **in
   force**; what the trial surfaced is in `docs/AGENT_WORKTREE_PROTOCOL.md`.

3. **The repo root belongs to the user. The main loop takes a worktree too.** Revised 2026-10-09,
   user direction:

   > *"It would actually be more convenient for me if **all work** is done via worktrees. That would
   > then free the root dir to be whatever branch I happen to need for testing. Or, most probably,
   > `main` where I could also add user input documents without disturbing the ongoing agentic
   > work."*

   So: a feature's worktree is named after the feature (not `worktree-agent-<id>`), and it lives
   until the feature merges. The user's own checkout is theirs to park wherever they like — usually
   `main`, so they can drop a sortie-feedback document in or check out a branch to fly without
   colliding with anything running.

   **The one defined exception: merging into `main` happens in the root, because that is where
   `main` is checked out.** Git allows no way around this, and both plausible workarounds were
   tested rather than assumed:

   ```
   $ git worktree add <path> main
   fatal: 'main' is already used by worktree at '/Users/sg/Code/DCS-petrobrain'
   $ git fetch . HEAD:main
   fatal: refusing to fetch into branch 'refs/heads/main' checked out at '/…/DCS-petrobrain'
   ```

   So the merge is `git -C <root> merge --no-ff <branch> -m "<message>"` with the root on `main` and
   its tree clean — **`--no-ff`, not `--ff-only`**: this project wants a real merge commit
   summarising the branch, and never a squash or a rebase of `main`
   (`.claude/skills/merge/SKILL.md`). The `--ff-only` preference in rule 1 is for harvesting an
   *agent* branch, which is a different operation; conflating the two is a mistake this rule made
   on its first writing.

   **The exception is narrow on purpose**: it moves `main` forward, which is what a merge is, and it
   does not change which branch the root has checked out — so it does not take the root away from
   the user. Check `git -C <root> status --short` is empty first; if they have work in progress
   there, stop and ask rather than merging around it.

   > **Superseded.** This read *"The main checkout belongs to the main loop and the user. This is the
   > inversion: side quests no longer need a worktree, because nothing else is using the checkout."*
   > That was true of agents-versus-main-loop and is **not** being reversed — agents still always get
   > a worktree. What is removed is the *main loop's* share of the root, which the 2026-09-21
   > inversion left in place only because nothing then needed it. The side-quest consequence is
   > reversed with it: see "Why a feature branch's history still stays clean" below.

4. **Name the commit the agent is meant to be looking at, and make the agent check it.** A
   worktree is created from **`origin/HEAD`** — the remote-tracking ref for the default branch — not
   from the target branch and not from the dispatching session's HEAD. Established by reflog
   2026-10-09 (`branch: Created from origin/main`), so **a stale base is the guaranteed starting
   state for any dispatch whose target is not `origin/main`, which is every feature-branch dispatch
   there will ever be.** Six consecutive dispatches that day landed stale, the worst 35 commits
   behind; three roles had each verified the wrong code before this rule existed. **Assume a stale
   base. Never hope for a fresh one.** Mechanism and the open question of whether
   `worktree.baseRef` can change it: `plans/agent-stale-base/plan.md`.

   - **The dispatching prompt states the branch and the expected tip sha.** "Review the fix" is not
     an address. **It also names the input documents**, because a stale base is harmless for source
     and dangerous for inputs — the check is not "is the source the same" but "is everything I was
     told to read present".
   - **The agent's first action is `git rev-parse HEAD`**, compared against that sha. A mismatch is
     reported first, always, and never worked around silently.
   - **Then, if and only if HEAD is a strict *ancestor* of the named tip and the tree is clean,
     `git merge --ff-only <tip>` and say so in the report.** It cannot lose work and cannot pick up
     anything the dispatcher did not name. **Anything else — diverged HEAD, unique commits, a dirty
     tree — stops.**
   - **When the tip cannot be checked out at all**, verify against an isolated snapshot:
     `git archive <branch> | tar -x -C <scratch>`, running every command with `cwd` inside that
     tree's own subproject directory. `pyproject.toml`'s `[tool.pytest.ini_options] pythonpath`
     resolves relative to pytest's own rootdir, so `PYTHONPATH` alone does **not** redirect imports.
     For a single *document*, `git show <tip>:<path>` works even when a checkout does not.
   - **Agent tooling is only as current as the agent's base commit** — a fix being on `main` does
     not mean an agent has it.

   A `PreToolUse` hook on `Agent` (`agent-worktree-reminder.sh`, `agent-sha-gate.sh`) injects this
   at dispatch, because the moment it matters is the moment attention is on the task instead — the
   same argument that made rule 1 structural. **Hooks themselves fire from
   `$CLAUDE_PROJECT_DIR/.claude/scripts/`, i.e. whatever the repo root currently has** — documented
   and deliberate, so a hook fix on your branch does **not** take effect until it reaches the root's
   branch. With the root now the user's and usually on `main`, that means **the active hooks are
   main's hooks.** A session developing a hook cannot exercise it through the hook mechanism; run the
   script directly instead. Being fixed, not accepted — `plans/all-work-in-worktrees/plan.md`.

   Incident record — the three burned roles, the eleven-commits-behind case, what each cost:
   `docs/AGENT_WORKTREE_PROTOCOL.md`.

### Naming the branch is the only channel, now that the root does not say it

**The user tests in the repo root, and they check branches out there themselves** (*"no problem"*,
2026-10-09). Nothing else moves that checkout.

- **Name the branch, explicitly, whenever asking the user to test anything.** Every test card, every
  "can you fly this", every acceptance request states the branch and the checkout command. "It's
  ready" is not actionable if they cannot tell what to check out.

  **This used to have a backstop and no longer does.** The rule before 2026-10-09 was *"leave the
  main checkout on the branch the user should test"*, so the root's branch told them what to test
  even when nobody said it. With the root theirs, that signal is gone — **naming the branch is the
  whole of the channel.** Forgetting it now means they have nothing to go on. Observed the same day
  the rule changed: their checkout sat on `main` for a 43-commit session, and the branch name was
  the only thing that would have led them to any of it.
- **Never leave a *worktree* on a detached HEAD at hand-off**, and never ask the user to look at a
  `worktree-agent-<id>` branch. Those are scaffolding and mean nothing to the person flying the
  aircraft.
- **`git worktree list` is the honest answer to "what is in flight".** That is why agent worktrees
  are removed at harvest and feature worktrees are not: a listed worktree should mean live work.

### Status: all four rules in force

All four are in force; rule 2 was trialled on cones 2B (2026-09-21) and worked. Two operative
frictions have no hook and so stay here rather than moving to the record:

- **Bash heredocs and `>>` redirection are refused inside a worktree.** Use the `Edit` and `Write`
  tools for file content there, which is better practice anyway. **Say this in an isolated agent's
  prompt**, or it will discover it mid-task and improvise.
- **The git stash stack is shared across every worktree**, and more sessions in more worktrees makes
  a bare `git stash` / `git stash pop` likelier to take someone else's work. Prefer a temporary WIP
  commit to set work aside. If you must stash: `git stash push -u -m "<unique-tag>"`, capture the
  sha immediately with `git stash list --format='%H %gs'`, restore with `git stash apply <sha>` —
  never `pop` — and drop the entry afterwards, re-finding it by tag.

The third — the agent-memory hook once denying the only correct path an isolated agent had — is
fixed, and is in `docs/AGENT_WORKTREE_PROTOCOL.md` along with why a memory that is never written is
the most expensive loss in this system.

### Why a feature branch's history still stays clean

Cross-cutting bookkeeping — skill edits, backlog notes, workflow-doc fixes — does not belong in a
feature branch's commits. **That still holds; how to honour it changed on 2026-10-09.** There is no
longer a main-loop session sitting in the root to commit such work directly, so it takes **its own
worktree on its own branch**, named after the work, and merges on its own. One more worktree is
cheap; `git worktree list` showing it is the point.

> **Superseded.** This read *"With the main checkout free, the way to honour it is simply to commit
> such work on `main` directly rather than on the feature branch — no worktree needed, same
> outcome."* The root is no longer free — it is the user's — and committing to `main` from it would
> move the branch under their feet, which is exactly what rule 3 now forbids.

**The user may override this for a specific piece of work, and did so twice on 2026-10-09**
(*"Use the same branch"*, *"Continue in this branch"*), putting cross-cutting convention edits onto
a feature branch deliberately so there was one thing to review rather than several. Their call to
make; the default stands.
See `.claude/skills/merge/SKILL.md` for the worktree pattern as it applies to merging.
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

The roster is `.claude/agents/` — read that directory rather than trusting this list to be complete;
it has been wrong before (`investigator` existed here, and in root `CLAUDE.md`, while this section
listed seven).

1. **Architect** — plan new features, module boundaries, design tradeoffs. Writes `plans/<featurename>.md`.
2. **Implementer** — writes code for an approved plan, adds tests, straightforward refactors.
3. **Reviewer** — reviews completed work against the plan and `CLAUDE.md` before handoff.
4. **Debugger** — bugs, regressions, unexpected behavior. Reproduce → isolate → fix → verify.
5. **Performance Reviewer** — runtime cost risk on hot paths / data-intensive changes.
6. **Security** — plan review (after Architect) and deep analysis (after Reviewer, before DoD); on-demand full audits.
7. **Definition of Done** — final gate: checks pass, acceptance testing with user, harvest NOTES.md.
8. **Investigator** — this project's own role, not from the template: reconnaissance on unverified
   DCS internals before a plan depends on them. Sits *before* Architect's plan is finalized, not in
   the Implementer→Reviewer→DoD chain. Writes dated findings to the relevant module's `research/`;
   never writes pipeline code. Root `CLAUDE.md`'s "Agents" section has the full remit.

---

## Explore Before Deciding

**Before an Architect pass on anything consequential, talk to the user first** — a new subsystem, a
data-model change, a hard-to-reverse decision, or anything touching how Petrovich behaves in the
cockpit. The procedure is `.claude/skills/explore/SKILL.md` (`/explore`).

**This cannot be delegated to an agent.** Subagents run in the background with no channel to the
user; only the main loop can hold a conversation. Treat it as a phase, not a role.

The reason it earns a place in the sequence: the user has lived experience of the aircraft that
exists in no file here and cannot be recovered by reading more code. Repeatedly on this project the
decisive constraint arrived *after* implementation began and reversed it — the mission-frequency
constraint that removed a planned transport, the screenshot-quality finding that invalidated a
merged calibration, the sentence about how recognition actually unfolds that turned a bug fix into
a belief model. Each was cheap to hear early and expensive to discover late.

**Before the first question, find out what is already known** (user direction, 2026-10-06). The
graph and a `grep` over `todo/`, `docs/acceptance/` and `.claude/agent-memory/` cost two minutes and
stop the conversation being spent on something already decided and merely absent from context — the
2026-10-05 "world-model LOS is testing-only" direction was captured in writing, missed by four
review reports, and a night went into making a fallback observable that was not allowed to run.
`.claude/skills/explore/SKILL.md` has the procedure and the graph-versus-`grep` split.

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

Full sequences below include Security and Performance Reviewer. **Read root `CLAUDE.md`'s "Agents"
section first for the cadence currently set for those two roles — an exemption, a once-per-feature
pass, or something else — and let it override the sequences shown here rather than restating it
per-sequence.** Do not assume the cadence you last saw still stands: it has changed, and the earlier
blanket skip outlived its premise precisely because nothing forced it to be re-read.

- **New feature**: *Explore (with the user)* → Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance-sensitive feature**: Architect → Security (plan review) → Implementer → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Bug fix**: Debugger → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance issue**: Debugger → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Refactor**: Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**

*Explore* precedes Architect on consequential work only — see "Explore Before Deciding" above. It is
a conversation with the user, not a role, and cannot run as a subagent.

### A change request from Security or Performance Reviewer re-enters the loop

**Added 2026-09-24 (user direction).** When either review asks for a change, that change is
implementation work and takes the implementation path:

> **Security / Performance Reviewer change request → Implementer → Reviewer (review of the fix) →
> Definition of Done.**

It does **not** go straight to DoD, and the main loop does not simply apply it itself. The reason is
the same one that put Reviewer after Implementer in the first place: a fix written in response to a
review is ordinary new code, arriving late, usually under time pressure, and touching a path the
original author had already stopped thinking about. It deserves the same reading as the code it
patches.

The failure this prevents is specific and was demonstrated on `feature/watch-reporting` the day this
rule was written. The performance review asked for one short-circuit; applying it also skipped a
piece of masking bookkeeping the review had not mentioned, which would have made a contact read as
line-of-sight-masked on its first tick back in range with no masked sample ever taken there. The
fix was correct in the end, but *the review that requested it was not the review that would have
caught that* — it had already reported and finished.

This applies however small the request looks. "Reorder two lines" is exactly the shape of change
that gets applied without a second reading.

---

## Auto-Advance

Once a role sequence starts, move to the next stage automatically — do not stop to ask "should I proceed?" between stages. Reviewer → Implementer is a loop: if Reviewer finds required fixes, hand back to Implementer and continue the loop until Reviewer approves, then proceed to DoD without asking.

A Security or Performance Reviewer change request re-enters that same loop rather than ending it — Implementer, then Reviewer on the fix, then DoD (see "A change request from Security or Performance Reviewer re-enters the loop" above). Auto-advance applies to that re-entry too: it does not need the user's go-ahead, only their decision on anything the Escalation Rules actually cover.

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
