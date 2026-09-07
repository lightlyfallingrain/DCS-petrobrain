# Body Layer Plan — Review

### Review Summary

Reviewed `plans/body-layer/plan.md` (new, 896 lines) and the staged edits to
`PETROBRAIN_RUNTIME.md`, `PETROBRAIN_SYSTEM.md`, `division-or-responsibility.md`, each read in
full rather than as diff-only. Planning artifact — no code, no lint/test run.

The core invariant work holds. The brain has no fact-writing tool and §3.3 says so explicitly;
facts enter only via the aircraft layer; the brain is never handed a raw transcript (§3.5); the
templated-speech classes strengthen "code owns truth" rather than weakening it. The
`LoGetWorldObjects`-ground-truth omniscience risk is identified honestly in §9 rather than
assumed away, and the three DCS-internals unknowns are flagged as Investigator-blocking rather
than encoded as fact. The "sanitized data over sensor API" precedent the SRS adapter is compared
against does genuinely exist in `division-or-responsibility.md` (Aircraft → outputs), and the
`plans/aircraft-layer/plan.md` decision-3 citations check out.

### Required Fixes

- **§3.4/§3.6 strip world-model provenance that §1 mandates.** §1's seams paragraph requires body
  to carry world-model provenance through to the brain ("an 'east side of the village' derived
  from an OSM-matched settlement is a different confidence claim than one derived from DCS
  raster"), but both worked examples render `semantic` as bare strings —
  `["east side of VILLAGE_12", "near ROAD_41"]`. The plan contradicts its own statement of a
  project invariant in the one place an Implementer will copy from. Make `semantic` entries
  objects carrying source + confidence.

- **BL-5's dependency order is inverted.** BL-5 "freeze the §3 tool set as an actual callable API"
  — but §3.3's tool set contains `scan_area`/`get_task_status`/`cancel_task` (PendingIntent
  machinery, built in BL-7), `say`/`ask_player`/`handle_player_utterance` (BL-5a), and
  `get_mission_phase` (BL-6). Three later milestones supply infrastructure BL-5 needs. Either
  scope BL-5 to the read/attention subset and freeze the rest incrementally, or state that BL-5
  freezes *signatures* with stubbed command tools.

- **Debounce/silence-gate placement is asserted as decided in one file and open in another.**
  `division-or-responsibility.md` states flatly "debounce and gating live in the SRS adapter, not
  body. Body should never see a transmission that was not real speech", and
  `PETROBRAIN_RUNTIME.md`'s inbound pipeline and PB-8 both bake it in — while plan §7 says the
  placement is "genuinely open and I am not confident" and §10.5 escalates it to the user. Hedge
  the two docs to match the plan, or drop the plan's open question. Currently a reader of the
  concept docs would never know a decision is pending.

- **Stage the architect's agent-memory files.** `.claude/agent-memory/architect/MEMORY.md` is
  modified and `.claude/agent-memory/architect/project_body_layer_api_decisions.md` is untracked.
  Sixth recurrence of this pattern; DoD requires a clean tree.

### Optional Refinements

- `phrasing_hints.certainty` has no derivation rule (optional). It collapses several per-attribute
  confidences into one 4-value enum, and §3.6's claim that dropping `visible` to false yields
  degraded hedging "without the brain being involved" references a `last_seen` field that the
  `contact_group` schema shown doesn't have. The enum also doesn't cleanly cover
  `PETROBRAIN_RUNTIME.md`'s four registers — "I lost him" maps to none of them.
- `acknowledge_event(event_id, spoken: bool)` asks the brain to self-report something body can
  observe directly, since `say` is the only speech path (optional). Deriving it removes a trust
  dependency on the model.
- No "Affected Modules / Files" section (optional), unlike `plans/aircraft-layer/plan.md`. §10.1
  asks whether `body-layer/` becomes a sibling subproject but never sketches its layout — the
  section an Implementer opens first is missing.
- Handing raw DCS `x`/`z` to the model in `facts.position.dcs` (optional) — unusable by a language
  model and an invitation to confabulate precision.
- `PETROBRAIN_RUNTIME.md`'s parenthetical "(adapter as a sibling of the aircraft layer, not part
  of it)" drops the "Proposed" hedge that the source bullet carries (optional).

### Verdict

APPROVED WITH MINOR FIXES

All four required fixes are text edits to a draft document, not architectural rework. The plan is
correctly marked provisional in the house style and does not overcommit on the two live unknowns.

### Review Confidence

Full read — plan, aircraft-layer precedent, and all three concept docs read in full; cross-file
consistency claims (SRS placement, decision-3 citations, "sanitized data" precedent, runtime
uncertainty registers) verified against source rather than taken from the diff.

