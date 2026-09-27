# System Integrity Audit — 2026-09-27

Scope: Petrobrain's Claude Code operating environment as a whole — root `CLAUDE.md` + six
subproject `CLAUDE.md`, `AGENTS.md`, `docs/AGENT_ROLES.md`, `docs/PROCESS.md`,
`.claude/agents/*` (8), `.claude/skills/**` (30), `.claude/settings.json` hooks and the 11 scripts
they invoke, `.claude/agent-memory/**` (8 roles, 319 files), the project auto-memory (21 entries),
`todo/todo.md`, `todo/backlog.md`, root and per-subproject `ROADMAP.md`/`BACKLOG.md`, `NOTES.md`,
`plans/**`, `docs/status/`.

Diagnostic only. Nothing in the audited system was edited.

Method: claims were checked by running the thing, not by reading about it — hooks were traced
against live process state, the commit gate's discovery loop read in full, `body-layer`'s test
suite executed, `launchctl` queried, branch counts taken from `git`. Baseline `main` = `ef8b135`.
Context: a Reviewer/Performance/Security pass over this same configuration ran earlier today
(X-B5, fixes in `d1c5724`); findings it already closed are not repeated here, and two of its own
fixes are re-verified below.

---

## Tier 1 — Definite integrity problems

### 1. The Session Start hook cannot fire after a context clear — the one case `CLAUDE.md` calls "not optional"

**Evidence.** `session-start.sh` keys its "first message of the session" marker on `$PPID`:
`SESSION_MARKER="/tmp/claude-project-session-${PPID}"`, treated as stale only after 12 hours.
`/clear` does not start a new process. Observed in this very session:

```
/tmp/claude-project-session-39517   created 13:27   (marker)
this session's PPID                 39517           (after /clear at ~14:24)
```

The `SESSION START:` `additionalContext` was consequently **not injected into this session** — the
caveman `UserPromptSubmit` hook's context appeared, this one did not.

**Why it matters.** The protocol this hook exists to enforce is the one whose fourth step is
"CHECK THE STATE, NOT ONLY THE ACCOUNT OF IT", added because a *cleared session* rebuilt ~2000
lines of already-existing work. The hook fires reliably for a brand-new process, which is the case
that needs it least (a fresh session reads `CLAUDE.md` anyway), and is silent for the case it was
written for. `CLAUDE.md`'s own words — "this is not optional after a context clear" — are exactly
what the mechanism cannot cover.

**Corrective action.** Key the marker on something that changes at `/clear`, not on the process:
the session id is available to hooks in the payload (`.session_id`), and a `/clear` starts a new
one. Move the marker out of `/tmp` into `.claude/state/` at the same time, so a stale marker is
visible in the repo rather than in a shared temp directory.

### 2. Nine numbered role procedure steps route into unconfigured template skills

**Evidence.** 13 of 30 skills still contain literal `{{PLACEHOLDER}}` tokens, including `cd
{{PROJECT_DIR}}` as the first line of their scripts. Nine of them are cited as *numbered steps* in
role prompts:

| skill | placeholders | cited as a step by |
|---|---|---|
| `security-scan` | 16 | `security.md:91`, `security.md:155` (deep analysis, step 1) |
| `audit-report` | 8 | `security.md:28` |
| `security-grep` | 12 | `security.md:32` |
| `extract-plan-deps` | 5 | `security.md:23` |
| `invariant-check` | 12 | `reviewer.md:85` (step 2) |
| `extract-feature-diff` | 2 | `reviewer.md:86` (step 3) |
| `plan-summary` | 1 | `reviewer.md:84`, `implementer.md:58`, `dod.md:67` (step 1) |
| `notes-harvest` | 1 | `dod.md:183` (the NOTES.md harvest) |
| `visual-smoke-test` | 6 | `reviewer.md:56` |
| `done`, `dependency-audit-update`, `update-template`, `pull-from-template` | 2–11 | not on a mandatory path |

