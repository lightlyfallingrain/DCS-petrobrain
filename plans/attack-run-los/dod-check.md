# Definition of Done: attack-run-los

**Scope note (AGENTS.md rule 4).** The dispatching prompt expected tip
`ddd8eadfc791aa43534836272268fae50845478c` with a strict-ancestor merge. HEAD at dispatch was
`df0bb377` (a sibling branch, `worktree-agent-aef6363c5005e3e40`, carrying unrelated `BL-B96`
commits) — `git merge-base --is-ancestor` failed both directions; merge-base was `3eb913ba`, an
ancestor of both but neither an ancestor of the other. Tree was clean, so per protocol:
`git checkout --detach ddd8eadfc791aa43534836272268fae50845478c`. **This verdict is scoped to
`ddd8eadf`, feature branch `feature/attack-run-los`. It says nothing about `df0bb377`/
`worktree-agent-aef6363c5005e3e40` or `BL-B96`, which are a separate, unrelated line of work.**

## Code Quality

- [x] **body-layer** (`ruff format --check`, `ruff check`, `cd body-layer && mypy src`, `pytest`) —
  all run directly from this worktree against `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`
  (no local `.venv` in this worktree; used the main checkout's per the dispatching brief's
  fallback). `ruff format --check`: 1 file would be reformatted —
  `body-layer/research/2026-10-05-security-audit.md`, a markdown file with embedded code fences,
  **not touched by this diff** (`git diff 3eb913ba..ddd8eadf --name-only` confirms; last touched
  by `83843b9f`, an unrelated prior commit) — pre-existing, not a blocker. `ruff check`: all
  checks passed. `mypy src`: success, 74 source files (matches implementer's report: 84 included
  `tools/`, which `mypy src` alone does not scan — consistent, not a discrepancy). `pytest -q`:
  **2663 passed, 4 xfailed** — matches implementer's report exactly (was 2650/4 before this
  feature).
- [x] **audio-adapter** (same four commands) — `ruff format --check`: 71 files already formatted.
  `ruff check`: all checks passed. `mypy src`: success, 16 source files. `pytest -q`: **349
  passed, 2 skipped** — matches implementer's report exactly.
- [x] `git diff 3eb913ba..ddd8eadf --name-only` confirms only `body-layer`, `audio-adapter`,
  `docs`, `plans`, and one `.claude/agent-memory/implementer/` file touched — no other subproject
  silently skipped.
- [x] No unhandled errors/panics in data paths — `query()` is pure, raises nothing new;
  `drain_where_is_it` mirrors the existing `drain_attack_run` error posture (none added).
- [x] No debug output left in committed code — grepped the diff for `print(`/`pdb`/`console.log`;
  the only hits are calls to `CrewConsole._print`, the module's own pre-existing speech/text output
  funnel, not debug output.
- [x] No TODO/FIXME introduced by this feature — grepped the diff, none.

## Scope & Correctness

- [x] Implementation matches `plans/attack-run-los/plan.md`, including the three 2026-10-24 user
  amendments (where-is-it's "No target" vs "Unable, no attack run"; the terrain-blocked-held flag;
  voice-only command surface) — confirmed by reading `implementation.md` against the plan and
  spot-checking the corresponding code (`attack_run.py`'s `terrain_blocked_held`,
  `crew_console.py`'s `drain_where_is_it`, `vocabulary.py`'s `VOICE_ONLY_TOKENS` addition).
- [x] No unplanned scope added — the five pre-existing test updates and the one audio-adapter
  phrasing fix are both documented in `implementation.md` as consequences of the plan's own
  decisions, not silent scope creep; Reviewer's `review.md` confirms the same read and found no
  required fixes.
- [x] No CLAUDE.md invariants violated — the no-omniscience boundary (`Percept`) is untouched by
  this diff; `attack_run.py` remains one of the two sanctioned files allowed to read
  `Percept.relative_direction` (fenced by `test_attack_run.py`, unchanged); the world-model seam
  and HTTP-vs-in-process boundaries are untouched.
