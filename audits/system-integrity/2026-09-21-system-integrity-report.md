# System Integrity Audit — 2026-09-21

Scope: Petrobrain's Claude Code operating environment as a whole system — `CLAUDE.md` (root + five
subprojects), `AGENTS.md`, `docs/AGENT_ROLES.md`, `docs/PROCESS.md`, `.claude/agents/*` (8),
`.claude/skills/**` (31), `.claude/settings.json` hooks and the 12 scripts they invoke,
`.claude/agent-memory/**` (8 roles, 242 files), the project auto-memory, `todo/todo.md`, root and
per-subproject `ROADMAP.md`, `NOTES.md`, `plans/**`.

Diagnostic only. Nothing in the audited system was edited.

Method note: every claim below was checked against the files or executed against the scripts in
this worktree; hook behaviour was verified by feeding the hooks real JSON payloads, not by reading
them. Commit shas cited are on `main` as of `19180a0`.

---

## Tier 1 — Definite integrity problems

### 1. Five of eight role prompts tell the agent that two live subprojects do not exist

**Evidence.** Identical line in `architect.md:36`, `implementer.md:34`, `reviewer.md:34`,
`debugger.md:38`, `performance-reviewer.md:36`:

> Mission Interpreter and Petrobrain Runtime modules do not exist yet — do not create them ahead of
> the World Model Builder proving out (see `world-model/ROADMAP.md`).

`mission-interpreter/` has `src/`, `tests/`, `pyproject.toml`, `CLAUDE.md`, `ROADMAP.md`, and
MI-0–MI-6 are all merged. The "Petrobrain Runtime" is `body-layer/`, which is where essentially all
work since BL-2 has landed, including every one of today's six merges.

All eight role prompts also open with "…currently focused on the DCS World Model Builder"
(`architect.md:9` and the same line in the other seven), and all eight `description:` frontmatter
fields name the project "Petrobrain (DCS World Model Builder)". `performance-reviewer.md:9` goes
further: "This phase is an offline data pipeline… the Petrobrain runtime layer (which will need hard
latency budgets) does not exist yet."

**Why it matters.** This is not cosmetic framing — it is an instruction. A role prompt is the
agent's highest-priority context, and it currently states a prohibition ("do not create them") over
the two subprojects where the work actually is. The most likely failure is quiet: a reviewer
weighting `world-model/` invariants over `body-layer/` ones, an architect declining to place logic
where it belongs, or a performance reviewer applying an offline-pipeline latency standard to
`perception.clustering`, which runs every poll. `todo/todo.md`'s own deferred re-enablement item
already records that performance-reviewer and security "independently reported their own exemption
has gone stale" for exactly this reason — the roles noticed the drift in their prompts before this
audit did.

**Corrective action.** Rewrite the orientation paragraph and the "do not exist yet" line in all
eight files to describe the five-subproject repo as it is, with the active layer named. Because the
same sentence is duplicated across five files, do it in one pass and keep the wording identical so a
future grep still finds all of them.

---

### 2. Agent memory indexes are being silently truncated, and 102 memory files are now unreachable

**Evidence.** `.claude/agent-memory/reviewer/` holds **77 memory files**; its `MEMORY.md` indexes
**4**. Commit `b245fb2` ("chore: reviewer and implementer memory from the silent-stop pass",
2026-09-20) is the cause — `git show --stat b245fb2` reports
`.claude/agent-memory/reviewer/MEMORY.md | 28 +----------------`: **27 index lines deleted, 1
added.** The deleted lines include entries the project has since re-learned the hard way:

- `feedback_rerun_mypy_dont_trust_log.md` — "always rerun checks yourself"
- `feedback_verify_pipeline_wiring_not_just_module.md` — "a correct leaf-module fix is a no-op if
  the orchestrator still calls the old function"
- `feedback_bounded_magnitude_isnt_optional_severity.md`
- 24 more, including every MI-*, group-contact-model and inbound-speech review note.

The same pattern exists in `architect/`: **36 files, 7 indexed**, with 28 deleted index lines across
its history (`a3817cd`: 2 insertions / 5 deletions; `6a85f63`: 1 insertion / 3 deletions). Today's
`reviewer/project_concurrent_session_race_verification.md` (written in `3ce4dd6`) was never indexed
at all.