Several carry Rust/cargo and npm examples (`cargo audit --json`, `cargo cyclonedx`), i.e. they were
never adapted from the template at all. `security.md:207` lists `sbom.json` as a produced artifact;
no `sbom.json` exists in the repo.

**Why it matters.** This is not latent: `security` and `performance-reviewer` became a **mandatory
once-per-feature gate on 2026-09-24**, and Security's deep analysis opens with "Run `/security-scan`".
Reviewer's step 2 is described as "a mechanical pass/fail on project constraints; use this as the
foundation for invariant verification" — so invariant verification, including the no-omniscience
invariant, has no mechanism behind it at all. An agent following the numbered steps either reports
a tool failure, or silently substitutes its own ad hoc grep and reports the *step* as done. The
second outcome is the dangerous one and leaves no trace.

**Corrective action.** Decide per skill, and delete rather than fill where the answer is "not this
project": `visual-smoke-test` (no GUI), `dependency-audit-update`/`audit-report`/SBOM (no
lockfile-based dependency surface worth a CVE table today) are plausible deletions; `invariant-check`,
`extract-feature-diff`, `plan-summary` and `notes-harvest` are cheap to fill for Python/`git` and
are on the per-feature path. Until then, remove the numbered citations from the role prompts, so a
role is not instructed to run something that cannot run.

### 3. `dod.md` still teaches the pre-inversion worktree model

**Evidence.** `.claude/agents/dod.md:191`:

> Background Architect/Implementer/Reviewer/DoD agents run without worktree isolation by default,
> so switching branches in the active checkout risks racing whatever else is running there

`AGENTS.md` "Where work happens" (inverted 2026-09-21, "all three rules in force") says the
opposite: read-mostly agents *always* take `isolation: "worktree"`, and the main checkout belongs
to the main loop and the user.

**Why it matters.** DoD is the last gate and reads its own file as authority. The stale sentence
justifies the right action (merge via a worktree) with a premise that is now false, which makes it
unfixable by reasoning: an agent that notices its own worktree contradicts the sentence cannot tell
which half is current. The **2026-09-21 audit reported this as Tier 1 finding #3**; the `/merge`
skill half of it was fixed (`SKILL.md:24` now points at `AGENTS.md` and notes the inversion), the
`dod.md` half was not, six days on.

**Corrective action.** One-sentence replacement in `dod.md:191` pointing at `AGENTS.md` rather than
restating the model, as `merge/SKILL.md` already does.

### 4. Nothing says which commit an agent's worktree is based on — and three roles have each been burned by it separately

**Evidence.** `AGENTS.md` specifies the handoff *out* of a worktree in detail (commit, report the
sha, cherry-pick, plain `remove`) and says nothing about what the worktree is *based on*. A graph
query for it returns `AGENTS.md` as the only source, and that section. Three roles independently
recorded the consequence:

- `reviewer/feedback_worktree_main_based_pytest_pythonpath_trap.md` — worktree based on `main`,
  which predated the branch under review, so the probe imported pre-fix code and compared it
  against itself (`fix/position-belief-runaway`, 2026-09-25).
- `dod/feedback_dod_worktree_pythonpath_trap_applies_here_too.md` — the same trap bit DoD: pytest
  in the worktree reported `1177/4`, exactly `main`'s baseline, against the branch's own `1192/4`.
  DoD verified `main` and would have passed the gate on it.
- `performance-reviewer/feedback_stale_worktree_check_first.md` — the assigned worktree's HEAD
  (`6b8a86e`) was not even an ancestor of the tip the task named (`cdb8c7f`), and `git log` looked
  entirely plausible.

**Why it matters.** Every one of these is a *silent* wrong-code verification: a review, a
performance pass and a Definition of Done gate that all report on code other than the code under
review, with plausible output. Memory is currently the only defence, it is per-role, and it is
being re-learned rather than applied — the exact pattern Phase 5 exists to surface. This is the
same structural argument `AGENTS.md` itself makes about the worktree rule: a thing that must be
remembered at the moment attention is elsewhere will keep being missed.

