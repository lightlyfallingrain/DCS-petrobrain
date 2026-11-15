# System Integrity Report — 2026-11-14

Scope: the whole Claude Code operating environment, **with the 2026-11-13 retro merge
(`8852fc2c`) as the focus** — `accepted-items-ledger.sh` and its hook, the `git checkout -- <path>`
refusal in `destructive-command-gate.sh`, the edits to five role files, and the file-list rebuild
recipe in `graph-refresh/SKILL.md`. Diagnostic only; nothing in the audited system was edited.

Inventory enumerated fresh: 7 `CLAUDE.md` (root + 6 subprojects from `git ls-files
'*/pyproject.toml'`), `AGENTS.md`, `docs/AGENT_ROLES.md`, `docs/PROCESS.md`,
`docs/BEHAVIOUR_ALIGNMENT.md`, `docs/DOC_CONVENTIONS.md`, 10 agent roles, 30 skill directories
(0 loose `.md`), 44 scripts, 20 `settings.json` hook registrations (19 + the new ledger), 2 git
hooks installed in the root, `.claude/agent-memory/**` (10 role dirs, 907 files, +
`skill-candidates.md`), auto-memory (27 entries), `notes/` (31 topic files), and every
roadmap/backlog/todo source **resolved through `roadmap-source.sh`**: 9 pointers (six
`<sub>/ROADMAP.md`, `body-layer/BACKLOG.md`, `todo/todo.md`, `todo/backlog.md`) over 280 `ROADMAP/`
entry files, 28 `todo/todo/`, 39 `todo/backlog/`. Root `ROADMAP.md` is the one non-pointer.

**Healthy, recorded so it is not re-checked:** every hook script `settings.json` names exists;
every path root `CLAUDE.md` cites exists; all six subproject `CLAUDE.md` files carry the
`cd <sub> && .venv/bin/mypy src` form; `mint-id.sh --list` derives 16 prefixes from the directories
(including `BR-`/`BR-B` in `brain-layer/ROADMAP/`, which now exists); `notes/`, `todo/todo/` and
`todo/backlog/` indexes are complete with no dangling links; `skill-candidates.md` has zero open
candidates; `GRAPH_REPORT.md` is dated 2026-11-13 18:27, i.e. rebuilt after the retro; the
graph-refresh recipe's inputs resolve (`~/.claude/skills/graphify/references/extraction-spec.md`,
`graphify-out/.graphify_python`; `.corpus.txt`/`.uncached.txt` are produced by the skill's own step
and deleted at **Finish**, so their absence at rest is correct); the `.checkout`/`restore` refusal
parses `-C`, `--staged`, `-b` and a leading ref correctly on reading, and reads the repo from the
payload's `cwd` — which is the pattern finding 1 is about.

---

## Tier 1 — definite integrity problems (5)

### 1. The commit-time gates inspect the root's index, so a commit made in a worktree is invisible to them — and the new ledger hook inherits this on day one

**Evidence.** All four `git commit`/`git push`/branch-delete hooks resolve the repository the same
way:

```sh
# commit-quality-gate.sh:16, push-roadmap-gate.sh:16, branch-delete-guard.sh:57, accepted-items-ledger.sh:34
REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0
...
STAGED=$(git diff --cached --name-only)          # commit-quality-gate.sh:19
features=$(git diff --cached --name-only ...)    # accepted-items-ledger.sh:88
```

