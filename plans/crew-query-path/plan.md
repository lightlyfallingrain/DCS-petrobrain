# The crew query path: `report`/`describe <what> <where> <how far>`

Decisions cited as **D<n>** are from `plans/post-review-fixes/explore-notes.md`, "Decisions this
conversation produced" (user direction, 2026-10-05/06). The two that own this plan are **D12** (the
grammar) and **D13** (answers summarise). §7 and §8 of those notes are the supporting argument.

### Goal

Turn `report`/`describe` from four enumerated token families that answer with an enumeration into
**one slotted command** — `report|describe [what] [where] [how far]`, every slot optional — that
answers with **one summary utterance whose job is to aim the pilot's eyes**.

---

## What I measured before designing (three corrections to the brief)

Run against `command_matcher.match_transcript` directly, both on `main` and on the
`feature/sortie-refinements` snapshot. These change the design, so they come first.

### 1. `BL-B28` is not a `say_again`/`confirm` asymmetry. It is a silent wrong-direction match.

| transcript | result |
|---|---|
| `"report left"` | `token='report_bearing_e'`, ratio **0.75**, `ambiguous=True` |
| `"report right"` | `token=None`, ratio 0.0 |
| `"scan left"` / `"scan right"` | `scan_left` / `scan_right`, ratio 1.0 each |

**`report left` resolves to "report east."** The `confirm` the pilot heard 40 seconds before the
`say_again` was Petrovich offering to report *a compass direction he had not been asked about* —
and `left` lands on `east` purely because `"report left"` and `"report east"` differ in one of two
words. The backlog item reads this as "a missing right-hand form"; it is worse than that, and the
fix is not a phrase.

**Root cause:** there is **no `report_left`/`report_right` token at all.** `PHRASES` carries
`scan_left`/`scan_right`/`scan_ahead`/`scan_full`, but the report side has only the eight cardinals,
the nine forward clock hours, and `report_bearing_deg`. The own-ship-relative frame exists for
`scan` and has never existed for `report`. That asymmetry is the defect, and **left/right are a
`where` value in D12's grammar** — so `BL-B28` is not a side fix, it falls out of this plan's Stage 1.

### 2. The `describe` synonym already shipped, and only covers the bare form.

`feature/sortie-refinements` commit `0caa39e` added `"describe"`/`"describe contacts"` to
`PHRASES["report_all"]`. Measured on that branch:

| transcript | `main` | branch |
|---|---|---|
| `"describe two o'clock near"` | `None`, not even anchored | `None`, **anchored** |
| `"report two o'clock near"` | `report_clock_2` (0.75) | `report_clock_2` (0.75) |

So `describe` is now an *anchorable verb* but not a substitutable one: every slotted form said with
`describe` fails where the same form said with `report` succeeds. **This plan is what makes the
shipped synonym actually usable**, and it does not duplicate `0caa39e` — it consumes it.

### 3. The distance band is already being heard and silently discarded.

`"report 2 o'clock close"` → `report_clock_2` at ratio 0.75. The extra word costs score but clears
`MATCH_FLOOR`, so the *where* works and the *how far* is dropped without trace. D12's band slot is
therefore not new recognition surface so much as stopping a silent drop.

### 4. `WM-B1` is done; the landmark blocker is somewhere else entirely.

The brief says `WM-B1` is "already open". `world-model/ROADMAP.md:599` marks it **`[x]`,
implemented on `fix/latin-place-names` (2026-10-02)** — `_select_name` prefers
`name:en`/`int_name`/`name` and Latin-1-checks the result. `query.search.find_place_by_name` exists
and works. What remains is a **full-theatre rebuild** for the data to take effect.

But that is not what blocks `"south of <village>"`. **The real blocker is open-vocabulary
recognition**: a Syrian village name cannot go into a closed GBNF grammar, and `vocabulary.py`
already states the rule for exactly this case — *"that target set is open, so it cannot be
enumerated into a grammar, and it belongs to free speech once the brain layer exists."* The landmark
slot is gated on the brain layer / free-speech STT path, not on place names. See Stage 5 for how it
ships later without redesign, and what it does in the meantime (nothing, deliberately).

---

## Design

### Decision A — one slotted `report` token, additively, modelled on `follow`

Enumerating the cross-product is not an option: 9 hours × 8 cardinals × 3 relative × 3 bands × 7
descriptors is in the thousands, against a closed grammar that has to list what it admits.

