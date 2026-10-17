# BL-8 — Mission Memory

Branch: `feature/bl8-mission-memory`. Plan written 2026-10-17 against tip `609b64fa`.
**Specification: `plans/bl8-mission-memory/explore-notes.md`** (same directory) — the user's own
words and ten numbered decisions from the 2026-10-17 `/explore` conversation. This plan decides
only what that document left to an Architect; where the two appear to disagree, the explore notes
win and this plan is wrong.

### Goal

Give Petrovich an append-only, per-sortie record of what he saw, marked, attacked and was shot at —
written from settled belief, held in memory for in-flight recall of things belief can no longer
answer for, and persisted as one JSONL file a future debrief tool can parse into the two kneeboard
views.

---

### Decision 0 — one earlier design memory is superseded

`.claude/agent-memory/architect/project_bl8_kneeboard_design.md` (an earlier, pre-explore pass)
proposed `belief/kneeboard.py` and *"No new tool — BL-7's precedent (fold into `get_situation`)
keeps the BL-6 15-tool freeze intact."* The 2026-10-17 explore notes decide otherwise on both
counts (own store beside belief; `TOOL_SET` extension is *"a deliberate, documented act"*). The
memory's two genuinely load-bearing parts survive and are carried into this plan: **the shut fold
door** (Decision 7) and **the import direction** (Decision 1). The memory file is updated rather
than left to mislead the next pass.

---

### Affected Modules / Files

**New — `body-layer/src/mission_memory/` (new package):**

- `entries.py` — the frozen entry dataclasses, the `kind` literal, and JSON encode/decode. No
  imports from `belief`: pure data, so the debrief tool can one day read it without body-layer's
  belief package on the path.
- `store.py` — `MissionMemory`: the in-memory append-only list, the derived indices, the strike
  bookkeeping, and the single `append()` that is the only way an entry is ever created.
- `admission.py` — the worth-remembering rules. Imports `belief` (one direction only), reads a
  settled `ContactStore`, returns entries to append. Holds every new tuning constant.
- `marks.py` — the commanded-mark path (mark index, the two command forms).
- `query.py` — the in-flight read surface the brain-facing tools call.
- `tools.py` — the two new brain-facing tool functions, so no module inside `belief/` other than
  `tool_api.py` gains a dependency on this package.
- `log.py` — the JSONL sink. Same posture as `speech_log.py`: unbuffered, one row per entry,
  disable-once-and-report on `OSError`.

**Changed:**

- `body-layer/src/belief/tool_api.py` — `TOOL_SET` 15 → 17 (Decision 5), plus a docstring block
  recording this as the second deliberate extension of the frozen contract.
- `body-layer/src/belief/tools.py` — `get_contact_history` gains the memory chain for that contact
  id (Decision 5).
- `body-layer/src/belief/crew_console.py` — two new tokens in `DISPATCHED_COMMAND_TOKENS` plus
  `_handle_mark_here` / `_handle_mark_target` (Decision 6).
- `body-layer/src/belief/speech.py` — promote `_cardinality_phrase` to public `cardinality_phrase`
  (rename + keep a private alias; no behaviour change). Reason in Decision 2.
- `body-layer/src/logger.py` — `--mission-memory PATH`, the per-run stamp at `_per_run_log_paths`,
  and one `_mission_memory_step(...)` called from **both** poll loops.
- `body-layer/config/defaults.toml` — regenerated (never hand-edited).
- `body-layer/CLAUDE.md`, `body-layer/docs/STRUCTURE.md` — the new package's map entry and the one
  new invariant.
