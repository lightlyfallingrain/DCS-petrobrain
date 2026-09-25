# DoD Check: brain-layer BR-1 Stage 1

Branch `feature/brain-layer` @ `9e135a7` (not yet merged). Verification below was run against
`1f0dd63`; the one commit added after (`9e135a7`, "Reframe the loopback default") touches only a
shell-script comment in `run-scripts/run-brain.sh` — no source, no test — so re-running format/
lint/type/test was not needed, and was confirmed unnecessary by reading that commit's diff
directly (`git show 9e135a7 --stat`: one file, `run-scripts/run-brain.sh`, comment only). Checked
from an isolated `git archive` scratch tree (`/private/tmp/.../scratchpad/brtree`), not the DoD
worktree's own checkout — the worktree is `main`-based and cannot check the branch out a second
time, and `pytest`'s `pythonpath` override has silently reported `main`'s baseline in place of a
branch's own figures before
(`.claude/agent-memory/dod/feedback_dod_worktree_pythonpath_trap_applies_here_too.md`).

## Subprojects touched

`git diff --stat main..feature/brain-layer` shows two code subprojects — `body-layer/`,
`brain-layer/` (new) — plus `plans/`, `docs/`, and agent-memory files. No `aircraft-layer/`,
`world-model/`, `audio-adapter/`, or `mission-interpreter/` changes.

## Code Quality

| Subproject | format | lint | mypy --strict | pytest | Result |
|---|---|---|---|---|---|
| body-layer | `105 files already formatted` | `All checks passed!` | `Success: no issues found in 49 source files` | `1220 passed, 4 xfailed in 12.65s` | PASS — matches expected 1220/4 |
| brain-layer | `8 files already formatted` | `All checks passed!` | `Success: no issues found in 5 source files` | `20 passed in 4.30s` | PASS — matches expected 20 |

All four commands run verbatim, from inside the archived tree's own subproject directory, against
each subproject's own venv (`/Users/sg/Code/DCS-petrobrain/{body,brain}-layer/.venv/bin/`, per
task instructions — these venvs exist only in the main checkout, read-only from here).

No `TODO`/`FIXME`/`XXX` in the touched source files. `print()` calls found in
`belief/escalation.py` (`DebugPrintBrainClient`, an intentional debug-aid stand-in, documented as
such in the module docstring) and `logger.py` (pre-existing console-output paths, not new debug
output). One `except Exception:` in `brain-layer/src/server.py:77` — read in context: it is
`_run_job`'s documented crash boundary around `Decider.decide`, logs via `logger.exception` and
drops the job rather than silently swallowing — not suppression, and reviewed as such by Security
(`plans/brain-layer/security-review.md`, `job.py`/thread-safety row).

## Scope & Correctness

- Implementation matches `plans/brain-layer/plan.md` Stage 1: `StubDecider`, `POST /escalate`,
  `GET /replies/poll`, non-blocking handoff, stand-by-after-timeout, staleness revalidation,
  newest-wins at the job-slot level. Confirmed by reading `brain-layer/src/{server,job,decider}.py`
  and `plans/brain-layer/implementation.md` against the plan.
- Reviewer (`review.md`): **APPROVED, no required fixes**, all six focus areas checked out.
- No unplanned scope added: the two Stage 2 prerequisites and D10's absent validator are recorded,
  not built — correctly out of scope for Stage 1.
- `awaiting_reply_to`'s newest-wins exception is honestly left unimplemented (deferred to Stage 3,
  documented in `plan.md`), consistent with "no unplanned scope."
- No CLAUDE.md invariants violated: DCS stays authoritative (nothing in `situational_header`
  carries ground truth — independently re-traced by Security), no in-process cross-subproject
  import introduced (`brain-layer` and `body-layer` talk over HTTP only; Security grepped both
  trees and found none), no DCS installation write, single-player scope respected.
- All new files staged/committed on the branch (see file list in the SubagentHandback report);
  nothing left uncommitted on `feature/brain-layer` itself.

## Testing