`$CLAUDE_PROJECT_DIR` is **root-fixed** — `AGENTS.md` rule 4 (*"Hooks themselves fire from
`$CLAUDE_PROJECT_DIR/.claude/scripts/`, i.e. whatever the repo root currently has — documented and
deliberate"*) and `plans/all-work-in-worktrees/plan.md`'s table (*"`$CLAUDE_PROJECT_DIR`
per-worktree? No — deliberately fixed"*). It is always set when a hook runs, because every hook
command in `settings.json` is spelled `$CLAUDE_PROJECT_DIR/.claude/scripts/<name>` and would not
resolve otherwise. And since 2026-10-09 (`AGENTS.md`, "Where work happens", rule 3) **every commit
is made in a worktree**, never in the root.

Reproduced this run. A throwaway `plans/zz-ledger-probe/{plan.md,review.md}` (one accepted `U1`, no
`implementation.md`) was staged in this agent's worktree, and both scripts were fed the real hook
payload (`"cwd"` = this worktree) twice:

| `CLAUDE_PROJECT_DIR` | `accepted-items-ledger.sh` | `commit-quality-gate.sh` |
|---|---|---|
| `= <root>` (what a hook sees) | **silent pass** — `git diff --cached` in the root lists nothing | **silent pass** — same |
| unset (falls back to the worktree) | blocks: *"accepted U1 is never named in implementation.md"* | fires its memory-index advisory on the staged plan and review |

The probe files were unstaged and removed afterwards; the tree is clean.

**Why it matters.** The retro's headline mechanism — *"A record of a check is not the check; this
is the check"* (`accepted-items-ledger.sh` header) — does not run for the only commits it was built
to gate: a Reviewer or DoD agent committing `review.md`/`dod-check.md` in its `isolation:
"worktree"` checkout, with the session's `$CLAUDE_PROJECT_DIR` pointing at the root. The same hole
means `commit-quality-gate.sh` has not been running ruff/mypy/pytest on the staged diff of any
worktree commit since the inversion (it runs them on the root's — i.e. `main`'s — tree, which
passes), and `push-roadmap-gate.sh` has been checking the root's push. The one commit path that is
still gated is a session the user launches *inside* a feature worktree. Nothing announces the
miss: a passing hook and a hook that looked at the wrong index produce the same green.

**One bound on this claim, stated rather than assumed:** the probe sets `$CLAUDE_PROJECT_DIR`
explicitly rather than observing a live hook invocation from an agent worktree. The inference rests
on the root-fixed property both `AGENTS.md` and the worktree plan assert, and on the hook paths in
`settings.json` requiring it to be set. If a live capture ever shows `$CLAUDE_PROJECT_DIR` equal to
the agent's worktree, this finding collapses to "main-loop sibling worktrees only" — still the
common case for feature commits, still a defect.

**Correction.** Resolve the repository from the hook payload's `cwd`, which is a documented field
on every event and *follows the session* (same plan table) — exactly what the same retro's edit to
`destructive-command-gate.sh:36-37` already does:

```sh
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty'); [ -n "$cwd" ] || cwd=$(pwd)
REPO=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
```

Keep `$CLAUDE_PROJECT_DIR` for *locating sibling scripts* (`roadmap-source.sh`,
`roadmap-entry-consistency-gate.sh`), which is the one thing it is right for. Four scripts, one
line each; then re-run the probe above from a worktree with `$CLAUDE_PROJECT_DIR` set to the root
and expect a block. Record in `docs/AGENT_WORKTREE_PROTOCOL.md`'s "hooks fire from the checked-out
branch" note that the *index* a hook reads is a second, separate question from the *script* it
runs — that note covers only the latter.

---

### 2. Security's plan review was dropped 2026-10-30 and five places still require or advertise it

**Evidence.** `AGENTS.md:352` — *"Security's plan review left the sequences at the same time (user
direction, 2026-10-30: 'Drop the security between AR and I')"*; `security.md:85-87` — *"Mode 1 —
Plan Review (on demand only) … Dropped from the role sequences 2026-10-30"*. Against:

| where | text |
|---|---|
| `.claude/agents/dod.md:49` | checklist: `- [ ] plans/<featurename>/security-plan-review.md exists and is APPROVED` |
| `docs/AGENT_ROLES.md:137` | DoD checklist, same line |
| `.claude/agents/security.md:3` (frontmatter) | *"Use this agent to review security of a feature plan (after Architect) and …"* — and the example block rendered into the orchestrator's agent listing still says *"Security plan review runs after Architect and before Implementer starts work."* |
| `.claude/skills/dod-check/SKILL.md:274-278` | *"before treating a missing `security-review.md`/`security-plan-review.md` as a real FAIL, read root `CLAUDE.md`'s 'Agents' section for the scope currently set for `security`"* — root `CLAUDE.md`'s Agents section says nothing about the plan review; the drop is recorded only in `AGENTS.md` "Behaviour alignment" |
| `.claude/skills/plan-summary/SKILL.md:70` | lists `security-plan-review.md` in the expected plan-file table |

**Why it matters.** The DoD role file's own checklist asks for a document that no sequence
produces any more, so a DoD run that follows its checklist literally fails every feature, and one
that waives it does so by judgement each time. The `dod-check` skill tries to defer the call to a
document, and points at the wrong one. The frontmatter description is what the *dispatcher* reads
when choosing a role — it is the one place the drop most needed to land and the one it did not.

