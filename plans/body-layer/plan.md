# Body Layer — Architecture Plan

> **Status: Draft / provisional — first pass, iterate later.**
>
> Same framing as `docs/concept/PETROBRAIN_RUNTIME.md`: this is a target architecture, not a
> contract. It depends on (1) what the aircraft layer can actually export — in particular the
> still-unresolved Petrovich-perception question, (2) what the Mission Interpreter will eventually
> produce, (3) what shape the brain layer's local model turns out to tolerate. Expect the
> brain-facing API in particular to be rewritten once a real small model is driving it.
>
> Nothing here is scheduled for implementation yet — the aircraft layer is paused mid-stage-3 and
> is a hard prerequisite for most of this. This plan exists so body-layer decisions are recorded
> before they get made incidentally inside aircraft-layer or brain-layer work.

**Architect note on model depth:** this plan sets the API contract between deterministic code and
an LLM — the seam the whole "code owns truth, models own interpretation" principle lives on, and
the hardest thing here to change later. It was drafted at opus depth. Section 3 (brain-facing API)
and Section 4's decision D2 are the parts most worth re-reviewing at opus depth before
implementation starts, once a concrete small model has been picked.

---

### Goal

Define the body layer: the deterministic process that owns Petrovich's belief state — contacts,
attention, mission phase, events, spatial semantics — sits between the brain (LLM) and the
aircraft layer (DCS I/O), and exposes a narrow, self-describing query/command API that a small,
fast local model can operate reliably.

---

## 1. Scope and Boundaries

### What body owns

- Contact identity and data association (observations → persistent contact records).
- The observation-vs-belief separation (raw observation log vs. synthesized current belief).
- Uncertainty and per-attribute decay.
- Attention state (per contact and per area).
- Event detection and the event log (`CONTACT_DETECTED`, …).
- Mission-phase state machine.
- Mission-relevance scoring.
- Egocentric geometry (bearing/range/clock/relative-altitude, computed on demand from absolute
  positions + current ownship state).
- Semantic spatial description ("east side of the village") — by calling the world model, not by
  reimplementing it.
- Translation of brain intents into aircraft-layer command sequences, plus the inspect-and-adapt
  loop that verifies the outcome.
- **Deterministic parsing and dispatch of player utterances** (transcript in, action out), and the
  gate that decides whether an utterance can be handled deterministically or must go to the brain.
- **Templated utterance generation** — command readbacks, contact reports, urgent reactive calls.
- The brain-facing API surface itself.

### What body does not own

| Concern | Owner | Body's relationship to it |
| --- | --- | --- |
| What we're doing and why | brain | Body records the current intent as opaque state; it never decides it. |
| Wording, phrasing, reference resolution from free text | brain | Body supplies facts + phrasing hints; brain writes the sentence — *except* for the templated classes body writes itself (§2.1). |
| Audio capture/playback, PTT debounce, silence/noise gating, STT, TTS | SRS adapter | **Settled**: raw audio never crosses into body, and body never sees a transmission that was not real speech. Signal-level gating (duration, energy) is the adapter's. Any *context-dependent* suppression later — e.g. tighter tolerance mid-engagement — is body's, acting on already-transcribed `PlayerUtterance` records; that refinement is not needed now. Which *process* hosts the adapter is still open (§7). |
| Reading/writing DCS | aircraft layer | Body is an HTTP client of it. |
| Static geography | world model | Body queries `describe_position`-style APIs; it does not cache-and-diverge from them. |
| Mission understanding (role, phases, threats, player intent) | Mission Interpreter | Body loads it once at mission start as read-only reference. |
| Long-lived memory across missions | memory layer | Body owns *active mission* memory in-process; campaign/world/player/aircraft memory are separate stores body reads and appends to. |

### Seams

**body ↔ aircraft-layer** — HTTP/JSON client, per `plans/aircraft-layer/plan.md`. Body polls
`GET /telemetry/latest` and `GET /telemetry/since/{t}` for ownship state; later, a
perception/contacts endpoint (shape unknown, see §7) and a command endpoint. Body is the *only*
consumer of the aircraft layer — nothing else in the system talks to DCS. Assume commands are
fire-and-forget with no completion guarantee; body is responsible for verifying outcomes (D3).

**body ↔ world-model** — in-process Python import (`world-model/src/query`) if body runs where the
SQLite store lives, otherwise a thin local HTTP wrapper. Read-only, no writes. Body must treat
world-model output as *reference data with provenance*, and must not strip that provenance when
passing descriptions to the brain — an "east side of the village" derived from an OSM-matched
settlement is a different confidence claim than one derived from DCS raster.

**body ↔ memory** — a store interface, not a shared object graph. Active mission memory is body's
in-process state, checkpointed to disk for debugging/crash-recovery, and discarded at mission end
(per `division-or-responsibility.md`: replaying a mission starts clean). Campaign/world/player/
aircraft memory are separate persistent stores body reads at mission start and appends to at
mission end. **Recommendation: do not build the persistent memory stores in this phase** — define
the interface, back it with an in-memory no-op, and let real stores land after active mission
memory has proven out.

**body ↔ SRS adapter** — text in, text out, over LAN. Inbound: `PlayerUtterance` records
(transcript, timestamps, confidence, duration). Outbound: text to speak, plus a priority flag so
the adapter knows an urgent call pre-empts whatever is currently being spoken. Body never sees
audio and never handles PTT. Per `division-or-responsibility.md`'s new "Speech / audio (SRS ICS)"
section, the adapter is proposed as a sibling of the aircraft layer rather than part of it — SRS
is a separate external application, not DCS — but see §7, this placement is not settled.

**body ↔ brain** — the important one. See §3.

---

## 2. Core Responsibilities

Reconciling `PETROBRAIN_RUNTIME.md`'s "runtime" against the brain/body/aircraft/memory split: the
runtime doc describes one component, but almost everything in it that is *mechanism* rather than
*language* is body-layer work. Explicit mapping:

| PETROBRAIN_RUNTIME.md section | Layer |
| --- | --- |
| Perception adapter | aircraft (extraction) + body (normalization into observations) |
| Contact identity / data association | **body** |
| Observation vs. belief | **body** |
| Spatial memory (absolute + historical relative) | **body** |
| Semantic contact context | **body** (via world-model queries) |
| Uncertainty and decay | **body** |
| Attention model, area attention | **body** (state) + brain (resolving *which* contact from text) |
| Event model | **body** |
| Mission relevance | **body** (deterministic rules first, per the doc) |
| Runtime mission state machine | **body** |
| Runtime LLM role (reference resolution, intent, language generation) | brain |
| Proactive speech: *whether* to speak | **body** (relevance + cooldown) |
| Proactive speech: *how* to phrase it | brain, except templated classes (§2.1) |
| Speech input/output — SRS intercom: routing gate, intent parse, templates | **body** |
| Speech input/output — audio, debounce, gating, STT/TTS | SRS adapter |
| Reactive urgent calls (bypass the cooldown gate) | **body** |
| Senior model escalation | brain |
| Debugging/inspectability | **body** (it owns the state worth inspecting) |