- Core logic covered: `test_decider.py`, `test_job.py`, `test_server.py` (brain-layer, 20 tests,
  including the async round-trip, staleness, and generation-superseded cases); `test_brain_client.py`
  (211 new lines, body-layer's poll/parse path); `test_crew_console.py` (328 new lines — stand-by
  timing, drain_brain, pick/confirm/ask handling); `test_speech.py` (unable/stand-by rendering);
  `test_escalation.py` (payload shape).
- Tests are meaningful, not decorative: verified by reading `test_server.py`'s async-handoff and
  superseded-generation cases and `test_crew_console.py`'s stand-by-boundary case directly; these
  assert on behavior (timing, discarded replies), not just "does not raise."
- No existing tests broken: full body-layer suite (1220/4) and brain-layer suite (20) both green
  against the branch tip, matching each role's own prior reported counts.
- Additionally verified live, this session, against a running `python -m brain_layer` process
  (see Live spot-check below) — this repeats what the plan's own `live_cross_process_check.py`
  already established, as a sanity check before writing the acceptance card, not as new evidence.

## Live spot-check (mechanical, not acceptance)

Started `PYTHONPATH=src .venv/bin/python -m brain_layer --port 7797 --stub-delay-s 0` from the
archived tree; confirmed via `urllib` (curl is blocked in this sandbox):
- `GET /health` → `{"ok": true}`
- `POST /escalate` with a minimal payload → `{"ok": true}`
- `GET /replies/poll?after=0` → `[{"kind": "unable", "reason": "NO_SUCH_COMMAND", "utterance_id": "u1", "t_sim": 1.0}]`

This confirms the module name, `PYTHONPATH=src` convention, and the flags `run-brain.sh` uses are
correct and actually produce a working server — not re-derived from reading the code alone.

## Documentation

- Reviewer findings: none required, none outstanding.
- Non-obvious behavior: extensively documented via module docstrings (`escalation.py`, `job.py`,
  `server.py`, `decider.py`) and `body-layer/CLAUDE.md`, rather than a separate `NOTES.md` note —
  consistent with this project's convention of documenting in code/CLAUDE.md where the explanation
  is local to the mechanism.

## Security

- `security-plan-review.md`: **absent.** Consistent with the project's default exemption for the
  Security role at this phase (`CLAUDE.md` "Agents": "Skip performance-reviewer and security for
  now... Only run either when the user explicitly asked"). This feature explicitly invoked Security
  once, for deep analysis after Reviewer — not at the plan stage — which matches both the upstream
  summary and what exists on the branch. Not treated as a DoD failure: the generic criterion
  assumes both passes are the project's default sequence, which this project has deliberately
  narrowed.
- `security-review.md`: **exists, APPROVED**, one recommended (non-blocking) fix — the
  `run-brain.sh` `--host 0.0.0.0` override, which exposed `POST /escalate` to the LAN with no
  compounding gap actually being exploited today. Confirmed fixed: `1f0dd63` removes the `--host`
  flag; `9e135a7` (after the security review, on user direction) rewords the comment so loopback
  reads as the correct *default for this deployment*, not a hardcoded property of the service —
  both changes verified directly by reading the commits on the branch.

## Verdict

**DoD: PASSED** on all mechanical and paper-trail criteria. Live acceptance is outstanding, listed
as debt (below and in `body-layer/ROADMAP.md`'s "Live acceptance debt" list), not counted as
passed — see the Acceptance Testing Plan in the handback report and
`docs/acceptance/2026-09-25-brain-layer-stage1-sortie.md`.

## Acceptance boundary — what fixtures structurally cannot reach

`StubDecider` produces a canned structural reply from plain code; no fixture in this branch, and
no amount of adding more, exercises whether a real model's output is sane, whether the wire format
survives contact with actual model text, or whether the crew loop *feels* right with a real voice
answering. Two specific gaps a fixture pass cannot catch, named because this workstream's own
history has a worked example (the F10 vocabulary's `Scan`-drove-the-9K113-sight defect and the
raw-task-id-spoken-aloud defect, both invisible to fixtures and only findable by a human hearing
the cockpit): whether "stand by" lands at a moment that actually feels right mid-utterance, and
whether hearing Petrovich answer *at all*, after silence, changes how the exchange reads — neither
is a thing code can assert on.
