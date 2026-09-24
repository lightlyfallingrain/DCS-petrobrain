---
name: retro
description: Multi-agent retrospective — every workflow role (architect, implementer, reviewer, debugger, performance-reviewer, security, dod, investigator) inspects its own persistent memory for a time window, and the orchestrator inspects its own session transcript, each reporting what worked, what failed, and what to learn; findings are synthesized and turned into concrete config/workflow proposals. Use when the user asks for a retro, a process review, or "what have we learned" across the agent workflow.
type: user-invocable
---

Multi-agent retrospective. Usage: `/retro` (defaults to the window since the last retro) or
`/retro <window>` (e.g. `/retro this week`, `/retro since 2026-09-08`) as an explicit override.

This is a meta-process review of *how the agents worked* — the 8 workflow roles and the
orchestrator (you, running this skill) — not of the product. Each participant reads only its own
record of its own reasoning — role agents their `agent-memory/`, the orchestrator its own session
transcript — never re-derives conclusions by reading the underlying code fresh. That's the whole
point: it measures whether the memory/transcript record and the role process are actually paying
off, using only what was actually recorded, not a fresh audit.

**Why the orchestrator uses its transcript, not a memory file:** the orchestrator already has a
persistent memory system (auto-memory, user/feedback/project/reference — cross-session, distinct
purpose: durable facts, not a session's reasoning trail). A second, role-style
`agent-memory/orchestrator/` would duplicate that rather than add anything — and would need the
orchestrator to *decide in advance* what today's retro-relevant moments were, which is exactly
the bias a retrospective is supposed to avoid. The transcript is already the complete, unbiased
record; read it fresh each time instead of maintaining a parallel store of self-selected excerpts.

## Step 1 — Resolve the time window

Default: since the last retro. Read `.claude/state/last-retro` (repo root, tracked in git) — it
holds a single ISO date, the end of the last successful retro's window. If present, the window is
`--since="<that date> 00:00" --until="<today> 00:00"`. If absent (first run, or the file was
never created), fall back to today (`--since="<date> 00:00" --until="<next-date> 00:00"`) and say
plainly in the retro's own output that no marker was found and today was used as the default. If
the user gives an explicit `<window>` argument, that overrides the marker entirely — resolve it to
concrete `--since`/`--until` values before spawning anything. Either way, every role agent needs
the same resolved window.

## Step 1b — Resolve the branch under review

Determine which branch this retro is actually reviewing (the active feature branch, or `main` if
nothing is in flight — check `git branch --show-current` and/or ask the user if it's ambiguous).
Resolve this to a concrete ref **before spawning anything**, and pass it explicitly in every role
agent's prompt: each role's `git log` must run against that ref (e.g. `git log <branch>
--since=... --until=... -- .claude/agent-memory/<role>/`), not against whatever branch its own
worktree happens to have checked out. A read-mostly role agent runs in its own worktree, whose
checked-out history is not guaranteed to contain the branch under review — a `git log` run
against the wrong ref can find zero activity and report a confident, wrong "nothing happened"
when the work is actually there.

Tell every role agent explicitly: if you find no activity in the window, first confirm you are
looking at the right ref (`git log <branch> ...`, not just `git log ...` on whatever's checked
out) before concluding nothing happened. "I see nothing [from where I'm looking]" and "nothing
happened" are different claims — only report the latter after ruling out the former.

## Step 2 — Spawn all 8 roles in parallel

One message, one `Agent` call per role, `subagent_type` set to the role name (`architect`,
`implementer`, `reviewer`, `debugger`, `performance-reviewer`, `security`, `dod`,
`investigator`) — never `fork` here, each role must reason only from its own memory, not from
this conversation's context. Each prompt must be self-contained (fresh agent, no shared
context) and state:

- This is a retrospective, not a request to do the role's normal work — don't plan/implement/
  review/debug/investigate/run-DoD on anything.
- The resolved branch under review (Step 1b) and the resolved `--since`/`--until` window (Step 1).
- Look at `.claude/agent-memory/<role>/` (repo root) via `git log <branch> --since=... --until=...
  --oneline -- .claude/agent-memory/<role>/` (and `git log <branch> -p` on specific files if
  needed) — always against the resolved branch, not whichever branch the role's own worktree
  happens to have checked out — meta-data the role itself wrote (memory files, `MEMORY.md`, and
  narrative sections of its own plan/review/debug/dod-check output), never the underlying code.
  If this comes back empty, re-run against the resolved branch explicitly before concluding there
  was no activity — "I see nothing from my worktree's checkout" and "nothing happened" are
  different claims.
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

## Step 2b — Orchestrator self-assessment

While the 8 role agents run, do the same exercise for yourself, from this conversation's own
transcript (and, if the window extends before this session, any prior sessions on this project
you have transcript access to — `ListAgents` surfaces other sessions on this machine; note
plainly if an earlier part of the window is out of reach rather than guessing at it). Same three
questions, same standard: cite actual turns/decisions/tool calls, not generic self-praise. Things
worth specifically looking for, since these are orchestrator-shaped failure modes the role agents
structurally can't self-report:
- Delegation calls — was spawning an agent (or not spawning one, or forking vs. fresh) the right
  choice each time, in hindsight?
- Redundant or wasted work — tool calls that re-derived something already known, polling loops
  that could have been a single wait, context spent on something that turned out unnecessary.
- Places you should have stopped to ask the user (or shouldn't have) — did autonomy calibration
  match what the user actually wanted?
- Whether your own synthesis/reporting back to the user was accurate, complete, and appropriately
  concise — not just whether the underlying work was correct.

This becomes a 9th input to Step 3's synthesis, held to the same bar as the role reports — a real
finding with a citation, not a rubber stamp.

## Step 3 — Wait for all 8 roles, then synthesize with your own self-assessment

Do not fabricate or predict role results while waiting — each agent's finding arrives as a real
notification. Once all 8 are back, don't just concatenate their reports (plus your own from Step
2b). Read across all 9 for cross-cutting themes: a failure mode named by 2+ participants
independently is a stronger signal than one participant's one-off. Group the synthesis into:

- **Value delivered** — what's working, with the strongest cross-role evidence first.
- **Failure modes** — recurring defect classes, process gaps, anything that cost rework.
- **What to learn** — the underlying mechanism connecting the failure modes (usually simpler than
  the list of symptoms — e.g. "verification that happens automatically is reliable; verification
  that depends on someone remembering a manual step is not").

Present this to the user before proposing any changes.

## Step 4 — Propose concrete changes

For each real finding, propose a specific, mapped change — not a vague "improve X":

- A recurring mistake a role's own instructions already name but didn't prevent → a **hook**
  (PreToolUse gate; see `.claude/skills/update-config/SKILL.md`-style skill or invoke the
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

List proposals prioritized, each with a one-line rationale citing which participant(s) — role(s)
and/or the orchestrator's own self-assessment — surfaced it. A change addressing an
orchestrator-shaped failure mode (e.g. a delegation-judgment pattern) may not map to a hook or an
agent `.md` file at all — it may just be something to do differently next time, worth saying
plainly rather than forcing it into a config change for its own sake.

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

## Step 6 — Write the last-retro marker

On successful completion (Step 3's synthesis was presented and Step 4's proposals were resolved
with the user, whether or not any were implemented), write today's date to
`.claude/state/last-retro` (create the file and its directory if absent), overwriting any previous
value. This is what makes the next `/retro`'s default window start where this one left off — skip
it and the next run silently re-reads the same window. Commit this alongside any Step 5 changes
(or by itself, if the user declined every proposal).

## Rules

- Never let a role agent read the underlying code to "improve" its answer — the whole diagnostic
  value is in exposing what the memory system captured (or failed to capture) on its own. Same
  rule for yourself in Step 2b: answer from the transcript, not from re-reading the diffs to
  reconstruct a tidier account than what actually happened.
- Don't skip a role because it seems unlikely to have activity — an honest "nothing happened,
  here's why" is itself a useful data point (e.g. confirms an exemption is working as intended).
  Same for yourself — a quiet, low-intervention session is a legitimate self-assessment outcome,
  not a finding to manufacture around.
- Keep the retrospective's own output out of `agent-memory/` — it's a meta-review of the roles
  and the orchestrator, not one role's own memory. If a proposal becomes an actual change, that
  change should show up in the normal places (role `.md` files, `settings.json`, `ROADMAP.md`),
  not as a new memory type. Do not create an `agent-memory/orchestrator/` directory — see this
  file's own opening note on why the transcript substitutes for it.
