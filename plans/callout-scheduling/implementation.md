### Implementation Summary

Implemented `plans/callout-scheduling/plan.md` in full, both slices, as two separate commits on
`feature/callout-scheduling-and-aggregation` so Slice A (the scheduler) stays independently
revertible from Slice B (aggregation) per the task's explicit instruction.

- Slice A (`bd7c150`): `belief.callouts.CalloutScheduler` moves the "what to say" decision to
  speech time. `drain_events` no longer renders/acknowledges every unacknowledged event on every
  poll; it delegates to `scheduler.tick`, which re-reads `store.unacknowledged_events` fresh each
  call, speaks at most one thing, and renders it from current belief the instant it is chosen.
  Occupancy (`busy_until_sim`) is a pure function of sim time and the rendered text
  (`estimate_speech_duration_s`) — never wall clock, keeping replay deterministic. An injected
  urgent call resets occupancy via `note_urgent`, since `AudioPlaybackSender.interrupt` kills
  whatever the scheduler believed was still playing.
- Slice B (`a0b21df`): `belief.callouts.group_candidates` collapses same-`(unit type word, range
  word)` reports within a 30-degree clock span (capped at a 2-hour total chain span) into one
  group, ranked by its best member's priority. `belief.speech.render_group_report` composes the
  group's line from several `describe_contact` results at speech time — no new belief-state
  entity, no persisted group. `CONTACT_CLASSIFICATION_CHANGED` events are never grouped.

### Files Changed
- `body-layer/src/belief/callouts.py` (new) — `CalloutScheduler`, `estimate_speech_duration_s`,
  `callout_priority`, `group_candidates`, `_chain_by_clock`/`_clock_diff`, and the module's five
  new constants (`CALLOUT_MAX_AGE_S`, `INTER_UTTERANCE_GAP_S`, `SPEECH_RATE_WPS`,
  `MIN_UTTERANCE_S`, `CALLOUT_GROUP_CLOCK_SPAN_HOURS`/`CALLOUT_GROUP_MAX_SPAN_HOURS`).
- `body-layer/src/belief/speech.py` — added `render_group_report`; updated the module docstring's
  "No contact clustering" note to point at `belief.callouts` instead of describing group speech as
  out of scope.
- `body-layer/src/belief/crew_console.py` — new `scheduler: CalloutScheduler` field; `drain_events`
  rewritten to delegate to `scheduler.tick`; `_print` gained a required `now_sim` parameter
  (threaded through all 8 call sites) so it can call `scheduler.note_urgent` on the
  `bypass_gate=True` path.
- `body-layer/tests/test_callouts.py` (new) — 16 tests across both slices (see below).
- `.claude/agent-memory/implementer/project_callout_scheduling_stages.md` (new) — the Slice A/B
  split mechanics, the fixture-timing gotcha, and the plan-defect note, for a future implementer
  working the same plan again or a similar split.

### Tests Added
- `test_estimate_speech_duration_s_is_min_plus_words_over_rate` /
  `..._empty_string_is_just_the_floor` — pins the pure duration formula.
- `test_callout_priority_ranks_priority_attention_above_watch_above_normal` /
  `..._ranks_nearer_range_above_farther_at_same_attention` /
  `..._no_relative_now_sorts_last` / `..._ranks_newer_event_above_older_at_same_range` — the four
  tuple keys in isolation.
- `test_nothing_spoken_while_busy_until_sim_is_ahead` — occupancy blocks speech without consuming
  or acknowledging the candidate.
- `test_expired_candidate_is_never_spoken_and_never_acknowledged` — an event past
  `CALLOUT_MAX_AGE_S` is dropped, stays unacknowledged (so a future brain's `poll_events` still
  sees it), and is never re-attempted.
- `test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken` — monkeypatches
  `belief.callouts.describe_contact` to simulate a mid-render vanished contact; asserts the next
  candidate is spoken instead.
- `test_urgent_call_resets_occupancy_even_mid_routine_line` — drives `CrewConsole.handle_line`'s
  `!inject-urgent` path with `scheduler.busy_until_sim` set far in the future; asserts
  `note_urgent` overwrites it.
- `test_mixed_type_pair_does_not_merge` / `test_very_close_never_merges_with_a_kilometre_range` —
  the merge predicate's two negative cases.
