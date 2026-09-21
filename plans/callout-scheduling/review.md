### Review Summary

Branch: `feature/callout-scheduling-and-aggregation` (commits `48f182a` plan, `63e2d12` Slice A,
`d84f0b9` Slice B, `934cadd` implementation notes). Reviewed against
`plans/callout-scheduling/plan.md` and `CLAUDE.md`.

Re-ran the full body-layer verification sequence directly (not trusting the implementer's report):
`ruff format --check`, `ruff check`, `mypy src` (strict, `cd body-layer && mypy src`), and
`pytest tests -q` all pass — 858 passed, 4 xfailed, matching the reported numbers exactly.

Checked each of the six priorities called out for this review, plus the standard checklist:

1. **Replay determinism** — confirmed by direct inspection: `callouts.py` contains no
   `time.time()`/wall-clock/thread/I-O access; `busy_until_sim` is only ever advanced by
   `now_sim + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S` (a pure function of the
   rendered string) or reset by `note_urgent(now_sim, text)`, both sim-time-only. `test_replay_is_
   deterministic` (run twice, byte-identical output) passes.
2. **Staleness fix holds** — traced `unacknowledged_events -> group_candidates -> describe_contact
   (scoring) -> _render_group -> describe_contact/route_event (render)`. No pre-rendered text is
   cached anywhere; every candidate is rendered from belief fresh in the same `tick()` call that
   speaks it. Confirmed structurally, not just by the passing tests.
3. **Aggregation never swallows an identification** — `CONTACT_CLASSIFICATION_CHANGED` is a
   hard-coded singleton case in `group_candidates` (checked first, before any bucketing).
   Hand-verified the merge/chain-cap boundary directly against the running code (not just the
   fixture): a 2-hour clock gap correctly fails to merge, a 4-member adjacent chain (12,1,2,3)
   correctly splits into `[12,1,2]`/`[3]` at the `CALLOUT_GROUP_MAX_SPAN_HOURS=2` cap, and a 1-hour
   gap correctly merges. All three match the plan's stated rule. `test_mixed_type_pair_does_not_
   merge` and `test_very_close_never_merges_with_a_kilometre_range` cover the two negative word
   cases in the test suite itself.
4. **perception/belief boundary** — grepped both `callouts.py` and `speech.py`'s import lists:
   neither imports anything from `perception.clustering`; `ClusterCandidate` is mentioned only in
   docstring prose explaining why it is *not* imported. Boundary holds.
5. **Plan defect (worked example says "three infantry", mechanism renders "a couple of
   infantry")** — verified by reading `_cardinality_phrase` and `render_group_report` directly:
   an unattended 3-member group's interval `(3, 3)` hits the `lo >= 2 and hi <= 3` branch, same as
   a 2-member group, so it genuinely renders `"a couple of infantry"`, not `"three infantry"`. The
   implementer followed the actual reused mechanism over the plan's prose, which is the right call
   — inventing a new branch to match the plan's worked example would have meant a second,
   parallel cardinality-phrasing path solely to satisfy prose that was itself wrong. Note this
   `lo>=2 and hi<=3 -> "a couple of"` bucket is pre-existing behavior from `group-contact-model`
   (Stage 4b), not introduced by this feature — this feature only newly exposes it through
   aggregation. Whether "a couple" is the ideal word for 3 is a pre-existing wording judgment call,
   not a regression; flagged below as optional, not blocking.
6. **`SPEECH_RATE_WPS`/`MIN_UTTERANCE_S` calibration status** — both constants carry explicit
   `"**Uncalibrated -- needs a live sortie.**"` docstring comments in `callouts.py`, in the same
   style as `perception/optics.py`'s per-field provenance comments, and the plan's own "Risks &
   Unknowns" section names this as the one real guess. Confirmed present, not just claimed.

**Headline test honesty** — read `test_2c_transcript_fixture_renders_four_lines_not_seven` in
full, including its own docstring explaining the bunched-at-t=0 attempt that produced only 2 lines
and why staggering (t=0/4/8/12, matching how a sortie actually produces detections one at a time)
was chosen instead. This is a legitimate reproduction of realistic pacing, not a fixture tuned
until it produced the wanted number — the docstring documents the discarded first attempt and
why it was rejected, which is exactly the honesty this priority asked me to check for.

### Required Fixes

None. No invariant violation, no staleness gap, no scope creep (`perception/`, `decay.py`,
`gaze.py` untouched — confirmed via `git diff --stat`), no misplaced responsibility.

### Optional Refinements

- **No dedicated unit test for the clock-merge boundary or the chaining cap** (exactly
  `CALLOUT_GROUP_CLOCK_SPAN_HOURS` apart merging, more than that failing to merge, or a chain
  exceeding `CALLOUT_GROUP_MAX_SPAN_HOURS` splitting). I hand-verified all three directly against
  `_chain_by_clock` and they are correct, but the only place this is currently exercised
  end-to-end is incidentally, inside the much larger headline transcript fixture (12/1 o'clock
  merging). A few small direct tests on `_chain_by_clock` would make this boundary explicit and
  regression-proof rather than resting on one large fixture continuing to happen to cover it.
- **`test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken`'s assertion is a
  tautology**: `assert vanished_id not in unacked_ids or live_id not in unacked_ids` is always
  true given the very next line (`assert live_id not in {...}`) already establishes the right
  disjunct. Harmless, but doesn't test what its comment claims ("the vanished candidate's event
  was consumed") — that would need `assert vanished_id in unacked_ids` (still present, unacked) or
  an equivalent direct check against `scheduler._consumed`.
- **`ROADMAP.md`/`todo/todo.md` not yet updated** — the plan explicitly scopes this as "tick the
  two 2C findings when this merges," so this is correctly deferred rather than missing; flagging
  only so DoD/merge doesn't skip it, per this project's recurring pattern of merges landing without
  the roadmap entry.
- **Readback speech (F10 command confirmations, `watch`/`ignore` acknowledgements, `say_again`,
  etc.) does not update `scheduler.busy_until_sim`.** Only `drain_events`-sourced scheduler output
  and `note_urgent` touch occupancy. A readback and a scheduled callout can therefore still queue
  back-to-back in the downstream audio FIFO without the scheduler modeling that overlap. This does
  not reintroduce staleness (nothing is pre-rendered either way) and is consistent with the plan's
  own accepted "annoying, not stale" slack around duration-estimate drift, so it's not a fix — just
  worth a line in `callouts.py` or `crew_console.py` acknowledging it's an accepted gap, the same
  way the other placeholder constants are documented, so a future reader doesn't have to
  rediscover it.
- **Priority scoring calls `describe_contact` twice for a chosen candidate** (once during the
  `scored` ranking pass, once more inside `_render_group`/`route_event`). Not a performance
  concern at sortie scale (the plan's own "Risks" section already accepts the unbounded
  `unacknowledged_events` scan as fine at sortie length), just a minor duplication that a future
  refactor could fold into one pass if this module is revisited for another reason.

### Verdict
APPROVED

### Review Confidence
Full read — plan, implementation.md, both new/changed source files (`callouts.py` in full,
`speech.py`'s new/changed sections, the full `crew_console.py` diff) and the full `test_callouts.py`
test file. Re-ran `ruff format --check`, `ruff check`, `mypy src`, and `pytest tests -q` directly
against the feature branch (not trusted from the implementation report). Independently
hand-verified the clock-merge/chain-cap boundary and the perception/belief import boundary against
the running code rather than relying on the test suite alone.
