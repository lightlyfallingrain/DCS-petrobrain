# System Integrity Audit — 2026-09-10

Diagnostic only. No files were edited as part of this audit.

Context: an extremely active session — BL-2.6, BL-3, BL-4, BL-5, BL-5a all merged today, plus a
significant object-permanence bug fix. AGENTS.md/CLAUDE.md gained a new "side quest" worktree rule
today; `.claude/skills/merge/SKILL.md` was rewritten today.

## Tier 1 — Definite integrity problems

### 1. World-model-only hardcoding survives in three places, despite an earlier fix that generalized the same gap elsewhere (most important finding)

On 2026-09-08, commit `2fa2610` ("Fix system-integrity audit findings: stale priority, role-sequence
drift, **per-subproject enforcement gap**") correctly generalized `.claude/scripts/commit-quality-gate.sh`
to detect which subproject(s) a commit touches and run *that* subproject's own format/lint/type/test
commands (world-model, aircraft-layer, body-layer all handled). That fix was never propagated to three
sibling mechanisms that describe the same responsibility:

- **`.claude/agents/dod.md` lines 20-22** — the DoD agent's own hardcoded verification checklist still
  reads:
  ```
  - [ ] `ruff format --check world-model/src world-model/tests` passes
  - [ ] `ruff check world-model/src world-model/tests` passes
  - [ ] `pytest world-model/tests -q` passes
  ```
  Every DoD pass this session (BL-2.6, BL-3, BL-4, BL-5, BL-5a, the gate-ambiguity fix — 8+ runs, several
  touching `body-layer/` exclusively or `body-layer/`+`world-model/` together) had to silently deviate
  from this literal checklist and infer the right subproject(s) from the plan/task context instead. It
  worked every time by luck of good agent judgment, not because the template is correct. `docs/AGENT_ROLES.md`'s
  own DoD section (§7) is generic and does NOT have this problem — only the agent's own system-prompt file does.

- **`.claude/settings.json`'s `PostToolUse` hook on `Edit|Write`** — for any edited `.py` file (matched
  by extension only, not path), runs `mypy world-model/src` unconditionally:
  ```json
  "command": "cd $CLAUDE_PROJECT_DIR && mypy world-model/src 2>&1 | tail -30 || true"
  ```
  Editing a `body-layer/src/belief/*.py` file (the bulk of today's work) triggers a `mypy` run against
  `world-model/src` — output that has nothing to do with the file just edited. It's not incorrect
  enough to fail loudly (`|| true` swallows the exit code), so it silently produces irrelevant signal
  after nearly every edit this session.

- **Root `CLAUDE.md`'s "Verification" section**: "see `world-model/CLAUDE.md` 'Commands' for the current
  list" — phrased as if there is one canonical list. `body-layer/CLAUDE.md` and `aircraft-layer/CLAUDE.md`
  each have their own equally-canonical `## Commands` section (confirmed by reading all three); the root
  file points at only one of the three.

**Why it matters:** all three are fossils from when world-model was the only subproject. The fact that
the enforcement layer (the hook that actually blocks commits) was fixed but the guidance/template layer
(what an agent reads to know what to do) was not, means the *mechanical* safety net exists but the
*documented intent* still lies. A future session or a differently-behaving agent could follow the
literal checklist/hook text and silently verify the wrong subproject, or waste cycles on irrelevant
`mypy` output, with nothing catching it except the commit-time hook's independent (and correct) logic
catching the actual commit — i.e., two sources of truth that currently happen to agree in effect only
because the newer one is authoritative and the older ones are ignored by convention, not because they
were reconciled.

**Corrective action:** update `.claude/agents/dod.md`'s checklist to name all three subprojects (or
reference `commit-quality-gate.sh`'s per-subproject-detection logic instead of hardcoding a list); scope
the `PostToolUse` mypy hook to the subproject containing the edited file (mirror
`commit-quality-gate.sh`'s `git diff`-path-prefix detection, applied to the single file path instead);
reword root `CLAUDE.md`'s Verification section to point at "each subproject's own CLAUDE.md," not
world-model's specifically.

### 2. A corrective lesson was patched into one role template, not generalized, and recurred in a different role this session

`.claude/agents/implementer.md` line 114 has an explicit added warning: writing agent-memory to
`world-model/.claude/agent-memory/implementer/` instead of the repo-root path "is a mistake that has
[recurred]" — added after it happened twice. `.claude/agents/debugger.md` (and the other five role
templates: architect, reviewer, dod, investigator, performance-reviewer, security) have no equivalent
warning — they only state the correct path once, with no history/recurrence note.

This session, the **Debugger** role wrote its own memory files under `body-layer/.claude/agent-memory/debugger/`
— the identical mistake class (cwd-relative path used instead of repo-root-relative), just in a
different role and a different subproject directory. It was caught and fixed manually by the
coordinating session before commit, so `commit-quality-gate.sh`'s stray-memory-path rejection check
(added in the same 2026-09-08 fix, and which *would* have caught it at commit time) was never actually
exercised as a backstop.

**Why it matters:** the lesson was captured as an ad hoc patch to one template instead of a rule that
generalizes across all seven role templates sharing the identical phrasing pattern ("write to
`.claude/agent-memory/<role>/` ... relative to the repo root"). The recurrence in a second role,
one session later, confirms the fix didn't generalize far enough. The commit-time hook is a real
backstop but only fires if the mistake survives to a `git commit` — it did not this time only because
a human/coordinating session happened to catch it first.

**Corrective action:** either add the same recurrence warning to all seven `.claude/agents/*.md` files
(mechanical, low-risk), or move the warning into a shared location referenced by all of them (if the
template system supports a shared include) so it can't drift out of sync as more roles are added.

## Tier 2 — Possible improvements

- **Root `CLAUDE.md`'s "Milestone Completion" section** literally reads "Before marking a milestone
  done in `world-model/ROADMAP.md`..." — but every BL-x milestone this session (which is most of the
  project's current activity) never touches `world-model/ROADMAP.md`; its DoD reports ask the same
  "does this change the next milestone" question anyway, informally, inside `plans/<feature>/dod-check.md`
  files. The intent is being followed by convention, not by what the rule literally says applies to.
  Not urgent (no observed failure from it), but worth rewording to "before marking a milestone done in
  its tracking file (`world-model/ROADMAP.md`, or `todo/todo.md`/`plans/body-layer/plan.md` for BL-x
  work)" so a future reader doesn't conclude the rule doesn't apply to body-layer work.

- **`~/.claude/projects/-Users-sg-Code-DCS-petrobrain/memory/project_pb2_next_milestone.md`** (auto-memory,
  not agent-memory): "WM/aircraft-layer/PB-1 all done as of 2026-09-08, next is PB-2/BL-2 contact
  memory." The project is now well past BL-5a and a subsequent bug fix (2026-09-10) — this entry is
  two milestones' worth of history stale. Low-stakes (auto-memory is consulted with a staleness check
  per its own usage rules), but a clear candidate for removal or update the next time auto-memory is
  touched.

- **`.claude/agent-memory/skill-candidates.md`'s "Resolved" log** is healthy (three prior rejections
  recorded with reasons, one creation) — no long-accumulating unreviewed backlog found. No action
  needed; noted only because Phase 5 explicitly asks to check.