Notable per-responsibility notes:

- **Data association** is a tracking problem, not an LLM problem. Start deliberately dumb:
  gate on classification compatibility + a range gate that grows with elapsed time since last
  observation. When ambiguous, prefer creating a *new* contact over wrongly merging — a duplicate
  contact is a visible, correctable error; a bad merge silently corrupts belief history.
- **Observation vs. belief**: observations are append-only and immutable. Belief is derived and
  recomputable from the observation log. This makes the whole layer replayable from a recorded
  observation stream — which is the only practical way to test any of it without a live DCS
  session, and should be treated as a hard design requirement, not a nice-to-have.
- **Decay** should be per-attribute with explicit half-lives (identity slow, exact position fast,
  general area medium, motion medium) and must be a pure function of `(observation, now)` so it is
  trivially testable and never requires a background ticker to stay correct.
- **Semantic description** should be computed lazily and cached per (contact, ownship-position-
  bucket), not recomputed per query — world-model queries hit SQLite and this is the one plausible
  hot path in the layer.
- **Inspect-and-adapt loop**: every command body issues to the aircraft layer creates a
  `PendingIntent` with a desired observable end-state, a deadline, and a max-retry count. A
  supervisor tick compares telemetry against the desired state and re-issues or escalates. Crucially
  it must tolerate DCS taking time — "not yet achieved" is not "failed" until the deadline. Scope
  now: sensors/detection only. Flight control deferred, per `division-or-responsibility.md`.

### 2.1 Crew interaction — parse, dispatch, template

Body sits on both halves of the conversation. It receives transcripts from the SRS adapter and it
decides most of what Petrovich says.

**Inbound: parse and dispatch.** A `PlayerUtterance` arrives as text. Body runs a deterministic
intent parser over it — a small grammar of crew phrasing: bearings and clock positions, ranges,
place references, attention verbs, status questions. Outcome is one of:

- **matched, unambiguous** → body acts directly and emits a templated readback. No brain call. A
  readback is confirmation, and it should be fast and identical every time; waiting on an LLM to
  say "scanning 2 o'clock" is the wrong trade.
- **matched but a reference is ambiguous** ("watch *that*") → body resolves candidates
  deterministically (§3.3 `find_contact`) and escalates only the choice, not the whole utterance.
- **unmatched, open-ended, or a genuine question** → escalate to the brain via §3.5, carrying
  the partial parse rather than the raw string.

The parser must fail *loudly and cheaply*: an unmatched utterance costs one escalation, whereas a
wrong confident match makes Petrovich do the wrong thing silently. Bias the grammar toward narrow,
high-precision patterns and let the brain absorb the long tail.

**Outbound: three classes of speech.**

1. **Templated, body-written** — readbacks, contact reports, urgent reactive calls. Body produces
   the final text. See the contact-report worked example in §3.6.
2. **Body-facts, brain-worded** — the existing `facts` / `summary` / `phrasing_hints` mechanism
   (§3.2). Body still supplies a `summary`; the brain voices it.
3. **Brain-written** — advisory and judgement calls ("suggest terrain cover east of target"),
   answers outside template coverage, anything conversational.

**Urgent reactive calls are a distinct event class.** Missile launch, tracer, imminent terrain —
these are templated, body-generated, and **exempt from the cooldown, relevance-scoring and
already-mentioned suppression** that `PETROBRAIN_RUNTIME.md`'s "Proactive speech" section applies
to everything else. They also pre-empt in-progress speech rather than queueing behind it. The two
mechanisms must not be conflated in implementation: ordinary proactive speech is filtered because
chatter is a real failure mode; urgent calls are exempt because silence is a worse one. Concretely,
an event carries `bypass_gate: true` and the event queue checks that flag *before* any other
filter, and urgent events never enter the brain's `poll_events` path at all — body speaks them
directly, then records that it did so.

---

## 3. The Brain-Facing API

The design constraint that dominates everything else: **the brain is a small, fast, local model.**
It will be worse than a large model at multi-step synthesis, at holding a large state blob in
working memory, and at inferring intent from a terse API. It will be reasonably good at picking
one tool from a short list of well-described tools and filling in its arguments.

So: **narrow, enumerable, self-describing, pre-digested.**

### 3.1 Recommendation: fixed enumerable tool set, no open-ended queries

**Recommended.** The brain may only call a fixed set of named functions with typed arguments.
No free-form query language, no SQL-ish filter expressions, no "ask body anything."

Reasoning:
- Every call is validatable before execution, which is the mechanical enforcement of "the model
  does not decide whether the Shilka exists." An open-ended query surface makes it possible for the
  brain to phrase a question whose *premise* is invented, and get a confusingly-shaped answer back.
- Small models compose poorly. A query DSL is a second language to get right on top of the tool
  call; failure modes are silent (a subtly wrong filter returns plausible wrong data) rather than
  loud (an unknown tool name is an immediate, catchable error).
- The tool list doubles as documentation of what Petrovich can *do*, which is a genuine
  design forcing-function — if a capability is not in the list it does not exist.

**Alternative considered: open-ended structured query (e.g. a JSON filter spec over contacts).**
Rejected for now. Its real advantage is flexibility without redeploying body — useful during
development when we don't yet know what the brain needs to ask. Mitigation that captures most of
that value without the cost: keep the tool set *easy to extend* and log every case where the brain
tried and failed to express something, then add a tool. If that log shows a long tail of one-off
needs after real use, revisit — that would be actual evidence, which we don't have yet.

**Alternative considered: give the brain read access to a full state blob each turn** and let it
extract what it needs. Rejected — this is precisely the "huge context, model does the synthesis"
pattern the system's core principle exists to avoid, and it scales badly with contact count.

### 3.2 Pre-digestion tradeoff

**Lean strongly pre-digested,** with a structured escape hatch.

Every fact-bearing response carries three things:
1. `facts` — structured, typed, machine-checkable.
2. `summary` — a plain, flat, English-ready phrasing of the same facts, with hedging already
   correct for the confidence level ("I've got him", "last saw him about a minute ago",
   "I think it was"). Body decides the epistemic register; brain decides the voice.
3. `phrasing_hints` — urgency, brevity, whether this is interrupting.

The brain's job then collapses to *voicing* `summary`, not deriving it. That's the task a small
model is actually good at.