- [x] All new files staged — confirmed via `git status --porcelain` after staging (see below).

## Testing

- [x] Core logic covered: 12 new `test_attack_run.py` tests (F2 repro, Decision 2's hold/clear/
  reset, `query()`'s purity and per-cause rendering), 2 new `test_crew_console.py` tests (no-target/
  target-set-no-run), 2 new `test_logger.py` tests (poll-loop wiring with/without an engaged run).
- [x] Tests are meaningful, not decorative — confirmed by the plan's own two independent mutation
  reversions (the `tier != 1` keying, the `effective_cause` substitution), each breaking the
  expected tests; I did not re-run the mutations myself but cross-checked the reported failure
  counts against the specific tests named as mutation-confirmed in both `implementation.md` and
  `review.md`, which agree.
- [x] No existing tests broken — the full suites pass (2663/4 and 349/2 above); the five
  pre-existing `test_attack_run.py` tests that needed *updating* (not just extending) are each
  individually justified in `implementation.md`'s "Existing tests updated" section as the plan's
  own behaviour change making their old pinned assertions describe the bug being fixed, and
  Reviewer's independent read reached the same conclusion.

## Documentation

- [x] Reviewer findings addressed — `review.md`'s verdict is **APPROVED**, **Required Fixes: None**.
  Two Optional Refinements noted (command-map staleness, the pre-existing double-speak-on-
  transition behaviour) — both informational, not required, and both are recorded in this entry
  and/or `notes/`.
- [x] Non-obvious behaviour explained: `notes/attack-run-guidance-design-bl-14.md` corrected (the
  earlier `cause == "too_far"` keying note was itself the bug, not an instance of the general
  principle it illustrated — see "Knowledge harvest" below) and extended with the transition-text
  double-speak insight.

## Security

- [x] **Waived by user direction, 2026-10-24**, recorded verbatim in `implementation.md`: *"skip
  the security in the attack run plan, go to implement"*; *"skip perf and security on these
  fixes ... When DoD passes, merge."* No `security-plan-review.md` or `security-review.md` exists
  for this feature and none is required — this is not an oversight, it is the dispatching
  instruction, consistent with root `CLAUDE.md`'s standing exemption for this project's current
  phase.

## Verdict: PASS

Scoped to `ddd8eadfc791aa43534836272268fae50845478c` (`feature/attack-run-los`).

## Tracking

No existing BL milestone entry covered this specific fix. Minted **`BL-B97`**
(`body-layer/ROADMAP/BL-B97.md`) via `.claude/scripts/mint-id.sh BL-B` — the script reported
`BL-B96` as next-unused *from this detached history*, but `BL-B96` already exists on the sibling
`worktree-agent-aef6363c5005e3e40` line (`"audio adapter unreachable -> warn and keep trying"`,
confirmed by `git show df0bb377:body-layer/ROADMAP/BL-B96.md`) — a real collision the mint-id
script cannot see across diverged histories. Used `BL-B97` instead. Added to
`body-layer/ROADMAP/body-layer-backlog.md`'s index. **The main loop will need to reconcile this
with whatever BL-B id main actually lands on next** when it merges both lines — flagging this
explicitly rather than letting it merge silently, since the backlog index line I added (after
`BL-B95`) will conflict with `main`'s own `BL-B96` insertion at the same line.

`body-layer/ROADMAP/BL-B76.md` already carried the implementer's 2026-10-24 note describing how
this fix narrows (but does not close) its own open question — left as-is, correctly still
`#status/open`.

Marked `#status/done #needs-flight` on `BL-B97` itself.

## Knowledge harvest

Ran `/notes-harvest attack-run-los`. Two candidates from `implementation.md`'s "Notable
Discoveries," neither flagged as a duplicate by the script's keyword match, but one of them turned
out to require a **correction** to an existing note rather than a fresh addition:

