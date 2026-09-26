# DoD Check: sortie-2026-09-26-fixes

Branch `fix/sortie-2026-09-26`, HEAD `63684c4` at time of gate (`aa9b7e8` after this gate adds the
missing Security pass), diffed against `main` three-dot (`git diff main...63684c4`), per the task's
own instruction — both sides merged `main` separately during development.

## Gap found and closed before this gate could pass

**No Security pass had run on this feature at all** — `plans/sortie-2026-09-26-fixes/` had no
`security-plan-review.md` or `security-review.md`, and no Security commit appears anywhere in
`git log 5e78ea3..63684c4`. Root `CLAUDE.md`'s "Agents" section states Security runs once per whole
feature, immediately before DoD (enabled 2026-09-24, replacing the earlier blanket exemption, which
had a stated end condition this project has since crossed — a live 5 Hz DCS I/O pipeline, a LAN HTTP
surface, inbound speech capture). This branch reached DoD without it. Dispatched Security (Mode 2,
deep analysis, isolated worktree) before proceeding; it returned APPROVED — NO REQUIRED FIXES
(`plans/sortie-2026-09-26-fixes/security-review.md`, cherry-picked as `aa9b7e8`). No dependency
changes, no new external-facing surface, the five new per-contact/per-look fields follow the
codebase's own pre-existing accepted growth-bound pattern (contacts are never pruned, so any
per-contact map already grows for one sortie's worth — not a new exhaustion class), and the
observability gate closes a disclosure-shaped gap rather than opening one (confirmed the gate never
reaches the query/answer path). This gap is process debt worth naming to the user, not a defect in
this feature's code.

## Code Quality

- [x] `body-layer` is the only touched subproject (confirmed by `git diff main...63684c4 --stat`
  against every `pyproject.toml` in the repo — no changes anywhere else; plan/decisions/review/
  memory files are the only non-`body-layer` diff).
- [x] `ruff format --check src tests` — 111 files already formatted, pass (re-run independently).
- [x] `ruff check src tests` — all checks passed (re-run independently).
- [x] `mypy src` (from `cd body-layer`, the CWD-only config-discovery requirement) — Success: no
  issues found in 52 source files (re-run independently).
- [x] `pytest tests -q` — **1303 passed, 4 xfailed** (re-run independently; matches both the
  implementer's and reviewer's reported counts exactly; `main` baseline was 1292/4 per
  `diagnosis.md`, authored before implementation began — 11 new tests, no regressions).
- [x] No unhandled errors/panics: Security's pass confirmed the new command-lowering branch in
  `logger.py` sits inside the pre-existing broad per-poll `try/except Exception: logger.exception;
  continue`, and `_callout_may_speak` is pure computation over already-non-`None` fields.
- [x] No debug output: `git diff main...63684c4 -- body-layer/src | grep -E '^\+' | grep -iE
  "TODO|FIXME|print\(|pdb|debugger|XXX"` — no hits.
- [x] No leftover debug/TODO code introduced by this feature.

## Scope & Correctness

- [x] Implementation matches `plans/sortie-2026-09-26-fixes/plan.md` and `decisions.md`, verified by
  reading every changed line of `contacts.py`, `optic_policy.py`, `crew_console.py`, `logger.py`,
  `decay.py` directly against the plan's own stage-by-stage description — not by trusting
  `implementation.md`'s account. The one deliberate plan deviation (`last_observable_sim` in place
  of the plan's literal `unobservable_since_sim` formula) is correct: confirmed by reading
  Reviewer's own empirical check (patching the rejected formula back in, watching the defect test
  fail) rather than re-deriving it myself, since the review already did the discriminating
  experiment and documented it reproducibly.
- [x] No unplanned scope added: `git diff main...63684c4 -- plans/binocular-optic/plan.md` is empty
  (confirmed directly); no `choose_look` line is added or changed anywhere in the diff (confirmed
  by grepping the diff's `+`/`-` lines specifically, not just the presence of the string
  `choose_look` in unchanged context lines, which also appears).
- [x] No CLAUDE.md invariants violated: no-omniscience is exactly what Fix A closes a gap in — the
  gate sits only on the spontaneous path (`ContactStore.tick`/`route_event`), confirmed by grep to
  never reach `describe_contact`/`render_contact_report`, which is Decision 3's explicit
  requirement (a future pull-only briefing-answer path must not be foreclosed).
- [x] All new/modified files staged and committed — `git status --porcelain` was clean at every
  point I checked (before and after the Security cherry-pick).

## Testing

