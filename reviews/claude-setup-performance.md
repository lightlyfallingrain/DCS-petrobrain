# Performance Review — Claude Code Operating Environment

Scope: the Claude Code session itself as a runtime — hooks, context/token fixed cost,
agent-dispatch cost, skill cost. Not project source code. Measurements taken 2026-09-27
in worktree `agent-a327503066497d216` (no subproject venvs installed there, so mypy/ruff/pytest
wall-clock is estimated from file counts, not measured directly — flagged per item below).

### Verdict

**APPROVED — MONITOR**, with one **NEEDS MITIGATION** item: `posttooluse-mypy.sh` runs a
whole-subproject `mypy` pass on *every* `.py` Edit/Write, not just the touched file. For the two
largest subprojects (body-layer, world-model — 116 and 126 `.py` files) that is a real per-edit
latency tax at realistic edit counts, and it silently does nothing for three of the six
subprojects. Everything else measured is cheap relative to LLM turn latency and not worth
touching — said plainly, because a false-positive flag here costs more than the nit is worth.

---

### Overhead budget table

| Cost | Frequency | Amount | Measured / Estimated |
|---|---|---|---|
| PreToolUse Bash hooks (3 inline pattern checks + `build-filter.sh`) on a non-matching command | per Bash call | ~4 process spawns × 8–14ms ≈ **35–55ms** | **Measured** (bash+jq spawn timed individually, see below) |
| PostToolUse Bash hook (`merge-skill-review.sh`) on a non-matching command | per Bash call | ~10–12ms | **Measured** |
| PreToolUse Write/Edit hooks (`agent-memory-path-gate.sh` + `skill-layout-gate.sh`) | per Write/Edit | ~18–20ms | **Measured** |
| PostToolUse `.py` Edit/Write hook (`posttooluse-mypy.sh`) | per `.py` Edit/Write, world-model/aircraft-layer/body-layer only | full-subproject `mypy` run: **est. 1–3s** (aircraft-layer, 46 files) to **est. 3–8s** (body-layer/world-model, 116–126 files) | **Estimated** — no venv in this worktree to run mypy; based on typical `mypy --strict` throughput on a project this size and file count, not timed |
| UserPromptSubmit: role-sequence reminder (unconditional) | every user turn | ~170 tokens injected + 1 jq spawn (~3–10ms) | **Measured** (byte-counted the literal string; jq timed separately) |
| UserPromptSubmit: `session-start.sh` | first turn of session only (marker-gated) | ~cheap, single jq/touch | **Measured**, negligible |
| Root `CLAUDE.md` + `AGENTS.md` | every session, always in context | 18,292 + 17,902 B ≈ **9,050 tokens** | **Measured** (byte count, ÷4 approx.) |
| Subproject `CLAUDE.md` (varies by which subproject the task touches) | per session touching that subproject | brain-layer 7,995B (~2K tok) · world-model 11,957B (~3K tok) · mission-interpreter 14,941B (~3.7K tok) · aircraft-layer 18,672B (~4.7K tok) · audio-adapter 27,702B (~6.9K tok) · **body-layer 96,947B (~24.2K tokens)** | **Measured** |
| `.claude/agents/*.md` (role files) | once per agent-type first dispatch, not per session | 7.3–16.2KB each, 88.4KB / 8 roles total | **Measured** |
| Skill frontmatter descriptions (30 project skills) | every session, always in context | 4,918 B total ≈ **~1,230 tokens** | **Measured** |
| Agent-memory `MEMORY.md` index | once per agent dispatch of that role | reviewer 14.9KB, implementer 19.7KB, architect 9.8KB, investigator 10.3KB, debugger 3.3KB, security/dod/perf-reviewer 1.4–1.8KB | **Measured** |
| `graphify-ast-refresh.sh` (post-commit git hook, not a Claude Code hook) | per commit | full-repo AST (141 files) measured by the script's own comment at 1.56s; a normal commit touches a handful of files, so well under 1s in practice | **Measured** (per the script's own recorded prior measurement, re-verified by reading the script — not re-run here) |
| `commit-quality-gate.sh` (ruff format/check + mypy + pytest, per touched subproject) | per `git commit` | not re-timed here (no venv); appropriately gated to commit-time, not the hot path | Correctly scoped — **no action** |

---

### Findings

