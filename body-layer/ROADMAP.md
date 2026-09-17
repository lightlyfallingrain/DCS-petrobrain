# Body Layer — Roadmap

Petrovich's belief-state process: contacts, attention, perception ingestion, the brain-facing API.
Full architecture/design (scope boundaries, tool-set design, data model, open questions, decisions):
`plans/body-layer/plan.md` — that doc's §6 "Milestones (BL-x)" describes what each milestone below
*is*; this file tracks what's actually *done*. PB-x in the descriptions below cross-references
`docs/concept/PETROBRAIN_RUNTIME.md`'s runtime milestone numbering — BL-x is the body-owned slice
of it. Update this file (not `../todo/todo.md`) whenever a body-layer branch merges — see
`../.claude/skills/merge.md`.

**Live acceptance debt.** A milestone can pass DoD on fixture/console testing alone when its plan
scopes live-DCS acceptance out deliberately (a real decision, not debt — e.g. BL-3, the overlay
clock/range summary). This list is for the other kind: a milestone whose live acceptance was
*deferred*, not waived, and hasn't been confirmed since. Added 2026-09-10 after a retro found this
caveat being logged repeatedly (BL-4, BL-5, the continuity fix) without ever being tracked as
accumulating risk. Clear an entry only once a real sortie actually exercises it, and say which one.

- [ ] **BL-4's attention/events tools** (`set_attention`/`watch_area`/`get_attention_state`/
  `list_events`/`acknowledge_event`) — live acceptance deliberately deferred, "bundled with BL-5's
  transport layer" per the BL-4 plan. BL-5's own live sortie exercised `place`/`position`/
  `situation`, not these — unclear whether BL-4's tools have had a live run at all yet.

- [~] **F10 command vocabulary — the 15-token set and relative-sector re-projection** (merged
  2026-09-16, `plans/f10-command-vocabulary/`). **First sortie flown 2026-09-16/17 — partially
  cleared.** Confirmed live: the menu tree is navigable, scans register real tasks, and
  `Cancel Task` genuinely cancels. Two defects found and fixed (merge `74f0fff`,
  `fix/scan-naked-eye-not-9k113`): Scan was driving the 9K113 sight instead of this project's own
  naked-eye perception, and `Cancel Task` spoke a raw task id. Still unexercised, so this entry
  stays open: relative-vs-bearing sector rotation through a manoeuvre including a 0/360 wraparound,
  and the `F10_SCAN_RADIUS_M` / `DEFAULT_SCAN_DEADLINE_S` placeholder calibration — the latter is
  hard to judge until a scan actually steers perception (`todo/todo.md`). What that sortie must
  exercise: the new menu tree is navigable (Scan -> Ahead/Left/Right/Full, Scan -> Bearing ->
  eight compass items, Watch -> Nearest, Cancel Task); relative scans rotate with the nose while
  Bearing scans do not — including a heading sweep through 0/360 to confirm no wraparound
  discontinuity; each scan registers a real pending task; **Cancel Task actually cancels
  something**, which it never could before this milestone; and a failed live trigger still
  leaves the task registered. Also the milestone's one real calibration gap:
  `F10_SCAN_RADIUS_M` (3000 m) and `DEFAULT_SCAN_DEADLINE_S` are uncalibrated placeholders and
  want real numbers from a flight. Full plan in
  `plans/f10-command-vocabulary/dod-check.md`'s Acceptance Testing Plan.

## Status

- [x] **BL-0 — Harness and replay.** Body process skeleton, aircraft-layer HTTP client, world-model
  query client, recorded-stream replay harness (`body-layer/src/replay.py`). Landed as part of PB-1.

- [x] **BL-1 — Observation ingestion (≈ PB-1, done 2026-09-08).** `feature/pb1-perception-logger`.
  Hybrid HelperAI perception source + association + text logger. Live acceptance on a real Mi-24P
  sortie with manually-placed ground targets; plausible bearing/range in an ambiguous-candidate
  scenario (4 clustered Ural trucks). Original two-tier architecture falsified by a live spike and
  pivoted to a single hybrid implementation (HelperAI text as detection gate, `LoGetWorldObjects`
  geometry via association). Full history: `plans/pb1-perception-logger/`.

