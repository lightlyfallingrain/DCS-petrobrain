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

- [ ] **`fix/contact-report-flood` — DoD PASSED on fixtures, not yet merged, not yet flown
  (2026-10-05).** Suppresses the spoken `CONTACT_DETECTED` callout for a freshly-founded contact
  when an existing, not-yet-`lost` contact is spatially/class-plausibly the same real thing — the
  speech-layer fix for the naked-eye gaze sweep's merge-direction continuity loss (the user's own
  complaint, mid-flight 2026-10-04: *"it feels like many of those reports were about the same
  units"*). Retrospective reconstruction against sortie-1004: 17 of 34 contact-id foundings would
  now be suppressed; the named six-vehicle cluster's four genuinely-simultaneous sightings each
  speak once and the one later re-founding echo goes silent. `CONTACT_REACQUIRED` and group lines
  are untouched. Known, accepted cost: a genuine split immediately after a merge is
  indistinguishable from a merge-echo at this layer and also goes quiet (see
  `plans/contact-report-flood/plan.md`, "The honest cost of the chosen fix"); suppression is
  one-shot and permanent per sortie (belief stays queryable via `report`). Reviewer APPROVED WITH
  MINOR FIXES (since applied); Security deep analysis APPROVED, no Performance pass (Security
  examined the O(n)-per-`CONTACT_DETECTED`-event cost directly — ~34 events per sortie, not per
  tick — and judged none warranted). Does **not** close `BL-B24` or
  `plans/contact-duplication-ambiguity-runaway/plan.md` — both carry a note saying so. Acceptance
  card: `docs/acceptance/2026-10-05-contact-report-flood-sortie.md`. **What the next sortie has to
  settle, because the 17/34 figure is a retrospective reconstruction from pipeline outputs, not a
  byte-for-byte replay**: whether the real cockpit experience is quieter without losing a
  genuinely-distinct contact, and whether the occasional silenced genuine split is ever actually
  noticed. Also flyable on the same sortie: `feature/silence-command` (merged, already on `main`)
  — the manual half of quieting the cockpit, this fix being the automatic half.

