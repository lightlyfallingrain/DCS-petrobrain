### Implementation Summary

All five stages implemented, in the plan's own order, one commit per stage (per the "mechanism and
calibration never share a commit" rule, and Stage 3's own 3a/3b/3c split). Two orchestrator-level
corrections to stale plan text were verified and applied: `body-layer/data/threat_envelopes.json`
was already committed and tracked on `main` (no re-extraction needed), and `OP_LRSAM` was already
folded into `crew_console._AIR_DEFENCE_OP_CLASSES` with its own guard test (kept passing throughout,
untouched).

### Files Changed

**Stage 1 — watched contacts report their movement**
- `body-layer/src/belief/speech.py` — `_contact_report_text` gains optional `lead`/`event_clause`
  affixes; `_render_lifecycle_text` gains a `CONTACT_MOTION_CHANGED` branch.
- `body-layer/src/belief/callouts.py` — `_WATCHED_ONLY_KINDS`, `WATCH_REPORT_MIN_GAP_S`,
  `CalloutScheduler._last_spoken_sim`; the watched-attention + min-gap check in `tick`'s `live`
  filter; watched-only kinds forced singleton in `group_candidates` (a decision the plan's prose
  didn't spell out explicitly but is required: these kinds render via affixes `render_group_report`
  has no concept of).

**Stage 2 — kilometre range crossings**
- `body-layer/src/belief/events.py` — `CONTACT_RANGE_CROSSED` kind, `Event.previous_range_km`/
  `range_km`.