**Corrective action.** Make it structural, in the dispatch rather than in eight memories: state the
branch *and* the expected tip sha in every isolated agent's prompt, and require the agent's first
action to be `git rev-parse HEAD` against that sha, reporting a mismatch instead of proceeding. The
`Agent` `PreToolUse` hook that already fires (`graph-query-reminder.sh`) is the natural place to
inject the reminder, and `AGENTS.md` "The three rules" the natural place to write it down.

### 5. `todo/todo.md`'s "read this first after a context clear" block is stale and contradicts the roadmap

**Evidence.** `todo/todo.md` carries a section headed *"State of play — end of 2026-09-24 (read
this first after a context clear)"* which states `main` is at `c912478` (it is `ef8b135`, ~30
commits on), that three milestones are "merged and unflown", and that "the outstanding card is
`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md`". Root `ROADMAP.md` says of exactly those:
"The eyes-and-voice, position-belief and damage/firing-probes cards it was batched with were all
flown and closed 2026-09-25." The same block says the brain layer "is the only component with no
plan file" — `plans/brain-layer/plan.md` exists and BR-1 Stages 1 and 2 are merged.

Separately, the file's own header names three roadmaps (`world-model/`, `aircraft-layer/`,
`body-layer/`) out of six — the hardcoded-three defect whose third recurrence `push-roadmap-gate.sh`
documented this morning.

**Why it matters.** It instructs a cleared session to read it *first*, and root `ROADMAP.md`'s
"Keeping this current" note says a disagreement between a roadmap and `todo.md` is "a bug in the
update discipline, not ambiguity to guess through". A session that obeys the block will ask the
user to fly a card that was closed two days ago and will treat flown work as unflown.

**Corrective action.** Delete the block (its content is in the roadmaps) or reduce it to a pointer.
A dated "state of play" narrative in a second file is a competing source of truth by construction;
the roadmap restructure of 2026-09-10 removed one of these already.

### 6. The mandated state check is now 65% agent scaffolding

**Evidence.** 125 local branches, **67** of them `worktree-agent-*`. `CLAUDE.md`'s Session Start
step 4 prescribes `git branch -v --sort=-committerdate | head -20`; run now, 13 of those 20 lines
are `worktree-agent-*` and the only live feature branch (`fix/sortie-2026-09-26`) sits at line 5
among them. 41 of the 67 are unmerged into `main` — expected, since the harvest is a cherry-pick,
which means **nothing distinguishes a harvested branch from an unharvested one**. Two other
leftovers (`main-local-tmp`, `main-ref`) sit in the same listing.

**Why it matters.** The check exists because skipping it once cost ~2000 duplicated lines. A
20-line window in which the real answer is outnumbered two to one by scaffolding degrades exactly
the signal it was added to provide, and it degrades further with every agent run.

**Corrective action.** Delete the 26 `worktree-agent-*` branches already merged into `main`, and
add the harvest sha to the remaining 41 so "harvested" is answerable; going forward, delete the
branch as the last step of the handoff (after the cherry-pick is verified), which `AGENTS.md`
already sequences for the worktree itself. Cheaper alternative if the branches are wanted as an
audit trail: change the documented command to `git branch -v --sort=-committerdate | grep -v
worktree-agent- | head -20`.

### 7. The status page's daily refresh is documented as running and is not installed

**Evidence.** `.claude/skills/status-page/SKILL.md:215` states as fact: "A launchd agent runs
`.claude/scripts/status-page-refresh.sh` at 05:00 local, daily", and `status-page-refresh.sh:4`
says "Run by a launchd agent at 05:00 local time". On this machine `launchctl list | grep -i
petrobrain` is empty and `~/Library/LaunchAgents/` contains no such plist — the plist exists only
as an in-repo template. `docs/status/petrobrain-status.html` was last written 2026-09-26 12:40,
before the 2026-09-27 commits.

