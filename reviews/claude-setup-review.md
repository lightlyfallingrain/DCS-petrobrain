# Claude Code Operating Environment Review — 2026-09-27

Scope: this repo's Claude Code config/process surface only (CLAUDE.md files, AGENTS.md,
docs/AGENT_ROLES.md, docs/PROCESS.md, .claude/agents/*.md, .claude/skills/**, .claude/settings.json,
.claude/scripts/*.sh, .claude/agent-memory/**, .claude/docs/agents.template.md), cross-checked
against todo/todo.md, todo/backlog.md, ROADMAP.md files. No subproject source code was reviewed.
This is the audit named in `todo/backlog.md` X-B5 ("Run Reviewer, Performance Reviewer and Security
on this repo's Claude configuration itself"); it covers the Reviewer half of that item.

**Housekeeping note**: this worktree was created from `bd28563`, five commits behind `main`
(`4fec9c4`..`1a7f714`, the backlog-split series). I merged `main` into the worktree branch before
starting so the audit reflects current `main`, not a stale snapshot — worth knowing since several
things X-B5's 2026-09-25 seed material flagged turned out to already be fixed by that later work.

## Verdict

**NEEDS REVISION.** The project has been actively self-correcting on exactly this surface — most of
X-B5's own seed findings (the graphify-corpus-mirror contradiction, the "Current Focus" dead
reference, `/dod-check`'s hardcoded subproject list, `AGENTS.md` role count) are already fixed. But
two mechanisms that inject text into *every single turn* — the `UserPromptSubmit` role-sequence hook
and the session-start hook — have drifted from the CLAUDE.md text they're supposed to summarize, in
each case in the direction of skipping a step the docs currently require. These are higher-impact
than the seed material's remaining item (one leftover hardcoded subproject list) because they fire
silently, on every prompt, with no human reading them.

## Required Fixes

- **[BLOCKER] `.claude/settings.json:96`** — the `UserPromptSubmit` hook injects a fixed summary of
  AGENTS.md's role sequences that **omits Security from all four sequences** and Explore from the
  "new feature" line, then tells the agent: *"CLAUDE.md Agents section may currently exempt one or
  both for this project phase — that exemption wins."* But CLAUDE.md's "Agents" section (current
  text, unchanged since 2026-09-24) says the opposite: *"performance-reviewer and security run once
  per whole feature, immediately before DoD... Enabled 2026-09-24... replacing the previous blanket
  skip."* There is no exemption in force — there's a cadence — and the hook's printed sequences
  (`Architect → Implementer → Reviewer → Definition of Done`, no Security anywhere, not even the
  bug-fix line's `Security (deep analysis)` step that AGENTS.md's own current text includes) encode
  the pre-2026-09-24 blanket-skip world as if it were still the default. This fires on every prompt
  with no gate on it being read. **Fix**: either drop the hardcoded sequence text and just point at
  AGENTS.md + CLAUDE.md's Agents section, or update it to include Security/Performance Reviewer in
  every sequence and drop the "may currently exempt" hedge that no longer matches CLAUDE.md.

- **[BLOCKER] `.claude/scripts/session-start.sh`** — the injected `SESSION START` text (fires on the
  first prompt of every session) says: *"read todo/todo.md, identify the next actionable milestone
  (first non-completed, non-deferred section with open items)."* This contradicts CLAUDE.md's
  current Session Start protocol on two counts: (1) CLAUDE.md step 1 says read root `ROADMAP.md`
  first, then the active subproject's own `ROADMAP.md` — the hook never mentions ROADMAP.md at all;
  (2) CLAUDE.md's own "Current priority" section states *"todo/todo.md no longer duplicates milestone
  narrative; it only holds items not yet assigned to one subproject's roadmap"* — so deriving "the
  next actionable milestone" from a todo.md section, as the hook instructs, is exactly the thing
  CLAUDE.md says not to do. The hook also never mentions `todo/backlog.md` (split out 2026-09-27) or
  the `git branch -v --sort=-committerdate` / worktree-list state check that CLAUDE.md calls "not
  optional after a context clear" — the step added specifically after a cleared session rebuilt
  ~2000 lines of already-existing work because it trusted the roadmap's account of state over the
  state itself. A hook whose entire job is to enforce Session Start is currently enforcing an older,
  incompatible version of it. **Fix**: rewrite the injected text to match CLAUDE.md's current 5-step
  protocol (ROADMAP.md → todo.md + backlog.md → milestone from roadmap → branch/worktree state check
  → show and ask), or have it just say "follow CLAUDE.md's Session Start protocol" without
  restating steps that will drift again.

- **[REQUIRED] `CLAUDE.md:63-66`** (root, "Subprojects" section) still hardcodes exactly three
  subprojects:
  ```
  - `world-model/CLAUDE.md` ...
  - `aircraft-layer/CLAUDE.md` ...
  - `body-layer/CLAUDE.md` ...
  ```
  `git ls-files '*CLAUDE.md'` shows six subproject CLAUDE.md files (`audio-adapter/`, `brain-layer/`,
  `mission-interpreter/` also exist and are not listed here). This is the exact defect the file's own
  "Current priority" section (a few lines above, ~line 24) warns against by name: *"Take the list of
  subprojects from that status table, never from this file... That already happened — three were
  named here long after six existed."* Three of the four places X-B5's seed material found this
  problem (Current priority, Milestone Completion, Verification sections) are now fixed to defer to
  root `ROADMAP.md`'s status table; this is the one that wasn't. A reader who reaches "Subprojects"
  without having internalized "Current priority" 40 lines earlier gets the stale list back. **Fix**:
  either drop the bulleted list and point at root `ROADMAP.md`'s status table like the other three
  sections now do, or keep the list but generate/verify it against `git ls-files '*/pyproject.toml'`
  before every edit to this file.

