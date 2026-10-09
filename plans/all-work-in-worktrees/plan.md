# All work in worktrees; the repo root belongs to the user

Queued 2026-10-09, by user direction. Nothing here is started. The contract edit waits for the
round-4 fix harvest, because that agent is editing `CLAUDE.md` right now and both halves of this
change land there.

## The direction, in the user's words

> *"related to repo root dir and worktrees. It would actually be more convenient for me if **all
> work** is done via worktrees. That would then free the root dir to be whatever branch I happen to
> need for testing. Or, most probably, `main` where I could also add user input documents without
> disturbing the ongoing agentic work."*

Two things are being asked for, and the second is the point: **a working copy that is theirs, that
nothing else moves**, where they can check out a branch to fly or drop a sortie-feedback document in
without colliding with whatever is running.

## This is independent of the stale-base problem — established, not assumed

The adjacent investigation (`plans/agent-stale-base/plan.md`) proved by reflog that agent branches
are created from **`origin/main`**:

```
29217c0 worktree-agent-a8670f1ca75f53a4a@{1}: branch: Created from origin/main
```

Not from the project root's HEAD, not from the dispatching session's. **So freeing the root dir
neither fixes nor worsens the stale base.** Adopt this direction on its own merits; it changes
nothing about where agents start. The one real fix for that remains having `agent-sha-gate.sh`
compute and inject the dispatching session's sha.

## What changes

### `AGENTS.md` rule 3 inverts

Current: *"The main checkout belongs to the main loop and the user."* Becomes: **the repo root
belongs to the user alone.** The main loop takes a worktree like everything else, named after the
feature rather than `worktree-agent-<id>`.

This is the second inversion of this rule. The first (2026-09-21) moved agents *into* worktrees and
side quests *out* of them, on the grounds that the main loop and agents were racing over one
checkout. That reasoning still holds and is not being reversed — what is being removed is the main
loop's claim on the root, which the first inversion left in place only because nothing then needed
it. **Record it as a revision with a pointer, per `docs/PROCESS.md` "Superseding a decision", not as
a rewrite.**

### The "contract with the user" section changes meaning, and loses one thing

Today: *"Leave the main checkout on the branch the user should test"* — the branch in the root tells
them what to test without being told. Under the new scheme they check branches out themselves, so
that signal is gone and **naming the branch explicitly becomes the only channel.** That is already
the rule (*"Name the branch, explicitly, whenever asking the user to test anything"*), so the loss is
small — but it is a real loss and the rule stops having a backstop. Worth stating in the section
rather than quietly dropping the sentence.

Also: *"Never leave the main checkout on a worktree branch or a detached HEAD"* survives unchanged
and matters **more**, since the main loop will no longer be there to notice.

### User corrections, 2026-10-09 — three of this plan's costs are not acceptable, they are work

The first draft of this plan listed the hook and graph consequences as costs to be accepted. The
user rejected two of them and corrected a third:

> *"`29217c0 worktree-agent-…@{1}: branch: Created from origin/main` -> **this could be changed**"*
>
> *"you'd check branches out yourself -> **no problem**"*
>
> *"Hooks become consistently main's hooks -> **is problem. Hooks should fire wherever work is being
> done**"*
>
> *"The shared graph becomes main's graph -> **same as hook, graph should reflect what is being
> worked on**"*
>
> *"with an instruction not to cd to the root -> **that was not me. I instructed to continue in same
> branch, that's different.**"*

And then, refining the graph requirement:

> *"graph - for docs main's state is ok, but for code the graph should be up to date with what the
> agent is working on"*

**The last correction matters for the record:** the instruction not to `cd` to the repository root
came from the session environment, not from the user. Their *"use the same branch"* was about the
branch, not the directory. So nothing the user said ever required the main loop to stay out of the
root — the plan below stands on their actual preference, which is that the root be theirs.

#### The graph split is already the project's own line, and the artifacts already support it

`graphify-ast-refresh.sh`'s own header states the division: **"structure per commit, meaning per
merge."** The AST layer is cheap — measured 1.56s over all 141 Python files — and runs post-commit;
the semantic layer needs an LLM and runs at merge. That maps exactly onto the user's requirement:
**borrow main's semantic/doc layer, build the code layer per worktree.**

On disk the layers are already separate files: `graphify-out/.graphify_ast_incremental.json` is
distinct from `graphify-out/graph.json`. So this needs no new graph architecture, just two path
fixes:

1. **`graphify-ast-refresh.sh:28-29` resolves `${CLAUDE_PROJECT_DIR:-…}` and `cd`s to it**, so a
   commit made in a worktree refreshes the **main checkout's** AST layer, not its own. It must
   resolve the committing worktree's root instead. It also bails at line 33 when there is no
   `graphify-out/graph.json`, which is always true in a fresh worktree — so it must be able to
   create a code-only layer there rather than exiting.
2. **`gq.sh:48` treats "no local `graph.json`" as "borrow everything"**, including code structure.
   It should borrow main's *semantic* graph while preferring a local AST increment, so a query in a
   worktree gets main's documents and the worktree's code.

Note the git hooks themselves are shared — there is one `.git/hooks`, so a commit in any worktree
already fires them. The defect is purely where the script writes.

**Honest scope note:** this branch's diff against `main` is documents only, no `.py` touched, so a
stale code layer has not actually bitten yet. It would on the first code branch, which is most of
them.

#### Hooks firing from the wrong branch is a defect to fix, not a cost to accept

Superseded reasoning is kept below for the mechanism it records. The user's requirement is that a
session working in a worktree on branch X gets branch X's hook scripts. Whether Claude Code supports
that directly is being established; if not, the fallback is a dispatcher shim — every hook registered
as `hookrun.sh <name>.sh`, which reads the stdin JSON once, extracts `cwd`, resolves that worktree's
root, and execs `<root>/.claude/scripts/<name>.sh` when it exists, replaying stdin. Hooks here
already read stdin JSON with `jq` (`agent-sha-gate.sh:45`), so the mechanism is available.

#### Documentation findings, 2026-10-09 — the user was right that the base is configurable

From a docs lookup against `code.claude.com/docs`. **Everything in this subsection is a relayed
claim, not a verified one**, and one of them is being measured by probe right now (see below) because
a plausible-sounding setting name is exactly the kind of thing a lookup invents.

| question | documented answer |
|---|---|
| base of an `isolation: "worktree"` agent | `origin/HEAD` — the remote-tracking ref for the default branch. Claude Code fetches it if not fetched in 24h. **Documented and intended**, and the 34-commits-behind case is "expected when the feature branch hasn't been pushed" |
| configurable? | **Yes, but project-wide only**: `worktree.baseRef` in `.claude/settings.json`, `"fresh"` (default, `origin/HEAD`) or `"head"` (local HEAD) |
| per-dispatch base? | **No mechanism.** Cannot name a branch or sha for one agent |
| pre-create a worktree for an Agent to use? | **No documented mechanism** |
| `$CLAUDE_PROJECT_DIR` per-worktree? | **No — deliberately fixed**, with the docs giving the main-checkout hook script as the explicit example. Intended behaviour, not an oversight |
| `cwd` in hook stdin? | **Yes**, a documented common field on every event, and it follows the session |
| hook commands shell-evaluated? | **Yes** by default (shell form, `sh -c`); `"args": []` switches to exec form with no expansion |
| per-worktree or per-branch `settings.json`? | **No supported mechanism.** A branch's own `.claude/settings.json` is readable only because it is in the tree; nothing prefers it |

**`baseRef: "head"` is the whole question, and "local HEAD" is ambiguous in the one way that
matters.** If it means the **dispatching session's** HEAD, it fixes the stale base outright. If it
means the **project root's** HEAD, it is worthless under this plan — the user wants the root parked
on `main`, so "head" would equal `main` and nothing would change. The documentation quote does not
disambiguate, and `$CLAUDE_PROJECT_DIR` being deliberately root-fixed is weak evidence for the
unhelpful reading.

**Attempted measurement, INCONCLUSIVE — and the reason is a mistake worth recording.**
`worktree.baseRef: "head"` was written to `.claude/settings.local.json` and a no-op probe agent
dispatched. It came back at `29217c0` — `main`'s tip, unchanged, while the dispatching session was at
`50dcea6`, 36 commits ahead. That looks like a clean negative and **is not one:**

- The file was written to **this worktree's** `.claude/`, but settings are read from
  `$CLAUDE_PROJECT_DIR/.claude/` — the project root, where no such file existed
  (`ls` confirmed). **The setting was never in scope.** The docs' own point that
  `$CLAUDE_PROJECT_DIR` is deliberately root-fixed is exactly what this got wrong, one paragraph
  after quoting it.
- Even correctly placed, settings are likely read at session start, so a mid-session write may not
  take effect at all.

So three confounds remain live: wrong location, load timing, and whether `worktree.baseRef` is a real
key or an invention of the lookup. **Nothing has been learned about `baseRef` yet.**