- [x] **PB-1.5 — Naked-eye visual detection channel (done 2026-09-09, no direct BL- number —
  a perception-tier addition, not contact-memory work).** `feature/pb1.5-naked-eye-detection`. A
  second, independent perception channel (`NakedEyePerceptionSource`) reporting plausibly-visible
  ground objects from `LoGetWorldObjects`, gated by FOV + angular-size + terrain-LOS, quantised to
  ED's own callout vocabulary. A live A/B probe established DCS's ambient contact callout has no
  Lua-readable companion — the synthetic filter is not a fallback, it's the only implementation.
  Findings: `aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`. One live bug
  fixed: `LoGetWorldObjects` included the player's own aircraft as a contact
  (`association.exclude_ownship`, later replaced — see BL-2 Stage -1 below).

- [x] **BL-2 — Contact memory and association (= PB-2, done, merged 2026-09-09).** Persistent
  contact identities, detected/lost/reacquired, observation-vs-belief split, decay/certainty ladder,
  cross-channel fusion, a debug console (`belief/console.py`). Stages: **-1** aircraft-layer
  `is_ownship` flag (replacing the proximity-heuristic exclusion); **0** scope-channel type-namespace
  repair (`association._type_match_score` resolves DCS type names through `reporting_names` before
  scoring); **1** belief core (`belief/percept.py`'s `Percept` structurally drops DCS truth fields,
  `belief/contacts.py`'s `ContactStore`, `belief/association_over_time.py`'s gating); **2**
  decay/certainty ladder + lifecycle events; **3** `emit_mode` + `--console` wiring; **4**
  `belief/tools.py`'s `get_contacts`/`describe_contact`/`get_contact_history`/`find_contact`; **5**
  cross-channel fusion (fixture-validated); **6** live acceptance (a real sortie against
  `--console`; one real bug found and fixed — `--console`'s poll thread crashed on a
  main-thread-opened `sqlite3.Connection`, since `sqlite3.Connection` is thread-affine). Core design
  decision: contact identity is geometric, from perceived attributes only — never `object_id` or any
  truth field, so Petrovich can confuse two identical trucks (the omniscience CLAUDE.md forbids).
  Full history: `plans/pb2-contact-memory/`.

- [x] **BL-2.5 — In-cockpit text mirror (interim, no PB- equivalent; done, merged 2026-09-09).**
  `feature/dcs-text-panel-output`. Mirrors belief lifecycle events into a DCS Hook-state overlay
  window (`Saved Games/DCS/Scripts/Hooks/`, `AutoScrollText` widget, SRS-pattern loopback UDP),
  fed via new `POST /text/push` on aircraft-layer, so live sortie testing is readable in-cockpit.
  Live-verified on a real sortie. Refinement pass: a restyle matching DCS's own `gameMessages.dlg`
  values was live-tested and **rejected by the user** — "reads worse in cockpit than the titled
  window despite being factually grounded" — reverted, keeping only the contact-id fix. Lesson:
  grounding a design in authoritative source values does not guarantee visual acceptance; keep
  cosmetic and correctness changes in separate commits so a rejected restyle doesn't collateral
  damage an unrelated fix. Full history: `plans/dcs-text-panel-output/`.

- [x] **BL-2.6 — Classification refinement (interim, no PB- equivalent; done, merged 2026-09-09).**
  `feature/classification-refinement`. Replaces BL-2's last-writer-wins classification fusion with a
  four-level specificity lattice (`unknown → presence → class → type`, `belief/classification.py`)
  and a fold rule so identity refines monotonically instead of oscillating; fires
  `CONTACT_CLASSIFICATION_CHANGED` on refinement/contradiction only. User decisions departing from
  the architect's recommendation: naked-eye reaches `type` at close range (not capped at `class`),
  gating tier moved `medres → lowres`. **Live-acceptance-found bug, fixed**: a single real object
  was producing 8–20 `Contact` records — the spatial gate budgeted only the incoming percept's own
  position uncertainty and treated `Contact.last_position` as exact; naked-eye's clock-bucket
  requantisation re-anchors to current heading every poll, so a stationary object's implied position
  can jump a full bucket-width between polls. Fixed with a symmetric gate
  (`Contact.last_position_uncertainty_m`, budgeted both sides). Watch-item carried forward: the
  wider symmetric gate roughly doubles the close-range floor, raising false-merge risk for two
  distinct objects at ~300–600 m — this is exactly what the object-permanence fix below closed.
  Full history: `plans/classification-refinement/`.

