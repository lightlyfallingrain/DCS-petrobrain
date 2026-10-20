# Definition of Done — `9k113-narrow-search`

**Scoped to tip `1147dacce7ba97e16c0618f1e9b6ea04db2c8046`** (`feature/9k113-narrow-search`,
detached). This verdict describes that commit only; if the branch has moved since, re-run.

**Verdict: PASS.** Not merged (per dispatch — user pre-approved merge once DoD passes, but this
report stops short of merging; see the final note).

## Code Quality

Single subproject touched: `body-layer/` (confirmed from the diff against the fork point,
`f60f99daa20c4ffdadfe9470b99ae67bdbd61f4f` = `git merge-base main HEAD` — every changed path under
`body-layer/`, `.claude/agent-memory/`, `aircraft-layer/research/`, `docs/acceptance/`, or
`plans/9k113-narrow-search/`; no other subproject's `src`/`tests` changed).

| Check | Command | Result |
|---|---|---|
| Format | `.venv/bin/ruff format --check src tests` (from `body-layer/`) | PASS — 155 files already formatted |
| Lint | `.venv/bin/ruff check src tests` | PASS — all checks passed |
| Type check (strict) | `cd body-layer && .venv/bin/mypy src` | PASS — no issues in 68 source files |
| Tests | `.venv/bin/pytest tests -q` | 2284 passed, 4 xfailed, **2 failed** on first run |
| `defaults.toml` staleness | `.venv/bin/python tools/generate_defaults.py` | PASS — up to date |

**The 2 test failures are the dispatch's own named known-flakes**
(`test_connection_reporter_says_disconnected_once_then_connected_once`,
`test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop`) — both
`ConnectionRefusedError` against a loopback aircraft-layer client that genuinely is not running in
this sandbox. Reran both together in isolation: **2 passed in 2.00s.** No other failure, and
`test_mission_start_reset.py`'s connection tests were not implicated this run.

No debug output, `print(`, `TODO`/`FIXME`/`XXX`, bare `except:`/`except Exception`, or
`pdb`/`breakpoint` introduced in the feature's own diff (`git diff` on
`belief/optic_policy.py`/`logger.py`, grepped). `git status --porcelain` is empty at this tip —
every file is already committed; nothing left unstaged.

## Scope & Correctness

