# Definition of Done — BL-15 Stage 1 (mission start: clean slate + theatre)

Run on `feature/bl15-mission-start`, verified at tip `259e84e8bd7ed5efd054a2a8c26fca0c31f162bb`
(fast-forwarded from this worktree's stale base `89ca6c2a`, clean tree, confirmed before any
other work). **This verdict is scoped to that sha plus the documentation commit this DoD pass
itself adds on top of it** (the `aircraft-layer/WORKFLOW.md` deploy step, a one-line
`aircraft-layer/CLAUDE.md` cross-reference, and the two roadmap entry updates below) — if the
branch moves again before merge, re-run.

## Scope

Plan stages 1–3 (`plans/bl15-mission-start/plan.md`): the mission-start signal (Hook
`onSimulationStart` → loopback UDP 7799 → collector → `GET /mission_start/latest`), belief/
mission-memory/perception-source reset on a detected restart, and runtime theatre switching with a
loud-refusal degrade mode on failure (plus per-mission log re-roll, decision 5). Stage 2 (Mission
Interpreter briefing) is explicitly deferred — see Acceptance Boundary below. Stage 4 (live
acceptance + the `WORKFLOW.md` deploy step) is split: the deploy-step documentation was missing
from the implemented diff and is added by this DoD pass; the live sortie itself is the user's and
does not block merge (tagged `#needs-flight` on `BL-15`).

Touched subprojects: aircraft-layer, body-layer.

## Code Quality

| Check | aircraft-layer | body-layer |
|---|---|---|
| `ruff format --check src tests` | PASS (67 files) | PASS (155 files) |
| `ruff check src tests` | PASS | PASS |
| `mypy --strict src` (run `cd <subproject> && .venv/bin/mypy src`) | PASS (25 source files) | PASS (68 source files) |
| `pytest tests -q` | PASS (374 passed) | PASS (2216 passed, 4 xfailed — pre-existing, unrelated, same count Reviewer reported) |
| `luac5.1 -p` on new Hook script | PASS | n/a |

All four run fresh by me, from inside each subproject's own venv (`/Users/sg/Code/DCS-petrobrain/<subproject>/.venv/bin/<tool>`, since this worktree carries no `.venv` of its own — git worktrees don't carry gitignored directories), not taken on the Reviewer's or Implementer's report. Counts matched Reviewer's own figures exactly.

- No unhandled errors/panics in data paths: confirmed by Reviewer's three batch passes (mutation-tested, not just read) and Security's deep analysis — malformed/forged datagrams are rejected or degrade loudly, never crash a poll loop.
- No debug output left in committed code: grepped for stray `print(`/TODO/FIXME/XXX across the new files; every `print(` hit in `logger.py` is pre-existing, deliberate stdout/stderr output (startup banners, `--print-tuning`, help text, reroll notices), not a debug leftover.
- No TODO/FIXME comments introduced by this feature: none found.
- All new files staged: confirmed — `git status --porcelain` on this worktree showed a clean tree after the fast-forward merge; everything from the three implementation batches was already committed.

## Scope & Correctness

- Implementation matches `plans/bl15-mission-start/plan.md`: Reviewer's three batches independently traced every piece of plan-stated behavior (reset completeness against `BL-B68`'s table, shared-object ordering, the `init=False` trap, first-poll no-op, schema rejection, refusal-mode dispatch, theatre-switch guard ordering, stale-closure fixes, log re-roll, `fired_on_tracker`) against the implemented code, not the implementer's account of it.
- No unplanned scope added silently: Reviewer explicitly confirmed Decisions 1/5 (loud refusal, per-mission logs) were correctly deferred then correctly delivered in the batch that was supposed to carry them; no scope drift flagged in any of the three review passes.
- No CLAUDE.md invariants violated: the no-omniscience boundary (`Percept`), the `THEATRE_PROJECTIONS` membership-before-path-build guard (the exact vulnerability class from `multi-theatre-afghanistan`, re-verified independently by both Reviewer and Security), and the module-independence/HTTP-boundary rules are all unaffected by this diff — confirmed by Security's deep analysis and my own read of the dependency diff stat (no `pyproject.toml` touched in either subproject).
- All new/modified files staged: yes, confirmed via `git status --porcelain` before and after this DoD pass's own documentation additions.

## Testing

- Core logic covered by tests: the reset-completeness pattern (`reset_for_new_mission()` reinvoking `__init__`) has a dedicated completeness test per class using `dataclasses.fields()` enumeration — mutation-tested by Reviewer (removing the reset line reproduces the exact stale-state defect each test guards against). Refusal-mode dispatch, theatre switching, log re-roll, and `fired_on_tracker` reset each have targeted tests, independently mutation-verified by Reviewer in all three batches (not merely read).
- Tests are meaningful, not decorative: confirmed by Reviewer's own mutation testing (e.g. `test_refused_drain_brain_speaks_nothing_against_a_pending_escalation` also asserts side effects, not just the return value — would catch a reversion to "call the method and discard its result" that a return-value-only test would miss).
- No existing tests broken: body-layer's 4 pre-existing xfails are unrelated (confirmed by name, matches Reviewer's count across all three batches); aircraft-layer's 374 tests all pass.
- One acknowledged, accepted test-coverage gap (not blocking): `NakedEyePerceptionSource`/`HybridPerceptionSource`'s `reset_for_new_mission` tests assert a fixed, hand-written attribute list rather than enumerating `dataclasses.fields()` — a newly added dedup/counter field on either class would not be caught automatically. Flagged by Reviewer as an Optional Refinement, not required; the plan itself names this tradeoff (no cheap "fresh instance" to diff against for a class requiring live collaborators).