- [x] **Object-permanence continuity (no BL- number — a contact-memory refinement in the BL-2/2.6
  lineage; done, merged 2026-09-10, `c1af0e0`).** `fix/association-gate-ambiguity-runaway`. BL-2.6's
  symmetric-gate fix reopened a different bug: the wider gate now overlaps between genuinely
  distinct nearby real objects, and `ContactStore.ingest`'s "never guess-merge" rule had no bound on
  runaway spawning once that overlap fired (reproduced: 2 stationary objects ~874 m apart, 60 polls
  → 120 duplicate contacts). Scope grew mid-plan from "zero-gap continuity only" to full object
  *permanence*, per the user's framing: correlation now fires on any `object_id` match regardless of
  gap length, subject to a 600 s decay (`OBJECT_ID_MEMORY_S` = `IDENTITY_HALF_LIFE_S`,
  `object_id_continuity_valid`) — an expired match falls through to the ordinary spatial/class gate
  exactly like an unresolved one. `association_over_time`'s gate is now the *exception* path
  (founding observations, non-correlating reacquisitions, expired continuity), not the common case.
  Both perception sources are in scope (the scope/hybrid channel's earlier exclusion from `object_id`
  correlation no longer applies). **Live-verified**: masked-gap reacquisition (76 s behind terrain,
  correctly reacquired under the same contact id) and the original duplication scenario (mixed-unit
  cluster) no longer runs away. Full history: `plans/contact-duplication-ambiguity-runaway/`.

- [x] **BL-3 — World enrichment (= PB-3, done, merged 2026-09-10, `8df2791`).**
  `feature/bl3-world-enrichment`. Filled the four still-empty `describe_contact` fields
  (`position.confidence`, `relative_now`, `semantic`, `motion_when_seen`) without touching BL-2's
  contact/classification logic. New `belief/enrichment.py`: `SemanticFact` + a placeholder
  string→numeric confidence table, `semantic_facts_for` (one `query.describe_position` call per
  contact), `WorldEnrichmentCache` (keyed by `contact_id`, recomputes only when `last_position`
  changes), `relative_geometry`, `motion_when_seen` (direction from the two most recent distinct
  implied positions, unsmoothed). `geometry.py` gained `project_terrain_aware` (iterative
  fixed-point terrain-fit) alongside the existing `project_from_bearing_range`; gating is single-shot
  by default, iterative only when `range_m ≤ PROJECTION_ITERATIVE_RANGE_M` (placeholder `2000`) or
  `contact.attention == "watch"`. Fixture-tested only; no live sortie required by plan scope. DoD
  passed, zero required fixes. **Load-bearing placeholders inherited by BL-4**: the confidence
  table, unsmoothed motion derivation, position-keyed (not time-keyed) semantic cache staleness —
  first-guess constants, not tuned. Full history: `plans/bl3-world-enrichment/`.

- [x] **Overlay clock/range summary (small feature riding on BL-3 + BL-2.5; done, merged 2026-09-10,
  `4ef08bd`).** `feature/overlay-clock-range-summary`. Appends a clock-position/range fragment
  (`"11 o'clock, 3.0 km."`) to `Contact` summaries via `tools.py`'s `_contact_summary`, rendered
  whenever `relative_now` is present regardless of visibility. No `console.py` change needed —
  `format_event_for_overlay` already reads `summary` verbatim, so overlay and console both picked it
  up automatically. One Reviewer-required fix: a double-punctuation defect from appending onto a
  string already ending in `.`. No live acceptance needed — judged a pure formatting change over an
  already-verified field. Full history: `plans/overlay-clock-range-summary/`.

- [x] **BL-4 — Attention and events (= PB-4, done, merged 2026-09-10, `546fa93`).**
  `feature/bl4-attention-events`. Four-state `Attention` (`ignore`/`normal`/`watch`/`priority`,
  `belief/attention.py`), `AttentionArea` (center + radius + optional sector) with `area_contains`,
  `effective_attention` (direct mark vs. area membership, `ignore` always wins), a
  `CONTACT_ATTENTION_CHANGED` event wired into `ContactStore.tick` with a 15 s per-contact-per-kind
  cooldown independent of classification's own contradiction lockout. New tools:
  `set_attention`/`watch_area`/`unwatch_area`/`get_attention_state`/`list_events`
  (aliases `poll_events`)/`acknowledge_event`; seven new console commands. 333 tests (291→333),
  Reviewer approved zero required fixes across six independently cross-checked design claims.
  Console/replay-only scope — live-DCS acceptance deliberately deferred, bundled with BL-5's
  transport layer per the plan. Design note worth knowing: `effective_attention` stores *effective*
  (not direct) attention in `last_emitted_attention`, so a contact walking into/out of a watched
  area fires an event even with no change to its own direct mark — deliberate, flagged as
  reversible in the plan. Full history: `plans/bl4-attention-events/`.