---

## Round 2 — Re-review of applied fixes

### Review Summary

Verified the four round-1 required fixes against the staged content of
`plans/body-layer/plan.md` and the three concept docs (`plan.md` is a newly-added file, so no
round-1→round-2 git delta exists; each fix area was re-read directly instead).

1. **Provenance leak — landed.** `semantic_claim` is defined in §5 with
   `text`/`feature_id`/`confidence`/`provenance`, carries the explicit "never bare strings" rule
   plus the templated-speech carve-out, and both worked examples (§3.4, §3.6) now use it. The fix
   also propagated to spots round 1 did not name: `contact.general_area` gained
   `provenance: osm_matched`, `semantic_cache.descriptions` is annotated `SemanticClaim, never a
   bare string`, and §3.6's bullet now cites §5. No remaining bare semantic string in a `facts`
   block — the surviving plain-English strings (§3.4 `summary`, `event.suggested_phrasing`,
   `find_contact(description)`) are spoken/query text, correctly out of scope.
2. **BL-5 dependency order — landed.** BL-5 is scoped to the 12 read/attention tools, BL-5a/BL-6/BL-7
   each carry an *Adds to the tool API* line, and the freeze point is restated as end of BL-7 with
   a rationale. The subset matches what BL-0..BL-4 are described as delivering (BL-4 supplies
   attention + event queue, so `poll_events`/`acknowledge_event`/`watch_area` are legitimately in).
3. **Debounce/gate placement — landed in all three places it needed to.**
   `division-or-responsibility.md` (signal-level adapter-side + later context-dependent body-side
   refinement), `PETROBRAIN_RUNTIME.md` PB-8 (same two-part wording), and plan §2's split table
   marked **Settled** now agree verbatim in substance. §7's "genuinely open" framing is gone and the
   residual open item is narrowed to which process hosts the adapter; §10.5 keeps the sibling-vs-
   aircraft-layer question open while explicitly bracketing the responsibility as settled — the
   right line. `PETROBRAIN_SYSTEM.md` does not discuss the audio boundary at all, so nothing was
   owed there.
4. **`certainty` derivation — landed but the table has a logic defect** (see below). The table,
   the `lost` register, and `last_seen_ago_s` on `contact_group` all exist as claimed, and the
   fields referenced (`visible`, `position.confidence`, `classification.confidence`) do match the
   §3.4/§5 data model.

### Required Fixes

- **The `certainty` table's `unknown` row is unreachable, and a visible low-confidence contact
  gets a declarative register** (§3.4, plan.md:409-415). Evaluated top-down, first match wins:
  `uncertain` already fires on `classification.confidence < 0.5`, which subsumes the `unknown`
  row's `< 0.3` entirely — so `unknown` can never be selected. Symmetrically, `observed` fires on
  `visible: true` alone, so a contact seen right now at `classification.confidence: 0.15` yields
  "I have him." with no identity hedge — the exact conflation of *positional* and *classification*
  certainty that this table was added to prevent. Order `unknown` above `uncertain` and make
  `observed` conditional on classification confidence as well as `visible` (or split the enum into
  a position register and an identity hedge). This is a two-line edit, but the table is now the
  single normative source for the epistemic register, so a defect in it propagates into every
  templated utterance.

### Optional Refinements

- `lost`'s condition is written as a state *transition* ("`visible` transitioned true→false within
  the last ~10 s") while the paragraph below claims `certainty` is a pure function of
  `(contact, now)` needing no separate state (optional). It is derivable — `not visible and
  last_seen_ago_s <= 10` — but restating it in those terms removes the apparent contradiction and
  the temptation to store a transition flag.
- `docs/concept/threat-levels.md` is untracked in the working tree (optional, and outside this
  review's scope — it is not architect output). It overlaps §2's relevance/urgency model, so it
  should either be staged and referenced from the plan or explicitly left as a scratch note.

### Verdict

APPROVED WITH MINOR FIXES

Three of four fixes are fully resolved with no new inconsistencies introduced and no scope creep;
nothing was prematurely settled — the placement question that genuinely remains open is still
flagged in both §7 and §10. The fourth landed structurally but its table needs one ordering/guard
correction. That correction does not warrant another full review round.

### Review Confidence

Full read of the four fix areas and their cross-references (§1 seams, §2 split table, §3.3 tool
list, §3.4, §3.6, §5, §6 milestones, §7, §10) plus the corresponding sections of all three concept
docs. Deliberately did not re-review plan sections untouched by these fixes — round 1 covered them.
