# Definition of Done: BL-B118 (operator altimeter QNH sync at mission start)

**Scope: `feature/bl16-qnh-mission-start`, tip `b83707fd1a296d0caa1d5866c9cbbd69c1946a4d`.** This
verdict is scoped to that exact commit. The DoD worktree was fast-forwarded onto it
(`git merge --ff-only b83707fd...`) after confirming HEAD (`a7bea50d`) was a strict ancestor with a
clean tree — the working tree checked below is byte-identical to that commit's content, not a
reconstruction. If the branch moves again before merge, this verdict is stale.

## Code Quality

| Check | body-layer | aircraft-layer |
|---|---|---|
| `ruff format --check` | pass — 206 files already formatted | pass — 80 files already formatted |
| `ruff check` | pass — all checks passed | pass — all checks passed |
| `mypy src` (run from inside the subproject) | pass — no issues, 84 source files | pass — no issues, 27 source files |
| `luac5.1 -p` on `petrobrain-mission-start-hook.lua` | n/a | pass |
| **Full suite incl. `slow` (`.claude/scripts/fast-tests.sh --full <subproject>`, foreground, xdist)** | **pass — 3308 passed, 4 xfailed, 154.28s** | **pass — 801 passed, 9.35s** |

Both run at tip `b83707fd` (tested-tree sha above) — the merge can skip its own full run if its
tree matches this sha. The 4 xfails are pre-existing and unrelated (confirmed by Reviewer's own
re-review pass).

No bare `except:`/`except Exception:` found in the feature's own new/changed lines
(`altimeter_qnh_sync.py`, the `body.py`/`crew_console.py`/`mission_start.py` diff) — the six
occurrences a whole-file grep finds in `body.py`/`crew_console.py` are pre-existing, outside this
diff (confirmed: zero `except Exception` lines appear in `git log -p` over this feature's own
commit range for either file). No debug `print()`/`pdb`/`breakpoint()` in new code — `crew_console.py`'s
matches are all `self._print(...)`, the module's own established output path, not debug code. No
`TODO`/`FIXME`/`HACK`/`XXX` introduced. `altimeter_qnh_sync.py` is 314 lines, `mission_start.py` is
129 — both well under the 400-line split threshold.

**Live wire check, executed, not just unit-tested**: started `aircraft-layer`'s real collector
process on this Mac (`PYTHONPATH=src .venv/bin/python -m collector --api-port 17791`), sent a UDP
datagram to its loopback mission-start receiver with the new fields
(`{"sequence": 1, "theatre": "Syria", "qnh": 762.5, "atmosphere_type": 0}`), and polled
`GET /mission_start/latest`:

```
sent {'sequence': 1, 'theatre': 'Syria', 'qnh': 762.5, 'atmosphere_type': 0}
{"sequence": 1, "qnh": 762.5, "atmosphere_type": 0, "theatre": "Syria", "received_wall_clock_s": 1794858419.501187}
```

Confirms the collector → `GET /mission_start/latest` hop actually carries `qnh`/`atmosphere_type`
end to end, on real code, not just the schema's own round-trip test. This is the one hop reachable
without Windows/DCS; `net.dostring_in` reading the real `env.mission.weather.qnh` inside DCS itself
is not (see Acceptance below).

**Tunables registered, confirmed live**: `cd body-layer && PYTHONPATH=src:../world-model/src
.venv/bin/python -m body --print-tuning | grep -i altimeter` returns all eight constants from the
plan's table at their stated defaults/status (`ALTIMETER_QNH_TOLERANCE_MMHG: 0.3 (agreed-guess)`,
`ALTIMETER_QNH_CALIBRATION_STEP: 0.05 (uncalibrated)`, `ALTIMETER_QNH_MAX_STEP: 0.3 (uncalibrated)`,
`ALTIMETER_QNH_SETTLE_S: 0.3 (uncalibrated)`, `ALTIMETER_QNH_MAX_ITERATIONS: 20 (agreed-guess)`,
`ALTIMETER_QNH_MAX_DURATION_S: 15.0 (agreed-guess)`, `ALTIMETER_QNH_NO_RESPONSE_EPSILON: 0.002
(uncalibrated)`, `ALTIMETER_QNH_NO_RESPONSE_STRIKES: 2 (agreed-guess)`).

## Scope & Correctness

Implementation matches `plans/bl16-qnh-mission-start/plan.md`'s four stages: Stage 1 (wire field),
Stage 2 (the closed loop), Stage 3 (wiring into `body.py`/`CrewConsole`) are built; Stage 4 (the
live card) is explicitly out of scope for code and is this report's Acceptance section below.
Reviewer's full read (`review.md`) confirms the same, including both plan-aligner CONCERNS
(QFE-vs-QNH, dynamic-weather home) resolved in the plan's own "Decisions Requiring User Input"/
"Risks & Unknowns" sections before code was written. No unplanned scope found — `implementation.md`'s
two opportunistic docstring fixes (`aircraft_client.py`, `mission_start_receiver.py` wire-shape
examples) are corrections to text the Stage 1 change itself broke, not new scope.