- **`notes/attack-run-guidance-design-bl-14.md`** already carried a bullet (from `BL-B70`'s own
  harvest) holding up `cause == "too_far"` keying as the correct instance of "key a transition on
  resolvability, not the proximate interruption." This feature's own root cause is that exact
  keying being wrong — `cause` answers "why is there no look," `tier` answers "is there a look,"
  and the register needed the second question. Appended a dated correction in place rather than
  silently leaving the stale claim standing (the general principle survives; the field it was
  attached to does not).
- **Added**: the `_should_emit` text-equality veto firing once more on a transition because the
  transition's own wording differs from the steady-state phrase for the same cause — a second,
  distinct lesson from the existing "disjunctive suppression" bullet already in that file (that
  one is about a redundant clause; this one is about a transition's wording itself causing one
  extra tick of speech, by design, not by a suppression gap).

Nothing from `review.md`'s Required Fixes (there were none) or any other section needed harvesting.
No recurring-fix pattern against `.claude/agent-memory/dod/` to flag — this review produced zero
required fixes, so there is no fix category to compare against prior entries.

## Acceptance Testing Plan: Attack-run LOS — "eyes on" means line of sight, and "where is it?"

**Goal:** Confirm Petrovich only claims "Eyes on" when he genuinely, freshly sees the attack
target, that losing sight behind terrain is narrated honestly ("Behind the ridge, ..."), and that
the new "where is it?" voice command answers correctly in all three of its cases.

**Prerequisites**
- [ ] Type-checked and importable: `cd body-layer && .venv/bin/mypy src` (or the main checkout's
  `.venv` if this worktree has none) — already run above, clean.
- [ ] `audio-adapter` running with the updated vocabulary (`"where is it"` / `"where is target"` /
  `"where is it now"` now recognised, voice-only, no F10 equivalent).
- [ ] An attack target selected and an engaged attack run, with enough terrain nearby to produce a
  genuine 15–20 second occlusion (a ridge, hill, or similar mask) — this is sortie-dependent
  terrain, not something a fixture can stand in for.

**Test Cases** — see the published flight-check card (test case numbers match its steps 1–6):
https://claude.ai/artifact/BxG7nojsxP5tBA1YCk4Mob. Branch: `main`, once this merges (or
`feature/attack-run-los` directly before then). Mirrored in prose at
`docs/acceptance/2026-10-24-sortie-feedback.md`, F2/F3's "Flight check" section.

1. Genuine tier-1 look → "Eyes on, <o'clock>" fires once.
2. Turn away behind terrain for 15–20s+ → no further "Eyes on" while hidden; "Behind the ridge,
   <o'clock>." fires once if a fresh terrain-blocked verdict was seen.
3. Turn back to genuine re-acquisition → "Eyes on, <o'clock>" fires on the real re-look, not
   before.
4. "Where is it?" with a target set, run not engaged → speaks the standard guidance phrase, not a
   refusal.
5. "Where is it?" with no target selected → "No target."
6. "Where is it?" while the "Behind the ridge" hold is active → the held qualifier still appears
   in the answer.

**Edge Cases to Probe**
- A target that goes too-far → masked → too-far without ever actually being occluded by terrain —
  should **not** narrate a spurious "Behind the ridge" (Decision 2's hold must not latch onto
  something that never happened).
- Saying "where is it?" immediately after a genuine fresh "Eyes on" — should answer consistently
  with "Eyes on" (the sighted case), not with stale terrain-blocked wording.
- Rapid repeated "where is it?" calls — should not cause any state mutation or double-speak (the
  function is pure by construction, but this is the one thing a fixture cannot prove against real
  poll timing).

**Pass Criteria**
The feature passes if all six flight-check steps produce the expected result, no false "Eyes on"
is ever heard while the target is genuinely hidden, and no regression is audible in ordinary
too-far/masked attack-run narration elsewhere in the sortie.

**Acceptance boundary, stated plainly.** Everything verified above is fixture/unit-test-level: it
proves the code implements the decided behaviour. It cannot prove the wording lands at the right
moment in a live run, or that the purity/no-mutation guarantees hold under DCS's own poll timing
rather than the test suite's synthetic ticks. That is exactly what this flight check is for, and it
is `#needs-flight` on `BL-B97` until a real sortie clears it.