**What this costs:** flexibility. If the player asks something body's summary didn't anticipate
("was it closer to the road or the treeline?"), the brain can't synthesize a new answer from the
pre-digested text — it only has what body chose to summarize. This is why `facts` ships alongside
`summary` rather than instead of it: the brain *can* fall back to structured data for unanticipated
questions, it just isn't expected to for the common path. Flag honestly: the failure mode of
over-digestion is a Petrovich who answers the five questions we designed for very well and is
stiff and evasive on the sixth. Watch for that in acceptance testing; it's the signal to move a
particular answer from `summary` back toward `facts`.

**Where NOT to pre-digest:** anything where phrasing depends on conversational context the brain
has and body doesn't (what was just said, whether the player already knows). Body should never
pre-digest *whether to speak at all* into the summary text — that's an explicit separate field.

### 3.3 Proposed tool set

This is the API's intended *final* shape. It is not built at once — §6 assigns each tool to the
milestone that builds its underlying machinery, and the freeze point is the end of BL-7.

Each tool's description is written as the model will read it — plain language, stating when to use
it and when not to. Grouped by kind.

**Perception / contacts (read)**

```
get_contacts(filter: "all" | "visible" | "watched" | "threats" | "near_aircraft")
  "List what Petrovich currently knows about. Returns short one-line summaries with contact
   IDs. Use this when you need to know what's out there. Use the 'visible' filter when the
   player asks what you can see right now, and 'all' when they ask what you know about."

describe_contact(contact_id)
  "Everything Petrovich knows about one contact: what it is, how sure he is, where it was
   last seen, how long ago, where it is relative to us now, and what it's near. Use this
   before answering any question about a specific contact. Do not guess details that aren't
   in the answer."

get_contact_history(contact_id)
  "The list of times Petrovich actually saw this contact, in order. Use only when the player
   asks about how something changed over time. For 'where is it' use describe_contact."
```

**Reference resolution (read)**

```
find_contact(description: str)
  "Turn something the player said - 'that Shilka', 'the one by the road', 'the BMP we saw
   earlier' - into a contact ID. Returns zero, one, or several candidates with a confidence
   for each. If it returns several, ask the player which one. If it returns none, say you
   don't know what they mean - do not invent a contact."

find_place(description: str)
  "Turn a place the player mentioned - 'the village', 'the ridge to the west', 'the LZ' -
   into a place ID from the world model or mission plan."
```

Note: `find_contact` is *body-side deterministic matching* (classification keywords, recency,
spatial qualifiers) returning ranked candidates — the brain supplies the phrase and picks among
the candidates. This deliberately splits reference resolution across the seam rather than handing
it wholly to either side: body has the data, brain has the language. Getting this split right is
one of the higher-risk parts of the design (see §7).

**Attention (command)**

```
set_attention(contact_id, level: "ignore" | "normal" | "watch" | "priority")
  "Change how closely Petrovich follows a contact. Use 'watch' when the player says to keep an
   eye on something, 'priority' when they say it's the main threat, 'ignore' when they say
   forget it or it doesn't matter."

watch_area(place_id, sector?: "north"|"south"|"east"|"west"|"all")
  "Have Petrovich pay attention to a place rather than a specific contact - 'watch the north
   side of the village'."

get_attention_state()
  "What Petrovich is currently watching and why. Use when the player asks what you're
   focusing on."
```

**Situation / mission (read)**

```
get_situation()
  "A short summary of right now: where we are, what's around us, mission phase, the most
   important thing Petrovich is aware of. Use this to orient yourself at the start of a
   conversation or after a gap. Do not call it repeatedly."

get_mission_phase()
  "What part of the mission we're in and what that implies about priorities."

describe_our_position()
  "Where the aircraft is in terms a person would use - near what, how high, heading where."
```

**Aircraft actions (command)**

```
scan_area(place_id | bearing_deg + range_m, reason: str)
  "Point Petrovich's attention/sensors at an area and look for contacts. This takes time -
   it returns immediately with a task ID, and you will get an event when it finishes or
   fails. Do not assume it succeeded. 'reason' is a short note about why, for the log."

get_task_status(task_id)
  "Whether a command you issued has finished, is still running, or failed."

cancel_task(task_id)
```

**Event / speech coupling**

```
poll_events()
  "Things that have happened since you last checked, that Petrovich would notice and might
   want to mention. Each event comes with the facts and a suggested phrasing. You decide the
   wording; you do not decide whether the event happened."

acknowledge_event(event_id, spoken: bool)
  "Tell the body layer whether you actually said something about this event, so it doesn't
   come up again."

say(text: str, urgency?: "normal" | "interrupt")
  "Say something to the player over the intercom. Use this for anything you decided to say
   yourself. You do not need this for readbacks or contact reports - those are already
   spoken before you see them."

ask_player(question: str, about?: utterance_id)
  "Ask the player to clarify something you could not resolve. Use this instead of guessing
   what they meant. Body will match their next reply back to this question for you."
```

Explicitly **not** exposed: anything that writes a fact into belief state. The brain has no tool
to say "there is a BMP at X". Facts enter only through the aircraft layer. This is the mechanical
enforcement of engineering principle 4.

### 3.4 Response shape

```yaml
# describe_contact("C17")
facts:
  id: C17
  classification: {value: BMP-2, confidence: 0.8}
  visible: false
  last_seen_ago_s: 42
  position: {dcs: {x: ..., z: ...}, confidence: 0.6}
  relative_now: {bearing_deg: 118, clock: "4 o'clock", range_m: 2700, relative_alt_m: -340}
  semantic:                          # never bare strings - see §1's provenance rule
    - text: "east side of VILLAGE_12"
      confidence: 0.8                # combined: world-model feature conf x position conf
      provenance: osm_matched        # dcs_raster | dcs_native | osm_matched | derived
      feature_id: VILLAGE_12
    - text: "near ROAD_41"
      confidence: 0.6
      provenance: dcs_raster
      feature_id: ROAD_41
  motion_when_seen: {direction: north, confidence: 0.6}
  relevance: 0.7
  attention: watch
summary: >
  BMP, last saw it about forty seconds ago on the east side of the village near the road,
  heading north. Should be around four o'clock, two and a half kilometres.
phrasing_hints:
  certainty: remembered
  urgency: low
  brevity: normal
```

#### `certainty` — enum and derivation

