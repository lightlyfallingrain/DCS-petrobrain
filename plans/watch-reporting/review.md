### Review Summary

Reviewed `feature/watch-reporting` (head `0b1e394`, branched from `main` at `3409b66`) against
`plans/watch-reporting/plan.md` and root/subproject `CLAUDE.md`. Read the plan in full (1030
lines), the implementer's `implementation.md`, and the actual diff for every module the plan
names as affected — `belief/threat.py`, `belief/contacts.py`'s sixth/seventh blocks,
`belief/callouts.py`, `belief/speech.py`, `belief/crew_console.py`, `belief/voice_commands.py`,
`belief/position_belief.py`, `audio-adapter/src/command_matcher.py` and `vocabulary.py`,
`transcript_queue.py`/`server.py`, `logger.py`, and the two `ROADMAP.md`s / `STATE_TRANSITIONS.md`
/ `todo/todo.md`.

**All four flagged judgement calls verified against the code, not the implementer's summary:**

1. **Watched-only kinds forced singleton in `group_candidates`.** Confirmed:
   `_WATCHED_ONLY_KINDS` (`CONTACT_MOTION_CHANGED`, `CONTACT_RANGE_CROSSED`,
   `CONTACT_ENGAGEMENT_CHANGED`) is checked in `group_candidates` right alongside
   `CONTACT_CLASSIFICATION_CHANGED` and routed to `singles` before the facts-bucketing path ever
   runs (`callouts.py` ~line 419). A singleton group of length 1 goes through
   `CalloutScheduler._render_group` → `route_event` → `_render_lifecycle_text`, which does have a
   branch for each of the three kinds using the `lead`/`event_clause` affixes — so these events are
   spoken, not silently dropped. The gating happens twice, correctly: attention/min-gap is checked
   earlier in `tick`'s `live` filter (before `group_candidates` is even called), and the singleton
   force in `group_candidates` is what stops them being merged into a multi-contact line that
   `render_group_report` has no affix mechanism for.

2. **`follow`'s slot parsing runs before the generic phrase table.** Confirmed in
   `command_matcher.match_transcript`: the `follow`-verb fuzzy-anchor check and
   `_parse_follow_slots` call sit textually and behaviourally before the `_PHRASE_WORDS` scoring
   loop. Checked the claimed collision is real (`"follow two o'clock"` vs. `"report two
   o'clock"`/`"scan two o'clock"` — only the verb token differs in the phrase table, so it's a
   genuine word-sequence collision) and that reordering doesn't shadow anything: `"follow
   nearest"`/`"follow nearest air defence"`/bare `"follow"` parse to zero slots (`"nearest"`/`"air"`/
   `"defence"` are not in `DESCRIPTOR_WORDS`, and no clock/range unit words are present), so
   `_parse_follow_slots` returns `None` and those phrasings correctly fall through to the ordinary
   phrase table unchanged.

3. **`FOLLOW_MATCH_FLOOR = 3.0` / `W_FOLLOW_CLOCK = 0.6`.** Confirmed self-consistent: max clock-only
   score is `_clock_delta` worst case (6) × 0.6 = 3.6, which is `> FOLLOW_MATCH_FLOOR` and is
   therefore correctly refused (`_resolve_follow_target`'s `best_score > FOLLOW_MATCH_FLOOR` check,
   strict `>`). `W_FOLLOW_DESC_WRONG = 10.0` always refuses alone by a wide margin, as documented.
   The constants carry their own "disposable guess" framing in-line, matching the plan's
   instruction not to let them read as calibrated.

4. **The class-level rollup's ~3-of-19 join rate — consequence check.** Confirmed `threat.py`'s
   `envelope_for` degrades honestly: a `CLASS`-level classification whose `op_class` has no
   surviving row in `_CLASS_ENVELOPES` (dict `.get`, no default) returns `None`. In `contacts.py`'s
   seventh block, `envelope is None` unconditionally clears `last_emitted_engagement`/
   `los_masked_since_sim` and skips the whole engagement test — no danger/safe-from call, ever, for
   that contact. This is silence, not a wrong default in either direction (no under-claim via a
   too-short envelope, no over-claim via a fabricated one). Matches the implementer's claim exactly.

