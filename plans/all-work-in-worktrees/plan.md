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
