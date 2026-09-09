# PB-2 / BL-2 — Contact memory and data association over time

> Branch: `feature/pb2-contact-memory` (from local `main`).
> Milestone source: `plans/body-layer/plan.md` §6 BL-2; `docs/concept/PETROBRAIN_RUNTIME.md` PB-2.

### Goal

Turn the two independent `PerceptionSource` observation streams into persistent, decaying contact
beliefs with a detected/lost/reacquired lifecycle, exposed through a debug text console whose
commands are the literal ancestors of §3.3's `get_contacts` / `describe_contact` /
`get_contact_history` / `find_contact` brain tools.

---

### Investigator check (architect step 2)

**No investigator pass was invoked. Every DCS-internals fact this plan rests on is already
recorded**, and each is cited at the point of use below:

| Claim the plan depends on | Where it is already settled |
| --- | --- |
| HelperAI's five `*_list_text` leaves are a **window into a multi-row target list**, holding several simultaneous distinct contacts | `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Finding 6 |
| `upper_list_text` does not exist; `upper_upper_list_text` is present but empty in every sample | ibid. Finding 5 |
| The list is populated only ~2% of flight time and is sight-gated | ibid. Finding 7; `2026-09-09-pb15-ambient-callout-live-probe.md` |
| The DCS ambient callout has no Lua-readable companion — there is no third channel coming | `aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md` Finding 1 |
| `LoGetWorldObjects` is unfiltered global ground truth including ownship | `aircraft-layer/src/schema/world_objects.py`; `plans/pb1.5-naked-eye-detection/debug.md` |
| `object_id` appears stable within a session | `todo/todo.md` Backlog, closed 2026-09-09 by PB-1.5's acceptance sortie |
| ED's own detection constants / callout vocabulary | `aircraft-layer/research/2026-09-08-pb1-5-...md` Findings 2–3 |

One aircraft-layer fact confirmed by reading rather than assumed: `schema/petrovich_indication.py`'s
`parse_indication_text` **already flattens the whole indication tree into `fields`**, so all
populated leaves are on the wire today. The multi-row fix below is body-layer-only — no
aircraft-layer change, no wire-format change.

---

### Interface confirmation (task constraint 2)

**Confirmed: `PerceptionSource` needs no protocol change.** `poll(now_sim, ownship_state) ->
list[Observation]` is already channel-agnostic and already returns a list, so BL-2 consumes both
channels through one interface, as required. Three concrete gaps sit in the *records and emission
policy*, not the protocol, and are addressed in stages 0/1/3:

1. **`Observation.id` collides across sources.** Both `HybridPerceptionSource` and
   `NakedEyePerceptionSource` mint `f"OBS_{self._observation_count}"` from their own per-instance
   counter, so an append-only observation log keyed by id would silently overwrite. Fixed by a
   per-source id prefix (stage 1).
2. **Source-level debounce starves the belief layer.** Both channels emit only *on change*
   (`middle_list_text` text-equality; naked-eye object-id set membership). A statically visible
   tank produces exactly one observation and then nothing — under decay, contact memory would age
   it to "lost" while Petrovich is staring straight at it. The debounce was a PB-1 device to keep
   the *text logger* readable; de-duplication belongs at the belief layer, which is what a tracker
   does. Fixed by an `emit_mode` flag (stage 3).
3. **`Observation` carries DCS ground truth alongside perceived values.** `derived_world_position`
   holds the candidate's exact x/z on *both* channels. Belief code must never read it. Enforced by
   a `Percept` projection rather than a comment (stage 1).

---

### Decision: how much this design leans on `object_id` (task constraint)

**Contact identity never consults `object_id`, `derived_world_position`, or any other truth field.**
Identity is derived from perceived attributes only: perceived position (projected from
bearing/range/ownship-at-observation), class compatibility, and elapsed time. This is not
conservatism about the 2026-09-09 evidence — it is the anti-omniscience invariant. A contact
identity is a *belief about* an object; a passthrough of the DCS key would make Petrovich
incapable of ever confusing two identical trucks, which is precisely the omniscience CLAUDE.md
forbids.