**No CLAUDE.md invariants violated.** Checked against `body-layer/CLAUDE.md`'s "Invariants" list:
no-omniscience is not engaged (this mechanism never touches `Percept`/belief state — it is a pure
aircraft-effector closed loop); mechanism and calibration are separate commits (Stage 1/2/3, no
retuning of an existing constant bundled with a behaviour change); the tuning mechanism is used
correctly (8 new `tuning.real`/`tuning.whole` constants, `#:` comments, `config/defaults.toml`
regenerated and its staleness test passing). `aircraft-layer`'s `cockpit_switch`/`read_args`
channels are reused exactly as documented, not reinvented — the plan names and rejects the
effector-sequences engine as the wrong tool, per root `CLAUDE.md`'s "name what you depart from."

**All new files staged.** Working tree is the fast-forwarded commit itself (`git status --porcelain`
empty) — nothing to stage; every file in the plan's "Affected Modules" list is present in the
diff and committed.

## Testing

Core logic (`advance_altimeter_qnh_sync`) is covered by 13 tests in
`test_altimeter_qnh_sync.py`: every terminal phase (`succeeded`, `failed_no_response`,
`failed_timeout` via both the iteration bound and the wall-clock bound), an inverted-gain-sign
convergence, a noisy single non-response that must not trip the strike counter, transient
read/write failures (skip-and-retry), the settle gate, both terminal phases' inertness, and the
Reviewer-required clamp fix (`test_calibration_step_is_clamped_to_max_step_even_when_configured_larger`).
Tests are meaningful, not decorative: both the implementer and the Reviewer independently
mutation-tested the two safety-critical guards (settle gate, terminal-state inertness) by breaking
each and confirming the matching test goes red for the stated reason, then restoring the file and
verifying its checksum — Reviewer's own re-review did this a second time, independently, for the
clamp fix specifically, reverting it and confirming `test_calibration_step_is_clamped...` fails
with `assert False` on the override pair, not merely passing to begin with.

No existing tests broken — `test_mission_start_schema.py`/`test_mission_start_api.py` were updated
(not broken) where the new fields changed an exact-equality assertion; `test_mission_start_reset.py`/
`test_crew_console.py` got matching new tests for the two adoption sites and the failed-line
drain, mirroring the existing theatre-adoption/`drain_config_error` test shapes.

## Documentation

**Reviewer findings addressed.** The one Required Fix (the `else` branch's unclamped write) is
verified fixed and independently reproduced by Reviewer's re-review (`review.md` lines 131-203,
verdict APPROVED). Both Optional Refinements were handled appropriately: the stale roadmap closing
line was fixed (optional, done); the defensive ternary clarity suggestion was explicitly skipped
per its own "optional" framing.

**Accepted-items ledger.** `.claude/scripts/accepted-items-ledger.sh plans/bl16-qnh-mission-start`
reports "decisions U1 U2 not yet answered (no `**Answered` line) -- nothing accepted to check."
This is the mechanical floor, not the real answer — read by hand, same as Reviewer did:

- **U1 (silent on success or speak?)** — taken as recommended (silent). **Built**:
  `advance_altimeter_qnh_sync`'s `succeeded` branch has no `_print`/speech call; confirmed by
  reading the code and by `test_crew_console.py`'s drain tests, which only ever speak on a
  `failed_*` phase.
- **U2 (one sortie or two for the card?)** — taken as recommended (two: ground start and air
  start). **Deferred to Stage 4**, this report's own Acceptance Testing Plan below defines exactly
  those two sorties, matching the pilot's own "both ground start and air start" requirement.
- **QNH vs QFE** (not a numbered `U<n>`, but a real "Decisions Requiring User Input" item) — the
  pilot was shown the QFE evidence found after the fact (recon note section E) and confirmed QNH
  stands (*"Skip the probe, just build setting QNH."*). **Built as QNH.** Carried forward
  explicitly as the first alternative to try if the first live flight shows a wild target
  persisting.
- **Dynamic-weather risk** (also not numbered) — handling decided (main loop, 2026-11-16): the hook
  now also reads `atmosphere_type` and logs it beside the resolved target; no special-casing. **Built**
  (confirmed live above: the wire round-trip carries `atmosphere_type` end to end). Home for a
  real dynamic-weather defect, if one is observed: a new body-layer backlog item linked from
  `[[BL-B118]]`, per the plan's own words.

