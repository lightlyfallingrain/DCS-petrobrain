### Implementation Summary

Implemented both backlog items in the decided build order: BL-B82 (no scanning on the ground,
replacing the on-ground silence default) then BL-B81 (radio check / greeting), per
`body-layer/ROADMAP/BL-B82.md` / `BL-B81.md` and `plans/radio-check/plan.md`.

### Files Changed

- `body-layer/src/belief/crew_console.py` —
  - Removed `CrewConsole.maybe_apply_on_ground_default`/`_on_ground_default_applied` (and the
    module docstring paragraph describing it); added `on_ground: bool` field, refreshed every
    poll the same way `enrichment` is.
  - Added `_LOOK_COMMAND_TOKENS` (every scan token + `watch_nearest`/`watch_nearest_air_defence`/
    `follow`) and a `handle_command` branch: `self.on_ground and token in _LOOK_COMMAND_TOKENS` ->
    `render_unable("ON_GROUND")`, placed after the silence-ends-on-any-command reset (so a
    refused-on-the-ground look command still ends silence) and after the world-model refusal
    check (refusal still wins).
  - Added `radio_check`/`greeting` to `DISPATCHED_COMMAND_TOKENS`, dispatch branches in
    `handle_command`, and `_handle_radio_check`/`_handle_greeting` handlers.
  - Added `_RADIO_CHECK_PATTERN`/`_GREETING_PATTERN`/`_GREETING_TIMES_OF_DAY` and
    `_match_radio_check_or_greeting`; `handle_line` now checks it (same position as the existing
    `!inject-urgent`/`!voice` special cases) and routes a match straight to `handle_command`.
  - `reset_for_new_mission`'s docstring updated for the field swap.
- `body-layer/src/belief/speech.py` — `render_radio_check`, `render_greeting`
  (`_GREETING_TEMPLATES`), and `_UNABLE_TEMPLATES["ON_GROUND"] = "Unable, on the ground."`.
- `body-layer/src/logger.py` —
  - `PerceptionLogger.run_once` and `ConsolePerceptionRunner.run_once`: the single
    `[observation for source in self.sources for observation in source.poll(...)]`
    comprehension in each is now gated on `ownship.alt_agl_m > ON_GROUND_AGL_THRESHOLD_M`,
    else `[]`. `ContactStore.tick`/`store.ingest([], ...)` still run unconditionally, so existing
    belief keeps decaying normally — Petrovich just stops adding anything new to it while on the
    ground. This is the "cleanest seam" the plan called for: one gate per poll loop, no change to
    any individual `PerceptionSource`.
  - The old `crew_console.maybe_apply_on_ground_default(runner.last_ownship_state)` call site is
    now `crew_console.on_ground = runner.last_ownship_state.alt_agl_m <=
    ON_GROUND_AGL_THRESHOLD_M`, refreshed every poll (not a one-shot latch) at the same point
    `crew_console.enrichment` is refreshed.
  - `ON_GROUND_AGL_THRESHOLD_M` imported from `belief.crew_console`.
- `body-layer/tests/test_crew_console.py` — removed the `maybe_apply_on_ground_default` test
  block; added look-command/on-ground/radio-check/greeting tests (below).
- `body-layer/tests/test_logger.py` — added on-ground perception-gating tests for both poll
  loops (below).
- `plans/radio-check/plan.md` — the implementation plan (committed before building).

**Not changed:** `body-layer/CLAUDE.md` — grepped first; it never described the on-ground silence
default (no "on-ground"/`maybe_apply`/`silent mode` text anywhere in it), so there was nothing to
update, matching the task's own "if it describes..." condition. `aircraft-layer/` — untouched,
per the F10 decision below.

### Tests Added

