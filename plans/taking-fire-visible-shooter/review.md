### Review Summary

Reviewed `fix/taking-fire-visible-shooter` tip `6029f184e10907a4dcaafae8127d3e36fe37411d`
(one commit on `431b5598`) against `docs/acceptance/2026-10-20-sortie-feedback.md` F6/F6-follow-up
and `plans/taking-fire-visible-shooter/debug.md`.

Spec: a shooter Petrovich has admitted (passed gaze/cockpit mask/optic FOV/terrain LOS, with or
without the emitter bypass), marked `targets_ownship` by the collector, must produce "Taking fire,
X o'clock." Gaze gating is unchanged (user: current behaviour correct). Emitter state must never
raise classification tier.

The fix is two edits in `NakedEyePerceptionSource` (`body-layer/src/perception/naked_eye_source.py`):
`targets_ownship_by_object_id` no longer requires `result.emitter_kind is not None`, and
`_build_observation`'s provenance fold checks `member_targets_ownship == {True}` first,
independently of `member_emitter_kinds`, falling back to the old bypass-gated branch for
"something firing... far" / burning.

**Verified, not just read:**

- **Repro mutation on base**: restored `431b5598`'s `naked_eye_source.py` into the worktree,
  reran the new test — `test_a_visible_unit_firing_at_ownship_sets_the_targets_ownship_provenance`
  fails on base (`PROVENANCE_VISIBILITY_FILTER_ONLY` instead of the targets-ownship provenance),
  the two new regression tests pass unchanged on base. Restored the tip file (`git status` clean
  throughout).
- **End-to-end callout path, traced by reading, not assumed**: `naked_eye_source.py` provenance →
  `belief/percept.py::percept_of` (`_TARGETS_OWNSHIP_PROVENANCE` closed mapping →
  `Percept.targets_ownship`) → `belief/contacts.py::record` (`firing_targets_ownship`) →
  `belief/events.py` (event's own `targets_ownship`) → `belief/callouts.py::callout_priority`
  (`_FIRING_TARGETS_OWNSHIP_THREAT_BAND`, more urgent) → `belief/speech.py` line 3231:
  `if event.targets_ownship: return f"Taking fire, {clock} o'clock."` Confirmed this chain is
  entirely untouched by the diff — the fix only has to get the fact into `Observation.provenance`
  correctly, which it does.
- **Cluster-fold precedence for mixed clusters** (explicitly checked, not just read): wrote an ad
  hoc probe (not committed) reusing the test module's own fixtures to build genuine 2-member
  clusters:
  - Mixed `targets_ownship` (one visible unaided shooter firing at ownship + one ordinary,
    non-firing member in the same cluster) → degrades to `PROVENANCE_VISIBILITY_FILTER_ONLY`, per
    the "identical keeps, disagreement degrades" rule. Correct.
  - **Unanimous** `targets_ownship=True` across 2 genuinely clustered, unaided (no-bypass) members
    → `PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP`. Correct — this is the actual multi-member
    aggregation the fix depends on, and it works.
  - Mixed kind (one unaided firing-at-ownship member + one bypass-admitted burning member) →
    degrades to ordinary (`len(member_emitter_kinds) != 1`). Correct, matches the existing
    "disagreement in kind" convention, not a new behaviour.
  - All three match the docstring's stated rules exactly.
- **Checks, all run from inside `body-layer/` (worktree has no `.venv`; borrowed
  `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`)**: `ruff format --check` clean (155 files),
  `ruff check` clean, `mypy src` clean (68 files), full `pytest -q`: 2242 passed, 4 xfailed, one
  `test_logger.py::test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` failure
  on the first run (the documented intermittent connection-refused flake), passed in isolation on
  rerun — not caused by this change, matches the dispatch's own known-flake note.
- **Scope**: `visibility.py` and `emitters.py` are untouched (`git diff` confirms zero changes) —
  gaze gating, cockpit mask, optic FOV, terrain LOS, and the tier-clamp bypass logic are all
  unaffected, as claimed. `classification_raw == "T-72B"` (exact hires tier, not
  `DEFAULT_OP_CLASS`) is asserted in the new test, proving the bypass's tier clamp was correctly
  never reached.
- **No new tunable constants** were introduced by this diff, so the tuning-mechanism checklist does
  not apply. No `#:` doc-comment renders to `config/defaults.toml` from this module (these are
  plain attribute docstrings on `Final[str]` provenance labels, not `tuning.*` declarations).
- **Comment pruning**: the two rewritten doc comments/docstrings replace the old "bypass-only"
  explanation with the corrected one; nothing dated, no verbatim user quote, and no boundary-case
  comment was dropped without a replacement or a covering test — the "vanishingly unlikely mixed
  cluster" comment at line ~420 (pre-existing, untouched by this diff) remains accurate and is now
  empirically confirmed above.
- **New agent-memory file** (`.claude/agent-memory/debugger/project_emitter_kind_bypass_conflation.md`)
  is well-scoped and correctly distinguishes the fixed bug from the (deliberately unchanged)
  tier-clamp gating.

### Required Fixes

None.

### Optional Refinements

- **Add a committed regression test for the multi-member cluster-level `targets_ownship`
  unanimity fold** — every existing test in `test_naked_eye_source.py` (new and old) exercises this
  branch with a single-member "cluster," which only trivially satisfies `len({x}) == 1`. The real
  aggregation (`member_targets_ownship == {True}` across 2+ genuinely clustered members, and the
  mixed-member degrade case) is untested by the committed diff — I verified it by hand with an ad
  hoc probe (see above) and it is correct, but this is a pre-existing gap in the
  `emitter-visibility`/`BL-B72`/`BL-B73` feature's own test coverage (no "mixed"/"degrad"-named
  cluster test exists for `member_emitter_kinds` either, before or after this fix), not something
  this commit introduced. Worth closing opportunistically, not blocking this fix.

### Verdict
APPROVED

### Review Confidence
Full read — plus empirical mutation (base-vs-tip red/green on the repro test) and a hand-built
multi-member cluster probe to exercise the one code path no committed test reaches.