**What degrades if id stability turns out false:** the dependency is confined to the two *sources'*
acquisition-set bookkeeping. Under `emit_mode="every_poll"` an unstable id causes every object to
re-enter the "newly acquired" set each poll, so `NAKED_EYE_MAX_NEW_PER_POLL` throttles emission and
the observation rate becomes noisy/capped. **Belief is unaffected** — BL-2 associates on geometry
and would still build the same contacts, just from a lumpier stream. The failure mode is a degraded
observation rate, never corrupted belief. That is the whole reason for the split.

---

### Affected Modules / Files

**New — `body-layer/src/belief/` package** (observation *consumption*; `perception/` stays
observation *production*. This is §1's observation-vs-belief split drawn as a package boundary):

- `belief/percept.py` — `Percept` (t_sim, source, classification_raw, bearing_deg, range_m,
  ownship_at_observation, observation_id) + `percept_of(Observation) -> Percept`. The mechanical
  enforcement of "belief may only see what was perceived": truth fields are structurally absent, so
  no downstream function can read them by accident. Tested by asserting the type has no truth field.
- `belief/contacts.py` — `Contact`, `SightingSpan`, `ContactStore`. Append-only observation log,
  derived contact records, per-contact sighting spans, `ingest(observations, now_sim)`,
  `tick(now_sim)`.
- `belief/association_over_time.py` — percept→contact gating and the "prefer new contact over bad
  merge" decision. Distinct from `perception/association.py` (detection→world-object, within one
  poll); the name keeps the two from being confused.
- `belief/decay.py` — per-attribute half-life decay + the §3.4 `certainty` enum table. Pure
  functions of `(contact, now_sim)`; no ticker.
- `belief/events.py` — `Event` record and `CONTACT_DETECTED` / `CONTACT_LOST` /
  `CONTACT_REACQUIRED` derivation.
- `belief/tools.py` — `get_contacts`, `describe_contact`, `get_contact_history`, `find_contact`
  as plain Python functions returning the §3.4 `{facts, summary, phrasing_hints}` triple. **This is
  the brain API's body, minus a transport.** BL-5 adds the transport; it does not rewrite this.
- `belief/console.py` — line parser + pretty-printer over `tools.py`. Owns no belief logic.

**Modified:**

- `perception/source.py` — no protocol change. Add `SOURCE_*`-style id-prefix constants only if
  the prefix lands here rather than in each source.
- `perception/hybrid_source.py` — (stage 0) emit one `Observation` per distinct populated leaf;
  (stage 1) id prefix; (stage 3) `emit_mode`.
- `perception/naked_eye_source.py` — (stage 1) id prefix; (stage 3) `emit_mode`, with
  `NAKED_EYE_MAX_NEW_PER_POLL` re-read as an *acquisition-rate* limit rather than an emission cap.
- `perception/association.py` — (stage 0) `_type_match_score` resolves each candidate's
  `object_type` through `reporting_names.reporting_name_for` and scores against **both** raw type
  and reporting name, taking the max, so nothing that scores today regresses.
- `perception/geometry.py` — add `project_from_bearing_range(ownship, bearing_deg, range_m) ->
  GeoPosition`: flat, no terrain. Deliberately crude; BL-3 replaces it with terrain-aware
  estimation. Placed here because it is the inverse of the existing `bearing_deg`/`range_m` pair.
- `src/logger.py` — `main()` gains a `--console` mode that runs the belief pipeline; the plain
  text-logger path is unchanged.
- `body-layer/CLAUDE.md` — document the `belief/` package and the console entrypoint.

