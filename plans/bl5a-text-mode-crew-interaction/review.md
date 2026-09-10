### Review Summary

BL-5a builds the whole text-mode SRS pipeline minus audio: `belief.utterance.parse_utterance`
(deterministic regex-table intent parser), `belief.speech` (readback/contact-report templates +
`route_event`'s outbound gate), `belief.escalation.handle_player_utterance` (the body->brain
entry point with `NullBrainClient`/`DebugPrintBrainClient` stand-ins), and `belief.crew_console.
CrewConsole` wired into `logger.py` behind `--crew-text`. Read the plan and implementation.md in
full, read all four new source modules plus the `logger.py`/`events.py`/`tools.py` diffs, read
all four new test files, and ran the subproject's full verification suite myself.

The implementation matches the plan's scope closely — no scope drift found. All four self-flagged
deviations were checked against the actual code and are reasonable, well-justified departures, not
corner-cutting.

**Deviation-by-deviation verification:**

1. **`UrgentCall` instead of `bypass_gate` on `Event`.** Confirmed by reading `belief/events.py`:
   `EventKind` is a closed `Literal` of 5 members with no "urgent call" member, and `events.py` is
   explicitly listed as out of this milestone's Affected Modules in the plan. `route_event`
   dispatches cleanly via `isinstance(event, UrgentCall)` first, before any other logic — this *is*
   the plan's own "check bypass_gate first" ordering, just implemented as a type check instead of a
   field check. `UrgentCall` is constructed nowhere except `crew_console.py`'s `!inject-urgent`
   harness, so there is exactly one producer and one consumer (`route_event`) — this is not two
   parallel "speakable thing" types accreting independent behavior, it's one narrow union with one
   dispatch point. The plan's own sketch shows `bypass_gate` on a generic "event" object but never
   pins it to `belief.events.Event` specifically as an implementation requirement — a reasonable
   reading, not a rewrite of the design.
2. **No fabricated `score` on `ReferenceCandidate`.** Confirmed by reading `tools.py`'s
   `find_contact` (lines 355-386): it is a plain case-insensitive substring match over
   `classification.value`, sorted by recency, with no ranking value anywhere to carry through.
   Leaving `score` off is honest, not a gap.
3. **`CONTACT_ATTENTION_CHANGED` gets no template.** The plan's Stage 2 text lists three lifecycle
   kinds by name (`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`) then says "render the
   event's template (all four lifecycle kinds get one)" — the fourth is `CONTACT_CLASSIFICATION_
   CHANGED`, separately introduced in the plan's Affected Modules bullet for `speech.py`. Four
   templated kinds + one excluded (`CONTACT_ATTENTION_CHANGED`) = the five-member `EventKind`
   literal, exactly. `_render_lifecycle_text` in `speech.py` does implement all four: DETECTED,
   LOST, REACQUIRED, CLASSIFICATION_CHANGED, confirmed by reading the function. This is the plan's
   own intended reading, not a scope-narrowing invention.
4. **BMP-1/BMP-2 substitute for the "shilka by the road" example.** The original example needs a
   classification value (`Shilka`) and place-name spatial phrasing this branch's grammar
   deliberately doesn't parse (place references wait for BL-5's `find_place`, an already-documented,
   correctly-scoped-out gap). `test_ambiguous_reference_escalates_with_candidates` in
   `test_utterance.py` uses two spatially-separated BMP contacts and confirms `parse_utterance`
   returns `disposition == "escalated"`, `reason_escalated == "ambiguous_reference"`, and both
   candidates populated — this exercises exactly the mechanism the original example was meant to
   demonstrate (verb match + multiple candidates => escalate, never guess). Genuine, not weaker.

**Independent checks:**

- **Determinism.** `belief/utterance.py`'s `_PATTERNS` table is real `re.compile` regexes,
  evaluated top-down, first-match-wins. Grepped the whole escalation path (`utterance.py`,
  `speech.py`, `escalation.py`, `crew_console.py`) for any LLM/network/random call — none found.
  `NullBrainClient`/`DebugPrintBrainClient` are both pure/local; `DebugPrintBrainClient` only
  prints to stderr.
- **Escalate-not-guess.** Traced `parse_utterance` -> `_resolve_reference`: zero candidates ->
  `reason_escalated="unmatched"`; 2+ candidates -> `reason_escalated="ambiguous_reference"`. Both
  paths set `referenced_contact_id=None` and never fall through to `_act` in `crew_console.py`
  (`_handle_utterance` only calls `_act` when `disposition == "handled"`). Confirmed by both direct
  code reading and `test_utterance.py`'s `test_ambiguous_reference_escalates_with_candidates`/
  `test_zero_candidates_escalates_as_unmatched_but_keeps_matched_intent`.
- **The scripted acceptance test.** Read
  `test_crew_console.py::test_scripted_crew_session_reproduces_the_first_useful_success_criterion`
  directly — one coherent session: detect -> `drain_events` speaks the detection -> `watch <id>`
  readback with zero brain calls -> lost -> reacquired (both via `drain_events`) -> `"where was
  that bmp?"` answered from `describe_contact`'s structured summary with zero brain calls ->
  `status <id>` contact report -> `!inject-urgent` urgent call spoken verbatim with
  `bypass_gate=True`. All four required pieces are genuinely present in one flow with shared state
  (one `store`, one `console`), not four independent assertions bolted together.