`follow` already solved this shape. `command_matcher.match_transcript` (`:488-494`) tries
`_parse_follow_slots` **before** the phrase table, precisely because a clock-only `"follow two
o'clock"` would otherwise score against `"report two o'clock"`. The report path gets the identical
treatment:

- New token `"report"` in `VOICE_ONLY_TOKENS`, phrase `("report",)`-style bare verb, with
  `_parse_report_slots` tried before the phrase table and after the `follow` branch.
- `_REPORT_VERBS = ("report", "describe")`, both fuzzy-tested at `VERB_FLOOR`, so **every** slotted
  form works under either verb. This is the one change that makes `0caa39e` complete.
- **The existing `report_all` / `report_clock_*` / `report_bearing_*` / `report_bearing_deg` tokens
  stay.** They are referenced by `LEGACY_F10_TOKENS` ordering, by the STT bench corpus
  (`tools/stt_bench.py` prompts are built from `PHRASES`), and by `DISPATCHED_COMMAND_TOKENS`'
  pinned test. Removing them is a separate retirement, not this plan's business. A zero-slot
  `"report"` falls through to `report_all` exactly as today.
- **Verb-branch ordering is load-bearing**: `follow` first, then `report`/`describe`. `"follow"` and
  `"report"` are far apart under `SequenceMatcher`, so the two branches do not contend — but the
  order must be pinned by a test, because the follow branch's own comment already records this
  collision class.