Compare the healthy roles: implementer 89 files / 83 indexed, investigator 27 / 27, debugger 8 / 8.

**Why it matters.** The files are not lost — they are on disk and in git — but the index is what an
agent reads at the start of a run, so an unindexed file is functionally deleted. AGENTS.md states
the principle directly: *"A memory that is never written is the most expensive loss in this system,
because its entire purpose is to stop a later agent repeating a mistake."* Today's inversion of the
worktree rule was motivated by exactly that risk, and a great deal of design effort went into
guaranteeing an isolated agent *can* write memory — while the bigger leak, overwriting an index
instead of appending to it, went unnoticed on the shared checkout. `implementer/MEMORY.md` carries
an explicit convention line ("One line per entry… Write directly to this directory") and a sibling
lesson, `feedback_implementation_log_append.md` ("read/append, never replace"), which was learned
for `implementation.md` and never generalized to `MEMORY.md`. Reviewer's index has additionally lost
the convention header that the other seven still carry, so the next reviewer sees no instruction to
append.

**Corrective action.** Two parts, both cheap:
1. Restore the lost entries — `git show b245fb2^:.claude/agent-memory/reviewer/MEMORY.md` has all 27
   verbatim; architect's can be reconstructed the same way — and restore reviewer's convention
   header.
2. State the append rule where it will be read: in each role file's memory section (the reviewer
   already has one at `reviewer.md:114`) and/or as a line in the `MEMORY.md` header. A mechanical
   backstop is also available and narrow: `commit-quality-gate.sh` already has a `check_memory`
   helper; a second check that fails when a staged `MEMORY.md` has *fewer* `^- \[` lines than its
   `HEAD` version would have caught `b245fb2` at commit time and costs one `git show` per role.

---

### 3. The worktree inversion did not reach the merge skill or the DoD agent

**Evidence.** `AGENTS.md` "Where work happens" (rewritten today, `643dd9b`) establishes that agents
run with `isolation: "worktree"` and the main checkout belongs to the main loop and the user. Two
files still encode the pre-inversion premise as the *reason* for their behaviour:

- `.claude/skills/merge/SKILL.md:21-25` — "**Why a worktree in this case, not `git checkout main`…**
  this project runs background Architect/Implementer/Reviewer/DoD agents in the same working
  directory (**no `isolation: "worktree"` on those Agent calls**)."
- `.claude/agents/dod.md:190` — "Background Architect/Implementer/Reviewer/DoD agents run without
  worktree isolation by default, so switching branches in the active checkout risks racing whatever
  else is running there."
- `.claude/skills/status-page/SKILL.md:20-23` — "Is a feature branch mid-flight, **or is an agent
  running in the working directory?** If so, do this in a disposable worktree on `main`… editing in
  a shared checkout races any background agent."

`dod.md:190` carries two further problems on the same line. First it mandates the worktree merge
path unconditionally ("**never `git checkout main` in the current directory**"), which contradicts
`merge/SKILL.md:14-18`, where merging the already-checked-out branch in place is the documented
path and is marked "(User decision, 2026-09-10.)". Second, its literal steps — `git worktree add
../<repo>-merge-<name>`, then `cd` into it — cannot be executed by a DoD agent that is itself
worktree-isolated; this audit run confirmed that a worktree-isolated agent's shell refuses commands
it cannot verify stay inside its own worktree, and AGENTS.md:93-96 records the same class of
refusal for heredocs.

**Why it matters.** These are not stale descriptions, they are stale *justifications*, which is
worse: an agent that reads "no isolation on those Agent calls" will make correct-looking decisions
from a false model of the system, and there is no contradiction visible from inside the file. The
merge skill is also where the branch-in-place-vs-worktree decision is made, so the false premise
sits directly on a decision point. Meanwhile AGENTS.md now adds a third consideration neither file
knows about — the main checkout's branch is a contract with the user — which should be the thing
governing what state a merge leaves the checkout in.

**Corrective action.** Update all three to the current rule. For `merge/SKILL.md`, the in-place path
is now the *normal* case (nothing else is using the checkout) and the worktree path is for merging a
branch other than the one the user should be testing. For `dod.md:190`, remove the "never
`git checkout main`" absolute and defer to `merge/SKILL.md` rather than restating its steps — the
restatement is what let the two diverge. For `status-page/SKILL.md`, the "agent running in the
working directory" trigger no longer exists.