- [x] **BL-5 — Deterministic tool API (= PB-5, done, merged to main, `288e31d`).**
  `feature/bl5-tool-api`. Formalizes `belief/tools.py`'s functions into a named, documented,
  fixed twelve-tool surface (`belief/tool_api.py`'s `TOOL_SET: list[ToolSpec]`) a human can hold a
  full tactical conversation against by hand, no LLM involved. Nine tools already existed; three
  net-new: `find_place` (new `world-model/src/query/search.py`'s `find_place_by_name`,
  case-insensitive substring match over settlements/named places/airfields/navaids,
  confidence-ranked), `describe_our_position`, `get_situation` (aggregates contact counts,
  highest-attention contact, unacknowledged event count, position summary — deterministic, no
  relevance scoring since BL-6 hasn't built one). Three new console commands (`place`, `situation`,
  `position`). 252 world-model tests (+8), 356 body-layer tests (+23). **One live bug found and
  fixed**: `situation` crashed on first live run — `sqlite3.ProgrammingError` from BL-3's
  `ConsolePerceptionRunner.enrichment` holding a poll-thread `sqlite3.Connection` the REPL thread
  then read (same defect class as BL-2 Stage 6, in a field that fix didn't cover). Fixed: the REPL
  now lazily builds its own thread-local connection/`EnrichmentContext`. Harvested to NOTES.md:
  sqlite3 thread-affinity is a recurring defect class in this codebase's polling/REPL architecture.
  **The tool-set freeze point was BL-6, not BL-7** (moved 2026-09-11 when BL-6's investigation
  resolved what it needed to add — see that entry below) — §3.3's tool list is the API's intended
  final shape, delivered incrementally; a brain-layer prototype can start against the BL-5 subset
  now but should expect the surface to grow through BL-6. Full history: `plans/bl5-tool-api/`.

- [x] **Scope-channel type-namespace mismatch, re-verified (closed as a stale backlog item, not
  new work; `fix/association-namespace-mismatch`).** The fix was already in `main` under BL-2/PB-2
  Stage 0 (`association._type_match_score` resolves DCS type names through `reporting_names`
  before scoring); this item had just never been checked off. A 2026-09-10 debugger pass
  re-measured the four originally-0-scoring real pairs (Slava cruiser, SA-3 launcher, Tarantul III
  corvette, SA-3 radar) directly against current code — all score nonzero, regression-tested in
  `test_association.py`/`test_hybrid_source.py`. Still open, not tracked separately: a live re-test
  against ship/SAM-site contacts specifically (the original PB-1 acceptance test used only Ural
  trucks, the one case where the two naming vocabularies happen to coincide).

- [x] **Deterministic mock-flight test fixture for the whole aircraft+body+world chain (excluding
  the brain/LLM). Done, merged 2026-09-10.** Raised after two live-only bugs (the duplicate-contact
  runaway, the cross-thread sqlite REPL crash) that per-layer fixture/unit tests didn't catch
  because they only exercise one layer at a time. Built: `tests/support/mock_aircraft_layer.py` (a
  real loopback HTTP server standing in for aircraft-layer's `/telemetry`, `/world_objects`,
  `/petrovich_indication` endpoints) + `mock_world_model.py` (synthetic world-model store) +
  `tests/fixtures/mock_flight_canonical.json` (a canonical 20-frame flight) +
  `test_mock_flight_chain.py` (4 tests: mock-server frame semantics, LOS-gate wiring,
  single-threaded full-chain determinism, threaded console/REPL smoke test). Test-only, no `src/`
  changes; 374/374 passing. **Notable finding:** the harness did not reproduce either bug that
  originally prompted it — both were already fixed on `main` — so it stands as the regression gate
  for that bug class going forward, not a repro of a live incident. Generalizes `replay.py`'s
  narrower single-source pattern up to the aircraft-layer HTTP boundary. Plan:
  `plans/mock-flight-fixture/`.

- [x] **BL-5a — Text-mode crew interaction (precursor to PB-7/PB-8; done, merged to main,
  `64015cd`).** `feature/bl5a-text-mode-crew-interaction`, cut from `main` before BL-5 merged.
  Deterministic intent parser (`belief/utterance.py`), readback/contact-report/urgent-call
  templates (`belief/speech.py`), the body→brain escalation entry point (`belief/escalation.py`,
  `handle_player_utterance`), and a typed-input crew-facing REPL (`belief/crew_console.py`,
  `logger.py --crew-text`). 367 new tests, Reviewer approved zero required fixes, DoD passed (4/4
  acceptance criteria demonstrated) — **then** live acceptance testing surfaced a duplicate-contact
  bug (2 stationary objects ~874 m apart, 60 polls → 120 contacts) that the Debugger declined to
  patch (both mechanisms involved are deliberately-designed invariants) and escalated to Architect,
  unresolved (`6d7a8d8`, 2026-09-10 18:48). Resolved without a fresh Architect decision: the
  already-merged object-permanence continuity fix (`c1af0e0`, merged 20:00 the same day — after
  BL-5a's bug was found) targeted exactly this failure mode. Re-verification: merged `main` into
  the branch, full body-layer suite green (ruff format/check, mypy --strict, 408/408 pytest), then
  the user re-ran live acceptance against the same repro scenario post-merge — passed, no more
  duplicate spawning. Full history: `plans/bl5a-text-mode-crew-interaction/`.

- [x] **BL-6 — Commands and inspect-and-adapt (done, merged 2026-09-11, `feature/bl6-commands-
  inspect-adapt`, merge commit — see `git log --oneline -1 main` after this push).** `PendingIntent`
  lifecycle (`body-layer/src/belief/tasks.py`), `scan_area`/`get_task_status`/`cancel_task`; this
  was the tool-set freeze point (moved from BL-7, see that entry above). A day of live-DCS probing
  plus a real-manual cross-check (RU Mi-24P QuickStart, `docs/concept/mi-24_info/`) resolved the
  plan's original two blocking premises — see `aircraft-layer/research/2026-09-11-SUMMARY-
  petrovich-control.md` and the revised `plans/bl6-commands-inspect-adapt/plan.md`: Petrovich has
  real search verbs (`SRCH FWD`/`BRST` triggerable; every *directed*-aim route — `SRCH 9K113 LOS`,
  `DesignateAttackPoint`, puppeting the pilot's view — closed, the last confirmed by the manual to
  have no real-hardware analog at all) and a real, directly-readable outcome signal
  (`list_indication(6)`/`(10)`), so `scan_area` triggers a real search and verifies a real outcome
  rather than inferring success from belief-state timeout. `cancel_task` removes its
  `AttentionArea` (user decision). Aircraft-layer effector: `POST /command/petrovich_search` +
  `GET /petrovich_wheel/latest`, wired into body-layer's `Console` via an optional
  `aircraft_client` field — no separate Security plan review was run (this project's current
  phase exempts Security/Performance Reviewer per root `CLAUDE.md`'s "Agents" section; the
  original "needs its own Security plan review" language above predates that exemption and is
  superseded). 437 body-layer + 90 aircraft-layer tests green; live-DCS acceptance of the new
  effector (does `POST /command/petrovich_search` actually fire `SRCH FWD` in a running mission)
  is deliberately deferred to the user's own follow-up, not this milestone's DoD gate — add to the
  "Live acceptance debt" list above if it isn't exercised soon. **Downstream consequence for BL-7/
  BL-8:** every future "have Petrovich actually do X" idea inherits the same closed-directed-aim
  ceiling this investigation found — no design assumes we can point his attention at a bearing we
  choose, only trigger-and-verify. **Next queued item (user priority, `todo/todo.md`):** route
  `belief.speech`'s spoken contact callouts to the in-game overlay (currently only reaches
  `--crew-text`'s stdout, not `--overlay`'s cockpit text panel) — not part of BL-6's own scope, a
  separate follow-on.

- [x] **BL-7 — Mission phase and relevance (≈ PB-9's deterministic half; done, merged 2026-09-13,
  `feature/bl7-mission-phase-relevance`, merge commit `ec4cf12`).** `MissionPhaseTracker` consumes
  Mission Interpreter's MI-6 `--emit-compact` JSON output (file read, no cross-subproject import —
  mission-interpreter is not the body-layer ↔ world-model in-process exception). Sequences ownship
  monotonically through route waypoints via a capture-radius check (`WAYPOINT_CAPTURE_RADIUS_M`,
  uncalibrated placeholder, same debt class as `visibility.py`'s tier constants pending live
  calibration). Pure in-memory tracker (ints/tuples, no sqlite), written from poll thread
  (`.update()`), read-only from REPL thread (`.current_phase()`), deliberately mirrors
  `EnrichmentContext.ownship`'s cross-thread split to avoid this codebase's recurring
  sqlite thread-affinity defect class (BL-2 Stage 6, BL-5). **No new tool** — mission-phase
  proximity folds additively into `get_situation`'s facts payload as a tie-breaker *only* within
  attention tiers, never overriding cross-tier ranking (resolves the stale "adds `get_mission_phase`"
  flag — the tool-set freeze point was BL-6, not BL-7, and the decision here was to extend
  `get_situation`'s existing payload rather than a new tool, per `tool_api.py`'s module docstring).
  Tests: 475 passed (+24). Fixture-based acceptance testing only; live acceptance (real MI-6 output
  end-to-end against a real flight) deliberately deferred, same posture as BL-6's `scan_area` wiring
  gap. Full history: `plans/bl7-mission-phase-relevance/`.

- [ ] **BL-8 — Memory layer interfaces.** Not started, deliberately last (user decision, 2026-09-10:
  "the shape of what's worth remembering is only knowable after BL-2..BL-7 have run for real").
  Standing awareness note while BL-2..BL-7 touch in-mission memory shapes (`Contact`/`ContactStore`,
  BL-4's `AttentionArea` registry): keep BL-8's eventual mission-end export/persistence boundary in
  mind, not as a design constraint yet, just don't shape something in a way that obviously fights it.

- [ ] **BL-9 — Debug visualization.** Not started. Belief-vs-DCS-truth debug view. Arguably worth
  pulling earlier if BL-2/BL-3 turn out hard to reason about textually.

- [ ] **BL-10 — SRS transport wiring (= PB-7 + PB-8, body's half only).** Not started. Swaps BL-5a's
  typed/printed stand-ins for the real SRS adapter. The adapter itself (SRS client, ICS channel, PTT
  debounce, silence gate, STT, TTS) is not body-layer work and needs its own plan and Investigator
  pass on SRS's interface.

  **Also owns the rich command vocabulary** (user direction 2026-09-16): the F10 radio menu is
  deliberately capped at the simple fixed set `f10-command-vocabulary` built, and everything the
  command half of `docs/concept/state-transitions.jpg` asks for beyond it — `watch <unit>
  <where>` against a live contact list, waypoint/landmark-anchored scans, the
  `o'clock-and-distance` location form — is SRS's, not F10's. Those are *rejected* for the radio
  menu rather than deferred, so this milestone's scope is wider than "swap the transport": that
  diagram's command half is its requirements input. Do not re-expand the F10 tree instead.

- [x] **Cockpit visibility limits for the naked-eye channel (no BL- number — a perception
  correctness fix, not a milestone; done, merged 2026-09-17, merge `bd4a4dc`,
  `feature/cockpit-visibility`).** `perception/visibility.py`'s naked-eye gate was a bare azimuth
  cone with **no elevation term at all** — a contact 90 m below and 60° off the nose passed as
  easily as one on the horizon. At 100 m AGL a contact 200 m out sits ~27° below, so this was the
  normal case, not an edge case: Petrovich saw through the fuselage and floor and reported contacts
  he could not possibly see. A standing no-omniscience violation, predating the milestone that
  surfaced it (the first live F10 sortie).

  Replaced by a body-relative occlusion mask (`perception/cockpit_mask.py`): max depression per
  azimuth band, evaluated in the airframe frame via `geometry.body_relative_direction`, so it
  follows pitch and bank rather than heading alone — a banking helicopter is exactly when a
  heading-only cone is most wrong. No aircraft-layer change was needed; `pitch_rad`/`bank_rad` were
  already on the wire and simply never consumed by `OwnshipState`. Per-station (D6, only the
  co-pilot populated), symmetric (D5, the real cockpit is slightly asymmetric but the user judged
  the difference insignificant).

  **Angles are the user's own measurement from the DCS co-pilot seat**, boresight-relative: 22° down
  flat across az 0–60, 10° at az 90, tapering to 0 at the az 130 rear cutoff. That replaced a
  screenshot-derived first pass it showed wrong in *both* directions — nose far too permissive
  (45° vs 22°), rear cutoff far too tight (100° vs 130°). Because D3 mandated splitting mechanism
  from calibration, that correction was a table swap with the mechanism untouched and not
  re-reviewed: the split paid for itself within a day.

  Petrovich is now strictly blinder by design, most noticeably close-in abeam and directly below.
  The mock flight chain drops 57 → 53 observations for exactly that reason (a target 200 m below
  passes under the nose once horizontal range closes inside ~495 m). 527 → 544 tests.

  **Open risk:** the pitch/bank sign convention is assumed, not verified. Partial evidence supports
  the pitch sign (a parked sample reads +2.76°, consistent with an airframe sitting nose-up on its
  gear); none exists for bank. An inverted bank sign **fails dangerous** — it silently swaps which
  side gains visibility in a turn, and no unit test can catch it, since they all check the code's
  own convention against itself. Resolved by rolling right once in a real sortie and reading the
  sign. See `plans/cockpit-visibility/` (plan, review, dod-check, implementation).

## Backlog (body-layer)

- [x] **F10 radio-menu command input for Petrovich — mechanism done, merged 2026-09-13 (merge
  `eacc45c`, `feature/f10-crew-commands`).** The player's preferred in-cockpit command UI: the
  native DCS F10 radio menu, not keybinds (F-4E-style radial wheel explicitly out of scope). A
  Hook script (`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua`) registers
  F10 → Other → Petrovich (Watch Nearest / Scan Forward / Cancel Task) via
  `net.dostring_in("scripting", "missionCommands.addCommand(...)")` at `onSimulationStart`, polls
  selections back at 1 Hz, and forwards them over loopback UDP 7794 to the collector's
  `GET /f10_commands/poll` (drain-once queue); `logger --crew-text --f10-commands` dispatches them
  through `CrewConsole.handle_f10_command` into the same output/overlay path as typed commands.
  Prerequisite: `Saved Games\DCS\Config\autoexec.cfg` with `net.allow_dostring_in = { "scripting" }`
  (minimal set, live-confirmed). Recon: `aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md`
  Findings 7–11. **Live acceptance (user, 2026-09-13, DCS 2.9.29.27278):** menu appears and all
  three items reach body-layer, including across pause and mission restart. User verdict: "the
  commands themselves need work. But the mechanism is ok." — merged on the mechanism, command
  behaviour split into the follow-ups below. History: `plans/f10-crew-commands/` (plan, review,
  dod-check). Next-milestone impact: none on the BL sequence; it adds a second `CrewConsole` input
  surface that BL-10's SRS transport can follow.

- [x] **F10 command vocabulary and ownship-relative sectors — command half done, merged
  2026-09-16, merge `1a9189c` (`feature/f10-command-vocabulary`,
  `plans/f10-command-vocabulary/plan.md`).** Addresses "F10
  command refinement and specification" below for the command half of `docs/concept/
  state-transitions.jpg`'s spec — the vocabulary/geometry/wiring half, not the autonomous-behaviour
  half (deliberately out of scope, see that plan's Scope section). Widens the F10 menu from three
  flat items to 15 tokens (D4): **Scan** → Ahead/Left/Right/Full (ownship-relative) + eight compass
  **Bearing** items (absolute), **Watch** → Nearest/Nearest Air Defence, **Cancel Task**;
  `scan_forward` was *replaced* by `scan_ahead`, not kept as a synonym. **Watch → Nearest Air
  Defence** (D6) filters on the *believed* classification -- `class`/`type` level resolving into
  the four air-defence `OP_*` buckets -- so a `presence`-level contact is never matched even when
  the object really is a SAM; it will honestly report nothing rather than name an unidentified
  blob as air defence. New ownship-relative `AttentionArea` kind
  (`belief/attention.py`'s `RelativeSector`/`wedge_deg`/`project_relative_area`) that re-projects
  onto ownship's current heading every telemetry tick (`ContactStore.reproject_relative_areas`,
  called from `logger.py`'s `run_once` before `ingest`/`tick`) — a standing "watch left" now tracks
  the nose through a turn instead of freezing to the heading held when the button was pressed (D1-D3).
  **D5 fixes the hollowness this backlog item's live test found**: every `scan_*` token now
  registers a real `belief.tasks.PendingIntent` via `belief.tools.scan_area` *before* firing the live
  effector, wrapped so a failed trigger still leaves the task registered — `cancel_task` (previously
  always "no pending task" in `--crew-text` sessions) is no longer dead. What this milestone did
  **not** do: the spec's `Observ`/`Track` verbs (still blocked — the 9K113 OBSERV OFF control is
  still not identified, BL-6 recorded only 3001/3015; an Investigator pass is needed before that's
  plannable) and the spec's autonomous-behaviour half (weapon filtering, classification-upgrade
  reports, engagement-envelope danger/safe calls, auto-watch-on-engaged, group-as-single-threat,
  mission-lifecycle reset/debriefing — deferred to design against real sortie feedback, same
  reasoning that gates BL-8 on real flights). No live-DCS acceptance in this milestone's own DoD —
  the whole point is to enable the next sortie; that sortie is the acceptance test and feeds the
  autonomous half. Next-milestone impact: none on the BL-x sequence.

- [x] **F10 Watch Nearest reply in contact-report format — done, merged 2026-09-13 (merge
  `a4e8704`, `fix/f10-watch-nearest-readback`).** Live
  2026-09-13 it replied "Watching CONTACT_1."; now `"Watching <unit type>, <clock> o'clock, <range>
  km[ <semantic fact>]."` via `speech.render_watch_nearest_readback` / `_contact_report_text`, no
  spoken id. Typed `watch <id>` readback unchanged.

- [>] **Coalition/IFF for contact reports — deferred, inferred not omniscient.** Raised 2026-09-10:
  the new contact-report format (`belief/speech.py`'s `render_contact_report`) has a
  FRIENDLY/ENEMY/HOSTILE/UNKNOWN slot, always `"UNKNOWN"` for now — no coalition/IFF perception
  channel exists (`perception.association`'s own docstring: "no coalition/IFF filtering"), and
  reading `LoGetWorldObjects`'s real ground-truth coalition straight into `Contact` would violate
  the no-omniscience invariant `percept.py` enforces on purpose. **User decision: when built, infer
  coalition from unit-type vocabulary (which types each side is known to field) and world position
  (whose controlled terrain the contact sits in) — not from DCS truth.** Terrain-control data
  doesn't exist in world-model yet either. Not scoped to a specific BL-x milestone. **Do not start
  without the user's instruction.**

- [>] **Parked: stop consuming DCS's ambient detection at all, own perception end-to-end.** Raised
  2026-09-09 after the PB-1.5 live probe showed DCS's ambient callout is unreadable/late/
  sight-coupled. All four open questions were answered by the user 2026-09-09 (scope channel
  stays — needed for future acquire/lock/fire gameplay, which is why the association-namespace-
  mismatch fix above mattered; suppressing DCS's own radio callout text is low-priority,
  investigate only if resumed; BL-2 is barely affected since it already consumes `Observation`s
  channel-agnostically). What's left, once those deferrals are subtracted, is not architectural:
  reclassify `visibility.py`'s naked-eye filter from "fallback" to "primary mechanism" in the
  docs, and calibrate its tier/range constants against "if the player can see a unit, Petrovich
  should too." Calibration needs live sorties, so it's meant to ride along with a milestone that's
  flying anyway rather than run standalone. **Do not start without the user's instruction.**

- [ ] **Cross-channel contact duplication — continuity maps are per-channel, not shared.** Found
  2026-09-10 during the object-permanence fix's live acceptance: a real civilian bus was tracked as
  two separate contacts, one per channel (naked-eye and scope/HelperAI), because each
  `PerceptionSource` instance keeps its own `object_id → observation_id` continuity map, not a
  shared cross-channel store, even though the underlying DCS `object_id` namespace is global.
  Candidate fix: a shared, cross-channel map (owned where — `belief/`? a new shared perception-layer
  component?). Not investigated or scoped yet.

- [~] **`certainty`/classification fusion is last-writer-wins — classification half resolved by
  BL-2.6, certainty half still open.** `Contact.classification` no longer overwrites on last-write
  (BL-2.6's `fold_classification`). `decay.certainty_of` is still a pure function of
  `now_sim - last_seen_sim` with no notion of which contributing observation had tighter position
  uncertainty or which channel produced it — a tight naked-eye observation followed by a
  wider-uncertainty scope observation still fully resets `certainty` to `"observed"`. Reworking into
  a quality-weighted ladder is a real design question (what "better" means across channels with
  different uncertainty models), not a quick patch — revisit once real sortie data shows it actually
  degrading perceived contact quality.

- [ ] **BL-2.5 overlay clips its last line at 420×200.** Root cause: the dynamic-sizing fix was
  bundled with a since-reverted restyle commit and reverted with it. Candidate fix: re-implement
  dynamic sizing as an independent commit, separate from any cosmetic change.

- [ ] **BL-2.5 overlay has no dismiss affordance.** Moot while the titled window (with its close
  button) is in effect. Would matter again if the borderless restyle is ever revisited.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. Today's channels implicitly assume Petrovich is looking everywhere at once within
  range/FOV gates. Future design: distinct optical modes (peripheral/naked-eye/binoculars/APS-17,
  each its own FOV/acuity/movement-tradeoff), an attention/scan state machine, a scanning loop
  interrupted periodically by a full-area sweep. Would change what feeds `Percept`/`Observation` in
  the first place, upstream of everything BL-2 built — a future perception-layer milestone, likely
  well after BL-4.

## Rejected

- **Persistent omniscient mission-memory store, upstream of perception filtering — REJECTED
  2026-09-10.** A performance angle (avoid DCS LOS queries via a coarse world-model precheck) rested
  on a false premise: `line_of_sight_clear` already samples world-model's *local* elevation grid, not
  a live DCS call. Do not revive without a new concrete trigger. `plans/omniscient-mission-memory/plan.md`
  (never merged) has the proposed pipeline for the record.