**The test that would settle it, and it needs the user or a fresh session:** put
`{"worktree":{"baseRef":"head"}}` in **`/Users/sg/Code/DCS-petrobrain/.claude/settings.local.json`**
(gitignored), start a **new** session in a worktree whose HEAD differs from the root's, dispatch a
no-op probe, and read its `git rev-parse HEAD`. Root's HEAD → the setting is useless under this plan.
Session's HEAD → it fixes the stale base outright. Unchanged `origin/HEAD` → the key is not real.
The probe must be told **not** to fast-forward; the self-correction every other agent performs would
destroy the measurement.

Writing into the root's settings was deliberately **not** done here: it is the user's checkout and
their configuration, and this plan is queued rather than in flight.

**A cheaper alternative to the shim, worth testing before building one.** If the hook *process*
inherits the session's cwd, then a hook command — which is shell-evaluated — can resolve the
worktree itself with `$(git rev-parse --show-toplevel)`, no shim and no stdin parsing. Unknown
currently: `commit-quality-gate.sh:10` explicitly `cd`s to `$CLAUDE_PROJECT_DIR`, which shows the
scripts do not rely on cwd but says nothing about what cwd is. One `pwd`-logging hook answers it.
Test this first; the shim is the fallback.

**If the shim is needed, two cautions from the lookup.** It must write diagnostics to stderr only —
anything on stdout prepends to the child's JSON and breaks the parse. And two things are *not*
formally documented: that a hook may read stdin (every example does), and that exit codes and
`additionalContext` pass through a wrapper unchanged. Both need a trivial echo-hook test before the
shim carries real gates.

> **Superseded by the three subsections above.** What follows treated the hook and graph behaviour as
> consequences to live with. They are requirements. Kept because the mechanisms it describes are
> accurate and are what any fix has to work against.

### Hooks become predictable instead of varying

Hooks execute from `$CLAUDE_PROJECT_DIR/.claude/scripts/`, i.e. whatever the root has checked out —
already recorded in `AGENTS.md` and already a trap (a sha-gate fix on `main` stayed inactive for a
session parked on `fix/los-hook-statics`, 2026-10-06).

With the root usually on `main`, **the active hooks are main's hooks, consistently.** That is better
than today, where they silently tracked whichever branch the root happened to hold. The cost: **a
session developing a hook cannot exercise it through the hook mechanism** until it merges, because
its own branch's copy is not what fires. Run such a script directly instead, and say so in the
convention — otherwise the first person to change a hook will test it, see nothing, and conclude the
hook is broken.

If the user does check a feature branch out at the root to fly it, that branch's hooks become active
for any session running at the time. Harmless in practice, worth knowing when something behaves
oddly.

### The knowledge graph's base becomes `main`

`graphify-out/` is gitignored and per-worktree, and `gq.sh` was already fixed (`c33af2e`) to let a
worktree borrow the root's graph. With the root on `main`, **the shared graph is built from `main`** —
which is the right base for a reference graph, and removes today's oddity where the graph could
describe an unmerged branch. `/graph-refresh` should then be understood to refresh *main's* graph.

### Things that do not change but are worth re-stating in the convention

- **`git stash` is shared across all worktrees.** Already hazardous, unchanged, and more sessions in
  more worktrees makes a bare `git stash pop` likelier to take someone else's work. The existing
  guidance — a temporary WIP commit, or `git stash push -u -m "<unique-tag>"` and `apply <sha>` — is
  the right answer and should be in the convention rather than only in session environments.
- **Agent handoff is unchanged.** Commit in the worktree, cherry-pick, verify against the file list,
  plain `git worktree remove`, `git rev-parse` before `git branch -D`.
- **Worktrees need pruning.** A worktree whose directory is deleted externally needs
  `git worktree prune`. With every piece of work in one, `git worktree list` becomes the thing that
  tells the user what is in flight — which is a gain, and an argument for naming feature worktrees
  after the feature.

## The one thing to check before committing to it

**Can the harness start a session directly in a worktree, or does the user have to?** This session
*was* started in `.claude/worktrees/doc-conventions` with an instruction not to `cd` to the root, so
it is clearly possible — but it is not established whether that was arranged deliberately or is
something the user must set up per session. If it needs a manual step every time, the convention has
to say what that step is, or the direction costs the user more friction than it removes. **Ask them
how this session came to start where it did** rather than guessing.

## Order of work

1. Harvest the round-4 fixes (that agent is editing `CLAUDE.md`).
2. Answer the question above.
3. `AGENTS.md`: invert rule 3 as a recorded revision; rewrite "The main checkout's branch is a
   contract with the user"; add the hook-development caveat and the `git stash` note.
4. Root `CLAUDE.md` "Workflow": the bullet saying non-code cross-cutting work goes on `main` in the
   main checkout needs rewording — under this scheme there is no main-checkout session to do it in.
