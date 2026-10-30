# Definition of Done — `bl-b104-ground-contacts-on-ground`

DoD, 2026-10-30. Branch `feature/bl-b104-ground-contacts-on-ground`, fast-forwarded cleanly from
`54633ef8` (local `main` tip) to the dispatched tip `0b70a82ea4e53d591b6e0270b8182c4f684e2a6d`
(strict ancestor, clean tree before and after). **This verdict is scoped to that tip.**

Batch: Stages 1-5, 7, 8 of `plans/bl-b104-ground-contacts-on-ground/plan.md`. Stage 6 (live test
card) is deliberately not built in this batch — see "Acceptance boundary" below.

## Checklist

**Code Quality**
- [x] Format/lint/type/test pass per subproject, re-run fresh (not trusted from prior reports) —
  both subprojects had no `.venv` in this worktree; built both from scratch.
  - `aircraft-layer/`: `ruff format --check` (75 files), `ruff check`, `mypy src` (26 files, strict)
    all pass; `pytest -q` — **663 passed**. `luac5.1 -p` clean on both touched Lua files
    (`Export.lua`, `petrobrain-line-of-sight-hook.lua`).
  - `body-layer/`: `ruff format --check` (190 files), `ruff check`, `mypy src` (79 files, strict)
    all pass; `pytest -q` — **2858 passed, 4 xfailed** (the 4 xfailed are pre-existing, from
    `fix/flexible-sequence-tests` on `main`, unrelated to this feature — confirmed against `main`'s
    own list, not compared to zero).
  - Both counts match the Implementer's/Reviewer's own final reported numbers exactly.
- [x] No unhandled errors/panics in data paths — the one gap found (Security Finding 1,
  NaN/Infinity on `category`/`subcategory` raising uncaught at a LAN boundary) is closed,
  mutation-tested, and re-confirmed by Security's own re-check (APPROVED).
- [x] No debug output left in committed code — grepped the diff for `print(`/`TODO`/`FIXME`/
  `console.log`/`debugger` outside test files: none found.
- [x] No leftover debug/TODO comments introduced by this feature — same grep, clean.

**Scope & Correctness**
- [x] Implementation matches `plans/bl-b104-ground-contacts-on-ground/plan.md` — confirmed by
  three Reviewer rounds plus this role's own read of the plan against `implementation.md`.
- [x] No unplanned scope added silently — the one scope addition (the `Turn` leg kind, Stage 7
  amendment) was planned and reviewed, not silent; `BL-B105` (filed this pass) is a new backlog
  item, not scope creep into this branch.
- [x] No project invariants violated — no-omniscience fence holds (grep-pinned in
  `test_estimation.py`; Security's deep analysis independently confirmed no new field reaches a
  player-facing surface directly); world-model elevation grid not used on the live path (per
  Decision 0, matching the 2026-10-05 posture); module independence preserved (no new cross-
  subproject import).
- [x] All new files staged — `git status --porcelain` empty after `git add`; see file list below.

**Testing**
- [x] Core logic covered by tests — envelope/convergence tests for the fused estimator, domain
  rule table, association scenario tests (closing run + two-groups-on-one-bearing), the Stage 8
  motion-gate unit tests, and a real differential (before/after control experiment, re-run by this
  role's predecessors, not just read) for both the E5 fold fix and the fold-displacement
  integration path.
- [x] Tests are meaningful, not decorative — three Reviewer rounds specifically chased down and
  fixed two cases where a test passed without actually exercising the mechanism it claimed to
  (Findings 1/2, then 5/6), each closed with a real before/after control experiment.
- [x] No existing tests broken — full suite green in both subprojects, matching main's own
  pre-existing xfail baseline exactly.

**Documentation**
- [x] Reviewer findings addressed — `review.md`'s final verdict is **APPROVED** (three rounds: the
  main batch, the Stage 7/8 follow-up, and the security-fix re-check). All Required Fixes
  resolved and independently reconfirmed by re-running control experiments, not trusted from the
  Implementer's account.
- [x] Non-obvious behaviour explained — `plan.md`'s own worked-numbers sections (Monte Carlo
  fusion comparison, the fold-threshold arithmetic), module docstrings, and this pass's notes
  harvest (below) cover the transferable insights.

