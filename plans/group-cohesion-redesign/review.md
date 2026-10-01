### Review Summary

Reviewed `fix/group-undermerging` @ `3d7d51c` (range `fc74e90..3d7d51c`, 1384 insertions / 12 files)
against `plans/group-cohesion-redesign/plan.md`, its three explore-notes files,
`plans/group-undermerging/{explore-notes,debug}.md`, root `CLAUDE.md`, and `body-layer/CLAUDE.md`.

Stage 1 (infantry `EAGER`) and Stage 2 (`installation_component`, 500 m cap) are implemented exactly
as settled, with the single-link-chaining consequence correctly found and pinned, and the plan's own
stale Stage 2 S-300 acceptance wording correctly identified and flagged rather than silently patched
around (confirmed true: the plan's §1 settled list really does exclude `OP_LRSAM` from
`installation_component`, so a four-member S-300 merge is not achievable under the settled design).
`AIR_DEFENSE_OP_CLASSES` correctly uses `OP_ZU23` (verified complete against every real `op_class`
string in `object_model.py`: `OP_ARMORED`, `OP_INFANTRY`, `OP_LRSAM`, `OP_MRSAM`, `OP_SHIP`,
`OP_SPAAG`, `OP_SRSAM`, `OP_TRUCK`, `OP_ZU23` — nothing air-defence-shaped is missing). The
`render_group_full_disclosure` split for the pull ("report") path is the right fix for a real,
correctly-diagnosed gap, and is directly unit-tested (`test_render_group_full_disclosure_ignores_
the_delta_taxonomy`). All six named taxonomy branches (never-spoken, leader-changed,
first-differentiation, new-class-delta, air-defence-repeat-delta, non-air-defence-repeat-silence,
departure-silence) are reachable and individually tested. Clock position is never used for identity
anywhere in the diff — only in rendering. The `content_signature`/`last_spoken_signature` dedup from
the earlier debug fix still composes correctly with the richer taxonomy state (verified by reading
`callouts.py`'s tick logic): a `None` return from the taxonomy short-circuits before the
dedup-by-signature check even runs, and the check remains a correct defensive fallback.
`ruff format --check`, `ruff check`, `mypy --strict`, and `pytest` all reproduced clean/green exactly
as the implementer reported (1366 passed, 4 xfailed).

Two real defects were found by actually running the rendered output through the implementation,
not by reading alone — both are about the generated English, not the taxonomy logic, and both are
missed by the test suite's own assertions.

### Required Fixes

- **Hard-coded indefinite article `"a"` in `_group_composition_clause` (`belief/speech.py` line
  ~1077, `phrases.append(f"a {_unit_type_display(value, level)}")`) is wrong for any vowel-initial
  class word.** `"armor"` and `"infantry"` (`_OP_CLASS_DISPLAY["OP_ARMORED"]`/`["OP_INFANTRY"]`) are
  the only two vowel-initial entries in the vocabulary, and both produce bad grammar: `"a armor"`,
  `"a infantry"`. This is not hypothetical — the implementer's own new test
  `test_render_group_disclosure_new_class_arrival_is_a_delta` pins the defect as *expected* output:
  `assert speech.text == "A armor, in the group."` This is exactly the grammar defect the task
  description called out, confirmed by inspection and reproduction. Needs an indefinite-article
  helper (even a small hard-coded vowel-initial exception set — `"armor"`, `"infantry"` — would fix
  both known cases) applied wherever `_group_composition_clause` builds a count==1 phrase, and the
  now-wrong assertion in that test (and the identically-shaped one in
  `test_render_group_disclosure_air_defence_repeat_arrival_is_a_delta`, which currently passes only
  because `"ZSU-23-4 Shilka"` happens to be consonant-initial) needs updating to the corrected text.

- **The "first differentiation → full disclosure" branch produces nonsensical English when the
  group has undifferentiated members mixed in with the newly-differentiated one — directly
  contradicting the plan's own worked example for this exact branch.** Reproduced directly (not
  guessed): a 2-member group, one member still at `presence` level and one newly at `class` level,
  renders as `"A ground and a truck."` via `_render_full_group_composition`'s `elif differentiated:`
  branch, which calls `_group_composition_clause` over *all* member facts including undifferentiated
  ones — `_unit_type_display(None, "presence")` returns `"ground"`, and the count==1 branch then
  renders it as its own counted noun phrase, `"a ground"`. This is the same code path the plan's §4
  cites by name as proof the branch works (*"`'AAA in the group'` reads as full because, with one
  member known, full and delta coincide; no utterance contradicts treating this branch as
  'full'"*) — but the actual rendered text for that scenario is not `"AAA in the group"`, it is
  `"A ground and a <type>."` This is pre-existing code (the `elif differentiated:` branch is
  unchanged in substance from before this plan, only moved into the new `_render_full_group_
  composition` helper), but it sits squarely in the path this plan's Stage 3 depends on and
  explicitly claims is correct. **The implementer's own test for this branch
  (`test_render_group_disclosure_first_differentiation_is_full_once`) does not catch this**: its
  assertions (`"in" not in speech.text or "o'clock group" not in speech.text`,
  `not speech.text.startswith("Now leading")`) only rule out the *other* branches' shapes; they
  never check the actual rendered content, which is exactly the fixture-blind-spot pattern the task
  warned about (item 8). Needs the mixed-differentiated-members case either to drop undifferentiated
  members from the enumerated composition (matching the "in the group" implicit-rest pattern the
  membership-delta branch already uses) or some other deliberate fix — and a test that asserts the
  actual string, not just the absence of other branches' markers.

### Optional Refinements

- `tests/test_crew_console.py::test_report_speaks_a_persisted_group_through_render_group_disclosure`
  (not touched by this diff) is now stale in both name and body: its docstring says `_handle_report`
  "speaks it once via `render_group_disclosure`," and it builds its own `expected` value by calling
  `render_group_disclosure` directly — but production code now calls `render_group_full_disclosure`
  for this path. It still passes only because the group in this test has never been spoken (the
  "never spoken" branch of both functions coincides), so it currently provides **no regression
  coverage for the actual bug the implementer fixed**: nothing at the `CrewConsole`/`handle_command`
  integration level proves "report" still returns the full roster for a group that *has* already
  spoken and would get a delta or silence from `render_group_disclosure`. The unit-level test in
  `test_speech.py` (`test_render_group_full_disclosure_ignores_the_delta_taxonomy`) does cover the
  renderer directly, so this is not a correctness gap in the shipped behaviour — but the stale
  integration test is exactly the kind of thing that could let `_handle_report` silently drift back
  to the taxonomy-gated function in a future edit without any test noticing. Worth a rename + a
  second case (already-spoken group) next time this file is touched; not blocking.
- `plans/group-cohesion-redesign/implementation.md` states "Branch `fix/group-undermerging`, tip
  `fc74e90`" — `fc74e90` is the review range's *starting* sha (the pre-existing base), not this
  work's own tip. Harmless (the file is a historical record, not consumed by tooling), but worth a
  one-line correction if the file is touched again.

### Verdict

NEEDS REVISION

### Review Confidence

Full read of the diff (all 12 changed files) and the plan/explore-notes/debug.md chain. Both
required fixes were confirmed by running the actual code in a venv built from `body-layer/
pyproject.toml` (reproduction scripts via Write, run with `.venv/bin/python`, then deleted — working
tree left clean), not inferred from reading alone. `.claude/scripts/gq.sh` was not usable in this
worktree (`graphify-out/` is gitignored and absent here); not needed for this review since the
controlling documents were all explicitly named in the task and read directly.

---

## Round 2: re-review of the fix rounds

Re-reviewed `fix/group-undermerging` @ `0317431` (range `3d7d51c..0317431`, three commits:
`8c9708a` round-1 fix, `adb7d19` round-2 fix correcting round 1, `0317431` citation cleanup)
against this file's two Required Fixes above and
`plans/group-cohesion-redesign/explore-notes-delta-taxonomy.md`'s worked utterances as the
grammar specification.

**Worktree note**: the assigned worktree had landed on `main`'s tip
(`67da508`, own branch `worktree-agent-aee7d0266358765f8`), not `fix/group-undermerging`. Verified
with `git rev-parse HEAD` per the rule-4 procedure before doing anything else, then built an
isolated snapshot with `git archive fix/group-undermerging | tar -x` into the scratchpad and ran
every check from inside that tree's own `body-layer/` with a fresh venv — never from the worktree's
actual checkout.

**Finding 1 (indefinite article), re-reviewed.** Round 1 (`8c9708a`) replaced the bare `"a"` with
an `_with_indefinite_article` helper plus a `{"armor", "infantry"}` vowel-initial exception set —
grammatically correct for count nouns but still wrong for `"armor"`, a mass noun that takes no
article in either form. I sent this back. Round 2 (`adb7d19`) removed the mechanism entirely rather
than extending it: `_with_indefinite_article`/`_VOWEL_INITIAL_CLASS_WORDS` are gone from
`speech.py` (grepped — no trace), and `_group_composition_clause`'s `count == 1` branch now appends
`_unit_type_display(value, level)` bare. Checked the implementer's claim that this brings the
function in line with the module's existing convention rather than creating a new inconsistency:
`_contact_report_text` and `_identification_lead` were already bare-noun (grepped both; neither
ever prepended an article) before this fix, so the claim holds — the module is now consistent in
the direction it already had, not inconsistent in a new one. Cross-checked every worked utterance
in `explore-notes-delta-taxonomy.md`: `"AAA in the group"`, `"Shilka and zsu"`, `"SRSAM, Shilka,
armor 2 o'clock 2.5 km"` — count nouns and mass nouns alike are bare in a composition clause; the
file's one article, `"there's a zsu"`, sits in a different sentence frame (existential singular
announcement, not composition) and is correctly not treated as counter-evidence by the fix's own
code comment. Grepped `tests/test_speech.py`, `test_callouts.py`, `test_crew_console.py` for any
remaining `"[Aa]n? <class/type noun>"` pattern in an actual assertion (not a docstring) — none
found; the five assertions the round-2 commit message names, plus the `test_callouts.py` fixture
line, account for all of them.

