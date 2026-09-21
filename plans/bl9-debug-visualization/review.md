### Review Summary

Reviewed `feature/bl9-detection-trace` (12 commits) against `plans/bl9-debug-visualization/plan.md`
and `implementation.md`. The implementation matches the plan's design closely: `check_visibility`
gains an additive `trace` parameter with no change to gate order or return value,
`NakedEyePerceptionSource` annotates admitted candidates post-clustering, `DetectionTraceWriter` is
the sole module allowed to hold ground truth and belief together and is verifiably read-only, and
`--detection-trace` is off-by-default and gated on `--console`/`--crew-text`.

All five weighted checks were independently verified, not just read:

1. **Reducer output vs. the milestone question.** Reproduced the pipeline end-to-end with a fresh
   synthetic scenario (own script, not the implementer's) — three objects run through
   `NakedEyePerceptionSource` + `DetectionTraceWriter` via `replay.py`, then
   `tools/summarize_detection_trace.py`. Output:
   ```
   First-admitted range per object (metres, nearer-tier-first):
    object_id  type                        presence       class        type
          101  Infantry                           -           -          71
          102  T-72B                           2024        2000           -
          103  Kilo                               -           -           -
   ```
   For object 102, closing from ~2024 m to ~2000 m over three polls, the table shows presence
   first-admitted at 2024 m and class first-admitted at 2000 m — this **is** readable as a tier
   transition (the range at which each tier first passed), even though it doesn't separately print
   the last-*failed* range immediately before the transition the way the plan's own "failed at
   3.4, passed at 2.1" phrasing suggests. The implementer's own flag in "Notable Discoveries" is
   accurate and the underlying judgment holds: this reduction answers the calibration question,
   just not in the exact two-sided form the example prose implied. Not a required fix — see
   Optional Refinements for a cheap way to close the literal gap if it turns out to matter after a
   real sortie.

2. **Non-perturbation test.** Read `test_trace_sink_does_not_perturb_the_observation_contact_or_event_streams`
   and its `_replay_with_trace_sink` helper directly. It runs the real `replay.py` harness over the
   committed `tests/fixtures/telemetry_frames.json` twice — once with `trace_sink=None`, once with a
   real `DetectionTraceCollector` — and compares full `Observation` dataclasses (all fields except
   the legitimately wall-clock-varying `t_wall`), `Contact.id` ordering plus
   `last_position`/`classification`/`contributing_observation_ids`, and the full `Event` list, for
   equality. This is exactly the plan's own specified test, not a weaker inertness check.

3. **No-omniscience boundary.** `grep`-verified: `perception/` has zero imports of `belief/`;
   `belief/` has zero references to `detection_trace`/`detection_trace_writer` anywhere.
   `detection_trace_writer.py` only reads `store.contacts` (a public property) — no call to
   `ContactStore.ingest`/`tick` or any other mutator appears in the file. The boundary is real in
   the code, not just asserted in comments.

4. **Off by default.** Traced every `None`-default path: `check_visibility(trace=None)`,
   `NakedEyePerceptionSource.trace_sink=None`, and both `logger.py` poll loops only construct a
   `DetectionTraceCollector`/`DetectionTraceWriter` when `--detection-trace` is passed. Confirmed by
   check 2's own test, which is the strongest evidence available (behavioral equivalence, not just
   code inspection).

5. **Verified against real data.** Independently reproduced the claim: wrote a script that drives
   `NakedEyePerceptionSource` + `DetectionTraceWriter` through `replay.py` over the committed
   fixture with three synthetic objects (one hires-admitted, one presence/class-admitted, one
   range-cap-rejected), producing a real JSONL trace, then ran the actual
   `tools/summarize_detection_trace.py` against it (output above). The mechanism and output shape
   match what `implementation.md` describes; my own numbers differ only because I used different
   synthetic geometry, which is expected and not a discrepancy.

Also confirmed: the two "Decisions Requiring User Input" from the plan (trace-only vs. live view;
flush cadence and default path) are recorded in `implementation.md`'s "Open decisions" section as
picked-but-not-confirmed, not presented as settled.

Re-ran `body-layer`'s full check sequence independently (`cd body-layer`):
- `ruff format --check src tests` — pass
- `ruff check src tests` — pass
- `mypy src` — pass, 37 source files
- `pytest tests -q` — pass, 732 tests

All matches the reported numbers exactly.

### Required Fixes
- **Four non-BL-9 commits are bundled into this feature branch's history**: `6bc7644` (research:
  9K113 sight optics), `860a55a` (research: calibration screenshot manifest), `7e63761` (docs:
  `docs/PROCESS.md` binary-sources rule), and `44a96a0` (chore: `/test-card` skill —
  `.claude/agents/dod.md`, `.claude/skills/test-card/SKILL.md`). None of these touch BL-9's Affected
  Modules; the last one is a skill/config edit, exactly the category `AGENTS.md`'s "Side quests"
  rule names explicitly as needing a disposable `git worktree` on `main`, not the active feature
  branch. `main` is currently at `d22abfe` (the BL-9/detection-cones planning commit), so these four
  commits exist only on `feature/bl9-detection-trace` today. Content-wise none of the four are
  objectionable, but they should land on `main` independently (cherry-pick via a disposable
  worktree) before this branch merges, so BL-9's own history stays scoped to BL-9 and a background
  Architect/Implementer/Reviewer/DoD run on this checkout was never at risk of racing an unrelated
  commit landing in the middle of it.

### Optional Refinements
- The reducer's per-tier "first-admitted range" table could optionally grow a second column pair
  (last-failed range/poll immediately preceding each tier's admission) to literally match the
  plan's own "failed at 3.4, passed at 2.1" phrasing — worth doing only if a real sortie shows the
  current per-tier framing insufficient for debrief, per the implementer's own correctly-scoped
  call not to build it speculatively.
- `world-model/run.sh`, `world-model/syria-full-build.log`, and
  `world-model/syria-theatre-unfiltered.osm.pbf` are untracked in the working tree — unrelated to
  this branch's diff, but `syria-theatre-unfiltered.osm.pbf` is a large raw dataset sitting outside
  `world-model/data/`'s gitignore coverage. Worth a `git status` check before any future commit in
  this checkout accidentally sweeps it in; not this branch's responsibility to fix.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — every changed file in the BL-9 diff was read in full, all five weighted checks were
independently reproduced (not just re-read), and the subproject's full format/lint/type/test
sequence was re-run from a clean shell rather than trusted from the implementer's report.