- **Two independent sqlite3-thread-affinity bugs this session** (BL-3's `EnrichmentContext.conn` read
  from the REPL thread; the original PB-2 Stage 6 bug it structurally resembles) are already captured
  as agent memory (`.claude/agent-memory/reviewer/project_bl5_repl_thread_sqlite_fix.md`,
  `.claude/agent-memory/debugger/project_sqlite_thread_affinity_bodylayer.md`) with an explicit
  "grep any new `ConsolePerceptionRunner` field for REPL-thread reads of a `sqlite3.Connection`"
  instruction. This is a good example of the right promotion candidate — recurring pattern, explicit
  future-check instruction — and is *not* flagged as a problem; it's already at the right altitude
  (agent memory, not yet a permanent rule, since it's only recurred twice and is narrowly scoped to
  one field-addition pattern). Revisit promoting it to `body-layer/CLAUDE.md` if it recurs a third time.

## Summary

**Tier 1 (definite): 2 findings.** Both are the same underlying class — a fix applied once (the
2026-09-08 per-subproject audit fix) that didn't propagate to every place describing the same
responsibility, so stale/incomplete copies survive alongside the corrected one. Most important:
finding 1 (world-model-only hardcoding in `dod.md`, the `PostToolUse` mypy hook, and root
`CLAUDE.md`'s Verification section) — three fossils from a single-subproject era, still active in a
now three-subproject project, papered over so far only by individual agents' good judgment rather
than by the documentation/hooks actually being correct.

**Tier 2 (possible improvements): 3 items.** A stale rule-scope wording, one stale auto-memory entry,
and one confirmation that memory hygiene elsewhere is currently healthy.
