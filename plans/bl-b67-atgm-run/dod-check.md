# Definition of Done — BL-B67 batch A (Stages 1-4 + Stage 0 probes)

Scope: `feature/bl-b67-atgm-run`, tip `822f9ad17f6e67a0522aade7f0978f27e59dfcbb` (pushed to
origin). This verdict is scoped to that commit; if the branch moves after this report, re-run.
HEAD was a strict ancestor of the tip and the worktree tree was clean, so the merge was a plain
`git merge --ff-only` — no cherry-pick, no divergence.

Batch A = Stages 1-4 (run skeleton, single-unit aim, `atgm_run.decide`, aircraft-layer payload
feed) plus the Stage 0 probe sortie's own disposable Lua. Batch B (Stages 5-7, the real own-weapon
channel and effectors) waits on the Stage 0 sortie's answers; Stage 8 is live acceptance of the
whole run. **This DoD gates batch A only.**

## Code Quality

| Check | body-layer | aircraft-layer |
|---|---|---|
| `ruff format --check` | 190 files already formatted | 75 files already formatted |
| `ruff check` | all checks passed | all checks passed |
| `mypy --strict` (`cd <sub> && .venv/bin/mypy src`) | 0 errors, 78 files | 0 errors, 26 files |
| `pytest -q` | 2778 passed, 4 xfailed | 645 passed |

Subproject list derived from the diff (`git diff --name-only main HEAD`), not from memory:
`aircraft-layer`, `body-layer` (plus `.claude/agent-memory/`, `docs/`, `plans/` — no
format/lint/type/test commands apply to those).

Lua (`luac5.1 -p` + `GETGLOBAL` scan) on all three changed `.lua` files — re-run directly, not
taken from `implementation.md`:
- `Export.lua`, `Export.probe-weapons.lua`, `petrobrain-damage-events-probe-hook.lua`: syntax
  clean; every `GETGLOBAL` hit is a genuine DCS API, Lua stdlib, or this project's own established
  `DUMPED_*`/`PB_PROBE_*` cross-call shared-global pattern — no own-helper name leaked (the
  no-hoisting bug class this check exists for).
- The `dostring_in` string literals inside `petrobrain-damage-events-probe-hook.lua`
  (`EVENT_REGISTER_CODE`/`EVENT_POLL_CODE`/`WEAPON_EXIST_POLL_CODE`/`LIFE_CODE`) were independently
  extracted and scanned by Reviewer's Stage 0 pass (not re-extracted here — Reviewer's own pass
  already re-ran this mechanically rather than trusting `implementation.md`, see `review.md`
  "Stage 0"); confirmed clean there.

No unhandled errors/panics in data paths, no debug output, no stray TODOs introduced — confirmed
by Reviewer's full-diff reads across all four stages (`review.md`), not re-derived here.

## Scope & Correctness

- Implementation matches `plans/bl-b67-atgm-run/plan.md` for Stages 1-4 and Stage 0, per
  Reviewer's own stage-by-stage checklist verification (`review.md`).
- No unplanned scope added silently — every deviation from the plan is flagged in
  `implementation.md`'s "Notable Discoveries / Deviations From the Plan" sections per stage, and
  each was judged by Reviewer, not silently accepted.
- No invariants from `CLAUDE.md` violated: the no-omniscience fence (`percept.py`/`attack_run.py`
  only) holds for the new `aim_unit_direction` field, confirmed by Reviewer's mutation test
  (appended a stray reference elsewhere, the grep fence failed correctly, reverted). The
  `body-layer/CLAUDE.md` and `docs/STRUCTURE.md` invariant-text gaps Reviewer found (Stages 1-2
  required fixes) were confirmed landed directly: grepped `CLAUDE.md` for `aim_unit_direction`
  (present, naming it as the sibling field under the same fence) and `STRUCTURE.md` for the same
  plus a dedicated `atgm_run.py` module entry — both present.
- All new files staged with `git add` — confirmed via `git status --porcelain` (clean) after the
  fast-forward; nothing was left uncommitted by any stage.

## Testing

- Core logic (`atgm_run.decide`'s full state machine, single-unit aim, the payload wire
  parser/ledger/cache) is covered; Reviewer ran five targeted mutations against Stage 3's
  highest-risk claims (range-call latch, backstop silence, no-ATGM callout, the N2
  pass-through exclusion, failed-launch no-op) and one against Stage 4's change-gate — all caught
  correctly, one (N2) found a real test gap that was then closed.
- Tests are real, not decorative: the Lua test harness extracts and runs the actual shipped
  functions under a real Lua interpreter rather than a hand-duplicated copy (confirmed by
  Reviewer); the four Co-moving-Fields integration tests drive the real threaded poll loop, not a
  unit-level stand-in.
- No existing tests broken — full-suite pass counts above match `implementation.md`'s own reported
  counts stage-by-stage, confirmed independently rather than trusted.

## Documentation

- Reviewer's required fixes, all three, verified landed by direct grep/read (not taken on report):
  1. `CLAUDE.md`/`STRUCTURE.md` `aim_unit_direction` sibling-field text (Stages 1-2 review).
  2. `ATGM_MIN_RANGE_M` wired into `_maybe_range_call` (`atgm_run.py:386`,
     `inputs.belief_range_m < ATGM_MIN_RANGE_M`) and the Decision-N2 pass-through-exclusion test
     added to `test_callouts.py` (Stage 3 review).
  3. The Stage 0 probe's knob auto-advance delayed `ADVANCE_DELAY_S` past the count-drop rather
     than switching on the same poll as a launch (`Export.probe-weapons.lua`'s
     `maybe_advance_station`, confirmed present at line 303+).