No other `U<n>` ids exist in the plan (`grep -n '\*\*U[0-9]' plan.md` returns only U1/U2).

**Non-obvious behaviour explained.** `body-layer/CLAUDE.md` carries a full paragraph on the
mechanism (why it is deliberately not an effector-sequence trigger, why it shares
`_maybe_switch_theatre`'s adoption sites rather than `EffectorTrigger.MISSION_START`). The module
itself documents the secant-method rationale, the "unable" lines' wording convention, and the
cross-key relationship between `ALTIMETER_QNH_CALIBRATION_STEP`/`ALTIMETER_QNH_MAX_STEP` the
Required Fix closed.

## Security

`plans/bl16-qnh-mission-start/security.md` exists, verdict **APPROVED**, zero required fixes. One
low-probability × low-impact finding (the NaN/Infinity clamp holding only by `min`/`max` argument
order, not a designed `math.isfinite` guard) is filed as `[[BL-B120]]`
(`body-layer/ROADMAP/BL-B120.md`), correctly minted after a collision check — the DoD brief notes
it was first minted as `BL-B119` and renumbered because `BL-B119` is already taken on another
branch; `.claude/scripts/mint-id.sh --list` confirms `BL-B120` is the current highest body-layer
backlog id, no collision. Both `BL-B118`/`BL-B120` are correctly registered in
`body-layer/ROADMAP/body-layer-backlog.md`'s index (not just their own entry files).

## Performance

`plans/bl16-qnh-mission-start/perf.md` exists, verdict **APPROVED — MONITOR**. The one real,
named risk (a ~0.25 s typical / ~2.0 s pathological stretch of the shared poll thread's period,
recurring for up to ~15-20 s after any mission (re)start including an already-engaged air start)
is bounded on every axis (one read + at most one write per poll, iteration- and wall-clock-capped,
zero cost once terminal) and is architecturally cheaper than the already-accepted `effector_engine`
one-shot-read pattern it mirrors. No action required before merge.

## Recurring-fix pattern (process signal, not a blocker)

Reviewer's one Required Fix here (`ALTIMETER_QNH_MAX_STEP` not actually bounding the calibration-step
branch) is the **third** occurrence in two months of the same underlying shape: a tunable's
docstring claims a cross-branch or cross-key bound that per-key `lo`/`hi` validation cannot see,
invisible because every test runs at defaults, caught only by Reviewer reading every branch by
hand. The first two (`X-T26`'s `belief/decay.py` assert, and its recurrence on
`9k113-narrow-search`/`BL-B85`) were *existing* tunables gaining a coupling; this one is two *new*
constants in the same commit with the ordering stated only in prose. Recorded in
`notes/planning-and-process-lessons.md` and `.claude/agent-memory/dod/
project_recurring_tunable_bound_enforced_in_one_branch_only.md`. **Recommendation for the user**:
three instances is enough to consider moving this check earlier — requiring a plan or
implementation that states a cross-branch/cross-key tunable ordering in prose to also wire the
enforcing mechanism (a `tuning._check_*_coupling` or an inline clamp) at Architect/Implementer
time, rather than relying on Reviewer to find it by hand each time. Not acted on here; flagging
for the user's own prioritisation.

## Acceptance boundary — what this DoD cannot verify

This DoD pass is entirely fixture/unit-level plus one live-on-Mac wire check (the UDP→HTTP hop
above). It **cannot** verify, and does not claim to have verified:

- That `env.mission.weather.qnh` actually resolves to a sensible value inside a real DCS process —
  the Hook script's `net.dostring_in("scripting", ...)` call needs a live DCS session; nothing on
  this Mac can execute it.
- That `performClickableAction(42, 3001, v)` actually moves the operator altimeter's pressure
  window at all, from either seat — the research note's own "unverified, the one real risk"
  (whether device 42 honours the write from the pilot seat) is exactly what no fixture or unit test
  can answer, by the plan's own design. The closed loop's fixture tests prove the *algorithm*
  converges against a scripted fake device; they say nothing about the *real* device's gain,
  linearity, or whether it responds at all from a given seat.
- That the secant method's step-size/settle-time tunables (all eight marked `uncalibrated`/
  `agreed-guess` in the plan's own table) are actually well-chosen against the real knob's response
  curve — only a live flight can show whether convergence is fast, slow, or oscillates toward
  `failed_timeout`.
- That "Request Aircraft Control" no longer produces the wild barometric target the takeover-fix
  probes measured (+742 m, +737 m) — this is BL-16's own open question this feature exists to
  answer, and it is answerable only by flying both features together.

This is the acceptance boundary a fixture pass structurally cannot close — not a gap in this DoD
pass, but the reason Stage 4 is a live card, not more unit tests.