**Slots** (all optional, mirroring `follow`'s `dict[str, int | str] | None`):

| slot | values | parser |
|---|---|---|
| `descriptor` | `DESCRIPTOR_WORDS` (`armor`, `truck`, `infantry`, `sam`, `aaa`, `ship`, `group`) | **reuse `parse_descriptor` unchanged** |
| `clock` | 1–4, 8–12 | **reuse `parse_clock` unchanged** |
| `sector` | the eight cardinals | small new parser over the existing word list |
| `relative` | `left` / `right` / `ahead` / `full` | small new parser; **this is `BL-B28`** |
| `band` | `near` / `medium` / `far` | new parser, word table below |

Four of the five already exist. `descriptor` and `clock` are reused verbatim, which also means
`"report group near"` (today `None`) and `"report armor north"` work for free.

**Band vocabulary**, from D12's own numbers, several spoken forms each because this is the slot the
pilot will phrase loosely: `near` ← *near, close, close in* (<2 km) · `medium` ← *medium, medium
distance, mid* (2–5 km) · `far` ← *far, far out, distant, long* (5 km+). Boundaries as D12 gives
them, with 2 000 m / 5 000 m as the only two constants.

**Where slots are mutually exclusive.** `clock`, `sector` and `relative` all answer *where*; a
transcript carrying two is a recognition failure, not a conjunction. Two present → `token=None`,
`verb_anchored=True` — the *detected* error shape `parse_bearing`'s illegal-bearing branch already
uses, which earns a "say again" rather than a guess.

### Decision B — the filter is a span, not an equality, and `relative`/`band` reuse existing tables

`_handle_report` today filters `relative_now["clock_position"] != clock` — an **exact hour**. D13's
answer form speaks a bearing *span* ("one o'clock through two o'clock"), and the pilot saying "two
o'clock" means *around* two. So the clock filter widens to ±1 hour, reusing
`callouts.CALLOUT_GROUP_CLOCK_SPAN_HOURS = 1`, which is already documented as *"two reports whose
clock positions are this close read as the same direction to a listener."* That constant is the
project's existing answer to this exact question — do not introduce a second one.

`relative` resolves through **`perception.gaze._RELATIVE_SECTOR_WEDGE_DEG`** (center, half-width per
`RelativeSector`), the same table `attention.project_relative_area` uses — so `report left` and
`scan left` agree on what "left" means by construction. `sector` keeps the existing ±45°.

`band` filters on `relative_now["range_m"]`, which `relative_geometry` already returns.

`descriptor` reuses **`_FOLLOW_DESCRIPTOR_OP_CLASSES`** and the three-valued logic already in
`_descriptor_score` (`crew_console.py:1275`): exact class match / unclassified / known-wrong class.
Report needs a *filter*, not a score, so extract the three-way verdict into a named predicate both
call. **Unclassified contacts are included** in a `report armor` answer, hedged in the wording —
the same judgement `_descriptor_score` already records (*"he is pointing at a thing he believes is
armour — matching it is right"*), and D13's graceful-degradation rule says the same.

`"group"` keeps its non-classification meaning: `cardinality.lo > 1`, per that function's own branch.

### Decision C — the answer: one summary utterance, replacing the enumeration at the pull site

Today `_handle_report` resolves each group, renders `render_group_full_disclosure` per group, sorts
by `report_priority`, truncates at `REPORT_MAX_GROUPS = 3` and joins. **That is mock A**, the one
the user did not choose.

New `speech.render_report_summary(...)`, taking aggregates computed over the in-scope facts, not
texts:

| part | derived from | wording |
|---|---|---|
| count | sum of `cardinality` `lo`..`hi` over in-scope contacts | "About eight units" |
| dominant class | modal `parent_class_of(classification.value)` → `_OP_CLASS_DISPLAY_PLURAL` | "mostly infantry" |
| bearing span | min..max `relative_now["clock_position"]` | "one o'clock through two o'clock", collapsing to "at two o'clock" when min == max |
| distance band | max `range_m` over in-scope, bucketed | "inside two kilometres" |
| deferral | **at most one** low-confidence or stale group | "Still checking the truck group." |

Every input already exists on `facts`; nothing new is computed from the world and no new belief
field is needed. The spoken plural table (`_OP_CLASS_DISPLAY_PLURAL`) is already exhaustiveness-
tested against the object model, so a new `OP_*` class fails a test rather than reaching the audio
channel.

**`render_report`/`REPORT_MAX_GROUPS` stay in place, unused by this path**, until the user has flown
the summary. If the summary reads too thin, reverting is one call site. Do not delete them in this
plan.

**Length bound, and where it comes from.** `callouts.speech_duration_s` is
`MIN_UTTERANCE_S + words / SPEECH_RATE_WPS` (0.6 s + words/2.5). The user's chosen mock B is **24
words ≈ 10.2 s**. So the budget is *measured from the answer he accepted*, not guessed:
`REPORT_SUMMARY_MAX_WORDS = 25`. When the parts overflow it, the **deferral clause drops first,
then the dominant-class clause** — count, direction and band are the pointer, and the pointer is the
whole product. Say in the constant's docstring that it derives from mock B, so a later tuner knows
what it would be contradicting.

### Decision D — no-omniscience on a *pull*, which is not the same case as D11's push gate

A query reads belief only (`get_contacts`), and belief is already perception-bounded — so **presence
claims are safe regardless of where Petrovich is currently looking.** The invariant bites in two
other places, and only those two:

1. **Absence claims.** `render_no_view` already exists for exactly this (*"asserting absence from
   nothing, rather than inventing presence from nothing"*) and fires today for a rear-hemisphere
   `sector`. It extends unchanged to `relative`. But `render_clear` still fires for any *forward*
   direction with nothing believed — **including one he has never looked at**, which is a false
   claim shipping today. Stage 4 addresses it.
2. **Freshness.** A remembered contact must be spoken as remembered. `_PHRASING_CERTAINTY` already
   has the vocabulary (`observed`→current, `tracked`→recent, `estimated`→remembered), and
   `decay.OBSERVED_WINDOW_S` (= `SCAN_CYCLE_PERIOD_S`, with assertions pinning it to the scan cycle)
   is already the project's "how long since a look is still fresh" bound. Reuse it; do not add a
   staleness constant.

**Explicitly: `contacts._callout_may_speak` must NOT be applied to the pull path.** D11 extends that
gate to every *callout* kind, and a later implementer working D11 will be tempted to apply it
uniformly. Belief survives the aircraft turning away, and the pilot asked the question — filtering
his own query by current gaze would answer "nothing there" about a contact Petrovich genuinely
believes in. The honest shape is: **report it, qualified** ("last I saw"), never **withhold it**.
This sentence exists so D11's work does not silently break this one.

### Decision E — the seam

Everything mechanical stays in `audio-adapter` (normalise, anchor, parse slots, separation) and
body-layer receives `{token: "report", slots: {...}}` over the existing HTTP/JSON channel. No shared
import, no new seam. The cost: `DESCRIPTOR_WORDS` ↔ `_FOLLOW_DESCRIPTOR_OP_CLASSES` is a
**hand-synced mirror pair** (both files say so), and the band words become a second such pair. That
is the module-independence rule's standing price; the mitigation is a test on each side asserting
its own table's membership, so a drift fails a test rather than a sortie.

---

## Affected Modules / Files

**audio-adapter**
- `src/vocabulary.py` — new `"report"` token; `_BAND_WORDS` + `parse_band`; `parse_sector_word`;
  `parse_relative_word`; `_REPORT_VERBS`. `parse_descriptor`/`parse_clock` untouched.
- `src/command_matcher.py` — `_parse_report_slots` and its verb branch, after the `follow` branch and
  before the phrase table; mutual-exclusion rejection for two *where* slots.
- `tests/test_command_matcher.py` — the measured cases above as regressions: `report left` and
  `describe left` both resolve `relative=left` and **never** `report_bearing_e`; `report right`
  symmetric; `describe <any slot form>` ≡ `report <same form>`; branch order pinned; two *where*
  slots → `token=None, verb_anchored=True`.
- `tests/test_vocabulary.py` — `PHRASES`/`TOKENS` parity for the new token; band/sector/relative
  mirrors.

**body-layer**
- `src/belief/crew_console.py` — `"report"` into `DISPATCHED_COMMAND_TOKENS`; dispatch branch; a
  `_describe_token_for_confirm` slots branch for `report` (model it on the `follow` branch at
  `:522-533`, which already composes a slot readback); `_handle_report` gains
  `descriptor`/`relative`/`band`, widens the clock filter to ±1 hour, and calls the summary
  renderer; the `_descriptor_score` three-way verdict extracted into a shared predicate.
- `src/belief/speech.py` — `render_report_summary`, `REPORT_SUMMARY_MAX_WORDS`, band wording.
  `render_report`/`render_clear`/`render_no_view` unchanged.
- `src/belief/decay.py` — **read only.** Reuse `OBSERVED_WINDOW_S`; add nothing.
- `tests/test_crew_console.py`, `tests/test_speech.py` — filter matrix and summary wording,
  including empty / all-stale / 40-contact cases.

**Not touched, deliberately:** `tools.py` (`facts` already carries every input), `groups.py`,
`callouts.py` (the push path keeps `render_group_full_disclosure`), `contacts.py`, world-model.

---

## Implementation Plan

**Stage 1 — the slotted token, and `BL-B28` with it.** `audio-adapter` only: the `report` token,
the three new parsers, `_parse_report_slots`, `_REPORT_VERBS`. Body-layer accepts the token and
dispatches it to today's `_handle_report` using only `clock`/`sector`, ignoring the rest. **At the
end of Stage 1 `report left`, `report right` and `describe two o'clock` all work and none of them
can resolve to a cardinal.** The single most concrete evidence that the channel is open, shippable
on its own.

**Stage 2 — the filter slots.** `descriptor`, `band`, `relative` reach `_handle_report`; the shared
descriptor predicate is extracted; the clock filter widens to ±1 hour. Still answering with today's
enumeration, so Stage 2 is testable against unchanged speech output.

**Stage 3 — the summary answer (D13).** `render_report_summary` and the word budget; the pull site
switches from per-group enumeration to aggregates; freshness qualifier from `OBSERVED_WINDOW_S`;
`render_no_view` extended to `relative`. **This is the stage whose output the user has to hear**, so
it ends with a test card naming the branch.

**Stage 4 — "haven't looked there" (closes the false `clear`).** A per-clock-hour
`last_gazed_sim` ledger (12 floats, one write per poll from the live gaze), so an empty answer can
distinguish *scanned and empty* → `render_clear` from *never scanned / not within
`OBSERVED_WINDOW_S`* → a new "Haven't looked at two o'clock yet" line. Independently mergeable, and
genuinely optional — Stages 1–3 stand without it. Note that gaze is a pure function of sim time, so
this could instead be *derived* from the active `ScanPlan`; a ledger is proposed because derivation
silently goes wrong across a plan change, and 12 floats is not worth the fragility.

**Stage 5 — landmark `where`, after free-speech STT.** Parse `south of <place>` on the **typed**
console path only (`utterance._PATTERNS`, where text is already free), resolving via
`query.search.find_place_by_name` + `_SECTOR_CENTER_DEG` into the same `sector`-shaped filter Stage 2
builds. Because it lands as an existing filter shape, wiring it to voice later is adding a parser,
not a redesign. **Not started in this plan.** In the meantime a spoken `"report south of Gemerek"`
anchors, finds no *where* slot, and answers as a bare `report` — the honest degradation, and the
pilot hears a general report rather than a `say_again`.

Each stage runs its own touched subprojects' gate: `cd audio-adapter && .venv/bin/ruff format
. && .venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest`, and the same inside
`body-layer`. mypy config discovery is CWD-only.

---

## Risks & Unknowns

- **The new slot parsers run on every anchored transcript.** `parse_descriptor` already builds a
  word set per call; three more scans of a ≤10-word transcript is nothing, but the branch sits in
  front of the phrase table on the live path. Keep each parser a single pass over the already-
  normalised words.
- **Band words are unbenched on this user's voice**, like every token added without re-recording the
  corpus. `near`/`far` are short; `close` is phonetically near `clock`, which the clock slot also
  consumes — the one collision worth measuring. The mutual-exclusion rule limits the damage (a
  transcript that lands both reads as a detected error), but a bench clip set is the real answer and
  is not in this plan.
- **`REPORT_SUMMARY_MAX_WORDS = 25` is calibrated against a mock, not a flight.** 10 s is a long
  time in a hover. It may need halving, which is why the drop order is specified rather than left to
  whatever the formatter happens to truncate.
- **A summary can hide the one thing that mattered.** Aggregating eight contacts into "mostly
  infantry" discards a single SAM among them. `_OP_CLASS_DISPLAY`'s own comment records the
  governing judgement — *"the difference between a short-range and a long-range SAM is the
  difference between a threat you can fly around and one you cannot"* — so an air-defence class
  present in scope should survive aggregation even as a minority. Flagged as **Q2**; it interacts
  with D6's air-defence carve-out and should not be resolved silently.
- **Widening the clock filter to ±1 hour changes existing `report_clock_*` answers**, which until now
  were exact-hour. More contacts in scope per query. Intended (it is what makes a span sayable), but
  it is a behaviour change to a shipped command, not purely additive.
- **The mirror pair grows.** Two hand-synced tables across the audio-adapter/body-layer seam become
  three. Tests on each side are the mitigation, not a fix.
- **`feature/sortie-refinements` is unmerged** and carries `0caa39e` plus Item 1's rewrite of
  `speech.py`'s per-contact location fragment. Stage 3 edits the same file. **Merge that branch
  first**, or Stage 3 conflicts with it.

---

## Second-order effects

1. **It converges with D10.** `plans/` has `feature/d10-structured-candidates` (token overlap over
   structured reference candidates) for `follow <descriptor>`. `report <descriptor>` is the same
   resolution problem one step along — same descriptor vocabulary, same three-valued class verdict,
   differing only in filter-vs-score. Extracting the shared predicate in Stage 2 is what lets D10
   improve both at once instead of improving one and diverging from the other. **D10's work should
   target the shared predicate, not `_resolve_follow_target`.**
2. **It constrains D11.** Decision D's "do not apply the observability gate to the pull path" is a
   boundary D11's own implementation has to respect. Worth a cross-reference in whichever plan does
   D11 (`plans/post-review-fixes/`), per the standing amend-open-plans rule.
3. **It is the brain layer's first real consumer shape.** The slotted `report` is a closed-grammar
   approximation of a question a pilot would just *ask*. When free speech arrives, the brain's job
   becomes filling these same five slots from open text and calling the same handler — so this
   plan's slot schema, not a new one, is what the brain layer should target. The landmark slot being
   parked in Stage 5 rather than approximated is deliberate for that reason.

---

## Questions for the user (queued — no answer needed before Stage 1)

**Q1 — Should the band be a filter or a hint?** `"report two o'clock near"` could mean *tell me only
about what is inside 2 km* (filter — proposed) or *start with the near stuff* (sort key, nothing
excluded). The filter reading is the literal one and makes the answer shorter, but it means a tank
at 2.1 km goes unmentioned to a pilot who asked about two o'clock. My recommendation: **filter**, on
the grounds that he asked a narrow question and can ask a wider one — but it is his call.

**Q2 — Should an air-defence contact always survive the summary's aggregation?** Eight contacts,
seven infantry and one SAM, currently summarise as "mostly infantry". Adding "and a short range SAM"
costs ~5 of the 25-word budget. D6 already treats air defence as the exception elsewhere (threat
envelopes key on believed classification), and `_OP_CLASS_DISPLAY`'s own comment argues the SAM tier
is the most decision-relevant thing in a call. Recommendation: **yes, always named**, and the budget
absorbs it by dropping the deferral clause first.

**Q3 — Is `REPORT_SUMMARY_MAX_WORDS = 25` (~10 s) right?** It is taken from the length of mock B,
the answer you chose, so it is at least defensible — but mock B was read on the ground. If 10 s of
Petrovich talking is too much in a hover, say so and the number halves to ~13 words, which still
carries count, direction and band.

**Q4 — Confirm that `report left` was a wrong-direction match, as measured.** `"report left"`
resolved to **report east** at 0.75. Do you recall the confirm prompt you heard that day — did it
say "report east, confirm?"? If it did, that pins the diagnosis to the live path and not just to the
matcher in isolation.