**Security**
- [N/A] `security-plan-review.md` — not produced; Security's plan-review step was dropped from the
  standard sequence project-wide on 2026-10-30 (root `CLAUDE.md`/`AGENTS.md`, "Security's plan
  review left the sequences"). Not a gap specific to this branch.
- [x] `security-review.md` exists; verdict **APPROVED** (one Required Fix, Finding 1 —
  NaN/Infinity on `category`/`subcategory` conversion at the LAN-HTTP boundary — closed and
  re-checked clean).

**Performance**
- [x] `performance-review.md` exists; verdict **PASS WITH NOTES** (nothing blocking; one MONITOR
  item — `bridge_call_ms` on the next dense-scene sortie, given the LOS Hook's new per-candidate
  `land.getHeight` call).

## Acceptance boundary — what this feature's fixtures structurally cannot reach

Every test in this batch runs against a mock aircraft-layer server, a flat synthetic world-model
plane, and deterministic sha256-hashed "noise." None of the following can be checked without a
real DCS session:

- **Whether the installed DCS version's `LoGetWorldObjects` actually reports `Type.level1`/
  `level2` the way the community-sourced wsType enumeration this plan assumes.** The whole domain
  classification (`perception/domain.py`) rests on an enumeration never read live — the plan's own
  "Risks & Unknowns" names this explicitly, and the Stage 1 WARNING log plus a one-shot `Type`
  dump are built specifically to settle it on the first live sortie, not before.
- **Whether `land.getHeight` in the LOS Hook's per-candidate loop costs what the micro-benchmark
  predicts under DCS's own real mission-scripting load**, not a Python-side estimate. The
  Performance Reviewer's MONITOR item exists for exactly this reason — `bridge_call_ms` is the
  observable that would show a regression DCS itself introduces, not body-layer.
  **Run before writing it down as acceptable**: the micro-benchmark (3.9 µs/surface-cluster) *was*
  executed against this tip's real `src/` by the Performance Reviewer — reported in
  `performance-review.md` — but the DCS-side `land.getHeight` cost itself was never measured in
  DCS, only reasoned about by comparison to an existing raycast call of a similar class. That
  specific number is unverified, not merely unquoted.
- **Whether a real sortie's actual closing speed/altitude/mask-geometry combination keeps Stage
  8's fold fix inside its margin.** The Reviewer's own final-round measurement (independently
  re-run, not taken on trust) found the mechanism demonstrated at 600 m AGL / 12 m/s with a
  comfortable margin, but a *faster, lower* run (300 m AGL / 51 m/s, within this project's own
  normal envelope) leaves only ~30 s of masked window against the ~42 s the fix needs — closer to
  the edge than the test's own geometry shows. No fixture can tell us whether a real pilot's
  attack-run shape lands on the safe or unsafe side of that margin; only a flown sortie with a
  fast, low pass can.
- **Whether the cockpit-mask behaviour change (callouts suppressed closer than ~740 m
  forward/~1.7 km abeam at 300 m AGL) reads as correct to the pilot in the cockpit**, as opposed to
  merely matching the stated mask geometry in a test. The worked example this role's own
  instructions name (F10 vocabulary passing on fixtures, then a sortie finding `Scan` driving the
  wrong subsystem) is exactly this class of gap: the mechanism can be bit-for-bit correct and still
  feel wrong to someone flying it, which no mock-flight scenario can surface.

## `#needs-flight` — what the next sortie must cover

Filed on `body-layer/ROADMAP/BL-B104.md`'s own done-entry, batched into one card
(`#needs-flight`):

1. Redeploy `Export.lua` and the LOS hook on Windows.
2. A live one-shot `Type` field dump (settles the wsType enumeration question above).
3. Cockpit-mask boundary checks at 300 m AGL: ~740 m forward, ~1.7 km abeam.
4. Ground contacts visibly placed on the ground (not at ownship altitude) across a closing/
   descending run — the sortie's own original defect.
5. Two groups on one bearing stay two contacts through a real attack-run shape — ideally
   including a fast, low pass, since that is the geometry closest to Stage 8's own margin.
6. `bridge_call_ms` watched in a dense scene (Performance Reviewer's MONITOR item).

These six are named as one sortie's worth of acceptance, per the project's "batch what a single
flight can clear" rule — nothing here needs its own separate flight.

## Pending merge-time pointer amendments (from `plan.md`'s "On merge" section)

All four done in this pass, within DoD's remit:

- **`plans/attack-run/plan.md` Decision 4 REVISED** — pointer added saying surface contacts now
  carry their own height in belief (`attack_run.remembered_target_alt_m`), and the ownship-altitude
  trap this decision describes now applies to air contacts only.
- **`plans/bounded-fold-displacement/plan.md` §6** — pointer added saying `BL-B104` Stage 8 built
  the wider motion-keyed growth-rate direction this section only probed the narrower form of.
- **`docs/acceptance/2026-10-13-position-uncertainty-direction.md`** — pointer added saying this
  direction is now built (Stage 8's `UNOBSERVED_MOTION_GROWTH_RATE_MPS`), not still open.
- **The two `last_alt_m` agent memories**
  (`.claude/agent-memory/architect/project_last_alt_m_is_the_ownship_altitude.md`,
  `.claude/agent-memory/debugger/project_contact_last_alt_m_flat_projection_trap.md`) — both
  amended to say the ownship-altitude trap now applies to air contacts only; a surface contact's
  `last_alt_m` is its own believed ground height and is safe to read directly.
- **Backlog item for `group_matches`'s two-sided widening** — minted `BL-B105`
  (`body-layer/ROADMAP/BL-B105.md`), added to `body-layer/ROADMAP/body-layer-backlog.md`'s index.
  Flagged by the Reviewer's follow-up round as still not minted after two review passes; done here.

## Notes harvest

Reviewed `implementation.md`'s Notable Discoveries, `review.md`'s Required Fixes, and `plan.md`'s
worked-numbers sections against `notes/notes-index.md`. Three additions, all non-duplicate and
non-obvious from code:

- `notes/solve-the-problem-in-its-natural-coordinate-space.md` — a second worked instance of the
  topic's own thesis: fusing two range cues in inverse distance rather than metres is never worse
  than either cue alone, while metre-domain fusion is up to 1.74× worse at some geometries (Monte
  Carlo measured, not argued).
- `notes/fixture-management-and-test-infrastructure.md` — two additions: (1) a scenario's
  masked-window-to-admission gap is structurally bounded by
  `separation - admission_range + mask_range`, so widening separation to buy time is
  self-defeating; altitude is the lever that actually works, within limits. (2) a module-level
  function imported via `from x import f` is a separate binding from the defining module's own
  attribute, and a monkeypatch revert must patch both or the revert silently does nothing — caught
  here before it reached a committed test.
- `notes/attack-run-guidance-design-bl-14.md` — another distinct-mechanism instance of the
  standing "verify the rendered `defaults.toml`, not the source comment" trap: the generator's
  first-sentence splitter has a digit-adjacency lookbehind that silently merges a comment's
  intended first sentence with the next one if it ends in a numeral.

Deliberately not added: the cross-thread `CrewConsole.enrichment` footgun (already captured as
implementer agent memory with the exact fix pattern, and the Reviewer recommended a backlog item
rather than a notes entry — low severity, both current callers already correct) and the
`DEPRESSION_SIGMA_DEG`/`_SIGHT_*_SCALE` cross-key coupling (matches an already-documented,
accepted class of unclosed coupling in `body-layer/CLAUDE.md`, not a new insight).

## Recurring-fix pattern — process signal

**`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`**
already existed, recording three findings from 2026-10-13 (two in `position_belief.py`, one in
`forest.py`) — all a raw float reaching an integer conversion or arithmetic expression with no
`math.isfinite` guard. This branch's own Security Finding 1 (NaN/Infinity on the new `category`/
`subcategory` wire fields, `int(raw)` called after only an `isinstance` check, worse at one site
with no type guard at all) is a **fourth occurrence**, in a different feature, after the memory
already existed to name the category.

**This is a process signal, not just a repeated code mistake**: the pattern is being caught
reliably at Security/DoD, which means the gate works, but a brand-new feature still made the
identical mistake on its *own* new field — the lesson from findings 1-3 did not reach whoever
wrote this feature's Stage 1 wire parsing. Updated the memory file to record this as finding 4 and
to suggest the fix move earlier: a checklist item at Architect/Implementer time for any plan adding
a new numeric field across a LAN/wire boundary ("every new `int(raw)`/`float(raw)` on externally-
sourced data is `math.isfinite`-guarded before conversion") would catch this before Security does,
rather than after a fourth live finding.

## Verdict: PASSED

Mechanical checks, Reviewer, Security and Performance Reviewer all clean at tip
`0b70a82ea4e53d591b6e0270b8182c4f684e2a6d`. Live acceptance is **PENDING (live)** — `#needs-flight`,
batched above — per the project's standing rule that live acceptance does not gate a merge. Proceed
to merge; the main loop's `/merge` is the trigger per root `CLAUDE.md`'s "DoD PASSED is the merge
trigger."
