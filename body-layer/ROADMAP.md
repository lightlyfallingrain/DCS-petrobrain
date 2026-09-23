# Body Layer — Roadmap

Petrovich's belief-state process: contacts, attention, perception ingestion, the brain-facing API.
Full architecture/design (scope boundaries, tool-set design, data model, open questions, decisions):
`plans/body-layer/plan.md` — that doc's §6 "Milestones (BL-x)" describes what each milestone below
*is*; this file tracks what's actually *done*. PB-x in the descriptions below cross-references
`docs/concept/PETROBRAIN_RUNTIME.md`'s runtime milestone numbering — BL-x is the body-owned slice
of it. Update this file (not `../todo/todo.md`) whenever a body-layer branch merges — see
`../.claude/skills/merge/SKILL.md`.

**Live acceptance debt.** A milestone can pass DoD on fixture/console testing alone when its plan
scopes live-DCS acceptance out deliberately (a real decision, not debt — e.g. BL-3, the overlay
clock/range summary). This list is for the other kind: a milestone whose live acceptance was
*deferred*, not waived, and hasn't been confirmed since. Added 2026-09-10 after a retro found this
caveat being logged repeatedly (BL-4, BL-5, the continuity fix) without ever being tracked as
accumulating risk. Clear an entry only once a real sortie actually exercises it, and say which one.

- [ ] **Two things waiting on the user's own machines, added 2026-09-19.** Neither blocks work.
  - **The daily status-page launchd job** (`.claude/scripts/com.petrobrain.status-page.plist`) is
    written but **not installed** — installing writes outside the repo. Test with
    `launchctl start com.petrobrain.status-page` and check
    `~/Library/Logs/petrobrain-status-page.log`. The unproven part is whether a headless
    `claude -p` can republish the artifact to the existing URL; everything else is guarded and was
    verified firing.
  - **The sortie.** Five separate entries now clear on one flight — see the list below plus Stage 4b
    speech and the contact-report wording. Flight card:
    `docs/acceptance/2026-09-18-stage6-sortie.md`.

- [x] **BL-4's attention/events tools — CLOSED 2026-09-21 as tested and good enough** (user
  direction). `set_attention`/`watch_area`/`get_attention_state`/`list_events`/`acknowledge_event`.
  Live acceptance had been deferred as "bundled with BL-5's transport layer", and this entry existed
  because it was unclear whether BL-5's own sortie had exercised these tools at all rather than just
  `place`/`position`/`situation`.

  **Closed on the user's judgement from flying it, not on a fresh acceptance run.** That is the
  right call for a debt of this shape: the question was never "is it correct" — the code is tested —
  but "has anyone watched it work", and the person doing the watching has now flown it enough to
  say. Recorded as user judgement rather than as a passed acceptance test so the distinction stays
  visible.