**Correction.** Remove the `security-plan-review.md` line from `dod.md:49` and
`AGENT_ROLES.md:137` (or mark it "on-demand only; absent is normal"); rewrite `security.md`'s
`description:` to lead with deep analysis before DoD and name plan review as on demand; make
`dod-check`'s note point at `AGENTS.md` "Behaviour alignment" (or at `security.md` Mode 1), which is
where the fact lives; drop the file from `plan-summary`'s table or label it optional.

---

### 3. The ledger's "reader's half" is assigned to `dod.md`, which never mentions it — and the DoD step that *does* look for recurring fixes reads a stub

**Evidence.** `accepted-items-ledger.sh:22-26`: *"'mentioned' is the mechanical floor, 'built or
deferred to a named stage' is the reader's half (reviewer.md checklist, dod.md)."* The retro added
the reader's half to `reviewer.md:77-87`. `grep -n 'ledger\|U<n>\|accepted' .claude/agents/dod.md`
returns nothing. The hook *does* fire on a staged `dod-check.md` (`accepted-items-ledger.sh:89`),
so DoD is gated by a check its role file has never heard of: a block arrives with no procedure
behind it.

Adjacent, same file: `dod.md:195` — *"Check `plans/<featurename>/review.md` required fixes against
`.claude/agent-memory/dod/MEMORY.md` for prior 'recurring fix' entries."* Every `MEMORY.md` has
been a 747-byte *"this is not an index"* pointer since 2026-10-16 (`todo/todo/X-T25.md`; commit
`6311b678`). The step reads a stub, finds no entries, and silently reports no recurrence — the
same shape as the `todo.md` "Current Focus" check the 2026-10-09 audit found (finding 6).

**Why it matters.** The retro's own account (`reviewer.md:81-86`) is that BR-2's U4 survived
*because nobody held the list of what was promised*; DoD is the last reader and the one the hook
blocks. And an instruction that resolves to an empty file is worse than none: it reads as a check
performed.

**Correction.** Add the ledger step to `dod.md`'s checklist mirroring `reviewer.md:77` (run it,
read the lines it prints per `U<n>`, decide built-vs-deferred, say so in `dod-check.md`). Replace
`dod.md:195`'s `MEMORY.md` read with `python3 .claude/scripts/memory-search.py -r dod <fix terms>`,
which is what every other role step in that file already uses (`dod.md:286`).

---

### 4. The retro's role-file edits are not threaded through the two documents that summarise the roles

`AGENTS.md` ("Roles (one-liners)") and `docs/AGENT_ROLES.md` are the project's own restatements of
`.claude/agents/*.md`, and Phase 1 of this skill exists to catch exactly this drift. Four
divergences, all introduced or widened by `8852fc2c`:

| topic | role file (truth) | summary docs |
|---|---|---|
| plan location | `architect.md:149` — *"Always write the plan to `plans/<featurename>/plan.md`"*; the ledger needs `plans/<feature>/plan.md` **and** `implementation.md` in that directory | `AGENTS.md:250` — *"Writes `plans/<featurename>.md`"*; `AGENT_ROLES.md:30` — *"write plan in `plans/<featurename>.md`"* (the pre-directory layout; a plan written there is invisible to the ledger) |
| decisions format | `architect.md:174-185` — `**U<n>: <question>**` rows, `**Answered <date> (user, verbatim):**` line; *"Number user decisions `U<n>`, always"* | `AGENT_ROLES.md:24` — *"decisions requiring user input"*, unnumbered; `AGENT_ROLES.md:188` — *"risks and open decisions"* |
| plan-check statuses | `plan-aligner.md:27-37` — met / missing / contradicted / **deferred → [[ID]] or Stage N** | `AGENT_ROLES.md:163` — *"met / missing / contradicted"*; `docs/BEHAVIOUR_ALIGNMENT.md` names no statuses at all |
| ALIGNED verdict | `goal-aligner.md:43-52` — ALIGNED *"when the why is stated, every expectation follows from it, and no open assumption would silently break an expectation … open questions can still be listed under it"* | `docs/BEHAVIOUR_ALIGNMENT.md:109` — *"**ALIGNED** — nothing found, one line"* — the calibration the role file was changed to escape, in the shared frame it tells the role to cross-check against |

**Why it matters.** The first row is load-bearing: the ledger can only see a plan in
`plans/<feature>/plan.md`, and two documents still tell a reader to write it elsewhere. The fourth
is the contradiction with teeth — the retro measured *"six of six goal checks returned CONCERNS"*
and recalibrated the role, while the shared doc the role cites as its calibration source still
defines ALIGNED as "nothing found", which makes a report with open questions a CONCERNS report by
that doc's reading.

