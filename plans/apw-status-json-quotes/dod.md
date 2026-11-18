# Definition of Done: fix/apw-status-json-quotes

**Verdict: PASSED**

**Scoped to tip `d574c47420671409fd2b84de3d1f18c717e0403c`** (base `main` `797f53db`). `git
rev-parse HEAD` matched the expected sha exactly; `main` is a strict ancestor of `HEAD`; working
tree clean before any DoD work began. If this branch moves past this sha before merge, this
verdict no longer applies to the new tip.

Commits under review: `c7f2524e` (fix), `bdb6db20` (Reviewer APPROVED), `d574c474` (Security
APPROVED). Diff vs `main`: aircraft-layer only (+ two agent-memory files, plans/ reports, the
AC-B15 roadmap entry).

## Acceptance boundary — what this fixture pass structurally cannot reach

The regression test extracts the real Lua function and round-trips it through a fake `client:send`
+ `json.loads`, which proves the *line produced* is now valid JSON. It cannot prove:
- that the collector's downstream cache/belief code, once it starts actually receiving these
  lines for the first time in practice (this parsing path was effectively dead code before the
  fix, per `debug.md`), behaves correctly on live DCS-shaped data rather than just well-formed
  JSON — e.g. a seat change tracked continuously instead of frozen;
- anything about the two other flight cards (P2 voice goals, BL-17 flight-commands) that may have
  been reading this same frozen line while under test on 2026-11-17.

Both require a live sortie. Named as such below, not glossed over as "tested."

## Code Quality

- **Subprojects touched** (from `git diff --name-only main...HEAD`): aircraft-layer only.
- `ruff format --check .` (aircraft-layer, via `/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv/bin/`,
  this worktree's own venv was absent): clean except `research/2026-10-06-unit-id-join-reduce.py`
  — pre-existing (`bc680887`), not touched by this branch's diff, not re-fixed here (out of this
  bug fix's scope).
- `ruff check .`: same single pre-existing finding (`EXE001`, same file), not introduced by this
  branch.
- `cd aircraft-layer && mypy src`: `Success: no issues found in 27 source files`.
- `.claude/scripts/fast-tests.sh --full aircraft-layer` (ran directly with
  `PYTHONPATH=src <venv>/pytest tests -q -n auto` after the script's own venv-resolution tripped
  on this worktree having no `.venv`): **885 passed**, full suite, parallel.
- `luac5.1 -p aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`: syntax OK.
- GETGLOBAL audit on the touched file: every name is Lua stdlib, a genuine DCS API, or a declared
  `core.lua` cross-module global (`client`, `debug_log`, `extract_json_number_field`,
  `extract_json_string_field`, `fmt_num_or_null`, `json_escape_string`, `safe_call`,
  `WHEEL_CENTER_BUTTON`, `WHEEL_MENU_BUTTON`). No new global leak.
- No debug output, no TODO/FIXME introduced by this branch's diff (checked the touched Lua + test
  file directly).
- Only aircraft-layer touched — no other subproject's checks needed.

## Scope & Correctness

