### Implementation Summary

Built the whole text-mode SRS pipeline minus audio, against BL-0..BL-4's belief surface only
(this branch deliberately does not depend on the unmerged `feature/bl5-tool-api`): a deterministic
intent parser, an outbound routing gate, body-written readback/contact-report/urgent-call
templates, the `handle_player_utterance` escalation entry point, and a typed-input/printed-output
`CrewConsole` wired into `logger.py` behind `--crew-text`.

### Files Changed

- `body-layer/src/belief/utterance.py` (new) — `PlayerUtterance`/`PartialParse` records and
  `parse_utterance`: an ordered table of `(regex, intent)` pairs, first-match-wins, over the four
  `set_attention` verbs (`watch`/`keep an eye on`, `ignore`/`forget`, `priority`, `unwatch`/
  `normal`) and two `describe_contact` phrasings (`where is/was ...`, `status ...`). A verb match
  alone never produces a `"handled"` disposition — only a verb match *and* exactly one resolved
  reference candidate do; zero or several candidates always escalate
  (`reason_escalated: unmatched`/`ambiguous_reference`). Reference resolution is a literal
  `CONTACT_<n>` id or `belief.tools.find_contact` after stripping leading filler words
  (`that`/`the`/`a`/`an`).
- `body-layer/src/belief/speech.py` (new) — `OutgoingSpeech`, the three body-written templated
  classes (`render_readback`, `render_contact_report`), and `route_event`: the outbound gate over
  `belief.events.Event | UrgentCall`, checking which type it got before anything else. An
  `UrgentCall` speaks immediately with `bypass_gate=True`, no ack/cooldown touched. An `Event`
  renders through a per-kind template (`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`/
  `CONTACT_CLASSIFICATION_CHANGED`) and is auto-acknowledged the moment it's spoken.
  `CONTACT_ATTENTION_CHANGED` deliberately gets no template.
- `body-layer/src/belief/escalation.py` (new) — `handle_player_utterance`, the one body→brain
  entry point, plus `EscalationPayload`, the `BrainClient` protocol, and `NullBrainClient`/
  `DebugPrintBrainClient` stand-ins (no real brain exists yet).
- `body-layer/src/belief/crew_console.py` (new) — `CrewConsole`: dispatches a `"handled"` parse
  directly into `belief.tools`/`belief.speech`, an `"escalated"` one into
  `handle_player_utterance`; `drain_events` speaks queued lifecycle events via `route_event`;
  `!inject-urgent <contact_id> <text>` is the Stage 5 manual bypass_gate test harness.
- `body-layer/src/logger.py` — added `--crew-text` (mutually exclusive with `--console`/
  `--overlay`, enforced via `parser.error`) and `--brain-client debug|null`.
  `_run_crew_text_poll_loop`/`_run_crew_text_repl` mirror the existing `--console` machinery
  exactly, reusing `ConsolePerceptionRunner`, plus one extra call: `crew_console.drain_events`
  after each poll's `tick()`.
- `body-layer/CLAUDE.md` — Structure entries for the four new modules, plus a `--crew-text`
  addendum to the existing `logger.py` entry.

### Tests Added

- `test_utterance.py` (13 tests) — one test per verb/phrasing, the required adversarial case
  ("watch out for that BMP" must not match `watch`), ambiguous-reference escalation (two
  spatially-separated BMP contacts), zero-candidate escalation, a not-found literal id, and a
  fully unmatched line.
- `test_speech.py` (10 tests) — readback text per attention level, contact-report reuse of
  `describe_contact`'s summary, `route_event`'s bypass-first ordering for `UrgentCall` (no store
  lookup needed), auto-ack on a rendered lifecycle event, detected/lost/reacquired template text,
  `CONTACT_ATTENTION_CHANGED`'s no-template/no-ack behaviour, and a vanished-contact fallback.
- `test_escalation.py` (5 tests) — payload field construction, `situational_header`'s
  absent-without-enrichment / present-with-enrichment behaviour, `NullBrainClient`'s silence, and
  `DebugPrintBrainClient`'s stderr-style output.
- `test_crew_console.py` (6 tests) — the required end-to-end acceptance scenario (detect → watch →
  readback → lost → reacquired → "where was that BMP?" → memory-backed answer, plus a
  `status <id>` contact report and an injected urgent call), an unresolvable-reference escalation,
  the `!inject-urgent` usage message, `_act`'s defensive not-found branches (exercised directly
  since `parse_utterance` never hands `_act` a contact id that doesn't exist), and output-stream
  printing.

333 → 367 tests (34 new).

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (strict, run from `body-layer/`): pass
- `pytest body-layer/tests -q`: pass (367 passed)

### Acceptance criteria demonstrated

All four pieces the milestone brief names are exercised in
`test_crew_console.py::test_scripted_crew_session_reproduces_the_first_useful_success_criterion`:

1. **First useful success criterion** — detect → `watch CONTACT_1` → readback → lost →
   reacquired → `where was that bmp?` → an answer built from `describe_contact`'s structured
   `summary`, not an improvised string, and with zero brain escalations along the way.
2. **Readback** — `watch <id>` → `"Watching <id>."`.
3. **Contact report** — `status <id>` → `describe_contact`'s certainty-hedged summary
   (single-contact, per the plan's scope cut).
4. **Urgent call** — `!inject-urgent <id> <text>` → the text spoken verbatim with
   `bypass_gate=True`, via the same `route_event` gate the proactive path uses.

A live typed-session walkthrough (`--crew-text` against a running aircraft-layer instance) is
still recommended before user acceptance, but the automated scenario above already covers the
same sequence end to end.

### Notable Discoveries / Deviations from the plan

- **`bypass_gate` could not live on `belief.events.Event`.** The plan's §3.5/§5 sketches show
  `bypass_gate` as a field on a generic event object, but `events.py` is explicitly out of this
  milestone's Affected Modules ("BL-5a is a consumer of the existing belief surface, not a
  modifier of it"), and `EventKind`'s closed `Literal` has no member for "urgent call" anyway.
  Introduced a small separate `UrgentCall` type instead; `route_event` accepts
  `Event | UrgentCall` and dispatches on which one it got. Functionally equivalent to a
  `bypass_gate`-attribute check, without touching BL-4's event model.
- **No numeric candidate score.** The plan's §3.5 sketch shows a `score` per reference candidate;
  `belief.tools.find_contact` (BL-2) does no ranking of its own, so `ReferenceCandidate` carries
  only `id`/`why` rather than a fabricated placeholder score.
- **"All four lifecycle kinds get one [template]"** (plan Stage 2) is read as the four *speech-
  worthy* kinds — `CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`/
  `CONTACT_CLASSIFICATION_CHANGED` — not all five `EventKind` values. `CONTACT_ATTENTION_CHANGED`
  is deliberately silent: the player's own command already got a readback, and an area-driven
  attention change is not yet narrated proactively (a real, documented gap for a future milestone,
  not an oversight).
- **The plan's own `"keep an eye on that shilka by the road"` worked example (§3.5) is not
  literally reproduced in tests.** It relies on a "Shilka" reporting-name classification value
  this codebase's fixtures don't use elsewhere, and a trailing spatial clause ("by the road") the
  parser's filler-stripping deliberately does not attempt to parse (place-name phrasing is
  explicitly out of scope until BL-5's `find_place`, per the plan's "Resolved dependency
  question"). The equivalent ambiguous-reference behaviour is instead tested against two
  synthetic, spatially-separated `BMP-1`/`BMP-2` contacts.
- Baseline confirmed before starting: 333 passing on this branch (BL-0..BL-4 only, no BL-5's +22).