**Correction.** One pass over `AGENTS.md:250` and `docs/AGENT_ROLES.md` §1, §9/10 and "Output
Style" to match the role files (directory layout, `U<n>` + `Answered` line, `deferred`); rewrite
`BEHAVIOUR_ALIGNMENT.md:109`'s verdict definitions to the role file's wording, since the role file
points there as the calibration source.

---

### 5. The session-start hook's role-sequence text has drifted from `AGENTS.md` again

**Evidence.** `session-start.sh`'s injected `additionalContext`: *"Core loop: Architect →
Implementer → Reviewer (loop …) → Definition of Done; a bug fix starts at Debugger instead of
Architect … Consequential work gets an Explore conversation with the user before Architect."*
`AGENTS.md` "Recommended Role Sequences": *"Explore → Goal Aligner → Architect → Plan Aligner →
Implementer → Reviewer → Security → Definition of Done"*, with the two aligner roles added
2026-10-30; and root `CLAUDE.md` "Workflow" / `AGENTS.md` "Auto-Advance": **DoD PASSED is the merge
trigger** (2026-10-26). The hook text knows neither.

**Why it matters.** The text self-describes as *"a pointer, not the source"* and `AGENTS.md` is in
context via `@AGENTS.md`, so the harm is bounded — but it is the first thing a cleared session
reads about sequencing, it says *"apply them automatically"*, and it is one of the two hooks the
2026-09-27 reviewer self-audit (`reviewer/project_claude_config_self_audit_2026_09_27.md`) found
*"drifted from CLAUDE.md text they summarize"*. Same hook, same drift, seven weeks and three
user directions later.

