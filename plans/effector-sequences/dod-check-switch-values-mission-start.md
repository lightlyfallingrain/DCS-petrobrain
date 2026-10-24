# DoD check — switch-reference Values column + mission-start/mission-start-in-air triggers

Scope: the batch on `feature/switch-reference-values`, tip `59aebd7e52f6817e1766eb688ed5d3847c5e0a46`
(branched from `feature/effector-sequences` at `27c19054`). **This verdict is scoped to that exact
sha.** `git rev-parse HEAD` matched it exactly on checkout (detached) before any check ran; the
tree was clean at that point.

Covers: the switch-reference Values column (generator value ranges, two Windows reruns, the
regenerated reference), the generated `triggers.md`, and the `mission-start`/
`mission-start-in-air` triggers with their stale-data fallback. Does **not** cover Stage 3's
re-flight card's live acceptance (not yet flown) or Stage 4 (not built) — both still belong to the
wider BL-B90 milestone, not this batch.

## Code Quality

- [x] **body-layer** (only subproject this batch touches besides a research doc): `ruff format
  --check src tests tools` — 183 files already formatted. `ruff check src tests tools` — all
  checks passed. `cd body-layer && .venv/bin/mypy src` — success, 74 source files. `.venv/bin/mypy
  tools` — success, 10 source files. `pytest -q` — **2605 passed, 4 xfailed**, matching every
  review pass's reported count exactly. (No `.venv` in this worktree; used the main checkout's
  `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/` tools with cwd in this worktree's
  `body-layer/`, per the dispatching task's instruction.)
- [x] Staleness tests specifically: `test_render_switch_reference.py`,
  `test_render_switch_reference_values.py`, `test_render_triggers.py`,
  `test_tuning_defaults_toml.py` — 16/16 passed. Confirms the committed `switch-reference.md`,
  `triggers.md`, and `defaults.toml` all match their generators' current input, not just that the
  generators themselves are correct.
- [x] **aircraft-layer**: confirmed only `aircraft-layer/research/
  2026-10-23-mi24p-clickable-value-ranges.md` changed (`git diff --name-only 27c19054 59aebd7e --
  aircraft-layer`) — a research note, no code. No aircraft-layer checks needed.
- [x] No unhandled errors/panics in data paths — covered by the security deep analysis's focus on
  the `ast`-whitelist arithmetic evaluator (no `eval`/`exec`, both `SyntaxError`/`ZeroDivisionError`
  caught) and by Performance's read of the mission-start poll block (no new I/O, no new allocation
  on the steady-state path).
- [x] No debug output or TODOs introduced by this batch — not flagged by either review pass or by
  my own read of the diff.

## Scope & Correctness

- [x] Implementation matches `plans/effector-sequences/plan.md` (R7's value-ranges extension was
  user-requested mid-stream and folded into the plan's revision table; R14's mission-start
  triggers are the plan's own row, built exactly as specified: `takeoff` no longer fires on an air
  start, the two new triggers are `cardinality="once"`, no sequence file ships for either this
  cut).
- [x] No unplanned scope added silently — both review passes and the security pass independently
  confirm scope (`review-mission-start.md`'s "Scope" checklist item; `security-values-triggers.md`
  Focus 2: new triggers reach the same `fire_trigger`/`advance()` path, no new write capability).
- [x] No CLAUDE.md invariants violated — checked against "DCS authoritative," "no omniscience,"
  module independence (aircraft-layer↔body-layer stays HTTP, no new cross-subproject import),
  single-player-only. Confirmed by the security pass's own invariant read and my own grep of the
  diff for new imports (`ast` only, stdlib).
