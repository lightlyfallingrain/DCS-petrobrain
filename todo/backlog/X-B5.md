# X-B5 — Review this repo's Claude configuration itself

- [x] **X-B5 — Run Reviewer, Performance Reviewer and Security on this repo's Claude configuration
  itself.** #status/done Done 2026-09-27. All three roles ran in worktrees, advisory-only as this item required;
  reports at `reviews/claude-setup-{review,performance,security}.md`. All HIGH/MEDIUM findings fixed
  with the user in the loop in `d1c5724`.

  **What the audit actually found, beyond the seed list below** (most of which had self-corrected by
  the time it ran — the mirror contradiction, the "Current Focus" dead reference, `dod-check`'s
  hardcoded list and the `AGENTS.md` role count were all already fixed):
  - Two mechanisms injecting text into *every turn* had drifted from `CLAUDE.md`, each toward
    skipping a step it requires: the `UserPromptSubmit` reminder omitted Security entirely and
    asserted an exemption revoked on 2026-09-24, and `session-start.sh` still taught the
    todo.md-derived milestone protocol with no ROADMAP.md and no branch/worktree state check.
  - **`commit-quality-gate.sh` could not pass at all.** It invoked bare `ruff`/`mypy`/`pytest`, none
    of which are on `PATH` (each subproject has its own `.venv`), so every check exited 127 and the
    gate blocked any commit touching subproject code. Invisible for as long as commits touched only
    `.claude/`, `docs/` and `todo/`. It also ran mypy from the repo root, where config discovery is
    CWD-only — `body-layer` reports 6 phantom import errors from there and none from inside.
  - The deny list was defeated by ordinary flag rewrites (`rm -fr`, `git worktree remove -f`,
    `git -C <dir> reset --hard`), the last of these demonstrated destroying an uncommitted change.
    Replaced by argv-aware parsing in `destructive-command-gate.sh`.
  - The hardcoded-three-of-six defect recurred in three more places (`posttooluse-mypy.sh`,
    `push-roadmap-gate.sh`, root `CLAUDE.md`'s Subprojects section) — all now discovery-based.

  **Two lessons worth more than the fixes**, both about how the audit itself went wrong:
  - *A rule whose trigger is unobservable stays broken, and so does a script nobody executes.* The
    performance pass read `commit-quality-gate.sh`, called it "correctly scoped", and never ran it;
    one synthetic payload would have shown the 127s. For a hook, running it with a fake input is the
    first step, not the last.
  - *File counts do not predict cost for an incrementally-cached tool.* The same pass estimated
    whole-subproject mypy at 3–8s per edit from file counts and recommended narrowing the check.
    Measured with the real venv it is **110ms** warm — and a single file is also 110ms. The
    recommendation was dropped rather than applied, and the estimate would have bought a real loss of
    coverage for nothing.

  **Left open, deliberately** (all low-priority; see the reports for detail): `body-layer/CLAUDE.md`
  at ~24K tokens is the largest fixed-context item in the setup and wants a content pass by whoever
  owns it; the `UserPromptSubmit` reminder has no session-marker gate, so it re-injects ~170 tokens
  every turn; agent-dispatch overhead (~20–40K tokens × 5–6 per feature) is structural to
  worktree isolation and was sized for visibility, not for cutting.

  Original framing follows.

  The config is treated as prose nobody reviews, while it is
  in fact the thing that decides how every agent behaves — and a defect in it is executed rather
  than read.

  Scope: `CLAUDE.md` (root and every subproject's), `AGENTS.md`, `docs/AGENT_ROLES.md`,
  `docs/PROCESS.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/settings.json`
  hooks and its deny list, `.claude/scripts/`. Each role reads it as its own kind of artifact:
  **Reviewer** for contradiction between files and instructions that cannot be followed as written;
  **Performance Reviewer** for what the configuration costs per session and per agent — context
  loaded on every turn, hook latency on every tool call, agents spawned where one would do;
  **Security** for the hooks and scripts as executable surface, the deny list's actual coverage, and
  what an agent is permitted to do without asking.

  **Seed material already found, 2026-09-25, not yet acted on** — the skill-file sweep (`a5fd5ef`)
  surfaced these in files it was told not to edit:
  - Root `CLAUDE.md` hardcodes three subprojects in four separate sections (Current priority,
    Subprojects, Milestone Completion, Verification). There are six — `git ls-files '*/pyproject.toml'`.
    `brain-layer` has shipped code and is named in none of them. The same class of defect made
    `/check`, `/compile`, `/test` and `/dod-check` capable of reporting PASS while never looking at
    half the repo.
  - **A live contradiction**: root `CLAUDE.md`'s "Knowledge graph" says the graph is built from the
    `graphify-corpus/` mirror; `.claude/skills/graph-refresh/SKILL.md` says that mirror was removed
    because it broke cache lookups and leaked `graphify_corpus_*` into the graph's vocabulary, and
    that it must not be reintroduced. One of the two is wrong and the skill is the newer.
  - Root `CLAUDE.md`'s "Subprojects" sends readers to `todo/todo.md` "Current Focus" for BL-x
    status, which the same file's "Current priority" section says no longer holds milestone
    narrative. There is no "Current Focus" heading in this file.
  - Root `CLAUDE.md`'s "Agents" asserts a role count and that all roles use one model, immediately
    followed by its own dated exception — the shape that goes stale silently.
  - `AGENTS.md`'s "Roles (one-liners)" lists seven and omits `investigator`, which root `CLAUDE.md`
    describes at length. Its "Recommended Role Sequences" still points at a possible exemption of
    security/performance-reviewer that `CLAUDE.md` replaced on 2026-09-24 with a cadence.
  - `AGENTS.md`'s rule 2 still says "trial this before relying on it" inside a section headed
    "Status: all three rules in force".

  Note the precedent this sits on: the skill sweep was worth running because three of its findings
  were *already wrong at the time of the audit*, not merely aging. The same is likely here, and the
  blast radius is larger — `CLAUDE.md` is loaded into every session, so a wrong line there is
  believed by every agent from its first turn. Do not let the roles edit the config themselves;
  `integrity-audit` is deliberately diagnostic-only and this should keep that posture — report,
  then apply with the user in the loop.