- `body-layer/ROADMAP/BL-8.md` — status, and a correction: the entry says the "safe from" callout is
  *"switched off in `belief/speech.py`'s `engaged=False` branch"*. It is not. `speech.py` renders it
  fine; the gate is `belief/callouts.py`'s `_OBSERVABILITY_EXEMPT_KINDS`, which exempts only
  `engaged is True`, for a stated reason that is about **priority, not memory** (*"nothing is evaded
  by hearing it… silence costs the pilot the chance to stop evading, which is a comfort, not a
  threat cue"*). See Decision 10 and the open question.

**Read, not changed:** `belief/contacts.py`, `position_belief.py`, `classification.py`,
`cardinality.py`, `motion.py`, `threat.py`, `mission_phase.py`, `enrichment.py`,
`world-model/src/coordinates/__init__.py`.

---

### Decision 1 — its own package, not `belief/`

`body-layer/src/mission_memory/`, a sibling of `belief/` and `perception/`, not a module inside
`belief/`.

The explore notes settle the substance: memory is *"the third queryable store beside belief and the
world model"*, and its whole purpose is the cases belief **cannot** answer. `belief/` is live
belief; this is a record *of* belief, and it outlives the contacts it records. Putting the record
inside the thing it records is how the two start fusing.

**The invariant that actually matters is the import direction**, and it is now structural rather
than conventional:

> `mission_memory` may import `belief`. **No module in `belief/` may import `mission_memory`, with
> exactly one carved exception: `belief/tool_api.py`.**

`tool_api.py` is a leaf — the composition root of the brain-facing surface. Nothing in belief's own
reasoning path imports it, so a second dependency there cannot create a cycle and cannot let a
written-down note re-enter belief. Keeping `TOOL_SET` where it is matters more than purity:
`belief.tool_api.TOOL_SET` is the published brain↔body contract, and moving it would be a larger
break than extending it.

Enforced by a test that greps `src/belief/*.py` for `mission_memory` and asserts the one allowed
importer — the same mechanical posture `/invariant-check` already uses. Notes never enter
`passes_gate`; contact identity stays geometric-from-percepts (BL-2).

---

### Decision 2 — the entry schema

One envelope, a per-kind payload. Every entry is a frozen dataclass; nothing is ever mutated.

```
Entry
  schema: int                 # 1. The file must be parseable later without guessing.
  seq: int                    # 1-based, monotonic, per sortie. Never reused. The strike key.
  kind: "group" | "air_defence" | "attack_run" | "mark" | "fired_on"
  provenance: "observed" | "commanded"   # "briefed" reserved, see Risks
  t_sim: float                # sim clock at write
  t_wall: float               # wall clock, so the file orders under a paused mission
  phase: {name, waypoint_index} | null   # MissionPhaseInfo, or null before a route is loaded
  pos: EntryPosition | null
  seen: SeenHow | null
  belief_ref: str | null      # the Contact id, e.g. "CONTACT_17"
  strikes: int | null         # the seq this entry supersedes
  iff: null                   # RESERVED. Always null in BL-8. Present so the schema never changes.
  payload: <per kind, below>

EntryPosition
  x: float; z: float          # believed, from PositionEstimate
  y: float | null             # Contact.last_alt_m — see the provenance note below
  uncertainty_m: float        # from PositionEstimate.covariance, at write time
  as_of_sim: float            # PositionEstimate.as_of_sim — NOT t_sim; a note may record an old look
  lat: float | null; lon: float | null    # dcs_to_wgs84(theatre, x, z); null if unprojectable
  landmark: str | null        # frozen phrase, X-B20-gated — see Decision 9

SeenHow
  optic: str; range_m: float | null; confidence: float; certainty: Certainty
```

Per-kind payloads:

| kind | payload |
|---|---|
| `group` | `composition: [{op_class, lo, hi, confidence, count_word}]`, `motion: {state, dir}`, `ad_link: int \| null` |
| `air_defence` | `composition` (same shape), `group_link: int \| null`, `threat: {envelope_m, source} \| null` |
| `attack_run` | `target_seq: int \| null`, `target_ref: str \| null`, `weapon: str \| null`, `outcome: "destroyed" \| "survived" \| "unknown"` |
| `mark` | `index: int` (its own counter), `label: str \| null`, `anchor: "ownship" \| "target"` |
| `fired_on` | `shooter_seq: int \| null`, `shooter_ref: str \| null`, `targets_ownship: bool` |

Five points where this schema is making a decision rather than transcribing one:

1. **`motion.dir` and `attack_run.outcome` ship nullable**, per the user's own scope decision. Both
   are legal nulls forever until the direction and destruction work exists; the >45°-strike rule
   (explore Decision 9) is written *there*, not here. Nothing in this schema has to change to accept
   them.
2. **`y` does not have the same provenance as `x`/`z`, and the schema must not pretend it does.**
   `PositionEstimate` carries only `x`, `z`, `covariance`, `as_of_sim`; altitude lives on
   `Contact.last_alt_m`, which is a **last-observed** value, not a fused estimate. So `y` is a
   weaker fact than `x`/`z` in the same object, and `uncertainty_m` says nothing about it. Written
   down because a debrief renderer plotting all three as equals would be quietly overclaiming.
3. **`as_of_sim` is separate from `t_sim`** for the same reason: an entry written now may record a
   look taken thirty seconds ago. Collapsing them would make every note look fresher than it is.
4. **Composition carries both the structured belief and the frozen word.** `{op_class, lo, hi,
   confidence}` is what code reasons over; `count_word` is `cardinality_phrase`'s output frozen at
   write time, so debrief needs no belief code to render a page. It is the *existing* ladder
   (`couple`/`handful`/`several`/`many`), reached by promoting `speech._cardinality_phrase` to
   public rather than copying it — a count vocabulary existing in two places is a thing that
   diverges silently, and this is the one duplication this plan goes out of its way to prevent.
   Note the honest limit: `belief/classification.py` has **no** `"armor"`/`"truck"` super-classes
   today, only `"air defense"` via `CLASS_GROUP_OF`. So "class level" means the `OP_*` class string,
   and the richer vocabulary arrives when the attention-tier milestone decides it.
5. **`strikes` points forward, never back.** See Decision 4.

---

### Decision 3 — who decides an entry is worth writing, and when

**Worth-remembering and worth-saying are different judgements, and memory is not a side effect of
speech.** This is the plan's load-bearing claim, so here is the argument rather than the assertion:

- Worth-**saying** is bounded by a single voice channel and the pilot's attention. `callouts.py`
  suppresses, defers, prioritises and retires calls; plenty of what Petrovich firmly believes is
  deliberately never said — too minor, already said, cooldown, something more urgent won. None of
  that is a statement about whether he *knows* it.
- Worth-**remembering** is bounded by consequence: write when belief reaches a state a later
  question could depend on.
- The asymmetry runs both ways. Speech also contains things that are not entries at all —
  readbacks, acknowledgements, "say again".
- And the failure mode if they were fused is concrete: memory would become a transcript of what was
  said, which is **already** `speech_log.jsonl`, and the generalised "safe from" consumer could not
  answer about a group Petrovich never got round to mentioning. That is exactly the case BL-8
  exists for.

So the writer is driven by **belief-state transitions, not by percepts and not by callouts**.
Placement in the loop: inside one `_mission_memory_step(...)` called from both
`_run_crew_text_poll_loop` and `_run_console_poll_loop`, **after `runner.run_once()`** (so belief is
settled and `tick()` has materialised its events) and **before `crew_console.drain_events(...)`**
(so a `seq`/mark index exists if a callout ever wants to name it). It reads the post-tick store and
writes; it never re-derives perception.

The five admission rules, each named, each with a threshold:

| rule | writes when |
|---|---|
| `group` | a contact's `classification.level` first reaches `CLASS` with `confidence >= GROUP_ENTRY_CONFIDENCE_FLOOR`; thereafter only on a **material** change (below) |
| `air_defence` | a contact's class is in `AIR_DEFENSE_OP_CLASSES` — always its own entry at first identification, regardless of the `group` rule, and linked both ways (`ad_link`/`group_link`). A group that is *all* air defence is the air-defence entry, with no separate group entry. |
| `attack_run` | the attack-run machinery completes a run (see the effort/value flag) |
| `mark` | synchronously, on the pilot command — not on a tick |
| `fired_on` | a `CONTACT_FIRING_SEEN` event, suppressed per shooter for `FIRED_ON_FOLD_WINDOW_S` |

**"Material change" is the whole mechanism that keeps the log readable**, so it is explicit:
believed position moved ≥ `RESIGHT_MOVE_M`, **or** composition changed class or cardinality bucket,
**or** motion state changed — **and in every case** at least `RESIGHT_MIN_INTERVAL_S` has passed
since that contact's last entry. Entry-worthiness is a change threshold on belief, never an event
in perception. Writing on every percept would make the file useless, which is the thing this
decision exists to prevent.

---

### Decision 4 — striking, and same-subject identity

**The store never decides anything.** A strike is proposed by the same admission rule that writes
the replacement, which names the entry it supersedes: `strikes: <seq>`. `append()` records it.

**The file is never mutated**, so the strike cannot be written *into* the struck entry. The
"struck flag naming what struck it" that the explore notes ask for is therefore a **derived read
value**: the store keeps `struck_by: dict[int, int]` in memory, and a debrief tool rebuilds it by
replaying `strikes` forward. This is the single place the append-only rule could be broken by
accident, so it is named here rather than left to a reviewer.

**Same-subject identity is `belief_ref` — the Contact id — and nothing else.** Memory holds no
second associator; the judgement is `association_over_time`'s, which is Petrovich's own and
fallible, exactly as the explore notes record. Three consequences, all **expected behaviour, not
defects** — written down so a reviewer does not file them as bugs:

- Belief splits one real group into two contacts → two unstruck entries for one group. Honest: he
  believes there are two.
- Belief wrongly merges two groups → the strike chain merges with them. Honest for the same reason.
- A contact that lapsed and was **re-founded under a new id** does **not** strike the old entry.
  Correct: Petrovich does not know they are the same thing. This is the no-omniscience invariant
  working, and it is also why the strike chain is a *believed* history rather than a true one.

A `mark` is never struck by observation. Only the pilot could strike a mark, and no "forget mark 3"
command is in BL-8 — the chain simply grows.

---

### Decision 5 — the in-flight query surface: `TOOL_SET` 15 → 17

Both halves, because they answer different questions:

- **Fold into `get_contact_history`.** For a contact that still exists, "what do we know about its
  history" is one question with one key, and splitting it across two tools would be duplication.
  Its result gains the memory chain for that `contact_id` (entries, oldest first, strike state
  included), merged into the existing oldest-first ordering.
- **Two new tools**, because a contact-keyed tool cannot reach the cases BL-8 exists for — a mark,
  or a group belief has forgotten entirely, has no live contact id to key on:
  - `recall_memory` — the notepad read: entries newest-first, filtered by kind, by radius around a
    position, and by current-only versus include-struck.
  - `remember_location` — the commanded mark, so the brain has the same path the pilot's voice
    command has.

**This is a deliberate extension of a frozen contract, and `tool_api.py`'s docstring must say so**,
alongside why it differs from the precedent it appears to contradict: BL-7 *declined* to add
`get_mission_phase` because mission phase was *"a strict id-less subset of what `get_situation`
already returns"*. Mission memory is the opposite — a store that answers questions belief cannot
answer at all. Reuse where it is a subset, extend where it is a new store.

---

### Decision 6 — the mark command has no new F10 item

Marks reach `CrewConsole.handle_command` as two new tokens in `DISPATCHED_COMMAND_TOKENS`:
`mark_here` (ownship's current position) and `mark_target` (the currently selected target's believed
position, reusing `select_target`). Reachable by **voice and by the brain tool only — no new F10
radio-menu entry.** BL-10 carries an explicit instruction not to re-expand the F10 tree, and this
plan does not get to quietly overrule it.

**Scope narrowing, surfaced rather than assumed:** the explore notes' richer mark forms — mark a
named landmark, mark a grid coordinate — need open-vocabulary speech and are BL-10/SRS territory.
BL-8 ships the two fixed forms, which are reachable with today's fixed-vocabulary voice chain, and
the `mark` payload's `anchor` field already has room for the others.

---

### Decision 7 — the fold door stays shut

`fold_position(estimate, estimate) -> estimate` could technically fold a written-down position back
into live belief. **It must not.** Folding an old snapshot *shrinks* the covariance: Petrovich
becomes more confident by consulting a note written before the thing moved. Precision laundering.
This is named so a later plan proposing it meets the counter-argument already written down.

Relatedly: **staleness is a property of reading a note, not of the note.** Readers inflate —
`covariance.inflated(now - as_of_sim)` — and no new half-life goes into `decay.py`. A note's
staleness is a motion question, not a confidence question, and none of the five existing half-lives
is the right reuse (checked).

---

### Decision 8 — no ground truth, ever

`detection_trace_writer.py` is body-layer's **single sanctioned** ground-truth exception
(`body-layer/docs/STRUCTURE.md`: *"Do not add a second exception"*). Mission memory is not a second
one. Every position in an entry comes from `PositionEstimate`/`last_alt_m`; `lat`/`lon` are
`dcs_to_wgs84(theatre, x, z)` applied to the **believed** x/z, never to a DCS object's true
position. `dcs_to_wgs84` raises `ValueError` on an unregistered theatre — caught, `lat`/`lon` null.
A memory write never kills the poll loop.

---

### Decision 9 — the landmark phrase is gated, and BL-8 is the gate's other half

`X-B20` (`todo/backlog/X-B20.md`) requires a landmark reference to pass two gates before being
spoken — LOS on the landmark itself, and *knowledge* of it — and names BL-8 as the knowledge half.
So BL-8 must not make it worse. `pos.landmark` is populated **only** from a phrase that already
passed whatever gate exists at write time (today: `enrichment.semantic_facts_for`'s near-fact
radius for a landmark Petrovich has an observational basis for); otherwise `null`. A null landmark
is the correct, common case, not a defect. The reverse direction is the second-order effect below.

---

### Decision 10 — "safe from" gets what it needs here; flipping the switch is its own change

The user's direction is on record and is not being questioned — `plans/dcs-driven-los/plan.md`:
*"for 'safe from' when unit is not within visibility cone, mission memory of where those are
believed to be would have to be used. Defer safe-from"*, and **"Un-defers when mission memory
lands."** So the intent is clear: BL-8 is what un-defers it.

**What changes is the cost, because the code pointer everything was written against is wrong.** Both
`BL-8.md` and `dcs-driven-los`'s decision locate the deferral in `belief/speech.py`'s
`engaged=False` branch. It is not there — `speech.py` renders *"Safe from …"* perfectly well. The
actual gate is `belief/callouts.py`'s `_OBSERVABILITY_EXEMPT_KINDS`, which exempts only the
`engaged is True` danger call, **for an independent reason that is about priority rather than
memory**: *"nothing is evaded by hearing it… silence costs the pilot the chance to stop evading,
which is a comfort, not a threat cue."*

Two consequences:

1. Un-deferring is **a second, separate change** in a different module, not a line uncommented once
   memory exists — and it has to decide what to do with that observability rationale, which memory
   does not answer.
2. It is an **absence-claim callout**, the more dangerous of the two to get wrong by the user's own
   framing, so it wants its own acceptance sortie rather than riding on Sortie A.

This plan therefore **supplies what it needs** (a believed position for a contact outside live
coverage, via `recall_memory`) and stages the switch separately as Stage 6. See the open question —
it is a sequencing call, not a reopening of the user's direction.

---

### Co-moving Fields

Step 6a's trigger fires: `seq`, the mark `index`, and two derived indices must all move together on
an append, and the mark index is driven **externally** (a pilot command) while `seq` is driven
internally by the admission rules. The store type does not exist yet, so the obligation transfers to
the Implementer: **grep every construction site before finalising this table, and make `append()`
the only one.** Fresh construction bypassing `replace()`/the single writer is this project's
recurring root cause (`BL-B71`'s fourth transition was found exactly that way, by grepping
`OpticState(` rather than by enumerating transitions).

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `_next_seq` | internal (`append`) | any append | incremented by exactly 1; no entry anywhere holds this value yet |
| `_next_mark_index` | external (pilot `mark_here`/`mark_target`, brain `remember_location`) | a `mark` append **only** | incremented on `mark` appends and on nothing else; never reused, never renumbered, even if the entry it numbered was struck |
| `_struck_by: dict[seq, seq]` | internal (`append`) | an append carrying `strikes=s` | `s` is an existing seq, `s` is not already struck (a second strike of one entry is a bug, not a chain), and the new entry is itself unstruck |
| `_latest_live: dict[contact_id, seq]` | internal (`append`) | any append with `belief_ref` | points at the newest **unstruck** entry for that contact, so the admission rules' material-change check is O(1) and never scans the log |
| the JSONL sink | internal (`append`) | any append | exactly one line written per appended entry, or the sink is disabled and has said so once; **never** a rewrite of an earlier line |

All of it moves under one lock: appends come from the poll thread, reads from the REPL/brain thread,
and two fields updating between a reader's two reads is the failure this prevents.

---

### Implementation Plan

**Stages 1–4 are one batch** — none needs a flight to proceed, and all four are inspectable
post-sortie from the file. **One performance pass and one security pass after Stage 4**, then DoD.
Stage 5 joins that batch if the user settles the `TOOL_SET` question before implementation starts;
otherwise it is its own batch with its own two passes. Stage 6 is deferred pending the open question
and would be its own batch.

1. **Schema + store + sink, pure, unwired.** `entries.py`, `store.py`, `log.py`. Tests: JSON
   round-trip for every kind including all-nullable fields; the strike chain (append → strike →
   derived `struck_by`, and a replay rebuilding it from the file alone); the Co-moving Fields table
   asserted field by field; a single-construction-site test; sink write-failure disables once and
   reports. Independently mergeable: nothing imports it yet.
2. **Observed entries + wiring.** `admission.py` (the `group` and `air_defence` rules), the tuning
   constants, `--mission-memory PATH`, the per-run stamp at `_per_run_log_paths`, and
   `_mission_memory_step(...)` called from both poll loops. Tests against a fake `ContactStore`:
   a contact crossing the confidence floor writes once and not again; jitter below `RESIGHT_MOVE_M`
   writes nothing; an air-defence class always writes its own entry and links both ways; a
   nullable-everything contact still produces a valid entry. Plus the `belief/`-must-not-import test
   from Decision 1.
3. **Commanded marks and `fired_on`.** The two tokens, `marks.py`, the suppression window. Tests:
   two shots from one shooter inside the window produce one entry and outside it produce two; the
   mark index never reuses a number across a struck entry; `mark_target` with nothing selected fails
   the way every other target-less command already fails.
4. **Attack-run entries** — schema and trigger only; `weapon` and `outcome` null. **Read the
   effort/value flag below before building this stage.**
5. **The query surface.** `query.py`, `tools.py`, the `get_contact_history` fold, `TOOL_SET` 15 → 17
   and its docstring. Tests: recall reaches a mark and a struck-chain for a contact belief has
   dropped; `recall_memory` filters behave; `get_contact_history` for a live contact returns belief
   history and memory chain in one ordering.
6. **(Deferred, pending the open question)** "safe from" re-enablement. Not in the batch.

**Acceptance sorties, separated out:**

- **Sortie A, after Stage 4.** Fly a mission with ground units, air defence, a mark, and something
  shooting. The feature is write-only in flight, so acceptance is **reading the file afterwards**:
  does the notepad read like a kneeboard page, is the entry count in the tens rather than the
  thousands, is any group's strike chain a sensible history, and is anything obviously missing or
  obviously noise? The thresholds in Stage 2 are guesses until this sortie; expect to re-tune and
  re-fly.
- **Sortie B, after Stage 5.** In-flight recall, driven through the console REPL or the brain:
  ask about a mark set twenty minutes earlier and a group now outside the bubble.

---

### Effort/Value flag — Stage 4 (attack runs) buys almost nothing today

Worth saying before it is built rather than after. An attack-run entry wants **time, target, weapon,
outcome**. Of those:

- **time** — available, from the attack-run machinery.
- **target** — available, from the selected target.
- **weapon** — **no source.** There is no weapon-release signal anywhere in body-layer; the
  `engage [<what> <where>] [weapon]` command's weapon slot exists in the grammar but
  `_parse_target_slots` has no weapon field and silently drops it.
- **outcome** — **no source.** Nothing in belief determines destruction, by the user's own scope
  decision.

So Stage 4 as written produces a record of *"at T, aimed at CONTACT_9, weapon unknown, outcome
unknown"* — two of four fields null and the plumbing to carry them. My recommendation: **build the
schema (Stage 1 already does) and defer the trigger**, because the cheaper prerequisites are both
small and both live elsewhere:

- **weapon**: the cockpit weapon selector (arg 523: OFF/GM/URS/NPU) is already read by
  `aircraft-layer/dcs-export/Export.probe-detection.lua`. Exporting it is a small aircraft-layer
  change, and it would also let the `engage` command's existing weapon slot be parsed.
- **outcome**: `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`
  already establishes the route — `Unit:getLife()`/`getLife0()` over the mission-scripting bridge,
  callable from Hook state, with a `petrobrain-damage-events-probe-hook.lua` already in the tree.
  Researched, not built.

With either in hand, attack-run entries become genuinely useful for a debrief. Without both they are
a shape. **Your call** — if you want Stage 4 now, it is cheap and the schema is right; I am only
saying the value arrives later than the effort does.

---

### Tuning Constants (X-T26 pattern — `body-layer/src/tuning.py`)

All four are behaviour-affecting: they change what Petrovich remembers.

| key | default | `lo`/`hi` | status |
|---|---|---|---|
| `mission_memory.admission.FIRED_ON_FOLD_WINDOW_S` | `120.0` | `10.0` / `900.0` | judgement |
| `mission_memory.admission.RESIGHT_MOVE_M` | `250.0` | `50.0` / `2000.0` | agreed-guess |
| `mission_memory.admission.RESIGHT_MIN_INTERVAL_S` | `60.0` | `5.0` / `600.0` | agreed-guess |
| `mission_memory.admission.GROUP_ENTRY_CONFIDENCE_FLOOR` | see note | — | — |

- `FIRED_ON_FOLD_WINDOW_S` is the user's *"~2 min"*, stated as a tunable in explore Decision 5.
- **`GROUP_ENTRY_CONFIDENCE_FLOOR`: reuse before declaring.** If a nameability threshold already
  exists for the describe/callout path, use it and declare **no new constant** — a second,
  independently tunable "is this nameable yet" number is how two surfaces start disagreeing about
  what Petrovich knows. Only if none exists does this become a `tuning.fraction` key. The Implementer
  decides by reading, not by assuming (this project's dominant failure mode, and `IDENTITY_HALF_LIFE_S`
  sitting unread in the file a plan was editing is the worked example).
- **`#:` comments: the first sentence is all that renders.** `tools/generate_defaults.py`'s
  `_first_sentence` emits exactly that into `config/defaults.toml`; anything written second reaches
  nobody. **`RESIGHT_MOVE_M`'s warning must therefore be in sentence one**, because it is the one
  that bites: position belief is now a continuously fused estimate carrying per-look noise (it used
  to step in ~500 m buckets), so a threshold set too low makes the log churn on jitter rather than on
  movement. This is the same hazard `plans/watch-reporting/plan.md` Decision 5a was amended for.
  Check the **rendered** TOML, not the comment it came from.
- Regenerate with `tools/generate_defaults.py --write`; never hand-edit.

---

### Risks & Unknowns

- **The three thresholds are uncalibrated.** Stage 2's behaviour is a guess until Sortie A. Plan on
  re-tuning and re-flying; that is the milestone's main schedule risk, not the code.
- **Store growth and query cost.** At `RESIGHT_MIN_INTERVAL_S=60` with ~30 tracked contacts the
  worst case is ~30 entries/minute, ~3600 in a two-hour sortie. Fine in memory — but the **poll
  thread must never scan the log**, which is exactly what `_latest_live` is for. `recall_memory`'s
  radius filter is a linear scan, and it runs on demand from the brain, never per tick. If that ever
  moves onto the poll thread, this estimate stops holding.
- **`pyproj` on the poll thread.** `dcs_to_wgs84` is a projection call per entry — negligible at
  entries-per-minute rates, and it would not be at per-poll rates. A reason the admission thresholds
  are not merely cosmetic.
- **The `"briefed"` provenance is reserved, not built.** Mission-interpreter's compact artifact is
  the only channel, and `CompactLocation` still has no position field, so a briefed entry would carry
  `place_name` with `position=None`. Out of scope; the enum value exists so the schema does not
  change later.
- **`motion.dir` and `attack_run.outcome` remain unresolved dependencies, not silent assumptions.**
  They stay null by decision. The >45°-strike rule is the direction work's, not this milestone's.
- **The two poll loops already duplicate their writer block.** Adding a third copy of the wiring is
  the drift risk; one `_mission_memory_step(...)` called twice is the mitigation, and the reason this
  plan names it rather than leaving placement to the Implementer.
- **A debrief format is being committed to without a debrief design.** The mitigation is `schema: 1`
  and the reserved fields; the residual risk is that debrief wants something this schema makes
  awkward. Accepted deliberately — the explore notes scope debrief out, and the obligation here is
  only that the file be parseable into those views later.

---

### Second-Order Effect

**BL-8 unblocks `X-B20`'s knowledge gate, which currently has no implementable second half.** X-B20
requires a landmark reference to be both LOS-gated *and* knowledge-gated, and names BL-8 as the only
candidate source of *"a standing memory of that landmark."* Once this store exists, a landmark
Petrovich has previously written down is checkable, so the gate becomes buildable rather than
aspirational — and Decision 9's write-time freeze is what makes the stored phrase trustworthy enough
to re-use. It also narrows the destruction-determination and motion-direction work: both now have a
schema slot waiting with a defined null, so neither gets to invent its own record format.

---

### Decisions Requiring User Input

1. **Stage 4 (attack runs) — build now with two null fields, or defer until the weapon selector
   and/or `getLife()` route exist?** See the effort/value flag. My recommendation: defer the
   trigger, keep the schema.
2. **"safe from" — in this milestone's batch, or its own?** Your direction already says it un-defers
   when mission memory lands, so this is sequencing, not scope: the gate turns out to live in
   `callouts.py` with its own priority-based rationale (Decision 10), so it is a second change in a
   second module plus an absence-claim callout flown for the first time. My recommendation: Stage 6,
   after Sortie A has shown the memory itself is trustworthy, with its own sortie.
3. **`TOOL_SET` 15 → 17** (Decision 5) — extending a contract that is frozen by design. The
   reasoning is in the explore notes and the fold-versus-extend split is argued above, but the
   freeze was deliberate and this is your call, and settling it before Stage 1 is what lets Stage 5
   join the single batch.