**Why it matters.** The page is explicitly derived-not-authoritative, so a stale page is not a
correctness hazard — but "it regenerates daily" is load-bearing for how much anyone trusts it, and
the doc asserts a mechanism that is not running anywhere. Either the automation or the sentence is
wrong.

**Corrective action.** Install it (`launchctl bootstrap`, per the plist's own install lines) or
change both statements to say it is a manual `/status-page` run. Not both.

### 8. Two body-layer tests still fail on `main`, and the repaired commit gate now blocks on them

**Evidence.** Reproduced against `ef8b135`:

```
cd body-layer && ./.venv/bin/pytest tests -q
FAILED tests/test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask
FAILED tests/test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned
2 failed, 1292 passed, 4 xfailed in 11.23s
```

Filed this morning as `X-B22`, still open, not investigated.

**Why it matters, as a configuration finding rather than a code one.** `commit-quality-gate.sh` was
repaired today and now genuinely runs each touched subproject's suite from inside it, so **no
commit touching `body-layer/` can pass the gate until these are fixed** — the next body-layer task
will hit a red gate it did not cause. Both names describe pilot-visible belief defects (a crossing
callout for a contact behind the cockpit mask *is* the no-omniscience violation the sortie
reported; a permanently burned interrupted look is an optic that never recovers), so the failures
are candidate regressions, not stale tests. `X-B22` already notes the right first move: establish
how long they have been failing, since the gate's prior 127 exit means the last commit that
*appeared* to run these is not the last one that did.

**Corrective action.** Debugger on `X-B22` before the next body-layer feature, and check
`plans/callout-outside-gaze/debug.md` first — it has already diagnosed and partly fixed that
mechanism once.

### 9. `commit-quality-gate.sh`'s own docstring names three subprojects

**Evidence.** Lines 2–3: "Detects which subproject(s) the staged diff touches (world-model/,
aircraft-layer/, body-layer/)". The body, 80 lines later, discovers them (`for sub in */; do [ -d
"$sub/src" ] && [ -d "$sub/tests" ]`) under a comment that reads "DISCOVERED, NOT ENUMERATED — and
that distinction is the point", recounting two prior audits of this same defect.

**Why it matters.** Small, and worth fixing precisely because it is small: the docstring is what a
reader trusts, the enumeration in it is the exact artifact this project has now mis-stated four
times, and a future reader reconciling the two has no way to know which was intended. `todo/todo.md`
(finding 5) and the agent descriptions (Tier 2) are the same defect in two more places.

---

## Tier 2 — Possible improvements

- **All eight agent `description:` fields still call the project "Petrobrain (DCS World Model
  Builder)"**, and every role prompt opens with "currently focused on the DCS World Model Builder".
  The 2026-09-21 audit's Tier 1 #1 removed the false "those modules do not exist yet" claims, which
  was the harmful half; the framing remains. Descriptions are what a dispatcher matches on, and
  essentially all work since BL-2 has been body-layer, brain-layer and audio-adapter. One-line
  rewrite per file, no behavioural risk.
- **`/compile`'s description does not match its body.** Description: "Run the project build command
  with filtered output"; body: `ruff check <subproject>/src <subproject>/tests`, with prose that
  says "lint only that one". There is no build step in a Python project — the skill is a linter
  named after a compiler, sitting next to `/check` (mypy) and `/test`. Rename or re-describe; an
  agent choosing by description will pick it expecting something else.
- **Two auto-memory entries assert states that have since changed.**
  `project_pb2_next_milestone.md` says "next milestone is PB-2/BL-2 contact memory" (merged three
  weeks ago) and directs the reader to `todo/todo.md`'s "Current Focus" as the live source of truth
  — a section that no longer exists in a file that no longer holds milestone status.
  `project_brain_layer_is_the_bottleneck.md` says the brain layer "is the only Petrobrain component
  with **no plan file at all**", which stopped being true when `plans/brain-layer/plan.md` landed
  and BR-1 Stages 1–2 merged. Its structural half (the seams exist and sit idle; judgement features
  proposed before the brain exists get deferred to it) is still exactly right and worth keeping —
  rewrite rather than delete, and retire `project_pb2_next_milestone` outright.
- **`brain-layer/` has a `CLAUDE.md` but no `ROADMAP.md`**, and root `ROADMAP.md`'s row for it
  points at `body-layer/ROADMAP.md` with a parenthetical saying so. `CLAUDE.md` states the root
  table "links to **every** subproject's own `ROADMAP.md`, which is that subproject's source of
  truth"; for one of six that is a documented exception rather than a fact. `BR-B<n>` is reserved
  in the backlog-ID table with no file to hold it. Low urgency — but the brain layer is the active
  subproject, so it is the row most likely to be read.
- **`extract-plan-deps/SKILL.md:9` uses `plans/star-rendering/plan.md` as its example** — another
  project's domain, inherited from the template. Harmless in itself; it is the marker of a skill
  nobody has adapted (see Tier 1 #2), which is the useful signal.
- **`docs/AGENT_ROLES.md:77,95` frame the Security and Performance Reviewer cadence as "it may
  currently exempt this role"** and defer to `CLAUDE.md`'s Agents section for the answer. That
  deferral is correct and is why this is Tier 2, not Tier 1 — but the blanket exemption outlived
  its premise once already, in this exact wording, and a reader who stops at `AGENT_ROLES.md`
  learns only that an exemption is possible. Worth a five-word pointer to the current cadence and
  its date.

---

## Checked and found healthy

Recording these so a later audit can see what was verified rather than re-deriving it:

- **Agent-memory indexes are complete** — all eight roles index every file they hold (46/46, 16/16,
  6/6, 106/106, 30/30, 9/9, 99/99, 7/7). The 2026-09-21 audit's Tier 1 #2 (102 unreachable memory
  files) is fully closed, and `commit-quality-gate.sh` now carries a shrinking-index guard.
- **Every hook script referenced by `settings.json` exists** (11/11), and the three that were
  hardcoded to a subset of subprojects — `commit-quality-gate.sh`, `push-roadmap-gate.sh`,
  `posttooluse-mypy.sh` — now discover them from the filesystem. All six subprojects have a
  `## Commands` section in their own `CLAUDE.md`.