- [x] All new/modified files staged — `git status --porcelain` is accounted for below (my own
  edits plus the batch's own commits, all tracked).

## Testing

- [x] Core logic covered: the generator's 22 helper signatures each get a dedicated minimal-call
  assertion (`test_value_range_for_every_helper_signature_minimal_call`, closing the exact
  mutation-coverage gap the first review pass found); the mission-start mechanism has 6+2 new
  poll-loop integration tests covering cold/warm/second-restart/no-fresh-sample-fallback paths, 2
  of them independently mutation-verified by Reviewer against the pre-fix code.
- [x] Tests are meaningful, not decorative — both review passes ran the implementer's reported
  mutations themselves rather than trusting the report (`default_blue_cover` removed/restored,
  `mission_start_resolving = False` reverted/restored, `MISSION_START_RESOLVE_FALLBACK_S` import
  removed), each producing the predicted red/green.
- [x] No existing tests broken — pass counts climbed from 2584 (first review) through 2605 (final,
  this pass) monotonically across the batch's fix commits; no regression anywhere in that history.

## Documentation

- [x] Reviewer required fixes addressed: `review-switch-values.md`'s two required fixes
  (`default_1_position_tumb`'s fallback grouping bug, the mutation-coverage gap) both closed and
  independently mutation-verified in the fix re-review. `review-mission-start.md`'s required fix
  (stale "warm air start re-fires takeoff" documentation in three places) and its first-pass
  optional refinement (baseline-collision stall) both addressed; the second fix re-review's own
  required fix (the fallback's comments claiming a narrower trigger condition than the code has)
  closed in fix re-review 2, final verdict APPROVED with no required fixes outstanding.
- [x] Reviewer's two *optional* refinements from fix re-review 2 — both explicitly asked for by
  this DoD pass's dispatch — applied in this pass:
  - `pending_mission_start_in_air_check`'s field docstring (`src/logger.py`) now states both
    clearing paths (fresh sample vs. fallback-without-a-fresh-sample).
  - `_check_for_new_mission`'s docstring now states the same two-cause clearing path.
  - `body-layer/CLAUDE.md`'s BL-B90 entry now mentions the fallback-drop case, `triggers.md`'s and
    `switch-reference.md`'s Values column, and the per-aircraft raw-dump path (the last was
    already present; added the fallback-drop sentence and the Values-column sentence).
- [x] Non-obvious behaviour explained: the `AC-TEMP-KNOB-PTR` count/delta mismatch (top position
  `1.111111`, not `1.0` — ED's own `delta_ = 1/9` over 11 steps, faithful rendering, not a
  generator bug) is now a one-line note in `aircraft-layer/research/
  2026-10-23-mi24p-clickable-value-ranges.md`'s "Real calls" section, next to the other
  `multiposition_switch` examples, where a future sequence author reading that note (or the
  generated `switch-reference.md` row it explains) will see it.
- [x] Re-flight card checked against the built code: `docs/acceptance/
  2026-10-23-bl-b90-sequences-reflight.md` block 4 (air start) already matched the shipped
  mission-start mechanism before this pass (it was updated when the mission-start trigger commit
  landed). Added a short "Where things live" section pointing at `triggers.md` and the Values
  column, since block 4 invites the user to write their own `mission-start-in-air` sequence file
  and needs to say where the trigger vocabulary and legal values are documented.

## Security

- [x] `plans/effector-sequences/security-values-triggers.md` — **APPROVED**, no findings. Threat
  model: single-user, LAN-only. The one new import (`ast`) is stdlib, used only by a strict
  node-whitelist constant-arithmetic evaluator with no `eval`/`exec`/`Pow`/`Call`/`Name`; two
  theoretical-only edges (unbounded recursion on a pathological literal, `inf` from `1e400`-shaped
  input) are DoS/correctness-only on an offline, non-network, developer-invoked tool. The two new
  triggers only ever reach the same registry-constrained write path the original five already use
  — no new attacker-reachable surface.
- [x] No prior plan-level security review gap — this batch's plan content was already covered by
  the Stage 1-2 security pass (`security-stage1-2.md`, referenced throughout) for the underlying
  effector write path; this deep analysis is the batch-specific follow-up for the new generator
  code and the two new triggers, consistent with root CLAUDE.md's "once per batch actually
  executed together" cadence.

## Verdict: PASS

All mechanical checks pass at the stated tip. Both Reviewer passes (switch-values, mission-start)
reached APPROVED, with every required fix closed and independently mutation-verified rather than
taken on the implementer's report. Performance and Security both APPROVED with no findings. The
two outstanding optional-refinement doc gaps named in the final review pass, plus the
`AC-TEMP-KNOB-PTR` oddity, the roadmap update, and the acceptance-card cross-check, are all closed
in this DoD pass.

## Acceptance boundary — what this batch's fixtures structurally cannot reach

**Everything in "Code Quality"/"Testing" above is proven against synthetic fixtures and
poll-loop-thread integration tests with a fake aircraft-layer client. None of it has run against
the real DCS install or a live mission except the one-shot Windows generator run that produced
`697f5bef` — a static snapshot of the Lua source, not a running sortie.** Specifically out of
reach of this pass:

- **Whether the Values column's ranges are actually settable the way the generator says.** The
  generator reads ED's own Lua *parameter* text (`count_`/`delta_`/`arg_lim_`/etc.) and computes a
  range from it — it has never driven the real DCS `performClickableAction` call across that
  range and observed what DCS actually does at the extremes (clamping, wrap, a different
  effective range than the declared one). A sequence author trusting an "unknown"-free Values
  column is trusting the generator's reading of ED's source text, not a live-verified contract.
- **Whether the `mission-start-in-air` fallback's 30 s window is well-calibrated for a real DCS
  mission-load screen.** No fixture or test exercises an actual DCS mission start — the poll-loop
  tests simulate "no fresh sample arrives" by withholding a fake telemetry update, not by timing a
  real DCS load. If real mission loads commonly take longer than 30 s, the fallback would fire
  (correctly, per its own design) more often than the plan anticipated — that frequency is
  unmeasured.
- **The `761` (`CPLR DISTR`) arg remains UNVERIFIED** — the dump confirms it as ED's
  `WEAP-DISTR-POWER-OP-PTR` by name, but no fixture or test can confirm that's the physically
  correct switch without a pilot watching the cockpit on a real takeoff. This is explicitly called
  out on the re-flight card's block 1.
- **No sequence file ships for either new trigger this cut**, so nothing in this batch's tests
  exercises `mission-start`/`mission-start-in-air` actually writing a switch — only that the
  trigger *fires* (or correctly declines to classify) at the right moment. The write path itself
  is exercised only by the pre-existing five triggers' tests.

None of this is a gap in the testing that was done — it is the gap between "this code does what
its own tests say" and "this code does the right thing in the cockpit," which only a flight closes.

## Live acceptance — deferred, not waived

This batch's live acceptance rides the same `#needs-flight` re-flight card BL-B90's roadmap entry
already carries (`docs/acceptance/2026-10-23-bl-b90-sequences-reflight.md`, branch
`feature/effector-sequences`) — block 4 already covers the mission-start mechanism this batch
adds. **Not re-tagged separately**: this is the "batch what a single flight can clear" case
exactly — one sortie on `feature/effector-sequences` (once this batch is fast-forwarded into it)
clears both the Stage 1-2 items and this batch's mission-start/Values-column items together.

Per this role's "execute the unblock condition of accepted debt" rule: the re-flight card's own
clearing condition is "fly the card" — there is no command to run in its place, so there is
nothing further to execute here beyond confirming the card itself is current (done above, "Where
things live" section added) and that it was not silently promised as already flown (it has not
been — the roadmap entry says so explicitly, and this pass changes nothing about that).

## Not merging to main

Per the dispatch: the main loop fast-forwards `feature/effector-sequences` to this tip after this
report. This DoD pass does not merge to `main` and did not attempt to.
