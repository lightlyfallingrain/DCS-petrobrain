# Agent worktrees land on a stale base, five times out of five

Queued 2026-10-09, by user direction, after the round-4 reviewer flagged it as *"worth acting on at
the infrastructure level"* rather than corrected per dispatch. Nothing here is started.

## The observation

Every agent dispatched in the 2026-10-09 session landed on `29217c0` — `main`'s tip — rather than
the tip it was told to work at:

| dispatch | named tip | got | behind by |
|---|---|---|---|
| Stage 2 (body-layer roadmap) | `b7faa4d` | `29217c0` | 7 commits |
| Stage 3 (backlogs + todo) | `4b08b52` | `29217c0` | 1 |
| Stages 4–5 (three roadmaps) | `004a1cd` | `29217c0` | 26 |
| Review round 4 | `6c0325b` | `29217c0` | 34 |
| Round-4 fixes | `2856770` | — | (in flight at time of writing) |

**All five reported it and corrected with `git merge --ff-only`, which is the rule working.** This is
not a case of silent wrong-base verification — `AGENTS.md` rule 4 caught it every time. It is a case
of a correction firing so reliably that it should be unnecessary.

**Why it is worth fixing anyway, and the reason is not the wasted calls.** In three of the five, the
stale base did not merely lag — **none of the primary input documents existed in the tree as
created.** Stage 3's and Stages 4–5's inputs (`docs/DOC_CONVENTIONS.md`,
`plans/obsidian-links-and-tags/implementation.md`, the converted `ROADMAP/` directories) were absent
entirely. The rule's "is everything I was told to read present" half is what covered that, and it
covered it because each agent happened to check. The failure mode if one did not is an agent
confidently doing the work against documents that do not exist, which is the 2026-09-27 class of
defect the rule was written for.

## RESOLVED 2026-10-09 — the cause is `origin/main`, and it is neither candidate below

`git reflog show worktree-agent-a8670f1ca75f53a4a`:

```
2856770 …@{0}: merge 2856770…: Fast-forward
29217c0 …@{1}: branch: Created from origin/main
```

**Agent branches are created from `origin/main`.** Not from the project root's HEAD, not from local
`main`, not from the dispatching session's HEAD. The distinguishing test described below is answered
and does not need to be run.

Three consequences:

1. **Candidate fix 1 — "do feature work in the main checkout" — would not have worked.** Where the
   main loop sits is irrelevant; so is what the project root has checked out. It was marked
   conditional on cause 1, and cause 1 is false.
2. **Candidate fix 2 is the only one that helps**, and it is now the whole of the work: have
   `.claude/scripts/agent-sha-gate.sh` compute the dispatching session's `HEAD` and inject it as the
   sha to name, rather than relying on the dispatcher to type it. Under this cause a stale base is
   not an accident to be detected — it is the **guaranteed** starting state for any dispatch whose
   target is not `origin/main` itself, which is every feature-branch dispatch there will ever be.
3. **A latent hazard this exposes, worth the hook knowing about.** The base is the *remote-tracking*
   ref. Local `main` and `origin/main` were identical all session (`git rev-list --left-right
   --count main...origin/main` → `0 0`), so it never bit — but **work merged to local `main` and not
   yet pushed puts every agent behind even local `main`**, with nothing in the dispatch naming a sha
   that exists only locally. A dispatch should either verify `main` is pushed or name a sha reachable
   from `origin/main` plus the branch.

### Bearing on the "all work in worktrees" direction (user, 2026-10-09)

> *"It would actually be more convenient for me if **all work** is done via worktrees. That would
> then free the root dir to be whatever branch I happen to need for testing. Or, most probably,
> `main` where I could also add user input documents without disturbing the ongoing agentic work."*

**That direction is independent of this problem and can be adopted on its own merits.** Because the
base is `origin/main` regardless, freeing the root dir neither fixes nor worsens the stale base. The
earlier draft of this plan implied the two were coupled — they are not. See
`plans/all-work-in-worktrees/plan.md`.

