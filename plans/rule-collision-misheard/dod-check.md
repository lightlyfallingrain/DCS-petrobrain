# Definition of Done: fix/rule-collision-misheard

**Scoped to tip `7cafd792597563948151f56124a133a6d54cbc7b`** — the branch's own stated tip, fast-forwarded
into this worktree cleanly from `36d7e63c` (`origin/HEAD`/`main` at dispatch time). HEAD was a strict
ancestor of `7cafd792` and the tree was clean, so `git merge --ff-only 7cafd792` applied with no
conflict. If the branch moves again, this verdict is stale.

## What it is

Bug fix (user-approved 2026-11-19): `audio-adapter`'s `compile_rules` rejected `cbtm_align`/
`cbtm_break` (from `body-layer/config/rules/flight.lua`) because the rule x legacy collision check
disabled a rule whenever its perturbed sample confidently resolved to an unrelated legacy command,
even though `command_matcher`'s own rule/legacy merge already picks the higher-`match_ratio` branch
regardless of registry membership — so the rule's disablement changed nothing at runtime except
losing correct recognition of the rule's own clean wording. "Align" and "break turn left/right" were
silently inactive in flight before this fix.

`763d4288` narrows `_is_genuine_collision`'s confident-loss clause to rule x rule only (new
keyword-only `confident_loss_disables` parameter, `True` for rule x rule, `False` for rule x
legacy); `9b2d0ccc` records the 2026-11-19 narrowing in `plans/speech-rules/plan.md` D9. No
plan.md of its own — diagnosed in the main loop, the commit message is the account, per the
dispatch.

## Code Quality

- **Full audio-adapter suite** (`/Users/sg/Code/DCS-petrobrain/audio-adapter/.venv/bin/pytest
  audio-adapter/tests -q -n auto`, run from this worktree's `audio-adapter/` with the absolute
  venv path, no venv created): **566 passed, 2 skipped.** Matches the Reviewer's own full-suite run
  exactly.
- `ruff format --check audio-adapter/src audio-adapter/tests`: 36 files already formatted. PASS.
- `ruff check audio-adapter/src audio-adapter/tests`: All checks passed. PASS.
- `cd audio-adapter && .venv/bin/mypy src` (absolute venv): Success, no issues found in 17 source
  files. PASS.
- No unhandled errors/panics introduced — the diff is a pure boolean-parameter threading change in
  `_is_genuine_collision`/`_collides_with_legacy`, no new I/O, no new exception paths.
- No debug output, no leftover TODOs in the diff (`git diff 36d7e63c..763d4288 --
  audio-adapter/src/rule_patterns.py` reviewed directly: docstring updates plus the one-line
  `return True` -> `return confident_loss_disables` change and the new kwarg).
- **Only audio-adapter is touched** by this fix's code/test diff (confirmed via
  `git diff --name-only 36d7e63c..763d4288`: `rule_patterns.py`,
  `tests/test_rule_patterns.py`, `tests/test_rules_api.py`). The plan/memory/review files touch
  `plans/speech-rules/plan.md` and two agent-memory files, not a second subproject's own code —
  no other subproject's commands are owed a run here.

## Scope & Correctness

- No `plans/rule-collision-misheard/plan.md` exists by design (bug fix, no architect plan; stated
  explicitly in the dispatch). `.claude/scripts/accepted-items-ledger.sh plans/rule-collision-misheard`
  returns nothing (exit 0) — consistent with no plan.md to carry `U<n>` decisions; nothing to check
  against the ledger for this fix.
- Matches the stated intent exactly: `review.md` independently re-derived and confirmed the claim
  (`command_matcher.match_transcript`'s merge picks by ratio regardless of rule existence) rather
  than trusting it, and confirmed the two real patterns (`cbtm_align`/`cbtm_break`) are exact copies
  of the shipped `flight.lua` rules, not synthetic examples.
- No unplanned scope: rule x rule behaviour (`_rules_collide`) is unchanged (`confident_loss_disables`
  defaults `True`, same as before); only the rule x legacy pass changed, matching the user-approved
  narrowing.
- No CLAUDE.md invariant violated — this is internal to audio-adapter's own collision-gating logic,
  no cross-subproject seam touched, no omniscience/provenance concern (audio-adapter has no belief
  state).
- All files already staged/committed as part of the branch's own commits (`763d4288`, `9b2d0ccc`,
  `a9b26ffc`, `7cafd792`) — `git status --porcelain` is clean after the ff-merge, before this DoD
  pass's own additions.

## Testing

- Core logic covered: the renamed unit test correctly flips its assertion to the new behaviour; a
  new unit test covers the exact-tie case explicitly; a new `test_rules_api.py` test exercises the
  fix end-to-end through the real `PUT /rules` handler and the real legacy pipeline, anchored to the
  two motivating rules. Not decorative — each test asserts the actual boundary condition
  (`confident_loss_disables` True/False, exact tie vs. confident loss) rather than a smoke check.
- No existing test broken: full suite 566 passed / 2 skipped, same skip count as before the fix
  (per review.md).

## Documentation

- Reviewer findings addressed: `review.md` Required Fixes is **None**; both Optional Refinements
  (plan.md D9 staleness note — already resolved by `9b2d0ccc`; a missing DEBUG/INFO log on the
  now-silent confident-loss-but-kept path) are explicitly optional and not required for this fix's
  own scope.
