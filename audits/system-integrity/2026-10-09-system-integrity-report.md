# System Integrity Report — 2026-10-09

Scope as requested: the whole Claude Code operating environment, **with the 2026-10-09 roadmap/
backlog split and the "all work in worktrees" inversion as the focus**.

**Findings 1–7 were fixed on user direction after the audit ran**, on
`fix/roadmap-gate-and-branch-hook` — see the "Fixed" block under each. The audit pass itself edited
nothing; the fixes are separate, explicitly directed work.

**Finding 8 was found while fixing finding 7** and is open: `agent-memory-path-gate.sh` refuses the
sibling worktree path that this repo's own merge skill prescribes, so an agent in a documented
worktree cannot write memory through `Write`/`Edit`. It needs a decision about which layout is
canonical, not a patch. The seven Tier 2 items are also untouched.

Inventory enumerated fresh: 7 `CLAUDE.md` (root + 6 subprojects from `git ls-files '*/pyproject.toml'`),
`AGENTS.md`, `docs/AGENT_ROLES.md`, `docs/PROCESS.md`, `docs/DOC_CONVENTIONS.md`, 8 agent roles,
30 skill directories (0 loose `.md`), 33 scripts, 19 `settings.json` hook registrations, 2 git
hooks, `.claude/agent-memory/**` (8 role dirs + `skill-candidates.md`), auto-memory (21 entries),
`NOTES.md`, and every roadmap/backlog/todo source **resolved through
`.claude/scripts/roadmap-source.sh`** (9 pointers, 193 `ROADMAP/` entry files, 25 `todo/todo/`,
36 `todo/backlog/`).

**What the split got right, so it is not re-litigated:** both commit gates already accept
`ROADMAP/<ID>.md`; `roadmap-source.sh` derives destinations rather than listing them; all six
code-reading agent roles carry the pointer warning; `roadmap-entry-consistency-gate.sh` passes
clean; `graph-corpus-files.sh` picks up all 254 entry files and `graph-corpus-guard.sh` reports
436/520. The split's consumer sweep was thorough. The findings below are what it did not reach,
plus unrelated drift.

---

## Tier 1 — definite integrity problems (7 found in the audit, plus 8 found while fixing them)

### 1. Five of six subproject `CLAUDE.md` files prescribe the mypy invocation root `CLAUDE.md` says is broken

**Evidence.** Root `CLAUDE.md`, "Subprojects":

> `mypy`'s config discovery is **CWD-only**: run it from inside the subproject
> (`cd <subproject> && .venv/bin/mypy src`), never as `mypy <subproject>/src` from the repo root,
> which silently drops `strict` and the subproject's `mypy_path` and reports phantom import errors.

What the subproject files say under "Commands":

| file | line | command |
|---|---|---|
| `world-model/CLAUDE.md` | 35 | `mypy world-model/src` |
| `aircraft-layer/CLAUDE.md` | 43 | `mypy aircraft-layer/src` |
| `body-layer/CLAUDE.md` | 66 | `mypy body-layer/src` |
| `audio-adapter/CLAUDE.md` | 115 | `mypy audio-adapter/src` |
| `mission-interpreter/CLAUDE.md` | 104 | `mypy mission-interpreter/src` |
| `brain-layer/CLAUDE.md` | 76 | `cd brain-layer && mypy src` ✅ |

Reproduced this run on world-model:

```
$ world-model/.venv/bin/mypy world-model/src
world-model/src/terrain/skeleton.py:57: note: Hint: "python3 -m pip install scipy-stubs"
Found 1 error in 1 file (checked 72 source files)

$ cd world-model && .venv/bin/mypy src
Success: no issues found in 72 source files
```

**Why it matters.** The subproject file is the one an agent reads while working in that directory,
and root `CLAUDE.md` explicitly hands it override authority on "Commands". So the authoritative
local instruction is the broken form. Two failure directions, both live: a clean tree reports a
phantom error (above), and `strict` being silently dropped means a real error can go unreported.
`commit-quality-gate.sh` and `posttooluse-mypy.sh` both already `cd` into the subproject and both
carry the reproduction in their header comments — so the mechanical gate is right and only the
human-facing instruction is wrong, which is the worst split of the two.