**Correction.** Either cut the sequence enumeration to the pointer it claims to be (*"apply
AGENTS.md's role sequences automatically; DoD PASSED triggers `/merge`"*) or bring it current with
the aligner roles and the merge trigger. The script's own header argues for the first.

---

## Tier 2 — possible improvements (7)

- **The always-loaded files are 46–49 % over the guideline the budget hook carries.** Measured:
  `CLAUDE.md` 6,253 words against `always-loaded-budget-gate.sh:93`'s 4,201; `AGENTS.md` 4,670
  against 3,194. The hook is advisory by user direction (*"guideline, not ceiling"*) and is doing
  its job; this is the slope it was built to make visible, recorded here so the next compaction
  pass starts from a number. The accretion is inside existing sections, as the hook's header
  predicted — the 2026-11-13 retro added evidence paragraphs to five role files rather than to
  these two, which is the right direction.

- **The ledger's section match is exact-case and 22 existing plans use another heading.**
  `accepted-items-ledger.sh:43` matches `^#+ *Decisions Requiring User Input`; `plans/*/plan.md`
  carry `### Decisions requiring user input` (5), `## Decisions Requiring User Input` (2, matched),
  `### Decisions` / `## Decisions` (13), plus two dated variants. Legacy plans are unnumbered anyway,
  so nothing is lost *today*; but a multi-stage plan still in flight that was written before the
  retro (the `BL-14` series, `relative-distance-grouping` with its `**Answered`-style lines but
  numeric ids) stays unledgered through its remaining stages. A case-insensitive match on
  `Decisions` would cost nothing and the `U<n>` grep already filters the rest.

- **`/plan-summary` reports answered decisions as open and drops the `Answered` line.**
  `plan-summary/SKILL.md:58-63` counts `- ` bullets under `### Decisions` and prints them as *"Open
  Decisions Requiring User Input"*; with the new format every `**U<n>**` row is still a bullet after
  the user has answered, and the `**Answered …**` line (not a bullet) is the one line that would say
  so. The Implementer is told to run this first (`implementer.md:147`). Print the `Answered` line
  when present, or retitle the section "Decisions" and let the reader see the status.

- **`goal-aligner/` has no `MEMORY.md` stub.** `X-T25` records *"every `.claude/agent-memory/*/
  MEMORY.md` is now a 747-byte pointer"*; `plan-aligner/` (same day's role) has one, `goal-aligner/`
  (one memory file) does not. Harmless — `memory: project` loads an absent file as empty — but the
  stub is what tells a reader *why* there is no index. One `cp`.

- **Template residue and two stale lines in `docs/AGENT_ROLES.md`.** §7 checklist: *"verify all
  DoD criteria pass (fmt, clippy, tests …)"* — `clippy` is the Rust template's linter; §7 "Must not:
  merge or push (belongs to the user)" predates the 2026-10-26 auto-merge (the DoD role file has the
  current rule at `dod.md:200`); "Why two role-configuration decisions" still paraphrases the
  cadence as *"once per feature before DoD"* where root `CLAUDE.md` restated it as per batch on
  2026-10-17. None changes behaviour; all three are the kind of line a future reader quotes.

- **`.claude/state/` is gitignored (`.gitignore:31`) while `.claude/state/last-retro` is tracked.**
  A tracked file keeps tracking regardless of the ignore rule, so the retro skill's *"repo root,
  tracked in git"* holds in this clone — but a fresh clone that has to *create* it (the skill's
  own instruction when absent) needs `git add -f`, and nothing says so. One clause in
  `retro/SKILL.md` Step 6.

- **The new discard refusal will fire on the one test card that prescribes the discarded command.**
  `docs/acceptance/2026-10-23-bl-b90-sequences-reflight.md:113` tells the reader to revert a
  deliberately edited config file with `git checkout -- body-layer/config/…`. For the user that is
  fine (hooks do not run for them); an agent following the card is refused, with a message that
  says to commit or stash first — which is the intended behaviour, not a defect. Noted so the first
  refusal is not read as a hook bug. `status-page-refresh.sh:158`'s `git checkout -- "$f"` runs
  from launchd, outside the hook, and is unaffected.

---

## Prior-audit findings status (2026-10-09 report)

**Tier 1 (8): all still closed, one residual now generalised.**

| # | finding | status 2026-11-14 |
|---|---|---|
| 1 | five subproject `CLAUDE.md` prescribed `mypy <sub>/src` | **resolved** — all six carry `cd <sub> && .venv/bin/mypy src` (re-verified by grep this run) |
| 2 | `git checkout -b` hook gated on the root's branch, told the agent to move it | **resolved** (message rewritten); the recorded residual — *"the hook still reads `$CLAUDE_PROJECT_DIR` rather than stdin `cwd`"* — is **still open** and is the same mechanism as this report's finding 1, which now shows four more hooks share it with consequences beyond a wrong message |
| 3 | root `CLAUDE.md` Workflow bullet 2 said "checkout `main` first" | **resolved** — bullet now gives the worktree form and quotes the superseded wording |
| 4 | both roadmap gates satisfied by touching a pointer | **resolved** — both gates and `graph-corpus-files.sh` still shell out to `roadmap-source.sh --is-pointer` (grep this run) |
| 5 | ID spaces uncovered, mint command prefix-blind | **resolved and superseded** — `mint-id.sh --list` derives the map; `BR-*` now lives in `brain-layer/ROADMAP/` (user direction 2026-10-17), which **reverses** the Tier 2 "decided, not changed" entry below; `docs/DOC_CONVENTIONS.md:218-228` records the reversal and the reason |
| 6 | two auto-memory entries described reversed states | **resolved** — both rewritten; the auto-memory index now carries 27 entries, all present on disk |
| 7 | three memory files absent from their index | **resolved and moot** — the per-role `MEMORY.md` indexes were replaced by 747-byte stubs + `memory-search.py` on 2026-10-16 (`X-T25`); completeness is now derived, not maintained |
| 8 | `agent-memory-path-gate.sh` rejected the sibling-worktree path | **resolved** — the gate still asks `git worktree list --porcelain` (grep this run) |

**Tier 2 (7): six done and still in place; the brain-layer `ROADMAP/` decision was reversed eight
days later** (`brain-layer/ROADMAP/` created 2026-10-17, commit `7ae978b0`, six entries today) —
the "condition to watch" the audit named (*"if `BR` grows past a couple of entries"*) was met by
`BR-2`. `skill-candidates.md` remains at zero open candidates, with one more resolved entry
(2026-10-15) since.

**Regressions:** none of the eight reopened. **Newly surfaced by this run that the previous audit
could have caught:** finding 1 — `commit-quality-gate.sh:16` was already in that form on
2026-10-09, when the inversion that made it wrong was that audit's own focus.

---

## Inspect-and-adapt line

The single thing to do first is finding 1: four hooks — including the one the retro just added as
its main corrective — read the wrong index for every worktree commit, and the fix is the one-line
pattern the same retro already used in `destructive-command-gate.sh`. Findings 2–5 are threading:
three user directions (2026-10-26 auto-merge, 2026-10-30 plan-review drop and aligner roles,
2026-11-13 ledger/U<n>) each landed in the role file that owns them and not in the documents that
summarise those roles, which is the drift shape this audit has reported at every run since
2026-09-08. The budget hook's numbers (Tier 2, first item) say where the next compaction pass
should start.
