# Review: BL-8 Mission Memory, Stages 1, 2, 3, 5

Branch `feature/bl8-mission-memory`, tip `dc3735da86206774f03350e33d535b73996a807f`
(HEAD was `24f217fc`, 44 commits behind; fast-forwarded cleanly, tree was clean).

### Review Summary

The implementation matches the plan closely and the reasoning in `implementation.md` is sound —
the closure-injection resolution of the Decision 1 / Decision 6 tension is the correct call, the
schema honestly separates believed facts from last-observed ones (`y`, `as_of_sim`), and the
append-only/strike bookkeeping is exactly as specified. Mutation-testing the two structural guards
(import-direction grep, single-construction-site grep) confirmed both are real contracts, not
decorative: injecting a `mission_memory` import into `belief/contacts.py` and a second `Entry(`
construction site each failed the corresponding test immediately, then were cleanly reverted.

The gaps found are all in test coverage for claims the implementer stated but did not exercise,
plus documentation the plan designated "Changed" that was never touched. None of them is a logic
defect in the shipped code as far as I can tell from reading it; they are coverage/documentation
debt the batch should close before DoD.

### Required Fixes

- **No test exercises `admission._seen_how`'s output on a written entry.** No test in
  `test_mission_memory_admission.py` asserts on `entry.seen` at all — not `.optic`, not
  `.range_m`, not `.confidence`. The implementer's own claim ("`range_m` is honestly `None` where
  the sighting source cannot supply it, never fabricated") is correct by reading
  `admission.py:166-179`, but it is currently unverified by the test suite: deleting the
  `range_m=None` line or hardcoding a wrong value would not fail a single test. Add an assertion
  on `entry.seen` (optic matches `sighting_spans[-1].source`, `range_m is None`, confidence/
  certainty populated) to at least one of the existing `group`/`air_defence` admission tests.

- **No test exercises `dcs_to_wgs84` on a registered theatre, or the `ValueError` catch for an
  unregistered one, anywhere in the mission-memory suite.** Every admission and marks test passes
  `theatre=None`, which skips the `if theatre is not None:` branch entirely in both
  `admission._build_entry_position` and `marks._mark_position`. Decision 8's two concrete claims —
  "`lat`/`lon` are `dcs_to_wgs84` applied to believed x/z" and "an unregistered theatre yields null,
  never raises, and a memory write must never kill the poll loop" — are therefore both untested.
  This is the one place in the batch where a regression could silently reintroduce a crash on the
  poll thread (a memory write raising past `step()`/`mark_here`/`mark_target`) with nothing to
  catch it. `test_tools.py` already uses `theatre="Syria"` against a registered projection
  elsewhere in this test suite, so the fixture pattern exists; add one test per site
  (`admission.py`, `marks.py`) with a registered theatre asserting `lat`/`lon` populate, and one
  with an unregistered theatre string asserting `lat`/`lon` are `None` and no exception propagates.

- **The plan's own "Changed" file list for `body-layer/CLAUDE.md`, `body-layer/docs/STRUCTURE.md`,
  and `body-layer/ROADMAP/BL-8.md` was not touched by either implementation pass.** Confirmed by
  grep: zero hits for `mission_memory` in `CLAUDE.md` or `STRUCTURE.md`, and `BL-8.md` still reads
  "Not started" / `#status/open` with no record that Stages 1, 2, 3 and 5 have landed. The
  implementer flagged this explicitly both times ("Flagging for whoever closes out the milestone")
  rather than silently skipping it, which is the right instinct, but the plan lists these as
  "Changed" files for *this* work, not for a later closing pass, and root `CLAUDE.md`'s own
  "Milestone Completion" expectation is that a roadmap entry reflects what has actually landed.
  Add the `mission_memory/` module-map entry (the eight-file package, the import-direction
  invariant) to `CLAUDE.md`'s Module map and `STRUCTURE.md`, and update `BL-8.md` to record that
  Stages 1/2/3/5 are done with Stage 4 (trigger) and Stage 6 deferred per the user's own 2026-10-17
  decisions already quoted in the plan.

### Optional Refinements

