# DoD Check — BL-B112 (motion-aware contact certainty)

**Branch:** `feature/motion-aware-certainty`
**Verdict scoped to tip:** `248e3d4e9f4efe3e5dab55f93646613cfe3dc652` (fast-forwarded cleanly from
`main` `fe93aa0a`, which is an ancestor; tree clean before and after). **If the branch moves past
this sha, this verdict is stale and must be re-run.**

## Code Quality

- `ruff format --check src tests` — PASS (198 files already formatted)
- `ruff check src tests` — PASS (all checks)
- `cd body-layer && .venv/bin/mypy src` — PASS (0 errors, 81 source files)
- `pytest tests -q` — PASS: **3173 passed, 4 xfailed** (274.03s) — matches the number stated in the
  dispatch prompt and in `review.md` exactly
- `tools/generate_defaults.py` (check mode) — PASS (`config/defaults.toml` up to date)
- No debug output, `print(`, `pdb`/`breakpoint()`, or TODO/FIXME introduced — grepped the diff
  `fe93aa0a..248e3d4e` over `body-layer/src`, none found
- Single subproject touched (body-layer only) — confirmed via `git diff --name-only`, no other
  subproject in the diff

## Scope & Correctness

- Implementation matches `plans/motion-aware-certainty/plan.md` — confirmed independently by
  `review.md`'s stage-by-stage diff read (full read, not spot-check) and by my own read of
  `implementation.md`'s Files Changed / Deviations sections. Two explicitly plan-authorized
  departures: `fold_motion`'s founding-case reversal (user-directed, Q2) and Buk/SA-11 left out
  (with the plan-check's wrong-precedent forward-note correction already landed before Implementer
  started).
- No unplanned scope added silently — the three test files outside the plan's named Affected
  Modules (`test_mock_flight_chain.py`, `test_crew_console.py`, `test_body.py`) were genuinely
  necessary mechanical/behavioural follow-ons, confirmed by Reviewer reading each diff, not just
  trusting the Implementer's claim.
