# Agent worktree protocol — the incident record behind the rules

`AGENTS.md` "Where work happens" states the four rules and is always loaded. This file holds the
evidence: what went wrong, when, and what it cost. It is the same split as `AGENTS.md`'s role
one-liners against `docs/AGENT_ROLES.md`'s full detail.

**Read this when a rule looks like bureaucracy, when you are about to skip one, or when deciding
whether to change one.** Nothing here is needed to *follow* the rules — `AGENTS.md` has those, and
`.claude/scripts/agent-worktree-reminder.sh` plus `agent-sha-gate.sh` reprint the addressing half at
every `Agent` dispatch. It is needed to know why they are not negotiable.

Moved out of `AGENTS.md` on 2026-10-09, verbatim, under the criterion in
`plans/always-loaded-compaction/plan.md`: a rule's evidence may leave the always-loaded file when a
hook delivers that rule at the point of use. Rule 4 qualifies. **Rule 1's harvest protocol does
not**, and its evidence deliberately stayed in `AGENTS.md` — the harvest happens after an agent has
already reported, which is after every dispatch hook, so nothing fires at the moment it matters.

---

## Rule 4 — wrong-base verification. Why the prompt must name a tip sha

### The three roles that were each burned separately (2026-09-27 integrity audit)

A worktree is created at *some* commit, and until the rule existed nothing said which. Git will not
check the same branch out twice, so when the branch under review is already in the main checkout,
the worktree lands on `main` — which predates the work. The agent then verifies the wrong code and
reports a plausible result:

| role | what happened |
|---|---|
| Reviewer | worktree based on `main`, so `body-layer/src` on disk was pre-fix code; a probe compared the fix against itself (`fix/position-belief-runaway`, 2026-09-25) |
| Definition of Done | pytest in the worktree reported `1177/4` — exactly `main`'s baseline — against the branch's own `1192/4`. The gate would have passed on `main` |
| Performance Reviewer | the worktree's HEAD (`6b8a86e`) was not even an ancestor of the tip the task named (`cdb8c7f`); `git log` looked entirely plausible |

**Every one of those is a silent wrong-code verification**, and the only thing that caught them was
three separate agent-memory files — which means it was being *re-learned*, per role, rather than
prevented.

### Worse than "it lands on `main`": it can land on neither tip (2026-10-06)

Two Architects dispatched minutes apart both got `19143fa` — **eleven commits behind** the `dce2534`
they were told to work at — with clean trees and nothing unique. Both caught it because the prompt
named a sha and they checked; neither could `git reset --hard` to the target (denied by
permissions), so one read every input document through `git show <tip>:<path>` instead, which is the
snapshot approach the rule prescribes and is worth knowing works for *documents* even when a
checkout does not.

Three agents hit this in one night and each handled it differently — one read its inputs through
`git show`, two fast-forwarded — which is what produced the rule's current shape: report first, then
`--ff-only` when and only when HEAD is a strict ancestor and the tree is clean, otherwise stop.
Stopping dead on a trivially correctable condition wastes a whole run, especially overnight when
nobody is awake to re-dispatch.

### A stale base means the agent's tooling is stale too

`gq.sh` was fixed on 2026-10-06 to let a worktree borrow the main checkout's graph (`c33af2e`) — and
the Architect based at `19143fa` still got *"No graph yet"*, because the fix was not in its tree.
**A fix to agent tooling only reaches agents whose base commit contains it, which is not the same
thing as "it is on `main`".**

### A stale base is harmless for source and dangerous for inputs

On that same occasion `git diff 19143fa dce2534 --stat` was docs and agent-memory only, so every
`src` file read was byte-identical — but those eleven commits included
`plans/post-review-fixes/explore-notes.md`, the agent's *primary input*, which simply did not exist
in its tree. **So the check is not "is the source the same", it is "is everything I was told to read
present".**

### It is routine, not exceptional (2026-10-09)

Three consecutive implementer dispatches in one session — Stages 2, 3 and 4–5 of the
`obsidian-links-and-tags` roadmap conversion — all landed on `main`, 1, 1 and 26 commits behind the
named tip. In the Stage 3 and Stage 4–5 cases **none of the primary input documents existed in the
tree as created**. All three reported it and fast-forwarded, which is the rule working. The point of
recording it: a stale base is the normal case for an agent whose target branch is checked out in the
main checkout, not a rare accident, so the `--ff-only` correction carries most of the traffic and the
"name the input documents" half is what catches the rest.

---

## Rule 1 — why `git worktree remove --force` is in the deny list