**The one kept article, `"A couple of contacts."`**, judged separately rather than taken on
faith: `"couple of"` is a fixed cardinality-hedge idiom (`_cardinality_phrase`'s own vocabulary,
alongside `"a handful of"`, `"several"`) that always takes "a", structurally unlike `_with_
indefinite_article`'s per-noun a/an choice on a bare count==1 class word — it is quantifying a
plural noun phrase, not choosing an article for a singular one. The user's own example
(`"a couple of contacts"`) uses exactly this form. Real distinction, not a missed case papered
over: `_cardinality_phrase` and `_group_composition_clause`'s count==1 branch are different
functions serving different grammatical slots, and nothing in the diff touches `_cardinality_
phrase`'s article.

**Finding 2 (undifferentiated-member aggregation), re-reviewed.** Unchanged by round 2 — this was
only round 1's fix, and it stands. `_undifferentiated_phrase` (new) returns `"something"` for
count 1 and a spoken-number/`"many"` count of `"contacts"` otherwise, matching the user's own `"SAM
and something"` example exactly; `_group_composition_clause` buckets `presence`/`unknown`-level
members out of the per-class loop and appends this as one trailing phrase instead of rendering
`_unit_type_display`'s `"ground"` fallback as its own noun phrase. Ran the originally-reproduced
scenario and its siblings directly (not just read): `test_render_group_disclosure_first_
differentiation_is_full_once` now asserts `"Truck and something."` (was `"A ground and a
truck."`), and `test_crew_console.py`'s new `test_report_speaks_an_already_spoken_group_in_full`
exercises the two-undifferentiated-member count path end to end via `"report"` after the group has
already spoken once, giving `"Three BMP-2, 3 o'clock, 1 kilometre."` for a fully-undifferentiated
group's full roster. Both ran green in isolation, not just inside the full suite.