- No CLAUDE.md invariants violated — `mission_memory` import-direction invariant re-verified by
  grep (Reviewer); no-omniscience boundary untouched by this plan; tuning constant added
  (`LAST_I_SAW_GROWTH_THRESHOLD_M`) through `tuning.py` with `lo`/`hi`/`status`, per the standard
  mechanism, and appears correctly in the rendered `defaults.toml` (checked the rendering, not just
  the `#:` comment, per that section's own stated trap).
- All new/modified files staged — fast-forward merge brought everything in as one clean commit set;
  `git status --porcelain` clean before my own edits (see below).

## Testing

- Core logic covered: `test_belief_motion.py`, `test_decay.py`, `test_mission_memory_admission.py`,
  `test_mission_memory_entries.py` all gained real new tests for the growth-based boundary, the
  founding-case motion reversal, and the lost-contact kneeboard write. Not decorative — e.g.
  `test_decay.py::test_immobile_contact_still_goes_lost_at_the_lost_threshold` is exactly the test
  that caught the test-card's own wrong expectation (see Required Fix below).
- No existing tests broken — 3173 passed matches pre-implementation baseline class count plus the
  new ones; 4 xfailed are the same pre-existing xfails named in both the Implementer's and
  Reviewer's reports.

## Documentation

- Reviewer findings addressed — one Required Fix (`test-card.md` Case 1's wrong "still in working
  memory past 2 minutes" expectation, contradicting the plan's own kept-unchanged `LOST_THRESHOLD_S`
  rule and a passing test) was fixed in commit `3c055ea7`, already on this tip. Confirmed by reading
  the current `test-card.md` Case 1 text — correctly split into (a) within ~2 min / (b) past ~2 min.
  Two Optional Refinements noted, not blocking (surfaced below).
- Non-obvious behaviour explained: `implementation.md`'s "Notable Discoveries" covers the
  scope/hybrid-only-contacts-never-get-"estimated" consequence and the `on_surface` gate's effect on
  growth rate; both are genuinely non-obvious cross-module interactions, not derivable from a diff
  alone.

## Security

- `plans/motion-aware-certainty/security.md` — **APPROVED**. No dependency change (confirmed empty
  `pyproject.toml` diff). No I/O, injection, or external-input surface in the touched code
  (pure in-memory arithmetic over contact fields).

## Performance

- `plans/motion-aware-certainty/performance.md` — **APPROVED**. Added work per call is a
  `functools.cache`d dict lookup plus two attribute checks and a multiply — still O(1), no
  allocation, no I/O, on a poll loop with no hard real-time budget yet.

## A defect found by running a card command, not by reading it

**`test-card.md` Case 5 instructed running `triage.py --mission-memory <path>` after landing.**
`triage.py --help`, run before trusting the card, shows no such flag exists — the script's own
header comments explicitly note mission-memory is not one of the logs it reduces (it covers
belief/detection-trace/speech/slew/expected-area, not mission-memory). This would have failed on
the user's first attempt. **Fixed in this worktree**: replaced the command with a direct
`python3 -c "..."` JSONL read, tested against a synthetic fixture matching
`mission_memory/entries.py`'s real `encode_entry` output shape (`kind`/`t_sim`/`payload` keys) to
confirm it actually prints the right fields before committing it to the card.

This is the same class of defect this role's own instructions name repeatedly ("five acceptance
cards... never executed") — recorded as `.claude/agent-memory/dod/feedback_test_card_tool_flag_must_exist.md`,
a distinct sub-case (nonexistent flag, caught by `--help`, not by running the full command against
real data).

## Acceptance boundary — what these fixtures structurally cannot reach

The unit tests prove the growth-distance math and the lost-contact write in isolation. They
**cannot** prove: (1) that a real naked-eye "watch for 5s" motion percept actually arrives at the
rate a live sortie produces it (Case 3's single-glance-vs-watch distinction is only exercised by
fixture-timed percepts, never a real poll cadence against a real DCS clock); (2) that the spoken
wording ("last I saw" vs stated as fact) is what a pilot actually hears mid-flight rather than what
`render_report_summary` returns in a test; (3) the Kub/SA-6 widened-hedge case at a real range in a
scene with other traffic competing for glass budget — only a synthetic `Contact` was measured
(`implementation.md`'s acceptance table). A fixture pass is not a flight pass for any of these
three.

## Milestone completion question

**Does BL-B112 change what the next milestone should be, or invalidate a downstream assumption?**
Yes, in the direction already anticipated and acted on: the goal check's own Q5 (recorded in
`explore-notes.md`) split the original BL-B112 scope in two, and the user agreed. BL-B112 (this
branch) only writes a lost contact's last-known place/time to mission memory; it does **not** make
Petrovich *read* mission memory back when answering a live question. The newly created
`body-layer/ROADMAP/BL-B115.md` ("Kneeboard read-back") is the split-out successor, explicitly
depending on BL-B112's lost-contact-noting behaviour and reversing BL-8's settled "write-only in
flight" decision. Until BL-B115 lands, a fixed site still drops out of live in-cockpit answers
~2 minutes after last seen — the test card's own "A known gap, not a regression" section says so,
and it is the correct, intended state of the world right now, not an oversight in this branch.

## Verdict

**PASSED**, scoped to tip `248e3d4e9f4efe3e5dab55f93646613cfe3dc652`.

Acceptance testing: **PENDING (live)** — `#needs-flight` on `body-layer/ROADMAP/BL-B112.md`
(already tagged, in-progress status to be marked done by the merge step). Test card published as
an artifact: https://claude.ai/artifact/6nzbkGbm7DgubzaRz6z5gr (source:
`plans/motion-aware-certainty/test-card.md`, fixed in this pass, see above), branch to fly is
`main` after merge.

Per the 2026-10-26 standing direction, live acceptance does not gate this merge.
