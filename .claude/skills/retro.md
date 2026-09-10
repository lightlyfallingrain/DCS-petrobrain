---
name: retro
description: Multi-agent retrospective — every workflow role (architect, implementer, reviewer, debugger, performance-reviewer, security, dod, investigator) inspects its own persistent memory for a time window and reports what worked, what failed, and what to learn; findings are synthesized and turned into concrete config/workflow proposals. Use when the user asks for a retro, a process review, or "what have we learned" across the agent workflow.
type: user-invocable
---

Multi-agent retrospective. Usage: `/retro` (defaults to today) or `/retro <window>` (e.g.
`/retro this week`, `/retro since 2026-09-08`).

This is a meta-process review of *how the agents worked*, not of the product. It reads only
memory/notes each role already wrote about its own reasoning — never re-derives conclusions by
reading the underlying code fresh. That's the whole point: it measures whether the memory system
and role process are actually paying off, using only what they themselves recorded.

## Step 1 — Resolve the time window

Default: today (`00:00`–`24:00` in the project's date, i.e. `--since="<date> 00:00"
--until="<next-date> 00:00"` for `git log`). If the user gives a window, resolve it to concrete
`--since`/`--until` values before spawning anything — every role agent needs the same window.

## Step 2 — Spawn all 8 roles in parallel

One message, one `Agent` call per role, `subagent_type` set to the role name (`architect`,
`implementer`, `reviewer`, `debugger`, `performance-reviewer`, `security`, `dod`,
`investigator`) — never `fork` here, each role must reason only from its own memory, not from
this conversation's context. Each prompt must be self-contained (fresh agent, no shared
context) and state:

- This is a retrospective, not a request to do the role's normal work — don't plan/implement/
  review/debug/investigate/run-DoD on anything.
- The resolved `--since`/`--until` window.
- Look at `.claude/agent-memory/<role>/` (repo root) via `git log --since=... --until=...
  --oneline -- .claude/agent-memory/<role>/` (and `git log -p` on specific files if needed) —
  meta-data the role itself wrote (memory files, `MEMORY.md`, and narrative sections of its own
  plan/review/debug/dod-check output), never the underlying code.
- Role-specific supplementary sources, since not every role's output lives only in
  `agent-memory/`:
  - `dod`: also check `plans/*/dod-check.md` files touched in the window — DoD's real findings
    often land there even when `agent-memory/dod/` itself wasn't updated.
  - `investigator`: also check for `*/research/<date>-*.md` files in the window — dated findings
    are its other primary output format.
  - `performance-reviewer` / `security`: these may show zero activity in a given window if the
    project's `CLAUDE.md` currently exempts them from the default role sequence — that's a valid,
    expected finding, not a gap to paper over.
- Answer exactly three questions, grounded only in what was found: (1) what worked well and
  brought value, (2) what failure modes occurred or didn't bring value, (3) what to learn — any
  pattern worth changing. Cite actual file names/content, not generic process platitudes. If
  there's no activity in the window, say so plainly rather than inventing findings.
- A word budget (~200–250 words; shorter, ~150–200, for a role likely to report no activity).

## Step 3 — Wait for all 8, then synthesize

Do not fabricate or predict results while waiting — each agent's finding arrives as a real
notification. Once all 8 are back, don't just concatenate their reports. Read across all of them
for cross-cutting themes: a failure mode named by 2+ roles independently is a stronger signal
than one role's one-off. Group the synthesis into:

- **Value delivered** — what's working, with the strongest cross-role evidence first.
- **Failure modes** — recurring defect classes, process gaps, anything that cost rework.
- **What to learn** — the underlying mechanism connecting the failure modes (usually simpler than
  the list of symptoms — e.g. "verification that happens automatically is reliable; verification
  that depends on someone remembering a manual step is not").

Present this to the user before proposing any changes.

## Step 4 — Propose concrete changes

For each real finding, propose a specific, mapped change — not a vague "improve X":

- A recurring mistake a role's own instructions already name but didn't prevent → a **hook**
  (PreToolUse gate; see `.claude/skills/update-config.md`-style skill or invoke the
  `update-config` skill directly) that catches it before the mistake happens, not after.
- A process step skipped because it depends on someone remembering → a **mechanical backstop**
  (a script wired into an existing hook point, e.g. gating `git push`/`git commit`) rather than
  a reminder added to prose that can be skipped the same way again.
- A role missing a check it could reasonably run itself → an edit to that role's own
  `.claude/agents/<role>.md` process steps, with the concrete incident as the worked example (so
  future readers know *why*, not just *what*).
- A caveat that keeps recurring without ever being tracked → a small tracked list in the
  relevant `ROADMAP.md` (see root `ROADMAP.md` / per-subproject `ROADMAP.md` convention), not a
  one-off note that will drift stale itself.
- Explicitly flag findings that need **no** change (e.g. a role correctly reporting no activity
  because of a deliberate project-phase exemption) — don't manufacture a fix for a non-problem.

List proposals prioritized, each with a one-line rationale citing which role(s) surfaced it.

## Step 5 — Implement only on confirmation

Ask the user which proposals to implement (all, some, or none) unless they already said so when
invoking the skill. When implementing:

- Hooks/settings.json changes: follow the `update-config` skill's full construction-with-
  verification workflow (dedup check, pipe-test the raw command, write the JSON, validate with
  `jq -e`, **prove the hook actually fires** via the sentinel-prefix technique, clean up the
  sentinel before finishing).
- Agent `.md` edits: keep them concrete — cite the specific incident/file that motivated the
  change, not just an abstract rule.
- `ROADMAP.md` trackers: match the existing per-subproject roadmap's tone and structure; don't
  invent a new section pattern per retro.
- Commit with a message that names which retro findings drove which change, so a future retro
  (or integrity audit) can see the causal chain instead of an unexplained config diff.

## Rules

- Never let a role agent read the underlying code to "improve" its answer — the whole diagnostic
  value is in exposing what the memory system captured (or failed to capture) on its own.
- Don't skip a role because it seems unlikely to have activity — an honest "nothing happened,
  here's why" is itself a useful data point (e.g. confirms an exemption is working as intended).
- Keep the retrospective's own output out of `agent-memory/` — it's a meta-review of the roles,
  not one role's own memory. If a proposal becomes an actual change, that change should show up
  in the normal places (role `.md` files, `settings.json`, `ROADMAP.md`), not as a new memory type.