## Documentation

- Reviewer findings addressed: all required fixes across the three batches resolved — Batch 1 APPROVED (none), Batch 2 APPROVED WITH MINOR FIXES (one required fix: `drain_events`/`drain_brain` `self.refused` guard), Batch 3 APPROVED (confirms that fix is structural and mutation-verified, plus the `fired_on_tracker` optional refinement promoted to done).
- Non-obvious behavior explained: `body-layer/CLAUDE.md` documents the mission-start channel, theatre switching, the loud-refusal degrade mode, and per-mission log re-roll in its own "What this is" narrative section; `aircraft-layer/CLAUDE.md` documents the new channel in its channel inventory.
- **Gap found and closed by this DoD pass**: the plan's own Implementation Plan step 4 ("Wire the F10/overlay/crew-text acceptance path and update `WORKFLOW.md`") named a `WORKFLOW.md` deploy section for the new Hook script, but it was absent from the implemented diff (verified: `grep -n "mission-start\|mission_start" aircraft-layer/WORKFLOW.md` returned nothing before this pass). Added — mirroring the existing F10-commands Hook deploy section exactly (same structure: copy step, `autoexec.cfg` note reusing the F10 Hook's existing opt-in since both use the same `net.dostring_in` bridge at the same callback, port 7799 confirmed from `mission_start_receiver.py`'s own `DEFAULT_PORT`, a no-DCS-required manual UDP-send check). Also added a one-line cross-reference to it in `aircraft-layer/CLAUDE.md`'s `WORKFLOW.md`-contents bullet, matching the existing convention for the overlay/F10 sections. This is documentation only — no design decision, no code change, mirrors an established pattern exactly — so I wrote it directly rather than looping back through Implementer/Reviewer for a one-section mirror.

## Security

- `plans/bl15-mission-start/security-plan-review.md`: **APPROVED**. One genuinely new risk (forged local loopback datagram → belief wipe) surfaced via the Risk Communication format and explicitly accepted by the user 2026-10-19 (`stage1-decisions.md`: *"Accept the risk, it's not like there's anything else sending DCS or Petrobrain signals on my computer."*). The `theatre`-string-into-path/SQLite-URI risk reuses the already-fixed `THEATRE_PROJECTIONS` mitigation from `multi-theatre-afghanistan`, carried into Mode 2 for verification.
- `plans/bl15-mission-start/security-deep-analysis.md`: **APPROVED**. Both Mode-1 carry-forwards independently re-verified by reading the implemented code (membership-check ordering, schema rejection). All additional checks named in the dispatching brief clean (loopback bind, hardcoded `dostring_in` expression, log-path provenance, new CLI flag). One scope note: Stage 3 widens the accepted risk's blast radius (a forged datagram can now also trigger refusal mode, not just wipe belief) — same trust boundary, not re-raised as a new finding.

## Performance

`plans/bl15-mission-start/performance-review.md`: **APPROVED — MONITOR**. No hot-path allocation, full-dataset iteration, or poor batching found. One new per-poll cost (an 8th synchronous `GET` at 1 Hz, ~14% increase on an already-established pattern) and two pre-existing `AircraftLayerClient`/poll-loop properties (no connection pooling; a slow collector can stall a full poll cycle) are noted as MONITOR — inherited, not introduced or worsened by this batch. No required fixes.

## Overall Verdict: PASS

No blocking gaps. The one gap found (missing `WORKFLOW.md` deploy step) was documentation-only and closed directly in this pass.

## Acceptance Boundary

**What this feature's fixtures structurally cannot reach**, stated before any live testing: the completeness/mutation-tested unit tests prove that *given* a `MissionStartEvent` with a given sequence/theatre, the reset, theatre-switch, and refusal mechanisms behave correctly. No fixture can prove (a) that `onSimulationStart` actually fires, exactly once, on a genuine single-player "restart mission" action in this DCS build — the investigator's own research note (`aircraft-layer/research/2026-10-19-theatre-detection-at-mission-start.md`) states this is unverified without the box; (b) that it does *not* also fire on pause/resume, which is the mid-flight-false-positive risk the plan names as residual; or (c) that `env.mission.theatre` actually resolves over the live `net.dostring_in` bridge at that exact callback in this DCS version. These three are exactly what the acceptance card below asks the user to check, and are the reason this milestone stays `#needs-flight` rather than fully closed at DoD.

## Acceptance Testing Plan

Published as an artifact card (in-cockpit-readable, checkboxes persist): https://claude.ai/artifact/UJsBH2VU64VPLp2vo42TXd — source of truth at `docs/acceptance/2026-10-19-bl15-mission-start-card.md`. Covers: Hook deploy, starting body-layer with `--world-model-dir` (the one new, load-bearing flag this card depends on — independently re-verified by me against a real throwaway Syria store, see that file), same-theatre restart reset, cross-theatre refusal, recovery, and an optional theatre-detection probe. Every command in the card is either run by me with its real output pasted, or explicitly asked of the user as something only their DCS box can answer.

Asking the user: does the feature pass acceptance testing? (yes / no + details)