- **Matches the plan as amended.** `plan.md`'s Amendment 2 (the user's own second round,
  2026-10-20) overrides the plan body, and `implementation.md` is explicit about building exactly
  that shape: Stage 1 (idle aim always in regard, all four paths) and Stage 2/3 (split-sector
  geometry, the four-leg `wide → narrow_near → narrow_far → binocular` cycle, wide's far edge
  later corrected to its own derived reach per the F4 follow-up) are built as specified. Stage 4
  Part A (`sight_look_optic`, least-capable-optic-for-a-look) is built; **Part B (attack-run
  guidance's sight-wide-over-binoculars preference) is explicitly not built**, per Amendment 2
  point 3 — confirmed absent by reading `implementation.md`'s own summary and `_apply_guidance`'s
  diff (only the Stage-1 aim-safety cap and the pre-existing down-cap are present; no up-cap).
  This is **not** silent scope-cutting: the plan names the decision, the user settled it, and the
  deferral target (`BL-B66`) is recorded in three places (plan Risks, `implementation.md`, the
  `BL-B64` roadmap note added by this report).
- **No unplanned scope added silently.** Three things were added beyond the original plan text, and
  all three are disclosed, justified, and traced to a required fix or a user direction, not
  invented: (1) the F4 follow-up (wide's far edge derivation) — user direction, F4 in the sortie
  doc; (2) the review's required fix (`sight_can_still_improve`) — user direction mid-review
  ("Fix it, otherwise the whole point of narrow is missed"); (3) the security required fix
  (elevation field-of-regard filtering) — Security's own Required Fix 1. All three re-entered the
  Implementer → Reviewer loop per `AGENTS.md`'s re-entry rule rather than being applied directly,
  confirmed by `review.md`'s three separate re-review sections, each APPROVE.
- **No CLAUDE.md invariants violated.** No-omniscience checked directly by Security ("every new
  function's inputs trace to belief/commanded state, never ground truth") and independently by
  this report (reading `_sight_in_regard_sweep`/`_sight_out_of_regard_sweep`/`_idle_sight_search`:
  all take `ScanPlan`/`OwnshipState`/`OpticState`, no DCS object id or ground-truth position
  anywhere in the new code). Code owns truth / models interpret: unaffected, no model-facing
  surface touched. Read-only DCS access: unaffected, no DCS I/O added.
- **All new/modified files staged.** `git status --porcelain` empty at tip; the diff against the
  fork point lists every touched file and all are present in the commit tree.

## Testing

- Core logic is covered: Stage 1's idle-aim invariant (all four transition paths), Stage 2's
  geometry (`_split_sector_by_regard`/`_commanded_or_default_sector`, including the out-of-regard
  clamping edge case the plan's own worked example never exposed), Stage 3's four-leg cycle and
  its binocular-excursion composition, Stage 4 Part A (`sight_look_optic`), the required fix
  (`sight_can_still_improve`, both call sites, verified by independent mutation by the Reviewer),
  the F4 follow-up (`_SIGHT_WIDE_SEARCH_FAR_M`, wiring verified by mutation), and the security fix
  (elevation filtering, verified by mutation against the review's own reproduced defect figures).
- **Tests are meaningful, not decorative** — every behaviour-critical change in this feature was
  verified by mutation (revert the fix, confirm the specific test goes red for the stated reason,
  restore, confirm empty diff) at least once, by the implementer and independently re-done by the
  Reviewer: `_apply_guidance`'s aim-safety cap, the out-of-regard clamp, both `sight_can_still_
  improve` call sites, the `_SIGHT_WIDE_SEARCH_FAR_M` wiring, and the elevation filter. This is well
  past "the test passes" — it is "the test fails for the right reason when the fix is absent."
- **No existing tests broken.** Nine range-sensitive tests were deliberately rewritten (now assert
  `SIGHT_WIDE_OPTIC` instead of `SIGHT_NARROW_OPTIC` for a 1000 m presence-level target, since
  `sight_look_optic`'s own threshold now resolves that case to wide) — each rewrite is explained in
  `implementation.md`'s "Tests Rewritten" section with the specific measured threshold that
  motivated it, not a blanket "updated to pass." One pinned-bug test
  (`test_idle_sighting_rests_wide_with_nothing_worth_looking_at`) was rewritten because it was
  pinning the F5 defect itself — exactly what the plan's own "Test impact, pinned bug" note
  anticipated before implementation began.

## Documentation

- **Reviewer findings addressed.** `review.md`'s one Required Fix (the sight-candidate admission
  gate) — APPROVE on re-review, verified by independent mutation. Both Optional Refinements were
  resolved in substance even though neither was required: the wide/narrow band-assignment question
  was settled by the user directly (F4 follow-up) rather than left as a guess, and the `_search_
  sweep` right/full test-symmetry gap is low-risk and explicitly disclosed, not silently dropped.
- **Non-obvious behaviour explained.** `implementation.md`'s "What the pilot will notice" section
  (security-fix round) describes the near-edge-band dropout at altitude; the Reviewer's own
  re-review flagged that note as incomplete (it doesn't mention the full-stop case above ~3.6–4 km
  AGL for free/ahead scans) and that gap is now closed structurally — `BL-B86` carries the full
  account and this report's `BL-B64` roadmap note points at it.

## Security

- `plans/9k113-narrow-search/security-review.md` **Part 1 (retroactive plan review): APPROVED.**
  Run together with Part 2 because the plan-review step was skipped after Architect (the plan grew
  by amendment after an initial Security pass structure wasn't invoked in sequence) — disclosed in
  the review's own header, not hidden. The retroactive review found exactly the design gap (regard
  enforcement reasoned in azimuth only) that Part 2's Required Fix then closed, which is the
  intended outcome of a retroactive review finding something real rather than rubber-stamping.
- `plans/9k113-narrow-search/security-review.md` **Part 2 (deep analysis): NEEDS FIXES → fixed →
  re-reviewed by Reviewer (`bb6364b0`) → APPROVE.** One Required Fix (elevation field-of-regard
  enforcement on the idle search cycle), re-entered the Implementer → Reviewer loop per `AGENTS.md`
  rather than going straight to DoD, confirmed by `review.md`'s "Review — security fix" section.
  Filed two backlog items from this pass (`BL-B85`, `BL-B86`), both disclosed non-blocking
  findings, neither a defect introduced carelessly.
- Performance: `plans/9k113-narrow-search/performance-review.md` — **APPROVED — MONITOR**, this
  batch's whole build (Stages 1-4 + the required fix + two follow-up rounds), per the current
  once-per-batch cadence.

## Acceptance boundary — what these fixtures structurally cannot reach

**Every test in this feature is a synthetic `decide()`/`search_pattern` call or a `ConsolePerception
Runner.run_once()` against fakes — none of it is DCS.** Three things no fixture here can show:

1. **Whether the search cycle is perceptible and useful to the pilot as a *behaviour*, not just as
   correct geometry.** A fixture can prove every committed aim stays within ±60°/+20°/−15° and that
   the cycle advances `wide → narrow_near → narrow_far → …` — it cannot show whether that cycle
   *reads*, from the cockpit, as "the sight is searching" the way F4's complaint wanted, or whether
   the ~66 s full-cycle period (measured by the Reviewer's own stress scenario) feels too slow or
   too fast in a real sortie.
2. **Whether the no-lower-bound sight-candidate gate behaves as disclosed under a real, not
   synthetic, classification pipeline.** `BL-B85`'s pessimistic scenario (classification frozen at
   `presence` forever) is a deliberately-unrealistic stress case the review itself flags as "not
   modelled behaviour" — it tells us the gate degrades gracefully in the worst case, not what the
   real belief layer's classification cadence will actually produce in flight.
3. **Whether the F4-follow-up wide-band-far-edge figure (~8.28 km) and the four-leg cycle's actual
   timing feel right against real terrain, real contact density, and a real workload** — none of
   which a 900-simulated-second synthetic stress test or a unit test of `search_pattern` in
   isolation can stand in for.

**None of this blocks the merge.** Per the dispatch: live acceptance is card item A8 on the Open
Flight Tests card (`docs/acceptance/2026-10-20-open-flight-tests-results.md`, "still open") — a
later flight, not asked for here. Tagged `#needs-flight` on `BL-B64`'s roadmap entry (this report's
own addition), where F4/F5 and this follow-on build are now recorded together.

## Unblock-condition check (accepted debt)

Checked whether any of this feature's deferred/accepted items name an executable clearing
condition: `BL-B83`/`BL-B84` are genuinely deferred design decisions with no stated command to run
(they wait on a Mission Interpreter objective-area datum and a user decision, respectively — not a
script). `BL-B85`/`BL-B86` are disclosed, non-blocking measurement results with open design
questions, not commands. `#needs-flight` on `BL-B64` names a sortie, which this report is
explicitly instructed not to execute (live acceptance is later, card A8). **No executable unblock
command exists for any item this feature leaves open** — nothing was skipped here.

## Roadmap / bookkeeping

- `body-layer/ROADMAP/BL-B64.md` — appended a done-note for this follow-on build, `#needs-flight`,
  naming F4/F5, what was built and deferred, and cross-linking `BL-B83`/`BL-B84`/`BL-B85`/`BL-B86`.
  `BL-B83`–`BL-B86` were already filed and indexed in `body-layer/ROADMAP/body-layer-backlog.md` by
  the Architect/Security passes during this feature's own work — confirmed present, not re-filed.
- Root `ROADMAP.md`'s Body Layer row — appended one summary sentence for this merge (the status
  table is the enumeration source per root `CLAUDE.md`'s rule; this is an addition to an existing
  row, not a new row).
- `notes/` — restored from `git show main:notes/<file>` (this branch's base predates the
  2026-10-19 `NOTES.md` split) and appended to two existing topic files:
  `the-9k113-sight-bl-b64.md` (two bullets: the third occurrence of the field-of-regard
  enforcement gap on this subsystem, specifically on `search_pattern`'s elevation; and the
  test-overlap gap — an invariant test with empty inputs and a real-geometry test checking only
  azimuth, side by side, neither covering the combination that mattered) and
  `attack-run-guidance-design-bl-14.md` (one bullet: a two-sided window's lower bound exists for a
  specific reason, and copying its shape into a context that lacks that reason over-excludes —
  `sight_can_still_improve`'s deliberate no-lower-bound departure from `improvement_window_m`).
  No new topic file needed.
- `.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md` — new pattern
  memory. **Process signal, not code debt**: this is the third time the same category (a new
  producer/caller of a committed sight aim not checked against the optic's own field-of-regard, on
  every axis the bound has) has shipped past the plan and at least one review pass before being
  caught — twice by Security specifically. Worth surfacing to Architect/plan review for any future
  9K113 work (`BL-B66` is next) rather than continuing to rely on a Mode-2 Security pass to catch
  it a fourth time.

## Milestone-completion question

**Does this change what the next milestone should be, or invalidate a downstream assumption?**
Yes, in one concrete way: `BL-B66` (the 9K113 effector/slew entry) now inherits `sight_search_leg`
as a condition its real slew model must reckon with — a slew interrupted by a leg transition
(wide→narrow, or either→binocular-excursion) behaves differently from one that completes
undisturbed, which is new surface this feature adds for `BL-B66` to account for, not present
before it. It also hands `BL-B66` the Stage 4 Part B deferral directly: the "prefer sight-wide over
binoculars, except for a quick look" preference becomes buildable the moment `advance_sight_aim`
gets a real, nonzero slew duration, and should be built then rather than guessed at now (both
already stated in `plan.md`'s Second-order effect and reiterated in this report's `BL-B64` note).
No downstream assumption is invalidated — `BL-B67` (the ATGM run) is unaffected.

## Note on merge (batch 1)

Per the dispatch, this report stops at DoD PASS and does **not** merge — "Don't merge." The branch
is `feature/9k113-narrow-search`, this report's tip is `1147dacce7ba97e16c0618f1e9b6ea04db2c8046`,
and the roadmap/notes/memory edits above are committed on top of it on this same detached HEAD (see
final commit sha in the handback message).

---

# Batch 2 — 2026-10-20/21, tip `9f4b96103134602a060e0d2642cbfbda778bad2b`

**Scoped to tip `9f4b96103134602a060e0d2642cbfbda778bad2b`.** This verdict describes that commit
only; if the branch has moved since, re-run. Batch 1 (above) already got DoD PASS at `1147dacc`.
This batch is everything on the branch's own first-parent history between `1147dacc` and
`9f4b9610` — confirmed by `git log --first-parent --no-merges 1147dacc..9f4b9610`: F5 boresight-
relative regard check (`49f92738`), the `BL-B85` review required fix (`9cba4943`), Review CHANGES
REQUIRED (`effbd933`) → fix (`135e2414`: import-crash floor, `BL-B85` realistic-case test) →
re-review APPROVE (`8cb3c527`), Performance review batch 2 (`2f3c2627`), Security deep analysis
batch 2 (`9f4b9610`, APPROVED). Two merge commits in this range (`cce0b57a`, `88ac4200`) pull in
unrelated, already-DoD-passed work from `main` (`landmark-words-no-names`,
`taking-fire-visible-shooter`, `voice-latency-instrumentation`, `audio-adapter-os-independent`) —
confirmed none of those touch `body-layer/src`/`body-layer/tests`/`plans/9k113-narrow-search/`
(the same scoping the Reviewer and Security passes for this batch already established and this
report independently re-confirmed via `git diff --name-only`), so they are out of scope for this
batch's own DoD and are not re-verified here (they carry their own DoD reports).

**Verdict: PASS.**

## Code Quality

Single subproject touched by this batch's own commits: `body-layer/` (plus
`plans/9k113-narrow-search/`, `.claude/agent-memory/`, `body-layer/ROADMAP/`,
`docs/acceptance/`, `notes/` — none of them a subproject with its own commands). Confirmed by
`git log --first-parent --no-merges 1147dacc..9f4b9610` and `git show --stat` on each of those
commits individually (the two bookkeeping-only `BL-B89` commits in the range touch only
`body-layer/ROADMAP/` and `docs/acceptance/`, no source).

Re-ran every check myself, from inside this worktree, using the main checkout's `body-layer/.venv`
binaries with `cwd` set inside this worktree's `body-layer/` (the documented pattern for an
isolated worktree with no `.venv` of its own,
`.claude/agent-memory/implementer/feedback_worktree_no_venv.md`):

| Check | Command | Result |
|---|---|---|
| Format | `python -m ruff format --check src tests` | PASS — 156 files already formatted |
| Lint | `python -m ruff check src tests` | PASS — all checks passed |
| Type check (strict) | `cd body-layer && python -m mypy src` | PASS — no issues in 68 source files |
| Tests | `python -m pytest tests -q` | **2360 passed, 4 xfailed, 0 failed — clean on first run, no flakes** |
| `defaults.toml` staleness | `python tools/generate_defaults.py` | PASS — up to date; `git status --porcelain` empty after |

No debug output, `print(`, `TODO`/`FIXME`/`XXX`, bare `except:`/`except Exception`, or
`pdb`/`breakpoint` found in this batch's own diff (`git diff --first-parent 1147dacc..9f4b9610 --
body-layer/src`, read in full while reviewing scope above). `git status --porcelain` is empty at
this tip before any of this report's own edits.

**Tuning**: `SIGHT_STALL_COOLDOWN_S` (new this batch, `BL-B85`) is declared via `tuning.real` with
`lo=30.0, hi=400.0` and a `#:` comment; checked the **rendered** `config/defaults.toml` directly
(`body-layer/config/defaults.toml:108-111`) — the full first-sentence comment, bounds line, and
value are intact, no truncation. `_EFFECTIVE_SIGHT_STALL_COOLDOWN_S` (the import-crash fix) is
correctly excluded from `tuning.*`/`defaults.toml` — its RHS is a derived expression over one
already-tunable constant and one already-derived constant, failing the inclusion test's
free-parameter criterion by construction, consistent with this same file's own `_SIGHT_WIDE_
SEARCH_FAR_M` precedent from batch 1.

## Scope & Correctness

- **Matches the plan, as amended by the sortie feedback this batch responds to.** F5's second round
  (`docs/acceptance/2026-10-20-sortie-feedback.md`, "the 9K113 vertical limits are boresight-
  relative") is the user's own correction of batch 1's shipped fix, not new scope invented by this
  batch — batch 1's elevation check was real and correct at zero pitch/bank, and this batch extends
  it to the general case the user actually described. `BL-B85`'s required fix (the progressing-look
  commit rule) is Review's own required fix on code this feature itself shipped in batch 1, not
  scope drift.
- **No unplanned scope added silently.** The one thing beyond the immediate fix requests —
  `_EFFECTIVE_SIGHT_STALL_COOLDOWN_S` replacing a bare assert — is Review's own required fix
  (Required Fix 1, "Review — F5 boresight + BL-B85 refinement"), not an invented addition; disclosed
  in `implementation.md`'s "Required fixes round 2" section.
- **The re-entry loop was followed correctly.** Every required fix in this batch (Review's two
  fixes from "Review — F5 boresight + BL-B85 refinement," Security's — none this batch, Part 2 was
  already closed in batch 1) went Implementer → Reviewer-on-the-fix before Performance/Security's
  own batch-2 passes ran, confirmed by `review.md`'s own re-review section dated after `135e2414`
  and by the commit graph (`135e2414` → `8929f824`/review-memory commit → `8cb3c527` re-review
  APPROVE → `2f3c2627` perf → `9f4b9610` security, in that order).
- **Performance review asked for no change this batch** — verdict is APPROVED — MONITOR with every
  finding disposed as "none"/"MONITOR, not NOW"; no re-entry needed, confirmed by reading
  `performance-review.md`'s "Batch 2" section in full (no "Action: NOW" or fix request anywhere in
  it).
- **No CLAUDE.md invariants violated.** No-omniscience re-checked directly by Security's batch-2
  deep analysis ("every new function's inputs trace to belief/commanded state, never ground truth")
  and independently by this report: `heading_relative_to_body_relative`'s only new inputs are
  `ownship.pitch_deg`/`ownship.bank_deg` (ownship's own telemetry, not a contact field) and
  `target.current_level` (belief-derived, via `_look_targets`). Code owns truth / models interpret:
  unaffected. Single-player scope: unaffected, no multiplayer surface touched.
- **All new/modified files staged.** `git status --porcelain` empty at tip `9f4b9610`, before this
  report's own additions.

## Testing

- Core logic covered: F5's frame conversion (`test_geometry.py`'s pitch/nose-up/bank cases,
  independently re-derived algebraically by the Reviewer before being checked against the tests,
  not fitted to them), the three `TestSightInRegardSweepBoresightRelative` tests in `test_logger.py`
  driving the real production sweep builders, and `BL-B85`'s progressing-look fix
  (`test_a_progressing_contact_is_relooked_near_the_pre_bl_b85_cadence`) plus its realistic-case
  scenario now a committed test
  (`test_three_progressing_contacts_all_reach_type_and_search_resumes`,
  `TestSightStallCooldown`) rather than a narrative figure — this directly satisfies the prior
  review round's explicit "as a committed test, not a one-off narrative number" requirement, and
  the committed test is what resolved two independently-reproduced, disagreeing sets of prose
  numbers (10.4%/97/262/427s vs. 19.4%/130/163/196s) to one.
- **Tests are meaningful, not decorative.** Every behaviour-critical change this batch was verified
  by mutation at least once by the Reviewer, independently of the implementer's own claimed
  mutations: the frame-conversion's `pitch_deg` hardcoded to `0.0` (5 tests red, matching the
  implementer's claimed count exactly); the old unconditional commit restored in
  `_start_glance_away` (94 s reproduced exactly); the bare assert restored verbatim (import-time
  `AssertionError` reproduced under a constructed `PETROBRAIN_TUNING` file); `max`→`min` swapped in
  the floor expression (caught by the committed test's own behavioural assertion, not just a
  snapshot). This is "the test fails for the stated reason when the fix is absent," not "the test
  passes."
- **No existing tests broken.** `TestSightLookOptic`'s stale "narrow is unreachable" docstring claim
  (already corrected in batch 1) and `BL-B85.md`'s stale ~175 s/71.5% narrative figure (this batch)
  are both the kind of claim this review explicitly checked does not survive uncorrected — confirmed
  removed by reading the current file, not the diff hunk alone.

## Documentation

- **Reviewer findings addressed.** Both required fixes from "Review — F5 boresight + BL-B85
  refinement" (the import-time-crash assert, the missing committed test) — re-reviewed, APPROVE,
  verified by this report's own fresh reading of the re-review's mutation evidence rather than
  taken on trust.
- **Non-obvious behaviour explained.** `BL-B86.md`'s own 2026-10-20 addendum (added by this batch's
  own security-adjacent work, read and confirmed by this report) already states that its altitude
  figures are level-flight-only and move with attitude once F5's frame fix lands — the roadmap
  entry was kept honest about its own figures' scope *before* this report touched it, which this
  report independently verified rather than assumed.

## Security

- `plans/9k113-narrow-search/security-review.md` **"Deep analysis — batch 2" (scope: `git diff
  5e917840..8cb3c527 -- body-layer/src`, restricted to this feature's own first-parent commits):
  APPROVED, no required fixes.** One finding (the never-pruned `attempted_at_level`/
  `pending_attempted_at_level` dicts) disposed as "not filed, intentionally" with reasoning given
  in the review itself (bounded by per-mission reset, single-player non-adversarial context) —
  read and agree with that reasoning rather than taking the disposition on trust; it is the same
  shape as the pre-existing, previously-accepted `attempted_at_range_m`/`attempted_at_time_sim`
  dicts, not a new growth mechanism.
- Performance: `plans/9k113-narrow-search/performance-review.md` **"Batch 2": APPROVED — MONITOR.**
  Worst measured per-poll cost (495.8 µs, commanded `full` at altitude with pitch/bank) is
  0.0496% of the 1.0 Hz poll budget — three orders of magnitude under budget.

## Acceptance boundary — what these fixtures structurally cannot reach (batch 2, additive to
batch 1's own boundary above)

1. **Whether the boresight-relative correction *feels* right in a real climb/dive/bank, not just
   algebraically right.** The fixtures prove the rotation is the correct general identity and that
   it is wired through every real producer — they cannot show whether a pilot flying a steep bank
   near the sight's ±60° azimuth limit perceives the sight's reach changing the way the physics now
   says it should, which is exactly the shape of thing F5 itself was: a defect visible only in a
   real cockpit, not a fixture.
2. **Whether `SIGHT_STALL_COOLDOWN_S = 132.0 s` is the right default once flown.** `BL-B85.md`
   itself says this explicitly — "a judgement on whether 132.0 s is the right default... is not
   something a synthetic 600 s reproduction can validate by itself." This batch's own committed
   realistic-case test confirms the *mechanism* behaves as intended; it cannot confirm the
   *constant* is well-tuned for an actual sortie's contact tempo.

**None of this blocks the merge.** Same outstanding sortie as batch 1 — card A8,
`docs/acceptance/2026-10-20-open-flight-tests-results.md` — not a second card; this batch corrects
the mechanism the same flight will exercise.

## Unblock-condition check (accepted debt), batch 2

No new accepted-debt item with a stated executable unblock condition was added this batch.
`#needs-flight` on `BL-B64` is unchanged (same sortie, card A8, already checked in batch 1's own
unblock-condition section above — re-confirmed here rather than re-derived: still names a sortie,
not a command, and this report is not the one flying it). `BL-B86`'s own open design question
(whether the idle fallback should do better than hold a fixed aim) names no executable command
either — it is a decision for Architect/the user, per the review's own disposition, unchanged by
this batch.

## Roadmap / bookkeeping (batch 2, this report's own additions)

- `body-layer/ROADMAP/BL-B64.md` — appended a "Batch 2" addendum under the existing follow-on
  section: what F5's second round fixed and why batch 1's fix was insufficient, the `BL-B85`
  required-follow-up, the self-corrected import-crash defect, and an explicit note that
  `#needs-flight` is unchanged (same sortie, not a new one).
- Root `ROADMAP.md`'s Body Layer row — appended one sentence to the existing `9k113-narrow-search`
  entry (addition to an existing row, not a new one, per root `CLAUDE.md`'s enumeration rule).
- `body-layer/ROADMAP/BL-B85.md` — already current as of this batch's own commits (the realistic-
  case paragraph was rewritten by the implementer/reviewer loop itself, not left for DoD to fix);
  confirmed by reading it, no edit needed from this report.
- `notes/the-9k113-sight-bl-b64.md` — appended two bullets: a bound check can be present and tested
  and still wrong if evaluated in the wrong reference frame (the F5 second-round lesson), and a fix
  for a pathological case can silently throttle the healthy case too, which only a committed test
  (not a narrative figure) can settle (the `BL-B85` refinement lesson). No new topic file needed.
- `.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md` — updated from
  "third occurrence" to "fourth occurrence," adding this batch's variant (checked, but in the wrong
  frame — a different failure shape from the first three's "never checked at all," same root cause
  one level up). Process signal restated for `BL-B66`.

## Milestone-completion question (batch 2)

**Does this change what the next milestone should be, or invalidate a downstream assumption?**
No change beyond what batch 1 already recorded: `BL-B66` still inherits `sight_search_leg` as new
surface its real slew model must reckon with, and still inherits the Stage 4 Part B deferral. This
batch's own addition to that inheritance: `BL-B66` also inherits a sight whose field-of-regard
check is now correctly boresight-relative, which it must preserve (not regress to ground-anchored)
once real slew dynamics are added. No downstream assumption invalidated.

## Note on merge (batch 2)

Per the dispatch, this report does **not** merge — the main loop will. Branch
`feature/9k113-narrow-search`, this report's tip `9f4b96103134602a060e0d2642cbfbda778bad2b`, and
the roadmap/notes/memory edits above are committed on top of it inside this worktree (see commit
sha and file list in the handback message).