**Tests** — new `tests/test_percept.py`, `test_contacts.py`, `test_association_over_time.py`,
`test_decay.py`, `test_events.py`, `test_tools.py`, `test_console.py`, `test_cross_channel_fusion.py`.
Existing PB-1/PB-1.5 tests are **extended, not rewritten** — `emit_mode` defaults to the current
`on_change` behaviour, so every existing assertion stands.

---

### Implementation Plan

**Stage 0 — Scope-channel repair (see Decision 1; recommended in-scope).**
Own commits, own before/after evidence, per the backlog's requirement that this not ride along
invisibly. (a) `association._type_match_score` scores against raw type *and* reporting name.
(b) `hybrid_source` emits one `Observation` per distinct populated leaf among the five
`*_list_text` names, de-duplicated by text within the poll, each associated against a candidate
pool with already-claimed candidates removed.
*Acceptance (fixture):* a fixture reproducing Finding 6's four real tuples — `Slava cruiser` +
`Tarantul III corvette`, `SA-3 launcher` + `SA-3 Low Blow radar` — scores non-zero against the real
DCS type names (`MOSCOW`, `MOLNIYA`, `5p73 s-125 ln`, `snr s-125 tr`) where it scores 0 today, and
the SA-3 tuple yields **two** Observations, not one. Recorded as a before/after table in
`implementation.md`.

**Stage 1 — Belief core (minimal working version).**
`Percept` + `percept_of`; `ContactStore` with an append-only observation log; per-source
`Observation.id` prefixes; `project_from_bearing_range`; percept→contact gating.
Gate = spatial (hard) **and** class-not-incompatible (hard). Class compatibility is *three-valued*
— compatible / unknown / incompatible — because the two channels speak different vocabularies
(naked-eye emits `OP_TRUCK`; scope emits `"Ural truck"`), and `unknown` must neither block nor
confirm. Decision rule, per §2: exactly one contact passes the gate → merge; **two or more pass →
create a new contact.** The weak cross-channel vocabulary therefore costs at worst duplicate
contacts (visible, correctable) and can never cause a silent bad merge.
Spatial gate radius = perceived-position uncertainty + a growth term in elapsed time. Naked-eye
uncertainty is derived from its own quantisation: cross-range ≈ `range × sin(15°)` (the 30° clock
bucket) and down-range = the `OP_D*` bucket width — an honest uncertainty, not a tuning constant.
*Acceptance (fixture):* hand-authored `Observation` sequences produce the expected contact count;
two ambiguous candidates produce a new contact rather than a merge; `percept_of` provably drops
`derived_world_position`.

**Stage 2 — Decay, certainty, lifecycle.**
Per-attribute half-lives (identity slow, exact position fast, general area medium, motion medium)
as named constants; §3.4's `certainty` table implemented **once**, here, evaluated top-down.
`tick(now_sim)` materialises `CONTACT_LOST` transitions by comparing derived state against
last-emitted state — driven by `now_sim`, never wall clock, preserving BL-0's replay determinism.
*Acceptance (fixture):* a replayed stream produces detected → lost → reacquired in order; identical
input replayed twice produces byte-identical events; each `certainty` row is pinned by a test.

**Stage 3 — Emission policy and pipeline wiring.**
Add `emit_mode: "on_change" | "every_poll"` to both sources, defaulting to `on_change`.
`every_poll` emits one Observation per currently-perceived object/leaf per poll; the naked-eye
acquisition cap now gates *entry into the acquired set*, not emission, preserving its
"no instant global awareness" intent while giving BL-2 continuity. Wire the belief pipeline into
`logger.py` behind `--console`.
*Acceptance (fixture):* under `every_poll`, a continuously-visible object stays `certainty:
observed` across 60 s of replayed frames instead of aging to `lost`; all existing `on_change`
tests still pass untouched.