## The mechanism — superseded by the section above, kept for the probe it records

> **Superseded by "RESOLVED" above.** This narrowed the cause to two candidates and specified a test
> to distinguish them; the reflog answered it instead, and neither candidate was right. Kept because
> the probe it records — a worktree created from a session's own working directory defaults to that
> session's HEAD — is a true fact that the resolution does not contain, and it is what rules out any
> fix based on where the main loop sits.

**A new worktree created from *this* session's working directory defaults to *this* session's HEAD.**
Probed directly: `git worktree add --detach <scratch>` run from the `doc-conventions` worktree
produced `HEAD is now at 2856770`, the correct tip.

**Yet five harness-created worktrees landed on `main`'s tip.** So worktree creation is not based on
the dispatching session's HEAD. The two candidate causes:

1. **It is run with the project root as cwd** — `/Users/sg/Code/DCS-petrobrain`, the main checkout,
   which sat on `main @ 29217c0` untouched for the whole session.
2. **It explicitly bases the worktree on the default branch**, independent of any cwd.

Both predict `29217c0` here, so this session cannot distinguish them.

**The distinguishing test, owed before implementing anything:** put the main checkout on a branch
other than `main`, dispatch a trivial agent from a *second* worktree on a *third* branch, and read
what its HEAD is. Cause 1 predicts the main checkout's branch; cause 2 predicts `main`. One
throwaway dispatch answers it.

**Caveat on the fifth row:** the in-flight agent's worktree reads `2856770` in `git worktree list`,
which is the correct tip — but it may already have self-corrected with `--ff-only` before that was
read. It is not evidence either way, and should not be treated as such.

## The underlying condition, which is the part worth noticing

**The main loop spent this entire session working in a secondary worktree** (`.claude/worktrees/doc-conventions`),
with the feature branch checked out there and the main checkout left on `main`. That is itself
contrary to `AGENTS.md` rule 3 — *"The main checkout belongs to the main loop and the user"* — and it
is what made the main checkout stale from every agent's perspective. The session's environment
placed it there and instructed it not to `cd` to the repository root, so this was not a choice made
in the moment; but the consequence is exactly the five rows above.

It also breaks the other half of rule 3's companion rule: **the main checkout's branch is a contract
with the user.** Theirs sat on `main` all day while 34 commits of work accumulated on a branch they
would have had to know the name of to find.

## Candidate fixes, cheapest first

1. **Do feature work in the main checkout, not a secondary worktree.** If cause 1 holds, this fixes
   the problem outright and for free: the project root's HEAD becomes the feature branch tip, so
   every agent worktree starts there. It also restores rule 3 and the user-facing contract. **Free if
   cause 1 holds, no help at all if cause 2 does** — hence the test above comes first.
2. **Compute the sha instead of typing it.** `.claude/scripts/agent-sha-gate.sh` already fires
   `PreToolUse` on `Agent`. It could compare the dispatching session's `HEAD` against the project
   root's `HEAD` and, when they differ, inject the dispatching session's sha as the one to name —
   turning a rule the dispatcher must remember into a value the hook supplies. This works under
   either cause and does not depend on the test.
3. **Keep `--ff-only` as the backstop regardless.** It cannot lose work, cannot pick up anything the
   dispatcher did not name, and is the only thing that helps when the base is stale for a reason
   nobody anticipated. Nothing here should remove it.

**Recommendation:** run the test, then 1 if it applies, and 2 in either case. 2 is the durable half —
it removes a remembered step rather than a symptom, which is this project's stated preference.

## Not to be done

- **Do not fast-forward `main` to make agents land correctly.** That merges unreviewed work to make
  tooling convenient, which is the wrong trade in the wrong direction.
- **Do not remove or weaken `AGENTS.md` rule 4.** It is what caught all five. The compaction on
  2026-10-09 already moved its *evidence* out while keeping the procedure; the procedure stays.