- [x] **F10 command vocabulary — CLOSED 2026-09-21 as tested and good enough** (user direction).
  The 15-token set and relative-sector re-projection, merged 2026-09-16
  (`plans/f10-command-vocabulary/`). First sortie flown 2026-09-16/17, closed after further flying.

  **Confirmed live:** the menu tree is navigable, scans register real tasks, and `Cancel Task`
  genuinely cancels — which it never could before this milestone. Two defects were found and fixed
  (merge `74f0fff`, `fix/scan-naked-eye-not-9k113`): Scan was driving the 9K113 sight instead of
  this project's own naked-eye perception, and `Cancel Task` spoke a raw task id.

  **Some items close unexercised, deliberately — worth saying why that is reasonable rather than a
  shortcut.** The F10 menu is an explicitly temporary surface, with voice as the primary interface
  (user, 2026-09-16: *"It's alright if F10 menu goes stale, we'll remove it at some point"*).
  Proving relative-vs-bearing rotation through a 0/360 wraparound on a path scheduled for deletion
  is effort spent on a deliverable nobody will keep. If that behaviour matters again it will matter
  for voice, which needs its own sortie regardless.

  **Not closed — re-homed, because these outlive the menu:**
  - `F10_SCAN_RADIUS_M` (3000 m) and `DEFAULT_SCAN_DEADLINE_S` are still **uncalibrated
    placeholders**. They are properties of *scanning*, not of the F10 surface, so they belong with
    the cones work and the existing `todo/todo.md` entry — and they stay hard to judge until a scan
    actually steers perception.
  - The scan → naked-eye-perception wiring (`todo/todo.md`, "Scan commands should drive naked-eye
    perception") is a perception item that merely happened to surface through the menu.

  Full original acceptance plan, kept for the record:
  `plans/f10-command-vocabulary/dod-check.md`.

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
  fixed tool surface (`belief/tool_api.py`'s `TOOL_SET: list[ToolSpec]`; twelve at BL-5, 15 once BL-6 added `scan_area`/`get_task_status`/`cancel_task`) a human can hold a
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

- [x] **Vision range calibration (perception-tier, no BL number — the PB-1.5/`visibility.py`
  lineage).** **Done 2026-09-17.** `perception/visibility.py`'s recognition-tier range constants
  are no longer guesses: they are derived from a nine-range screenshot ladder (503 m to 8.89 km,
  one 12-unit complex on flat desert, four optics per range, each range's ground truth taken from
  an F10 ruler frame). Dataset: `body-layer/tests/fixtures/vision_calibration.json`
  (`png-2026-09-17` records). Derivation and full ladder:
  `body-layer/research/2026-09-17-vision-range-calibration-pass2.md`.

  **What changed.** `MEDRES_ANGULAR_RADIUS_RAD` 0.008 → 0.014 (class range for a 7 m vehicle
  3500 m → 2000 m), `HIRES` 0.02 → 0.028 (type 1400 m → 1000 m), `LOWRES` 0.0043 → 0.003
  (presence 6511 m → 9333 m), `NAKED_EYE_RANGE_CAP_M` 5000 → 10000.
  `BINOCULAR_RANGE_MULTIPLIER` stayed at 4.0. The old constants were wrong in **both** directions
  at once — over-claiming classification while under-claiming presence — which is why they read as
  plausible for so long. Note the cap no longer matches `association.RANGE_CAP_M` (5000):
  deliberately decoupled, since one number now has data behind it and the other does not.

  **The result that made a per-optic model unnecessary.** Read as apparent angular size (true
  angular size × magnification), the unaided and binocular columns land on the *same* tier
  thresholds — class at ~0.014 rad from both, agreeing to within 2%. The tiers are properties of
  the eye; the optic only multiplies the angle. So retuning three constants was sufficient, and
  the 2026-09-17 decision to defer the per-optic dimension holds. The 9K113 wide/narrow columns
  are recorded in the fixture as founding evidence for the deferred "attention direction and
  detection cones" item below, which owns that split.

  **Pass 1 (the same day) reached the opposite conclusion and was wrong.** It graded compressed
  JPEGs of a similar scene and concluded class was never resolvable through binoculars at any
  range down to 895 m — recommending `medres`/`hires` be made unreachable. The lossless ladder
  shows class at 1.99 km and type at 1.00 km. The JPEG rows are kept in the fixture as
  `authoritative: false`, with `test_jpeg_set_is_excluded_and_understates` pinning the
  contradiction (a *better* grade at a *longer* range) so nobody folds them back in. Lesson worth
  carrying: for a perception threshold, a lossy screenshot is not conservative evidence, it is
  wrong evidence — the codec is part of the instrument.

  **Still open, deliberately.** `LOWRES` is an upper bound, not a measured boundary — presence was
  still unmistakable at 8.89 km, the farthest range photographed, so a longer ladder would push it
  lower again and `NAKED_EYE_RANGE_CAP_M` remains a sanity bound rather than a measurement.
  Nothing below 503 m, so the unaided type threshold is unmeasured. One condition only (flat
  desert, unobstructed, clear, one theatre/time/altitude band) — contrast, haze, dusk, night and
  cluttered backgrounds are untouched, and `min_contrast_f`/`min_fog_transparency` remain
  unaddressed. Every derivation uses a 7 m armored reference; infantry ranges follow from the
  formula, not from measurement. All targets were static, and movement is a strong real detection
  cue this does not model.

- [~] **Group contacts: cardinality and composition as refinable beliefs.** **Stages 0-4a done
  2026-09-18 on `feature/group-contact-cardinality`; 3b-ii, 4b, 5 and 6 pending.** Plan:
  `plans/group-contact-model/plan.md`. Diagnosis: `plans/contact-merge-undercount/debug.md`.

  **What the model became, after two reworks.** A `Contact` is a belief about the occupants of one
  **resolution cluster**, not one object — and separability is **angular**, measured at ownship in
  3D: two units are separable when the angle between them exceeds half the sum of their own angular
  sizes (the disc-overlap criterion), with an acuity floor. The user's framing that forced this:
  *"two apples 20 cm apart at 50 cm are obviously two side by side, and may be one when one sits
  behind the other"*.

  **Two reworks, and why.** Stage 3b-i rev.1 modelled the uncertainty as a world-space **ellipse**
  (cross-range acuity, down-range bucket width). That was an approximation of the angular reality,
  and it cost a full implement-review cycle before the user restated the problem in its natural
  space. rev.2 replaced it with the angular predicate and **deleted 144 net lines of `src/`** —
  the correction made the code smaller. Before that, the radius itself had been built on half a
  **30 degree clock bucket**, a *reporting* quantisation mistaken for *resolving* power, roughly 50x
  too coarse.

  **Two findings that paid for themselves:**
  - **The optic multiplier cancels out** of the separability test — both sides are angles through
    the same optic. Verified in the code, not just the algebra.
  - **The acuity floor is provably non-binding for anything the channel detected**, since detection
    is itself an angular-size test against the same constant. So the acuity *magnitude* is not
    load-bearing for clustering — which **removed Stage 3b-ii's headline reason to fly**.

  **Behaviour now** (all fixture-verified): twelve units perpendicular to the line of sight at 9 km
  → **12 contacts**; the same twelve *along* it at 200 m AGL → **1 contact, `OP_1UNIT`** — correct
  and confident, he genuinely sees one dot; the same layout at **1000 m AGL → `OP_TO5UNITS`**,
  because climbing widens the depression-angle spread. Altitude-sensitive counting falls out of
  geometry with no tuned parameter, which is the clearest evidence the model is right.

  **Stages:** 0 ✅ presence-tier veto (interim, removed by Stage 2 as designed) · 1 ✅ cardinality
  mechanism (a no-op by merge criterion — 608 pre-existing tests passed untouched) · 2 ✅ clustering,
  which fixed the live defect · 3a ✅ same-source/same-poll exclusion in `ContactStore.ingest`,
  radius-independent · 4a ✅ cardinality observable in `facts`/console · 3b-i ✅ angular separability
  (rev.2) · 3b-ii ⚠ scope now questionable (see below) · **4b ✅ speech and events — merged
  2026-09-19** (feature/group-contact-speech) · **5 ⏸ composition — DEFERRED** · 6 ⛔ hardening.

  **Rule delivered in Stage 4b — Attention earns precision:** A `watch` or `priority` contact with an
  exact cardinality interval (`lo == hi`, no uncertainty) speaks its real count, capped at twelve.
  An inexact interval (`lo ≠ hi`) stays hedged regardless of attention — no manufactured precision.
  Honesty condition: attention buys disclosure of precision already held, never creates precision.

  **Open questions for the next pass, both real rather than rhetorical:**
  - **Does Stage 3b-ii still justify a sortie?** Its headline purpose was pinning the acuity
    magnitude, which rev.2 showed is not load-bearing. What remains is the tier → count-coarseness
    cap and the chaining cap. Consider folding them elsewhere rather than flying for them. **Status
    (2026-09-19):** Still deferred pending F10 vocabulary sortie feedback; user to re-judge.
  - **Is Stage 5 (composition) still worth building?** The angular model resolves the twelve-unit
    case that originally motivated the whole group model, so the headline example has largely
    dissolved. Cardinality retains real uses — along-LOS columns, tight formations, infantry below
    detection size. The user's own instruction was to re-judge this after flying. **Status
    (2026-09-19):** Same sortie (F10 vocabulary + Stage 4b speech live) will exercise whether
    kind separation (tanks vs. BTRs) adds tactical value beyond cardinality alone. DoD's acceptance
    plan documents what to listen for that argues for or against this stage.

  **Stage 5 (composition) is deferred, and may never be built** (user, 2026-09-19: *"Let's at least
  defer stage 5. It may become entirely redundant, but that needs testing first."*). The case for
  it has weakened twice over. The angular model resolved the twelve-unit scenario that motivated the
  whole group model, so the headline example dissolved; and Stage 4b's hedged register plus
  attention-earned counts may already carry what a crew member actually needs to hear. *"Several
  armor, eleven o'clock, two kilometres"* — with an exact count available on anything watched —
  might simply be enough.

  **What would settle it, and it is a listening test rather than an analysis**: fly with 4b and
  notice whether the missing piece is *what they are*. If "several contacts" leaves a real question
  unanswered in the moment, composition earns its build. If the hedge plus a watch mark covers it,
  Stage 5 is redundant and not building it is a saving, not a compromise. Do not start it on
  reasoning alone — the whole point of deferring is that the evidence comes from the air.

  **Deferred, recorded so they are not silently assumed away** (user, 2026-09-18): occlusion (a near
  object hiding a far one on the same line of sight), and shape, colour and movement as
  separability cues. Movement especially is a strong real-world cue this model ignores entirely.

- [ ] **BL-8 — Memory layer interfaces.** Not started, deliberately last (user decision, 2026-09-10:
  "the shape of what's worth remembering is only knowable after BL-2..BL-7 have run for real").
  Standing awareness note while BL-2..BL-7 touch in-mission memory shapes (`Contact`/`ContactStore`,
  BL-4's `AttentionArea` registry): keep BL-8's eventual mission-end export/persistence boundary in
  mind, not as a design constraint yet, just don't shape something in a way that obviously fights it.

- [x] **Cones slice 2C — the o'clock scan loop. DONE, merged 2026-09-22** (`4f89fc8`). The
  default gaze stops being "everywhere" and becomes a scan: 12, then 11/10/9, then 12 again, then
  1/2/3 — 30° cones, two seconds each, a 16-second cycle that covers the forward arc twice. The
  numbers are the user's (*"scan per o'clock cone"*, 2 s per sector), not fitted.

  **`gaze_at(t_sim, plan)` is a pure function of sim time**, so replay determinism falls out of
  purity rather than being managed — nothing holds a scan phase that could drift from the clock.
  Two consequences followed rather than being designed: `decay.OBSERVED_WINDOW_S` moved 5.0 → 16.0,
  derived from the cycle and bounded on both sides, and acquisition state became time-based,
  because poll-indexed sets break the moment the cone moves.

  **Two fixes rode in from the sortie that followed, and both came from the pilot flying it.**

  - **The overlay now names the cone he is looking at.** Two of the test card's four blocks were
    unevaluable without it — *"very difficult to judge when I don't visually see where Petrovich is
    looking"*. A perception model that steers attention is invisible from the cockpit unless it
    says where it is pointed.
  - **Scan and Watch became standing modes rather than one-shot tasks.** `tasks.py` marked a task
    succeeded on first contact and `_active_gaze` honoured only pending tasks, so a commanded scan
    silently reverted to free scan the moment it found anything — which is why *"scan left"* still
    produced 12 o'clock reports. The same assumption sat in three places, so fixing only
    `_active_gaze` would have left cancel hollow.

  **Left open at merge and closed afterwards:** `watch_nearest` created no `PendingIntent` at all,
  so `Cancel Task` had nothing to find regardless of the above. Fixed in `32346a0` (watch as a
  standing mode), where cancel now ends every governing kind and names each.

- [x] **Cones slice 2B — gaze as a filter. DONE, merged 2026-09-21.** `perception/gaze.py`;
  `check_visibility` evaluates a gaze first in the gate chain; `Optic.peripheral` and the bypass
  rule; **F10 scan commands finally steer naked-eye perception** rather than only registering an
  attention area.

  **Behaviour-preserving by construction** — nothing observable changed by default, which is the
  point. Achieving that required deviating from the plan: it specified `FULL_GAZE` (±90°) as the
  default and called it a no-op, but `cockpit_mask.py`'s measured envelope reaches ±130°, so that
  would have silently narrowed detection through the 90–130° band. The default is `None`
  (plan corrected in `e520e8b`).

  **Live-acceptance debt, deferred not waived:** a commanded scan is testable today but reads
  properly only against free-scan gaze, so it clears on 2C's sortie.

  **Standing exposure until the capture channel exists:** `Optic.peripheral` is wired with no
  triggers — nothing generates a peripheral stimulus, because there is no behaviour-change channel.
  From 2C onward, nothing outside the focus cone captures attention.

- [x] **Cones slice 2A + 2A.5 — DONE, merged 2026-09-21.** The first two sub-slices of the
  detection-cones slice 2 milestone (`plans/detection-cones-slice2/plan.md`).

  **2A** (`7d82018`): an `Optic` carries per-tier range multipliers instead of one magnification
  (unaided 1/1/1, binocular 2.42/3.50/3.00, BTR-60-derived); `distinctiveness` as a per-`op_class`
  default plus per-type exception; and the clamp `class = min(presence, …)` making
  `type ≤ class ≤ presence` structural. It reproduces the measurement it was built from — infantry
  class collapses onto presence at every optic, the 1.00 ratio observed at all four instruments.
  Also fixed `clustering.py`'s acuity floor, recorded benign by two prior reviews: its slackness
  proof holds only while the active optic's presence multiplier is ≤ 4.0, and the 9K113 narrow's
  5.81 expired that premise silently.

  **2A.5** (`a06f1e8`): the naked-eye intake cap counts **groups**, not objects — ten trucks in one
  glance is one perceptual event, the same ten spread across a sector is ten. `clustering.py`
  already computed that distinction; only acting on it was missing. Fixed a real defect on the way:
  a capped-out group was dropped permanently rather than retried.

  **What these deliver is the model's shape, not calibrated numbers** — and the acceptance position
  says so rather than overstating. Infantry binocular computes 1452 m against an observed 2.0 km.
  Four `xfail`s carry that gap visibly: 2A moved the binocular presence multiplier to 2.42 while
  `LOWRES_ANGULAR_RADIUS_RAD` still encodes the flat 4.0 it was derived against. They are a
  tripwire — if recalibration happens and they do not turn green, the recalibration was wrong.

  **Next: 2B** (gaze as a filter; F10 scans finally steer perception), behaviour-preserving by
  construction. Then 2C (the o'clock scan loop) and conditionally 2D.

- [x] **Aspect-aware object profiles — DONE, merged 2026-09-21** (`3f624d9`, branch
  `feature/aspect-aware-profiles`). `ObjectTypeProfile` gains optional length/width/height;
  `apparent_extent_m` gives `max(L·|sinθ|+W·|cosθ|, height)`. **Aspect drives recognition
  (`MEDRES`/`HIRES`) only — detection keeps the aspect-invariant `size_m`**, because a BTR-60 seen
  through four instruments showed presence identical at every aspect while class and type moved
  1.33×–2.31× (`body-layer/research/2026-09-21-aspect-magnification-and-distinctiveness.md`).

  Fixes the tall-mast bug: the S-300 40B6M's presence range went from 1665 m to 8000 m against an
  observed 6700 m, on an independently sourced 24 m mast height. Only the two S-300 rows carry real
  dimensions; the other ~148 are untouched and unaffected.

  **Threshold recalibration remains deferred, now for a third reason.** Class is short for radars
  while too generous for vehicles, which no single threshold pair resolves. The missing term is
  silhouette distinctiveness, measured this session: infantry classifies at *exactly* its detection
  range at all four instruments, while a BTR-60 needs 7.75× closer. That is a model-shape change,
  not a constant.

- [x] **BL-9 — Debug visualization. DONE, merged 2026-09-20** (`1553eb9`, branch
  `feature/bl9-detection-trace`). `--detection-trace` flag, `DetectionTraceWriter` (a read-only join
  between `LoGetWorldObjects` ground truth and belief state), and a post-flight reducer.
  **Merged immediately after cones slice 1 (`ce9baea`) so one sortie serves both** — that slice's
  deferred detection-range question and BL-9's own acceptance.

  **The merge itself found two defects neither branch's tests could see**, which is worth recording
  because both were invisible by construction: each branch was correct alone. The trace computed its
  `range_threshold_m` with `BINOCULAR_RANGE_MULTIPLIER` hardcoded, so once the naked eye became the
  default optic every trace row would have reported a threshold 4x larger than the gate applied —
  the instrument misreporting precisely the quantity it exists to measure. And the new field-of-view
  gate returned without recording, which would have started dropping trace entries as soon as slice
  2 made a non-default optic selectable. Full detail in the merge commit.

  Original entry, kept for its reasoning (user, 2026-09-20: do it after inbound-speech Stage 3). Belief-vs-DCS-truth debug view. Its own entry already allowed for this — "arguably worth
  pulling earlier if BL-2/BL-3 turn out hard to reason about textually" — and the reason it moved is
  stronger than legibility: it multiplies what a single sortie is worth.

  Detection-range calibration has never been flown, and the loop above means the next sortie has to
  serve calibration, the five outstanding acceptance debts, and BL-8's "run for real" gate at once.
  Without this, calibration data is a pilot's recollection of roughly when a callout happened. With
  it, it is what Petrovich believed next to what was actually there. Same flight, very different
  evidence.

- [~] **BL-10 — audio transport wiring (= PB-7 + PB-8, body's half only).** **First slice done
  2026-09-17 (outbound TTS, `plans/tts-voice-output/`); the rest not started.** Swaps BL-5a's
  typed/printed stand-ins for the real audio adapter. The adapter itself (SRS client, ICS channel,
  PTT debounce, silence gate, STT, TTS) is not body-layer work — it now lives in its own
  `audio-adapter/` sibling subproject (see `audio-adapter/ROADMAP.md` for that subproject's own
  milestone status).

  **Slice 1 — outbound TTS (stages 1-4 merged; 5-6 pending hardware).** Petrovich's already-
  generated text is synthesized on the Mac and played as audio. Body-layer's share came to exactly
  one optional field, `CrewConsole.speech_client`, read by the same `_print` funnel `overlay_client`
  already uses, plus `logger.py --speech-audio --audio-adapter-url`. **That smallness is the
  milestone's own stated test of BL-5a, and BL-5a passed it** — the plan said "body changes here
  should be small; if they are not, BL-5a's interface was drawn in the wrong place."
  `audio-adapter` owns synthesis (`TTSEngine` protocol + `MacSayEngine`) and delivery
  (`--target local` plays on the Mac via `afplay`, needing neither Windows nor DCS;
  `--target aircraft-layer` POSTs WAV bytes to the collector's new `POST /audio/play`, played
  there by `AudioPlaybackSender` — FIFO for routine lines, urgent lines clear the queue and
  interrupt in-flight playback). Still unverified, needs the user's hardware: `winsound` playback
  on Windows and the urgent-interrupt mechanism (stage 5, no DCS needed), then latency and voice
  acceptability on a real sortie (stage 6).

  **Slice 2 — SRS ICS injection (next, not started).** `DCS-SR-ExternalAudio.exe --modulations
  INTERCOM --unitId <player unit id>` as a second `AudioSink` inside `audio-adapter`. The recon
  (`audio-adapter/research/2026-09-17-tts-audio-transport-recon.md`, read its two addenda) confirmed
  stock SRS declares an Intercom radio for the Mi-24P at 100.0 MHz modulation 2, and that
  `--unitId` exists specifically to allow intercom over external audio. **ICS is the only
  acceptable target** (user constraint, 2026-09-17): the player must stay on the mission frequency
  and the SPU-8 selects one source at a time, so a dedicated Petrovich frequency would compete with
  mission comms rather than layer under them. If the live ICS test fails, this slice *stops* — it
  does not degrade to a radio frequency, and slice 1's local playback is what ships. One unsolved
  prerequisite: discovering the player's DCS unit ID at runtime (`--unitId` defaults to 1000);
  likely already available via the aircraft layer's `LoGetWorldObjects`/`is_ownship` path, unverified.

  **Slice 3 — inbound speech (STT/PTT), not started.** The half that consumes `PlayerUtterance`
  records from real speech rather than typed input.

  **Also owns the rich command vocabulary** (user direction 2026-09-16): the F10 radio menu is
  deliberately capped at the simple fixed set `f10-command-vocabulary` built, and everything the
  command half of `docs/concept/state-transitions.jpg` asks for beyond it — `watch <unit>
  <where>` against a live contact list, waypoint/landmark-anchored scans, the
  `o'clock-and-distance` location form — is audio-adapter's, not F10's. Those are *rejected* for the radio
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

  **Risk closed 2026-09-17:** the bank sign convention was the riskiest open assumption here —
  inverted, it would have failed *dangerous* rather than fail-safe, silently swapping which side
  Petrovich gains visibility on in a turn, with no unit test able to catch it (they all check the
  code's own convention against itself). The user confirmed against DCS: **right bank positive,
  left negative** — the standard convention the implementation assumed. Verified the code behaves
  accordingly, not merely that it matches a docstring: a right-abeam contact 18.4° below is blocked
  level, rises to 11.6° *above* boresight under +30° bank, and buries further under −30°. Pitch confirmed
  the same day ("down is negative, up positive"), also matching — and consistent with that parked
  sample reading +2.76°. Both signs are now observed rather than assumed.

  Follow-up (`fix/pin-bank-sign-convention`): the gate-level bank test used a contact *directly
  below*, which rotates to azimuth ±90 under either sign — and `is_visible` folds azimuth through
  `abs()` — so it passed identically inverted. Added an asymmetric right-abeam case that fails
  under a sign flip (mutation-verified). The rotation-level geometry test already pinned the sign.
  See `plans/cockpit-visibility/` (plan, review, dod-check, implementation).

- [x] **Group detectability — presence split into resolution vs. salience.** The dots-off ladder
  and the single-unit sortie only looked contradictory because one constant (`LOWRES_ANGULAR_
  RADIUS_RAD`) was answering two questions: can the eye register a mark at all (resolution), and
  would a lone mark be noticed while scanning (salience). Split into two: `RESOLUTION_ANGULAR_
  RADIUS_RAD` (0.00128, looser) alongside the unchanged `LOWRES_ANGULAR_RADIUS_RAD` (salience). A
  member of a cohesive, resolvable group of at least `GROUP_MIN_MEMBERS` (3, stated assumption) is
  admitted at the looser resolution threshold instead of the tighter salience one — the group
  supplies the salience a lone dot at that range does not have. New `perception/group_salience.py`
  (pure, no state, single-link union-find over `GROUP_COHESION_GAP_UNIT_WIDTHS`, 10.0, stated
  assumption), wired into `naked_eye_source.poll` once per poll ahead of the per-candidate
  `check_visibility` loop. `clustering.py`'s floor (A) — the constant's own correctness condition —
  now points at `RESOLUTION_ANGULAR_RADIUS_RAD`, the loosest threshold any admission path can use,
  not `LOWRES_ANGULAR_RADIUS_RAD`: a group-admitted candidate could otherwise satisfy (A) at
  `RESOLUTION` while failing it at `LOWRES`, silently merging two genuinely separable contacts —
  the third time this floor has needed attention.

  **The model predicts a rung it wasn't fitted to.** Infantry's group-admitted ceiling
  (`1.8 / 0.00128 = 1406 m`) sits below the 1.91 km rung where the pilot reports "detection + unit
  count (no infantry)" on the same twelve-unit complex — infantry isn't rescued by its conspicuous
  neighbours because it isn't *resolvable* at that range, exactly what the ladder shows. Checked
  directly in `test_vision_calibration.py`, not just asserted.

  **A real discrepancy the 5.44 km rung's own test found — and fixed in this same feature.** The
  plan specified `RESOLUTION_ANGULAR_RADIUS_RAD = 0.0013`, which is `7 / 5440 = 0.0012868` rounded
  *up* — the opposite direction from `LOWRES_ANGULAR_RADIUS_RAD`'s own precedent of rounding down so
  the calibration point it derives from stays admitted. That put the boundary at 5384.6 m, ~55 m
  short of the photographed 5440 m rung the plan's own prose calls "admitted (marginal)"; the plan's
  worked table already showed the contradiction (`"5385 m"` against a `"5.44 km"` rung).

  **Corrected to `0.00128`**, boundary 5469 m, and the rung clears. The principle is the reason: a
  threshold derived from an observation must admit that observation, or the derivation cannot be
  reproduced from the data it cites. Three tests had been written to *document* the wrong-way value
  and now assert the property instead.

  **`LOWRES_ANGULAR_RADIUS_RAD` deliberately not recalibrated** — it stays conservatively short for
  lone units (2333 m vs. 2.8–3.1 km observed) so the next sortie validates the group term uncoupled
  from a threshold change; fitting the group's reach into a per-unit constant would silently
  re-merge the two questions this work just separated. Counting/individuation on newly-admitted
  distant groups will over-claim (angularly-separable-but-not-salient dots each report as their own
  singleton cluster) — a stated, accepted assumption, not fixed here (would need a new
  `belief.cardinality` uncertainty state).

  See `plans/group-detectability/plan.md`.

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
  surface that BL-10's audio transport can follow.

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

- [~] **Movement detection — design settled 2026-09-20 (user), implemented 2026-09-22
  (`plans/movement-detection/plan.md`), pending live acceptance.** The velocity transport
  (`petrobrain-mission-telemetry-hook.lua` + `GET /unit_velocity/latest`), the apparent-angular-rate
  gate (`perception/motion.py`), the belief fold and event (`belief/motion.py`,
  `CONTACT_MOTION_CHANGED`), and the reporting surface (`get_situation`'s `facts["motion"]`, one
  trimmable clause in contact-report speech) are all built and unit/fixture-tested — 887 passing
  before this work, 929 after, 0 regressions. Stage 0 part 3's Mac-answerable benchmark measured
  parse->join->gate at N=300 units at ~1 ms, confirming the plan's expectation that this cost is
  irrelevant next to `check_visibility`'s own. **Not yet flown**: Stage 0 parts 1-2's own
  self-measurement (the Hook's `os.clock()`/`dcs.log` unit_count/bridge_call_ms pair, and the
  `timer.getTime()`/`LoGetModelTime()` clock-identity assumption Decision 3's skew bound depends on)
  only answer themselves on a live sortie. The diagram
  (`docs/concept/STATE_TRANSITIONS.md`) lists `moving / stopped` as a reporting trigger, and
  `docs/concept/threat-levels.md` uses motion as a danger criterion. Nothing in the built event set
  can produce either. The user's design, recorded here so it is not re-derived:

  **Take the velocity vector from unit data rather than differencing observed bearings.** This is
  deliberately omniscient at the source and the user accepts that trade for the compute it saves —
  differencing angular positions across frames means retaining history per candidate and eating the
  noise. **The omniscience is then removed by the gate, not by the source**, which is the shape this
  project already uses elsewhere: truth in, perception-limited out.

  **The gate is apparent angular change over a short interval.** For velocity `v` over time `t` the
  unit travels `s = v·t`; the angular change seen from ownship is the component of `s` perpendicular
  to the line of sight, divided by range. Movement is detected only when that exceeds a perceptual
  threshold.

  **Cheap early-out first, and cheaper than it looks.** Since `|v⊥| ≤ |v|`, the test
  `|v|·t / range < threshold` rejects a candidate with no perpendicular component and no
  trigonometry at all — one multiply and one compare. Most candidates die here.

  **Use the unit's own velocity, not its velocity relative to ownship.** A stationary truck seen
  from a moving helicopter sweeps across the field of view but does not *look* like it is moving,
  because it is static against its background; humans discount self-motion through optic flow. So
  absolute velocity is correct for ground units against terrain. The exception is anything seen
  against empty sky, where there is no static background to be judged against — the same case as the
  next paragraph.

  **The model reproduces a real human failure mode for free, and this is a feature.** A unit on a
  constant-bearing collision course produces zero angular change, so it reads as "no movement" —
  precisely the general-aviation blind spot where an aircraft on an intercept course is hard to
  see because the eye perceives no motion (user's own example). No special-casing required; it
  falls out of the geometry. **Do not "fix" it.**

  **Two further perceptual inputs the user named**, not yet designed: higher speed grabs attention
  automatically rather than merely being detectable, and **lights and flashes** do the same —
  aircraft strobes, tracers, explosions, flares. Those are an attention-capture channel, closer to
  BL-4's attention machinery than to this gate.

  **The perceptual threshold: 8 arcmin/sec (≈0.133 °/s), over a ~1 s window.** Derived on user
  direction (2026-09-20) as **2 arcmin/sec lab baseline × 4 for the cockpit**. Human smooth-motion
  detection runs about 1–2 arcmin/sec in laboratory conditions; 2 is taken as the baseline because a
  *higher* threshold means motion is *harder* to detect, so it is the conservative end. The ×4
  covers three effects that stack and that lab conditions exclude by design: canopy vibration
  smearing the image, **scanning rather than fixating**, and divided attention — a lab subject
  stares at a known location, which is the opposite of what a scanning crewman does.

  Same debt class as `BINOCULAR_OPTIC`'s ~0.67 stabilisation penalty: **the factor is not measured,
  but it is named, isolated and measurable**, rather than buried inside the threshold as a single
  unexplained number. A sortie can measure it later; until then it can be moved in one place.

  Sanity-checked against three cases before adoption, which is what makes it credible rather than
  merely arithmetic:

  | Case | Angular rate | Detected |
  |---|---|---|
  | Truck 10 m/s crossing at 2 km | 17 arcmin/s | yes |
  | Truck 5 m/s crossing at 5 km | 3.4 arcmin/s | **no** |
  | Jet 200 m/s crossing at 5 km | 137 arcmin/s | yes, easily |

  The middle row is the one that argues for the number: a slow truck at 5 km genuinely does not read
  as moving at a glance, and a threshold that flagged it would be modelling a machine, not a crewman.

  **Velocity source — resolved, and the bridge to it was already shipping (2026-09-22).**

  `Object.getVelocity()` in the Mission Scripting environment is reachable **today**, through
  machinery this project already deploys: `petrobrain-f10-commands-hook.lua` has used
  `net.dostring_in("scripting", …)` since 2026-09-13, polling at 1 Hz, and the user has flown and
  accepted it. **The "gated on probing that bridge" condition below is already satisfied**, and the
  differencing fallback — with its per-`object_id` position history, poll-interval sensitivity and
  load-bearing id continuity — is not needed. What remains unknown is the per-call cost at the rate
  movement detection would need: a performance question, not a feasibility one. The same bridge
  reaches fog, so the weather half of detection conditions is unblocked with it.
  See `aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md`, which also records
  why the false "unprobed" claim propagated into four places before anyone grepped for it.

  Original entry follows, still correct about *where* velocity lives.

  **Velocity source — resolved 2026-09-21, and not where the design assumed.**

  `LoGetWorldObjects` carries **no velocity**, under any name. Its complete per-object field set is
  `Pitch, Bank, Heading, Type, Country, Coalition(ID), GroupName, Name, UnitName, Position,
  PositionAsMatrix, LatLongAlt, Flags` — a full `pairs()` enumeration listing a dozen fields this
  project never requests, so no synonym could have hidden.
  (`LoGetLockedTargetInformation` does return a velocity vector, but only for a locked target.)

  **But `Object.getVelocity()` in the Mission Scripting environment returns a vec3 for every unit**,
  which is how Tacview records speed for everything on the map
  (`aircraft-layer/research/2026-09-21-unit-velocity-via-mission-scripting.md`). Reaching it costs
  the mission-sandbox bridge — and that bridge **also** gates the fog half of "detection under real
  world conditions", so one probe unblocks both. Filed in `todo/todo.md`.

  So there are two routes, and the design should not be fixed until the bridge is probed:

  - **Via the bridge** — an exact `v⊥` per unit. Simpler *and* more accurate: no differencing, no
    accumulated sampling noise, no per-candidate history.
  - **By differencing in the collector** — the fallback, with three concrete consequences: the
    collector must hold a previous position per `object_id`; the computed rate is sensitive to the
    poll interval; and **`object_id` continuity across polls becomes load-bearing for movement** in
    a way it is not for position.

  Note that no screenshot ladder can ever supply the perceptual threshold the way it supplied the
  detection-range constants: a still frame cannot show motion, so that constant's only calibration
  path is a purpose-built sortie.

- [>] **Threat-based report prioritisation (`docs/concept/threat-levels.md`) — spec exists, mostly
  gated.** The user's own table: five priority bands (urgent / high / medium / low / ignore), what
  each does to reporting, and what counts as "dangerous to us". Raised 2026-09-20 asking where it
  fits; the answer is that it is **not one milestone** — it decomposes by what each row needs, and
  most rows are behind gates.

  **The dominant gate is coalition.** Roughly 15 of the 24 rows key on friendly/enemy/neutral/
  unknown, so they are downstream of the Coalition/IFF item below — which is itself deferred and
  needs terrain-control data `world-model` does not have. Today every contact is `UNKNOWN`, which
  collapses the table to its one unknown row.

  What the other rows need, none of which exists: unit **engagement envelopes** and "capable of
  firing at us" (also in the STATE_TRANSITIONS autonomous-behaviour backlog, with its 1.5 factor); a
  **behaviour-change channel** for "tracking us"/"engaging us" (there is none — the built event set
  is lifecycle, classification and cardinality); **terrain control** for the friendly-terrain /
  frontline / enemy-territory rows; **Mission Interpreter** output for "mission target" and escort
  targets; and a real **weapon detector** for the aimed-at-us rows, where `UrgentCall` already
  provides the mechanism and `!inject-urgent` is still the only trigger.

  **The buildable slice, and the recommended entry point: the bands themselves.** Urgent interrupts,
  high reports first, low gets the coarse form the spec writes out ("friendly ground 10 o'clock"),
  ignore is silent. This extends BL-7's relevance scoring with a band output and gives
  `belief/speech.py` a coarse rendering path. Every contact would band as `medium` today — which
  sounds useless and is not: it builds the machinery so each row lights up as its own input lands,
  rather than arriving later as one large blocked milestone with a dozen prerequisites.

  **No-omniscience constraint — corrected 2026-09-20 by the user, and the correction matters.** An
  earlier version of this entry claimed that "unit well outside its engagement envelope" and "not
  tracking self/flight" require knowing things Petrovich cannot perceive. **Both were wrong**, for
  two different reasons worth keeping distinct:

  - **An engagement envelope is knowledge, not perception.** A crewman knows what a Shilka can
    reach; it is doctrine held in the head, not a fact sensed about the particular unit. The error
    was conflating "cannot perceive X" with "cannot know X" — only the first is an omniscience
    problem, and envelopes are the second.
  - **"Tracking us" is observable.** Guns or a radar dish slewed onto you is a visible fact at
    usable range, and radar lock is a real signal. (Simplification, user: only the pilot has RWR and
    it is poor, but model it as radar lock rather than building an RWR fidelity model.)

  What survives is narrower and still binding: **envelope knowledge is keyed on unit type, so it
  inherits the classification tier.** A contact held only as `lowres` presence has no type, so there
  is nothing to look the envelope up *for*, and it cannot band above unknown/medium. The band must
  be computed from **believed** classification and carry that belief's uncertainty. Computed from
  ground truth instead, it would be an omniscience backdoor wearing a prioritisation label — and an
  invisible one, since the output would merely be unaccountably well prioritised.

  **Open question for an Investigator pass** before the tracking-us rows are built: is turret or
  dish azimuth actually exportable from DCS? `LoGetWorldObjects` gives position and heading; whether
  a unit's *turret* bearing is reachable at all is unverified, and the rule depends on it.

  Also connects to two things already recorded: "urgent units must receive automatic tracking
  status" is the auto-watch-on-engaged rule in the STATE_TRANSITIONS autonomous half, and the
  group rule ("use the highest-capability threat to determine reporting") is the threat-based member
  selection that `clustering.py` deliberately does not do.

  **Do not start without the user's instruction**, same posture as the coalition item it depends on.

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

- [ ] **Contact report fine tuning — a running list, appended to as real sorties surface things.**
  Opened 2026-09-18 from the first flights with TTS live. These are about what Petrovich *says* and
  how it sounds, not about what he believes; most touch `belief/speech.py` and
  `belief/enrichment.py` only. Grouped by what they cost.

  **Cheap — wording, in `speech.py`. ✅ All shipped 2026-09-19 (`9035317`).**
  - **Spell units out.** "m" and "km" must become "meters" and "kilometers"; TTS does not handle the
    shorthands. Note `_format_range_km` and `_round_enrichment_fragment` both currently emit them.
  - **Acronyms need spacing or expansion.** TTS reads a designation as one token. Wanted: "M I 8".
    **"SAM" is the exception** — a well-known word TTS already says correctly, so this is a
    per-token table, not a blanket rule. *Shipped: the table applies only at `type` level, and
    "SAM" is a `class`-level word, so it is structurally out of reach rather than protected by an
    exception entry. Two of this bullet's original examples were wrong and were corrected during
    implementation: "LR" occurs nowhere in the vocabulary (checked the class table and all reporting
    names) and was left out rather than given an invented use; the real string is "Mi-8", mixed
    case.*
  - **"very close" under 0.5 km.** Replaces a bare range figure at the distance where the exact
    number stops mattering and the fact of proximity starts to.

  **Cheap — thresholds, in `enrichment.py`. ✅ Shipped 2026-09-19 (`9035317`).**
  - **Within 10 m of a feature → "on the road"** (and the same for any feature reference, not just
    roads). *User correction 2026-09-19: originally written as "0 m", which a first pass read
    literally with a float-noise epsilon, leaving a 0.5-10 m gap that rendered as "near a road
    (~4 metres)". Within ten metres you are on it, and no eye resolves the difference.*
  - **Between ~10 m and ~100 m → "next to the road"**, with the side named. *Shipped without the
    side, which needs the bearing below. Note a deliberate gap: 0.5-10 m still renders as
    "near X (Nm)", disclosed in the code rather than silently rounded into one of the neighbours.*
  - These replace the current "near X (~200m)" shape entirely at short distances. The existing
    1000 m `NEAR_FACT_RADIUS_M` gate stays above them.

  **Needs world-model support — the one expensive item:**
  - **"200 meters north of the road"** and **"next to the road, north side"** both need the
    *direction from the feature to the contact*. `query.describe.RoadInfo` carries `distance_m` and
    `orientation_deg` (the road's own heading) but **no such bearing**, and neither do
    `SettlementInfo` or `WaterInfo`. So this is a `describe_position` change in world-model, not a
    phrasing change in body-layer. Given a bearing *and* the road's existing `orientation_deg`,
    "which side" falls out; without the bearing, neither does. Sequence this before the two wording
    items that depend on it rather than half-building them.

  **Deferred (user, 2026-09-19):**
  - [>] **Airborne contacts should be called "aircraft" or "helicopter"**, refining to
    fighter/bomber/attack/transport. Check what actually exists before scoping: whether the
    perception channel can tell a contact is airborne at all (candidate altitude versus terrain
    elevation is available to the naked-eye channel, but nothing currently reads it that way), and
    whether `object_model`'s `OP_*` vocabulary has air classes or needs them. This is plausibly a
    classification change rather than a speech one, which would put it outside this item.

- [ ] **Petrovich's voice has no character — generic English TTS, and monotonous with it.** Deferred deliberately at
  BL-10 slice 1 (`plans/tts-voice-output/plan.md` Decision 7) rather than forgotten. macOS `say`
  ships no Russian-accented English voice (`Milena` is Russian-*language*, a different thing), and
  solving it would have expanded a slice whose point was "audible at all". Options when picked up:
  a different local engine with a suitable voice, a trained/cloned voice, or accepting a generic
  one permanently. **Delivery is a separate problem from accent** (user, 2026-09-18, on first
  hearing it): the voice is flat and evenly stressed whether it is reading a routine contact
  report or an urgent break call. Prosody may matter more for believability than the accent does,
  and it has different fixes — SSML, per-line rate and pitch, or urgency-aware templates. Cheap to try in isolation — `audio-adapter --target local --voice <name>` plays a
  line on the Mac with nothing else running, so voice auditioning costs one command per candidate.

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

- **Detection under real world conditions — weather, light, vegetation.** Raised by the user
  2026-09-19, not started, no milestone assigned. **The framing matters more than the list:** every
  detection test so far has been flown in near-perfect visual conditions, which makes the current
  calibration *an upper bound on what is possible*, not a model of what usually happens. Conditions
  do not replace it; they multiply down from it.

  That gives the work the same shape as the optics split the detection-cones milestone owns, and
  the two compose cleanly rather than competing: **optics multiply apparent size up, conditions
  multiply detectability down, and the three calibrated angular thresholds stay fixed in the
  middle.** Neither needs a new acuity ladder. This is worth stating before anyone starts, because
  the obvious alternative — a separate detection model per condition — would throw away a
  calibration that cost a screenshot campaign and one invalidated merge.

  Four factors, in the order their cost-to-value argues for:

  1. **Vegetation and terrain cover — cheapest by a wide margin, because the data is already
     here.** Forest and other vegetation make ground detection hard and often impossible. World-model
     already resolves landcover (`forest`/`orchard`/`scrubland`/`open fields`/`barren`) and it
     already reaches body through `belief/enrichment.py`'s `inside_landcover` — it simply is not
     wired to `perception/visibility.py`. Nothing new has to be extracted from DCS. Note the
     asymmetry this introduces: a contact *in* forest is hard to see, and a contact *against* forest
     is a different problem again (contrast, factor 4).

     **Update 2026-09-20 — ED already does this, and decomposes it better than the sketch above.**
     `Scripts/AI/Detection.lua` sets `trees_LOS_test_T4 = true`, and all five installed theatres
     (Syria included) are Terrain-4, so **ED's AI detection samples tree geometry for line of
     sight**; our `line_of_sight_clear` samples the bare terrain mesh only, making us strictly more
     permissive through forest than the engine. Separately `background_factors[FOREST] = 0.3`, but
     the file states in capitals that background applies to **airborne targets only** — so ED models
     "hard to see an aircraft against trees" and deliberately does *not* model "hard to see a tank
     against trees" as a contrast effect. That resolves the asymmetry this bullet anticipated: the
     two halves are an **LOS term and a background term**, they apply to different target classes,
     and only the first one touches ground units.
  2. **Light level — dawn, day, dusk, night.** The user: *"light/dark/dusk matters immensely."*
     Mission time and sun elevation are the inputs; the effect is large and non-linear, and dusk is
     the interesting case rather than full night, because full night is nearly a binary. Needs a
     decision on whether Petrovich has any low-light aid at all.

     **Update 2026-09-20 — the inputs need no new channel.** `Export.lua` ships
     `LoGetMissionStartTime()` and `LoGetModelTime()` (both documented in the installed file), so
     time of day is already reachable on the existing telemetry path. With the mission date (the
     Mission Interpreter already parses it from the `.miz`) and ownship lat/long (already in
     telemetry), sun elevation is ordinary astronomy computed locally — **no Hook, no
     `net.dostring_in`, no new transport.** That makes this factor materially cheaper than factor 3
     and fully independent of it, which was not true when the four were first ordered.
  3. **Weather — visibility, fog, precipitation, cloud.** ~~**Needs an investigator pass
     first**~~ — **the pass is done (2026-09-19 desk, 2026-09-20 install).** `Export.lua` exposes
     **no** weather getter beyond `LoGetVectorWindVelocity` and `LoGetBasicAtmospherePressure`;
     fog is confirmed absent from that channel, so the Hook -> mission-sandbox bridge is the only
     candidate route and its reachability is still unprobed. ED's own fog is a **time series**
     (`fog2.manual = {{time, visibility, thickness}, ...}`), not a constant, so anything built here
     must sample rather than read once. Do not plan against assumed fields.

     There is prior art to read before inventing a curve, and 2026-09-20 made it concrete:
     `min_contrast_f` and `min_fog_transparency` are **Mi-24P HelperAI's own thresholds applied on
     top of the engine detector's outputs** (`wDetector::getContrastFactor`,
     `getMaxVisibilityDistWithFog`), while the engine's own fog term is
     `atmosphere_transparency_factor.fog_transparency_threshold = 0.085` in `Detection.lua`.
     `perception/visibility.py`'s docstring names the first two as deliberately unaddressed here.
  4. **Colour separation and camouflage — explicitly deferred by the user.** It is why units are
     painted the way they are, and it is the factor that interacts with all three above rather than
     standing alone. Do not start it with the others.

  **Do not start any of this without the user's instruction** — the note exists so that detection
  logic written between now and then leaves room for a conditions modifier instead of hard-coding a
  clear-day assumption, not as a call to build it.

- **PREREQUISITE for the detection-cones milestone: research ED's own detection and identification
  model.** Raised by the user 2026-09-19: *"ED native model should be researched in detail for
  detection and identification logic. What is there that we have not thought of, what is there that
  we are missing?"* Started as a desk pass from the Mac (forums, Hoggit, the existing
  `world-model/data/raw/dcs/2026-09-02/DCS-files.txt` listing); **the deep pass happens on the
  Windows box**, where the installed DCS tree can actually be read rather than inferred.

  **It gates the cones milestone's *later* slices rather than the whole thing** (narrowed
  2026-09-20, see the interdependence note below). The questions it answers are about dwell, scan
  pattern and range uncertainty — none of which slice 1 builds — so slice 1 can proceed without it
  and the deep read is needed before slice 2. Two of the questions it answers would change that
  milestone's design rather than its details:

  - Whether ED separates *detected / visible / type known / **distance known*** as distinct states.
    If it does, that is a near-exact analogue of our own PRESENCE → CLASS → TYPE lattice, and the
    fourth flag speaks directly to the range-uncertainty work the cones milestone owns — ED may
    already model the thing being deferred.
  - Whether ED models sensor field of view, scan pattern or dwell. That is the cones milestone's
    central mechanism, and the one part with no precedent anywhere in this codebase.

  **Desk pass done 2026-09-19** —
  `aircraft-layer/research/2026-09-19-ed-native-detection-identification-gap-analysis.md`. Four
  results worth carrying forward:

  - ~~**The movement suspicion was wrong, and that is useful.**~~ **THIS BULLET WAS ITSELF WRONG —
    corrected 2026-09-20 from the installed tree.** It said *"neither ED nor we model movement or
    dwell."* ED models both. `Scripts/AI/Detection.lua` has a `motion_factor` (detection-distance
    bonus up to 1.5x, keyed to angular speed over angular size, saturating at 10) and an aspect-
    and class-dependent detection-*time* model (1 s for a target ahead at max range, 10 s behind;
    10 s and 60 s respectively for ground units), plus a scan-time term for optic sensors. The
    desk pass reached its conclusion honestly — the Mi-24P tree genuinely contains neither term —
    but generalised from the module to the engine. Full reading:
    `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` findings 2-3.

    **What survives, and matters more than the correction:** ED's motion term and our own
    movement-detection design answer *different questions* and must not be swapped. ED's ratio
    reduces algebraically to `v_perp / size` — body-lengths per second, range-invariant — and it
    asks "is this easier to spot". Ours is an absolute angular rate and asks "can the crew tell it
    is moving". ED has no moving/stopped state at all, so our design is not redundant. The
    argument for building it on crew realism rather than parity stands unchanged; only the
    "nothing to catch up to" premise is gone.
  - **ED never exposes a raw numeric range on any crew-facing channel** — only a 24-bucket range
    fragment, or nothing. That corroborates rather than merely supports moving range uncertainty
    into this milestone: ED's own AI crew does not get a number either.
  - **Weather is live-readable after all.** `world.weather.getFogThickness()` and
    `getFogVisibilityDistance()` are real getters (DCS 2.9.10+), reversing the assumption that
    weather was `.miz`-only. They live in the Mission Scripting sandbox rather than `Export.lua`, so
    they need the Hook → `net.dostring_in` → UDP bridge already proven for F10 commands — untested
    against the `"mission"` target specifically.
  - ~~**The formula is still only partly known**, and the next artifact is named: `./Scripts/AI/
    Detection.lua` … **the single highest-value thing to read on the Windows box.**~~ **DONE
    2026-09-20** — read, along with `Skill_Factors.lua` and the detector symbol tables:
    `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`. Four results that
    change what slice 2 is planning against:

    - **ED models dwell and scan, with numbers.** Detection takes time; the time depends on aspect
      (6x penalty for a ground unit behind you versus ahead) and, for optics, on the ratio between
      the area being swept and the instrument's field of view. This was the part of the cones
      milestone described here as having "no precedent anywhere in this codebase." It has one now.
    - **The `min_contrast_f` hunt is closed.** The consumer is the engine's own `wDetector`, which
      `CockpitMi24.dll` constructs and calls directly (`getContrastFactor`, `isTargetDetected`);
      `Detection.lua` configures it via `wDetectorInfo::load_from_state`. So ED's two constant sets
      are **layered, not alternative** — engine detection first, module reporting filter on top —
      which is the same two-stage shape as our own `hybrid_source` -> `classification` split.
    - **Petrovich-class omniscience has a number: 27x.** `Skill_Factors.lua`'s `HUMAN_SKILL` tier
      (its own comment: *"for example, gunners on UH-1"*) multiplies visual detection distance by
      27.0 against the excellent-AI baseline, which clips against the 50 km absolute cap. This
      project is not working around an accident; it is replacing a deliberate concession.
    - **One disagreement to settle deliberately, not discover mid-build:** ED gives optics a
      *recognition* advantage over and above magnification (`recognition_distance_ratio_threshold`
      0.5 for optics vs 0.25 for the naked eye). Our 2026-09-17 calibration concluded the opposite
      — that the tiers belong to the eye and the optic only multiplies the angle. Ours is
      screenshot-calibrated on this aircraft and ED's is a game-tuning constant, so this is not a
      defect; it is a real, specific disagreement that slice 2 should decide on the record.

  **Not everything ED does is worth copying.** Our tier semantics are this project's own modelling
  choice and are already documented as never verified against ED internals; the goal is a crew
  simulation, not a reimplementation of ED's AI. The research should say plainly where adopting
  ED's approach would be wrong, and where we have reinvented something ED already does better.
  Nothing found may become a route to omniscience: a field that would let Petrovich know what a
  crew member could not perceive is unusable however readable it is.

- **Cones, calibration and the sortie are interdependent — plan it as a loop, not a chain**
  (user, 2026-09-20: *"I need the cone system to be able to tell whether detection ranges make
  sense. It's all inspect and adapt."*).

  The dependency was previously written as a chain: research, then cones; sortie, then calibration.
  That is wrong in a way worth stating, because it would have produced bad data. **Today Petrovich
  sees in every direction at once**, so a range-calibration sortie flown now measures "at what range
  does an all-seeing observer first report" — not the quantity anyone wants. The confound is exactly
  the thing cones exist to remove. And cones need flown numbers to set their own constants. Neither
  can honestly go first.

  **So the milestone gets sliced, and slice 1 is deliberately the part that needs no research and no
  prior sortie:**

  - **Slice 1 — the cone test and the optics table. DONE (2026-09-20).** `perception/optics.py`
    with an `Optic` dataclass and `within_optic_fov`; `check_visibility` takes an `optic` parameter
    and threads its magnification through the range formula.

    **It did not land as written here, and the difference matters.** This entry anticipated
    "mak[ing] the binocular default an explicit choice." The shipped outcome is the opposite: the
    **naked eye is now the default** (`UNAIDED_OPTIC`, M=1.0) and **binoculars became the explicit
    non-default choice**. The old default applied `BINOCULAR_OPTIC` unconditionally to every
    candidate — Petrovich permanently glassed-up, with binocular magnification across the whole
    cockpit-mask envelope at no cost in field of view. **Default detection range dropped roughly
    4×**, which is the largest single correction to over-detection the project has made, and larger
    than anything the cone test itself contributes.

    `BINOCULAR_OPTIC` is a Б-6 6×30 at M=4.0 — *derived* as 6× glass × a ~0.67 unstabilised-platform
    penalty, not the inherited `HelperAI.lua` constant restored — carrying a real 4.25° field-of-view
    half-angle that becomes enforceable once slice 2 can select an optic. The 9K113 was cut from this
    slice. Its figures live in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`, and
    the deferred backlog item is in `todo/todo.md` — filed on `main` (7a87514) as a side quest, so
    it is not visible from this feature branch.

    Full record, including a 4.0 → 8.0 → 4.0 excursion that the 2026-09-17 photographic ladder
    refuted within a commit: `plans/detection-cones-slice1/plan.md`.
  - **Slice 2 — scanning, dwell and honest range.** The attention state machine, detection as a
    process rather than a predicate, and range as a belief instead of a ground-truth figure.
    **Gated on the ED research deep pass**, because that is precisely what those questions are
    about.

  **The loop, then:** slice 1 → fly it (with BL-9 making belief-vs-truth visible) → adapt the
  constants and the FOV numbers → slice 2 once the ED read has happened. Inspect and adapt at
  milestone boundaries, which is what root `CLAUDE.md` already asks for at merges.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. **Now also owns range uncertainty** (moved here by the user, 2026-09-19), because that
  turned out to be the same kind of problem: a genuine perception limit that differs by optic, not a
  presentation choice. Summary of what moved, full reasoning below:

  > Count vagueness is presentation — the model may hold an exact twelve and still say "several".
  > **Range vagueness is not**: the eye cannot judge distance at these scales, which is why
  > everything that shoots far has carried a rangefinding solution. Today range reaches belief as a
  > ground-truth figure, so a brain layer asking "how far?" would get an answer no crew member could
  > give — the no-omniscience invariant leaking, which adverbs in the callout would have hidden
  > rather than fixed. The 9K113's stadiametric aide (useful to ~5 km, verify before building) means
  > certainty should *narrow* when he uses the sight. The settled rendering rule, once the belief
  > actually holds uncertainty: precision degrades with distance — "very close", a plain figure
  > close in, "about four kilometres", "eight, nine kilometres". Open: whether attention tightens
  > range — probably **no** by default, since attention does not improve the eye, unless it implies
  > he is looking through the sight.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. Today's channels implicitly assume Petrovich is looking everywhere at once within
  range/FOV gates. Future design: distinct optical modes (naked eye, binoculars, and the 9K113
  sight, each its own FOV/acuity/movement-tradeoff), an attention/scan state machine, a scanning loop
  interrupted periodically by a full-area sweep. Would change what feeds `Percept`/`Observation` in
  the first place, upstream of everything BL-2 built — a future perception-layer milestone, likely
  well after BL-4.

## Rejected

- **Persistent omniscient mission-memory store, upstream of perception filtering — REJECTED
  2026-09-10.** A performance angle (avoid DCS LOS queries via a coarse world-model precheck) rested
  on a false premise: `line_of_sight_clear` already samples world-model's *local* elevation grid, not
  a live DCS call. Do not revive without a new concrete trigger. `plans/omniscient-mission-memory/plan.md`
  (never merged) has the proposed pipeline for the record.
