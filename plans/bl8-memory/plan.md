### Goal

Give Petrovich a kneeboard: a small, selective, append-only record of contacts and places that
survives the live belief decaying away, written by the player's command, by the briefing, or by a
narrow high-threat auto-rule — and read back later without ever becoming a back door through which a
stale or never-perceived position re-enters belief as certainty.

Requirements and availability audit: `plans/bl8-memory/requirements.md`. This plan builds on it and
does not restate it.

---

### The one-sentence model

**A note is a record of a belief, not a fact, and it is read with a pen-and-paper's honesty: it does
not update itself, it does not decay, and the reader is the one who knows it is old.**

Everything below is a consequence of that sentence.

---

### Affected Modules / Files

- **`body-layer/src/belief/kneeboard.py` — new.** `Note`, `NoteOrigin`, `Kneeboard`, the admission
  rules, JSONL load/append. The whole storage model lives here; nothing else gains kneeboard state.
- **`body-layer/src/belief/position_belief.py`** — one new method on `PositionEstimate`:
  `range_uncertainty_m(observer)`, the exact down-range mirror of the existing
  `bearing_uncertainty_deg`. Used by the note reader to decide whether a note is precise enough to
  make a claim from (and, separately, by the watch-reporting amendment below).
- **`body-layer/src/belief/contacts.py`** — **no new field, no new behaviour.** `ContactStore` is
  deliberately untouched. Stated as an affected file only because a reviewer will look for the
  change here and must find the reason it is absent (see Decision 1).