Verified the implementer's "same latent bug on an untested second code path" claim rather than
accepting it: grepped every call site of `_group_composition_clause` (three — the air-defence
"Danger, X. Also Y" leading-member/rest line at `speech.py:1356`, the main composition line at
`:1366`, and the delta clause at `:1632`) and confirmed the fix lives inside the shared function
itself, so all three call sites get it for free rather than only the one path the original defect
was reproduced on. This is exactly the standing "grep for the new mechanism's own call site, not
the file list" check — all three call sites route through one function, so there is no sibling
path left uncovered.

**Test quality.** Re-swept `test_speech.py`, `test_callouts.py`, `test_crew_console.py` myself for
any remaining can't-fail assertion over a rendered group-composition string (negative-shape checks
like round 1's own `"in" not in speech.text or ...` that this feature has now hit three times) —
found none; every composition-clause/group-disclosure assertion in scope now pins the literal
string. The round-2 commit's claim of "five test assertions ... fixed all of them, not just the two
reported" is correct by direct count (four in `test_speech.py`, one in `test_callouts.py`,
confirmed above).

**Citation fix (`0317431`).** Diffed it directly: five `plans/group-undermerging/review.md` →
`plans/group-cohesion-redesign/review.md` string replacements in `speech.py` comments and
`test_speech.py`/`test_crew_console.py` docstrings, plus a rewrite of the implementer's "file does
not exist" note in `plans/group-undermerging/implementation.md` into a short "corrected" note.
Confirmed `plans/group-cohesion-redesign/review.md` exists at the destination path and its Finding
1/Finding 2 text matches every citing comment's description. No other hunks touched; nothing
mangled.

**Checks reproduced**, from a venv built fresh in the snapshot's `body-layer/` (no `.venv` shipped
in the worktree): `ruff format --check src tests` → 113 files already formatted; `ruff check src
tests` → all checks passed; `mypy src` (run with cwd inside `body-layer/`, per the CWD-only config
discovery note) → no issues, 53 source files; `pytest tests -q` → **1367 passed, 4 xfailed**,
matching the expected count exactly.

### Verdict (Round 2)

APPROVED

Both required fixes are resolved correctly and completely — Finding 1 by removing the article
mechanism rather than patching it (the right fix, since the defect was conceptual, not a missing
exception), Finding 2 unchanged and still correct. The one surviving article (`"a couple of"`) is a
different grammatical construct, not a missed case. No new findings; this round is a clean pass.

### Review Confidence (Round 2)

Full read of all three commits' diffs. Every claimed before/after string checked by running the
actual test (not reading the assertion alone) for the end-to-end fixture, both arrival deltas, the
first-differentiation branch, and the two crew-console group-report tests. The call-site grep for
Finding 2's "second code path" claim and the test-suite sweep for remaining can't-fail assertions
were both performed directly rather than accepted from the implementer's report.