- **`--crew-text` mutual exclusion.** `logger.py`: `if args.crew_text and (args.console or
  args.overlay): parser.error(...)`. Confirmed via `git diff` — the `--crew-text` branch builds its
  own fresh `crew_runner`/`crew_console`/`stop_event`/`poll_thread`, entirely separate from the
  `--console` branch's variables; no shared mutable state between the two paths.
- **`crew_console.py` vs `console.py`.** No belief logic duplicated — `crew_console.py` only calls
  existing `belief.tools` functions (`set_attention`, `describe_contact` via `render_contact_
  report`) and existing `belief.speech` templates; it holds no parsing/decision logic that
  duplicates `console.py`'s. `!inject-urgent` is clearly labelled in its own docstring, the
  `CrewConsole` module docstring, `HELP_TEXT`, and `body-layer/CLAUDE.md` as a test harness, never
  implied to be a real detector.
- **No BL-5 dependency.** Grepped for `find_place`/`get_situation`/`describe_our_position`/
  `poll_events` across `src/` and `tests/` — the only hits are docstring/comment references to
  future work, no imports. Branch is genuinely self-contained on BL-0..BL-4.

**Verification run myself** (from `body-layer/`, using `.venv/bin`):
- `ruff format --check src tests` — pass (54 files already formatted)
- `ruff check src tests` — pass
- `mypy src --strict` — pass (27 source files, no issues)
- `pytest tests -q` — **367 passed**. Reconciled the delta myself: `test_utterance.py` (13),
  `test_speech.py` (10), `test_escalation.py` (5, via `wc -l`/grep of `def test_`), and
  `test_crew_console.py` (6, counted directly by reading the file) sum to 34 new tests, matching
  367 - 333 baseline exactly.

No writes to the DCS installation (no DCS I/O in this milestone at all). No `world-model/data`
changes. Working tree clean aside from unrelated agent-memory bookkeeping files — nothing new to
stage.

### Required Fixes

None.

### Optional Refinements

- **Live `--crew-text` walkthrough against a running aircraft-layer instance.** The implementer
  flagged this as still recommended before final user acceptance. The plan's own Stage 6 text says
  the automated scripted scenario is "the automated form of the milestone's acceptance criterion,
  run *before* asking the user for a live typed-session acceptance pass" — i.e. the plan already
  anticipates the live pass as a separate, later, user-facing step, not something Reviewer or DoD
  gates on before approving the code itself. Unlike BL-2.6/PB-2, this plan does not mandate a live
  DCS session as part of Definition of Done. Recommend DoD confirm with the user whether they want
  a live `--crew-text` pass before merge (their call, not a blocker) — flagging this explicitly so
  it isn't silently skipped, not because the code needs it to be correct.
- **`situational_header`'s stand-in shape** (`{contact_counts, our_position}`) is explicitly
  documented as provisional in both the plan's Risks and `escalation.py`'s own docstring. No action
  needed now; noting only so a future BL-6 reviewer doesn't mistake it for a finished data-model
  entry.

### Verdict
APPROVED

### Review Confidence
Full read — plan.md and implementation.md read in full; all four new source modules read in full;
`events.py`, relevant slices of `tools.py`, and the full `logger.py` diff read directly; all four
new test files read in full (or fully grepped + spot-read for `test_utterance.py`); verification
commands (`ruff format --check`, `ruff check`, `mypy --strict`, `pytest`) run directly by me, not
taken on the implementer's word.
