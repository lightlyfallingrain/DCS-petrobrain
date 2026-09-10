### Goal

Build the whole SRS pipeline minus audio — a deterministic intent parser, an outbound routing
gate, body-written readback/contact-report/urgent-call templates, and the `handle_player_utterance`
escalation entry point, wired into a typed-input/printed-output crew session — so that PB-7/PB-8
later reduce to attaching a real audio transport to a pipeline that already works.

### Branch / dependency situation

This branch (`feature/bl5a-text-mode-crew-interaction`) is cut from `main`, i.e. **BL-0..BL-4**,
not from the unmerged `feature/bl5-tool-api` branch (BL-5). `body-layer/src/belief/tools.py` on
this branch has `get_contacts`, `describe_contact`, `get_contact_history`, `find_contact`,
`set_attention`, `watch_area`, `unwatch_area`, `list_areas`, `get_attention_state`, `list_events`,
`acknowledge_event`, `get_stats` — and **not** BL-5's `find_place`, `get_situation`,
`describe_our_position`, or the `poll_events` rename of `list_events`. Everything below is scoped
to build cleanly on the BL-4 subset and compose with BL-5 landing later, either before or after
this branch merges. See "Resolved dependency question" below for the concrete scope cut this
forces, and Risks for what stays open until BL-5 merges.

### Affected Modules / Files