- `body-layer/src/belief/position_belief.py` — `PositionEstimate.range_uncertainty_m`
  (`bearing_uncertainty_deg`'s down-range mirror).
- `body-layer/src/belief/contacts.py` — `WATCH_RANGE_REPORT_MAX_KM`/`RANGE_CROSS_MIN_DEADBAND_M`/
  `RANGE_CROSS_MAX_SIGMA_M`; `Contact.last_announced_range_km`; `tick` gains `ownship` and the
  sixth block.
- `body-layer/src/belief/speech.py`, `callouts.py` — `CONTACT_RANGE_CROSSED` rendering/gating.
- `body-layer/src/logger.py` — `store.tick(ownship=ownship)`.

**Stage 3a — `follow` as a `watch` synonym**
- `audio-adapter/src/vocabulary.py` — phrasings only, no token/matcher change.

**Stage 3b — `bearing_degrees` → `slots` migration**
- `audio-adapter/src/command_matcher.py`, `transcript_queue.py`, `server.py`.
- `body-layer/src/belief/voice_commands.py`, `crew_console.py`, `logger.py`.

**Stage 3c — the `follow` resolver**
- `audio-adapter/src/vocabulary.py` — `follow` token, `parse_clock`/`parse_range_km`/
  `parse_descriptor`, `DESCRIPTOR_WORDS`.
- `audio-adapter/src/command_matcher.py` — the follow-slot path, tried **before** the generic
  phrase table (not after, as a naive fallback reading of the plan might suggest — see Notable
  Discoveries).
- `body-layer/src/belief/speech.py` — `render_no_contact`.
- `body-layer/src/belief/crew_console.py` — `_resolve_follow_target`, `_descriptor_score`,
  `_handle_follow`, `_clock_delta`, the `W_FOLLOW_*`/`FOLLOW_MATCH_FLOOR`/`FOLLOW_SEPARATION`
  constants, `_parse_follow_slots_for_harness` (a harness-only re-parse for the `!voice` command,
  see Notable Discoveries), `DISPATCHED_COMMAND_TOKENS`/`_describe_token_for_confirm` updates.

**Stage 4 — engagement envelopes**
- `body-layer/src/belief/threat.py` — **new module**: loads `body-layer/data/threat_envelopes.json`
  (already committed), `envelope_for(ClassificationBelief) -> EngagementEnvelope | None`, the
  class-level rollup derived via `perception.object_model.profile_for`, per-field null handling
  (4f-i).
- `body-layer/src/belief/decay.py` — `LOS_MASK_CONFIRM_S`.
- `body-layer/src/belief/events.py` — `CONTACT_ENGAGEMENT_CHANGED`, `Event.previous_engaged`/
  `engaged`.
- `body-layer/src/belief/contacts.py` — `ENGAGEMENT_LEAVING_HYSTERESIS`,
  `LOS_UNCERTAINTY_SAMPLES`, `_threat_has_los`; `Contact.last_emitted_engagement`/
  `los_masked_since_sim`; `tick` gains `los_clear` and the seventh block.
- `body-layer/src/belief/speech.py`, `callouts.py` — `CONTACT_ENGAGEMENT_CHANGED` rendering/gating.
- `body-layer/src/logger.py` — the `los_clear` closure over `world_model_conn`/`theatre`.

**Stage 5 — prose and roadmap**
- `docs/concept/STATE_TRANSITIONS.md`, `body-layer/ROADMAP.md`, root `ROADMAP.md`, `todo/todo.md`.

### Tests Added

- `body-layer/tests/test_speech.py` — `_contact_report_text` affixes; `CONTACT_MOTION_CHANGED`/
  `CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_CHANGED` rendering and auto-acknowledge.
- `body-layer/tests/test_callouts.py` — watched-only gating, `WATCH_REPORT_MIN_GAP_S`, and one
  end-to-end test per new watched-only kind (each needed a multi-tick fixture to avoid colliding
  with `CONTACT_DETECTED`/an earlier watched-only kind sharing the scheduler's tie-break — see
  Notable Discoveries).
- `body-layer/tests/test_position_belief.py` — `range_uncertainty_m`, mirroring the existing
  `bearing_uncertainty_deg` tests.
- `body-layer/tests/test_contacts.py` — 10 range-crossing tests (seed, cap, deadband, freshness
  gate, sigma ceiling, opening/closing, clear-on-unwatch) and 9 engagement tests (immediate-entry
  seeding, unwatched/no-envelope no-ops, 1.5x hysteresis, altitude floor, LOS dwell + reset,
  clear-on-unwatch, `ownship=None` no-op).
- `body-layer/tests/test_threat.py` — new file, 11 tests against the **real**
  `threat_envelopes.json` payload (not a fixture double): level gating, type/class resolution,
  the SA-5 drop and SA-2 null-asymmetry cases from the plan's own worked examples, the
  no-`perception.source`-import guard, the provenance header.
- `audio-adapter/tests/test_command_matcher.py` — `follow` synonym tests; `bearing_degrees` →
  `slots` migration; the full follow-slot resolution suite (all-three-slots, each slot alone, bare
  `follow`, the `follow nearest` collision case, no-recognisable-slots).
- `audio-adapter/tests/test_vocabulary.py` — `parse_clock`/`parse_range_km`/`parse_descriptor`.
- `audio-adapter/tests/test_transcribe_api.py` — `slots` wire migration.
- `body-layer/tests/test_crew_console.py` — 10 `follow` tests (descriptor/clock resolution,
  no-qualifiers say-again, match-floor rejection with both wordings, unclassified-contact soft
  match, `"group"` descriptor, confirm-round-trip survival) plus
  `_describe_token_for_confirm("follow", ...)`.
- `body-layer/tests/test_logger.py` — `slots` threading and malformed-shape rejection through
  `_poll_transcripts` (extends the existing `bearing_degrees` regression tests rather than
  replacing their intent).

### Checks

**body-layer/** (from `cd body-layer`)
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass, 48 source files
- `pytest tests -q`: pass, 1174 passed, 4 xfailed (baseline was 1113 passed, 4 xfailed)

**audio-adapter/** (from `cd audio-adapter`)
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass, 15 source files
- `pytest tests -q`: pass, 198 passed, 1 skipped (skip is the pre-existing whisper-binary gate,
  unrelated to this work)

No other subproject was touched.

### Notable Discoveries

- **A defect the plan's own prose does not name: watched-only kinds must be forced singleton in
  `group_candidates`, exactly like `CONTACT_CLASSIFICATION_CHANGED`.** These kinds render through
  `_contact_report_text`'s `event_clause`/`lead` affixes, which `render_group_report` has no
  concept of — merging a motion/range/engagement event into a multi-contact group would silently
  drop the very fact the event exists to report. Fixed in Stage 1, carried through Stages 2 and 4
  by construction (both add to the same `_WATCHED_ONLY_KINDS` set the singleton check reads).

- **`follow`'s slot resolution has to run *before* the generic phrase table, not after, as a plain
  reading of "fallback" might suggest.** A clock-only `"follow two o'clock"` scores highly against
  `"report two o'clock"`/`"scan two o'clock"` under the existing word-sequence matcher (only the
  verb differs, and `"follow"` anchors as a verb same as `"report"`/`"scan"` do) — reordering the
  slot attempt ahead of the phrase table, gated only on the verb fuzzy-matching `"follow"`, avoids
  the collision while leaving `"follow nearest"`/`"follow nearest air defence"`/bare `"follow"`
  (which parse to zero slots) to fall through to the ordinary phrase table unchanged.

- **`_resolve_follow_target`'s constants needed one iteration to be internally consistent.**
  `W_FOLLOW_CLOCK`/`FOLLOW_MATCH_FLOOR` must satisfy "a maximal single-qualifier miss can clear the
  floor on its own" (Decision 2b-iii's own "watching the least-bad candidate is worse than
  admitting no match") — an initial `FOLLOW_MATCH_FLOOR=5.0`/`W_FOLLOW_CLOCK=0.5` pairing made this
  impossible (max clock-only score 3.0 < floor 5.0, so a clock-only `follow` could never be
  refused), caught by a test built around the worst-case clock delta rather than an arbitrary one.
  Landed at `FOLLOW_MATCH_FLOOR=3.0`/`W_FOLLOW_CLOCK=0.6` (max clock-only score 3.6). Both remain
  explicitly disposable guesses per the plan's own framing — this is a self-consistency fix, not a
  calibration.

- **Testing the watched-only kinds against real `ContactStore.tick` runs required "move the
  observer, not the target" fixtures throughout, not just for range-crossing.** A first attempt at
  the engagement hysteresis/collision tests re-ingested new observations at each new range, which
  the percept-gate correctly rejected as too large a jump for the same contact (founding a *second*
  contact instead) — silently invalidating the test's premise without an assertion failure pointing
  at the real cause. Every multi-step engagement/range test instead founds one contact and varies
  only the `ownship=` argument passed to successive `tick()` calls, mirroring the pattern
  `test_range_crossing_*` already established in Stage 2.

- **The class-level threat rollup's join rate against the real table is low (3 of ~19 SAM/AAA
  rows), not a bug in the join mechanism.** `object_model.profile_for`'s keyword table was authored
  against DCS unit names, not the Hoggit wiki's own naming (`"2K12 Kub"` vs. the keyword `"kub "`
  with a trailing space that never matches at end-of-string, `"9K331 Tor"` vs. `"tor 9a331"`,
  etc.). Type-level lookups are unaffected (they match directly against the same table). Recorded
  as a `body-layer/ROADMAP.md` backlog item rather than patched here, per Decision 4c's own explicit
  instruction not to hand-write a per-class number — the fix belongs in `object_model.py`'s keyword
  coverage, a different module's job.

- **`FOLLOW_MATCH_FLOOR`/weights aside, no other plan number needed correction.** Every other
  measured constant, null-handling rule, and worked example in the plan (the SA-2/SA-5 cases, the
  altitude-floor category split, the 1.5x hysteresis, the LOS uncertainty sweep, the SHORAD
  recognition-range arithmetic) held exactly as written once implemented and tested against the
  real payload.