**Stage 4 — Tools and console.**
`tools.py` returning `{facts, summary, phrasing_hints}`; `console.py` mapping
`contacts [filter]` → `get_contacts`, `show <id>` → `describe_contact`, `history <id>` →
`get_contact_history`, `find <text>` → `find_contact`, plus `watch <id>` / `unwatch <id>` (a bare
attention enum + source field — **no** policy, cooldown, or relevance scoring; that is BL-4) and
`stats` (observation/contact/event counts, for measuring stream volume live).
`facts` carries only what BL-2 actually knows; semantic/`general_area`/clock fields are BL-3 and
are **absent**, not present-and-empty.
*Acceptance (fixture):* a scripted console session over a replayed stream produces the expected
transcript; every console command maps 1:1 to a §3.3 tool name with no console-only logic.

**Stage 5 — Cross-channel fusion validation.**
Fixtures where both channels observe the same physical object in the same and in adjacent polls.
*Acceptance (fixture):* one contact, two sources in its history, `certainty` reflecting the better
of the two observations; and a negative case where two genuinely distinct nearby objects stay two
contacts.

**Stage 6 — Live acceptance (USER-ONLY, requires flying DCS).**
One sortie with mixed placed targets (at minimum: a truck group **and** a SAM site or ships — not
Ural trucks alone, which is the coincidence that hid the namespace bug through PB-1's acceptance).
Protocol: (a) confirm scope-channel observations now appear for non-truck units — stage 0's live
half; (b) `contacts` lists what the player can see and nothing he cannot; (c) fly away from a
tracked contact and confirm detected → lost → reacquired with plausible `last_seen_ago_s`;
(d) run `stats` at the end and record the observation count for the volume risk below.

---

### Risks & Unknowns

- **Observation volume under `every_poll`.** At 1 Hz with a modest visible set the in-memory log
  is tens of MB per hour; a dense scene is worse. Mitigated by sighting spans as the durable
  per-contact summary and by `stats` measuring it live in stage 6. No cap is imposed now —
  capping before measuring would guess. BL-8/BL-9 inherit the persistence question.
- **The ownship 50 m exclusion window becomes a *wrong belief*, not just a silent gap.** With
  contact memory, an object passing within `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` stops producing
  observations, so a tracked contact transitions to **lost exactly when the aircraft is closest to
  it** — troop insertion/extraction, hovering over a target. BL-1 had no memory, so this was
  invisible. See Decision 2.
- **Cross-channel class compatibility is weak.** `"SA-3 launcher"` (scope) does not resolve to an
  `op_class` through `object_model`'s keyword table. Contained by the three-valued gate, but it
  means fusion will under-merge on SAM/ship types, producing duplicate contacts. Acceptable per
  §2; worth measuring in stage 6.
- **Decay half-lives and the §3.4 certainty thresholds are placeholders.** The plan's own note
  applies: tune against real sessions, do not argue now. What matters structurally is that they
  live in one table.
- **`project_from_bearing_range` is flat and terrainless.** Naked-eye's quantised bearing gives
  ≈ ±0.26 × range cross-range error before any terrain error is added. BL-3 will not fully rescue
  this — terrain intersection cannot recover angular resolution that was never observed.
- **Stage 0's live half depends on the scope channel firing at all** — it is populated only ~2% of
  flight time and is sight-gated (Finding 7). A sortie that never dwells on the sight will produce
  no scope evidence, and the stage-0 before/after will rest on fixtures alone. Flag before flying.
- **No coalition/IFF filtering** anywhere in either channel — carried forward unchanged, now with
  the added consequence that friendly and hostile objects share one contact namespace.

---

### Second-Order Effects

- **Unblocks BL-3** cheaply: `Contact` is the record world enrichment enriches, and
  `project_from_bearing_range` is the explicit stub BL-3 replaces. BL-3 becomes an additive change
  to `belief/`, not a new structure.
- **Unblocks BL-5** almost entirely: `tools.py` already returns the frozen response shape, so BL-5
  reduces to attaching a transport. This is the milestone's main strategic payoff and is why the
  console is built tool-first rather than print-first.
- **Narrows:** the `Percept` boundary means any later feature wanting DCS truth must justify
  crossing it explicitly. Deliberate — that is the invariant made mechanical.
- **Complicates BL-4:** the `certainty` table and the bare attention enum land here. BL-4 must
  build policy *on* them and must not restate the thresholds, or the "one table in body and nowhere
  else" rule breaks.
- **Complicates BL-9:** belief-vs-truth visualisation now has two sources of truth to reconcile
  (`Observation.derived_world_position` in the raw log, and the object ids the sources track
  internally). BL-9 should read the observation log, not reach into source internals.

---

### Invariant Check

- **DCS authoritative / never modified:** unaffected — read-only HTTP consumption, no DCS writes.
- **Code owns facts, models interpret:** strengthened. No model is involved in BL-2 at all;
  `tools.py` produces `facts` deterministically.
- **Petrovich never omniscient:** the load-bearing one. Enforced structurally by `percept.py`
  (truth fields cannot reach belief code), by identity never consulting `object_id`, and by the
  deliberate refusal to consume object *disappearance* from `LoGetWorldObjects` as evidence of
  destruction — a contact leaves belief only by decaying, never because DCS stopped listing it.
- **Provenance / uncertainty / timestamps:** every contact retains its contributing observation
  ids, each of which carries `source`, `provenance`, `t_sim` and `t_wall`. Naked-eye and scope
  provenance strings stay distinguishable, per PB-1.5's invariant check.
- **`world-model/data/` gitignore boundary:** unaffected; no new fixtures captured from live DCS
  are committed (stage 6 produces a transcript for `implementation.md`, not a data file).

---

### Decisions Requiring User Input

1. **Is the stage-0 scope-channel repair in scope for BL-2?** *Recommend yes.* BL-2's *machinery*
   does not depend on the scope channel — contact memory, decay, lifecycle and the console are all
   buildable and fixture-testable against the naked-eye channel alone. But **cross-channel fusion
   is an explicit BL-2 deliverable** (deferred here by PB-1.5 Decision 3), and validating fusion
   against a channel that scores 0 on ships, SAMs and most armour means either a fusion path that
   never fires or one validated only on Ural trucks — the exact coincidence that let this bug
   survive PB-1's acceptance test. The backlog's requirement that the fix get "its own before/after
   evidence and live re-test" is honoured by keeping it in its own commits and its own line in the
   stage-6 protocol, rather than by a separate branch and milestone cycle. **This does enlarge the
   milestone**, which is why it is a question and not a silent inclusion.

2. **The ownship 50 m false-negative window.** Three options: (a) accept as a known BL-2 caveat and
   raise the backlog item's priority — *recommended*; (b) add a body-side mitigation (suppress
   `CONTACT_LOST` while the contact's last-known position is inside the exclusion radius) —
   *recommend against*: a heuristic layered on a heuristic, and it would mask the real fix;
   (c) pull the aircraft-layer ownship flag into BL-2 — correct but a wire-format change affecting
   every consumer of `/world_objects/latest`, and a different subproject's milestone. Recommending
   (a), but this is a cross-subproject scope call, not mine.

3. **Does BL-2 emit `summary` prose, or `facts` + `certainty` only?** *Recommend a minimal
   one-line summary*: the console needs a human-readable line regardless, and writing it here is
   what proves the `certainty` enum is actually right rather than plausible. Real templating stays
   BL-5a. This touches `plans/body-layer/plan.md` §10 decision 4 (the pre-digestion posture), which
   you deferred — flagging it because BL-2 is where it first becomes concrete.

**Decisions made without escalation** (local, reversible, recorded per AGENTS.md): the `belief/`
package boundary; the `Percept` projection (CLAUDE.md's no-omniscience invariant decides this — it
is not a tradeoff); `emit_mode` defaulting to `on_change` so no existing test is rewritten; the
three-valued class-compatibility gate; `watch` implemented as a bare enum with no BL-4 policy;
`project_from_bearing_range` living in `geometry.py`.
