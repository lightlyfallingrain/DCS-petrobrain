# BL-11 `feature/bl11-tick-cost` — Review, round 3

Branch `feature/bl11-tick-cost`, tip `69073ca` (checked out directly in this worktree — the main
checkout had moved to `main` — and confirmed by `git rev-parse HEAD` before anything was read).
Round-3 scope is the four commits `c50ac21`, `749c151`, `08025f7`, `69073ca` against round 2's
`d6e6288`, reviewed against `review-round2.md`'s three required fixes plus its deletion ruling, and
`implementation.md`'s round-3 section.

### Review Summary

The deletion is clean and the sweep behind it is complete. The two strengthened close tests use the
right mechanism. Both remaining defects are the same class the previous two rounds each found once:
**a docstring whose stated *reason* outruns what the code does, while its conclusion is correct.**
Neither changes behaviour; both are one-clause edits. That the class has now recurred three rounds
running is itself worth recording — see "The pattern" below.

Checks, run with the main checkout's `body-layer/.venv` binaries and `cwd` inside this worktree's
own `body-layer/`, import resolution proved first rather than assumed (`perception.group_salience`
and `logger` both resolve to this worktree's absolute `src/` path, and the imported module has
**no** `_resolvable` / `_cohesive` attribute and **does** have both `_terms` functions):

- `ruff format --check src tests` — 118 files already formatted
- `ruff check src tests` — all checks passed
- `mypy src` — success, 54 source files, strict
- `pytest tests -q` — **1512 passed, 4 xfailed**
- `pytest tests/test_group_salience_equivalence.py -q` — **15 passed**
- Both reworked tests confirmed **by name** in unfiltered `pytest tests -v` output
  (`tests/test_belief_truth_log.py::test_close_does_not_raise_on_a_healthy_writer`,
  `tests/test_detection_trace.py::test_close_does_not_raise_on_a_healthy_writer`), not by `-k`.

Invariants: not re-run as a battery. This round's diff is a deletion, four docstrings, two test
bodies and the plan log — no new exception handling, no DCS-install access, no `world-model/data/`
path, nothing generated. Round 2's all-PASS result stands unchanged.

The `close()` fix was **not** re-proved here: the orchestrator's own mutation (both writers'
`close()` gutted to `return` → 2 failed, 44 passed, the two healthy-case tests exactly) is the
evidence, and re-running it would add nothing.

### Required Fixes

- **`tests/test_group_salience_equivalence.py` module docstring: "Stage 2 did not touch them" is
  false for one of the four.** Stage 2 is commit `4166fc0`, *"BL-11 Stage 2: hoist group_salience's
  per-candidate terms, **cache profile_for**"* — it added `@cache` to `object_model.profile_for` on
  this branch (`git diff main..HEAD -- body-layer/src/perception/object_model.py`, +14 lines, the
  only change to any of the four leaf primitives; `clustering.py` and `geometry.py` are untouched by
  the branch entirely). The sharing judgement is right and the conclusion survives — memoising a
  pure function of one `str` that returns a `frozen=True` dataclass over never-mutated module tables
  cannot make an equality tautological, because both sides call the same function and would with or
  without the cache. What is wrong is the premise offered *as* the safety argument. This is the file
  whose round-1 and round-2 defects were both false claims about itself, and a reader auditing where
  the shared/not-shared line falls would find the stated reason does not hold and have to re-derive
  it. One clause: three of the four were untouched by Stage 2 and `profile_for` was only memoised,
  semantics-preserving, which is why sharing it still cannot move both sides of an equality
  together.