5. Re-read `.claude/skills/merge/SKILL.md`, which carries its own worktree pattern, and the six role
   files' shared "Where things live" block.

## Not to be done

- **Do not reverse the 2026-09-21 inversion.** Agents stay in worktrees; that is settled and this
  direction extends it rather than undoing it.
- **Do not make the root a worktree too.** It is the repository; the user wants it ordinary.
- **Do not couple this to the stale-base fix.** Proven independent above, and bundling them would
  make either one's failure look like the other's.


---

## The branch-based dispatch, and what it fixes (user, 2026-10-09)

> *"Since the branch for work is known, a created worktree should start from where that branch is.
> Then we only really need to know the branch. Right? Agent do commit as they progress so changes do
> end up in the branch. Then you could instruct agent to use worktree and checkout `<branch>` to do
> whatever needs doing. Whether worktree should be closed when agent finishes or at merge is another
> question."*

**The direction is right and leads somewhere better than the current scheme. Two corrections.**

### Correction 1 — an agent cannot check the branch out; it must start *from* it

**Git will not check the same branch out in two worktrees**, and the feature branch is held by the
main loop's worktree. So `checkout <branch>` in an agent's worktree fails. This is a git constraint,
not a project policy, and it is the actual reason agents commit to `worktree-agent-<id>` at all.

What works is starting *from* the branch without owning the ref:

```sh
git worktree add --detach <path> <branch>      # detached at the branch tip
git worktree add -b worktree-agent-<id> <path> <branch>   # own branch, based there
```

Both give the agent the branch's content. Only the second gives it somewhere to commit, which it
needs.

### Correction 2 — commits do *not* land on the branch, and the fix is better than that

An agent's commits land on `worktree-agent-<id>`. The branch gets them at harvest. **But if the
worktree starts at the branch tip, the harvest becomes a fast-forward instead of a cherry-pick** —
and that is the material gain:

| | base at `origin/main` (today) | base at the branch tip |
|---|---|---|
| harvest | cherry-pick | `git merge --ff-only worktree-agent-<id>` |
| shas | rewritten | **preserved** |
| does the branch register as merged? | **never** | **yes** |
| `git branch -d` | refuses; needs `-D` | works |
| "is this branch harvested?" | **unanswerable** | answered by git |

That last row is the 2026-09-27 defect at its root: 67 agent branches against 58 real ones, with no
way to tell a harvested branch from an unharvested one, *because the harvest was a cherry-pick.*
`AGENTS.md` rule 1 prescribes cherry-pick and deletion-at-harvest as the mitigation. **Under
branch-based dispatch the mitigation is unnecessary** — git answers the question itself.

### We are accidentally most of the way there already

Every agent's first action is `git merge --ff-only <named tip>`, so **its branch is already a
descendant of the branch tip.** Verified on the in-flight fix agent: `git merge-base --is-ancestor`
confirms its branch descends from the tip it was given, and the harvest could have been a
fast-forward. **I cherry-picked all four of this session's harvests anyway**, following rule 1 — which
was written when agents started at `origin/main` and a cherry-pick was the only option.

So one change to rule 1 captures most of the benefit with no configuration at all: **prefer
`git merge --ff-only` when the agent's branch descends from the feature branch tip, and fall back to
cherry-pick when it does not.**

### The one constraint this adds, and I broke it today

**A fast-forward harvest requires the main loop not to advance the branch while an agent holds it.**
I committed four plan commits to this branch during the fix round, so its tip moved past the agent's
base and the agent's branch no longer fast-forwards in. That harvest has to be a cherry-pick or a
real merge, and it is my doing, not a flaw in the scheme.

Either the main loop stops committing to a branch while an agent works on it, or it accepts
cherry-pick whenever it has. The first is cheap discipline with a mechanical check
(`git merge-base --is-ancestor <agent-branch> <branch>` before committing); the second is the status
quo. **Worth stating in the rule rather than discovered per harvest.**

### Worktree lifetime — the user's open question

Different answers for the two kinds, and the reason is what `git worktree list` should mean:

- **Agent worktrees: close at harvest.** Then `git worktree list` means "work in flight", which is
  the signal the branch accumulation destroyed. Unchanged from today, and the plain
  `git worktree remove` refusal on untracked files stays the safety check.
- **Feature worktrees (the main loop's): keep until merge.** That is where the work lives, and the
  user's own case for this change — being able to check out a branch at the root to fly it — depends
  on the branch's working copy continuing to exist somewhere else.

With both, `git worktree list` becomes the honest answer to "what is going on right now", which is
an argument for naming feature worktrees after the feature rather than after an agent id.