- Accepted-items ledger: no plan.md, so no `U<n>` lines to account for — nothing unmentioned.
- Non-obvious behaviour explained: both touched docstrings (`_is_genuine_collision`,
  `_collides_with_legacy`) were updated in the same commit to state the new split precisely, dated,
  with the concrete measured cases named. `plans/speech-rules/plan.md` D9 carries the same account
  at the plan level (`9b2d0ccc`). A notes/ entry was added (see Knowledge Harvest below) for the
  general lesson, since it recurs as a class of mistake worth flagging early next time.

## Security

- `plans/rule-collision-misheard/security-review.md` exists, **APPROVED**. No findings required
  action. Independently re-verified the same runtime-merge claim the Reviewer made (did not just
  trust it), and reasoned through the worst case of a hostile `PUT /rules` push under the loosened
  check — bounded by what `compile_rules`/`match_transcript` can already do with an accepted rule,
  no new "confident wrong command" primitive, no change to `PUT /rules`'s pre-existing
  (accepted-elsewhere) lack of authentication.

## Milestone-completion question

Does this fix change what the next milestone should be, or invalidate a downstream assumption? No
— it restores two already-shipped CBTM voice commands (`cbtm_align`/`cbtm_break`, part of BL-16's
Mode 2 Stages P3+P4 and Mode 1 batch) to the behaviour those batches' own plans and flight-test
cards already assumed; it does not add scope, change an interface, or alter anything downstream
milestones (mode-1 hover, etc.) depend on.

## Acceptance boundary (stated up front, not just tested)

**What this fix's fixtures structurally cannot reach:** the new `test_rules_api.py` test proves the
rule is *accepted* by `compile_rules` and *wins* the real `command_matcher` merge against the real
`_legacy_probe`, on the exact clean wording. It cannot prove that a live Whisper transcription of a
pilot actually saying "align" or "break turn left" in the cockpit, under real cockpit noise and
intercom gating, produces the same transcript text the fixture hands the matcher — that is
exactly the class of gap this role's own worked example (`Scan` driving the wrong subsystem) names:
a fixture proves the code does what it says against the text it is given, never that real speech
produces that text. This is why the item below is `#needs-flight`, not closed.

## Live acceptance: PENDING (live)

Not run now — correctly, per root `CLAUDE.md` Workflow ("never block a merge on live acceptance").
Recorded as `#needs-flight` on `body-layer/ROADMAP/BL-16.md`, folded into the existing P3+P4
`#needs-flight` entry (not a new one — the P3+P4 flight-test card's own "align"/"break turn
left/right" steps now also verify the fix, one sortie clears both). No new test card published:
the existing P3+P4 card (`https://claude.ai/artifact/VVw5ACyJd4VSSbRCqssome`,
`docs/acceptance/2026-11-19-bl16-p3p4-test.md`) already names these exact phrases as its steps 1-4
and is unflown — adding a second card for the same sortie and the same phrases would split one
flight's debt across two artifacts for no benefit.

**Unblock condition check (per this role's own retro finding):** the `#needs-flight` tag's own
clearing condition is "fly it" — there is no command, script or probe to run in its place; a live
DCS sortie is not something this role can execute. Nothing else in this fix carries a deferred item
with a stated, executable unblock condition (Security's "Not filed, intentionally" items are
standing accepted design decisions, not deferrals with a clearing command).

## Knowledge Harvest

- Added one bullet to `notes/voice-recognition-and-command-matching.md`: a load-time collision
  check can disable a rule for a reason that changes nothing at runtime, if the runtime merge
  already resolves ties independently of the registry — check what the gated outcome actually
  changes at runtime before tightening a defensive check "to be safe." Not a duplicate of the
  existing entries in that file (checked by reading it in full; the existing entries cover fuzzy-
  tolerance boundaries, digit homophones, and the five rule x rule/legacy collisions found at
  Stage 4 — none states this specific "the check changed nothing operationally" lesson).
- `python3 .claude/scripts/memory-search.py rule collision legacy confident loss` found exactly the
  Reviewer's and Security's own two memory files for this feature (both first occurrences, written
  during this feature's own review/security passes) — no 2+-occurrence recurring-fix category to
  flag as process debt.

## Roadmap

- `body-layer/ROADMAP/BL-16.md` (resolved via `.claude/scripts/roadmap-source.sh`, a real entry
  file, not the four-line `ROADMAP.md` pointer) updated: a new paragraph under the Mode 2 Stages
  P3+P4 entry records this fix, names the commits, and folds its live-acceptance debt into that
  entry's existing `#needs-flight` tag rather than creating a duplicate one.
- No BL-17/speech-rules ROADMAP entry needed a parallel update: `plans/speech-rules/plan.md` D9
  already carries the narrowing (commit `9b2d0ccc`, pre-existing on the branch), and BL-17 itself
  is `[>]` deferred/parked — this fix does not reopen or change that status.

## Verdict: PASSED

Commit `7cafd792597563948151f56124a133a6d54cbc7b` (the branch's own tip, ff-merged into this
worktree) plus this DoD pass's own commit (roadmap entry, notes/ entry, this report) are the full
account. Merge trigger per root `CLAUDE.md` Workflow: this PASSED report is what the main loop acts
on.