- **`_resolve_speech_log_path`'s closing paragraph gives a reason for keeping the local `mkdir` that
  the code does not support** (`logger.py:1685-1688`): *"it degrades before the default path is ever
  returned, so the `"writing <path>"` startup line is never printed for a location that cannot hold
  a file."* The first half is true; the `so` does not follow. `per_run_log_path` uses
  `Path.with_name`, which preserves the parent exactly ("renames the file, it never relocates it"),
  so `_per_run_log_paths`'s own `resolve` closure `mkdir`s **the same directory**, returns `None` on
  `OSError`, and the announcement loop prints `"<flag>: writing <path>"` only for non-`None` paths.
  Verified by execution rather than reading — `_per_run_log_paths` called alone with `logs` occupied
  by a regular file (i.e. simulating the local `mkdir` removed) printed
  `speech-log: could not create log directory logs ([Errno 17] File exists: 'logs'); continuing
  without this log` and returned `(None, None, None)`, so the misleading "writing" line would not
  print either way. The property is secured downstream regardless of this `mkdir`.

  The differences that *are* real are cosmetic, and either would be an honest reason: the local
  guard emits a speech-log-specific message (`could not create **default** log directory … continuing
  without **a speech log**`) rather than the generic per-flag one, and reports before stamping. So
  the fix is one of two: state that as the reason and drop the `so …` clause, or take round 2's
  optional refinement and delete the redundant `mkdir` outright. Round 2 asked for this paragraph to
  stop stating a policy that no longer holds; it now states a mechanism that does not hold. Same
  class, one line further on.

### The pattern, because it is now three for three

Round 1 found a test docstring claiming coverage it did not have. Round 2 found a module docstring
claiming "only the tuning constants are shared" and a function docstring stating a superseded
policy. Round 3 finds a false premise and a false causal clause. Every one of them is a *correct
conclusion with an unearned reason attached*, and every one was written in the act of fixing the
previous instance of the same thing.

The cheap check that catches it, and caught both of today's: **a docstring sentence of the form
"X, so Y" is two claims. Delete the mechanism X in your head (or in the file) and ask whether Y
still holds.** If Y holds anyway, X is not the reason for it — which is exactly the state both of
the above are in. This file's docstrings are unusually long and load-bearing, which is a strength;
it also means a wrong "so" survives several readings.

### What I was asked to judge, with the answers

**The deletion's sweep is complete.** `git grep` for `_resolvable` / `_cohesive` as identifiers
(excluding the `_terms` names) over the whole worktree returns **no hit in `body-layer/src/`** and no
hit in any present-tense documentation — not `body-layer/docs/STRUCTURE.md`, not the module map
`ab9188e` added, not `group_salience.py`'s own module docstring, and not either of the two other
plans that discuss `group_salience` (`group-cohesion-redesign`, `group-contact-identity`). The live
references left in `tests/test_group_salience_equivalence.py` are either `_reference_*` names or
explicitly historical ("then a predicate named `_resolvable`").

The three extra references the implementer found beyond the predecessor's three were genuinely
**false, not merely stale**, and all three now read true, checked individually rather than taken on
report: `_cohesive_from_terms`'s sole-caller claim verified by grep (one call site,
`group_salience.py:189`); `_resolvable_terms` now attributes the recomputation to "the pre-Stage-2
pair loop" rather than to a deleted function; the `_reference_*` docstrings now describe the
wrappers as deleted. `group_salient_ids`'s rewritten docstring was checked line-by-line against its
own body — the union-find really is over `_cohesive_from_terms`, and candidates for which
`_resolvable_terms` returns `None` really do `continue` before the pair loop. Deleting `_cohesive`
required no import changes, which is the deletion's own argument restated: it computed nothing the
live code does not already compute.

**The dated-records line: I agree with it, and the test that keeps it applicable is not "is this a
research note?"** It is: **does the text claim to describe the code as it is now, or does it record
what was observed or decided at a stated time?** Present-tense claims about current code must be
swept; dated records must not be. Two reasons that is the right line rather than a convenient one.
The project already runs on it — `plans/<feature>/review.md` is append-only across stages, and
agent memory is explicitly read as "what was true then, verify against current state". And the old
identifier is itself part of the evidence trail: someone doing archaeology with `git log -S
_cohesive` needs the note to *say* `_cohesive`. Rewriting a dated measurement to use today's names
makes it read as though the measurement were taken against today's code, which is laundering rather
than tidying. Under that test, every file the sweep left alone — `research/2026-10-05-performance-
review.md`, `ROADMAP.md`/`BACKLOG.md`'s measurements, the `plans/bl11-tick-cost/` and
`plans/group-detectability/` logs, four agent-memory files — is correctly on the leave-alone side.