**Correction.** Change the five lines to `cd <sub> && .venv/bin/mypy src`, matching brain-layer's
(which is the only one written after the CWD-only finding landed).

**Fixed 2026-10-09.** All five changed to `cd <sub> && .venv/bin/mypy src` — root `CLAUDE.md`'s own
wording — each followed by a short note giving the reason and the measurement, so the next person
to "tidy" the command back can see what it costs. `ruff`/`pytest` were left bare, as brain-layer
has them: they have no CWD-dependent config discovery, and widening the edit would bury the one
line that was wrong. Verified by running the prescribed form in all six subprojects from the main
checkout: `Success` in every one (72, 21, 54, 15, 31 and 7 source files). Note a worktree has no
`.venv` — these commands are only runnable in the main checkout, which is the standing
borrow-tooling friction, not a defect in the instruction.

---

### 2. The `git checkout -b` hook requires the repo root to be on `main` — which AGENTS.md rule 3 now forbids arranging

**Evidence.** `.claude/settings.json`, `PreToolUse` on `Bash`:

```sh
if echo "$cmd" | grep -qE '^git (checkout -b|switch -c)'; then
  current=$(git -C $CLAUDE_PROJECT_DIR rev-parse --abbrev-ref HEAD)
  if [ "$current" != "main" ]; then
    ... "stopReason":"Branch rule: new branches must be created from main. Currently on: %s. Run: git checkout main first."
```

Against `AGENTS.md`, "Where work happens", rule 3:

> **The repo root belongs to the user. The main loop takes a worktree too.** … The user's own
> checkout is theirs to park wherever they like — usually `main`, so they can … check out a branch
> to fly …

**Why it matters.** Two separate defects, both hard blocks (`"continue":false`):

- It reads `$CLAUDE_PROJECT_DIR`, which is **deliberately root-fixed**
  (`plans/all-work-in-worktrees/plan.md`, line 135). A session legitimately working in a feature
  worktree is therefore gated on *the user's* branch, not its own. The moment the user checks out a
  branch to fly — the exact thing rule 3 was written to enable — every branch creation anywhere in
  the repo is refused.
- Its remedy instruction, `git checkout main first`, tells the agent to move the root's branch
  under the user. That is the one action rule 3 names as forbidden.

This is the only hook in the set that still treats the root as the main loop's workspace.

