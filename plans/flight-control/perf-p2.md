### Performance Review

Batch: BL-16 Stage P2 (voice goals for heading/altitude/speed with rotation, plus HVRT
translate). Diff reviewed: `370f37c0..09d25186` (three-dot against `main`, merges of `main`
excluded). Reviewer has approved, including the re-review (`plans/flight-control/review-p2.md`).
Builds on the posture `perf-batch-a.md`/`perf-takeover.md` established: per-frame `Export.lua`
work is only what must be per-frame, one `list_indication(6)` read per 5 Hz tick serves every
consumer, and a wire command is sent only on a sequence/content change.

### Findings

#### `ai_pilot_goal_tick`/`ai_pilot_goal_tick_hvrt` run at the 5 Hz gate, not per frame — mitigation held

- **Location:** `aircraft-layer/dcs-export/Export.lua:413` calls
  `ai_pilot_wheel.update_ai_pilot_wheel_overlay(helperai_raw, t)` only inside the `core.tick_due(t)`
  block (line 390), using the one `helperai_raw` read shared with `petrovich.push_indication`'s
  own consumer at line 401-404 — confirmed by reading the call site, not inferred from a comment.
  `ai_pilot_wheel.lua`'s `update_ai_pilot_wheel_overlay` (line 1202) is what calls
  `ai_pilot_goal_tick(t)` (line 1284, guarded `not fields_all_nil`) and
  `ai_pilot_goal_tick_hvrt(t)` (line 1286, unconditional). `run_ai_pilot_wheel` (line 1027, called
  every frame at `Export.lua:388`) contains none of the new P2 goal logic — only the shared
  press-release deadline check (now covering both the takeover pair and the new
  `ai_wheel_goal_pending_cmd`/`_release_t` pair) and the pre-existing per-frame seat/park reads.
- **Risk:** none. This is exactly the shape `perf-batch-a.md` required and `perf-takeover.md`
  confirmed held through the takeover revision — device read decoupled from frame rate, every new
  P2 consumer riding the same 5 Hz tick rather than reintroducing a per-frame `list_indication`
  call. The `perf-batch-a.md` MONITOR item ("P2's 'release when readback reaches target' — don't
  re-introduce the per-frame pattern") is resolved: P2 did not reinstate per-frame overlay reads.
- **Action:** none (confirms prior mitigation still holds, for the new tick functions too).

#### Goal-channel wire send — gated on `goal_seq` change, not per poll

- **Location:** `body-layer/src/body.py:3360-3377` (`_apply_ai_pilot_wheel_goal`): `final_goal`'s
  `goal_seq` is compared against `runner.ai_pilot_goal_last_sent_seq`, and
  `aircraft_client.write_ai_pilot_goal(...)` is called only when they differ, mirroring
  `write_sight_target`'s existing "send on change" posture named in the plan. The `hvrt_step`
  one-shot send (lines 3385-3404) is a deliberate, documented exception — it always sends because
  it is a one-shot trigger acted on exactly once per distinct `goal_seq`, not a continuous target;
  it still only fires when `crew_console.ai_pilot_hvrt_step_transition is not None`, i.e. on an
  actual spoken step command, not every poll.
- **Risk:** none. The orchestrator's named concern (send rate should be gated on `goal_seq`
  change) is met by construction, checked against the real code rather than the docstring's
  claim. `decide_ai_pilot_wheel`/`request_goal`/`set_parked_*` are all pure `dataclasses.replace`
  calls on a small (8-field) frozen dataclass with a `pending_order` tuple bounded at 3 elements
  (heading/altitude/speed) — no loop over a collection, no per-poll allocation beyond that one
  small object, same cost class `perf-batch-a.md` already cleared for this endpoint's sibling
  reads.
- **Action:** none.

#### `send_ai_pilot_goal`/`handle_ai_pilot_goal_command` — one bounded message, no new allocation shape

- **Location:** `aircraft-layer/src/collector/command_sender.py:233-322` (`json.dumps` of a
  fixed 9-key dict, one `sendto`), `ai_pilot_wheel.lua:1302-1354`
  (`handle_ai_pilot_goal_command`, six `extract_json_*_field` calls plus one `hvrt_step` branch).
- **Risk:** none. Fixed-shape message, no iteration, same cost class as the pre-existing
  `send_sight_target`/`send_cockpit_switch` ops this plan explicitly follows as precedent.
- **Action:** none.

#### audio-adapter's HVRT bare-word exact-match pre-check — O(1) dict lookup, correctly scoped

- **Location:** `audio-adapter/src/command_matcher.py:910-917` (`match_transcript`): `if
  len(words) == 1 and words[0] in _HVRT_BARE_WORD_TOKENS: return ...` — a 7-entry `dict` literal
  (module-level constant, not rebuilt per call), checked before the fuzzy verb-anchor branch.
- **Risk:** none. The `len(words) == 1` guard means this adds one list-length check plus (only on
  single-word transcripts) one dict lookup ahead of the existing fuzzy-matching pipeline every
  other utterance already runs through `match_transcript` once per recognised transcript (a
  human-speech-rate event, not a per-frame or per-poll path) — the cheapest possible pre-check,
  not a new scan over anything. The six new slotted branches added lower in `match_transcript`
  (`turn_heading`, `turn_heading_relative`, `set_speed`, `speed_step`, `set_altitude`,
  `altitude_step`) each cost one `difflib.SequenceMatcher(...).ratio()` call against the verb
  only (not the whole transcript) before their own slot parser runs — the same per-branch cost
  shape every existing slotted token in this function already has; this function's cost already
  scales with the number of distinct verb branches, not with any dataset, and six more branches
  on an utterance-rate path is not a credible scale risk at this project's phase.
- **Action:** none.

#### Heading hold-and-poll at 5 Hz against the measured course press rate — checked, not assumed

- **Location:** `ai_pilot_goal_tick_heading` (`ai_pilot_wheel.lua:801-814`), released within
  `AI_PILOT_HEADING_TOLERANCE_DEG` (5°), checked once per 5 Hz tick — the same hold-and-poll
  shape `perf-takeover.md` already measured-cleared for altitude, now reused for a second
  parameter. `.claude/agent-memory/performance-reviewer/
  project_bl16_held_press_5hz_tolerance_check.md` flags this exact check as owed for "Stage P2's
  own heading/speed holds."
- **Check performed:** the plan's own P0-2 measurement (`plans/flight-control/plan.md` line 803):
  "0.7 s reliably reads as long (altitude ±4 m, course ±2° per hold)" — a held press moves course
  ≈2° per 0.7 s ≈ 2.9°/s. One 5 Hz tick (0.2 s) therefore moves the held heading ≈0.57° in the
  worst case. That is well inside the 5° tolerance band (same arithmetic shape as the altitude
  check: step size smaller than the band means the loop cannot skip over the band in one tick
  approaching from outside it). Speed is not a hold at all (`ai_pilot_goal_tick_speed`, a single
  tap per tick, no accumulating press), so the same question does not apply there — P0-4's
  measured ~0.007 s readback latency (cited in the plan) means a tap's effect is visible well
  within the next 5 Hz tick regardless.
- **Risk:** none credible, now checked rather than assumed. Noted for completeness since a prior
  memory named this exact gap for P2.
- **Action:** none (MONITOR item closed by this arithmetic check; re-open only if a live Flight
  P2a test shows visible heading overshoot).

### Verdict
APPROVED