**`plans/player-bubble/performance.md:64`: leave it — but the implementer's classification of it is
wrong, and that matters more than the disposition.** That document is a performance review of an
**already-merged** feature, not forward-looking prose for an unbuilt one: its own header reads
"Reviewed `feature/player-bubble` at tip `5c5bde6`", `filter_player_bubble` and
`PLAYER_BUBBLE_RADIUS_M` are in `src/perception/association.py` today, and line 64 sits inside the
"End-to-end measurement, realistic scale" block explaining where a measured 0.955 ms saving came
from. That is a dated measurement record, the same class as the research note — and the document's
genuinely forward-looking part (the 9K113 / `NAKED_EYE_RANGE_CAP_M` divergence) does not mention the
predicate at all.

So the answer to the rule question is **no fix now, and none owed when player-bubble is next
touched**: under the test above it is on the leave-alone side, and editing it would be the
laundering the implementer was right to avoid everywhere else. This needed checking rather than
accepting precisely because the stated rule and its stated application pointed opposite ways — had
the "forward-looking, unbuilt" reading been correct, "out of scope, left alone" would have been the
wrong call by the implementer's own rule.

**The inline precondition asserts are the right mechanism — keep them.** They turn the test's
unstated precondition into an executable one, which is the thing a comment cannot do: the toothless
version survived two rounds and was caught only by a mutation experiment, and it would come back
for free the moment someone set `flush_every_n_polls=1` or made `write_poll` flush eagerly. On a
*legitimate* future change (writers deliberately flush every poll) the failure is loud and its
message names the problem, forcing a rethink instead of silently returning the test to decoration —
the right direction for a guard to fail in. Two notes for the record rather than findings: the
belief-truth case had to move from `write_speech` to `write_poll` to be bufferable at all, so
`close()`-after-`write_speech` is no longer covered by a healthy-path test — acceptable, because
`close()` is path-agnostic and `write_speech`'s eager flush is itself what made the old test
toothless; and the test's `store._contacts[...]` poke is an established pattern in this suite (11
uses across `tests/`, 4 in that file), not new ground.

### Optional Refinements

- **The module docstring's "Shared:" enumeration still is not literally exhaustive.**
  `UNAIDED_OPTIC` / `BINOCULAR_OPTIC` are imported and carry `presence_range_mult` — the very
  calibration value the mutation experiment turns on — and `WorldObjectCandidate` / `GeoPosition` /
  `Optic` are shared types. I judge all of those correctly outside the sentence's scope: they are
  *inputs and types*, and an equality test must feed both sides the same inputs or it tests nothing.
  But if this file is going to be read literally — and it has earned that — "Shared, beyond the
  types and fixtures both sides are fed:" costs five words and closes the reading. (Optional.)
- **Round 2's queued `/invariant-check` gap is already filed** as `X-B33` (`315fe51` on `main`),
  so nothing is owed here.

### Verdict

**APPROVED WITH REQUIRED FIXES** — two one-clause docstring corrections, no behaviour change, no
test change. This is **not** the last round, though it is close: round 4 should be scoped to those
two clauses and needs only `ruff format --check src tests` plus the two touched files' tests, not a
re-read of the branch. Everything else on this branch is done: the deletion, its sweep, both
strengthened tests, and all three of round 2's required fixes land as asked, with the third
(`_resolve_speech_log_path`) correct in substance and wrong only in the reason it gives for one
surviving line.

Not claimed here: that any of this runs. The tests cover the hoist's output-equivalence (including
the raised-optic case, the only one structurally able to see the gate), per-run log path resolution
and its two failure modes, and both writers' shutdown path — now with the healthy-close half
actually load-bearing. The in-flight behaviour — three sortie logs landing in `body-layer/logs/`
under one stamp, and the poll loops holding cadence under load — needs a live sortie on
**`feature/bl11-tick-cost`**, which is DoD's acceptance card, not this review's.

### Review Confidence

**Full read** of the round-3 diff (all 11 files, `d6e6288..69073ca`), plus the surrounding
production context in `group_salience.py` (whole file), `logger.py`'s two path-resolution functions
and the announcement loop, `run_log_paths.py` (whole file), and `object_model.profile_for`'s
branch diff. Three claims were checked by execution rather than reading: import resolution to this
worktree's own `src` (both modules' `__file__`, plus attribute presence/absence on the deleted
pair); the deletion sweep (`git grep` over the whole tree, twice, with the `_terms` names filtered
out); and required fix 3's causal claim (`_per_run_log_paths` called in isolation against an
uncreatable parent, confirming the "writing" line is suppressed without the local `mkdir`). The
`close()` mutation was taken from the orchestrator's own run, as instructed, and not repeated.