---

### 4. Enforcement covers three subprojects; the repo has five

**Evidence.** `audio-adapter/` and `mission-interpreter/` each have `src/`, `tests/`,
`pyproject.toml`, and a `CLAUDE.md` with its own "Commands" section (`audio-adapter/CLAUDE.md:102`,
`mission-interpreter/CLAUDE.md:98` — ruff format/check + mypy --strict + pytest, identical shape to
the other three). Both are listed as subprojects in root `ROADMAP.md`. `audio-adapter/` had merges
as recently as 2026-09-20.

Every enforcement and instruction path names only `world-model|aircraft-layer|body-layer`:

| Location | What it misses |
|---|---|
| `.claude/scripts/commit-quality-gate.sh:27-65` | a commit touching only `audio-adapter/` or `mission-interpreter/` runs **zero** checks and passes silently |
| `.claude/scripts/posttooluse-mypy.sh:17-28` | no mypy feedback while editing those two |
| `.claude/scripts/push-roadmap-gate.sh:30` | a feature merge in those two never triggers the roadmap gate |
| `.claude/agents/dod.md:19-24` | DoD's own Code Quality checklist |
| `.claude/agents/reviewer.md:59`, `implementer.md:70` | per-subproject check instruction |
| root `CLAUDE.md:104` ("Verification"), `:69-71` ("Milestone Completion"), `:40-42` ("Subprojects") | the subproject list itself omits both |

**Why it matters.** `CLAUDE.md:104` states that the commit gate "enforces mechanically
per-subproject at commit time". For two of five subprojects that sentence is false, and it is false
in the direction that produces false confidence rather than friction. This is also a recurrence:
the 2026-09-10 audit's top finding was world-model-only hardcoding in these same three mechanisms.
The fix generalized them from one subproject to three by enumeration, and the enumeration went stale
the moment a fourth and fifth appeared. `graph-corpus-files.sh:51` shows the alternative already in
use in this repo — `ls -1 */ROADMAP.md */CLAUDE.md` discovers subprojects instead of listing them.

**Corrective action.** Replace the hardcoded lists with discovery in the three scripts (a subproject
is a top-level directory with a `pyproject.toml` and a `tests/`), and fix the three prose locations
to say "every subproject the change touches" rather than enumerating. `body-layer`'s cd-before-mypy
quirk is the one case needing a per-subproject exception, and it is already isolated to one line.

---

### 5. Two live automation scripts carry stale pointers

**Evidence.**

- `.claude/scripts/session-start.sh:11` injects, on the first prompt of every session:
  *"SESSION START: Follow the Session Start protocol from CLAUDE.md — **read todo/todo.md, identify
  the next actionable milestone** (first non-completed, non-deferred section with open items)…"*
  `CLAUDE.md:57-65` says the opposite order — read root `ROADMAP.md` first, then the active
  subproject's `ROADMAP.md`, and read `todo/todo.md` only for User priority tasks and cross-cutting
  items. `todo/todo.md:3-5` states outright: *"Milestone status, backlog, and deferred items live in
  `../ROADMAP.md` … **not here**."* The hook therefore directs every session to look for the next
  milestone in the one file that is documented not to contain it.
- `.claude/scripts/graph-corpus-files.sh:34` — `ACTIVE_PLAN="${GRAPH_ACTIVE_PLAN:-plans/inbound-speech}"`.
  The active plan is `plans/detection-cones-slice2`. The corpus deliberately includes exactly one
  plan ("The one plan currently being worked", line 58), so the knowledge graph is built with the
  wrong one.

**Why it matters.** Both are mechanisms whose whole purpose is to correct for something being
forgotten, and both now inject the wrong answer with the authority of automation. The session-start
hook is the more serious: it fires before anything else, it contradicts `CLAUDE.md` in the same
breath as citing it, and the roadmap restructure it predates (2026-09-10) existed precisely because
`todo/todo.md` had drifted. The graph pointer is quieter but undermines a rule `CLAUDE.md:78`
states firmly — "**Query it before concluding something is undocumented**" — since the graph cannot
answer questions about work whose plan was never ingested.

**Corrective action.** Rewrite the session-start injection to match `CLAUDE.md`'s five numbered
steps, or better, have it inject nothing but the pointer to that section, so there is one copy of
the protocol rather than two. For `graph-corpus-files.sh`, either update the default now or derive
it (the most recently modified `plans/*/plan.md` is a reasonable heuristic, and `GRAPH_ACTIVE_PLAN`
already exists as the override).