- `body-layer/src/belief/utterance.py` *(new)* — `PlayerUtterance` record (§5), `PartialParse`
  (§3.5's shape), and `parse_utterance()`, the deterministic intent grammar. Pure functions plus
  one call into `tools.find_contact` for reference resolution — no I/O.
- `body-layer/src/belief/speech.py` *(new)* — `OutgoingSpeech` record (§5), the readback /
  contact-report / lifecycle-event / threat-reaction templates (§3.6), and `route_event()`, the
  outbound routing gate that checks `bypass_gate` before anything else and auto-acknowledges any
  event it speaks from a template.
- `body-layer/src/belief/escalation.py` *(new)* — `handle_player_utterance()` (§3.5's payload
  builder), a small `BrainClient` protocol, and the two stand-in implementations BL-5a needs since
  no real brain exists yet (`NullBrainClient`, `DebugPrintBrainClient`).
- `body-layer/src/belief/crew_console.py` *(new)* — the typed-input/printed-output REPL itself:
  dispatches a line through `parse_utterance` → direct action + readback, or → `handle_player_
  utterance` + `BrainClient`; on the proactive side, drains `ContactStore.tick()`'s newly-appended
  events through `route_event()` each poll and prints whatever it returns. Deliberately separate
  from `console.py` (see "Module boundary" decision below), not an extension of it.
- `body-layer/src/logger.py` — add a `--crew-text` flag alongside the existing `--console`/
  `--overlay` flags, wiring `crew_console.CrewConsole` onto the same poll-loop-thread + REPL-thread
  pattern `_run_console_poll_loop`/`_run_console_repl` already use for `--console`.
- `body-layer/tests/test_utterance.py`, `test_speech.py`, `test_escalation.py`,
  `test_crew_console.py` *(new)* — parser grammar, template/gate behaviour (including bypass_gate
  ordering and pre-emption), escalation payload shape, and an end-to-end scripted session
  reproducing the runtime doc's "First useful success criterion" plus a readback, a contact
  report, and an urgent call.
- `body-layer/CLAUDE.md` — append a Structure entry for the four new modules once implemented
  (existing convention: every `belief/` module gets one).

No changes to `tools.py`, `contacts.py`, `events.py`, `attention.py`, `enrichment.py`, or
`classification.py` — BL-5a is a consumer of the existing belief surface, not a modifier of it.

### Resolved dependency question: BL-5a builds against the BL-4 subset only, no throwaway BL-5 duplication

The milestone brief lists `handle_player_utterance` and the readback/contact-report templates as
deliverables; it does not require `find_place`, `get_situation`, or a `poll_events` rename to
satisfy its acceptance criterion. Checked concretely against the runtime doc's "First useful
success criterion" plus the milestone's three worked examples:

- **Readback** (`"watch C17"` → `"Watching C17."`) needs only `tools.set_attention`, which exists.
- **"Where was that BMP?"** needs `tools.find_contact("BMP")` (exists) to resolve the reference,
  then `tools.describe_contact` (exists) to answer. Both already on this branch.
- **Contact report** is templated from a single contact's existing `describe_contact`-shaped
  facts (see the scope cut below on why this is single-contact, not `contact_group`) — no BL-5
  tool needed.
- **Urgent call** is templated from a `bypass_gate: true` event — no BL-5 tool needed.

The one place a BL-5-only tool would have been natural is resolving a *place* reference ("watch
the north side of the village") via `find_place`. Building a throwaway duplicate of `find_place`
now, only to delete it when BL-5 merges, fails the "don't introduce an abstraction you can't name
a clear duplication for" heuristic — it's not removing duplication, it's temporarily creating it.
**Decision: the parser's area-watching intent is scoped to bearing/range only for BL-5a** (mirrors
`console.py`'s existing `watch-area <bearing> <range_m> <radius_m> [sector]`), and place-name
phrasing is left unmatched → escalated with `reason_escalated: unmatched` until BL-5 merges and a
follow-up wires `find_place` into the grammar. This is a real gap in what the crew session can do
today, not a silent one — captured in Risks.

### Deterministic intent parser — concrete design

No precedent in this codebase for a text grammar, so this is a fresh design choice, made (not left
open): **a small ordered table of `(regex, intent_builder)` pairs, evaluated top-down, first match
wins** — not a general grammar, not a keyword bag-of-words scorer.

Reasoning:
- Matches §2.1's "narrow, high-precision patterns, let the brain absorb the long tail" mandate
  directly — a regex table makes precision an explicit, auditable property (the pattern itself),
  where a scored keyword-bag approach would need a threshold tuned by feel.
- First-match-wins over an ordered list is the same evaluation shape `belief.classification`'s
  lattice and `belief.attention`'s `effective_attention` already use elsewhere in this codebase —
  consistent, not a new evaluation idiom to learn.
- Cheap to extend: BL-5's `find_place` or BL-6/7's new tools each add one row, not a retrain or a
  re-tuned threshold.
- Genuinely deterministic — no LLM call anywhere in `parse_utterance`, satisfying root `CLAUDE.md`
  "code owns truth, models own interpretation" for this specific piece: the parser decides *that*
  an utterance means "watch," never *what* to watch if the referent is ambiguous (that's escalated,
  never guessed).

Sketch (illustrative, not final regex text):

```python
IntentPattern = tuple[re.Pattern[str], Callable[[re.Match[str]], PartialParse]]

PATTERNS: list[IntentPattern] = [
    (re.compile(r"^(watch|keep an eye on)\s+(?P<ref>.+)$"), _build_set_attention("watch")),
    (re.compile(r"^(ignore|forget)\s+(?P<ref>.+)$"), _build_set_attention("ignore")),
    (re.compile(r"^priority\s+(?P<ref>.+)$"), _build_set_attention("priority")),
    (re.compile(r"^(unwatch|normal)\s+(?P<ref>.+)$"), _build_set_attention("normal")),
    (re.compile(r"^where('?s| is| was)\s+(?P<ref>.+)\??$"), _build_describe),
    (re.compile(r"^status\s+(?P<ref>.+)$"), _build_describe),
]
```

`<ref>` resolution is shared across all patterns: a literal contact id (`^C\d+$`) resolves
directly; anything else calls `tools.find_contact(ref)` (already deterministic body-side matching,
§3.3's note) and yields zero/one/several candidates. Zero or several candidates is *never* a
"matched, unambiguous" outcome even though the verb matched — only a verb match **and** a single
confident candidate together produce direct action; otherwise the parse's `disposition` is
`escalated` with `reason_escalated: ambiguous_reference` or `unmatched` (no candidates), per §2.1's
three-way split. No pattern in the table above touches DCS state or invents a contact — every
branch either calls an existing `tools.py` function or escalates.

### Module boundary: `crew_console.py` is not an extension of `console.py`

`console.py`'s docstring is explicit that it is a developer debug tool — one command maps to one
`tools.py` call, no belief logic of its own, and its command set (`contacts`, `show <id>`, ...) is
deliberately terse and tool-shaped, not conversational. `crew_console.py` is the opposite kind of
surface: it exists to simulate what a player will eventually say over SRS, runs typed sentences
through a grammar instead of fixed verbs, and prints *proactive* output the debug console never
does (lifecycle events routed to speech). Folding crew-session parsing into `console.py`'s existing
line dispatch would conflate "developer inspects belief state" with "player talks to Petrovich" —
two different consumers of the same `tools.py` surface, which is exactly the layering `tools.py`'s
own docstring already establishes. Keeping them separate costs one more file; conflating them would
cost a confusing dual-purpose REPL. Both `--console` and `--crew-text` remain available on
`logger.py` side by side.

### Implementation Plan

1. **`PlayerUtterance` + deterministic parser** (`utterance.py`). Pure, no I/O beyond the one
   `tools.find_contact` call for reference resolution. Unit-testable against synthetic
   `ContactStore` fixtures, same pattern as existing `belief/` tests.
2. **`OutgoingSpeech` + templates + routing gate** (`speech.py`). Readback template (verb +
   resolved id → fixed phrasing), contact-report template (single contact, §3.6's hedging-by-
   `certainty` mechanism, reusing `tools._contact_result`/`describe_contact`'s facts — not
   `contact_group`, see scope cut below), lifecycle-event templates for
   `CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED` (the runtime doc's literal "C17 BMP" /
   "C17 lost" / "C17 reacquired" lines), and `route_event()`: check `bypass_gate` first: if true,
   speak immediately, pre-empt, done; if false, render the event's template (all four lifecycle
   kinds get one) and auto-acknowledge via `tools.acknowledge_event` — body already produced final
   text, so this event must not resurface once a real brain's `poll_events`/`list_events` exists.
3. **Escalation entry point** (`escalation.py`). `handle_player_utterance()` builds exactly §3.5's
   payload (`utterance_id`, `transcript`, `transcript_confidence`, `t_sim`, `partial_parse`,
   `situational_header` — reuse whatever header shape D2 already established if it exists in code,
   otherwise a minimal `{contact_counts, our_position}` stand-in — `awaiting_reply_to`). `BrainClient`
   is a two-method `Protocol` (`handle(payload) -> None`, `awaiting_reply_id() -> str | None`, for a
   later `ask_player` round trip). `NullBrainClient` does nothing (§3.5: "if the brain does nothing
   within a timeout, body says nothing" — since there is no brain yet, every escalation "times out"
   immediately, which is the honest behaviour, not a gap). `DebugPrintBrainClient` additionally
   prints the payload labelled `[escalated - no brain yet]` to stderr for session visibility during
   this milestone's own testing, while still producing no spoken output — kept as a debug aid, not
   the default.
4. **`CrewConsole` + `logger.py` wiring**. `CrewConsole.handle_line()`: parse → matched-unambiguous
   → act + readback via `speech.py`; matched-ambiguous or unmatched → build payload, call
   `brain_client.handle()`. A separate `CrewConsole.drain_events()`, called from the same
   poll-loop hook point BL-2.5's `--overlay` already uses (after each `tick()`), runs every new
   event through `route_event()` and prints non-`None` results. `logger.py` gets `--crew-text`
   (mutually exclusive with `--console`/`--overlay` for this milestone — running the debug console
   and the crew session against the same `ContactStore` concurrently is not a validated
   interaction and out of scope) and a `--brain-client debug|null` flag defaulting to `debug`.
5. **Synthetic urgent-event path for the bypass_gate demo**. No real threat-perception channel
   exists yet (missile launch / tracer detection is unbuilt and gated on unresolved DCS-internals
   questions already flagged in plan.md §7) — build a small test/console-only injection point (a
   `CrewConsole` command, e.g. `!inject-urgent <contact_id> <text>`, clearly marked as a test
   harness, not a production intent) that constructs a `bypass_gate: true` event and pushes it
   through `route_event()`. This demonstrates the mechanism (ordering, pre-emption, exemption from
   cooldown) without pretending a real detector exists.
6. **Tests, then the scripted acceptance session.** Unit tests per module first (parser table,
   template rendering incl. `certainty` hedging via `visible`/`last_seen_ago_s`, gate ordering,
   auto-ack, escalation payload shape). Last, an end-to-end `test_crew_console.py` scenario that
   feeds the exact runtime-doc sequence (detect → "watch C17" → readback → lost → reacquired →
   "where was that BMP?" → memory-backed answer) plus one contact-report trigger and one injected
   urgent call, asserting on printed output — this is the automated form of the milestone's
   acceptance criterion, run before asking the user for a live typed-session acceptance pass.

### Risks & Unknowns

- **Merge-order gap, not a blocker:** place-name references ("watch the village") and any
  situation-summary intent ("sitrep") are unmatched on this branch and stay so until BL-5 merges
  and a follow-up commit adds `find_place`/`get_situation` rows to the pattern table. If BL-5a
  merges first, this is a known, documented gap in the grammar, not a bug. If BL-5 merges first,
  re-verify the pattern table still composes against `feature/bl5-tool-api`'s actual `tools.py`
  before wiring those rows in (function shapes above were read from that branch's code as of
  2026-09-09/10 and could still change before its own merge).
- **No real urgent-event source.** The urgent path is demonstrated via manual injection (Stage 5),
  not a live threat detector. Do not read "urgent call works" from this milestone as "threat
  detection works" — those remain two separate, unresolved research questions (§7).
- **No contact clustering exists** (explicitly out of scope per `docs/concept/
  PETROBRAIN_RUNTIME.md` line 336). The contact-report template in this milestone is
  single-contact, not §3.6's multi-contact `contact_group` worked example. If/when clustering
  lands, the template needs a second variant, not a rewrite — keep the single-contact template's
  facts shape a subset of what a future `contact_group` shape would need (composition of one).
- **Auto-acknowledge interaction with BL-5's `poll_events`.** `route_event()` acknowledges any
  event it templates. Once BL-5 merges and a real brain exists, confirm `poll_events` (== today's
  `list_events(unacknowledged_only=True)`) genuinely never re-surfaces a body-already-spoken event
  — the mechanism should already guarantee this (acknowledged events are filtered), but it hasn't
  been exercised against a second consumer of the same queue yet.
- **Regex-table parser is a new, untested grammar shape in this codebase.** False-negative
  escalations are cheap by design; a false-positive match (wrong intent, high confidence) is not.
  Needs deliberate adversarial test cases (partial phrase overlaps between patterns, e.g. "watch
  out for that BMP" should not match the `watch` intent) before this is trusted beyond the typed
  debug session.
- **`situational_header` shape is underspecified.** §3.5 references "the D2 header, same as any
  other turn" but D2 (§4) is a design-decision discussion, not a data-model entry, and no code
  builds this header yet. Stage 3 uses a minimal stand-in; do not treat that stand-in as the final
  shape — BL-6's mission-phase work is likely to want to extend it.

### Second-Order Effects

**Unblocks:** PB-7/PB-8 (BL-10) narrow to a transport swap — replace `CrewConsole`'s stdin/stdout
with the SRS adapter's `PlayerUtterance`/text-to-speak channel, same `parse_utterance` →
`route_event` → `handle_player_utterance` pipeline underneath. It also gives BL-6 (relevance
scoring) and BL-7 (threat-detection-driven urgent calls) a proven hook point — `route_event()`'s
`bypass_gate`-first check and BL-4's existing cooldown are the two places those milestones plug
into, rather than needing to invent the outbound gate from scratch under time pressure once a real
brain or a real threat channel exists. **Narrows:** once `PlayerUtterance`/`OutgoingSpeech` are
committed here, BL-6/BL-7 inherit these shapes rather than getting to redesign them — reasonable
given §5 already specified them, but worth naming as a real constraint on those milestones' plans.

### Invariant check

- Code owns truth, models own interpretation: the parser and gate are pure/deterministic, call
  only existing `tools.py` functions, and never invent a contact/fact — escalation carries
  `reason_escalated` instead of a guess.
- Provenance/uncertainty: templates read `certainty`/`semantic` fields already present on
  `ContactResult`; no new fact-derivation path is introduced that could drop provenance.
- DCS read-only, no installation writes: untouched — this milestone has no DCS I/O of its own.
- Module independence: no new cross-subproject imports; `crew_console.py` stays inside
  `body-layer`, consuming only `belief.tools`/`belief.contacts`/`belief.events`.

### Decisions — resolved by the user, 2026-09-10

- **Manual/console injection of a `bypass_gate: true` event is accepted** as this milestone's
  "urgent call" proof, given no real threat-detection channel exists yet. Proceed with injection
  (Stage 5) as a clearly-labelled test harness, not a detector.
- **`--crew-text` mutually exclusive with `--console`/`--overlay` for this milestone is accepted**
  (Stage 4) — acceptable scope-narrowing.