- **[REQUIRED] `docs/AGENT_ROLES.md`** has zero mentions of `investigator` (`grep -n -i investigator
  docs/AGENT_ROLES.md` — no output), and its 7 numbered sections (Architect, Implementer, Reviewer,
  Debugger, Performance Reviewer, Security, Definition of Done) never include an 8th. `AGENTS.md`'s
  "Roles (one-liners)" section already lists investigator as item 8 and explicitly warns this list
  "has been wrong before (`investigator` existed here... while this section listed seven)" — but the
  document `AGENTS.md` points readers to for "Full per-role responsibilities, priorities, checklists,
  and output-style detail" never received the corresponding fix. Root `CLAUDE.md`'s "Agents" section
  dedicates a full paragraph to investigator as an established, actively-used role (dated examples,
  explicit non-goals). Anyone following `AGENTS.md`'s pointer to "tune a role or when unsure what it
  should/must not do" for investigator finds nothing. **Fix**: add an investigator section to
  `docs/AGENT_ROLES.md` matching the depth of the other seven.

- **[REQUIRED, recommend verifying by running mypy before fixing]** `.claude/scripts/commit-quality-gate.sh`'s
  discovery loop (`for sub in */; ... run "$sub mypy" mypy "$sub/src"`, ~line 44) invokes mypy
  identically for every subproject from the **repo root** as cwd, with no special-case for
  body-layer. But `.claude/skills/check/SKILL.md:20-22`, `.claude/skills/dod-check/SKILL.md:100-103`,
  and `.claude/scripts/posttooluse-mypy.sh:24-26` all explicitly `cd body-layer && mypy src` instead,
  because (their words) "mypy's config discovery there is CWD-only and `mypy --config-file` alone
  does not fix it." Mypy's config-file search is documented as CWD-relative-only (it does not walk
  up from, or resolve relative to, the paths passed on the command line), and `body-layer/pyproject.toml`'s
  `[tool.mypy]` sets `strict = true` and a CWD-relative `mypy_path = "src:tests:../world-model/src"`
  (the world-model cross-import body-layer is allowed per CLAUDE.md's "Module independence"
  exception). Run from repo root with no root-level `pyproject.toml`/`mypy.ini` (confirmed:
  `ls pyproject.toml` at repo root fails), mypy would fall back to its unconfigured defaults —
  losing `strict` and the `mypy_path` entry that resolves the world-model import — on the one
  hook that runs on **every commit**, not just at DoD or on manual `/check`.
  I could not execute mypy in this sandbox (no root `pyproject.toml`, no bare `mypy` on `PATH`, and
  body-layer's own `.venv` isn't provisioned in this worktree) to observe the actual diff in errors
  reported, so this is inference from the config shapes and the project's own documented claim about
  CWD-only discovery, not a reproduced failure — **verify with**
  `diff <(cd body-layer && .venv/bin/mypy src 2>&1) <(.venv/bin/mypy body-layer/src 2>&1)` (adjust
  venv path) from repo root before changing the script.
  **Notable wrinkle for whoever fixes this**: `world-model/pyproject.toml`, `aircraft-layer/pyproject.toml`,
  and `audio-adapter/pyproject.toml` all have the *identical* shape (`strict = true`,
  CWD-relative `mypy_path`) yet nobody has flagged them needing the same `cd` treatment. Two
  explanations are consistent with that: either they're silently getting weaker (non-strict, no
  `mypy_path`) checks from commit-quality-gate.sh and nobody noticed because it doesn't error
  loudly, or there's something about mypy's discovery this project hasn't fully characterized. Either
  way it's worth resolving for all four subprojects together, not just body-layer, when this is
  looked at.

## Optional Refinements