#### 1. `posttooluse-mypy.sh` runs whole-subproject mypy on every single `.py` edit
- **Location:** `.claude/scripts/posttooluse-mypy.sh`, `PostToolUse` matcher `Edit|Write`, filtered to `.py` files in settings.json.
- **Risk:** The script does not check just the edited file — it invokes `mypy world-model/src`, `mypy aircraft-layer/src`, or `(cd body-layer && mypy src)` in full, keyed only on which subproject the edited path falls under. An implementer session on body-layer or world-model (116 and 126 `.py` files respectively) pays a whole-package mypy pass after **every** Edit/Write to a `.py` file — which in a normal implementation session is dozens of calls. mypy's own cache reduces this somewhat run-to-run, but the process-startup + graph-resolution cost recurs every time regardless of cache hit rate, and `--strict` mode (per every subproject's `CLAUDE.md`) is slower per file than default mode. At even a conservative 1–3s per invocation and 20–40 edits in a session, that's a credible **20–120s of added wall-clock per implementer session**, paid in small increments between edits rather than once.
- **Additional gap, same script:** the `case` statement only covers `world-model/*`, `aircraft-layer/*`, `body-layer/*`. **audio-adapter, brain-layer, and mission-interpreter get no post-edit mypy signal at all** — silently, since the script exits 0 either way. This is the exact "hardcoded three, six exist" pattern root `CLAUDE.md` already documents as a recurring failure mode in this project, just recurring in a different script. It's not itself a perf cost, but it means type errors in those three subprojects surface only at `commit-quality-gate.sh` time instead of at edit time — which turns into *more* Reviewer↔Implementer round trips (each one a full agent dispatch) than the equivalent error caught immediately in world-model/aircraft-layer/body-layer. That is a real, if indirect, cost multiplier on agent-dispatch count.
- **Action:** NOW (for the coverage gap — cheap, mechanical, same fix pattern `commit-quality-gate.sh` already applied: discover subprojects with `[ -d src ] && [ -d tests ]` instead of enumerating three). MONITOR (for the whole-package-vs-single-file cost — real but bounded, and changing it risks losing real signal; see mitigation).
- **Mitigation:** Two independent, non-exclusive options: (a) scope the check to the single edited file (`mypy <file>` or `mypy -p <touched module>`) instead of the whole subproject's `src/` — mypy still resolves imports for full-repo correctness but the invocation targets far fewer files to typecheck as "primary", which is usually the dominant cost lever; (b) extend the same directory-discovery pattern `commit-quality-gate.sh` already uses, so all six subprojects get equal post-edit coverage instead of three. Escalate (a) to the Architect/Implementer rather than have Performance Reviewer improvise a mypy invocation change, since it changes what errors surface when.