- **`body-layer/src/belief/tools.py`** — `get_situation` gains `facts["kneeboard"]` (absent when no
  kneeboard is wired, per the module's existing absent-not-empty convention). No new tool.
- **`body-layer/src/belief/tool_api.py`** — docstring only, recording that BL-8 followed BL-7's
  precedent and did not extend the frozen 15-tool surface.
- **`body-layer/src/belief/console.py`** — `!note`, `!notes`, `!scratch` debug commands (Stage 1's
  only interface).
- **`body-layer/src/belief/crew_console.py`** — four new command handlers; four new members in
  `DISPATCHED_COMMAND_TOKENS`.
- **`body-layer/src/belief/callouts.py`** — read-back rendering for `!notes`/`read_kneeboard`, and
  (Stage 6) the "he's moved — I had him at X" supersede wording.
- **`body-layer/src/belief/mission_phase.py`** — parses two more fields from the compact artifact
  (`key_locations`, `expected_threats`), which it currently reads and discards.
- **`body-layer/src/logger.py`** — owns the `Kneeboard` instance, the same way it owns
  `WorldEnrichmentCache` and `ContactStore`; runs the Stage 6 link step after `store.tick`.
- **`audio-adapter/src/vocabulary.py`** — four new tokens in `VOICE_ONLY_TOKENS` plus phrasings.
  Unbenched (see Decision 5).
- **`body-layer/src/belief/threat.py`** — *consumed, not created here*. Stage 5 depends on
  `plans/watch-reporting/plan.md` Stage 4 having landed it.

---

### Decision 1 — the storage model, and why it is not on `ContactStore`

**A new `Kneeboard` object, a sibling of `ContactStore`, both owned by `logger`. Notes hold copies,
never references.**

```python
NoteOrigin = Literal["briefed", "observed", "commanded"]

@dataclass(frozen=True, slots=True)
class Note:
    id: str                              # "NOTE-0001"
    written_sim: float                   # sim time, never wall clock
    origin: NoteOrigin
    text: str                            # the line as written, crew-readable
    subject: str | None                  # folded classification claim at write time
    cardinality: tuple[int, int] | None   # (lo, hi) at write time
    position: PositionEstimate | None     # a *copy* — plain floats, by construction
    place_name: str | None
    epistemic_status: str                 # "OBSERVATION" | "INFERENCE" | "ASSUMPTION" | "UNKNOWN"
    basis: tuple[str, ...]                # provenance strings, e.g. ("player:commanded",)
    source_contact_id: str | None         # which contact it was written *from*, for the record only
    supersedes: str | None                # a strike/annotation note names the note it acts on
```

Three properties, each load-bearing:

1. **Append-only. A note is never mutated and never deleted.** Correcting a note means appending a
   second note with `supersedes` set. This is the pen: you strike through, you do not erase. It also
   buys replay determinism for free (BL-0's invariant) and makes the on-disk form and the in-memory
   form the same thing.
2. **`position` is a `PositionEstimate` copy.** `plans/precise-position-belief/plan.md` made this
   possible deliberately — plain floats, no live reference into `ContactStore.observations` — and
   this plan is the consumer it was made possible for. Do not reintroduce a log dependency.
3. **Persistence is append-only JSONL**, `kneeboard.jsonl`, exactly the posture
   `speech_log.py`/`detection_trace_writer.py` already use. Loaded once at startup by replaying the
   file. No database, no schema migration surface, and the file is directly readable by a human —
   which matters for a feature whose whole premise is "what did he write down".

**Why not a field on `Contact`:** because a note must outlive the contact (Decision 4), and because
`ContactStore` is the *live belief* and the kneeboard is a *record of belief*. Putting the record
inside the thing it records is precisely how the two would start fusing into each other. The
boundary is structural: `kneeboard.py` imports from `contacts.py`, never the reverse, and
`ContactStore` gains no kneeboard field, so there is no code path by which a note can reach the
association gate or the position fold.

---

### Decision 2 — what gets written down, and who decides

**Code decides. Always. There are exactly three writers and each has a named, narrow admission
rule.** The brain layer never writes directly and gets no tool to do so in BL-8.

| origin | who triggers it | admission rule | bound on volume |
|---|---|---|---|
| `commanded` | the player, by voice or console | **always written** | the player's own words |
| `briefed` | mission load | one note per `key_locations` entry, one per `expected_threats` string | the artifact |
| `observed` | `ContactStore.tick` | **one rule only:** contact's folded `classification.level` is `class` or better **and** its class resolves to an engagement envelope in `belief/threat.py`. Once per contact, ever. | contacts with a real threat envelope |

The pen is a cost, and that cost is what makes the kneeboard mean anything. An auto-rule that wrote
every contact would produce a second `ContactStore` with worse data. So the automatic writer is
deliberately the narrowest useful one — the "high-threat auto-entry" the requirements name — and it
is defined by an existing table (`threat.py`'s envelopes) rather than by a new judgement constant.
A contact that never reaches `class` level never gets written: Petrovich does not write down "a
thing, somewhere".

**Why not the brain:** two reasons, and the second is the real one. (a) BL-6 froze `TOOL_SET` at 15,
and BL-7's precedent for new brain-facing state was *fold it into `get_situation`, do not add a
tool*; this follows that. (b) Letting a model decide what is worth remembering puts an interpretive
layer in charge of what becomes durable fact — the exact inversion of "code owns facts, models
interpret them". The brain reads the kneeboard; it does not hold the pen. If a later milestone wants
brain-proposed notes, the shape is a proposal that writes a `commanded`-origin note with
`basis=("brain:proposed",)` — visible in provenance, never silent.

---

### Decision 3 — a written position against a fused `PositionEstimate` (the important one)

**Rule, in one line: a note is never a measurement. It never folds in, and it is never folded over.**

`fold_position`'s signature is `(estimate, estimate) -> estimate`, and
`plans/precise-position-belief/plan.md` kept it that way specifically so a written-down position
*could* fold in later. **This plan names that door and deliberately leaves it shut**, because
walking through it would be precision laundering: folding a 20-minute-old snapshot into a live
estimate makes the covariance *smaller*, i.e. Petrovich becomes more confident about where something
is by consulting a note he wrote before it moved. That is exactly the failure the position milestone
exists to prevent, arriving through the other end.

So the interaction is one-directional and happens at **read** time, never at fold time:

- **Reading a note inflates it, rather than the note decaying.** A reader computes
  `note.position.covariance.inflated(now_sim - note.position.as_of_sim)` — the existing machinery,
  the existing `GATE_GROWTH_RATE_MPS`, no new decay constant and no new half-life in `decay.py`
  (checked: `IDENTITY_HALF_LIFE_S`, `POSITION_HALF_LIFE_S`, `GENERAL_AREA_HALF_LIFE_S`,
  `MOTION_HALF_LIFE_S`, `OBJECT_ID_MEMORY_S` all already exist there and none of them is the right
  thing to reuse — a note's staleness is a *motion* question, not a *confidence* question). The note
  on disk is immutable; what grows is the reader's honest uncertainty about it.
- **A note may not seed or found a contact.** In particular a `briefed` note must not conjure a
  contact for a SAM nobody has seen. That would be omniscience with provenance attached.
- **When a live contact and a note disagree, the live contact wins for belief and the note is
  annotated, not corrected.** "Disagree" is defined concretely: the contact's fused mean sits at
  Mahalanobis distance > 3 (against the note's *inflated* covariance summed with the contact's) from
  the note's mean. On disagreement, append a note with `supersedes` set to the old note's id. The
  original stays legible — that is what makes the read-back line possible: *"he's moved; I had him
  at the road junction."*

**Who is authoritative for a report** falls straight out: if a live contact exists, report the
contact. If it does not, report the note, and say when it was written. Never blend the two into one
number.

---

### Decision 4 — the note outlives the contact, and what re-acquisition may and may not do

**Yes, by construction.** A note holds no reference to a `Contact`; `source_contact_id` is a
provenance string for the record, not a lookup key that must resolve. A contact decaying to `lost`
and being pruned changes nothing about a note. This is the property the requirements call *durable*,
and it is free once Decision 1's separation is respected.

Re-acquisition is where the discipline is needed:

- **Notes are never inputs to `association_over_time.passes_gate`.** Contact identity stays exactly
  what BL-2 made it: geometric, from perceived attributes, never from a truth field — and a note is
  not perception. Feeding notes into the gate would let a written record decide that two different
  trucks are the same truck, re-opening the confusion BL-2 deliberately preserves.
- **Linking happens after founding, on the read side, and affects only language.** Once
  `ContactStore` has independently founded a contact, a link step (Stage 6, run by `logger` after
  `store.tick`) checks new contacts against notes for subject compatibility plus inflated-position
  overlap, and appends an annotation note recording the link. The contact's `position`,
  `classification` and `cardinality` are untouched. The only visible effect is that the callout can
  say *"that's the SAM we wrote down"* instead of *"new contact"*.

This is the single most important boundary in the milestone. Stated as a test rather than a
convention: **`belief/kneeboard.py` must not be imported by `contacts.py`,
`association_over_time.py`, or `position_belief.py`**, and an import-direction test asserts it.

---

### Decision 5 — the command surface, and the unbenched-token cost

Four new tokens, all **voice-only** — they belong in `VOICE_ONLY_TOKENS`, never in
`LEGACY_F10_TOKENS`, whose tuple must stay byte-identical to aircraft-layer's `ALLOWED_COMMANDS`
(that file's own docstring warns against "fixing" a mismatch by editing it). All four also go into
`crew_console.DISPATCHED_COMMAND_TOKENS`, which is the canonical "this token does something real"
set.

| token | phrasings | needs |
|---|---|---|
| `remember_here` | "remember this spot", "mark this position", "note this spot" | ownship position only — no resolver |
| `read_kneeboard` | "read the kneeboard", "read notes", "what have we got" | nothing |
| `remember_contact` | "remember that", "write that down", "note that one" | a contact resolver |
| `forget_contact` | "forget that", "scratch that" | the same resolver |

**Reuse, do not invent, the contact resolver.** `plans/watch-reporting/plan.md` Stage 3c designs
`_resolve_follow_target` (descriptor set, weights, floor, tie rule) for exactly this question —
"which contact does 'that one' mean". `remember_contact`/`forget_contact` are gated on that landing
and call it; building a second resolver would be the project's third way of answering one question.

**The cost, stated plainly: all four tokens are unbenched.** There is no corpus recording for any of
them, so their recognition accuracy on this user's voice is unmeasured — the same debt the nine
`scan_clock_*` tokens already carry (`vocabulary.py`'s own comment). Cheapest to record when the
corpus is next re-recorded, not free today. `remember_here` is the phrase most likely to survive
(three distinct syllabic shapes, no proper nouns) and `forget_contact`'s "scratch that" the least
distinctive against "cancel task"; if only one round of recording is affordable, measure those two.

**No new tool.** Kneeboard contents reach the brain as `get_situation`'s `facts["kneeboard"]` —
BL-7's precedent, and it keeps the frozen 15-tool surface intact.

---

### Decision 6 — the briefing boundary, enforced structurally

Briefing-sourced memory is knowledge Petrovich legitimately has without perceiving it, so the
question is not *whether* it may enter but *what stops author-only knowledge riding in with it*.
Three mechanisms, none of them a convention:

1. **The compact artifact is the only channel.** `mission_phase.py` already reads MI-6's
   `--emit-compact` JSON as a plain file read, and explicitly never imports mission-interpreter code
   (that subproject is not the `world-model` in-process exception). BL-8 adds two more fields to that
   same parse and opens no second path. Body-layer cannot reach a `.miz`.
2. **The filter runs upstream, in `mission-interpreter/src/filter/`** (`crew_available.py`,
   `threat_signals.py`) — before the artifact is written. Nothing unfiltered exists on the
   body-layer side of the file boundary to leak.
3. **Provenance is carried, not dropped.** Every `key_locations`/`expected_threats` entry is
   `Tagged` (`value` + `epistemic_status` + `basis`), and the `Note` above keeps both fields rather
   than collapsing to a bare value — the same discipline `mission_phase.py` already applies to route
   points. A `briefed` note therefore always reads back as briefed, with its epistemic status
   available, and can never be mistaken for something observed.

**The known upstream gap, unchanged by this plan:** `CompactLocation` has `id`/`kind`/`place_name`
and **no position**, and `expected_threats` is a tuple of bare strings. So a briefed note carries a
`place_name` and `position=None` until the Mission Interpreter grows a position field. That is an MI
milestone, not a BL-8 one; Stage 4 wires what exists and degrades honestly rather than guessing a
position from a name.

---

### Implementation Plan

Each stage ships and flies on its own, as the binocular and precise-position milestones did.

**Stage 1 — the kneeboard exists and the console can write to it.** `belief/kneeboard.py` (`Note`,
`Kneeboard`, append-only JSONL load/append), `PositionEstimate.range_uncertainty_m`, `logger` owns
the instance, `console.py` gets `!note <text>` / `!notes` / `!scratch <id>`. No voice, no auto-entry,
no briefing, no linking. Body-layer only; exercisable entirely from the typed console. **This is the
stage that proves the storage model end to end** — a note written, the process restarted, the note
still there.

**Stage 2 — the player can say it: `remember_here` + `read_kneeboard`.** Two tokens, phrasings, two
`crew_console` handlers, read-back rendering in `callouts.py`. No resolver needed, so this is the
cheapest path to the capability the requirements call the most valuable one. Needs an audio-adapter
redeploy (Mac-side) and one sortie. Flyable alone.

**Stage 3 — `remember_contact` + `forget_contact`. Gated on watch-reporting Stage 3c's
`_resolve_follow_target`.** Do not start without it. The body-layer half is tunable from the
`!voice` harness and the typed console before any redeploy, which is how to get the "that one"
resolution right without burning a sortie on recognition.

**Stage 4 — briefed notes.** `mission_phase.py` parses `key_locations`/`expected_threats`;
`load_mission_understanding` emits `briefed` notes at load with full `Tagged` provenance and
`position=None`. Wiring only, no new capability — and it is the stage that makes the provenance
field earn its place, because it is the first origin that is not perception.

**Stage 5 — the high-threat auto-entry. Gated on watch-reporting Stage 4's `belief/threat.py`.** One
rule, one note per contact ever, defined by the envelope table. Do not start without that table:
defining "high threat" a second time here is how two tables drift.

**Stage 6 — linking and supersede.** The post-`tick` link step in `logger`, the Mahalanobis
disagreement test, the supersede annotation, the "he's moved — I had him at X" wording, and
`get_situation`'s `facts["kneeboard"]`. Last because it is the only stage whose behaviour is a
judgement call rather than a threshold, and it is much easier to tune once real notes from Stages
2–5 exist to tune against.

---

### Risks & Unknowns

- **Four unbenched voice tokens** (Decision 5). Recognition accuracy unmeasured; "scratch that"
  against "cancel task" is the likely confusion and its failure mode is destructive-looking (it
  appends a strike note, so nothing is actually lost — which is itself an argument for the
  append-only model).
- **`briefed` notes are position-less until MI grows a position field.** They will read back as
  place names only. Say so in the sortie card or it reads as a bug.
- **What identifies a mission, for the JSONL file's name?** There is no mission id in the compact
  artifact's consumed fields today, and the body-layer process has no notion of "a sortie". Stage 1
  must pick something — see Decisions Requiring User Input.
- **Sim time is not monotonic across a DCS mission restart.** A kneeboard file replayed into a new
  mission would carry `written_sim` values from a different clock. Stage 1's file-identity choice has
  to make a restart start a new file, or every timestamp is nonsense.
- **Note volume is bounded but not small.** A long sortie with many threat-class contacts could
  accumulate dozens of auto-entries; read-back needs a cap and an ordering rule (recency ×
  threat-class is the obvious one) before Stage 5, not after.
- **The Mahalanobis threshold of 3 (Decision 3) is a declared judgement constant**, uncalibrated,
  in the same class as `BEARING_SIGMA_DEG` and `WAYPOINT_CAPTURE_RADIUS_M`. Isolated in one place.
- **The import-direction rule is the milestone's real invariant** and the one a later refactor is
  most likely to break silently — hence the explicit test in Decision 4 rather than a docstring.
- **`get_situation` is on the brain's hot read path** and Stage 6 adds a list to it. Cap it there
  too, not just in speech.

---

### Second-order effect

This **unblocks BL-8's other, unscoped half** — campaign/world/player/aircraft memory — because the
JSONL note file already *is* the export format that milestone was going to have to invent; a
mission-end export becomes a file copy plus a filter rather than a new serialiser. It also **narrows
BL-9** (the belief-vs-truth debug view now has a second, much simpler store to render, and the
append-only history is exactly what a debug view wants). And it **complicates nothing in
`contacts.py`**, deliberately — the whole design is arranged so the most performance- and
correctness-sensitive module in the body layer gains no field and no branch.

---

### Decisions — Resolved by the User (2026-09-24)

1. **Kneeboard file identity: option (c).** One file per mission-understanding artifact path, plus a
   sim-time-went-backwards reset. Stored in the memory layer as a local file (or DB) — the user's
   words: *"1 per mission data, stored in memory layer, local file (or db)"*. Notes survive a
   mid-sortie restart within the same mission; campaign persistence remains later BL-8 work.
2. **Stage 5's auto-entry waits for `threat.py`.** No temporary rule keyed on
   `_AIR_DEFENCE_OP_CLASSES`. Accepted cost: the one automatic writer is delayed a full milestone,
   and every kneeboard entry until then is player-commanded or briefing-sourced.
3. **The four new voice tokens ship unbenched.** No corpus recording gates BL-8 — user direction:
   *"just add them, let's not worry about recognition now"*. Recognition data comes from the speech
   log instead, which was made **default-on** the same day (`--speech-log` now defaults to
   `logs/speech.jsonl` whenever `--crew-text --speech-input` are active; `--no-speech-log` opts out).
   Every unrecognised utterance is already one row there with `disposition: "say_again"`, a
   `t_wall` stamp and the seven recognition fields, so garbling is measured post-hoc from real
   sorties rather than predicted from a corpus that does not exist. **This inverts the usual order:
   the first sorties after BL-8 are themselves the recognition experiment, so expect misfires in the
   air before there is data to fix them.**

### Superseded — the original open questions


1. **What identifies a kneeboard file — and therefore when a new one starts?** Options: (a) one file
   per body-layer process run, timestamped at startup (simplest, but a mid-sortie restart loses the
   notes, which contradicts "durable"); (b) one file per mission-understanding artifact path (notes
   survive a restart within the same mission, which is the crew-realistic answer, but two sorties of
   the same mission share a kneeboard); (c) a file per artifact path plus a sim-time-went-backwards
   reset. **Recommended: (c)** — it is (b) with the restart hazard closed, and the detection is three
   lines. Says nothing about campaign persistence, which is later BL-8 work.
2. **Should Stage 5's auto-entry ship at all before `threat.py` exists?** The alternative is a
   temporary rule keyed on the existing `_AIR_DEFENCE_OP_CLASSES` set in `crew_console.py`.
   **Recommended: no** — wait for the table. A temporary definition of "high threat" is exactly the
   kind of second source of truth that survives far longer than intended. Flagged because it delays
   the one automatic writer by a full milestone, and the user may judge that too long.
