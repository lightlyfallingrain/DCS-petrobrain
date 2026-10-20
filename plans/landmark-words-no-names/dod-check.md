# DoD Check: landmark-words-no-names

Checked at tip `34b9f659f3e6a3bb17ea2f91273a58454e5e5dff` (`feature/landmark-words-no-names`),
plus one retroactive gate-closure commit layered on top during this check (see "Security plan
review" below). **This verdict is scoped to that combined state, not to the branch generally** —
if the branch moves further, re-check.

Touched subprojects, from the diff vs `main` (merge-base `431b5598`): **body-layer**, **world-model**.
(The diff also carries `docs/open-flight-tests-2026-10-20`'s inherited docs commits, per the
dispatch note — not this feature's scope, not re-reviewed here.)

## Code Quality

| Check | Subproject | Status | Notes |
|---|---|---|---|
| `ruff format --check src tests` | body-layer | PASS | 155 files already formatted |
| `ruff check src tests` | body-layer | PASS | all checks passed |
| `mypy src` (from `body-layer/`) | body-layer | PASS | 68 source files, no issues |
| `pytest tests -q` | body-layer | PASS | 2257 passed, 4 xfailed, zero unexplained failures. 2 failures on first run (`test_logger.py::test_connection_reporter_says_disconnected_once_then_connected_once`, `...reannounces_after_a_recovery_and_a_second_drop`) — both are the documented timing-flake class; reran `-k test_connection_reporter` in isolation: 3 passed, 0 failed. |
| `ruff format --check src tests` | world-model | PASS | 118 files already formatted |
| `ruff check src tests` | world-model | PASS | all checks passed |
| `mypy src` (from `world-model/`) | world-model | PASS | 72 source files, no issues |
| `pytest tests -q` | world-model | PASS | 568 passed, 3 skipped, 0 failed — clean on first run, no known flakes hit |

**Debug output / TODO-FIXME-HACK-XXX / bare-except markers**: none in any file this feature
touches (`body-layer/src/belief/enrichment.py`, `body-layer/src/belief/speech.py`,
`world-model/src/query/describe.py`) — checked directly, not via a repo-wide scan.

**File size (>400 lines):** `body-layer/src/belief/speech.py` (3358 lines), `enrichment.py` (892
lines) and `world-model/src/query/describe.py` (814 lines) are all over the 400-line guideline —
**pre-existing condition, not introduced by this feature.** This diff adds a net +181/-36 lines
across the three files (mostly `speech.py`, +149/-36 net), nowhere close to pushing a
previously-compliant file over the limit. Splitting these files is a separate, much larger
refactor outside this plan's scope; not blocking.

**Staging / agent-memory path:** `git status --porcelain` is clean at every checkpoint in this
check (after each file written, before committing). The three agent-memory files this feature's
earlier stages wrote are all correctly rooted at `.claude/agent-memory/<role>/...`, not nested
under a subproject.

## Scope & Correctness

- **Implementation matches `plans/landmark-words-no-names/plan.md`.** Read the actual diff against
  the plan's Stage 1/Stage 2 steps line by line: `SettlementInfo.area_m2` addition, the new
  `_settlement_size_word`/`BUILT_UP_VILLAGE_MAX_AREA_M2` tunable, the `feature_id` middle-segment
  encoding for `settlement`/`inside_settlement`/`water`, `_landmark_speech_text` replacing
  `_round_enrichment_fragment` at both call sites — all match as planned, including the
  road-needs-no-change and coastline-generalisation calls the plan itself flagged.
- **Matches the settled sortie spec** (`docs/acceptance/2026-10-20-sortie-feedback.md`, F7 and "F7
  — settled"): village/town only (city folds to town), distance dropped not rounded, mission
  memory unaffected, generalised to every landmark kind speech renders.
- **No unplanned scope added.** The one generalisation beyond an explicit user quote (dropping
  coastline's distance figure) is flagged in the plan's own "Risks & Unknowns" as a deliberate,
  disclosed consistency choice, not silent scope creep, and Security's deep analysis agreed it's
  a product call, not a security one.
- **No CLAUDE.md invariants violated.** No-omniscience: `SemanticFact.text`/`confidence`/
  `provenance` unchanged for every kind — this is wording-only, never a knowledge-source change.
  World-model-authoritative: the new `area_m2` field is read-only, additive, sourced from the
  existing offline build pipeline. Single-player scope: untouched.
- **All new files staged** — confirmed via `git status --porcelain` (clean) at every commit in
  this check.

## Security

| File | Status |
|---|---|
| `plans/landmark-words-no-names/security-plan-review.md` | **Was missing at DoD start — see below.** Now present, APPROVED. |
| `plans/landmark-words-no-names/security-review.md` | PASS — APPROVED |

**Gap found and closed during this check.** The role sequence for this feature was Architect →
Implementer → Reviewer → Performance Reviewer → Security (deep analysis) → Reviewer (re-review).
Root `CLAUDE.md`'s "New feature"/"Refactor" sequences call for a Security **plan** review
immediately after Architect and before Implementer; it was never invoked, and no user override is
on record. This is not covered by the "once per batch, immediately before DoD" cadence exemption —
that governs the deep-analysis pass's frequency, not whether a plan-stage review happens at all for
a feature that went through Architect. There is direct precedent in this repo for exactly this
situation (`plans/emitter-visibility/security-plan-review.md`, written retroactively after the same
gap).

Dispatched Security (isolated worktree) to write the missing gate retroactively, following that
precedent's format: reconstruct the plan-stage review against `plan.md` as originally written, and
separately judge whether running on time would have changed anything now that the deep-analysis
pass already exists. Result: `plans/landmark-words-no-names/security-plan-review.md`, **APPROVED**
— clean dependency posture (only new import anywhere in the diff is `tuning`, this project's own
existing loader), `TOOL_SET`/mission-memory confirmed untouched against the actual diff (not the
plan's claim), no-omniscience not implicated, tunable bounds sane. Concludes running it on time
would not have changed the deep-analysis pass's conclusions — the one implementation-level finding
(`area_m2`'s untyped-tag `TypeError` path) is by nature something only the written code could
surface, and it was already correctly dispositioned there as low-severity, not filed.

Harvested onto this check's working commit by cherry-pick (the agent's own branch ref was stale —
pointed at `origin/main`, not its detached-HEAD commit — so fast-forward wasn't available; verified
the commit itself, `0d9f1d7b`, was a clean single-file child of the feature tip before picking it).
Agent's worktree removed, its branch deleted.

## Testing

- **Core logic covered.** `_settlement_size_word`: 8 unit tests, every branch (village/town/
  city-folds/built_up below-at-above threshold/no-area default/unrecognised-subtype). 
  `_strip_trailing_distance`: 2. `_landmark_speech_text`: 9, one per `feature_id` kind plus the
  no-`feature_id` fallback.
- **Tests are meaningful, not decorative — verified by mutation, twice over** (implementer's own
  pass, then independently re-verified by Reviewer's re-review): three gaps the first review found
  (water and `inside_settlement` `feature_id` wiring, `render_engage_readback`'s semantic branch)
  had only hand-built-fixture tests that stayed green under a producer-side mutation. All three
  closed with end-to-end tests derived from the real `semantic_facts_for` producer; each
  independently re-mutated in the re-review and confirmed to fail for the stated reason, then
  reverted with a `shasum` check against the pre-mutation file.
- **No existing tests broken** — the two call-site updates required touching two pre-existing
  tests that asserted a live settlement name (`"Jableh"`) in rendered speech; both were updated to
  assert the new generic wording and the name's absence (not deleted, not weakened). Five separate
  `_FakeInfo`-shaped test fixtures across `test_enrichment.py`/`test_speech.py`/`test_console.py`/
  `test_tools.py`/`test_crew_console.py` needed the new `area_m2` field added (caught by running the
  full suite, not by the plan's own test-impact list, which named only one of the five) — captured
  as both an implementer agent-memory entry and a `notes/` harvest (below), since this is a
  repeatable hazard, not a one-off miss.

## Documentation

- **Reviewer findings addressed.** All three Required Fixes from `review.md`'s first pass were
  independently re-verified in the re-review (mutation + revert + hash-check each), verdict
  **APPROVED**, not just re-read from the implementer's account.
- **Non-obvious behaviour explained.** `body-layer/docs/STRUCTURE.md`'s `enrichment.py` and
  `speech.py` entries updated in place (not left describing the deleted
  `_round_enrichment_fragment`), explaining the `feature_id` middle-segment encoding and why
  `belief.console`/mission memory are unaffected.

## Milestone-completion question

Does this change what the next milestone should be, or invalidate a downstream assumption? **No** —
this is a narrow, speech-rendering-only change with no effect on belief state, contact lifecycle,
`TOOL_SET`, or mission memory; the plan's own "Second-order effect" section, Security's deep
analysis, and Security's retroactive plan review all independently reach the same conclusion. The
one live boundary question this feature deliberately leaves open (what happens if the brain starts
reading tool results aloud as free text) is explicitly out of scope, same framing as the plan.

## Acceptance boundary — what these fixtures structurally cannot reach

Every check above is fixture- or mutation-verified; none of it can tell whether the *wording*
actually lands right in the cockpit. Specifically out of reach of anything run in this check:

- Whether "near a village"/"in the town" reads naturally at TTS cadence against real terrain, or
  whether it feels clipped/wrong in a way no transcript would show.
- Whether dropping the distance figure entirely (rather than rounding it, the pre-existing
  behaviour) loses information a pilot actually used — the user asked to drop it, but only a flight
  confirms the result is still useful, not just quieter.
- Whether the built_up/no-subtype village-vs-town size cutoff (`BUILT_UP_VILLAGE_MAX_AREA_M2`,
  1 km², explicitly `status="judgement"`, untuned) picks the right word against real OSM-derived
  polygons in Syria, as opposed to the synthetic fixtures this suite uses.

This is why the entry is `#needs-flight` (`body-layer/ROADMAP/BL-W40.md`) rather than closed. There
is no mechanical "unblock command" to run for this one — the clearing condition is a live sortie
and a judgement call only the user can make, not a script. Merge does not wait on it, per root
`CLAUDE.md`'s live-acceptance policy.

## Verdict

**PASS.** All mechanical checks green in both touched subprojects, Reviewer's required fixes
addressed and independently re-verified, both Security gates now present and APPROVED (the plan
review closed during this check, not before it), no invariant violations, no unplanned scope,
working tree clean. **Live acceptance deferred to the next flight — `#needs-flight`, tracked on
`body-layer/ROADMAP/BL-W40.md`, not a blocker on this merge decision.**

Per this dispatch's instructions: **not merged.** Reporting back to the orchestrator rather than
proceeding to merge/push.