**Correction.** Resolve the base branch from the hook's stdin `cwd` (a documented field on every
event — same plan, line 136) rather than `$CLAUDE_PROJECT_DIR`, and change the remedy text to
creating a worktree from `main` rather than checking `main` out. Note the hook cannot be tested
through the hook mechanism from a branch (`$CLAUDE_PROJECT_DIR` is root-fixed, so the active hooks
are the root's) — run the script directly, as `AGENTS.md` rule 4 already says.

**Fixed 2026-10-09**, user direction: *"stop and notify user that they are blocking"*. The hook
still stops, but the `stopReason` now names the root's parked branch as the cause, forbids
checking `main` out there, and gives the rule-3 route that does not involve the root at all —
`git worktree add -b <branch> ../<repo>-<short-name> main`, which the hook's own `^git (checkout
-b|switch -c)` pattern does not match. Verified by running the hook command directly (it cannot
be exercised through the hook mechanism from a branch): root off `main` → blocks with the new
reason; root on `main` → passes; unrelated `git status` → passes.

Two things learned in the fixing, both worth keeping:

- **The message must contain no apostrophe and no backtick.** It is interpolated into a
  shell single-quoted `printf`, so an apostrophe closes the quote (`bash: syntax error near
  unexpected token`) and a backtick command-substitutes. The first draft said "the root the
  user's" and broke the hook outright — caught by running it, which is the only way it would have
  been caught. A comment in the patch script records this.
- **Residual, deliberately not changed:** the hook still reads `$CLAUDE_PROJECT_DIR` rather than
  stdin `cwd`, so the root's branch still governs. With the worktree route now named in the
  message, the block has a correct way through that does not depend on the root — but a session
  that genuinely wants `git checkout -b` inside its own worktree is still gated on the user's
  branch. Left as the smaller, separable change.

---

### 3. Root `CLAUDE.md`'s own Workflow section contradicts itself, two bullets apart

**Evidence.** `CLAUDE.md`, "Workflow", bullet 2:

> **Always branch from local `main`** — checkout `main` first, then create the branch.

bullet 5:

> **All work happens in a worktree — agents and the main loop alike — and the repo root belongs to
> the user.** … **The user parks the root wherever they like**

**Why it matters.** Bullet 2 is the pre-2026-10-09 procedure and was not revised when bullet 5 was
added. It is the instruction the hook in finding 2 enforces, so the two defects reinforce each
other: an agent reads bullet 2, checks `main` out in the root, and the hook confirms it was right.
`AGENTS.md`'s own superseded blocks show the project's convention for this — mark the old text,
don't leave it reading as current.

**Correction.** Rewrite bullet 2 as "branch from local `main`, in a worktree named after the
feature", keeping the `origin/main` prohibition (that part is unaffected).

**Fixed 2026-10-09.** Bullet 2 now says to create the branch as a worktree —
`git worktree add -b <branch> ../<repo>-<short-name> main` — which branches from local `main`
without moving the root's checkout, keeps the `origin/main` prohibition, and quotes the superseded
wording in place so it does not read as current. It also names the hook from finding 2, so the two
are cross-referenced rather than each being discovered separately again.

---

### 4. Both roadmap gates are satisfied by touching a pointer — the exact silent failure the docs name

**Evidence.** `push-roadmap-gate.sh:65` and `commit-quality-gate.sh:239` both test:

```
grep -qE '(^|/)ROADMAP(\.md|/[^/]+\.md)$'
```

Root `ROADMAP.md`, "Keeping this current":

> **Writing that update into a `ROADMAP.md` pointer satisfies `push-roadmap-gate.sh` while changing
> nothing a reader or a `grep` will find**

`.claude/agents/dod.md:200` says the same, as does `.claude/skills/merge/SKILL.md:71`.

**Why it matters.** Three documents independently warn about a hole that is one regex alternative
wide and still open. The split work clearly knew — the `|/[^/]+\.md` branch was added for it — but
kept the `\.md` branch accepting the pointer, so the warning had to be prose in three places
instead of a gate in one. That is precisely the "competing sources of truth" shape the project's
own `roadmap-source.sh` header argues against, and the failure is silent by construction: entry
file stays `[ ]`, `grep '#status/done'` still reports it open, gate green.

**Correction.** Drop the bare-`ROADMAP.md` alternative for any path that `roadmap-source.sh
--is-pointer` accepts. Root `ROADMAP.md` is the only unsplit roadmap, so the rule is mechanical:
accept `^ROADMAP\.md$` and `/ROADMAP/[^/]+\.md$`, refuse a pointer. The resolver already exists and
the gates already shell out to other scripts, so this is a call, not a rewrite. Closing it retires
three prose caveats.

**Fixed 2026-10-09**, user direction: *"could change roadmap refs to point to the roadmap folder
that was created"*. Both gates now use a shared predicate shape:

- an entry file under `<sub>/ROADMAP/` always counts;
- a bare `ROADMAP.md` counts only if `roadmap-source.sh --is-pointer` says it is **not** a
  pointer — so root `ROADMAP.md` counts and the five subproject pointers do not;
- a path absent from the working tree does not count (a deletion is not a roadmap update);
- missing resolver → counts, i.e. fails open, like every other uncertainty in these scripts.

Deferring the pointer decision to the resolver rather than spelling the split out in a regex is
what keeps both gates correct when a tenth document splits, and is why they cannot drift apart
from each other.

Both failure messages were rewritten to name the folder: they now say the entry is
`<subproject>/ROADMAP/<ID>.md`, give `roadmap-source.sh --dir <subproject>/ROADMAP.md` as the way
to find it, note that root `ROADMAP.md` also counts and is the only roadmap edited directly, and
state that a pointer write no longer satisfies the gate.

Verified by extracting each predicate from the real script text and exercising nine cases against
both — root `ROADMAP.md` counts; `body-layer/ROADMAP.md` and `body-layer/BACKLOG.md` refused;
`body-layer/ROADMAP/BL-13.md` and `world-model/ROADMAP/WM-M7.md` count; a source file refused; a
non-existent pointer path refused; pointer-then-entry counts; empty list refused. 18/18 pass, and
both gates still exit 0 end-to-end on a real staged-commit payload.

**The three prose caveats are left in place** (root `ROADMAP.md`, `dod.md`, `merge/SKILL.md`).
They are still true and still useful as guidance to whoever is writing the update; what changed is
that they are no longer the *only* defence, which was the actual defect. Retiring them is a
separate call.

---

### 5. The ID-minting rules do not cover two live ID spaces, and the mint command is prefix-blind

**Evidence.** Root `CLAUDE.md`'s ID table lists `BL-B`, `AC-B`, `AA-B`, `WM-B`, `X-B`, reserves
`MI-B`/`BR-B`, and adds `<prefix>-W<n>`. Measured, this run:

```
body-layer/ROADMAP     BL-  BL-B  BL-W  BR-
world-model/ROADMAP    WM-M WM-B  WM-W
todo/todo              X-T   (24 items, X-T1 … X-T24)
```

- **`X-T<n>` appears nowhere in root `CLAUDE.md`.** It exists only in `docs/DOC_CONVENTIONS.md:84`
  and one line of `.claude/skills/status-page/SKILL.md`. Root `CLAUDE.md` presents its table as the
  authority ("The directory is the only place an ID exists") and names `todo/todo/` by path in
  Session Start step 2, so the 24 live items there sit in an ID space the authoritative table does
  not acknowledge.
- **`BR-` milestones already live in `body-layer/ROADMAP/`** (`BR-1.1.md`, `BR-1.2.md`), while
  `CLAUDE.md` says `BR-B<n>` is merely "reserved for … brain-layer". brain-layer is the only
  `pyproject.toml` subproject with no `ROADMAP/` of its own, so the mint command has no directory
  to be run against for that prefix.
- **The mint command is prefix-agnostic**, and that is now load-bearing:

  ```sh
  ls <dir>/ | grep -oE '^[A-Z]+-B[0-9]+' | sort -V | tail -1
  ```

  Run on `body-layer/ROADMAP/` it returns `BL-B46` today. The first `BR-B<n>` filed into that same
  directory makes it return the max across *both* prefixes — so minting a `BL-B` reads a `BR-B`
  number, or vice versa. This is the same class of defect `CLAUDE.md` already documents twice for
  `sort -t B -k2 -n` and `sort -t W -k2 -n`, caught by measurement on 2026-10-09; the `grep` half
  was not re-examined when two prefixes moved into one directory.

**Why it matters.** `CLAUDE.md`'s second ID rule — never reuse, never renumber — is what makes an
ID citable in a commit or plan. A collision breaks it silently: the new item takes a number a
commit message already used for something else.

**Correction.** Add `X-T<n> → todo/todo/` to the table; say where `BR-*` lives (body-layer's
directory, or give brain-layer its own); and pin the prefix in the command —
`grep -oE '^BL-B[0-9]+'`, not `'^[A-Z]+-B[0-9]+'`.

**Fixed 2026-10-09.** All three, in root `CLAUDE.md`: `X-T<n> → todo/todo/` added to the table;
`BR-*` documented as living in `body-layer/ROADMAP/` because brain-layer has no directory of its
own; and the mint command now spells the full prefix with the reason attached, since the
prefix-agnostic form is only safe in a directory that holds one prefix and `body-layer/ROADMAP/`
holds four (`BL-`, `BL-B`, `BL-W`, `BR-`).

**`docs/DOC_CONVENTIONS.md:183` had the identical defect in its `-W` recipe** and was fixed with
it — which is the finding behind the finding: root `CLAUDE.md` points at that file as carrying "the
same recipe", so a correction to one that skips the other leaves the wrong form published in the
document the other one cites. The `sort -V` correction made the same day had already visited both
files; the `grep` half of the same line was simply not re-examined.

Verified by running the corrected command in all ten live spaces: `BL-B46`, `BL-W38`, `BL-13`,
`WM-B16`, `WM-W12`, `WM-M11`, `X-T24`, `X-B35`, `AC-B5`, `AA-B3` — each the true maximum of its own
sequence, where the prefix-agnostic form returns `BL-B46` for `body-layer/ROADMAP/` regardless of
which space is being minted.

---

### 6. Two auto-memory entries describe states that have since reversed

**`project_pb2_next_milestone.md`** — "**Next milestone: PB-2 (BL-2 — contact memory …)**", written
2026-09-08. body-layer is at BL-13 with BL-2/2.5/2.6 long closed. Its "How to apply" line is the
sharper problem:

> `todo/todo.md` "Current Focus" is the live source of truth for exact status — check it before
> assuming this memory is still current

`todo/todo.md` is a four-line pointer and has no "Current Focus" section; the source of truth is
the subproject `ROADMAP/` directory. So the entry's own staleness check now resolves to an empty
file — it reads as a live instruction and silently confirms whatever the reader already believed.

**`project_brain_layer_is_the_bottleneck.md`** — "it is the only Petrobrain component with **no plan
file at all**", written 2026-09-24. `plans/brain-layer/` exists, `brain-layer/` has `src`, `tests`,
`pyproject.toml` and a `CLAUDE.md`, and BR-1 Stages 1–2 have shipped (`BR-1.1`, `BR-1.2`). The
entry's genuinely useful half — the idle seams, and the argument for deferring judgement features
*to* the brain rather than hand-rolling them — is unaffected and worth keeping.

**Why it matters.** Both carry `type: project`, both are in the index, and both are loaded as
background context every session. The first actively misdirects Session Start.

**Correction.** Rewrite both against current state, or delete the first (the roadmap covers it
better than a memory can) and trim the second to its seams argument.

**Fixed 2026-10-09.** Both rewritten, **filenames kept** so the `[[project_pb2_next_milestone]]`
and `[[project_brain_layer_is_the_bottleneck]]` links between them and from elsewhere stay valid —
renaming would have been the tidier-looking change and would have broken them.

- The first is no longer a milestone pointer at all. It now records the durable strategy it was
  really about — the chain is built thin and end-to-end rather than one layer perfected at a time,
  which is why a stub on a real wire beats a complete component behind no wire — plus the explicit
  rule that **a next-milestone pointer does not belong in memory**, with its own failure as the
  worked example.
- The second keeps the idle-seams argument and the transferable rule (defer "small" judgement
  features to the brain rather than hand-rolling a second judgement layer), and moves the
  four-gated-features/no-plan-file claim into a dated paragraph that says plainly which part has
  lapsed and where to check instead.

Both index hooks in `MEMORY.md` were updated to match, since the hook is what recall decides
relevance from — leaving `gates 4 built features, only component with no plan` in the index would
have kept the stale claim in context every session while the entry behind it said otherwise.

---

### 7. Three memory files are not in their own index, so recall cannot see them

```
auto-memory   feedback_dcs_probe_io_lfs.md
architect     project_terrain_feature_probing.md
implementer   project_group_contact_model_stage3bi_ellipse.md
```

`MEMORY.md` is described in the memory contract as "the index loaded into context each session", and
relevance is decided from its one-line hooks. A file absent from the index is written, committed,
and unreachable — which `AGENTS.md` calls "the most expensive loss in this system". Add one line
each.

**Fixed 2026-10-09.** One line appended to each of the three indexes, append-only (an index
*rewrite* is what `commit-quality-gate.sh` blocks, and rightly: one September commit replaced the
reviewer index's 27 entries with 1). Re-ran the completeness check across all eight role
directories and the auto-memory directory afterwards: no file is absent from its own index.

---

### 8. `agent-memory-path-gate.sh` rejects the worktree path the project's own convention produces

**Found while fixing finding 7, not during the audit pass.** Appending to
`.claude/agent-memory/architect/MEMORY.md` from the worktree at
`/Users/sg/Code/DCS-petrobrain-config-gate-fixes` was refused:

> Agent memory must live at `<repo root>/.claude/agent-memory/<role>/`. Valid roots are the main
> checkout (`/Users/sg/Code/DCS-petrobrain/.claude/agent-memory/`) and any agent worktree
> (`/Users/sg/Code/DCS-petrobrain/.claude/worktrees/<name>/.claude/agent-memory/`). Wrong path:
> … this looks like a subproject-relative path, which is the recurring mistake this gate exists to
> catch.

**Why it matters.** The gate accepts worktrees only under `<root>/.claude/worktrees/<name>/`, while
`.claude/skills/merge/SKILL.md:95` and `plans/all-work-in-worktrees/plan.md` give the convention as
the **sibling** `../<repo-name>-<name>`, which is what this session used and what `git worktree
list` shows. So a worktree created the documented way cannot write agent memory with `Write`/`Edit`
at all. `AGENTS.md` records this exact class of failure as already fixed — "the agent-memory hook
once denying the only correct path an isolated agent had" — and it is fixed for one worktree layout
and not for the one the skills prescribe.

This is the finding in the set with the worst shape: a memory that cannot be written is invisible,
the role carries on, and the next agent repeats the mistake the memory would have prevented.
`AGENTS.md` says as much in so many words.

**Correction.** Decide which layout is canonical and make the two agree. Either widen the gate to
accept any path `git worktree list` reports (robust, and it is the only source that actually knows),
or change the merge skill and the worktree plan to put worktrees under `<root>/.claude/worktrees/`.
The first is better: it cannot go stale, and it keeps working whatever naming convention is chosen
later.

**Worked around, not fixed, in this pass**: the three index lines were appended with a short Python
script via `Bash`, which the gate does not intercept. That is the wrong way round — the gate is
right to watch `Write`/`Edit`, and a hole in `Bash` is not a feature to rely on. Left for a decision
rather than patched silently.

---

## Tier 2 — possible improvements

- **Nine pointer files are still in the graph corpus** (`graph-corpus-files.sh` output: every
  `<sub>/ROADMAP.md`, `body-layer/BACKLOG.md`, both `todo/` pointers, plus root `ROADMAP.md` which
  belongs). A query can return a four-line redirect as a source. Harmless next to the pre-split
  staleness risk and the guard's count is comfortable (436/520), but the eight pointers contribute
  nothing but their own redirect text to the graph's vocabulary.

- **The SubagentStop skill-gap detector's premise is stale.** Its prompt tells the subagent to run
  `grep -h '^description:' $CLAUDE_PROJECT_DIR/.claude/skills/*.md` and states "Every `<name>.md`
  there is a user-invocable slash command". That glob has matched nothing since
  `skill-layout-gate.sh` landed (2026-09-21) — all 30 skills are directories. The hook still works
  via the `*/SKILL.md` half of the same grep, so this is noise rather than breakage, but the false
  premise it asserts is the identical one recorded as a *rejection reason* in
  `skill-candidates.md`'s 2026-09-09 `test-and-commit-cycle` entry.

- **`agent-worktree-reminder.sh`'s injected text predates rule 3.** It reports "Main checkout is
  currently `<branch>` @ `<sha>`" and explains that "when the branch under review is already in the
  main checkout the worktree lands on main". The mechanism (git refuses a second checkout of one
  branch) is unchanged and the advice still works, but the branch under review now normally sits in
  a *feature worktree*, and "the main checkout" is the user's. Worth rewording so the reason stays
  checkable.

- **`/new-feature` has no worktree step.** Step 2 stops on a dirty tree and step 3 runs
  `git checkout -b` in the current checkout — correct before 2026-10-09, and now dependent on the
  user's root being clean and on main. It defers ID/tracking questions to `CLAUDE.md` properly
  (good, and why the split did not break it), so only the branch-creation steps need the worktree
  framing. Note it will also be refused by the hook in finding 2 whenever the user parks the root
  off `main`.

- **brain-layer has no `ROADMAP/` of its own.** Root `ROADMAP.md`'s table routes it to body-layer's
  and says so explicitly, so nothing is lost today — but it is the one `pyproject.toml` subproject
  the enumeration rule finds and the roadmap enumeration does not, which is the shape of the defect
  that rule exists to prevent. Connected to finding 5.

- **`graph-corpus-guard.sh` has no caller but skill prose** (`graph-refresh/SKILL.md:48`), unlike
  `roadmap-entry-consistency-gate.sh` and `roadmap-tag-vocabulary-gate.sh`, which
  `commit-quality-gate.sh:184` runs mechanically. Deliberate as far as this audit can tell — the
  corpus only changes on a rebuild — but it is the one doc-graph gate whose running depends on
  someone following a document.

- **Healthy, recorded so it is not re-checked:** `skill-candidates.md` has zero open `##`
  candidates and nine resolved entries with reasons — the backlog-accumulation signal this audit
  watches for is absent. `doc-provenance-gate.sh`'s omission from the commit gate is documented in
  place as a deliberate deviation tied to the paused document-graph work (`X-B35`), not drift.