- `test_group_never_speaks_an_exact_count_unless_every_member_is_attended_and_exact` — drives
  `render_group_report` directly with hand-built `facts` dicts (the module's established
  pattern), covering both the hedge and the exact-number path.
- `test_group_candidates_never_groups_classification_changed_events` — a same-bucket
  classification-change event stays a singleton group.
- `test_2c_transcript_fixture_renders_four_lines_not_seven` — the headline acceptance test; see
  "Notable Discoveries" for its timing design and the plan-defect it caught.
- `test_replay_is_deterministic` — runs one scripted event stream through a fresh
  store+scheduler twice, asserts byte-identical spoken output.

### Checks
(body-layer/, the only subproject touched)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict, run via `cd body-layer && mypy src` per that subproject's CWD-only config
  discovery): pass, no issues in 40 source files
- `pytest -q`: pass — 858 passed, 4 xfailed (baseline was 842 passed, 4 xfailed; +10 Slice A
  tests, +6 Slice B tests, zero regressions, zero pre-existing xfail count change)

### Notable Discoveries

**A real plan defect (the task explicitly asked to look for a fifth one).** The plan's "Applied to
the sortie transcript" paragraph writes the 3-member infantry group as `"three infantry, 12
o'clock, 0.5 kilometres"`, but the mechanism it explicitly says to reuse
(`speech._cardinality_phrase`, tightened here to require every member both attended and exact
before speaking a number) renders an *unattended* 3-member group identically to an unattended
2-member group: `"a couple of infantry, ..."` — the `lo >= 2 and hi <= 3` branch covers both 2 and
3, and nothing in the sortie scenario marks any contact watched/priority. Implemented per the
actually-reused mechanism (not the plan's prose); `test_2c_transcript_fixture_renders_four_lines_
not_seven` asserts the real output and documents the mismatch in its own docstring.

**The headline test's timing had to be staggered, not bunched.** Building the 7-event fixture with
every event at `t=0` (matching how the transcript reads) and then polling `scheduler.tick` forward
only produced **2** spoken lines, not 4 — the two closest-range candidates (the BTR-70 and truck
identifications, both "very close") consumed the whole occupancy budget back-to-back before the two
infantry groups' shared 10-second deadline (`CALLOUT_MAX_AGE_S`, counted from each event's own
`t_sim`) arrived. This is a real demonstration of the plan's own stated caveat ("do not expect
aggregation alone to hit two") but does not isolate grouping's own effect from that separate
scheduling interaction. Fixed by staggering the founding events over ~18s of sim time (t=0, 4, 8,
12), matching how a real sortie actually produces detections one at a time — each group then gets
spoken well within its own deadline, and the result matches the plan's stated "4, not 2" claim
exactly.

**Test-fixture technique confirmed, not just assumed.** With `project_terrain_aware` monkeypatched
to an identity passthrough (the existing convention in `test_crew_console.py`/`test_speech.py`), a
contact's enriched `relative_now` (clock/range) is driven entirely by its founding observation's
`ownship_at_observation.x/z` against a fixed `EnrichmentContext.ownship` at the origin —
independent of `derived_world_position` (which drives `Contact.last_position`, i.e. spatial-gate
matching). This let every fixture in `test_callouts.py` give contacts exact, controllable clock/
range values while keeping them spatially separate (via far-apart `derived_world_position` values)
regardless of when each was ingested. `bearing_deg(observer, target) = atan2(delta_z, delta_x)`
was confirmed by running a small script before committing to the clock math, not assumed from the
docstring alone.

**No test-impact-list mismatches found.** The plan named `body-layer/tests/test_callouts.py`
(new), `tests/test_crew_console.py` (extend), and `tests/test_speech.py` (extend). In the event,
neither `test_crew_console.py` nor `test_speech.py` needed changes: `_print`'s new `now_sim`
parameter has no existing test calling it directly (grepped for `._print(` in `tests/` first), and
`render_group_report`/the "No contact clustering" docstring update needed no changes to
`test_speech.py`'s existing assertions (all of which exercise single-contact paths untouched by
this plan). All new coverage landed in the new `test_callouts.py` instead — noted here since the
plan predicted edits to files that turned out not to need any, the harmless direction of mismatch
per the role's own "missing entry is the dangerous one" guidance, but worth recording so it is not
mistaken for a gap next time.