- **[SUGGESTED] `.claude/scripts/push-roadmap-gate.sh:30`** hardcodes
  `^(world-model|aircraft-layer|body-layer)/src/` to decide whether a merge "looks like a feature
  merge" needing a ROADMAP.md update. `commit-quality-gate.sh` was hardcoded the same way twice
  before being rewritten to `for sub in */; [ -d "$sub/src" ] && [ -d "$sub/tests" ]` discovery —
  its own comment names the exact failure this recreates: *"the 2026-09-21 audit then found
  audio-adapter/ and mission-interpreter/ running zero checks on a commit that touched only them."*
  As written, a merge that touches only `brain-layer/src/`, `audio-adapter/src/`, or
  `mission-interpreter/src/` will never trip this gate, so it can land without a ROADMAP.md update
  and nothing will say so. It fails open by design ("a safety net, not a hard requirement"), so this
  is not a blocker, but it's the same bug recurring a third time in the file sitting right next to
  the two already-fixed instances. Fix: swap the hardcoded alternation for the same `*/src/`-with-`src`-and-`tests`
  directory-existence check `commit-quality-gate.sh` uses.

- **[NOTE, no action needed]** Agent-memory hygiene checked out clean: for every role directory
  under `.claude/agent-memory/`, the number of `- [...]` index entries in `MEMORY.md` exactly equals
  the number of memory files on disk (architect 46/46, debugger 16/16, dod 6/6, implementer 106/106,
  investigator 30/30, performance-reviewer 8/8, reviewer 98/98, security 6/6) — no orphaned files,
  no phantom index entries. `.claude/agent-memory/skill-candidates.md` has zero open (`##`-headed)
  entries; all past candidates are resolved (created or rejected with reasons) under its non-`##`
  "Resolved" marker.

- **[NOTE, cosmetic only]** All 8 `.claude/agents/*.md` files declare `model: claude-sonnet-5`,
  including `dod` (confirming the 2026-09-20 raise from haiku actually landed in the file, not just
  in prose). Root CLAUDE.md's "most are `claude-sonnet-5`" is now slightly imprecise (all of them
  are) but not wrong or misleading enough to act on.

- **[NOTE]** `todo/todo.md`'s old "## Cross-cutting / unscoped backlog" heading (line 302) is now a
  three-line pointer to `todo/backlog.md`, not duplicated content — the 2026-09-27 split was done
  cleanly on this side.

## Five Fixes Worth Doing First

1. Rewrite or neutralize the `UserPromptSubmit` role-sequence hook text in `.claude/settings.json`
   (~line 96) — it currently tells every turn that Security may be exempt when CLAUDE.md says it
   isn't.
2. Rewrite `.claude/scripts/session-start.sh`'s injected text to match CLAUDE.md's current 5-step
   Session Start protocol (ROADMAP.md first, backlog.md included, the git-branch state check).
3. Drop or correct the hardcoded 3-subproject bullet list in `CLAUDE.md`'s "Subprojects" section
   (lines 63-66) — the section 40 lines above it already warns against exactly this.
4. Add an `investigator` section to `docs/AGENT_ROLES.md`.
5. Reproduce (with mypy actually installed) whether `commit-quality-gate.sh`'s uniform
   `mypy "$sub/src"` invocation silently drops `strict`/`mypy_path` for body-layer (and possibly
   world-model/aircraft-layer/audio-adapter too), then apply the same per-subproject `cd` handling
   `check`/`dod-check`/`posttooluse-mypy.sh` already use.

## Review Confidence

Full read on: root `CLAUDE.md`, `AGENTS.md`, `docs/AGENT_ROLES.md` (structure + investigator grep),
`.claude/settings.json`, `commit-quality-gate.sh`, `push-roadmap-gate.sh`, `posttooluse-mypy.sh`,
`session-start.sh`, `graph-query-reminder.sh` (header), all 8 `.claude/agents/*.md` frontmatter,
`check`/`compile`/`test`/`dod-check` SKILL.md bodies, `agents.template.md`, all agent-memory
`MEMORY.md` indexes cross-checked against file counts, `skill-candidates.md`, backlog ID prefixes
across `aircraft-layer/ROADMAP.md`, `audio-adapter/ROADMAP.md`, `world-model/ROADMAP.md`,
`body-layer/BACKLOG.md`, `todo/backlog.md`, and `todo/todo.md`'s post-split state.

Spot-checked only (time-boxed, lower risk): `docs/PROCESS.md` (grepped for todo/backlog/NOTES
references only, not read in full), the bodies of `debugger.md`/`architect.md`/`investigator.md`
beyond their graph-query step placement, and the remaining ~20 skills not named above (skimmed for
hardcoded subproject lists via grep, not read end to end). The mypy CWD-discovery finding above is
explicitly flagged as inferred-not-reproduced since this sandbox has no usable mypy install — treat
it as a strong lead, not a confirmed defect, until reproduced.