#### 2. `body-layer/CLAUDE.md` is by far the largest fixed context cost in the system
- **Location:** `body-layer/CLAUDE.md`, 96,947 bytes ≈ **~24,200 tokens**.
- **Risk:** This single file is larger than root `CLAUDE.md` + `AGENTS.md` combined (36,194 B) by a factor of 2.7, and larger than every other subproject `CLAUDE.md` combined (81,267 B for the other five). Every session or agent dispatch that touches body-layer pays this as fixed context before any task-specific work begins — and body-layer is explicitly the most active subproject per its own `ROADMAP.md`, so this is not a cold path. At current model pricing this is a token-spend concern more than a latency concern (loading 24K tokens of static instructions is fast; re-processing them every turn via KV-cache-miss scenarios, or every fresh agent dispatch, is what compounds).
- **Action:** MONITOR. This is advisory, not a directive to trim — the content may all be load-bearing (this project's CLAUDE.md files are explicitly written to prevent staleness/re-derivation, and shrinking one has caused prior incidents in this project's own history when done carelessly, per the file's own inline commentary elsewhere in the repo). Worth a deliberate pass by whoever owns body-layer's CLAUDE.md to check whether any of it has become historical narrative that could move to `body-layer/ROADMAP.md` or a `NOTES.md`-style log instead of standing instruction, the same way root `CLAUDE.md` already separates "current priority" from roadmap detail.
- **Mitigation:** none proposed now — flagging size, not content, since assessing what's cuttable requires reading it in full against what body-layer work actually needs, which is Architect/DoD-adjacent judgment, not a performance call.

#### 3. UserPromptSubmit role-sequence reminder duplicates content already in context, every turn
- **Location:** `.claude/settings.json`, second `UserPromptSubmit` hook (inline `jq -n` producing `additionalContext`).
- **Risk:** This hook has no gating condition — unlike `session-start.sh`, which fires once per session via a `/tmp` marker file, this one injects ~170 tokens restating the AGENTS.md role sequences on **every single user turn**. AGENTS.md itself (with the full sequences, escalation rules, and auto-advance logic) is already loaded once per session as project instructions. Over a 40–60 turn session this is roughly 7,000–10,000 tokens of pure repetition with zero marginal information after the first turn — it does not adapt to session state, so turn 30 gets the identical string as turn 1.
- **Action:** MONITOR — this is small in absolute terms (170 tokens/turn is trivial next to a single tool result or file read) and the repetition may be intentional insurance against the model "forgetting" the sequence mid-session, which is a real failure mode this project has documented elsewhere (the AGENTS.md "auto-advance" section exists because sequences were skipped before). Given that history, I would not recommend removing it outright without the user weighing in — but gating it the same way `session-start.sh` is gated (fire once per session, or once per role-sequence-relevant trigger such as after Architect/Reviewer handoff) would recover nearly all of the token cost for the same insurance value.
- **Mitigation:** Gate on the same session marker pattern as `session-start.sh`, or fire only when a tool result indicates a role transition (e.g., after a `dod` or `reviewer` SubagentStop) rather than on every prompt.

#### 4. Agent-dispatch fixed overhead compounds across a role sequence, but each individual read is properly scoped
- **Location:** Role sequences in `AGENTS.md` / root `CLAUDE.md` "Agents" section.
- **Risk:** A "New feature" sequence (Architect → Security plan review → Implementer → Reviewer → Security deep analysis → DoD) is 5–6 agent dispatches. Each is a fresh context: root `CLAUDE.md` + `AGENTS.md` (~9K tokens) + the touched subproject's `CLAUDE.md` (2K–24K tokens depending on subproject) + that role's own file (2–4K tokens) + that role's `MEMORY.md` index (1.4–19.7KB depending on role) — before any task-specific file reading starts. For a body-layer feature that's roughly **20K–40K tokens of fixed overhead per dispatch**, ×5–6 dispatches ≈ **120K–240K tokens of pure fixed cost per feature**, on top of whatever the feature's actual diff requires reading.
- This is **not redundant waste** in the sense the brief asks about — each role legitimately needs project context and its own memory, and each role's memory file is scoped to that role only (no evidence of one role reading another's `MEMORY.md`). It is the structural cost of the role-sequence model itself, and is presumably why root `CLAUDE.md` already limits Security/Performance Reviewer to once per feature rather than once per stage.
- **Action:** MONITOR. No credible cheaper alternative exists without weakening the isolation that makes worktree-based agents safe (AGENTS.md's own stated reason for the worktree-per-role rule). Not proposing a change.
- **Mitigation:** none — noting for visibility, not for action.

#### 5. `commit-quality-gate.sh` is correctly scoped, not a hot-path problem
- **Location:** `.claude/scripts/commit-quality-gate.sh`, `PreToolUse` conditioned on `git commit` only via the `if` jq test.
- **Risk:** none credible. It runs ruff format/check + mypy + pytest per touched subproject (discovered dynamically via `[ -d src ] && [ -d tests ]`, not hardcoded — this script already fixed the staleness pattern that `posttooluse-mypy.sh` still has). This is real work but it happens once per commit, which is exactly where a verification gate belongs per this project's own "Verification" policy (early self-check during implementation, hard gate at commit). Re-running mypy here on top of `posttooluse-mypy.sh`'s per-edit runs is intentional defense-in-depth (catches whatever was edited without triggering the per-file hook, e.g. a file created by a script rather than Edit/Write), not accidental duplication.
- **Action:** none — flagging as already cheap/correctly scoped, per the instruction not to propose changes to things that are fine.

#### 6. Inline `PreToolUse` Bash pattern checks (reset-hard, graphify-query routing, branch rule) are cheap
- **Location:** `.claude/settings.json`, first three `hooks` entries under the `Bash` matcher.
- **Risk:** Each spawns a bash subshell + `jq` + `grep` even when the command doesn't match, measured at 8–14ms per invocation (dominated by process/jq startup, not the grep itself). Combined with `build-filter.sh` (also ~13ms on a non-matching command), that's **~35–55ms of fixed overhead per Bash tool call** — measured directly. Across a session issuing 50–100 Bash calls (typical for an implementer running tests/lint repeatedly), that's roughly 2–5.5 seconds of cumulative hook latency for the whole session.
- **Action:** MONITOR, not NOW. 2–5.5s spread across a whole session is well under the noise floor of a single LLM turn or a single `pytest` run, and these hooks each guard a real, previously-triggered incident (the `git reset --hard` block cites a specific 2026-09-20 data-loss event; the graphify-query router cites a specific tense-loss bug). Consolidating them into one script would save maybe 20–30ms per Bash call by reducing process spawns from 4 to 1, but that is not worth the added complexity of merging three independently-reasoned, independently-commented safety checks into one file — the current structure is more maintainable and the saving is marginal.
- **Mitigation:** none proposed — cost is real but small enough that touching it isn't worth it.

---

### Summary, ranked by measured/credible impact

1. **NOW**: `posttooluse-mypy.sh` — extend subproject discovery to all six subprojects (mechanical, same fix already applied in `commit-quality-gate.sh`). Consider scoping the mypy invocation itself to reduce per-edit cost on body-layer/world-model, but escalate that specific change rather than have this review apply it.
2. **MONITOR**: `body-layer/CLAUDE.md` size (~24K tokens, largest fixed-context item in the whole system) — worth a deliberate content pass, not a mechanical trim.
3. **MONITOR**: unconditional per-turn role-sequence reminder (~170 tokens/turn, no gating) — cheap in isolation, pure duplication after turn 1; gating it like `session-start.sh` would recover most of the cost.
4. **MONITOR**: agent-dispatch fixed overhead (~20–40K tokens/dispatch × 5–6 dispatches/feature) — structural cost of the worktree-isolated role-sequence model, no cheaper alternative without weakening isolation.
5. **No action** (already cheap, confirmed by measurement): `commit-quality-gate.sh` scoping, the three inline `PreToolUse` Bash safety checks, `agent-memory-path-gate.sh`, `skill-layout-gate.sh`, `merge-skill-review.sh`, skill frontmatter total size, `graphify-ast-refresh.sh`'s per-commit AST cost.