- **No `graphify-corpus/` mirror exists**, as `CLAUDE.md` requires; the semantic layer was rebuilt
  today (`graphify-out/GRAPH_REPORT.md`, 2026-09-27 13:42) and both git hooks are installed.
- **`skill-candidates.md` has no open candidates** — every entry is under "Resolved" with a created
  or rejected disposition and a reason. The mechanism is being worked, not accumulating.
- **All eight roles are `claude-sonnet-5`**, matching `CLAUDE.md`'s account including the
  2026-09-20 `dod` raise; `docs/AGENT_ROLES.md` now has its investigator section.
- **`session-start.sh`'s injected text matches current `CLAUDE.md`** (roadmaps as source of truth,
  the branch/worktree state check, the real Security/Performance cadence with the exemption
  explicitly revoked). Finding 1 is about when it fires, not what it says.

---

## Summary

**9 definite integrity problems, 6 possible improvements.**

The most important is **finding 1**: the hook whose entire job is to enforce the Session Start
protocol cannot fire after a `/clear`, because its "new session" marker is keyed on the process id,
which `/clear` does not change. Demonstrated live in this session. The protocol's own fourth step —
check the branches and worktrees before starting a milestone — exists because skipping it once
rebuilt ~2000 lines of work, and `CLAUDE.md` calls it "not optional after a context clear", which
is precisely the case the mechanism misses.

Running it close: **finding 2**, nine numbered steps in Reviewer, Security, Implementer and DoD
that point at skills still full of `{{PROJECT_DIR}}` and `cargo audit` examples, on roles that
became a mandatory per-feature gate three days ago. And **finding 4**, three roles that have each
independently verified the wrong code because nothing states which commit their worktree is based
on.