- Non-obvious behaviour explained via code structure/docstrings and the `notes/` harvest below;
  `docs/acceptance/2026-10-29-bl-b67-stage0-probe.md` + its published card document the Stage 0
  sortie for the user.
- **Branch-naming defect caught by actually reading the live card, not trusting the input
  list**: the published card and the acceptance doc both named `feature/bl-b67-atgm-run` (correct
  when written, before this merge). Since the probe `.lua` files are part of batch A's diff, the
  branch to fly after this merge is `main`, not the feature branch — which is normally harvested
  away. Fixed both (doc edited, card republished to the same URL) before writing this report, per
  this role's own standing rule to execute/verify every command and claim in a card rather than
  reconstruct it from what should be true.

## Security

- `plans/bl-b67-atgm-run/security-plan-review.md` — **APPROVED** (original pass + a re-review of
  the revised S_EVENT_SHOT design, also APPROVED, with one non-blocking amendment required before
  Stage 5 implementation: an independent parser-side length/charset bound on the own-weapon
  `<type>` field. Tracked for Stage 5, not reachable from this batch's diff — confirmed:
  `perception/own_weapons.py` does not exist yet).
- `plans/bl-b67-atgm-run/security-review.md` — **APPROVED**, batch A (Stages 1-4 + Stage 0 probes),
  no required fixes.

## Performance

`plans/bl-b67-atgm-run/performance-review.md` — **APPROVED**. Every new per-poll operation is O(1)
or bounded by cluster/station-count size, not full-dataset; no credible risk at any realistic
scale given this project's current (pre-Runtime) performance bar.

## Amendments made at this DoD pass

- `plans/attack-run/plan.md` Decision 15 marked `REVISED`: Stage 1 now reads
  `attack_run_weapon`/gates on `"missiles"`, superseding the decision's "parses and nothing reads
  it" premise.
- `body-layer/ROADMAP/BL-B67.md` updated: status `[~]` #status/in-progress #needs-flight (not
  done — batch B and Stage 8 remain), what landed, the published Stage 0 card, what batch B waits
  on, the milestone-completion question answered, and the re-point-gap precondition on Stage 7's
  dispatch carried forward explicitly so it cannot be silently dropped.
- `.claude/agent-memory/dod/project_recurring_stale_state_on_transition.md` updated: this is the
  tenth recorded occurrence of the project's recurring stale-state-on-transition defect shape
  (across `BL-14` x4, `BL-B64`/`BL-B80` x3, `BL-B89`/`BL-B98` x2, `BL-B67` x1) and the first where
  the Co-moving Fields table itself was already correct and only the construction site (written a
  stage earlier, before the table's relevant row became reachable) drifted from it. Flagged as a
  process signal: a plan that stages a state machine's construction and its activation separately
  should have Architect's step 6a ask whether every table row still holds at the later stage that
  makes it reachable, not only at the stage that writes the construction site.
- `notes/fixture-management-and-test-infrastructure.md`: two additions — (1) the Lua
  function-extraction for/while-truncation bug recurred exactly as a prior note predicted, in
  `test_payload_lua.py`, with `test_sight_servo_lua.py`'s own copy still unfixed; (2) a DCS
  scripting-API call modelled as `(ok, value)` from a `pcall`-wrapping snippet's variable names can
  in fact return a single value (`LoGetNameByType`).

## Unblock conditions executed (not just read)

- Verified `ATGM_MIN_RANGE_M`, the N2 test, and the knob-delay fix actually landed in the code
  (grep, not implementation.md's claim) — see "Documentation" above.
- Verified the re-point gap is genuinely inert today: `grep -rn "atgm_run\.decide\|import
  atgm_run" body-layer/src` returns exactly one hit (the dataclass import in `body.py`) —
  `decide` is called from nowhere in production code yet, confirmed directly in this worktree,
  not re-trusted from Reviewer's own grep.
- Ran the `#needs-flight` discoverability recipe from `docs/TAGS.md` against the live tree after
  editing the roadmap entry: `grep -rl '#needs-flight' --include='*.md' */ROADMAP/ todo/backlog/
  todo/todo/ | grep -vE -- '-(roadmap|backlog|tasks)\.md$'` lists `body-layer/ROADMAP/BL-B67.md` —
  the tag is mechanically findable, not just typed into prose.

## Acceptance boundary — what this batch's fixtures structurally cannot reach

All of batch A is pure-function/wire-level code with no production call site into `body.py`'s poll
loop (`atgm_run.decide` has exactly one reference in `src/`, the dataclass import). **No fixture in
this batch can show the run actually happening in a cockpit** — not the state machine's
correctness against synthetic events, not the payload feed's wire shape, not the Stage 0 probe's
own Lua syntax. The acceptance boundary is Stage 7 (wiring) and Stage 8 (live run), both still
ahead. The Stage 0 sortie is the first point any of this touches a real DCS session, and it only
exercises probe/recon code, not the production run.

## Verdict

**PASSED** for batch A (Stages 1-4 + Stage 0 probes) at tip `822f9ad1`. Merge trigger per root
`CLAUDE.md` "Workflow". Acceptance for the Stage 0 sortie is **PENDING (live)** —
`#needs-flight` on `body-layer/ROADMAP/BL-B67.md`, card published at
https://claude.ai/artifact/QyBjsW7tpswWzD63Zigbd5, branch `main` after this merge. Batch B
(Stages 5-7) and Stage 8 (live acceptance of the whole run) are explicitly not done and not
claimed done anywhere in this report.