- `test_crew_console.py`:
  - `test_look_command_on_ground_answers_unable`, `test_scan_command_on_ground_answers_unable`,
    `test_follow_on_ground_answers_unable` — `_LOOK_COMMAND_TOKENS` members refused on the ground.
  - `test_look_command_airborne_dispatches_normally` — same token, same store, only `on_ground`
    differs.
  - `test_look_command_on_ground_still_ends_silence` — refused-on-the-ground is still a real
    command for silence-ending purposes.
  - `test_non_look_command_on_ground_dispatches_normally` — `observ_on` is unaffected.
  - `test_refusal_mode_wins_over_on_ground_for_a_look_command` — BL-15 refusal takes precedence.
  - `test_radio_check_token_answers_loud_and_clear`, `test_radio_check_works_on_the_ground`,
    `test_radio_check_ends_an_explicit_silence`, `test_radio_check_in_refusal_mode_gets_the_refusal_line`.
  - `test_greeting_token_echoes_the_pilots_own_word` (parametrized, all four times of day),
    `test_greeting_with_missing_slot_degrades_to_say_again`.
  - `test_typed_radio_check_dispatches_through_handle_line`,
    `test_typed_greeting_dispatches_through_handle_line` (parametrized, incl. mixed case and a
    trailing period), `test_typed_radio_check_in_refusal_mode_gets_the_refusal_line`.
- `test_logger.py`:
  - `test_run_once_polls_no_source_while_on_the_ground` /
    `test_run_once_resumes_polling_once_above_the_ground_threshold` (`PerceptionLogger`).
  - `test_console_runner_ingests_nothing_while_on_the_ground` /
    `test_console_runner_resumes_ingesting_once_above_the_ground_threshold` /
    `test_console_runner_existing_belief_decays_but_is_not_wiped_on_the_ground`
    (`ConsolePerceptionRunner`) — the last one plants a contact airborne, polls once on the
    ground with an empty source, and asserts the contact is still there (existing belief kept,
    not wiped).