---

### 6. `CLAUDE.md`'s "Backlog Management" section is a pre-restructure fossil, and points at a section that no longer exists

**Evidence.** `CLAUDE.md:123-128`: "**`todo/todo.md` is the source of truth.** … Read before
starting work; **prefer Current Focus tasks**". Against this:

- `CLAUDE.md:25-30` (57 lines earlier): "Root `ROADMAP.md` is the entry point … each subproject's
  own `ROADMAP.md` … **is that subproject's source of truth** for milestone status, decisions, and
  backlog — read those, don't infer status from this file."
- `todo/todo.md` has **no "Current Focus" section** — its headings are "User priority tasks" and
  "Cross-cutting / unscoped backlog".
- `CLAUDE.md:42` sends the reader to the same phantom section: "BL-x milestone status: see
  `todo/todo.md` 'Current Focus'".

**Why it matters.** Two "source of truth" declarations in one file is the exact failure mode
`ROADMAP.md:61` warns about ("If a roadmap file and `todo/todo.md` … ever disagree, treat that as a
bug in the update discipline"). The dangling "Current Focus" reference is worse than a broken link,
because an agent that cannot find the named section will substitute its own judgement about where
BL-x status lives, and the correct answer (`body-layer/ROADMAP.md`) is not mentioned on that line.

**Corrective action.** Rewrite "Backlog Management" so `todo/todo.md` is described as the source of
truth *for what it actually holds* (User priority tasks, cross-cutting/unscoped backlog), keep the
task-state legend, and drop "prefer Current Focus tasks". Point `CLAUDE.md:42` at
`body-layer/ROADMAP.md`.

---

### 7. Root `ROADMAP.md`'s Body Layer row is six merges behind, and the gate that exists cannot see it

**Evidence.** `ROADMAP.md:40` is current as of the group contact model's Stage 5 merge (2026-09-18).
Merged since, and absent from the row: aspect-aware object profiles (`3f624d9`), BL-9 detection
trace (`1553eb9`), detection-cones slice 1 (`ce9baea`), cones 2A (`7d82018`), cones 2A.5 (`5763390`),
cones 2B (`81aa5e4`). `git log --oneline -- ROADMAP.md` confirms the file's last content change was
`9321897`, "group contact model, first five stages merged".

`body-layer/ROADMAP.md` is fully current by contrast — BL-9 at :480, aspect-aware at :463, 2A/2A.5
at :437, 2B at :419, plus today's closures of BL-4's attention tools (:29) and the F10 command
vocabulary (:41). So the per-subproject discipline is working; only the cross-subproject roll-up
drifted.

`push-roadmap-gate.sh:39` passes as long as *any* file named `ROADMAP.md` is touched in the push. Six
pushes satisfied it by updating `body-layer/ROADMAP.md`, which is the correct thing to update — the
gate simply cannot tell whether the root row also needed a refresh, and both `merge/SKILL.md:74` and
`dod.md:192` make the root update conditional ("if the subproject's overall phase status changed"),
a judgement call that has now been answered "no" six times in a row.

**Why it matters.** The root roadmap is step 1 of the Session Start protocol and the source for the
derived status page (`docs/status/`), which is published to the user. A reader following the
documented entry point today is told the Body Layer's frontier is the group contact model; it is
actually cones slice 2C.

**Corrective action.** Refresh the Body Layer row (and note that cones 2C is complete and unmerged —
see Tier 2 item 1). Separately, consider making the root update unconditional on any milestone
completion rather than conditional on a judgement about "phase status", since the conditional is
what six merges each independently decided against.

---

### 8. Three references were missed by today's flat-skill → directory rewrite

**Evidence.** All 31 skills are correctly at `.claude/skills/<name>/SKILL.md` (verified: no flat
`.md` remains, no directory lacks its `SKILL.md`), and both new gates work — I fed
`skill-layout-gate.sh` a flat path and it blocked, a `SKILL.md` path and it passed. Three textual
references survive:

- `.claude/skills/status-page/SKILL.md:21` — "(see **`merge.md`**'s worktree pattern)". No such file.
- `.claude/skills/update-template/SKILL.md:33` — "**`test.md`**, **`done.md`**/**`dod-check.md`**,
  agent role files".
- `.claude/scripts/push-roadmap-gate.sh:51` — the user-facing block message says "**merge.md**/dod.md
  require the relevant ROADMAP.md to be updated".

Two adjacent descriptions are also now wrong in a way that matters more than a path:

- `.claude/settings.json:126` (the SubagentStop skill-gap detector prompt) instructs
  `grep -h '^description:' $CLAUDE_PROJECT_DIR/.claude/skills/*.md …` — a glob that now matches
  nothing — and then asserts: *"Every `<name>.md` there is a user-invocable slash command `/<name>`;
  every subdirectory is a skill. CRUCIAL: the `.md` slash commands … **NEVER** appear as `Skill`-tool
  calls in the transcript. The absence of a `Skill` invocation is therefore **NOT** evidence that the
  capability is missing."* All 31 are now directories and all 31 *do* appear as `Skill`-tool calls,
  so the detector is told to discount its single best signal.
- `.claude/agent-memory/skill-candidates.md`'s Resolved log repeats the same stale claim: "The
  detector missed them because it only counts `Skill`-tool invocations and cannot see the `.md`
  slash commands in `.claude/skills/`."

**Why it matters.** The three path references are minor on their own. The settings.json prompt is
not: it is a live instruction to a haiku subagent that runs after every DoD, and it now
systematically *suppresses* true positives while directing its inventory grep at an empty glob. The
migration removed the condition that made the caveat true, and the caveat outlived it.

**Corrective action.** Fix the three paths to `<name>/SKILL.md`. Rewrite the settings.json prompt's
inventory step to `grep -h '^description:' $CLAUDE_PROJECT_DIR/.claude/skills/*/SKILL.md` and delete
the "CRUCIAL" paragraph, which is now backwards. Update the skill-candidates.md rejection note for
`test-and-commit-cycle` so the reasoning on file matches reality.

---

## Tier 2 — Possible improvements

1. **Cones 2C is complete on `feature/cones-2c-scan-loop` (7 commits, through `13b82b7` "acceptance
   test card, NOTES.md harvest") but `body-layer/ROADMAP.md` has no entry for it** — only a
   forward-looking mention at :461 ("Then 2C… and conditionally 2D"). This is consistent with the
   rule that the roadmap is updated *at merge*, so it is not a violation. But a session following
   the Session Start protocol today would read 2B as the frontier and 2C as unstarted, and the
   branch carries an unexecuted acceptance card. A one-line `[~]` entry naming the branch would
   close the gap without pre-empting the merge-time write-up.

2. **The calibration-target decision is findable only through git.**
   `body-layer/research/2026-09-21-calibration-target-decided.md` (committed in `5fb40e2`) is
   referenced from nothing — not `body-layer/ROADMAP.md`, not `todo/todo.md`, not any plan. Its
   commit message says it "clears the third of four recalibration blockers", but the roadmap's
   recalibration discussion (`body-layer/ROADMAP.md:474`, "remains deferred, now for a third
   reason") does not enumerate blockers and does not know the decision happened. The related
   scan-coverage decision (`46b0e3c`) is in the same position. The other today-filed items are fine
   by comparison: the 9K113 (`todo/todo.md:37`), the mission-sandbox probe (:63), movement detection
   (`body-layer/ROADMAP.md:648`) and `threat-levels.md` (:737) are each in exactly one place, with
   cross-references rather than duplicates — which is the pattern the two decision records should
   follow. `dod/feedback_verify_roadmap_prose_claims.md` is the memory entry that anticipated this
   exact class.

3. **Auto-memory promotion candidates and one orphan.**
   - `project_pb2_next_milestone.md` ("next is PB-2/BL-2 contact memory") has been obsolete since
     2026-09-09 and was **already flagged in the 2026-09-10 audit** as Tier 2. Eleven days and
     roughly twenty milestones later it is unchanged — a small but real signal that Tier 2 findings
     are not being harvested.
   - `project_module_independence_rule.md` is now fully covered by `CLAUDE.md:39` ("Module
     independence"), which states it at greater length and with the body-layer↔world-model
     exception. Promotion already happened; the memory entry is a duplicate that can only drift.
   - `feedback_dcs_probe_io_lfs.md` exists on disk but appears in no line of the auto-memory
     `MEMORY.md`. Same unreachable-file condition as Tier 1 item 2, in the other memory store.

4. **Repeated-correction classes that are still being re-taught rather than ruled.** Across roles,
   the same three lessons recur in independently written memory files:
   - *Verify before claiming* — `reviewer/feedback_rerun_mypy_dont_trust_log.md`,
     `feedback_verify_pipeline_wiring_not_just_module.md`,
     `feedback_verify_mypy_cwd_claims_by_reproduction.md`,
     `dod/feedback_verify_roadmap_prose_claims.md`,
     `implementer/feedback_verify_git_log_after_commit.md`,
     `feedback_verify_rebuild_row_counts.md`, `feedback_verify_mission_probe_pattern_claims.md`,
     `feedback_verify_keyword_vocab_against_real_strings.md`. Eight files, four roles, one rule.
     `dod.md` already carries a run-it-before-you-write-it rule (added 2026-09-20 with the model
     change); promoting it to a single line in `AGENTS.md` "General Rules" would cover all roles,
     and each memory file would then be an *instance* rather than the rule's only home.
   - *Agent-memory paths* — `implementer/feedback_agent_memory_path.md`,
     `reviewer/feedback_agent_memory_path_recurrence.md`, plus the prose at `reviewer.md:114`. This
     one is now genuinely enforced twice (`agent-memory-path-gate.sh` at write time,
     `commit-quality-gate.sh:68` at commit time) and I verified both fire correctly, including the
     new worktree-aware cases. The memory entries have become historical; they can be collapsed to
     one line noting the gate exists.
   - *Staged files / clean tree* — `reviewer/feedback_check_agent_memory_staged.md`,
     `feedback_side_quest_commits_on_feature_branch.md`, `implementer/feedback_verify_git_log_after_commit.md`.
     `CLAUDE.md:121` states the rule; nothing checks it. See item 6 below.

5. **`docs/AGENT_ROLES.md` and `AGENTS.md`'s role list both omit the Investigator.** AGENT_ROLES.md
   documents seven roles; `AGENTS.md` "Roles (one-liners)" lists the same seven. The investigator is
   a real role with its own `.claude/agents/investigator.md`, is described only in `CLAUDE.md:55`,
   and `CLAUDE.md` says Architect must invoke it proactively — a trigger stated in the one file that
   the Architect's own reference documentation does not include. Adding an eighth entry to both
   would cost two lines. (Pre-existing, not from today's churn.)

6. **Stated-but-unenforced rules.** Today closed two of these (flat skills; the worktree-path
   contradiction in the memory gate). The ones still open, in rough order of exposure:
   - `CLAUDE.md:121` — "run `git status` and confirm a clean working tree before declaring any task
     complete". Nothing checks; three memory files above record it failing.
   - The `MEMORY.md` append convention — see Tier 1 item 2. Highest value of the three, because its
     failure is invisible and cumulative.
   - `CLAUDE.md:110` — "Do not merge without user approval." Unenforceable mechanically, and
     probably should stay a norm; listed for completeness.
   None of these obviously warrants new automation on its own, except the memory-index check, which
   is ~5 lines inside a gate that already runs.

7. **Duplicated rule statements with real divergence risk** (currently in agreement, worth a
   cross-reference rather than a rewrite):
   - Role sequences exist in three places — `AGENTS.md:171-175`, `docs/AGENT_ROLES.md`, and the
     `UserPromptSubmit` `additionalContext` at `settings.json:87`. They agree today, and the hook
     correctly defers to CLAUDE.md's exemption. But the hook's copy omits the *Explore* phase that
     `AGENTS.md:171` puts first for consequential work, so the injected version is already a
     slightly lossy copy of the canonical one.
   - The roadmap-in-the-same-push rule is stated in `merge/SKILL.md:71`, `dod.md:192`,
     `ROADMAP.md:58`, `todo/todo.md:6` and enforced by `push-roadmap-gate.sh`. Five statements, one
     gate. This is the rule whose duplication already produced the Tier 1 item 3 divergence in a
     neighbouring paragraph.

8. **`docs/PROCESS.md` is described as generic but is not.** `CLAUDE.md:7` introduces it as "generic
   engineering heuristics/protocols", and most of it is. Three sections are not: "Keeping the
   knowledge graph honest" (this project's `gq.sh`/graphify setup), "`win-mac-sync/` is a delivery
   mechanism, not storage", and "The Mi-24P manual". This matters only for the
   `/pull-from-template` and `/update-template` flows, which diff this project against the template
   — a project-specific section in a file treated as generic is what makes those diffs noisy. Either
   move the three sections into `CLAUDE.md` or soften the description at `CLAUDE.md:7`. No other
   genericity leaks found: the `.claude/agents/*` templates carry DCS specifics by design, and
   `dcs-log-recon`/`dcs-file-investigation` are intentionally project-specific.

---

## What was checked and found healthy

Recorded so the next audit knows what it need not re-derive.

- **All four new/changed hooks work as described.** `skill-layout-gate.sh` blocks a flat skill path
  and passes `SKILL.md` (both executed). `agent-memory-path-gate.sh` allows a worktree-root memory
  path, allows the main checkout's, and denies a subproject path *nested inside a worktree* —
  the exact case AGENTS.md:90 says it was fixed for. `commit-quality-gate.sh`'s skill-layout block
  (lines 102-122) mirrors the PreToolUse gate for non-Write paths. All are registered in
  `settings.json` and all fail open.
- **The deny-list addition creates no contradictions.** `git worktree remove --force` appears in
  `AGENTS.md` only as the thing *not* to do; `merge/SKILL.md:80` and `dod.md:190` both use plain
  `git worktree remove`. No instruction anywhere would now be blocked by the deny list.
- **The skill migration is structurally complete** — 31 directories, 31 `SKILL.md` files, zero flat
  `.md`, and `dcs-log-recon`'s bundled `scripts/parse_dcs_log.py` survived intact.
- **`body-layer/ROADMAP.md` is accurate and current**, including today's two "closed as tested and
  good enough" entries (BL-4 attention tools :29, F10 command vocabulary :41). Neither appears as
  open or as acceptance debt anywhere else — checked against `todo/todo.md` and root `ROADMAP.md`.
- **No duplication between `todo/todo.md` and the roadmaps.** The 9K113, the mission-sandbox probe,
  movement detection and threat-levels each live in exactly one file, with genuine cross-references
  where they interact.
- **`skill-candidates.md` has no unreviewed backlog** — the Resolved log holds five entries, all
  created or rejected with reasons, and no open `##` candidate. The process is working as designed
  (one stale reason noted in Tier 1 item 8).
- **All eight agents are `claude-sonnet-5`**, matching `CLAUDE.md:46`, including `dod` after its
  2026-09-20 raise.
- **Every path, script and command referenced in `CLAUDE.md`, `AGENTS.md` and the hooks exists**,
  apart from the "Current Focus" section (Tier 1 item 6) and the three skill paths (item 8).

---

## Summary

**Tier 1: 8 findings.** They fall into three groups. *Today's churn left three loose ends* — the
worktree inversion did not reach `merge/SKILL.md`, `dod.md` or `status-page/SKILL.md` (item 3); the
skill migration left three path references and one actively-wrong hook prompt (item 8). *Two
mechanisms silently stopped covering what they claim to* — enforcement stalled at three of five
subprojects (item 4), and two scripts inject stale pointers into every session and every graph build
(item 5). *Three descriptions drifted from the project* — five role prompts deny that the active
subprojects exist (item 1), `CLAUDE.md`'s backlog section predates the roadmap restructure (item 6),
and the root roadmap is six merges behind (item 7).

**The single most important finding is item 2**, which is none of those: it is an ongoing,
undetected loss. `.claude/agent-memory/reviewer/MEMORY.md` was cut from 28 entries to 1 by a single
commit on 2026-09-20, orphaning 73 review memory files, and architect's index shows the same
overwrite pattern over a longer period. The system spent today's effort guaranteeing that an
isolated agent *can* write memory, while the larger leak — agents overwriting the index instead of
appending to it — ran unnoticed in the shared checkout. Everything is recoverable from git, and the
fix is one restore plus one append-don't-replace rule; a 5-line check in the gate that already runs
would make the next occurrence impossible.

**Tier 2: 8 items.** Chiefly memory hygiene — two promotion candidates and one orphan in auto-memory
(item 3), and three correction classes recurring across four roles that would be better as one rule
each than as eight memory files (item 4). One item is a repeat: `project_pb2_next_milestone.md` was
flagged stale in the 2026-09-10 audit and is still stale.
