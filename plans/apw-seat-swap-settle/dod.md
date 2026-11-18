### Definition of Done: `fix/apw-seat-swap-settle`

**Verdict: PASSED**

**Scoped to tip `d095d8fbabf61fac997481b222ba027996e08fd9`** (Review: "fix/apw-seat-swap-settle
-- APPROVED"). This worktree started on `origin/HEAD` (`59192cfa`, main's post-merge tip after
the unrelated `fix/apw-status-json-quotes` merge) — a strict descendant of this branch's own
base (`797f53db`) but not of this branch's tip, so `d095d8fb` is **not** a descendant of
`59192cfa` and `59192cfa` is not an ancestor of `d095d8fb`. Checked out `d095d8fb` directly
(`git checkout -B dod-settle d095d8fbab...`, clean tree) per the fallback instruction rather than
attempting a fast-forward that does not exist.

### Code Quality

- **Full aircraft-layer suite** (`.claude/scripts/fast-tests.sh --full aircraft-layer`, parallel
  via pytest-xdist): **884 passed**, 10.40 s. (The venv was resolved via a temporary, untracked
  symlink `aircraft-layer/.venv -> /Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`, since this
  worktree does not carry its own; removed again before committing — confirmed not staged, not in
  `git status`.)
- `aircraft-layer/.venv/bin/ruff format --check src tests` — 81 files already formatted.
- `aircraft-layer/.venv/bin/ruff check src tests` — all checks passed.
- `cd aircraft-layer && .venv/bin/mypy src` — Success: no issues found in 27 source files.
- `luac5.1 -p aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` — passes.
- No debug output, no `print(`, no `TODO`/`FIXME` in the diff (`git diff 797f53db..d095d8fb`
  grepped clean).
- No unplanned scope: diff touches exactly the Lua file, its test file, the debug/review/security
  plan files, and three agent-memory files — matches the bug's stated surface.

### Scope & Correctness

- Bug-fix path (Debugger → Reviewer → Security), no `plan.md`/`U<n>` decisions —
  `accepted-items-ledger.sh plans/apw-seat-swap-settle` returns no `U<n>` lines, confirmed.
- Implementation matches `debug.md`'s fix exactly: new `AI_PILOT_SEAT_CHANGE_SETTLE_S = 0.5`,
  settle window armed only on a detected pilot→operator transition, operator→pilot left
  immediate by design (not a gap — argued and tested both ways).
- No invariants violated: no new `performClickableAction` call site (Security confirmed); holds
  a belief at its prior value rather than inventing one (no-omniscience boundary respected).
- All new/modified files staged (they arrived pre-staged in the reviewed/approved commits
  `4c1224b0`/`15df914e`/`d095d8fb`; nothing new left unstaged by this DoD pass except the roadmap/
  notes additions below, now staged and committed in this same pass).

### Testing

- Core logic covered: `test_seat_swap_settle_absorbs_flight8_unstow_animation` (the actual
  flight-8 frame sequence, no edge fires), `test_automatic_handover_parks_after_the_settle_window`
  (852 stays stowed through the whole window — DCS automatic handover — edge fires only after),
  `test_request_control_key_with_no_seat_change_is_immediate` (no camera move, unaffected), and the
  updated `test_entering_operator_seat_with_stick_still_stowed_presses_nothing`. Reviewer
  independently mutation-checked these by forcing `settling` to always-`false` and confirmed 3 of 4
  failed as expected — the tests pin real behaviour, not merely exercise it.
- No existing tests broken: full suite green (884 passed), including the pre-existing
  reverse-direction tests Reviewer re-confirmed pass unchanged.

### Documentation

- Reviewer findings: **none required.** Security findings: **none required.** Both verdicts
  APPROVED with no required fixes — nothing to track against the ledger beyond the (empty) `U<n>`
  list already confirmed above.
- Non-obvious behaviour (the directional asymmetry, why the settle holds the *prior* value rather
  than a fixed one, why a first-ever seat read never arms the window) is explained in `debug.md`,
  `review.md`, and the three agent-memory files in the diff — read in full.

### Security

- `plans/apw-seat-swap-settle/security.md` exists, verdict **APPROVED**, no required fixes.

### Trial merge check against main's current tip