- Matches `plans/apw-status-json-quotes/debug.md` exactly: one-line fix (`text_or_null` stops
  re-wrapping `json_escape_string`'s already-quoted return value), plus its test and the two
  review/security reports. No unplanned scope.
- No invariants from CLAUDE.md violated (not DCS-authority, not provenance, not multiplayer, not
  the module-independence rule — single-file aircraft-layer Lua fix).
- All files staged and committed in the branch's own history already; nothing new to add except
  this report and the acceptance card (staged below).

## Testing

- `TestPushAiPilotWheelStateJson` (4 cases) is the core-logic coverage: all-nil, one text field,
  every string field set (matching the live-flight shape), and an escape-character case. Confirmed
  to fail pre-fix with the exact described `JSONDecodeError`, pass post-fix (Reviewer's own
  mutation check, independently repeated in effect by reading the diff and the test's assertions).
  Meaningful, not decorative — it reproduces the actual flight symptom.
- No existing tests broken: full suite 885/885 passing.

## Documentation

- No `plans/apw-status-json-quotes/plan.md` exists — this is a bug fix (debug.md/review.md/
  security.md), not a planned feature, so there is no `U<n>` ledger to run:
  `.claude/scripts/accepted-items-ledger.sh plans/apw-status-json-quotes` returned nothing, as
  expected for a bug-fix folder with no plan.md.
- Reviewer's required fixes: none (APPROVED, no required fixes). Security's required fixes: none
  (APPROVED; filed `[[AC-B15]]`, not blocking, properly indexed in
  `aircraft-layer/ROADMAP/aircraft-layer-roadmap.md`).
- One item Security explicitly passed to Reviewer without a verdict (`belief/ai_pilot_wheel.py`'s
  `_parse_float` accepting `"nan"`/`"inf"`/`"infinity"`) — Reviewer's report does not mention it.
  Judged not a DoD blocker: it is a pre-existing behavior of `_parse_float`, not something this
  branch's diff touches or introduces, and Security's own framing was "belief correctness, not
  security," i.e. advisory, not a required fix either role filed as blocking. Not filed as a new
  backlog item here since no role asked for it to be — flagging it in this report instead, in case
  it recurs as a live observation (a spoken "nan" readback is not plausible from `list_indication`
  text, so this is low-probability).
- Non-obvious behavior: `AiPilotWheelCache.latest()` only ever records a successful parse and
  never clears/flags on a drop, so a malformed line reads as "nothing changed" rather than
  "nothing arrived" — explained in `debug.md`'s "What mode 2 lost" section and now also in
  `notes/lua-export-module-architecture.md` (harvested below).

## Security

`plans/apw-status-json-quotes/security.md` exists, verdict **APPROVED**. No blocking findings.
`[[AC-B15]]` filed (control-character escaping gap in `json_escape_string`, low/low, same
precedent as `BL-B91`), correctly indexed.

## Accepted-debt unblock condition

`[[AC-B15]]`'s own entry has no stated executable clearing condition (it names a *recommended
fix*, not a probe or script that already exists to confirm the gap) — nothing to run. The only
clearing condition this fix carries is the live sortie itself, which this role cannot perform;
see `#needs-flight` below.

## Acceptance Testing Plan: AI Pilot Wheel Status Line Fix

**Goal:** confirm the AI-overlay status line now stays live instead of freezing, and that a
spoken AI-overlay goal is accepted rather than refused.

**Prerequisites**
- [x] Type-checked and importable: `mypy --strict` equivalent already run above
  (`cd aircraft-layer && mypy src`) — `Success: no issues found in 27 source files`.
- [ ] AI pilot wheel engaged in flight (stick parked, AI flying).

**Test Cases**
1. `OMEN=192.168.0.85; curl http://$OMEN:7791/ai_pilot_wheel/latest`, run 2-3 times a few seconds
   apart while the overlay shows mode/course/alt/speed text — expect the text fields non-null and
   changing between polls, not frozen.
2. Speak an AI-overlay goal (e.g. "heading 090") with mode 2 active and the player in the operator
   seat — expect it acted on (readback or status-line movement toward the target), not "say
   again" or "unable".

**Edge Cases to Probe**
- A seat change mid-flight — does `apw_seat`/`parked_active` on the status line track it live, or
  still read stale (this is the exact gating condition the bug froze)?

**Pass Criteria**
Both test cases produce the expected result, and no regression is visible on the P2 voice-goals
or BL-17 flight-commands behavior that was flying under this same (frozen) line on 2026-11-17.

## Acceptance testing: PENDING (live)

Per 2026-10-26 user direction, live acceptance does not gate merge. Card published:
https://claude.ai/artifact/8i4iurqBcLZTPzd6Jp6pHV
(`docs/acceptance/2026-11-18-apw-status-json-quotes-sortie.md`,
`docs/acceptance/2026-11-18-apw-status-json-quotes-card.html`). Every command on the card was run
here first (`curl` against `OMEN:7791/ai_pilot_wheel/latest` is the exact command already proven
working in `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`'s own flight feedback — host/port
confirmed in `aircraft-layer/src/api/server.py:333` — not a guess). The voice-command check is
inherently live-only and is marked as such on the card.

`#needs-flight` recorded on `body-layer/ROADMAP/BL-16.md` (the owning entry for the AI pilot
wheel/mode 2 surface), batched with that stage's existing open P2 item rather than opened as a
second separate debt line. Named, on that entry, the two already-open 2026-11-17 cards (P2
voice-goals, BL-17 flight-commands) this fix may retroactively explain.

## Knowledge harvest

Added one bullet to `notes/lua-export-module-architecture.md`: `json_escape_string` returns a
fully quoted literal, not a bare escaped body — a caller re-wrapping it in quotes fails silently
one layer downstream (the collector drops the malformed line), not at the write site. This is the
first DoD-stage occurrence of this specific contract-misuse category
(`python3 .claude/scripts/memory-search.py json escape quote` — a debugger and a security memory
already exist for this exact bug, but none from DoD, and no second prior occurrence found), so no
recurring-pattern memory was written; one occurrence is not (yet) a pattern.

## Milestone-completion question

Does this change what comes next? No new milestone to mark — this is a bug fix on an
already-shipped, in-progress stage (BL-16 Stage P2, already flagged `#needs-flight`). It does not
invalidate any downstream assumption; if anything it *removes* a candidate explanation (a frozen
status line) for behavior observed on two still-open 2026-11-17 flight cards, which is recorded on
`BL-16.md` so the next sortie batch checks it rather than assumes those cards' own logic was wrong.