- **`GROUP_ENTRY_CONFIDENCE_FLOOR`'s rendered `defaults.toml` entry carries no `range:` line**,
  unlike the other three new constants. This is not a bug in the Implementer's code: `tuning.
  fraction()` fixes `lo=0.0`/`hi=1.0` internally by delegating to `real()`, so the bound is
  genuinely enforced at runtime — but `generate_defaults.py`'s AST scan only reads `lo=`/`hi=`
  keyword arguments at the call site itself, and `fraction()`'s call site has none, so the
  generator has nothing to render. This is the first use of `tuning.fraction` in this codebase, so
  the gap in the generator was never exercised before now. Not a defect in this batch's own code,
  and not something this batch should be asked to fix in `generate_defaults.py` — flagging so a
  future reader checking "do `lo`/`hi` render" for a `fraction()`-declared key does not mistake a
  pre-existing generator limitation for a new constant's own error. (Saved to agent memory below.)
- **`ad_link`/`group_link` eventual symmetry is demonstrated in-memory, not via a genuine JSONL
  replay**, unlike the strike chain's own replay test (`test_replay_rebuilds_struck_by_from_an_
  actual_jsonl_file`). The in-memory version is logically sufficient (the same store methods
  decide both), but given the strike chain got the stronger "from the file alone" treatment, the
  link test reads as slightly less rigorous by comparison. Cheap to add if ever touched again; not
  worth a fix cycle on its own.

### Checklist verification

- **Decision 1 (import direction):** `tests/test_mission_memory_import_direction.py` greps
  `src/belief/*.py` for `from|import mission_memory` at line start, allowing only `tool_api.py`.
  Mutation-tested: adding `import mission_memory` to `contacts.py` failed it immediately. The one
  comment reference in `speech.py` (`#: mission_memory.admission's own name for...`) does not match
  the regex, correctly. `crew_console.py` never imports `mission_memory`; the plan's own
  Decision 6 tension with Decision 1 is resolved by closure injection in `logger.py`, matching an
  existing pattern (`speech_log_sink`). Sound.
- **Append-only:** confirmed by reading — `store.append()` never mutates an existing `Entry`
  (frozen dataclasses throughout), the strike is a separate append naming `strikes=<seq>`, and
  `struck_by` is rebuilt by replay (`rebuild_struck_by`), tested against both the in-memory store
  and an actual JSONL round-trip.
- **Co-moving Fields / single construction site:** `append()` is the only `Entry(` construction in
  `store.py` (grep-tested), and `admission.py`/`marks.py`/`query.py`/`tools.py` are grepped to
  contain no `Entry(` at all. Mutation-tested: injecting a second `Entry(` call anywhere in
  `admission.py` failed the grep test immediately.
- **No ground truth (Decision 8):** code reads correctly — both `admission._build_entry_position`
  and `marks._mark_position` derive `lat`/`lon` from believed `x`/`z` via `dcs_to_wgs84`, catching
  `ValueError` to `None`. **Untested**, see Required Fixes above.
- **Tuning constants:** all four render in `config/defaults.toml` with the rendered comment
  (not just the source `#:` comment) checked directly. `RESIGHT_MOVE_M`'s hazard sentence (per-look
  noise, not discrete step buckets) is genuinely sentence one in the rendered file — confirmed by
  reading the TOML, not the source. `lo`/`hi` on the three `real()`-declared constants are AST
  literals. `GROUP_ENTRY_CONFIDENCE_FLOOR`'s reuse search was re-run independently
  (`grep -rn "confidence >=\|CONFIDENCE_FLOOR" src/belief/`) and confirms nothing on the describe/
  callout path gates on a confidence threshold — `voice_commands.py`'s `CONFIRM_FLOOR` is speech-
  recognition confidence, an unrelated domain. New key correctly declared.
- **`TOOL_SET` 15 → 17:** `tool_api.py`'s docstring records the BL-7 fold-vs-extend reasoning in
  the required style, argues why `get_contact_history`'s fold is right where BL-7 declined one, and
  why the two new tools have no existing tool's question to be a subset of. `test_tool_api.py`'s
  `_EXPECTED_TOOL_NAMES` updated.
- **Scope:** nothing beyond Stages 1, 2, 3, 5. Stage 4's schema (nullable `weapon`/`outcome`)
  shipped in Stage 1 as the plan specified; no trigger code exists. Stage 6 absent entirely, as
  expected.

### Verification

Run from inside `body-layer/`, main checkout's venv (worktree has none, as both implementers
reported):

```
ruff format --check src tests   -> 152 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 68 source files
pytest -q                       -> 2158 passed, 4 xfailed in 16.81s
```

Matches the implementer's reported state exactly.

### Verdict

**APPROVED WITH MINOR FIXES.** The three Required Fixes are all test-coverage/documentation gaps,
not logic defects found in the shipped code — the behaviour they would catch already reads correct
by inspection and by the plan's own reasoning. They should go through the standard loop
(Implementer → Reviewer on the fix) rather than being waved through, since "add tests for an
already-correct code path" is exactly the kind of small change that can quietly miss something
(e.g. a test added against the wrong theatre fixture, or one that doesn't actually exercise the
`except ValueError` branch).

### Review Confidence

Full read of all seven new `mission_memory/` modules, all eight new/changed test files, the three
`belief/` files gaining mission-memory surface (`tool_api.py`, `crew_console.py`'s dispatch, the
`speech.py` rename), `logger.py`'s wiring, and the rendered `config/defaults.toml`. Mutation-tested
both structural guards. Not independently re-derived: the pre-existing `~160` test-file mypy
findings the implementer reported as unrelated noise (did not re-run `mypy tests` as a batch,
consistent with this subproject's own stated convention of not doing so).

---

## Re-review of the fix round — 2026-10-17

Branch `feature/bl8-mission-memory`, fix commit `b772500a0820e12ab24f030e2fe0f1dfa7004723`
(worktree HEAD started at `24f217fc`, 44 commits behind; `git merge --ff-only b772500a` fast-forwarded
cleanly onto a clean tree). Scope: the fix commit only (`git diff b772500a~1 b772500a`), not a
re-review of the whole batch.

### Fix 1 — `_seen_how` assertions

Confirmed real, not decorative. `admission._seen_how` (`admission.py:166-179`) reads
`contact.sighting_spans[-1].source` for `optic`, hardcodes `range_m=None`, and reads
`confidence`/`certainty` off the live contact belief — the new assertions check exactly that.
The `air_defence` test's contact is sighted via `source="scope"` (distinct from the `group`
test's `_contact` default `"naked_eye_visual_filtered"`), so passing both genuinely rules out a
hardcoded-string implementation: a `seen.optic == "naked_eye_visual_filtered"` literal would fail
the air-defence assertion. `seen.confidence == GROUP_ENTRY_CONFIDENCE_FLOOR + 0.1` is a safe
equality — same literal Python expression computed once in the fixture call and compared, no
cross-float-path drift. `range_m is None` is asserted for the stated reason: the implementer's
mutation test (changing `range_m=None` to `range_m=999.0` in source and confirming both new
assertions fail with `AssertionError: assert 999.0 is None`) is the right counterfactual and I
re-derived it independently by reading the guard rather than re-running it — the code has exactly
one `range_m=` assignment in `_seen_how`, so the claim holds.

### Fix 2 — Decision 8 theatre tests

Confirmed both guards are structurally identical and both new tests exercise the real branch, not
an accidental pass:

- `admission._build_entry_position` (`admission.py:182-211`) and `marks._mark_position`
  (`marks.py:46-66`) both skip the `if theatre is not None:` branch when `theatre=None`, which is
  what every pre-existing test in both files used. The four new tests are the first in this suite
  to pass a non-`None` theatre to either function.
- **Registered case asserts against `dcs_to_wgs84`'s own output, not a copied literal** — all four
  new tests call `dcs_to_wgs84("Syria", x, z)` directly inside the test body and compare against
  that return value (`expected_lat, expected_lon = dcs_to_wgs84(...)`), never a hand-typed
  lat/lon pair. This is the right shape: it would catch a regression in *how* the function is
  called (wrong argument order, wrong x/z source) without being brittle to the projection's own
  numeric output.
- **Unregistered case asserts no exception propagates**, not merely null values — the test bodies
  call `step(...)`/`mark_here(...)` directly with `theatre="Not_A_Registered_Theatre"` with no
  `pytest.raises` wrapper; if the `except ValueError` guard were removed, the call itself would
  raise and the test would fail with an uncaught exception before reaching the `assert pos.lat is
  None` line — so the null-value assertions are reached only when nothing raised. The
  implementer's mutation test (removing the `try/except ValueError` in each module and confirming
  the real `ValueError` propagates and fails the unregistered test, while the registered test
  stays green) is the correct counterfactual, and I re-ran it myself rather than trusting the
  report: removing the `except ValueError` block in `admission.py`'s `_build_entry_position`
  (replacing the `try/except` with a bare call) reproduced a `ValueError` raised from
  `coordinates/__init__.py`'s `_theatre_crs` and failed exactly
  `test_unregistered_theatre_yields_null_lat_lon_and_never_raises`, with the registered-theatre
  test (`test_registered_theatre_populates_lat_lon_from_believed_position`) still passing. Restored
  via `git checkout -- src/mission_memory/admission.py` and re-ran green (2162 passed, 4 xfailed).
  Did not additionally re-run the `marks.py` mutation — the guard is structurally identical
  (confirmed by reading both call sites side by side) and the admission.py run already shows the
  test harness genuinely exercises the branch.

### Fix 3 — documentation

`body-layer/CLAUDE.md`'s Module map gained a "Mission memory" section between Belief and Surfaces
with one bullet per module plus the import-direction invariant; `body-layer/docs/STRUCTURE.md`
gained matching per-module detail entries at the same boundary, each carrying the plan's own
*why* (Decision 8's believed-position/unregistered-theatre posture, Decision 3's belief-transition
cadence, Decision 1's import direction, Decision 6's non-shared position-building). Both read as
accurate against the code just reviewed. `body-layer/ROADMAP/BL-8.md` now reads `[~]`/
`#status/in-progress` (was `[ ]`/`#status/open`) and records Stages 1/2/3/5 landed with a pointer
to `review.md`, Stage 4's deferral (schema shipped, trigger blocked on aircraft-layer weapon-export
and a `getLife()`-based outcome signal) and Stage 6's deferral (belief that the memory itself is
trustworthy first, gated in `belief/callouts.py`) each with their stated reason, and Sortie A
named as outstanding with the explicit note that the feature is write-only in flight so acceptance
is a post-flight file read — a future reader will not go looking for an in-flight observable that
doesn't exist. `git diff b772500a~1 b772500a -- body-layer/ROADMAP.md` is empty — the pointer file
was correctly left untouched.

### Nothing new

- `git show b772500a -- body-layer/src` is empty — no production code changed in this commit.
- `git diff b772500a~1 b772500a -- body-layer/src/tuning.py body-layer/tools/generate_defaults.py
  body-layer/tests/test_mission_memory_store.py body-layer/config/defaults.toml` is empty — the
  two Optional Refinements (`tuning.fraction()`'s missing `range:` line; the in-memory-only
  `ad_link`/`group_link` symmetry test) were correctly left alone, as instructed.
- The full file list touched is exactly the seven named in the task (`git show b772500a --stat`):
  the two test files, `CLAUDE.md`, `STRUCTURE.md`, `BL-8.md`, `implementation.md`, and one new
  `.claude/agent-memory/implementer/` file. No eighth file, no scope creep.
- No debug code, no new TODOs.

### Verification

Run from the main checkout's `body-layer/.venv` against this worktree's `body-layer/` (worktree
has no `.venv`, as every prior pass reported):

```
ruff format --check src tests   -> 152 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 68 source files
pytest -q                       -> 2162 passed, 4 xfailed in 16.24s
```

Matches the implementer's claimed state exactly.

### Verdict

**APPROVED.** All three required fixes are discharged, each verified by reading the guard and
independently re-running (not merely trusting) the stated mutation test — the `admission.py`
`ValueError`-guard removal was re-run live in this review and reproduced the claimed failure. The
fix round introduces no production-code change, touches only the files named, and leaves the two
Optional Refinements untouched as instructed.

### Review Confidence

Full read of the fix commit's diff (all seven files). Independently re-ran one of the two claimed
mutation tests (the `admission.py` `ValueError`-guard removal) rather than trusting the report; the
`marks.py` mutation was verified by code-reading (structurally identical guard) rather than
re-run, since the admission.py re-run already demonstrates the test harness distinguishes a
raising guard from a suppressing one.

---

## 2026-10-17 — Narrow review: voice vocabulary fix for `mark_here`/`mark_target` (commit `f6b81f4b`)

Branch `feature/bl8-mission-memory`, worktree fast-forwarded cleanly from `24f217fc` to tip
`f6b81f4b7aad2eb74e866cb0c82fda9f8468e6cb` (tree clean beforehand, 44 commits behind as expected).
Scope: the single commit answering DoD's one finding — the batch itself (Stages 1/2/3/5) is already
APPROVED above and is out of scope here.

### Review Summary

`git show f6b81f4b --stat` touches exactly four files: `audio-adapter/src/vocabulary.py`,
`audio-adapter/tests/test_command_matcher.py`, `plans/bl8-mission-memory/implementation.md`, and
one new agent-memory file (`.claude/agent-memory/implementer/
project_voice_token_needs_audio_adapter_vocabulary.md`). No body-layer source change, nothing else
smuggled in.

The fix is exactly what Decision 6 and the DoD finding required: `mark_here`/`mark_target` added to
`VOICE_ONLY_TOKENS` with plain, slot-free phrasings matching `drop_target`/`disengage`/`observ_on`'s
own posture, `PHRASES` entries for both, and a `TestMarkHereMarkTarget` class.

**Independently re-ran `match_transcript`** (not trusted from the report) on all five new
phrasings — all resolve to the intended token at `match_ratio == 1.0`, `verb_anchored == True`,
`ambiguous == False`, `slots is None`, matching the claim exactly.

**Collision probe beyond what the implementer tested:** ran the four phrases against
`select_target`/`drop_target`/`engage` variants not in the implementer's own test
(`"engage target"`, `"set target two o'clock"`), plus ten adversarial near-misses the implementer's
four sentences didn't cover (`"mark here now"`, `"mark the target"`, `"remember the target"`,
`"mark my target"`, `"remember this spot"`, `"mark position"`, `"mark target now"`, `"remember
here"`, `"mark location"`, `"that's a remarkable sight"`, `"remarkably close call"`). None stole an
existing token's match and none of the new tokens' near-misses resolved to the wrong token; two
fuzzy near-misses (`"mark here now"`, `"mark my target"`, `"mark position"`, `"mark target now"`,
`"remember this spot"`) resolved correctly at a lower ratio (0.67) rather than failing outright,
which is the matcher working as designed, not a defect. `"remarkable"`/`"remarkably"` interestingly
anchor the verb (substring match on "mark") but correctly resolve to `token=None` — same tolerance
the existing design accepts for any anchor word (false anchor is cheap and reversible; false
rejection is not, per `command_matcher.py`'s own design comment) — not a regression this fix
introduced.

**Mutation-tested the two new tests directly**, not just read them: removed the two `PHRASES`
entries while leaving the tokens in `VOICE_ONLY_TOKENS` (simulating "wired into dispatch but no
vocabulary entry" — the exact defect DoD found) — `assert set(PHRASES) == set(TOKENS)` fails at
import, confirming the invariant is load-bearing, not coincidental. Removed the tokens from
`VOICE_ONLY_TOKENS` too (full revert) — all three `TestMarkHereMarkTarget` methods then fail with
`token=None` where a real token was expected, confirming the tests exercise behaviour through
`match_transcript`, not the table. File restored byte-for-byte afterward (`git diff` on
`vocabulary.py` is empty).

**The "remember" verb introduction.** `remember this location`/`remember target` are new anchor
vocabulary. Judged safe: `VERB_ANCHOR_WORDS` is derived automatically from `PHRASES`
(`_derive_verb_anchor_words`), so this is the same mechanism every other verb in the table already
uses, not a special case; the adversarial probe above (including two sentences the implementer
didn't test) confirms ordinary English containing "remember"/"mark" does not false-fire into either
token. Style is consistent with the existing table's comment conventions (cites Decision 6, explains
the posture match, explains why the phrase doesn't collide).

**Public open-source constraint**: phrasings are short, common English ("mark here", "mark target",
"remember target") with no pilot-specific jargon or idiom, consistent with the rest of the table.
"remember this location" is slightly more formal than a clipped radio call but that is the
implementer's own stated reasoning (the longer, less-clipped way a speaker might actually say it) —
reasonable, not fragile.

**Scope note (not a required fix):** the typed-text path (`belief/utterance.py`'s grammar) still has
no "mark" entry, so a console-typed line cannot set a mark. DoD flagged it, the implementer
deliberately left it out as a scope call for the user. Noting it per the task brief; not required.

### Required Fixes

None.

### Optional Refinements

None beyond what the implementer already flagged (typed-text parity, left to the user's call).

### Verdict

**APPROVED.**

### Verification

Run from this worktree's `audio-adapter/`, against the main checkout's `audio-adapter/.venv` (this
worktree has none, as every prior pass in this feature reported):

```
ruff format --check src tests   -> 29 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 15 source files
pytest -q                       -> 284 passed, 1 skipped in 28.83s
```

Matches the implementer's claimed state exactly.

### Review Confidence

Full read of the commit's diff (all four files). Independently re-ran `match_transcript` on all
claimed phrasings plus 17 additional probes (collisions and adversarial near-misses) not in the
implementer's own test. Mutation-tested both new tests by two separate reverts (phrase-only, then
full token+phrase), confirming each fails for the right reason; file restored clean afterward.