**Counterfactual run (per this role's "show the red" guidance):** since every one of the
perception-gating tests asserts an *absence* ("nothing was ingested"), I broke the
`ConsolePerceptionRunner.run_once` gate (forced the `if` branch to always poll, verified by
`shasum` before/after and restored from a byte-for-byte backup copy, not `git checkout`) and
confirmed `test_console_runner_ingests_nothing_while_on_the_ground` goes red for the stated
reason (an `Observation` that should not exist appears), while the sibling `PerceptionLogger`
test — a different gate, untouched by this edit — stayed green, confirming the two gates are
actually independent rather than one incidentally covering for the other.

### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass (68 source files)
- `pytest tests -q`: pass (2236 passed, 4 xfailed — same pre-existing xfails as before this
  branch)

**aircraft-layer/**: not touched, no checks run (no F10 item added — see below).

### Notable Discoveries / Decisions

- **`_LOOK_COMMAND_TOKENS` scope is a judgment call, stated in the plan and here rather than
  escalated** (local/reversible per the Escalation Rules): every scan token +
  `watch_nearest`/`watch_nearest_air_defence`/`follow`. The task names `watch` and `scan forward`
  as examples; `follow` is the one other token that shares their job exactly (it immediately
  raises binoculars onto a target — `logger.py`'s "any command lowers binoculars" glue reads
  `CrewConsole.last_command_target_contact_id`, which only `follow` sets). `select_target`/
  `engage`/`step`/`report*` are excluded: they only read existing belief and already degrade
  sensibly ("no such contact") when belief is thin from not having scanned.
- **`ON_GROUND_AGL_THRESHOLD_M` was not newly wired through `tuning.py`.** It is a pre-existing
  constant (not new), now doing more work (gating perception in two poll loops, not just the old
  one-shot silence default) — flagged per the root CLAUDE.md rule rather than silently expanded
  in scope. Still a bare module literal in `crew_console.py`; would want the mechanism if someone
  touches its semantics next.
- **F10 item for radio check/greeting: not added.** Checked the existing pattern first (per "do
  not reinvent the wheel") — every current F10 item is a Hook-side Lua menu entry in
  `aircraft-layer/dcs-export/`, deployed via `WORKFLOW.md`'s opt-in and requiring a DCS-side
  redeploy. That is a cross-subproject change, not a trivial extension of something already in
  place, so per the task's own conditional ("only if trivial") I did not add one. Radio check's
  stated purpose (confirm intercom/Petrobrain are alive during engine start) is already served by
  voice once `audio-adapter` recognises the phrase.
- **Voice wiring for BL-B81 is a no-op on the body-layer side beyond the token dispatch added
  above.** `handle_transcript`/`_act_on_voice_decision`'s "act" path already calls
  `handle_command` generically for whatever token `audio-adapter`'s `command_matcher` resolves
  to — recognising "radio check"/the four greetings as those tokens is an `audio-adapter`
  vocabulary change in a separate subproject, out of scope here and not touched.
- **Existing belief survives a ground poll (kept, not wiped)** — `self.store.tick`/
  `self.store.ingest([], ...)` still run unconditionally every poll regardless of `on_ground`;
  only the observation-gathering comprehension is gated. Verified by
  `test_console_runner_existing_belief_decays_but_is_not_wiped_on_the_ground`.
- One implementation slip caught by running the suite rather than by inspection: a
  `git checkout -- src/logger.py` run mid-session (meant to restore after a counterfactual probe)
  silently discarded all of that file's uncommitted `[[BL-B82]]` edits, since nothing had been
  committed yet. Caught immediately by `git status --short` no longer listing `logger.py` as
  modified; redone from the diff already reviewed above, re-verified with `mypy`/`ruff`/`pytest`
  before the second (correct, backup-copy-based) counterfactual run. No trace of this remains in
  the final diff — noted here only because the role's own guidance is to record what the
  verification scope should include, and "which file a destructive git command touches" is
  exactly that.

### Voice wiring (follow-up: wiring BL-B81 into `audio-adapter`'s voice recognition)

The paragraph above ("Voice wiring for BL-B81 is a no-op on the body-layer side...") described
what body-layer was ready for; this is the `audio-adapter` half it deferred — making "radio
check" and the four greetings recognisable from speech at all, per the user's own stated reason
in `[[BL-B81]]`: *"if intercom is off, there's no response. This is an easy check that A)
intercom is ON and volume good B) that Petrobrain is operational."*

**Files changed:**

- `audio-adapter/src/vocabulary.py` —
  - Added `"radio_check"`/`"greeting"` to `VOICE_ONLY_TOKENS` (no F10 button, same posture as
    `mark_here`/`drop_target`).
  - `PHRASES["radio_check"] = ("radio check",)` — plain, slot-free, matching `drop_target`'s
    one-exact-wording posture.
  - `PHRASES["greeting"]` — the four `"good <time_of_day> petrovich"` phrasings, one per
    `TIME_OF_DAY_WORDS` value. Bias hints only, like `follow`'s/`report`'s own phrasings: the
    slot is parsed, not enumerated, for the identical reason those two give (one dispatch token,
    not four).
  - `TIME_OF_DAY_WORDS = ("morning", "day", "evening", "night")` + `parse_time_of_day` — a new
    hand-synced mirror of `belief.crew_console._GREETING_TIMES_OF_DAY`, built on the exact
    `SECTOR_WORDS`/`parse_sector_word` template (whole-word match anywhere in the normalised
    transcript, table order as tie-break). Module independence forecloses importing
    `crew_console`'s set directly, same as every other cross-seam vocabulary table in this file.
- `audio-adapter/src/command_matcher.py` —
  - `_GREETING_VERB = "good"` and `_parse_greeting_slots(text)`, the same shape as
    `_FOLLOW_VERB`/`_parse_follow_slots`.
  - A new branch in `match_transcript`, ordered after the `engage` branch and before the generic
    phrase table, exactly mirroring `follow`/`report`/`select_target`/`step`/`engage`'s own
    "fuzzy-verb-match, try the slot parser, return on a hit, otherwise fall through unchanged"
    shape: a `"good"`-anchored utterance with a recognised `time_of_day` resolves immediately
    (`match_ratio=1.0`); one with no recognised `time_of_day` falls through to the phrase table,
    which can still score a near miss against `greeting`'s own enumerated phrasings (see
    `test_good_job_degrades_rather_than_falsely_resolving_a_greeting`) — body-layer's
    `_handle_greeting` already degrades a slot-less `greeting` to "say again", so this is a safe
    near-miss outcome, not a bug.
  - `"radio_check"` needed no matcher change at all — it is a single plain two-word phrase, no
    slot, resolved by the existing generic phrase table exactly like `drop_target`/`disengage`.

**Checked, not touched (confirmed correct as-is, per the task's own instructions):**

- **Readback**: `audio-adapter/src/server.py`'s `/speak` path is token-agnostic — it synthesizes
  whatever text `CrewConsole` hands it and adds no readback of its own on any path except
  `stop_talking`'s documented interrupt-only exception. `"Loud and clear."` reaches the pilot
  exactly once, from body-layer, with nothing added on this side.
- **Biasing prompt / hotwords**: `vocabulary.to_prompt()` (used by `__main__.py` as
  `--prompt`) samples from `TOKENS`/`PHRASES` automatically, so the two new tokens' phrasings are
  already eligible for inclusion with no separate hotword list to touch. `"petrovich"` was
  already biased via `wake_petrovich`'s phrasings; `greeting`'s own phrasings end in the same
  word, reinforcing it rather than needing a new one.
- **`tools/stt_bench.py`**: has no separate phrase list — `_print_prompts` and the recording
  layout both iterate `vocabulary.TOKENS`/`PHRASES` directly, so the new tokens are already
  covered the moment the vocabulary changed. Unbenched on this user's voice as of this work, like
  every token added without a re-recorded corpus (the same cost `vocabulary.py`'s own docstring
  notes for `cancel_scan`/`silence`/`observ_on`).

**Near-miss checks (the task's explicit ask) — measured, not assumed:**

- `"good"` becomes a new `VERB_ANCHOR_WORDS` member (derived from `greeting`'s phrasings' first
  word, same mechanism as every other anchor word) — `difflib.SequenceMatcher("good",
  "look").ratio() == 0.5`, exactly at `VERB_FLOOR`, so an ordinary sentence starting with "good"
  now anchors. This is the same already-accepted risk class as `look`/`watch`/`report`/`scan`
  being ordinary English words (module docstring) — the phrase-scoring pass that follows is the
  real defence, and `test_greeting_with_no_recognisable_time_of_day_says_again` /
  `test_good_job_degrades_rather_than_falsely_resolving_a_greeting` pin both of its outcomes.
- `"radio"`'s best fuzzy match against the pre-existing anchor-word set was 0.444
  (`"drop"`) — below `VERB_FLOOR` — so `radio_check` introduces no false-anchor risk of its own;
  confirmed by `test_radio_check_does_not_falsely_fire_on_report_or_check_style_speech`.
- Full regression run after both changes: `pytest audio-adapter/tests -q` — 300 passed, 1
  skipped (the pre-existing real-`whisper-cli` skip, unrelated), 16 of the 300 new.

**Not changed:** `audio-adapter/src/stt_engine.py`, `audio-adapter/src/audio_adapter/__main__.py`
— both already thread `vocabulary.to_prompt()` through generically; nothing token-specific lives
in either file. `body-layer/` — already wired at `01a69ec7`, confirmed to need no change (the
dispatch reads `slots["time_of_day"]` by key, which this work populates with the identical key
and the identical four string values).

### Review fixes

Addressing `plans/radio-check/review.md`'s one required fix and two of its optional refinements,
against reviewed tip `49c24eb1`.

- **Required — the asymmetric `time_of_day` drift guard.** Added
  `test_greeting_times_of_day_are_exactly_the_four_greetings` to
  `body-layer/tests/test_crew_console.py`, pinning
  `_GREETING_TIMES_OF_DAY == frozenset({"morning", "day", "evening", "night"})` (imported
  `_GREETING_TIMES_OF_DAY` into the test module alongside the other `belief.crew_console`
  imports). Updated both docstrings to name the other side's test by name — the body-layer test's
  docstring names `test_time_of_day_words_are_exactly_the_four_greetings` in
  `audio-adapter/tests/test_vocabulary.py`, and that test's own docstring now names the new
  body-layer test back, so the drift-guard claim each side makes is checkable from either file.
- **Optional — `CrewConsole.on_ground` now defaults to `True`.** Changed the dataclass field
  default (`body-layer/src/belief/crew_console.py`) and updated its own docstring plus
  `reset_for_new_mission`'s docstring, which referenced the old default's harmlessness. This
  flipped the implicit assumption of **50** pre-existing tests across `test_crew_console.py` that
  constructed a bare `CrewConsole(...)` and immediately issued a `_LOOK_COMMAND_TOKENS` member
  (`watch_nearest`/`follow`/every scan family/confirm-band round trips reaching one of those),
  relying on the old "airborne until told otherwise" default to let dispatch proceed — enumerated
  by running the full suite after the flip and reading every failure, not estimated. Each of those
  50 now sets `console.on_ground = False` immediately after construction (one line per test, same
  construction-site pattern each already used), restoring their original airborne-starting intent
  with the assumption now explicit instead of implicit. The review's own on-ground/airborne tests
  (`test_look_command_on_ground_answers_unable` and its five neighbours) already set `on_ground`
  explicitly both ways and needed no change. Confirmed by direct REPL: a freshly constructed
  `CrewConsole(store=ContactStore())` now reports `on_ground == True` and answers a look command
  `"Unable, on the ground."` before any telemetry has ever been seen.
- **Optional — `ON_GROUND_AGL_THRESHOLD_M` wired through `tuning.py`.** Declared via
  `tuning.real("belief.crew_console.ON_GROUND_AGL_THRESHOLD_M", 10.0, lo=0.5, hi=50.0,
  status="uncalibrated")` in `body-layer/src/belief/crew_console.py` (added `import tuning`),
  value and bounds unchanged from the prior bare literal — only the declaration form changed, per
  the review's framing ("already flagged... the right call for this change... noting it here only
  so a future touch... is the trigger"). Rewrote the constant's own comment so its **first
  sentence** (the only one `tools/generate_defaults.py` renders) states what it does, which
  direction is dangerous (too high false-grounds him in genuine low-level/NOE flight; too low lets
  him scan on the ramp), and is self-contained — the original comment's "below" referred to the
  constant's position in the source file, which does not survive into `config/defaults.toml`'s
  rendering; caught by reading the **rendered** file after the first regeneration and rewritten
  before committing. Regenerated `body-layer/config/defaults.toml` with
  `tools/generate_defaults.py --write`; `tests/test_tuning_defaults_toml.py` passes, confirming the
  committed file matches. **Trap check (per `.claude/agents/implementer.md`):** `lo`/`hi` are AST
  float literals, not references. Every consumer (`logger.py`'s two poll loops and the on-ground
  refresh in `_run_crew_text_poll_loop`) reads the constant via `from belief.crew_console import
  ON_GROUND_AGL_THRESHOLD_M`, a standard module-level import that only executes after
  `crew_console.py`'s own top-level `tuning.real(...)` call has already resolved, so every consumer
  sees the loaded value, not the code default, when an override is present. **No cross-key
  coupling identified** — this constant gates perception/look-command refusal only; it shares no
  asserted relationship with `belief.decay`'s `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` coupling
  or any other declared tunable.
- **Not addressed** (correctly, per the review's own framing): the third optional refinement
  (`DISPATCHED_COMMAND_TOKENS` membership note) was recorded by the reviewer as "verified directly,
  no fix needed" — nothing to change.

**Checks after these fixes:** body-layer `ruff format --check src tests`, `ruff check src tests`,
`mypy src` (68 files) — all pass. `pytest tests -q` — 2237 passed (2236 + the one new test), 4
xfailed, confirmed by name with `-k "greeting_times_of_day"` → 1 passed, not inferred from the
full-suite count alone. audio-adapter `ruff format --check src tests`, `ruff check src tests`,
`mypy src` (15 files), `pytest tests -q` — 300 passed, 1 pre-existing skip (unchanged from the
reviewed state; only a docstring changed on this side).