**Stage 3b `bearing_degrees` → `slots` migration.** Traced the full round trip:
`command_matcher.MatchResult.slots` → `transcript_queue`/`server.py`'s wire `to_dict`/reconstruction
→ `logger._poll_transcripts` (defensively validates shape) → `CrewConsole.handle_transcript`'s
`slots` parameter → `_act_on_voice_decision`'s `confirm` branch constructs
`PendingConfirmation(..., slots=slots)` → on `"affirm"`, `handle_transcript` calls
`self.handle_command(pending.token, now_sim, slots=pending.slots)`. All three `follow` qualifiers
(and the pre-existing `bearing_degrees`) survive a confirm-band round trip — the exact regression
the plan called out as "the specific way this breaks" if `PendingConfirmation.slots` were missing.
It is present and wired correctly.

**No-omniscience boundary (`belief/threat.py`).** `envelope_for` takes only a `ClassificationBelief`
and imports nothing from `perception.source`; verified by reading the module's imports directly
(`belief.classification`, `perception.object_model` only). `UNKNOWN`/`PRESENCE` → `None` before any
lookup runs. The `ownship` parameter threaded into `ContactStore.tick` supplies only
position/AGL/heading (`OwnshipState`), consumed for range/altitude/LOS geometry against *believed*
contact position — never fed into the classification lookup. No path from `tick`'s new parameters
to ground truth reaching `threat.py`.

**Decision 5a-i deadband / 5a-ii LOS dwell.** Read both blocks in `contacts.py` directly (not just
tested behaviour): the kilometre-boundary deadband is computed from
`contact.position.range_uncertainty_m(observer)`, floored at 50 m, and the crossing test compares
`abs(range_m_value - boundary_km * 1000.0)` against it — correct Schmitt-trigger shape, and
`last_announced_range_km` is only advanced once the deadband is actually cleared, which is what
prevents flip-flopping. The `RANGE_CROSS_MAX_SIGMA_M` ceiling suppresses the whole crossing test
before the deadband math runs. The LOS asymmetric dwell (`LOS_MASK_CONFIRM_S`, fail-open) matches
the plan's 5a-ii exactly: a clear verdict takes effect immediately, a masked verdict only clears a
standing danger state after holding continuously.

**Scope.** No files touched outside the plan's Affected Modules list. `perception/*` is untouched
except for `threat.py`'s read of `perception.object_model` (the legal direction, per the plan). No
`world-model/data/`-class artifacts staged. The provenance JSON (`threat_envelopes.json`) was
already committed on `main` prior to this branch, matching the implementer's stated verification
that 4g's blocking condition was already satisfied.

**Tests.** Read (not just counted) `test_threat.py`'s use of the real `threat_envelopes.json`
payload rather than a fixture double — this is the right call for a rollup that is entirely a
function of the shipped data file; a fixture would not have caught the low class-join-rate finding
the implementer recorded as backlog. `test_contacts.py`'s range-crossing/engagement tests move
`ownship` across successive `tick()` calls rather than re-ingesting new observations at each step —
confirmed this avoids founding a second contact via the percept gate, which is a real and
non-obvious test-construction trap for this shape of test.

**One process-level observation, not a code defect.** `body-layer/ROADMAP.md`'s Status table and
root `ROADMAP.md`'s entry, committed as part of Stage 5 on this feature branch, already say
"merged 2026-09-24" / "DONE" — written ahead of the actual merge, which per `AGENTS.md`/CLAUDE.md
workflow only happens after Reviewer + DoD + user approval. Not a required fix (this is this
project's established pattern of writing roadmap prose alongside the final stage rather than in a
separate post-merge commit, and it will be true by the time this branch actually merges), but
flagged so it isn't read as a factual claim if this review sends anything back to Implementer.

### Required Fixes

None found.

### Optional Refinements

- `body-layer/ROADMAP.md` / root `ROADMAP.md` say "merged"/"DONE" while committed on the
  not-yet-merged feature branch (see above). Harmless once merged; if this branch ever needs a
  revision round before merge, reword to avoid a stale "done" claim sitting on `main` history at
  the wrong commit. (Optional — cosmetic, self-correcting at merge time.)

### Verdict

APPROVED

### Review Confidence

Full read. Read the plan in full, the implementation log, and the actual source for every item the
orchestrator asked to be checked specifically (all four judgement calls, the slots migration, the
no-omniscience guard in `threat.py`, the 5a-i/5a-ii amendments), plus a scope/TODO sweep over every
non-test source file changed by the branch. Did not re-run `ruff`/`mypy`/`pytest` myself (the
orchestrator had already run and reported all four commands in both touched subprojects passing,
and this worktree does not carry a functioning `.venv` for either subproject — verification instead
consisted of reading the exact code paths each of the orchestrator's specific claims depends on).