- [x] Core logic covered: each of the three fixes has a purpose-built test exercising the exact
  defect it closes (masked-since-founding contact, interrupted-look retry, unrecognised-utterance
  interrupt, `follow`-already-on-target), plus the Decision-4.2-required unwatched-`CONTACT_
  MOTION_CHANGED` case and the B2 time-based-retry companion. Read the new tests directly, not just
  their names.
- [x] Meaningful, not decorative: `test_time_based_reeligibility_fires_for_a_naturally_completed_
  look_on_a_stalled_contact` (read in full) actually drives the look to `MAX_LOOK_S`, commits the
  attempt, then advances past `OPTIC_RETRY_INTERVAL_S` and asserts a second look is chosen — a real
  behavioural assertion, not a shape check.
- [x] No existing tests broken: 1303/4 matches the pre-implementation baseline plus 11 new tests,
  zero regressions. Two pre-existing tests were *updated* (not weakened) to check `pending_
  attempted_at_range_m` in place of `attempted_at_range_m` — a direct, mechanical consequence of the
  committed/pending split the plan itself specifies, confirmed by reading each test's docstring-
  stated invariant is still what's asserted.

## Documentation

- [x] Reviewer's one required fix (the `decay.py` docstring naming the never-built
  `unobservable_since_sim` field) is applied in `63684c4` and is correct: read the full corrected
  docstring directly — it names `last_observable_sim`, states the direction is deliberate and why,
  and records that the reviewer confirmed the rejected formula empirically. Checked for the same
  stale claim in sibling files per the reviewer's own memory note (doc drift hid in a sibling file
  once before): grepped `unobservable_since_sim` project-wide — the only non-historical hit is the
  corrected docstring's own explanatory prose (which *names* the superseded field on purpose, as
  history); `contacts.py`'s `_callout_may_speak`/`Contact.last_observable_sim` docstrings already
  described the real field correctly and needed no change.
- [x] Non-obvious behaviour explained: every new field/function carries a docstring citing the plan
  stage and decision it implements; `implementation.md`'s "Notable Discoveries" section records the
  plan-formula defect and the two pre-existing-test updates.

## Security

- [x] `security-review.md` exists and is APPROVED (dispatched by this gate, see "Gap found" above;
  no `security-plan-review.md` is needed — this branch is closer to a debugger→architect-lite
  sequence than a fresh feature plan a Security plan-review would normally gate, and root
  `CLAUDE.md`'s cadence names one pass "immediately before DoD" per whole feature, which this
  satisfies).

## Follow-on recording (the item most likely to be silently dropped)

Three things this feature deliberately deferred, checked against durable records:

1. **Sector coverage (Decision 2a)** — was **not recorded anywhere** before this gate. Added to
   `body-layer/ROADMAP.md` Backlog: needs its own `/explore` pass before Architect, proposed
   location `plans/optic-sector-coverage/plan.md`.
2. **More frequent glances at a watched contact (Decision 1's third point, assigned to
   attention-grabbing behaviour)** — was **not recorded anywhere**. Added to `body-layer/ROADMAP.md`
   Backlog, cross-referencing that it is what should eventually let `CALLOUT_OBSERVABILITY_GRACE_S`
   matter less.
3. **Decision 3's pull-only briefing-derived answering** — was **not recorded anywhere** as a
   backlog item (only implicit in `decisions.md`/`plan.md`, which are historical planning
   documents, not a forward-looking list). Added to `body-layer/ROADMAP.md` Backlog, naming its
   three prerequisites (Mission Interpreter output reaching body-layer, free-text questions,
   world-model terrain phrasing).
4. **The confirm-band dead end (finding 3 of the original sortie)** — already tracked, `todo/
   todo.md`'s "Sortie 2026-09-26" entry, unchanged, still open. No action needed.

`todo/todo.md`'s findings 1 and 2 changed from `[ ]` to `[~]` with a note that the fix has merged
and DoD-passed on fixtures but is awaiting the live sortie — not `[x]`, since the live-acceptance
rule (root `CLAUDE.md`/`body-layer/ROADMAP.md`) is explicit that a merge does not itself close a
finding whose live test is pending, only deferred-by-plan items close without flying.

## Milestone-completion question (root CLAUDE.md)

Does this change what the next milestone should be, or invalidate a downstream assumption? **No
change to the next milestone** (brain-layer work continues to be the stated bottleneck). One
specific note worth keeping: Fix A's 10s grace window is explicitly a stand-in for attention-
grabbing behaviour that does not exist yet (Decision 1's own framing) — its correctness as a value
depends on that behaviour eventually existing to make the window "rarely matter," so a future
attention-grabbing milestone should treat this constant as something to *revisit*, not something it
inherits as settled.

## Verdict

**DoD: PASSED**, contingent on the live acceptance card below and the user's own testing.