`--force` is not needed, and that was established by testing rather than assumed: a plain remove
succeeds on a clean worktree, succeeds when the only leftovers are **gitignored** build artifacts,
and refuses only when genuinely untracked files are present. **That refusal is the safety check** —
it fires in exactly the case where something unaccounted-for would be destroyed, so overriding it is
always either losing work or papering over a missing `.gitignore` entry.

The one artifact that ever forced it here was `*.egg-info/`, which agents generate by
`pip install -e .` and which no subproject `.gitignore` covered. Now they all do. A worktree whose
directory has already been deleted externally needs `git worktree prune`, not force.

## Rule 1 — why agent branches are deleted at harvest time

Nothing deleted them, and because the harvest is a cherry-pick they never register as merged, so
they accumulated permanently: by 2026-09-27 there were **67 against 58 real branches**, which broke
the Session Start state check (root `CLAUDE.md` step 4, now filtered) and — worse — left no way to
tell a harvested branch from an unharvested one. Deleting at harvest time makes the branch's
existence mean "not yet harvested", which is the signal the accumulation destroyed. The 41
already-ambiguous ones were left in place rather than guessed at.

## Rule 2 — what the worktree trial surfaced

Trialled on cones 2B (2026-09-21) and **worked** — the agent committed cleanly on its own branch,
reported the sha, and nothing raced. Two frictions surfaced:

- **The agent-memory hook denied the worktree path.** It allowed only
  `$CLAUDE_PROJECT_DIR/.claude/agent-memory/`, so an isolated agent had no correct move: write into
  the main checkout and violate rule 3, or skip the memory. 2B's implementer skipped it and
  *reported the contradiction*, which is how it was found — had it silently written to the main
  checkout instead, nobody would have noticed. `agent-memory-path-gate.sh` now accepts any worktree
  root while still denying subproject-relative paths, including a subproject path nested inside a
  worktree.

  **It recurred on 2026-10-09, and the sentence above is why it was not looked for.** "Accepts any
  worktree root" was written of a fix that accepted exactly one *layout* —
  `<project>/.claude/worktrees/<name>/` — and when rule 3 made every session take a worktree, the
  convention the skills prescribe became the **sibling** `../<repo-name>-<name>`
  (`.claude/skills/merge/SKILL.md`, `plans/all-work-in-worktrees/plan.md`). That layout was denied,
  so a worktree created the documented way could not write agent memory at all. Found by hitting
  it, again — not by the integrity audit that was running at the time, which read the gate and the
  skills as separate files and agreed with each.

  **The fix is to ask `git worktree list`, not to add a second prefix**, which is what this entry
  should have said the first time: git is the only thing that knows where the worktrees are, so the
  check cannot go stale the next time the convention moves — and it has now moved twice. The `git`
  call runs after both string comparisons, so the ~16 ms it costs lands only on a path that looks
  like agent memory and matched neither root; writes elsewhere are unaffected. Full account, with
  the before/after case table and timings: `audits/system-integrity/`, finding 8.

  **The transferable part: a fix described in general terms ("any worktree root") that is
  implemented for one special case will not be re-examined when the general case arrives.** The
  wording closed the question. Prefer describing what the code actually matches.
- **Bash heredocs and `>>` redirection are refused inside a worktree** ("too complex to verify it
  stays inside the worktree"). Not a bug to fix — use the `Edit` and `Write` tools for file content
  there, which is better practice anyway. This one stayed in `AGENTS.md` as a one-line rule, because
  an agent that does not know it discovers it mid-task and improvises.

A memory that is never written is the most expensive loss in this system, because its entire purpose
is to stop a later agent repeating a mistake. A hook that silently prevents one is worse than no
hook.

## Why the rules were inverted in the first place

The previous rule was the inverse — agents ran in the shared checkout and *side quests* went to a
worktree — and it failed the way rules relying on main-loop discipline fail: the main loop did a
bare `git checkout main` to write a document while an implementer was mid-task on a feature branch,
**twice in one session**, having quoted the rule at agents in between. A rule that must be remembered
at the exact moment attention is elsewhere will keep being broken. The current rules are structural
instead.

## A note that is not about agents: hooks fire from the checked-out branch

Hooks run from `$CLAUDE_PROJECT_DIR/.claude/scripts/`, i.e. **whatever the main checkout currently
has** — so while the main checkout sits on a feature branch that predates a hook fix, the *old* hook
is what fires. Observed 2026-10-06: a sha-gate fix was committed to `main` while the main checkout
was parked on `fix/los-hook-statics`, and the pre-fix gate stayed active for that whole session. If
a hook misbehaves right after you fixed it, check which branch the main checkout is on before
re-reading the script. Kept as a one-line pointer in `AGENTS.md`, because nothing announces it.