`git merge-tree --write-tree d095d8fb 59192cfa` (main's tip when this DoD ran) returned a single
tree sha with no `CONFLICT` markers for the **reviewed/tested diff itself** — the Lua fix, its
tests, and the plan files do not overlap `59192cfa`'s own changes (confined to `text_or_null`'s
body in the same file, a disjoint line range, as Review already noted).

**One real, trivial conflict exists, found while doing this DoD's own roadmap bookkeeping** (not
in the reviewed code): `fix/apw-status-json-quotes` added `[[AC-B15]]` to
`aircraft-layer/ROADMAP/aircraft-layer-roadmap.md` immediately after the same `[[AC-B14]]` line
this DoD pass's own `[[AC-B16]]` addition appends after — both branches insert at the identical
anchor point in the index's backlog list. This is a textbook same-line-append conflict a
three-way merge will flag (confirmed structurally, not by running a real conflicting merge against
a tree I should not create here) — `/merge`'s own flow resolves it by keeping both inserted lines
(order does not matter, they are independent list rows). Flagging it now rather than letting it
surprise the merge step. No other file in this DoD's own additions (`AC-B16.md` is a new file, no
collision possible; `notes/debugging-and-root-cause-diagnosis.md`'s edit only appends after the
existing last bullet, which `59192cfa` does not touch) carries this risk.

### Milestone Completion question

No — this closes a transient-reading defect in `[[BL-16]]` mode 2's existing seat gate; it does
not change what Stage P3 (align/launch, break turns) needs or assumes, and raises no new
assumption for any later stage.

### Acceptance

**Live acceptance needs DCS — marked `#needs-flight`** on the new roadmap entry
`aircraft-layer/ROADMAP/AC-B16.md`. What the user does: from the pilot seat with Petrovich flying
(AI-wheel mode 2) or with him off (`request control` not pressed), swap to the operator seat —
once with DCS's "automatic AI handover" setting on, once with it off (the two settings the user's
own direction named) — and watch/grep `GET /ai_pilot_wheel/latest`'s `parked_active` or the
in-cockpit log for a false park rising edge inside the first ~0.5 s of the swap. Expected: no
false edge with the setting off (control stays genuinely unparked throughout); with it on, the
edge fires once, only after DCS's own handover genuinely parks the stick, never during the
settle window on an unstow animation alone.

Acceptance card: not published as a separate artifact for this pass — the check is a single
timing observation (presence/absence of a transient park edge across one swap, twice) rather than
a multi-step script worth a dedicated card; the above paragraph is the full, concrete test and is
also written into `AC-B16.md`. **Branch to fly: `main`, after this merge.**

### Notes harvest

One insight added to `notes/debugging-and-root-cause-diagnosis.md`: the general pattern that a
DCS cockpit arg driven by the game's own animation can lag the camera-derived state read that
gates it, and the settle-window fix shape (arm only on transition, hold the *prior* value,
one-directional when only one side has a sensor-lag side to absorb). Checked against existing
topic files first (`notes-harvest` skill run manually via its embedded script, since the skill
tool resolves to a usage/instructions message rather than an executable in this harness) — no
existing bullet covers this mechanism; `debugging-and-root-cause-diagnosis.md` was the closest
existing fit (general root-cause/fix-shape lessons), so no new topic file was created.

`python3 .claude/scripts/memory-search.py -r dod seat settle animation lag transient` returned no
match — not a recurring pattern yet, nothing further to flag as process debt.

### Roadmap

- New entry `aircraft-layer/ROADMAP/AC-B16.md`, `[x]` done, `#needs-flight`, filed from this fix.
- `aircraft-layer/ROADMAP/aircraft-layer-roadmap.md` index updated with the new `[[AC-B16]]` row.
  **Known trivial merge conflict with `59192cfa`'s own `[[AC-B15]]` row at the same anchor point —
  see "Trial merge check" above; `/merge` resolves by keeping both.**
- `body-layer/ROADMAP/BL-16.md` deliberately **not** touched: main has moved substantially on that
  file since this branch's fork point (`797f53db`) — flights 7/8/9 of a separate M0 investigation
  are already on `main` and not in this branch's history — so appending here risks a second,
  larger conflict for no information this fix actually changes about BL-16's own stages. The
  `AC-B16.md` entry itself carries the milestone-completion note.