- [ ] **`fix/redundant-group-disclosure` — DoD PASSED on fixtures 2026-10-05, not yet merged, not
  yet flown.** Silences a `belief.groups.Group`'s first disclosure when every member was already
  individually reported (directly or via the flood fix's merge-echo above), and speaks only the
  unreported delta otherwise. **Rides the same sortie as `fix/contact-report-flood` above rather
  than needing a separate flight** — both fixes change what the pilot hears about the same
  contact/group stream, on the same cockpit, so one flight settles both: does the stream read as
  signal rather than noise, and does anything go unreported that should have been (the
  over-suppression risk direction both fixes share). Acceptance card published alongside DoD
  sign-off; add its ask to the already-pending contact-report-flood sortie rather than scheduling
  a second one.

- [ ] **`fix/confirm-band-affirmatives` — the confirm band was unanswerable in the air; fixed and
  merged 2026-09-28 (`583d786`), unflown.** **Merged before its acceptance flight at user
  direction** — *"so many things at this stage are intertwined that it's better to test to current
  HEAD"* — so the card
  (`docs/acceptance/2026-09-28-confirm-band-sortie.md`) is now flown from `main` alongside
  everything else outstanding, not from a branch. Same posture as the 2026-09-24 binocular-optic
  merge: a correction the flight produces lands on `main` rather than on a branch that has drifted. The 2026-09-26 sortie: `"cancel"` → *"Cancel everything, confirm?"* →
  `"yes"`/`"confirm"` → *"Unable, no such command."* Three defects behind one symptom, and
  `cancel` always routes through the confirm band whatever its match ratio, so all three hit
  every cancel: `"confirm"` — the word the question itself asks for — was not an affirmative;
  `CONFIRM_WINDOW_S` was 8.0 s timed from when the question was *decided* rather than heard,
  against a ~6.5–7.5 s round trip; and a late answer escalated to the brain, whose
  `NO_SUCH_COMMAND` is literally where that wording came from. Now 15.0 s, a 20 s late-answer
  grace that says "Say again?" instead, and a widened answer vocabulary.

  **What the sortie has to settle, because static review cannot**: whether 15 s and 20 s are
  right (both are reasoned budgets, not measurements), and whether `cancel` → `"confirm"` → the
  task actually stopping works in the cockpit.

  **Worth recording separately: this took five review rounds, and each round's fix broke
  something the previous round had right.** First word is an answer word → swallowed a real
  instruction opening "okay". Every word an answer word → rejected "yes do it", and inside the
  window a rejected answer *silently discards the pending command*, so the cancel just would not
  happen. `verb_anchored` → broke bare `"roger"` and `"negative"`, which had worked before the
  branch existed (`VERB_FLOOR` is 0.5 fuzzy; `roger` scores 0.55 against `report`, `disregard`
  *is* `cancel_nevermind` at 1.00). The anchor for multi-word utterances → still broke
  `"roger wilco"`, because the anchor is computed from the **first word alone**. What shipped is
  the union of all of them, ordered. **Every round was found the same way** — by running the real
  `command_matcher` end to end rather than trusting a test that supplied its own default for the
  parameter under scrutiny — and that is the transferable lesson, not the word list. The
  cross-subproject coupling is now pinned from both sides (`audio-adapter` asserts those words do
  anchor; body-layer asserts the classifier answers them anyway), since neither may import the
  other. Full five-round log: `plans/confirm-band-affirmatives/review.md`.

- [ ] **`sortie-2026-09-26-fixes` (Fix A/B1/B2/C) — merged, DoD PASSED on fixtures/console only,
  not yet flown.** All three fixes have real in-cockpit observables and this is deliberately
  *deferred*, not waived — the plan and DoD gate both treat a flown sortie as needed, not optional
  (unlike e.g. BL-3, waived by its own plan). Card: see the acceptance card DoD published for this
  branch. What it should clear: (1) crossing/motion callouts stop for contacts behind the cockpit
  mask or briefly occluded beyond the grace window, without regressing the already-fixed
  "sounds like a fresh sighting" wording; (2) binoculars actually get used on a watched/orbited
  contact held at constant range, not just a closing one; (3) an unrecognised utterance no longer
  interrupts an in-progress look, and `follow <target>` on the already-glassed target does not
  lower and re-raise. Sector coverage (Decision 2a, see Backlog below) is explicitly **not** in
  this branch — "all ten units to my left get identified" is still expected to fail and must not
  be read as a regression of this fix. `CALLOUT_OBSERVABILITY_GRACE_S` (10.0s) and
  `OPTIC_RETRY_INTERVAL_S` (~64s) are both starting values pending this sortie's feedback, not
  measurements — the card's own commands were run and their output verified before publishing, not
  written from reading the code (DoD role requirement).

- [x] **Binocular optic, voice command completeness, and precise position belief — FLOWN AND
  CLOSED 2026-09-25** (user direction). `docs/acceptance/2026-09-23-eyes-and-voice-sortie.md` is
  closed. **This sortie is where most of 2026-09-25's fixes came from** — the callout heard while
  scanning the other way (`plans/callout-outside-gaze/`, then `plans/scan-is-not-watch/`), cancel
  resurrecting a superseded scan, range crossings sounding like fresh sightings, and the outpost
  fragmenting into 18 contacts (`plans/contact-fragmentation-at-range/`). Original entry follows.

  ~~merged to `main` 2026-09-24 (`c398675`), still unflown.~~ All three passed DoD on fixtures/console only. **Merged
  before the sortie by user decision (2026-09-24)** — so any correction the flight produces now
  lands on `main` rather than on the branch. Precise position belief joined this list at merge:
  belief now carries a fused 2×2 covariance instead of quantised buckets, which changes what the
  pilot will hear for ranges and bearings and has never been heard in the air.
  The first two are deliberately batched onto one sortie because they are one cockpit
  loop (look, report, be told where to look): `docs/acceptance/2026-09-23-eyes-and-voice-sortie.md`.
  Clears when that sortie is flown and the card's "Bring back" items are answered — the nine
  unbenched `scan <clock>` tokens' recognition accuracy in particular has no measurement of any
  kind yet, benched or live. **Precise position belief's own debt item is superseded by the entry
  below** — the version merged here had the range-runaway defect the fix branch corrects; do not
  fly this card's position-belief items until that fix has merged. **It merged 2026-09-25 (`bfbcf8d`), so they are now judgeable.**

- [x] **Position-belief-runaway fix — FLOWN AND CLOSED 2026-09-25** (user direction).
  `docs/acceptance/2026-09-25-position-belief-sortie.md` is closed. No range beyond the cap was
  reported back; the belief-truth log from the same sortie is what exposed the separate
  fragmentation defect instead. Merged 2026-09-25 (`bfbcf8d`).**
  (`fix/position-belief-runaway`, 2026-09-25). Corrects the range-runaway defect above (see the
  Status entry for the four fixes). Card: `docs/acceptance/2026-09-25-position-belief-sortie.md`
  — its own headline check (no naked-eye range beyond 10 km) is checkable by ear in one flight;
  whether the underlying believed position is now *correct*, not just *bounded*, and whether
  hold-recovery timing (~7-10 s predicted) matches a real sortie, are both harder to judge and the
  card says so explicitly. Clears when a real flight exercises it post-merge.

- [ ] **Everything merged 2026-09-24/25 that has not been heard in the air — one card,
  `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`** (user direction, 2026-09-25: *"fold into
  single"*). Covers watch reporting (`9b16c3b`), scan-is-not-watch, cancel-everything, the
  range-crossing direction words, the subitizing cap at 5, glass-watched-first, the orange watched
  marker and the console-fit eyesight view, and BR-1 Stage 1. Two earlier cards were folded into it
  and are marked superseded in place: `2026-09-24-watch-reporting-sortie.md` (never flown, and
  **stale before it could be** — written while a commanded `scan` still conferred watched-ness, so
  its watch blocks would have tested the wrong thing) and
  `2026-09-25-brain-layer-stage1-sortie.md` (not stale, absorbed).

  **The reason this is one card rather than nine.** Most of what it checks came out of the
  eyes-and-voice sortie, which produced eight fixes rather than a pass. So the thing worth a flight
  is not "do these features exist" but "are the fixes right", and that is one continuous listening
  exercise: the card's block 1, whether commanded scans are still noisy, is the single item worth
  most.

  Two things it explicitly cannot judge, said on the card so no flight time is spent on them: with
  `StubDecider` behind the wire there is no intelligence to evaluate (only responsiveness,
  stand-by timing, and hearing a reply at all), and `follow <descriptor>` still cannot pick the
  right contact — the D10 validator wants the model's evidence to be a literal substring of the
  candidate's own description, which the structured-candidate revision fixes. Clears when the
  sortie is flown and its "Bring back" items are answered.

- [ ] **Two things waiting on the user's own machines, added 2026-09-19.** Neither blocks work.
  - ~~**The daily status-page launchd job**
    (`.claude/scripts/com.petrobrain.status-page.plist`), written but never installed.~~ **Closed
    2026-09-27 — the user rejected installing it, permanently** (`X-B24` in `todo/backlog.md`;
    `.claude/skills/status-page/SKILL.md` carries the reasoning). Regenerating the page is a manual
    `/status-page` run by design: the page is explicitly derived-not-authoritative, so a stale one
    is cosmetic, and that did not earn a background job on the user's machine. The plist stays in
    the repo as an unused template — do not offer to install it again. Found still listed here as
    an open item on 2026-10-01, four days after the decision.
  - ~~**The sortie.** Five separate entries clear on one flight — see the list below plus Stage 4b
    speech and the contact-report wording. Flight card:
    `docs/acceptance/2026-09-18-stage6-sortie.md`.~~ **Closed 2026-09-25 (user direction) without
    being flown**: all five blocks were answered piecemeal by later sorties. Detection ranges pass
    ("close enough for current stage"); voice, F10 scan vocabulary and attention/events were covered
    by other flights; contact separation moved to
    `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`. The card carries the per-block verdicts
    and is marked do-not-fly — it had gone stale (it still names `srs-adapter`) before it could be
    flown, which is why the 2026-09-25 cards were folded into one instead of batched the same way.

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

- [ ] **Group cohesion redesign — merged to `main` 2026-10-01 (`ff7934e`), still unflown.**
  DoD's mechanical gate passed at `6d6ea3f`; the merge followed on the user's instruction, with
  live acceptance tracked as debt rather than blocking it. Reviewer (round 2),
  Security, and Performance (MONITOR, `BL-B23` filed — see Backlog) all approved; 1367 passed/4
  xfailed, `ruff`/`mypy --strict` clean at the tip. Card: `docs/acceptance/
  2026-10-01-group-cohesion-sortie.md` (and its artifact). What the flight has to settle and
  static review cannot: whether the 500 m installation cap and the `AIR_DEFENSE_OP_CLASSES`
  membership guess (both one-source-of-evidence per the plan's own "Risks & Unknowns") hold up
  against real unit placement; whether the delta taxonomy's six branches land correctly by ear
  (new class speaks, repeat non-air-defence member silent, repeat air-defence member always
  speaks, leader change speaks a short delta not a restatement, pure departure silent); and
  whether the two user-approved but still-surprising behaviours (infantry `EAGER` bridging a
  non-infantry pair into one group; S-300 not flagged `installation_component` so its own
  components do not single-merge) read as intended in the cockpit rather than as noise or a
  miss. Clear this entry only once a real sortie exercises it, and say which one.

- [ ] **`silence` command — DoD PASSED on fixtures/console only, 2026-10-04, unflown.**
  `feature/silence-command`, tip `de6c530`. Deferred, not waived — the plan never scoped live
  acceptance out, and whether it works for the pilot is exactly the kind of thing fixtures
  cannot settle (unbenched recogniser accuracy on the three phrasings, whether one word of
  acknowledgement is the right amount, whether absolute silence is still wanted once a threat
  actually appears while muted). Card: `docs/acceptance/2026-10-04-silence-command.md` (and its
  artifact). What the flight has to settle and static review cannot: which of `"silence"`/
  `"be quiet"`/`"shut up"` the recogniser actually hears; whether `"Quiet."` then nothing at all
  — including danger calls — feels right in practice; whether any command correctly ends it
  (including the `"stop"` quirk noted in review: `stop_talking` also ends silence, since it is a
  command too). Clear this entry only once a real sortie exercises it, and say which one — it may
  share a sortie with the group-cohesion and confirm-band entries above, since all three are
  cleared by ordinary flying with commands and contacts present.

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

- [>] **BL-7's phase data is unreachable in a sortie — found 2026-09-24, DEFERRED TO THE BRAIN (user, 2026-09-24).**
  `--mission-understanding` loads the artifact and `MissionPhaseTracker` updates every poll, but
  **nothing a pilot can reach in flight reads it.** `mission_phase` appears in four files
  (`console.py`, `tools.py`, `mission_phase.py`, `tool_api.py`) and in none of `attention.py`,
  `callouts.py` or `crew_console.py`. The phase-proximity tie-break is real but sits inside
  `_highest_attention_contact`, called only by `get_situation`, called only by the `--console`
  debug harness; the brain that would otherwise call the tool API is still `NullBrainClient`. So
  mission phase currently changes nothing about what Petrovich attends to or says on a `--crew-text`
  sortie. Two ways out, and they are not equivalent: a crew-facing way to *ask* (a `situation`
  command — cheap, but only surfaces phase when asked), or phase feeding attention/callout ordering
  directly (what BL-7's own plan implies, and what would make the tie-break matter unprompted).
  Pilot's report of the same gap: *"the commands to exercise it during mission do not exist yet."*
  Blocks the B half of `docs/acceptance/2026-09-24-mission-interpreter-sortie.md`.

  **Deferred deliberately, not forgotten.** User direction 2026-09-24: *"situation/phase — not
  needed yet, there is nothing that consumes it yet. Defer till brain."* Building a `situation`
  command now would produce a readout nothing acts on; phase earns its place once a brain is
  reasoning over it. Do not start this without the brain layer existing.

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

  **A concrete consumer now waits on this, added 2026-09-29: the "safe from" callout.**
  `plans/dcs-driven-los/plan.md` defers it at user direction, and the reason names exactly what
  BL-8 would have to hold. *"Danger"* is a claim about something Petrovich can see; *"safe from"* is
  a claim about an **absence** — it asserts a unit is no longer able to shoot you, which needs to
  know where that unit is *now*, not where it was last observed. Once LOS comes from DCS for units
  the naked-eye channel is currently observing, a contact outside that coverage has no honest basis
  for a clearance without remembered believed positions. So BL-8 is no longer only "what is worth
  remembering after a sortie" — it now has one named in-mission consumer whose feature is switched
  off until it exists (`belief/speech.py`'s `engaged=False` branch).

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
  serve calibration, the outstanding acceptance debts, and BL-8's "run for real" gate at once.
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

- [x] **Five-fix sortie — FLOWN AND ACCEPTED 2026-09-23** (user: *"with these fixes, Five-Fix Sortie is done and accepted"*), four passes.
  (`docs/acceptance/2026-09-22-five-fixes-sortie.md`.)

  | | result |
  |---|---|
  | Callouts current | **pass** — *"pretty good"* |
  | Repetition gone | **partial** — *"not completely, but better than before"* |
  | Groups found sooner than singles | **undecided** — needs more testing |
  | Watch and scan together | **pass** |
  | Movement | **pass** on a preliminary test |

  Three of the five close outright; the aggregation and group items stay open below with what the
  transcript actually showed.

- [x] **Internal identifiers were being read aloud — fixed 2026-09-23** (`fix/spoken-vocabulary`).
  The sortie produced *"unit at 12 o'clock, 2 kilometres is OP_LRSAM"* and *"...is
  OP_GROUPSOMETHING"*: this codebase's own `op_class` bucket names, spoken to the pilot.

  **The cause is worth more than the fix.** `_OP_CLASS_DISPLAY` carried a comment stating that
  every `op_class` the object model assigns had an entry, and that was true when written.
  `OP_LRSAM` arrived later with the aspect-profile work and was never added, and the unmapped
  fallback returned the value *verbatim* — so a vocabulary gap became an intelligibility failure
  rather than a specificity one. The comment was the only thing enforcing the invariant, and a
  comment cannot fail. `test_speech.py` now derives the class set from `object_model` itself, so
  the next class added there fails a test instead of reaching the audio channel.

  A second stale claim fell with it: `OP_GROUPSOMETHING` was documented as unreachable at `class`
  level. The transcript disproved it.

  **Wording decided with the user, from the same transcript:**
  - The three SAM tiers are spoken apart — *short range SAM* / *medium range SAM* / *long range
    SAM* — rather than all collapsing to "SAM". The difference between a short-range and a
    long-range SAM is the difference between a threat you can fly around and one you cannot, so
    flattening them discards the most decision-relevant part of the call.
  - `AAA` is spoken *"triple A"*. Not a mis-reading fix like the `Mi-XX` entries: the letters are
    pronounced correctly and are still the wrong thing to say.
  - `OP_GROUPSOMETHING` is *"group"*.

  **One over-reach caught by the existing tests, worth recording.** The first fix replaced *every*
  unmapped class value with a generic word, which would have reduced *"BMP-2"* to *"contact"* — a
  `class`-level value is not always an `OP_*` bucket; it can be a raw DCS type name or scope/hybrid
  free text, and those are already sayable. The rule is narrower than it first looked: suppress the
  `OP_` prefix specifically, pass everything else through.

  Also fixed from the same transcript: *"1 kilometres"* → *"1 kilometre"*. Only exactly 1 takes the
  singular, which is why it is an equality check and not a less-than-or-equal one.

- [x] **Radio brevity, and cancel became three commands — 2026-09-23** (`fix/spoken-vocabulary`,
  user direction from the five-fix transcript).

  **Articles dropped.** *"a couple of contacts"* → *"couple contacts"*, *"Scanning to the left"* →
  *"Scanning left"*, *"Copy, stopping the scan to the left and the watch"* → *"Copy, stop scan left
  and watch"*. The user's reason is the right one and worth keeping: an article carries no
  information in a report and still spends a slice of a channel one person can occupy at a time.

  **An identification line now opens with the contact's class.** *"unit at 11 o'clock, very close
  is BTR-70"* → *"armor 11 o'clock, very close is BTR-70"*: it says what the pilot is being asked
  to look at before it says what it turned out to be. Two guards fell out of trying it — a type
  whose profile lands on the object model's default class (`BM-30`, `SA-10 Flap Lid radar`) keeps
  *"unit"* rather than opening with *"group"*, which reads as a formation; and a lead that would
  repeat the payload (*"truck … is truck"*) falls back to *"unit"*, because that is a stutter
  rather than a report.

  **Cancel is three commands now, reversing this console's own decision from two days earlier.**
  The old reasoning was sound given what existed: there was no vocabulary to say "cancel the watch"
  as opposed to the scan, so cancelling everything and naming each thing stopped beat guessing. The
  user's answer after flying it was to supply the missing vocabulary instead — *"stop watching
  \<unit\>"* and *"stop scan"* are separate actions, and **one cancel must not end the other
  mode**. Scanning while watching a contact is ordinary, and the old reading made it inexpressible.
  `cancel_scan` and `cancel_watch` are narrow; `cancel_task` stays as the explicit all-modes form
  and still names both. The F10 menu grew a `Stop` submenu with all three.

  **Voice caught up the same day** (user, 2026-09-23: *"voice command 'cancel task <task>' should
  work 'cancel <task>'"*). `cancel_scan`/`cancel_watch` are spoken as *"cancel scan"* / *"stop
  scan"* / *"stop scanning"* and their watch equivalents.

  The hesitation had been that these phrasings are **unbenched** — `audio-adapter`'s 99.2% figure
  was measured on a recorded corpus containing no examples of them — and that is still true. The
  user's answer is the right one: a menu-only way to say something the pilot is already saying out
  loud is the wrong side of that trade. The tests prove the phrasings are unambiguous against the
  rest of the vocabulary, which is a different claim from proving whisper hears them; the next
  corpus recording should include them.

  Two decisions inside it:
  - **A bare *"cancel"* stays the all-modes form.** It cannot name which mode it means, and
    guessing is exactly what the narrow tokens were introduced to stop.
  - **`stop scan` does not collide with `stop`** (which silences him), because that rule counts
    only when the single word is the entire transmission — settled in Stage 2 for an unrelated
    reason, and it carries this case for free.
  - **`ACT_FLOOR_CANCEL` now keys on a `CANCEL_TOKENS` set** rather than one name. A mis-heard
    *"stop watch"* destroys standing state exactly as a mis-heard *"cancel task"* does, and the
    narrow tokens would otherwise have inherited the ordinary floor silently.

- [ ] **Repetition is better but not gone — reopened 2026-09-23 from the sortie.** Aggregation
  works on same-type, same-range, adjacent-clock contacts, and the transcript shows it firing. What
  it does not catch is the run it left behind:

  ```
  ground, 12 o'clock, 2.5 kilometres.
  ground, 12 o'clock, 4.5 kilometres.
  ground, 12 o'clock, 3 kilometres.
  ground, 12 o'clock, 4 kilometres.
  ground, 12 o'clock, 4 kilometres.
  ```

  Five presence-level calls in one sector within one scan, differing only in range, two of them
  identical. They are not aggregated because the range differs, and the range is precisely the part
  that carries no information at presence level — *"ground, 12 o'clock"* five times is one fact.
  Two candidate rules, not yet chosen: widen aggregation to a range *band* at presence level only,
  or suppress re-reporting a contact already called within some window. The second is probably the
  real one, since the identical repeat suggests the same contact was called twice.

- [x] **Precise position belief — Stages 1 through 5. DONE**, merged on `feature/binocular-optic`
  alongside the two milestones below it (plan/review: `plans/precise-position-belief/`). Replaces
  the reporting-vocabulary quantisation that used to stand in for a believed position with a real
  perception-side error model, closing a bug that was worse than "coarse": `naked_eye_source.py`'s
  old `_quantise_range_m` snapped every range onto its bucket's *upper bound*, not its midpoint, so
  belief was systematically biased **long** by up to a full bucket width (500 m at 3 km) — not a
  conservative approximation, a one-directional error nobody had named. The old clock-bucket
  bearing/range-bucket split was also inverted: it claimed range was known tighter than bearing,
  when a human points at something far better than he judges its distance to it.

  **The model**: each look's error ellipse is elongated along its own line of sight —
  `sigma_down_m = RANGE_FRACTIONAL_SIGMA(0.17) * true_range_m` (derived from ED's own `OP_D*`
  range-bucket ladder, which coarsens with range — the signature of a fractional error), `sigma_
  cross_m = radians(BEARING_SIGMA_DEG(3.0)) * true_range_m` (a declared, unmeasurable judgement
  constant — nothing in DCS reports a crewman's own pointing precision). **Every reported bearing/
  range is perturbed**, not just budgeted with a disclaimer (`perception/estimation.py`,
  `perturbed_bearing_range`): a per-look draw hashed off the observation id (reproducible, averages
  down across looks) plus a per-object systematic bias hashed off the object id and never re-drawn
  (`SYSTEMATIC_BIAS_FRACTION = 0.4` of one look's sigma). The property this defends: a
  heavily-observed contact must converge to a position that is confidently and precisely **wrong**,
  not to exact ground truth behind a cosmetic uncertainty figure — stating an uncertainty on an
  exact number would make `belief/percept.py`'s no-omniscience boundary a comment rather than a
  mechanism. `derived_world_position` stays ground truth, unperturbed and never crew-facing (trace/
  debug tooling only).

  **Fusion is 2x2 covariance, not a running mean** (`belief/position_belief.py`'s `PositionEstimate`
  — mean x/z + covariance + `as_of_sim` — now what `Contact.position` holds and `record()` folds
  into via the standard information-form update; `last_position`/`last_position_uncertainty_m` stay
  as derived properties so existing readers compile unchanged). This is real triangulation: two
  looks from different lines of sight cross and narrow both axes, which a scalar radius cannot
  express. `association_over_time.py`'s spatial gate was promoted to match — a 2D Mahalanobis-style
  test on summed covariances instead of a scalar-radius comparison — **and this is the one piece
  carrying real regression risk pending a live sortie**: a gate that is too tight reproduces the
  2026-09-09 duplicate-contact runaway, this time from a genuinely different mechanism (covariance
  fusion, not shared-formula acuity) than the one Stage 3b-i's own revert was about, so the two
  should not be read as the same risk recurring.

  **Spent downstream**: `belief/optic_policy.py`'s binocular sweep now passes the contact's real,
  measured `bearing_uncertainty_deg` instead of a hardcoded half-clock-bucket default — a
  well-observed contact's sweep collapses toward a single stare instead of always stepping the full
  width Stage 3b assumed.

  **Required review fix, applied post-merge**: Stage 1's `PositionUncertainty` declaration landed
  on `perception/hybrid_source.py` (the scope/HelperAI channel) but Stage 2's actual perturbation
  never did — the plan's own Decision 2 ("does the scope channel get the same treatment?") was never
  recorded as answered by either implementer, so a heavily-observed scope contact was converging on
  *exact* ground truth behind the declared 300 m band, on the channel the pilot actually flies with
  today. Fixed by applying `perturbed_bearing_range` there too, isotropic on both axes at
  `SCOPE_UNCERTAINTY_M` (no reporting bucket on this channel to derive an anisotropic figure from);
  a regression test now pins that repeated scope-channel looks at a stationary object do not
  converge on truth. Decision 2 is recorded answered ("yes") in `plans/precise-position-belief/
  implementation.md`.

  **Uncalibrated, pending a sortie** — same debt class as every perception constant before its
  first flight: `RANGE_FRACTIONAL_SIGMA`, `BEARING_SIGMA_DEG` (the one number only the user's own
  cockpit judgement can move, if callouts point at the wrong place), `SYSTEMATIC_BIAS_FRACTION`,
  and `SCOPE_UNCERTAINTY_M` (still the original placeholder, never revisited). **Unflown as of this
  entry** — Stage 3's gate in particular needs a live sortie before it can be trusted, per the
  plan's own "do not merge Stage 3 without a live sortie" instruction.

- [x] **Binocular optic — Stages 1 through 3b. DONE, merged 2026-09-23** (`e91b9ee`,
  `feature/binocular-optic`; plan/review/stage3b design: `plans/binocular-optic/`). The optical
  model (`perception/optics.py`, `visibility.py`'s per-tier gates) already existed and was
  unreachable — nothing ever decided *when* to raise binoculars. This milestone is that decision,
  `belief/optic_policy.py`'s `decide`.

  **It is a phase cycle, not an interrupt, and the lockout is structural rather than a timer** (user
  direction: *"when scan detects target, do not immediately raise binoculars. First complete the
  current sector naked eye scan... then raise binoculars"*). A `GLASSING`/`SEARCHING` (binoculars
  up) phase is reachable only from the end of a `SCANNING` phase, never mid-scan — so *"at least one
  naked-eye scan before the next binocular look"* is not a rule that could be got wrong by a
  mistimed constant, it is a state the code cannot express reaching any other way. Its length then
  falls out of whichever gaze plan is active rather than being a number this module owns: a free
  scan gives ~16 s between looks, a commanded o'clock sector far less. A player command — F10 token
  or free-form text/voice, unconditionally, not a per-command special case — also drops the
  binoculars immediately (D4: *"the pilot asking for something is itself evidence that what
  Petrovich is doing matters less than what was just asked for"*), wired through a counter
  (`CrewConsole.commands_handled`) the poll loop diffs across each iteration rather than a callback,
  so a command surface added later needs no new wiring here to participate.

  **The trigger is the next classification tier, not always type.** A contact known only to exist
  is worth glassing to learn what *kind* of thing it is; one already classed is worth glassing to
  learn what it *is*. `improvement_window_m`'s `(unaided_range, binocular_range)` band is **computed
  from `tier_ranges` — the same calibration the naked-eye channel itself uses — not a threshold
  invented for this feature**: closer than the lower bound the eye reaches that tier on its own next
  dwell, so glassing there spends the look for nothing; beyond the upper bound the binoculars can't
  reach it either. The band is exactly where the instrument is the difference.

  **Stage 3b — a look is a sweep across the believed bearing's own uncertainty, not a stare at its
  centre.** Found by a test, not by reasoning: a believed contact's bearing is reconstructed from a
  quantised percept (the reporting vocabulary's 30° clock bucket), so it can sit up to 15° off true
  while the binocular field of view is ±4.25° — a single stare at the believed position misses the
  target most of the time. `look_sweep` steps outward from centre across that uncertainty
  (defaulted to half a clock bucket), degenerating to one step (a stare, unchanged) when the
  uncertainty is inside the field of view. `TestSweepFindsAnOffsetContact` is the tripwire that
  proves it — reviewer-verified by forcing the sweep's half-width to 0 and confirming the test then
  goes red.

  **Uncalibrated, pending a sortie, same debt class as every perception constant before its
  first flight:** dwell per look (6 s, split four ways across the Stage 3b sweep), the lockout's
  scan-plan-derived length, the bearing-uncertainty default the sweep steps across, and the
  Stage 3 search-band constant. **Unflown as of merge** — Stage 4 (sortie: does it feel like a
  crewman using binoculars, are the constants anywhere near right) is the next piece of work, and
  nothing above should be read as validated against a live cockpit.

- [x] **Voice command completeness — Stages 1 through 5. DONE**
  (`feature/voice-command-completeness`; plan: `plans/voice-command-completeness/plan.md`). 20 of
  41 recognised voice tokens (`report_all`, the nine `report_clock_*`, the eight
  `report_bearing_<compass>`, `report_bearing_deg`, `scan_bearing_deg`) reached `CrewConsole.
  handle_command` (renamed from `handle_f10_command`, Stage 1 — the F10 radio menu is the transport
  being retired, not the concept the rest of this codebase still needs) and fell through its
  defensive `else` doing nothing — recognition succeeded, the dispatcher said "act", and the act was
  a silent no-op, indistinguishable from not having been heard at all.

  **Stage 2 — the report families.** `report` is a read of current belief and nothing else, never a
  look (*"report is always about current belief. Scan tells to go look"* — user, 2026-09-23): no
  `AttentionArea`, no task, no gaze change. Drops `certainty == "lost"` contacts (never pruned, so a
  report would otherwise grow across a sortie) and anything with no `relative_now`, filters by the
  requested family, groups via a new `belief.callouts.group_facts` (the bucket+chain rule extracted
  out of `group_candidates` so the report and callout paths share one aggregation rule), and speaks
  **one utterance**, capped at `REPORT_MAX_GROUPS` (3, uncalibrated) with a trailing `"And more."`
  when truncated — never one line per group, the same discipline `plans/callout-scheduling/`
  established. An empty result says `"Clear."`/`"<direction>, clear."` — **except** a compass/
  numeric-bearing direction past the cockpit mask's rear cutoff relative to current heading, which
  says `"Can't see <direction>."` instead: `"clear"` there would claim a look that is physically
  impossible, the no-omniscience invariant's mirror image. A contact actually believed to sit there
  is still reported normally; only the absence claim is withheld.

  **Stage 3 — the numeric bearing slot.** `scan_bearing_deg`/`report_bearing_deg` quantise onto the
  nearest of the eight compass sectors (`_nearest_sector`, 45° buckets — *"o'clock direction is
  enough, no need for x degrees granularity now"*, user 2026-09-23) and then behave exactly like
  their compass-word sibling tokens, readback and confirm prompt included (naming the sector, never
  the raw number). Required an `audio-adapter` wire fix: `MatchResult.bearing_degrees` was computed
  by `command_matcher.match_transcript` and then dropped at the wire — `TranscriptEvent` carried
  seven fields, not eight. Now eight; `PendingConfirmation.bearing_degrees` carries the parsed value
  across a confirm round trip so an "affirm" commit does not lose the heading.

  **Stage 4 — prose** (`body-layer/CLAUDE.md`, `docs/concept/STATE_TRANSITIONS.md`, this entry).

  **`DISPATCHED_COMMAND_TOKENS`** (module-level, `crew_console.py`) is now the canonical
  "what has real behaviour" set, asserted against by test; an unrecognised token logs a warning
  instead of vanishing silently. `CrewConsole._print`'s non-urgent path now also calls
  `CalloutScheduler.note_reply`, closing a separate latent defect the reports made audible: every
  command readback has been unbudgeted since readbacks existed, so a routine callout could queue
  immediately behind one rather than waiting for it to finish.

  **Stage 5 -- ownship-relative o'clock scans, and compass scans that finally steer the naked eye**
  (both land together, per Decision 5, since they are two partial fixes to the same seam).
  `scan_clock_1..12` (nine forward hours, mirroring the report family's own clock tokens) give the
  ownship-relative frame the fine granularity it lacked: `left` alone spans three o'clock hours (a
  90-degree wedge), and there was no way to say "just there" relative to the nose (user, 2026-09-23:
  *"'scan 1 o'clock' directs scan at a narrow sector that is own ship relative. That is needed."*).
  `perception.gaze.ScanPlan` gained a `commanded_legs: tuple[int, ...] | None` field carrying legs
  directly -- the architect's own generalisation, rather than widening `RelativeSector` with twelve
  more literals -- so a single o'clock hour is a one-leg plan exactly as `ahead` already is.
  `logger._active_gaze` now also resolves a compass-only `AttentionArea.sector` task (previously
  silently skipped, the measured pre-existing defect: `scan north` registered an area and spoke a
  readback while Petrovich kept free-scanning), converting it to relative legs every poll via the
  new `perception.gaze.legs_within_wedge`, using that poll's own ownship heading -- so `scan north`
  finally moves his eyes, and stays correct as the aircraft turns. `belief.attention.AttentionArea`
  gained a third, sibling directional field, `relative_clock_hour: int | None`, pairwise mutually
  exclusive with `sector`/`relative_sector`; `project_relative_area` projects it the same way. The
  binocular search sweep (`logger._search_sweep`) stays gated on `commanded_sector` alone --
  deliberately not extended to the new commanded-legs cases, out of this stage's scope. Nine new,
  **unbenched** tokens (no recordings in this corpus), the same cost class as `cancel_scan`/
  `cancel_watch` before 2026-09-23 -- next corpus recording's job. **Unflown as of merge.**

- [x] **Watch reporting — Stages 1 through 5, merged 2026-09-24 (merge `9b16c3b`,
  `feature/watch-reporting`). Merged before flying, deliberately, so any correction the sortie
  produces lands on `main` rather than a branch — live acceptance is still outstanding
  (`docs/acceptance/2026-09-25-crew-behaviour-sortie.md`, which superseded the
  `2026-09-24-watch-reporting-sortie.md` written for this stage).** A watched contact now reports itself unprompted on three new
  triggers, plus `follow` becomes both a `watch` synonym and a new best-match way to *name* which
  contact to watch. Correctness review APPROVED (full read), performance review flagged a real
  finding (LOS called before the range/altitude gate) which was fixed and the fix re-reviewed
  APPROVED, security review APPROVED with three non-blocking hardening recommendations carried to
  backlog below. DoD gate run 2026-09-24: format/lint/type/test all green in both touched
  subprojects (body-layer 1177 passed/4 xfailed, audio-adapter 198 passed/1 skipped). **Live
  acceptance outstanding** — a real sortie has still not exercised it; card at
  `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`, which **superseded** this stage's own
  `2026-09-24-watch-reporting-sortie.md`. That card went stale before it could be flown: it was
  written while a commanded `scan` still conferred watched-ness, so its watch blocks would have
  tested the wrong thing.

  **Stage 1 — movement.** `CONTACT_MOTION_CHANGED` has fired since `movement-detection` and was
  never spoken; `belief.callouts._WATCHED_ONLY_KINDS` gates it at the speech layer (not at
  emission), so a contact watched *after* its motion event already fired still gets the callout.
  `_contact_report_text` gained `lead`/`event_clause` affixes reused by every later stage.
  `WATCH_REPORT_MIN_GAP_S` bounds how often one contact can interrupt with watched-only speech,
  independent of `EVENT_COOLDOWN_S`.

  **Stage 2 — kilometre range crossings.** `CONTACT_RANGE_CROSSED`, gated and bookkept *at
  emission* in `ContactStore.tick`'s new sixth block (the opposite placement from Stage 1's
  events, since the bookkeeping — `Contact.last_announced_range_km` — only means anything for a
  watched contact). Seeds silently on first watch. Gated on `certainty_of` so a decayed position
  never manufactures a crossing nobody observed. The trigger's deadband is derived from
  `PositionEstimate.range_uncertainty_m` (new, `bearing_uncertainty_deg`'s down-range mirror) —
  floored/ceilinged rather than a bare tuned constant, forced by `precise-position-belief`
  landing underneath this plan mid-design and turning the input from a step function into a
  continuous, noisy one.

  **Stage 3 — `follow`.** 3a: `follow nearest`/`follow nearest air defence`/`stop following`/
  `cancel follow` as free phrasings on the existing `watch_nearest`/`watch_nearest_air_defence`/
  `cancel_watch` tokens (`audio-adapter`, zero body-layer change). 3b: `MatchResult`/
  `TranscriptEvent`/`PendingConfirmation`/`handle_command`/`handle_transcript` all migrate their
  single-purpose `bearing_degrees` field to a generic `slots: dict[str, int | str] | None` — a
  breaking wire change between `audio-adapter` and `body-layer`, cheap because both are Mac-local
  processes restarted together, done while there was exactly one slot in flight rather than
  after `follow` added three more. 3c: `follow [<descriptor>] [<clock> o'clock] [<n> km]` — a new
  `follow` token whose three qualifiers are parsed slots, not enumerated phrases (the
  cross-product is in the hundreds); resolved by `_resolve_follow_target`, a scored best-match
  over the qualifiers, explicitly framed in its own docstring as a stopgap for the brain layer
  (user's own words) to be deleted, not extended, once free-text targeting exists.

  **Stage 4 — engagement envelopes.** `belief/threat.py` (new module) reads
  `body-layer/data/threat_envelopes.json` (28 Hoggit-derived entries, committed with its saved
  source page as provenance) and exposes `envelope_for(ClassificationBelief)` — the structural
  no-omniscience guard, since the signature cannot accept the type that would carry ground
  truth. Class-level envelopes are *derived* at import by joining the table through
  `perception.object_model.profile_for`, not hand-written (though the join rate against this
  particular table turned out low — see Notable Discoveries in `plans/watch-reporting/
  implementation.md`). `ContactStore.tick`'s seventh block ANDs three independent ways to be
  safe (out of range / under the altitude floor / behind a ridge), a 1.5x Schmitt trigger on the
  leaving side, and a fail-open, uncertainty-swept LOS term with an asymmetric dwell
  (`LOS_MASK_CONFIRM_S`) — a masked verdict needs to hold before it clears a danger call; a clear
  verdict takes effect immediately. Engagement is the one watched-only kind that does **not**
  silently seed: a contact recognised already inside its envelope fires immediately, since that
  is exactly the late-recognition warning this trigger exists for. Speech: `"Danger, <unit>..."`/
  `"Safe from <unit>..."` via `_contact_report_text`'s `lead` affix, `STATE_TRANSITIONS.md`'s own
  wording. **The practical value of this trigger is gated on an optic that does not exist yet**
  (the 9K113) — see the deferred-9K113 backlog entry below, un-deferred in reasoning but not in
  scope by this plan.

  Full design and every measured/decided number: `plans/watch-reporting/plan.md`,
  `plans/watch-reporting/implementation.md`.

- [x] **Position-belief-runaway fix — merged 2026-09-25 (merge `bfbcf8d`,
  `fix/position-belief-runaway`). Merged before flying, deliberately, so any correction the sortie
  produces lands on `main`; live acceptance remains outstanding.**
  (branch head was `0465290` at the DoD gate; plan/review paper trail:
  `plans/position-belief-runaway/`). Corrects a live defect the sortie the day after
  `precise-position-belief` merged actually found: `"couple contacts, 4 o'clock, 87.5
  kilometres"` against a 10 km naked-eye cap. Four distinct fixes under one report:

  1. **`FUSION_SANITY_SIGMA` residual guard in `fold_position`** — the root-cause fix for
     ill-conditioned triangulation (near-parallel disagreeing looks intersecting arbitrarily far
     from either input). Rejects a fused mean unless it sits within 5 sigma of at least one input's
     own covariance; holds the prior (inflated for elapsed motion) otherwise.
  2. **`clamp_to_detection_envelope`, a new function** — the gate that was entirely missing:
     nothing previously checked a fused position against what a channel could physically detect.
     This is the mechanism that actually caught the reported live defect (a slow directional drift,
     individually plausible at every step) — the ill-conditioning guard above addresses a real but
     separately-unreachable mechanism, since the pre-existing association gate already rejects a
     single large-residual jump before it reaches fusion. **This distinction — the user's own
     one-line diagnosis ("position uncertainty needs a gate, cannot be further than detection
     range") named the reachable path; the orchestrator's own ill-conditioning hypothesis, though
     real, did not** — see `NOTES.md`.
  3. **A scale-relative determinant floor** (`Covariance2D.inverse()`'s `_MIN_DETERMINANT_RATIO`,
     replacing an absolute `1e-9`) — found by Reviewer, not planned: the absolute floor was
     calibrated for covariance-scale determinants but silently corrupted the fused *mean* (not
     just reported uncertainty) for any same-bearing repeated naked-eye look beyond ~2.7 km, and
     made the new guard itself misfire on a legitimate residual. Required fix, re-reviewed
     APPROVED.
  4. **Hold-recovery timing decoupled from poll interval** (`PositionEstimate.fused_at_sim`/
     `fused_covariance`, new) — found by Security, not planned: a held position's elapsed-time
     inflation was compounding once per poll rather than once per real gap, so recovery time
     scaled as `O(1/poll_interval_s)` — ~47 s at the project's own 1.0 s default poll interval,
     not the ~20 s the merged review's approval had rested on (measured for a single-gap
     re-acquisition, not continuous disagreeing-look polling). Fixed by tracking "last genuinely
     fused" time separately from "last poll" time. Required fix, re-reviewed APPROVED.

  Also fixed: the doubled unit-type callout (`"truck ... is KrAZ truck"`, `belief/speech.py`'s
  `_identification_lead` stutter guard, an exact-string match that missed a class word appearing
  inside a longer type name) — an independent speech defect reported alongside the position bug,
  unrelated in mechanism.

  DoD gate run 2026-09-25: format/lint/type/test all green (1192 passed / 4 xfailed, +15 over
  main's 1177/4 — verified against an isolated `git archive` of the branch tip, not the working
  checkout, per the standing pytest/PYTHONPATH trap memory). Reviewer and Security both APPROVED
  after their respective required fixes were applied and re-reviewed. **Live acceptance
  outstanding** — card at `docs/acceptance/2026-09-25-position-belief-sortie.md`. This entry
  flips to `[x]`/merged on merge, per the roadmap-discipline rule below.

- [x] **BR-1 Stage 1 — Brain layer, first working slice: merged 2026-09-25 (merge `fc4e4af`,
  `feature/brain-layer`). Merged before flying, deliberately, so any correction the sortie
  produces lands on `main`; live acceptance remains outstanding.** body-layer's half of the first real seam to
  a new subproject, `brain-layer/` (see that subproject's own roadmap entry in root `ROADMAP.md`,
  Architecture and Status-table sections). A free-text utterance that used to produce silence now
  produces a real spoken response, end to end, over HTTP — with `StubDecider` (a configurable-
  delay stand-in) standing in for a model, proving the async wire (non-blocking handoff, stand-by-
  after-timeout, staleness revalidation, newest-wins at the job-slot level) with zero model risk.
  `body-layer/src/belief/brain_client.py` (`BrainLayerClient`, an independent `urllib`-based
  client, module-independence preserved — no import of `brain-layer/`), four new `belief.speech`
  templates (`render_unable`/`render_lost_contact`/`render_stand_by`/`render_disambiguation`), and
  `CrewConsole.drain_brain` (`--brain-client http|debug|null`, `http` requires `--brain-url`) are
  the body-layer surface. DoD verified 1220 passed/4 xfailed (body-layer) and 20 passed
  (brain-layer) against an isolated `git archive` of the branch tip, plus a live spot-check
  against a running `python -m brain_layer` process. Security's one recommended fix (`run-brain.sh`
  defaulting to `--host 0.0.0.0`, exposing `POST /escalate` to the LAN with no offsetting benefit
  in the current same-machine deployment) is applied — loopback is now the default, with the
  choice framed as a deployment fact (only `aircraft-layer` is pinned to a machine; every other
  seam here is HTTP precisely so it can move) rather than a hardcoded property of the service.
  **Two Stage 2 prerequisites measured during the perf pass, recorded not fixed** (unreachable
  under `StubDecider`, armed once Stage 2 adds a real model):
  `poll_replies()`'s 5 s poll-thread timeout (a wedged brain would cost ~83% tick loss at the 1 s
  default poll interval), and `Decider.decide()` having no bounded timeout (one unjoined daemon
  thread per `/escalate`). D10's semantic reply validator is deliberately absent — Stage 1's wire
  is structured JSON from plain code, so there is nothing yet for a validator to guard against.
  **Live acceptance outstanding** — card at `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`
  block 4 (the Stage-1-only card it superseded is
  `docs/acceptance/2026-09-25-brain-layer-stage1-sortie.md`);
  with no real model behind the wire, the only judgeable things are whether the cockpit stays
  responsive while the brain "thinks," whether stand-by timing lands right, and whether hearing
  Petrovich answer at all (instead of silence) feels right. This entry flips to `[x]`/merged on
  merge, per the roadmap-discipline rule below.

- [x] **BR-1 Stage 2 — `OllamaDecider`, a real local model behind the wire. DoD PASSED and
  merged 2026-09-25 (`4bc0df9`, from `feature/brain-layer-stage2`); unflown.** Replaces Stage 1's
  `StubDecider` with a real `qwen3:4b-instruct-2507-q4_K_M` call over `brain-layer/src/
  ollama_client.py`, the classify/discriminate prompt pair (`brain-layer/src/prompts.py`), and a
  new body-side D10 trust boundary (`body-layer/src/belief/brain_reply.py`) that re-validates every
  `PICK`/`CONFIRM`/`ASK`/`UNABLE` the model returns against body-owned data before anything is
  acted on or spoken — a model output can never invent a contact id or a command outside what body
  itself offered. Also lands the two non-blocking prerequisites the performance review required
  before a real model could safely sit behind the wire (`poll_replies()` off the shared poll
  thread; `Decider.decide()` under its own bounded timeout), both measured as discharged. **This
  milestone was implemented twice, independently, by two unaware sessions** — this branch and
  `feature/br1-stage2` — and folded per user direction; the episode and what was/wasn't taken is
  recorded in `plans/brain-layer/implementation.md`'s "Folding in the duplicate branch" section.
  Reviewer APPROVED across all three passes (Stage 2 proper, the fold, and the Security/Performance
  change-request fold — one required fix, addressed and taken further: an AST-based sync test now
  enforces the two mirrored vocabulary constants instead of relying on a comment). Security
  APPROVED (one recommended fix taken — the `_validate_confirm` offered-vocabulary asymmetry; one
  recommended fix explicitly deferred — no byte cap on `response.read()`, reachable only via
  operator misconfiguration of `--ollama-url`). Performance APPROVED — MONITOR: Ollama serializes
  generation, so one slow reply can chain-drop several *subsequent*, unrelated utterances, not just
  its own — reasoned from transport measurements plus D6's 32.7 s worst-case generation figure,
  never observed live. DoD gate: both subprojects' full command sets re-run from a fresh worktree
  checkout (brain-layer 45 passed, body-layer 1292 passed/4 xfailed, ruff and `mypy --strict` clean
  in both) — matching every prior role's claimed counts. **Nothing in this feature has ever talked
  to a real model** — the sandbox every agent on this branch ran in has no route to
  `127.0.0.1:11434`, so all verification (including the fold's own regression tests) ran against a
  fake HTTP server or, for the DoD gate's own live spot-check, `StubDecider` again (proving the
  live-check tool's wire mechanics, not a real model's output). **Live acceptance outstanding** —
  card at `docs/acceptance/2026-09-25-brain-layer-stage2-sortie.md`, published as its own artifact
  (https://claude.ai/artifact/VPYm5D44Z98kuEk3ErwbD1) since it needs Ollama running with the model
  pulled in addition to the usual three-process setup, a real branch checkout rather than `main`,
  and is the first flight where the pilot hears the model's own language rather than a canned
  reply. Does this change what the next milestone should be? Yes, in one respect: Stage 3's A/B
  answer leg and the D10 structured-candidate revision (`feature/d10-structured-candidates`) both
  build on the discriminate prompt's `BECAUSE` evidence, and this stage's live sortie is the first
  chance to learn whether the 7-token, no-slot `CLASSIFY_COMMAND_VOCABULARY` (deliberately narrowed
  from an alternative ~43-token version the folded-in branch had built) under-serves real
  utterances before either downstream piece is built further. This entry flips to `[x]`/merged on
  merge, per the roadmap-discipline rule below.

- [x] **Group reporting: `belief.groups.Group`, the disclosure ladder. Stages 1-4, reviewed,
  security-approved (deep analysis), performance-approved (MONITOR), and DoD-passed 2026-09-29
  pending the sortie's own acceptance verdict.** `plans/group-reporting/plan.md`, from the
  2026-09-28 sortie's
  log analysis (`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`) — the noise was
  contact *count*, not per-contact chattiness (only 3 of 52 contacts ever plural), which an
  associative `Group` fixes and a per-contact disclosure gate alone cannot. **Stage 1** — `belief.
  callouts.CalloutScheduler` suppresses a scheduled `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
  candidate whose rendered text repeats the last one actually spoken for that contact. **Stage 2**
  — `belief/groups.py`'s `Group`/`GroupStore`: relative-gap cohesion (`GROUP_PROXIMITY_GAP_RATIO`
  = 3.0, `GROUP_REPORTING_MIN_MEMBERS` = 2 — lowered from 3 by user direction 2026-09-28,
  deliberately renamed off `perception.group_salience.GROUP_MIN_MEMBERS`'s name so the two floors
  can no longer collide), union-find over fused `Contact.position`, majority-overlap split/merge
  reconciliation once per `ContactStore.tick()` call. Inspectable via `belief.tools`'s new
  absent-not-null `"group"` fact and `console.py`'s `show <id>`. **Stage 3** — `belief.speech.
  render_group_disclosure`, the disclosure ladder (bare `"Group."` while undifferentiated, a
  per-class composition clause once refined, `"Danger, <type>."` leading when a member resolves a
  real `belief.threat.envelope_for` envelope) — since Stage 4, extended with a two-member "pair"
  rung (`"A couple of contacts."` vague, `"Pair of T-72."` exact, tracking classification
  specificity the same way `_cardinality_phrase` already does within one contact). Named `render_
  group_disclosure`, not `render_group_report` — that name belongs to `belief.callouts`' separate,
  still-live report-space aggregation for contacts with no group. **Stage 4** — wired into both
  live speech paths: `CalloutScheduler.tick` reads `store.groups` alongside `store.
  unacknowledged_events` into one shared priority sort (`group_priority` mirrors `callout_
  priority`'s tuple shape), filtering a grouped contact's own `CONTACT_DETECTED`/`CONTACT_
  REACQUIRED` before scoring; `CrewConsole._handle_report` resolves and speaks each in-scope
  group the same way, so a pushed callout and a pulled "report" describe one group identically.
  `belief.callouts.group_candidates` (the event-level, report-space bucketer Stage 4 replaces) is
  deleted. **Stage 5** (common-fate cohesion) remains deferred, gated on a sortie's evidence.
  **A real discovery worth a decision before the next sortie**: at floor 2, `belief.groups`'
  relative-gap cohesion — working exactly as designed (no absolute radius, only a relative one) —
  means any two contacts alone in an otherwise-empty scene always cohere into a "pair," however far
  apart; combined with `_handle_report` speaking a whole group from one in-scope trigger member,
  this can pull a contact from *outside* a requested clock/sector into the answer. Confirmed
  directly (two contacts 500 km apart, nothing else tracked, still form one `Group`), not
  theorised — see `plans/group-reporting/implementation.md`'s Stage 4 "Notable Discoveries" for the
  full readout and the test fixtures it forced to route around it.

  **The n=2 tautology above was fixed on this branch first** (`9ecedaf`/`b0f9518`, user direction
  2026-09-29) with a flat 300 m backstop gated to `< 3` tracked contacts, then **superseded by a
  second mechanism the same day** (`9ecedaf`.. through `718a65a`/`d04412b`) once review flagged two
  problems with the flat figure: it had no notion of what the units meant (300 m is a different
  fraction of a vehicle for infantry vs. an S-300 component), and gating it to n<3 left the
  relative-only rule genuinely unbounded at n>=3 — confirmed against this branch's own
  `test_2c_transcript_fixture_renders_four_lines_not_seven`/`test_report_all_groups_and_
  truncates_multiple_contacts`, both of which had needed a `store._groups._groups = {}`
  workaround precisely because their own fixtures legitimately merged at n>=3.

  **`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS = 20.0` now closes both the n=2 and the n>=3 case**,
  applied to *every* pair at *every* tracked-contact count (not gated by n): a per-pair bound in
  unit widths of the pair's own mean believed physical size (`perception.object_model.size_m`, via
  each contact's `last_class_raw`), so two contacts 500 km apart no longer cohere (n=2, the
  original discovery) and neither do three-plus contacts kilometres apart with little else tracked
  (n>=3, review's finding). The relative-gap rule stays primary and can still be tighter in a dense
  scene; the unit-width bound only ever narrows it, never widens it. Confirmed by tests, not
  theorised (`GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M`/its n<3 gate are deleted; `test_sparse_desert_
  group_can_span_a_wide_gap` recalibrated to a 220 m span, still under the ~120-140 m backstop for
  the vehicles it uses; `test_2c_transcript_fixture_renders_four_lines_not_seven` re-verified
  against real per-tick output — the five-object n>=3 fixture no longer merges into one composite
  group across types).

  **The two attribution consequences the n>=3 risk raised (nearest-member clock/range vs.
  threat-led line; `_handle_report` speaking a whole group past a sector filter) are not separately
  fixed, but their blast radius is now bounded to ~140 m (a 20-unit-width vehicle pair) rather than
  unbounded kilometres** — a sparse merge can no longer put a named threat "somewhere else
  entirely" the way the original 500 km/kilometres-apart discovery could. Security's deep analysis
  (`plans/group-reporting/security-review.md`) independently re-traced this closure through the
  code rather than taking the plan's word for it. Stage 5 (common-fate cohesion) remains the
  intended real fix for cohesion generally and stays deliberately deferred pending this sortie's
  evidence — the unit-width backstop is a stated assumption (20.0, not a measurement), not a
  substitute for Stage 5.

  1349 passed/4 xfailed, `ruff`/`mypy --strict` clean. **Milestone completion question**: does this
  change what's next? Yes, in the direction Stage 5 should take — the sortie flying tonight is the
  first real evidence on whether 20 unit-widths groups the right things (see
  `docs/acceptance/2026-09-29-group-reporting-sortie.md`), and Stage 5's design should be built
  from what that flight actually shows about cohesion misses/false-merges, not from more code
  reading in advance of it.

- [~] **Group cohesion redesign: size-relative/kind-coherence cohesion, infantry `EAGER` release,
  and the delta taxonomy. Merged to `main` 2026-10-01 as `ff7934e` (branch was
  `fix/group-undermerging` @ `6d6ea3f`); flight outstanding. Reviewer (round 2), Security
  (deep analysis), and Performance (APPROVED — MONITOR, `BL-B23` filed) all passed; DoD's
  mechanical gate (format/lint/type/test) passed 2026-10-01 at this tip (1367 passed/4 xfailed,
  `ruff format`/`ruff check`/`mypy --strict` clean). Not merged as of this entry — pending the
  user's acceptance call, per the live-acceptance-debt entry below (which the project's own
  "never block a merge on live acceptance the user cannot currently perform" posture means the
  user may choose to merge ahead of the flight rather than wait, tracking the flight as debt).**
  `plans/
  group-cohesion-redesign/plan.md`, built on `plans/group-undermerging/debug.md`'s 2026-10-01
  sortie debug (the re-trigger fix already merged) and three Explore rounds the same day. **Stage
  1** — `belief.groups.CohesionBackstop` (`STRICT`/`EAGER`), `_OP_CLASS_COHESION_BACKSTOP` makes
  `OP_INFANTRY` `EAGER` (no backstop at all for a pair where either member is infantry) — user
  direction: *"Ok to merge infantry too eagerly."* **Stage 2** — `perception.object_model.
  ObjectTypeProfile.installation_component: bool`, `True` only for `"s-125"`/`"kub "` (a real
  finding mid-revision: `op_class="OP_SRSAM"` alone would have conflated the genuine fixed S-125
  site with four single-vehicle systems — Osa/Strela-10/Strela-1/Tor — that must stay excluded);
  `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M = 500.0` (down from a discredited 1000 m guess,
  grounded in `body-layer/research/2026-10-01-sam-site-geometry.md`'s real S-75/S-125 doctrine).
  **Stage 3** — the delta taxonomy: `Group` gains `last_spoken_member_contact_ids`/`.
  last_spoken_leading_contact_id`/`.last_spoken_differentiated`; `belief.speech.render_group_
  disclosure` now decides full/delta/silent per tick (leader change -> a short "Now leading: X."
  delta, never a full restatement; first differentiation -> full, once; a new or repeat-air-
  defence arrival -> a delta naming just the new member(s); a repeat non-air-defence arrival or a
  departure with no new arrivals -> silent). **A real design gap found and fixed while wiring
  this in**: `belief.crew_console.CrewConsole._handle_report`'s pull-based "report" command used
  to call `render_group_disclosure` directly and relied on it always returning the full
  composition (its own comment: "a report is pull-based, so it always speaks fresh"); the new
  taxonomy breaks that assumption (a post-taxonomy call can return a delta or `None`), so a new
  `render_group_full_disclosure` (taxonomy-free, always full) was added for the pull path, and
  `_handle_report` now calls that instead — confirmed against the delta taxonomy's own worked
  "report" roll-up example, which always names the full current roster.

  **Verified against real sortie data, not only hand-built fixtures**: the real S-300 battery's
  ground-truth emplacement geometry (`/Users/sg/dcs-belief-truth.jsonl`, 2026-10-01 trace,
  `true_x`/`true_z` for object ids 16785152/16784640/16784896/16785408) forms a 3-member cluster
  under the settled `installation_component` assignment (S-300/`OP_LRSAM` is explicitly NOT
  flagged — only `"s-125"`/`"kub "` are), with the fourth component ("64H6E sr") isolated —
  `tests/test_groups.py::test_real_s300_site_ground_truth_geometry_forms_a_three_member_cluster`.
  **This does not match the plan's own Stage 2 acceptance wording** ("confirmed to form one
  four-member group") — that wording is stale, inherited from before this revision's own §1
  finding narrowed the installation flag off `OP_LRSAM`; flagged in the implementation report
  rather than silently worked around.

  **`tests/test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven` rewritten**
  (AGENTS.md escalation, user-confirmed) — and the actual result is wider than "the infantry pair
  now merges": single-link chaining through an infantry member (no backstop at all) bridges the
  BTR-70 and truck into the *same* five-member group even though their own direct pairwise gap
  does not clear the ordinary backstop, a real and now-pinned consequence of the `EAGER` release
  (`tests/test_groups.py::test_infantry_eager_policy_bridges_a_non_infantry_pair_that_would_not_
  merge_alone`).

  1366 passed/4 xfailed (up from the branch's 1351/4 baseline), `ruff format`/`ruff check`/`mypy
  --strict` clean; two further rounds (indefinite-article removal, undifferentiated-member
  aggregation) brought this to 1367/4 at the merged tip. **Milestone completion question**:
  unblocks `BL-B11` (threat-based report prioritisation) once cohesion correctly reflects
  installation structure, per the plan's own "Second-Order Effect" section — otherwise does not
  change what is next, pending the first sortie to exercise the installation cap/delta taxonomy
  for real (tracked below).

  **Acceptance boundary, stated up front rather than left implicit**: every check above is a
  fixture/unit-test pass. It cannot observe whether the *right* contacts merge in a real,
  continuously-moving scene, whether the 500 m installation cap or the `AIR_DEFENSE_OP_CLASSES`
  membership guess holds up against a real Cold War-era mission's unit placement, or whether the
  delta taxonomy's rendered lines land correctly *by ear*, in the cockpit, under task load — the
  F10 vocabulary precedent (`Scan` driving the wrong sight; `Cancel Task` speaking a raw id) is
  the standing reminder that a fixture pass and a flight pass are different claims.

- [x] **Player bubble — 10 km computation-scope limit on ground/air detection. DONE, merged
  2026-10-02.** `feature/player-bubble` (merge commit, see below), implementing `todo/todo.md`'s
  "Player bubble: 10 km, settled 2026-09-28" item — the user's own already-complete spec was the
  authoritative source, so no separate Architect `plan.md` was written for this one.
  `perception.association.filter_player_bubble()` (`PLAYER_BUBBLE_RADIUS_M`, 10 000 m, ownship-
  relative, omnidirectional, equal-to-radius kept), called by both `NakedEyePerceptionSource.poll()`
  and `HybridPerceptionSource.poll()` immediately after `filter_ownship()` — the earliest point
  either channel's own candidate pool becomes work. Kept structurally independent of
  `visibility.NAKED_EYE_RANGE_CAP_M` (two `dir()`-namespace tests guard against either module
  importing the other's constant by name — a value-equality test can't catch aliasing since both
  constants legitimately equal 10 000 today). Ground/air only; world-model geography/enrichment is
  untouched and has no seam into the bubble (`test_enrichment_module_never_references_the_player_
  bubble`); a contact that drifts outside the radius stays remembered, only detection *computation*
  stops (`test_contact_that_drifts_outside_the_bubble_is_not_forgotten`, real `ContactStore` across
  two polls). New `GateOutcome.PLAYER_BUBBLE` detection-trace row records what the bubble excluded;
  fixed a latent bug in `tools/summarize_detection_trace.py` the new outcome exposed (it would have
  misreported a bubble-dropped candidate as "cleared the cockpit mask"). Reviewer (full read,
  required fixes: none), Security (deep analysis, APPROVED — fails closed on `nan`-valued input,
  no belief-state path for the new trace row), and Performance (APPROVED — MONITOR) all signed off;
  1379 passed/4 xfailed (up from `main`'s 1367/4, +12 new tests, no regressions), `ruff`/`mypy
  --strict` clean.

  **Measured finding, recorded precisely so it isn't later over-cited**: the bubble excludes 76.6%
  of raw candidates in a real sortie trace, but the measured end-to-end saving is only ~1.4%
  (0.955 ms/tick) — both channels' own pre-existing range gates (`NAKED_EYE_RANGE_CAP_M` = 10 000 m,
  `associate()`'s `RANGE_CAP_M` = 5 000 m, stricter) already bounded LOS/association reachability
  at or below the bubble radius, so the expensive work those candidates would have reached was
  already unreachable before this feature existed. This is not a defect — the real payoff is
  structural and arrives once the 9K113 sight (20 km cone) makes the two constants diverge, which
  is exactly why keeping them independent mattered more than the number does today.

  **Milestone completion question**: does not change what's next. `BL-B23` (`ContactStore` never
  pruned) is queued next, and the same Performance review found the bubble does **not** reduce
  `ContactStore`'s accumulation rate today, for the identical gate-duplication reason — noted on
  `BL-B23` itself (`body-layer/BACKLOG.md`) so its future measurement doesn't assume a baseline
  change that didn't happen.

  **Acceptance boundary, stated plainly rather than deferred as debt**: this feature changes
  nothing a sortie can hear or see — no candidate that would have been admitted, spoken, or
  remembered before this branch is excluded now, and none that was excluded is now admitted
  (confirmed by the Performance measurement above, not assumed). **No live acceptance is owed, and
  this is a waiver, not deferred debt** — unlike the live-acceptance-debt list above, there is no
  in-cockpit observable here for a flight to confirm or refute. The condition that will create one
  is already named in the spec: the 9K113 sight's 20 km cone, which makes `PLAYER_BUBBLE_RADIUS_M`
  and `NAKED_EYE_RANGE_CAP_M` diverge and gives the bubble a real, flight-observable effect for the
  first time. Full DoD report: `plans/player-bubble/dod-check.md`.

- [x] **BL-B23 — `ContactStore` never pruned, so clustering cost grew with every contact ever seen.
  DONE, merged 2026-10-02.** `fix/contact-store-pruning`. `ContactStore.tick`'s eighth block now
  filters `GroupStore.reconcile`'s input to `belief.decay.certainty_of(contact, now_sim) != "lost"`
  — reusing the existing lifecycle ladder, no new field. `_contacts` itself is untouched: nothing is
  deleted, a `lost` contact stays full memory and remains answerable via `describe_contact`. Fixes
  the total-ever-seen quadratic growth the Performance Reviewer found during the group-cohesion pass
  (2026-10-01): 403 ms -> 1.4 ms at 1200 total contacts (20 live, rest long-lost), independently
  reproduced by both Reviewer and Performance. Reviewer (full read, required fixes: none), Security
  (deep analysis, APPROVED — pure in-memory filter, no new narration path, memory invariant holds),
  and Performance (APPROVED — MONITOR) all signed off; 1384 passed/4 xfailed (up from `main`'s
  1379/4, +5 new tests), `ruff`/`mypy --strict` clean. `BL-B24` filed alongside (a pre-existing,
  unrelated `association_over_time` long-gap reacquisition ambiguity found while writing this fix's
  tests — see Backlog).

  **The fix is bounded, not complete, and that distinction matters for the next reader.** Performance
  confirmed the *total-ever-seen* axis is fixed, but the *live-count* axis is exactly as quadratic as
  before, by design — clustering's input is now the live set, and `_cluster_contacts` is still O(n²)
  over whatever it's given. Measured with all contacts simultaneously live: 20 -> 0.15 ms, 300 ->
  25 ms, 500 -> 70 ms (35% of a 200 ms 5 Hz tick budget). Performance deliberately kept this under
  the existing `group-cohesion-redesign` MONITOR finding rather than filing a new backlog item — it's
  the same risk that review already named, just confirmed to survive this fix unchanged — and framed
  whether a mission can realistically put 300-500 *simultaneously live* contacts inside the 10 km
  player bubble as a scenario-design question, not a code defect, today.

  **Acceptance boundary, stated plainly rather than left implicit**: every number above is a
  standalone microbenchmark against synthetic fixtures, independently reproduced three times
  (implementer, Reviewer, Performance) within single-digit-percent noise of each other and of the
  original group-cohesion-redesign measurement. That is exactly what a fixture can settle — "does
  clustering cost stop scaling with sortie length" is a closed, timing question with no cockpit
  observable, unlike e.g. the F10-vocabulary precedent where only a flight could reveal the wrong
  subsystem driving a command. **No dedicated acceptance card is warranted.** A long sortie already
  pending for the group-cohesion-redesign work exercises this same `tick`/`reconcile` path
  end-to-end and will confirm the fix incidentally; this rides along on that flight rather than
  generating its own. DoD report: `plans/contact-store-pruning/dod-check.md`.

  **Milestone completion question**: does not change what's next, and does not invalidate a
  downstream assumption. It does narrow the live-count MONITOR already on file: that risk is now
  confirmed to be exactly as large post-fix as pre-fix, so whoever next touches `group-cohesion-
  redesign`'s MONITOR item should treat BL-B23 as having tested, not changed, that number.

- [x] **`silence` command — DoD PASSED on fixtures/console, live acceptance outstanding (added
  to the live-acceptance debt list above).** `feature/silence-command`, tip `de6c530`. No
  architect/plan.md — the user's own message settled the two load-bearing decisions directly
  ("make Petrovich not talk until my next command"; chose absolute silence including urgent
  threat callouts, and one spoken acknowledgement, `"Quiet."`, before the mute). A single
  `self.silenced: bool` gates the one existing `speech_client.push_speech` choke point in
  `CrewConsole._print`, applying identically to routine and urgent (`bypass_gate=True`) lines;
  text/overlay surfaces and the scheduler's own occupancy bookkeeping are untouched, so nothing
  is deferred and dumped when silence ends. Cleared only by an actually-dispatched command
  (token-level or a resolved free-text intent), never by stray unresolved speech — the
  radio-traffic use case the command exists for. `silence` also added to
  `voice_commands.CANCEL_TOKENS` for its elevated confidence floor. Reviewer: full read, no
  required fixes. Security: deep analysis, APPROVED (ack-before-mute and no-stuck-on both hold
  by construction; no new dependency, no new ingress path). No performance pass — one `bool`
  check at a call site that already does synchronous HTTP to the TTS engine, not a hot path by
  any measure; recorded here rather than treated as a skipped gate. Checks: body-layer 1398
  passed/4 xfailed, audio-adapter 219 passed/1 skipped, `ruff`/`mypy --strict` clean in both.
  **Audio-adapter half**: `silence`/`"be quiet"`/`"shut up"` wired into
  `vocabulary.VOICE_ONLY_TOKENS`/`PHRASES`. Bare `"quiet"` was dropped from the candidate set —
  measured, not guessed — at a 0.889 `difflib` ratio from the ordinary word `"quite"`, enough to
  false-anchor `"quite a nice day for flying today"` as a command (see NOTES.md). **Not wired:
  no DCS F10 radio-menu button** — that enumeration lives in aircraft-layer's Hook script;
  `handle_command` already dispatches the token generically, so only a Hook-side menu entry
  (or audio-adapter's vocabulary, now done) is needed to reach it. Voice is the only route today.
  **Milestone completion question**: does not change what's next or invalidate a downstream
  assumption — a self-contained dispatcher addition on an existing choke point. DoD report:
  `plans/silence-command/dod-check.md`.

- [ ] **Contact-report flood (merge-echo callout suppression) — DoD PASSED on fixtures 2026-10-05,
  not yet merged.** `fix/contact-report-flood`. See the "Live acceptance debt" entry above for the
  full writeup — not duplicated here. Debug → Architect → Implementer → Reviewer → Security(deep)
  → DoD sequence (bug-fix path; no plan-review stage, matching this project's current
  once-per-feature security cadence). 1399 passed/4 xfailed (up from the branch's own 1389/4,
  +10 new tests), `ruff`/`mypy --strict` clean.

  **Milestone completion question**: narrows, slightly, what a future resolution of the
  `ContactStore.ingest` candidate-ambiguity root policy (`BL-B24` /
  `contact-duplication-ambiguity-runaway`) needs to additionally consider — the *audible* symptom
  of that unresolved policy goes quiet for the merge-driven case specifically, which could make the
  underlying belief-store duplication easier to leave unaddressed for longer simply because nobody
  hears it anymore (recorded in the plan's own "Second-order effect" section). Does not invalidate
  any downstream assumption and does not change what the next milestone should be.

- [ ] **Redundant group disclosure — Reviewer APPROVED 2026-10-05, not yet DoD'd, not yet
  merged.** `fix/redundant-group-disclosure`. A second, speech-layer duplicate-report path one
  level above the merge-echo fix above: a `belief.groups.Group`'s **first** disclosure used to
  always speak the full roster the instant two-plus members first clustered, even when every one
  of those members had already been announced individually — directly, or via a merge-echo the
  fix above already silences. User direction (2026-10-05) settled the design: no "those are
  together" acknowledgement, prioritize less speaking. `render_group_disclosure` gains a
  keyword-only `already_reported_contact_ids` parameter that splits the first-disclosure branch
  three ways — silent (every member already reported), a delta clause naming only the unreported
  members (partial), or unchanged full disclosure (none reported) — reusing the existing
  branch-4 delta taxonomy rather than inventing a second "new at time zero" rule. Scoped to the
  first disclosure only; every later branch (leader change, first differentiation, arrival delta,
  otherwise-silent) is untouched. New `CalloutScheduler._already_reported_member_ids` computes the
  set per tick from the scheduler's own `_last_spoken_signature` plus the same merge-echo
  predicate the flood fix's `CONTACT_DETECTED` suppression uses — now factored into one shared
  `_is_merge_echo_of_earlier_contact` helper so the two call sites cannot drift apart silently
  (Reviewer's optional finding; sharing was possible after all, despite the two call sites asking
  the question from an event vs. from group membership). Real sortie-1004 evidence: 1 of 5
  group-level spoken lines in the sortie confirmed suppressed by object id (`t_sim=730.9`), 1 more
  strongly suspected (`t_sim≈1021.9`), 3 unaffected. 5 new tests, zero regressions: 1414
  passed/4 xfailed (up from 1409/4). `ruff`/`mypy --strict` clean. Does **not** touch the settled
  delta taxonomy for later arrivals, and does **not** close `BL-B24` or
  `plans/contact-duplication-ambiguity-runaway/plan.md` — the root `ContactStore.ingest`
  "2+ candidates → always a new contact" policy is still open; both items now carry a note saying
  this fix doesn't close them either, same as the flood fix before it.

  **Known residual, recorded not fixed**: `_already_reported_member_ids` evaluates the merge-echo
  predicate at the *current* tick, not at the tick the original suppression happened. If the echo
  source has since gone `lost` or drifted apart enough that `contacts_plausibly_same` now reads
  false, a genuinely-already-suppressed member stops counting as reported and the group's first
  disclosure could re-speak content that, strictly, already reached the pilot. This errs toward
  speaking (the opposite of "prioritize less speaking"), but is bounded to the first-disclosure
  window only and is not a correctness or no-omniscience issue. See
  `plans/redundant-group-disclosure/implementation.md`.

  **Milestone completion question**: does not change what's next or invalidate a downstream
  assumption — a self-contained addition to one existing branch of `render_group_disclosure`,
  gated by a new optional parameter that defaults to the old always-full behaviour.

## Backlog (body-layer)

**Moved to `body-layer/BACKLOG.md` on 2026-09-27** — items keep their `BL-B<n>` ids. This file
stays the source of truth for milestone status; the backlog lives next door so that editing one
does not re-extract the other into the knowledge graph (that file's own header has the reasoning).

## Rejected

- **Persistent omniscient mission-memory store, upstream of perception filtering — REJECTED
  2026-09-10.** A performance angle (avoid DCS LOS queries via a coarse world-model precheck) rested
  on a false premise: `line_of_sight_clear` already samples world-model's *local* elevation grid, not
  a live DCS call. Do not revive without a new concrete trigger. `plans/omniscient-mission-memory/plan.md`
  (never merged) has the proposed pipeline for the record.