This field is the entire mechanism by which body, not the model, owns the epistemic register that
`PETROBRAIN_RUNTIME.md` describes ("I see him" / "I lost him" / "Last saw him…" / "I think he
was…"). It must therefore be a stated function of the confidence fields, not a judgement call.

| value | register | condition |
| --- | --- | --- |
| `lost` | "I've lost him." | not visible, `last_seen_ago_s` ≤ 10 |
| `unknown` | "Something was out there, I couldn't tell." | `classification.confidence` < 0.3 |
| `observed` | "I have him." | `visible: true` and `classification.confidence` ≥ 0.5 |
| `uncertain` | "I think he was…" | `position.confidence` < 0.5 **or** `classification.confidence` < 0.5 |
| `remembered` | "Last saw him near the road." | everything else (not visible, both confidences ≥ 0.5) |

Evaluated top-down, first match wins. Order matters: `unknown` must precede `observed`, otherwise a
contact that is currently visible but barely classified (confidence 0.15) would render as "I have
him" with no identity hedge — the exact conflation this table exists to prevent. `lost` was missing
from the earlier enum and is the register the runtime doc calls out explicitly — it is distinct from
`remembered` because losing contact is an *event worth reporting*, whereas remembering is a *state*.
Its window is a plain not-visible-recently condition (no separate transition tracking needed,
consistent with the "pure function of `(contact, now)`" note below) — after `last_seen_ago_s`
crosses 10 the same contact degrades naturally to `remembered` (or `uncertain`/`unknown` if
confidence is also low).

Confidences themselves come from decay (§2), so `certainty` is a pure function of
`(contact, now)` and needs no separate state — consistent with BL-0's replay-determinism
requirement.

Open: the thresholds above are placeholders. They should be tuned against real sessions, not
argued about now; what matters structurally is that they live in one table in body and nowhere else.

### 3.5 Escalation into the brain — `handle_player_utterance`

The tools above are all brain→body. This is the one body→brain entry point, and it is the *only*
way a player utterance reaches the model.

Critically, **the brain is never started from raw transcript text.** It receives the transcript
plus everything body's deterministic parse already extracted — so it is disambiguating a
partly-understood utterance, not parsing from scratch. This is the same principle as §3.2's
pre-digestion, applied to the inbound direction.

```yaml
handle_player_utterance:
  utterance_id: U_31
  transcript: "keep an eye on that shilka by the road"
  transcript_confidence: 0.82        # from STT; 1.0 for typed debug input
  t_sim: 1301.7

  partial_parse:
    matched_intent: set_attention    # null when nothing matched
    confidence: 0.6
    reason_escalated: ambiguous_reference
      # unmatched | ambiguous_reference | multiple_intents | question | low_stt_confidence
    extracted:
      attention_level: watch
      referenced_contact_candidates:
        - {id: C18, why: "ZSU-23-4, seen 20s ago, 80m from ROAD_41", score: 0.9}
        - {id: C22, why: "unknown vehicle, seen 4min ago, near ROAD_41", score: 0.3}
      referenced_places: [ROAD_41]
      bearing_deg: null
      range_m: null

  situational_header: {...}           # the D2 header, same as any other turn
  awaiting_reply_to: null             # set when this answers a prior ask_player
```

`reason_escalated` matters: it tells a small model *what is missing*, which is a far easier
starting point than "here is a sentence, work out what to do." A model told
`reason_escalated: ambiguous_reference` with two ranked candidates has a near-trivial task.

Body's expected outcomes: the brain calls a command tool, calls `say`, or calls `ask_player`. If
the brain does nothing within a timeout, body says nothing — it does not invent a fallback
utterance. Silence is honest; a guessed response is not.

### 3.6 Worked example — contact report templating

This is the concrete validation of §3.2's pre-digestion design, and it is deliberately the case
where body writes the final text rather than handing a `summary` to the brain.

Facts body holds, across three associated contacts in one cluster:

```yaml
contact_group:
  id: CG_3
  member_ids: [C31, C32, C33]
  iff: enemy                        # friendly | enemy | unknown | hostile
  composition:
    - {classification: T-72, count: 3, confidence: 0.8}
    - {classification: BMP-2, count: 2, confidence: 0.7}
    - {classification: infantry, count: unknown, confidence: 0.5}
  relative_now: {clock: "2 o'clock", range_m: 3100, relative_alt_m: -120}
  semantic:
    - {text: "crossroad", feature_id: JUNCTION_88, confidence: 0.7, provenance: dcs_raster}
    - {text: "east of VILLAGE_12", feature_id: VILLAGE_12, confidence: 0.85,
       provenance: osm_matched}
  visible: true
  last_seen_ago_s: 0                 # 0 while visible; drives `certainty` once it isn't
```

Template output:

```yaml
facts: {...as above...}
summary: >
  Enemy, 2 o'clock, 3 kilometres. Group of three tanks, two IFVs and infantry,
  at the crossroad east of the village.
phrasing_hints:
  certainty: observed
  urgency: medium
  brevity: normal
  template: contact_report          # body already produced final text
  bypass_gate: false
```

What this exercises, and why it validates §3.2:

- **The hedging is a function of confidence, not of wording.** `visible: true` and high
  classification confidence give `certainty: observed` → "Enemy, 2 o'clock" — flat, declarative.
  Set `visible: false` and `last_seen_ago_s: 90` and the same template derives
  `certainty: remembered` → "Had enemy, 2 o'clock, three kilometres, about a minute and a half
  ago", with no brain involvement in the epistemics. That was the whole point of body owning
  `certainty`. Derivation rule below.
- **Provenance survives the crossing.** The spoken words say "east of the village"; the `facts`
  block still records that this came from an OSM match at 0.85, not from DCS raster. §1's seam
  rule is not weakened by templating — see the `semantic_claim` note in §5.
- **`summary` is already speakable.** The brain adds nothing here, which is why this class skips
  it entirely — the `phrasing_hints.template` field is what tells the event queue "already final,
  speak it."
- **Where the pre-digestion cost shows up** (§3.2's honest caveat): if the player then asks "which
  one's the closest?", the template has no answer and `facts` has to carry it. `contact_group`
  therefore keeps `member_ids` rather than collapsing to counts — a general rule worth stating:
  **templates may summarize, but the `facts` block must stay decomposable.**

The urgent variant, for contrast:

```yaml
summary: "Missile launch, 9 o'clock! Break right!"
phrasing_hints:
  certainty: observed
  urgency: critical
  brevity: minimal
  template: threat_reaction
  bypass_gate: true                 # skips cooldown/relevance; pre-empts in-progress speech
```

---

## 4. Design Decisions — Strengths / Weaknesses

### D1. Event-driven vs. poll-driven body ↔ brain

**Push (body invokes the brain when something happens).**
Strengths: proactive speech falls out naturally; brain is idle between events, no wasted
inference; latency from event to callout is minimal.
Weaknesses: body must decide *what warrants waking the brain* — that judgment now lives in
deterministic code; a burst of events can queue up multiple inferences on a small model that can
only do one at a time; harder to reason about mid-conversation interleaving.

**Pull (brain polls body on a tick).**
Strengths: brain controls its own tempo, never overrun; simple to reason about; trivially
testable.
Weaknesses: latency floor equal to the tick; wasted inference on quiet ticks — expensive when
every tick is a local LLM call; proactive urgency ("he's shooting at us") is bounded by the tick.

**Recommendation: hybrid — pull-by-default with a push interrupt for high-urgency events.**
The brain's main loop polls (`poll_events`), but body may signal an interrupt for events over an
urgency threshold. This keeps the common case simple and cheap while not capping urgent callouts
at the tick rate. The urgency threshold is deterministic body-side policy — which is correct: the
system's whole premise is that relevance is code's job, not the model's.

Second-order: this makes body's event queue the single choke point for chatter control, which is
where cooldown/repetition suppression should live too. Good — one place.

Note the urgent class (§2.1) is *not* an interrupt to the brain — it does not reach the brain at
all. Body speaks it directly. An urgent call that waits on model inference has already failed, and
routing it through the brain would put the one class of utterance that must never be delayed
behind the one component whose latency we cannot bound.

### D2. How much state body pushes per turn vs. brain pulls on demand

**Push a full state snapshot each turn.** Strengths: brain always has everything; no multi-step
tool chains; one round trip. Weaknesses: context grows with contact count; small model
degrades badly with a large blob; it's exactly the "model does the synthesis" antipattern; and it
gives the brain material to confabulate from.

**Pull-only, minimal per turn.** Strengths: small focused context, model reliably grounded, cost
scales with what's actually needed. Weaknesses: multi-step tool chains — a small model may fail to
realize it should call `describe_contact` before answering, and answer from the one-line summary;
more round trips, more latency.

**Recommendation: small fixed "situational header" pushed every turn + everything else pulled.**
The header is a handful of lines — mission phase, ownship position summary, count of visible
contacts, highest-priority thing, whether anything is urgent. Cheap, constant-size, and it gives
the small model enough to know *which tool to call next*, which is the actual failure mode we're
guarding against. Everything detailed is pulled.

Risk to watch: the header quietly growing into the full blob. Cap it explicitly (say, 15 lines)
and treat exceeding the cap as a design smell.

### D3. Synchronous vs. asynchronous command execution against the aircraft layer

**Synchronous (body blocks until outcome confirmed).** Strengths: simple call/return; the brain
gets a definite answer; no task lifecycle. Weaknesses: DCS state takes real time to evolve — a
scan might take many seconds — and blocking body means telemetry ingestion, decay, and event
detection all stall; a lost DCS response hangs the layer; directly contradicts
`division-or-responsibility.md`'s requirement to *allow time* for state to evolve.

**Asynchronous with a task lifecycle.** Strengths: matches the inspect-and-adapt requirement
exactly; body keeps processing telemetry while a task is in flight; retries and partial progress
are representable; multiple concurrent intents possible. Weaknesses: more machinery (task IDs,
states, deadlines, cancellation); the brain must understand that a command hasn't finished yet —
a real burden on a small model.

**Recommendation: asynchronous, with the burden hidden from the brain.** Commands return
immediately with a task ID; completion arrives through the *same event stream* the brain already
polls. So the brain never has to poll a task — it just gets "the scan finished, nothing found" as
another event alongside "contact detected". `get_task_status` exists for debugging and for the
rare case where the brain is directly asked, not as the main path. This is the single most
important accommodation in the design for small-model reliability: it removes an entire class of
state the model would otherwise have to track.

### D4. Single body process vs. sharded by concern

**Single process.** Strengths: no internal serialization; contact/attention/event state is one
consistent snapshot; vastly easier to debug and to replay deterministically; matches the actual
scale (one aircraft, tens of contacts). Weaknesses: one crash takes everything; can't distribute
across the Mac/Windows split; a slow world-model query can stall event detection.

**Sharded (e.g. perception/tracking, spatial/semantic, dialogue-facing API as separate services).**
Strengths: fits the microservice framing in `division-or-responsibility.md`; isolates the
world-model query cost; independently restartable. Weaknesses: distributed consistency on state
that is inherently one coherent belief; every seam needs a schema and a failure mode; profoundly
harder to replay deterministically — which is the testing strategy this layer depends on.

**Recommendation: single process, with internal module boundaries clean enough to split later.**
The load argument for sharding does not apply at this scale — this is one aircraft, not a
theatre-wide sim. Take the one real risk (blocking world-model queries) off the table with a
bounded thread pool + result cache rather than a process boundary. Revisit only if profiling shows
a genuine problem, or if the multi-agent future in `PETROBRAIN_SYSTEM.md` (wingmen, JTAC) becomes
real — at which point the natural shard is *per agent*, one body process each, not per concern.

### D5. (secondary) Where semantic descriptions are computed

Body, on demand, cached — not precomputed at observation time. Precomputing bakes in the ownship
position at observation time, and the whole point of storing absolute positions is that relative
geometry is recomputable as the aircraft moves. Cache key on ownship position bucket, invalidate
on movement past a threshold.

---

## 5. Data Model Sketch

```yaml
semantic_claim:              # the unit of every semantic spatial statement body makes
  text: "east side of VILLAGE_12"
  feature_id: VILLAGE_12
  confidence: 0.8            # world-model feature confidence x body's position confidence
  provenance: osm_matched    # dcs_raster | dcs_native | osm_matched | derived
  # Rule: semantic claims are NEVER bare strings anywhere in body, including in anything
  # handed to the brain. §1's seam rule requires world-model provenance to survive the
  # crossing - an "east side of the village" derived from an OSM match is a weaker claim
  # than one derived from DCS raster, and collapsing them to a string destroys that.
  # Templated text (§3.6) may omit provenance from the *spoken words*, but the facts
  # block alongside it must retain it.

observation:                 # append-only, immutable
  id: OBS_812
  contact_id: C17            # assigned by association, may be null when unassociated
  t_sim: 1281.4
  t_wall: 2026-09-07T14:22:11Z
  source: petrovich_detection | inferred | player_report
  classification_raw: "BMP"
  bearing_deg: 32
  range_m: 3100
  ownship_at_observation: {x: ..., z: ..., alt_m: ..., heading_deg: ...}
  derived_world_position: {x: ..., z: ..., confidence: 0.6, method: bearing_range_terrain}
  provenance: aircraft_layer/petrovich_export

contact:                     # derived belief, recomputable from observations
  id: C17
  observation_ids: [OBS_803, OBS_812]
  classification: {value: BMP-2, confidence: 0.8, decay: slow}
  first_seen_sim: 1242.1
  last_seen_sim: 1281.4
  visible: false
  last_known_position: {x: ..., z: ..., confidence: 0.6, decay: fast}
  general_area:
    {place_id: VILLAGE_12, sector: east, confidence: 0.8, decay: medium,
     provenance: osm_matched}
  motion: {direction: north, speed_est_ms: 6, confidence: 0.6, decay: medium}
  semantic_cache:
    computed_at_ownship: {...}
    descriptions:                    # SemanticClaim, never a bare string
      - {text: ..., confidence: ..., provenance: ..., feature_id: ...}
  attention: watch
  attention_source: player | body_policy | mission_plan
  relevance: {score: 0.7, factors: {threat_type: 0.4, proximity_to_route: 0.3}}

attention_area:
  id: AA_2
  world_ref: VILLAGE_12
  sector: north
  level: watch
  source: player
  created_sim: 1290.0

mission_phase:
  current: INGRESS
  since_sim: 1200.0
  previous: DEPARTURE
  transition_evidence: [waypoint_2_passed, ownship_crossed_FLOT_line]
  confidence: 0.9

event:
  id: EV_44
  type: CONTACT_REACQUIRED
  t_sim: 1281.4
  subject: C17
  facts: {...}
  urgency: 0.6
  suggested_phrasing: "Got the BMP again, east side of the village."
  template: null                     # set when body produced final text (contact_report, readback,
                                     #   threat_reaction) - then the brain is not consulted
  bypass_gate: false                 # true = skip cooldown/relevance, pre-empt in-progress speech
  spoken: false
  cooldown_group: contact_status/C17

player_utterance:                    # inbound, from the SRS adapter or the debug console
  id: U_31
  t_sim: 1301.7
  t_wall: 2026-09-07T14:25:03Z
  source: srs_ics | debug_console
  transcript: "keep an eye on that shilka by the road"
  transcript_confidence: 0.82        # 1.0 for typed input
  duration_s: 1.9                    # post-debounce; adapter already dropped clicks and silence
  parse:
    matched_intent: set_attention
    confidence: 0.6
    disposition: handled | escalated | rejected
    reason_escalated: ambiguous_reference
    extracted: {...}                 # see 3.5
  outcome:
    action_taken: null
    readback: null
    escalated_to_brain: true

outgoing_speech:
  id: SP_12
  t_sim: 1302.0
  text: "Enemy, 2 o'clock, 3 kilometres. Group of three tanks, two IFVs and infantry."
  author: body_template | brain
  template: contact_report
  in_reply_to: U_31                  # null for proactive
  priority: normal | interrupt
  delivered: true

pending_intent:              # the inspect-and-adapt loop's unit of work
  task_id: T_9
  kind: scan_area
  requested_by: brain
  reason: "player asked to check the village"
  desired_state: {sensor_pointed_at: {x:..., z:...}, tolerance_deg: 5, dwell_s: 8}
  issued_sim: 1284.0
  deadline_sim: 1314.0
  attempts: 2
  status: in_progress | achieved | failed | cancelled | superseded
```

---

## 6. Milestones (BL-x)

Body-layer-only. Cross-referenced to `PETROBRAIN_RUNTIME.md`'s PB-x, with the reconciliation
noted: PB-x describes the whole runtime; BL-x is the body-owned slice of it. **PB-6/7/8 (LLM,
TTS, STT) have no BL equivalent** — they belong to a future brain-layer plan. PB-0 is largely
aircraft-layer and Mission-Interpreter work, not body's.

- **BL-0 — Harness and replay** *(no PB equivalent; prerequisite the runtime doc doesn't call out)*
  Body process skeleton, aircraft-layer HTTP client, world-model query client, and — most
  importantly — a recorded-stream replay harness so every later milestone is testable without a
  live DCS session. Do this first; it's what makes the rest verifiable.

- **BL-1 — Observation ingestion** *(≈ PB-1)*
  Ownship telemetry ingestion + observation records from whatever perception the aircraft layer
  exposes. If the perception unknown (§7) is still open, ingest a *synthetic* observation stream
  behind the same interface so BL-2/3/4 aren't blocked on it.

- **BL-2 — Contact memory and association** *(= PB-2)*
  Persistent contact identities, detected/lost/reacquired, observation-vs-belief split, decay.
  Exposed through a **debug text command console** (`contacts`, `show C17`, `watch C17`) — this
  console is deliberately the ancestor of the brain API: every command added here should be one
  that later becomes a brain tool. Design it that way from the start rather than retrofitting.

- **BL-2.5 — In-cockpit text mirror (DCS overlay output channel)** *(interim, no PB- equivalent)*
  Inserted between BL-2 and BL-3 by user decision, 2026-09-09. Mirrors belief lifecycle events into
  a DCS Hook-state overlay window so live sortie testing is readable in-cockpit. Not a cognition
  tier — dev/test instrumentation that also lays the transport BL-10's SRS text fallback reuses.
  See `plans/dcs-text-panel-output/plan.md`.

- **BL-2.6 — Classification refinement** *(interim, no PB- equivalent)*
  Inserted between BL-2.5 and BL-3 by user decision, 2026-09-09. Replaces BL-2's last-writer-wins
  classification with a four-level specificity lattice (`unknown` -> `presence` -> `class` -> `type`,
  `belief.classification.SpecificityLevel`) and a fold rule (`fold_classification`) that makes
  identity refine monotonically instead of oscillating: a higher-level, parent-consistent claim
  refines; the same level/value reinforces; a **lower level holds** rather than overwriting (the
  actual oscillation fix); a same-or-higher-level, resolvable, incompatible claim contradicts,
  collapsing to the deepest common ancestor and starting a 30 s re-promotion lockout. Fires
  `CONTACT_CLASSIFICATION_CHANGED` on refinement/contradiction only. Full design:
  `plans/classification-refinement/plan.md`.

  Four decisions were resolved by the user (2026-09-09), all departing from or confirming the
  architect's recommendation:
  1. **Naked-eye reaches `type` at `hires` range, not just `class`** — departs from the architect's
     cap-at-class recommendation; the `hires` tier now emits `reporting_name_for(object_type)`
     directly (ground truth), so "Petrovich can never mis-identify, only fail to identify" now
     applies to the naked-eye channel too, not only the scope channel.
  2. **The naked-eye gating tier moved `medres` -> `lowres`** (its own commit, separate from the
     tier-computation mechanism) — widens the detection envelope ~1.86x (~3.5x area) and makes the
     `presence` level reachable at all.
  3. **`NAKED_EYE_RANGE_CAP_M` stays `5000`** — accepted as-is, deferred to live tuning data.
  4. **Classification level stays sticky; only confidence decays**, via `decay.
     classification_confidence_at` finally consuming `IDENTITY_HALF_LIFE_S` (declared since BL-2,
     unused until now) — a contact identified as a T-72 two minutes ago becomes less sure of it, he
     does not revert to "something."

  **Live-acceptance-found bug and fix.** The first live sortie against this milestone (naked-eye
  only, no scope) surfaced a real duplicate-contact bug unrelated to the fold mechanism itself: a
  single real object was producing 8-20 `Contact` records. Root cause was in `association_over_
  time.py`'s spatial gate, not in `classification.py` — the gate budgeted only the incoming
  percept's own position uncertainty and treated `Contact.last_position` as exact, but naked-eye's
  clock-bucket requantisation re-anchors to current ownship heading every poll, so a stationary
  object's implied position can legitimately jump up to a full bucket-width between polls. Fixed by
  making the gate symmetric (`Contact.last_position_uncertainty_m`, budgeted on both sides). Re-flown
  and confirmed: correct `something -> class -> type` refinement, one contact per real object, no
  duplication. Watch-item carried forward, not a blocker: the wider symmetric gate roughly doubles
  the close-range floor, raising false-merge risk for two distinct real objects at ~300-600 m
  separation — no fixture exercises that band yet.

  **Absorbs an open BL-2 backlog item**: last-writer-wins certainty/classification fusion (see
  Backlog in `todo/todo.md`) is resolved by `Contact.classification`'s fold mechanism
  (`fold_classification`, `plans/classification-refinement/plan.md` §3) — closed as part of this
  milestone rather than tracked separately.

  **Supersedes part of PB-1.5's published calibration.** PB-1.5's worked range table and its
  `medres`-default gating tier (`plans/pb1.5-naked-eye-detection/plan.md`, "Angular-radius
  recognition tier" section) are **historical, not current** as of this milestone — the gate moved
  to `lowres`, and the naked-eye channel's tier -> classification-level mapping (`hires` -> `type`,
  `medres` -> `class`, `lowres` -> `presence`) is new. Current defaults and the current worked range
  table live in `body-layer/src/perception/visibility.py` and this entry. A note pointing here was
  added at PB-1.5's table itself so a future reader does not treat its numbers as current.

- **BL-3 — World enrichment** *(= PB-3)*
  World-position estimation from bearing/range + terrain, world-model semantic queries, current
  relative geometry recomputation, semantic caching.
  Follow-up inherited from BL-2.5: its `belief.console.format_event_for_overlay` can only surface
  BL-2's vocabulary (classification + certainty). BL-3's plan should enrich the mirrored line with
  the new semantic fields rather than leaving the cockpit overlay stuck at BL-2's wording.

- **BL-4 — Attention and events** *(= PB-4, plus the runtime doc's event model section)*
  Attention states, area attention, event detection, cooldown/chatter suppression, the event
  queue. Still console-driven.

- **BL-5 — Deterministic queries and the tool-shaped API (read/attention subset)** *(= PB-5)*
  Stand up the tool API as an actual callable surface (over HTTP or in-process) with the `facts` /
  `summary` / `phrasing_hints` response shape — but **only the tools whose underlying machinery
  BL-0..BL-4 actually built**: `get_contacts`, `describe_contact`, `get_contact_history`,
  `find_contact`, `find_place`, `set_attention`, `watch_area`, `get_attention_state`,
  `get_situation`, `describe_our_position`, `poll_events`, `acknowledge_event`.
  Acceptance test: a human can hold a useful conversation about the tactical situation using only
  these tools by hand, with no LLM involved. If a person can't, a small model certainly can't.

- **BL-5a — Text-mode crew interaction** *(precursor to PB-7/PB-8; the "text debug console
  precedes speech" principle applied literally)*
  The whole SRS pipeline minus the audio: typed input standing in for STT output, printed text
  standing in for TTS. Deliverables: the deterministic intent parser, the routing gate, readback
  and contact-report templates (§3.6), the urgent reactive-call path with its `bypass_gate`
  handling, `handle_player_utterance` (§3.5), and the `PlayerUtterance`/`OutgoingSpeech` records.
  None of this needs audio, and building it here means PB-7/PB-8 later reduce to attaching a
  transport to a pipeline that already works. Acceptance: a typed session reproducing the runtime
  doc's "First useful success criterion" plus a readback, a contact report and an urgent call.
  *Adds to the tool API:* `say`, `ask_player`, and the `handle_player_utterance` body→brain entry
  point (§3.5).

- **BL-6 — Mission phase and relevance** *(≈ PB-9's deterministic half)*
  Mission-phase state machine, mission-relevance scoring, Mission-Understanding ingestion. Gated
  on the Mission Interpreter existing, or on a hand-written Mission Understanding fixture — the
  latter is fine and should not wait. *Adds to the tool API:* `get_mission_phase`.

- **BL-7 — Commands and inspect-and-adapt** *(no direct PB equivalent; from
  `division-or-responsibility.md`)*
  `PendingIntent` lifecycle, aircraft-layer command issuance, outcome verification, retry and
  escalation. Sensors/detection only; flight control stays deferred. Gated on the aircraft layer's
  command channel, which per `plans/aircraft-layer/plan.md` needs its own Security plan review.
  *Adds to the tool API:* `scan_area`, `get_task_status`, `cancel_task`.

  **Tool-set freeze point is the end of BL-7, not BL-5.** §3.3 lists the API's intended final
  shape, but it is delivered incrementally — each milestone adds only the tools whose machinery it
  built. Freezing earlier would mean freezing a contract for behaviour that does not exist yet, and
  the tools most likely to change shape (`scan_area`'s async lifecycle,
  `handle_player_utterance`'s `partial_parse`) are precisely the ones whose milestones come last.
  A brain-layer prototype can begin against the BL-5 subset; it should expect the surface to grow,
  not to be stable, until BL-7 lands.

- **BL-8 — Memory layer interfaces** *(no PB equivalent)*
  Mission-end memory export, campaign/world/player/aircraft memory store interfaces. Deliberately
  last — the shape of what's worth remembering is only knowable after BL-2..BL-7 have run for real.

- **BL-9 — Debug visualization** *(from the runtime doc's "Debugging and inspectability")*
  Belief-vs-DCS-truth debug view. Arguably should be pulled earlier if BL-2/BL-3 turn out hard to
  reason about textually.

- **BL-10 — SRS transport wiring** *(= PB-7 + PB-8, body's half only)*
  Swap the typed/printed stand-ins from BL-5a for the real SRS adapter: consume `PlayerUtterance`
  records over LAN, emit text-to-speak with a priority flag. Body changes here should be small —
  if they are not, BL-5a's interface was drawn in the wrong place. The adapter itself (SRS client,
  ICS channel, PTT debounce, silence gate, STT, TTS) is **not body-layer work** and needs its own
  plan and its own Investigator pass on SRS's client/plugin interface.

---

## 7. Open Questions and Research Needed

**Blocking / needs Investigator:**

- **What Petrovich detection data DCS can actually surface.** Unresolved — flagged in
  `PETROBRAIN_RUNTIME.md` ("the first major technical unknown"), in the aircraft-layer plan's
  risks, and the ED forum thread that would likely answer part of it 403'd during the last
  investigation. Body must not assume the ideal `{classification, bearing, range}` observation
  shape exists. Design BL-1 behind an adapter interface, and if the answer turns out to be
  "only `LoGetWorldObjects` ground truth + external LOS filtering", note that **the LOS/masking
  filter is body-layer work** (per `plans/aircraft-layer/plan.md` decision 3) and becomes a
  substantial BL-1 sub-milestone, not a detail. Do not plan around either outcome until resolved.
- **Whether Petrovich's scan behavior can be influenced at all.** BL-7's entire premise. The
  runtime doc calls this "a separate research question" and it still is. If the answer is no, BL-7
  degrades to "body tracks intent and reports that it can't be actioned" — worth knowing before
  designing the `PendingIntent` machinery in detail.
- **Whether stable contact IDs exist in whatever export we get,** or only rendered descriptions.
  This materially changes how hard data association is: with stable IDs it's bookkeeping; without,
  it's genuine multi-target tracking. §2's "prefer new contact over bad merge" heuristic is written
  for the harder case.

- **How SRS audio is actually captured and injected.** Whether SRS exposes a plugin/client API, an
  audio device, or requires an external SRS client instance acting as a second "radio operator" is
  unverified. Needs an Investigator pass before BL-10 or any SRS-adapter plan. Do not assume.
  Related: whether Petrovich's ICS transmissions can be made audible to the player without also
  being audible to other SRS clients on the same server.

**Undecided, needs user input or later evidence:**

- **Whether the SRS adapter is a sibling component or part of the aircraft layer.** Argued as a
  sibling (SRS is a separate application from DCS; the aircraft layer's contract is DCS I/O). The
  counter-argument is real: both processes must run on the Windows box, both are "external system
  adapters", and two components where one would do is its own cost. Not settled.

- **Where the body process runs** — Windows (next to DCS/aircraft layer, low-latency telemetry) or
  Mac (next to the world model store and Ollama). Per the aircraft-layer plan's topology note it
  can be either. Leaning Mac, because body's *chatty* dependency is the world-model SQLite store
  and its brain-facing API wants to be local to the brain, while its aircraft-layer dependency is
  already designed as a LAN HTTP client. Not decided.
- **Which small model** the brain will use. The §3 API is designed for "small model" generically,
  but tool-calling reliability varies enormously between small models. The API may need to shrink
  (fewer tools) or flatten further once one is picked.
- **Whether `find_contact` reference resolution should be body-deterministic (as proposed) or
  brain-side.** Proposed split is a judgment call, not an established one; it's the piece of §3
  most likely to be wrong.
- **Mission Understanding schema** — treat `PETROBRAIN_SYSTEM.md`'s example as directional only.
  BL-6 should ingest through an adapter, not bind to it.
- **Whether active mission memory needs disk persistence at all** in this phase, beyond debugging
  crash recovery.

**Not open, recorded so it doesn't get relitigated:** world-model queries belong to body, not the
aircraft layer — decided in `plans/aircraft-layer/plan.md` decision 3.

---

## 8. Second-Order Effects

- **Unblocks:** BL-5 defines the brain layer's entire input surface, so a brain-layer plan becomes
  writable (and cheaply prototypable against the tool set by hand) as soon as BL-5 lands. It also
  makes the multi-agent future in `PETROBRAIN_SYSTEM.md` cheap — D4's per-agent-process shard is
  the natural extension.
- **Narrows:** committing to a fixed enumerable tool set means every new brain capability requires
  a body change. Deliberate, but it makes body the pacing item for brain-layer iteration. If brain
  work later feels bottlenecked on body, that's the predicted cost of D1/§3.1, not a surprise.
- **Complicates:** BL-0's replay harness constrains body to be deterministic given an observation
  stream — which forbids wall-clock-dependent or nondeterministic logic anywhere in decay,
  association, or relevance. Cheap to honour now, expensive to retrofit.

---

## 9. Invariant Check

- **DCS authoritative:** satisfied. Facts enter body only via the aircraft layer. The brain has no
  fact-writing tool (§3.3).
- **Code owns facts, models interpret:** satisfied structurally — body owns all belief state, the
  brain receives `facts` + `summary` and produces only wording and tool calls. Templated speech
  (§2.1) strengthens this rather than weakening it: readbacks, contact reports and urgent calls are
  written by code from structured facts, so the model cannot alter them. The brain is also never
  handed a raw transcript (§3.5) — it disambiguates a parse, it does not originate intent from text.
- **Bounded knowledge / no omniscience:** satisfied by the observation→belief pipeline. The one
  live risk is a `LoGetWorldObjects`-based perception fallback leaking ground truth; if that path
  is taken, the LOS/masking filter is the invariant's only defence and must be tested as such.
- **Read-only DCS:** satisfied — body never touches the install; commands go through the aircraft
  layer's own (future, Security-reviewed) channel.
- **Provenance/uncertainty/timestamps:** satisfied — every observation carries source, both
  timestamps, and derivation method; world-model provenance must be carried through, not stripped
  (§1 seams).
- **`world-model/data/` gitignore boundary:** unaffected; body reads the store, never commits it.
  A new `body-layer/` subproject would need its own gitignore for any recorded observation streams
  (BL-0 replay fixtures) — those are potentially large and should be treated like `world-model/data/`.

---

## 10. Decisions Requiring User Input

1. **Does body get its own sibling subproject** (`body-layer/`, mirroring `aircraft-layer/` and
   `world-model/`) with independent tooling config? Assumed yes, consistent with existing pattern.
2. **Which box runs body** (see §7). Affects whether the world-model dependency is in-process or
   HTTP.
3. **Is the fixed-tool-set recommendation (§3.1) accepted**, or do you want an open-ended query
   escape hatch during development?
4. **Is the heavy pre-digestion posture (§3.2) accepted** given the flexibility it costs? This is
   the decision most likely to feel wrong in acceptance testing.
5. **Is the SRS adapter a separate sibling component or part of the aircraft layer** (§7)? Argued
   as a sibling, but not confidently. (The debounce/gate *responsibility* is settled — adapter-side,
   signal-level — regardless of which process hosts it.)
6. **Should BL-0..BL-4 proceed against a synthetic observation stream** while the Petrovich
   perception unknown is open, or should everything wait on that Investigator finding? Recommend
   proceeding synthetically — it de-risks the schedule and the adapter boundary is needed anyway.
