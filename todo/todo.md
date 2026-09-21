# Todo

**Milestone status, backlog, and deferred items live in `../ROADMAP.md` (cross-subproject) and
each subproject's own `ROADMAP.md`** (`world-model/ROADMAP.md`, `aircraft-layer/ROADMAP.md`,
`body-layer/ROADMAP.md`) — not here. This file only holds User priority tasks and cross-cutting
items that don't yet belong to one subproject's roadmap. See root `ROADMAP.md`'s "Keeping this
current" note for how staleness is prevented: the `/merge` skill and the DoD agent both require
the relevant roadmap to be updated in the same push as any merge.

## User priority tasks
Prioritize any open task here over any other task in this file or roadmap files.

- [x] Route crew-text speech callouts ("tank, 12 o'clock, 3 km" style contact reports, from
  `body-layer/src/belief/speech.py`'s `render_contact_report`/`route_event`) to the in-game
  Petrobrain overlay (`aircraft-layer`'s `POST /text/push` channel, `--overlay` flag). **Done
  2026-09-12, merged to main:** routing mechanism (`_print` sink, `"!! "` urgent prefix);
  lifecycle-content fix (proper unit type/clock/range/enrichment instead of raw classification
  enum); a third live-test round made crew-text output terser per pilot-usability feedback — no
  contact ids, `CONTACT_LOST` unreported, `CONTACT_CLASSIFICATION_CHANGED` gained a
  position-bearing line, `"UNKNOWN"` coalition placeholder dropped, range/enrichment distance
  rounded; `OP_GROUPSOMETHING` (ED's unclassified-unit fallback) mapped to `"group"`. All rounds
  live-acceptance-tested and confirmed by the user. Full history: `plans/overlay-speech-callouts/`.
- [x] Create integrity audit skill, see instructions @todo/integrity-audit-skill.md — `.claude/skills/integrity-audit/SKILL.md` created 2026-09-08. 6-phase diagnostic audit (inventory → cross-file consistency → staleness → genericity leaks → duplication/dead mechanisms → memory hygiene → classify+report); never self-edits config, writes dated report to `audits/system-integrity/`.
- [x] claude workflow changes — `AGENTS.md` updated 2026-09-08: new "Auto-Advance" section (proceed through Architect → Implementer → Reviewer → (loop) → DoD without stopping between stages) and Escalation Rules extended with the local/reversible/non-material autonomy criterion. Existing `UserPromptSubmit` hook already injects "apply automatically, no user input needed" each turn — left as-is per user decision to observe first; hook mirror-update deferred unless AGENTS.md alone proves insufficient.
    - [x] move automatically to next stage in worklfows: architecht -> implementor -> reviewer -> (loop back to implementer if fixes are needed) -> DoD. If there is genuine ambiguity or need for user input/verification/perception, stop and hand to user. In normal cases, proceed to next step in workflow.
    - [x] If multiple reasonable technical approaches exist, choose one when the tradeoff is local, reversible, and does not materially affect product behavior, future architecture, dependencies, cost or risk. Escalate consequential or difficult-to-reverse decisions or where there is ambiguosity about expected behaviour.
- [x] Roadmap restructure (2026-09-10): split milestone/backlog narrative out of this file into
  root `ROADMAP.md` plus per-subproject `world-model/ROADMAP.md` / `aircraft-layer/ROADMAP.md` /
  `body-layer/ROADMAP.md`. Reason: an integrity check found this file had drifted — three merged
  milestones (BL-3, BL-4, BL-5) and one merged feature (`overlay-clock-range-summary`) were
  missing entirely, because the "update the backlog" step was easy to skip and not enforced at
  merge time. Fix applied at the process level, not just the data level: `.claude/skills/merge.md`
  and `.claude/agents/dod.md` now both require the relevant `ROADMAP.md` to be updated *in the
  same push* as any merge — see root `ROADMAP.md`'s "Keeping this current" note.


### Model the 9K113 sight as an optic (deferred, 2026-09-20)

- [>] **Model the 9K113 Raduga-Sh as a selectable optic.** Deferred by the user while cones slice 1
  ships the naked eye and binoculars only. Not blocked on research — the groundwork is already done:
  - **Figures are recorded** in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`,
    by confidence class. Field of regard ±60° lateral, +20°/−15° vertical (sourced, English manual
    §3.4). Magnification ×3.3 wide / ×10 narrow, switchable in flight (`LCtrl+X`). Fields of view
    11.5° / 6.0° (user-supplied, unverified — and the pair is internally inconsistent, so 6.0° is
    the figure to doubt first).
  - **Calibration ground truth already exists.** `body-layer/tests/fixtures/vision_calibration.json`
    grades `9k113_wide` and `9k113_narrow` at all nine ranges alongside `naked_eye` and `binocular`.
    No sortie is needed to calibrate this — the screenshots were taken with all four columns.
  - **Three things the eventual slice must get right**, each already argued out: two optic entries
    rather than one plus a zoom state (magnification is switched in flight, and either mode can use
    either field); field of view and field of regard as *separate* fields (they differ by an order
    of magnitude — a few degrees seen at a time, anywhere within a 120°-wide arc); and the doors as
    real state (`НАБЛ.` opens the outer doors, needs hydraulic pressure, closing runs inner then
    outer — so "Observ off" means the sight genuinely cannot see, not merely that it is unselected).
  - **Depends on mode selection**, which is cones slice 2. An optic nothing can select is table data
    nothing reads — the reason the 9K113 entries were cut from slice 1 in the first place.
  - Also recorded there and relevant: the operator commands an angular **rate**, not a position, so
    pointing the sight costs time proportional to angular distance; the gyro-stabilised head needs
    **~3 minutes** from power-on before it is ready; and launch entry requires the sight line within
    0.86° of the airframe axis, which is a *firing* constraint and not a *seeing* one.


### Probe the mission-sandbox bridge (Investigator + Windows box)

- [ ] **Probe whether `net.dostring_in` into the DCS mission scripting sandbox is reachable** from
  this project's `Export.lua`/Hook setup in single-player, and what it costs per poll. Raised
  2026-09-21. **This one probe unblocks two parked items**, which is why it is worth its own entry
  rather than sitting inside either:
  - **Unit velocity** for movement detection — `Object.getVelocity()` lives in the mission scripting
    environment and returns a vec3 per unit (`aircraft-layer/research/
    2026-09-21-unit-velocity-via-mission-scripting.md`). With the bridge, movement detection gets an
    exact `v⊥` instead of differencing two samples of a 5 Hz position feed.
  - **Fog and visibility state** — "detection under real world conditions", factor 3. The
    2026-09-20 deep read found Export carries no fog at all and named this bridge as the only
    candidate route.
  Deliverables: does it work in single-player; per-poll cost; whether results can be returned
  synchronously or must be pushed back through a side channel. **Do not design against the bridge
  before this is answered** — differencing positions remains the fallback for movement.


### Scan geometry: drop the invented radius (user direction, 2026-09-21)

- [x] **Remove `F10_SCAN_RADIUS_M` and make a sector scan unbounded. DONE, merged 2026-09-21.** User direction: *"get
  everything visible within a sector"* instead of a made-up cutoff. `belief/crew_console.py`'s
  `F10_SCAN_RADIUS_M = 3000.0` exists only because an F10 button carries no geometry the way the
  typed `scan-area <bearing> <range> <radius> <reason>` does, so the code had to invent a number.

  **The real objection is not that 3000 m is the wrong value — it is that the radius is a second,
  arbitrary limit layered on top of the real one.** What should bound a sector scan is what
  Petrovich can actually see. Measured against the current naked-eye envelope the constant is
  *non-binding for every ground unit* (armour 2333 m, Ural 2000 m, infantry 600 m are all inside
  3 km) and *wrongly binding* for the one thing that beats it — the S-300 mast at 8000 m, which a
  3 km area would have excluded from a scan that should have found it. A cutoff that does nothing
  except in the cases where it does the wrong thing is worse than no cutoff.

  Shape: `AttentionArea.radius_m` becomes `float | None`, `None` meaning unbounded, and
  `area_contains` skips the range test for it. The wedge still applies. The typed `scan-area`/
  `watch-area` console commands keep supplying a real radius — nothing about explicit geometry
  changes. Touches `belief/attention.py`, `tools.py`, `crew_console.py` and the task store, so it
  is a small data-model change rather than a constant deletion.

  Note it composes with the open "Scan commands should drive naked-eye perception" item: once a
  scan steers perception, "unbounded" means "as far as the optics and conditions allow", which is
  the honest answer and needs no constant at all.

- [>] **Anchored limited scan — "scan around that landmark / that unit" — deferred to the brain
  layer.** The other half of the same user direction: *"on purpose command a limited scan, probably
  around a landmark or another known unit."* A radius is genuinely meaningful there, and it comes
  from the thing being scanned rather than from a constant — a landmark's own extent, or a
  contact's position uncertainty.

  **This needs the brain layer, not merely voice** (user, 2026-09-21). An earlier draft of this
  entry deferred it to the voice era on the F10-scoping precedent — that richer command forms belong
  to BL-10/SRS, since a dynamically rebuilt contact list means collector-to-Hook menu pushes and
  `removeItemForGroup` traffic mid-flight for a menu the player still clicks through. That reasoning
  holds for the *input channel* but understates the requirement.

  Resolving *"that landmark"* or *"that unit"* is not transcription, it is **reference resolution
  against shared crew context** — which of the things we have both seen, and talked about, does
  "that" mean. That is the runtime cognition layer's job (`docs/concept/PETROBRAIN_RUNTIME.md`), not
  the transport's. A perfect transcript of "scan around that ridge" still leaves the hard part
  undone.

  `find_place` (`belief/tools.py`, backed by `query.search.find_place_by_name`) already resolves
  names to positions, so *name → place* is not the blocker. *Deixis → referent* is.

## Cross-cutting / unscoped backlog

- [>] **Re-enable the performance-reviewer and security roles, and run a catch-up audit of what
  shipped while they were exempt. Deferred until Stage 4b of the group contact model is done**
  (user, 2026-09-19) — not because the finding is weak, but because interrupting the current run
  to re-audit would cost more than the risk carries today.

  **Both exempted roles independently reported their own exemption has gone stale**
  (`/retro`, 2026-09-18). `CLAUDE.md` says: *"Skip performance-reviewer and security for now — this
  phase is an offline single-user local pipeline with no hot path and no untrusted-input surface
  yet."* That was written for the World Model Builder's offline phase. It no longer describes where
  the work happens.

  **Performance reviewer's case:** this week's changes landed in `aircraft-layer` and `body-layer`,
  which are live runtime paths, not the offline pipeline the exemption describes. Two specific
  candidates: `AudioPlaybackSender`'s worker thread and queue, which carries an explicit
  interrupt-*timing* correctness requirement, and `perception.clustering`'s O(n²) single-link pass
  running **every poll**. Its recommendation is to narrow the exemption's scope to `world-model/`
  explicitly, so runtime subprojects stop being swept under a phase description they have left.

  **Security's case, which contradicts a judgement already recorded elsewhere:** `POST /audio/play`
  was merged with the framing *"same severity class as what already exists, not a new category"*
  (`plans/tts-voice-output/plan.md` Decision 6, relayed to the user as settled). Security disagrees,
  and the disagreement is about the right axis: the existing unauthenticated endpoints push overlay
  text and trigger in-sim commands, with effects confined to the **DCS process**. Audio playback
  reaches the **host OS** — arbitrary content from any LAN device reaching the user's speakers — and
  audio-play primitives have a history of path/codec-confusion and resource-exhaustion issues that
  text overlays do not. Its reading is that this crosses the exemption's own stated line, *"no
  untrusted-input surface yet"*, because the LAN is now an input surface. The earlier framing
  reasoned about authentication being unchanged; severity is determined by blast radius, which
  changed.

  **When picked up:** narrow or lift the `CLAUDE.md` exemption, restore both roles to the sequences
  in `AGENTS.md`, and run a Mode-2 deep analysis on `POST /audio/play` plus a performance pass on
  the two candidates above. Note the exemption is a *phase* decision — the lesson worth carrying is
  that it needed a re-scope trigger and had none, which is the same failure shape the retro found
  in four roles' memory files.


- [ ] **`console.py`'s typed `scan-area` still drives the 9K113.** Found by review 2026-09-17,
  while checking the F10-path fix (`89b8b1d`). `body-layer/src/belief/console.py:548` calls
  `aircraft_client.trigger_petrovich_search("forward")` under the name "Scan" — the identical
  semantic mismatch just removed from `crew_console._handle_scan`, where *Scan* is naked-eye
  perception and *Observ* is the 9K113 (`docs/concept/state-transitions.jpg`'s glossary).

  Left out of `89b8b1d` deliberately: it is pre-existing, `--console`-only (a developer debug
  tool), and no crew or F10 path reaches it, so folding it in would have expanded a reviewed
  commit's scope for no in-flight benefit. But it is not merely mechanical either — `scan-area`
  is the *typed* command that takes explicit geometry, so "what should it trigger instead" has a
  real answer to pick: nothing at all (matching the F10 path), or a future `Observ` once that
  verb exists. Decide that when `console.py` is next touched, rather than copying the F10 fix
  blindly.

  Until then the repo contains two paths named "scan" that do different things, which is exactly
  the kind of contradictory precedent a future reader would follow in the wrong direction.


- [ ] **Scan commands should drive naked-eye perception.** Raised 2026-09-16 from the first live
  F10 test of `f10-command-vocabulary`; narrowed 2026-09-17 once `cockpit-visibility` shipped.

  **A scan changes attention, not perception.** `perception/visibility.py`'s naked-eye gate uses a
  fixed cockpit occlusion mask (`perception.cockpit_mask`, `plans/cockpit-visibility/plan.md`) that
  no command steers, so "scan left" registers an `AttentionArea` and a `PendingIntent` but does not
  change which contacts are detected. It raises attention on things the fixed mask already found.
  The 9K113 trigger removed on 2026-09-16 (`fix/scan-naked-eye-not-9k113`) was the only observable
  effect a scan had, and it was the wrong organ — so scan is now honest but perceptually inert
  until this is built.

  The mask's own mis-sourcing is now fixed — `NAKED_EYE_FOV_HALF_WIDTH_DEG` (the 9K113's angular
  limit, not a human-through-glass figure) is gone, replaced by a body-relative
  depression-per-azimuth mask derived from real co-pilot cockpit screenshots
  (`plans/cockpit-visibility/plan.md` D7 — still uncalibrated, ±10-15° at best, same debt class as
  `visibility.py`'s own tier constants, but at least sourced from the right thing now).

  What the full version looks like, per the spec diagram: a steered *sub-window* within that mask
  that follows the commanded sector for the task's duration, plus the diagram's default-state sweep
  (`ahead → left → ahead → right`), dwell time per sector, and naked-eye vs binocular tier varying
  with how long Petrovich has been looking somewhere. That needs a dwell/attention scheduler that
  does not exist. Composes with, not duplicates, the static mask (`plans/cockpit-visibility/plan.md`
  D4): the mask is what the airframe permits him to see at all, always applies; scan steering is
  where he is currently looking within that, dynamic. Effective visibility is the intersection.

  Deliberately deferred by user direction 2026-09-16 ("write entry in backlog for full pattern
  simulation, but for now simply remove 9K113 trigger").


- [ ] **Stage 5 road junctions: pathological single-chunk stalls — CONFIRMED DATA-DEPENDENT.** Raised
  2026-09-16 from the `syria-full` build log validating `osm-landcover-optimization`. Stage 5 took
  2885 s, and a large share of that sat in a handful of chunks: chunk 13867→13868 took 331 s and
  chunk 14017→14018 took 337 s (one chunk each), with two further ~330-350 s near-stalls around
  them — roughly 28 of the 48 minutes in a few chunks. This is exactly the gap `b260ee7`
  (road-junction progress logging) named as remaining: *"nothing is logged during a single slow
  chunk."* Confirmed in the wild, plus a second symptom — the ETA swings badly during a stall
  (495 s → 1657 s remaining), so the estimate actively misleads. Two separable pieces of work:
  (a) log progress *within* a chunk, or at least emit a "chunk N still running, Xs elapsed"
  heartbeat so a stall is distinguishable from a hang; (b) find out why those specific chunks are
  so expensive (dense urban road clusters? a union-find degenerate case?) — the fix may be a
  chunk-splitting heuristic rather than better logging. Not scoped to a milestone; `world-model`.

  **Update 2026-09-16 — reproduced on a second machine, at the identical chunk indices.** A Mac
  `syria-full` build hit exactly the same four chunks (13867, 13868, 14017, 14018) that stalled on
  Windows, at ~170 s each versus Windows' ~330 s. Same indices, different OS and different CPU, so
  this is a property of the *data in those chunks*, not of the machine — which makes (b) tractable:
  those four chunk bounding boxes can be extracted and profiled directly rather than hunted for.
  They cost ~680 s of the Mac run's 1,038 s total, so fixing them is most of Stage 5's wall-clock.
  Stage 5 overall was much faster on the Mac (1,038 s vs 2,885 s), as were roadnet (444 s vs 670 s)
  and SRTM (4.4 s vs 11.3 s).

  Unrelated caveat when reading `world-model/syria-full-build.log`: it contains a 2.5-hour wall-clock
  gap mid-Stage-5 that is **not** a stall. The host slept. The progress lines' own `elapsed` counter
  advanced only 201 s across it, because `ingest_junctions`/`roadnet.routes` both use
  `time.monotonic()`, which on macOS does not tick during system sleep. Wall-clock timestamps and
  logged elapsed disagree by design there.

- [ ] **`syria-full` pipeline logs only 6 of 8 stages.** Raised 2026-09-16 from the same build log.
  Output goes `[6/8] SRTM elevation grid: done` straight to `Built ...` — `[7/8]` and `[8/8]` never
  appear. `probe: skipped (probe_output_path not given or not found)` accounts for at most one of
  them. Either the remaining stages are silent (no `starting`/`done` lines, unlike stages 1-6) or
  `_TOTAL_STAGES` overcounts. Cosmetic but misleading during a ~1 h build. `world-model`.

- [ ] **SRTM: 131 tiles staged, `tiles_used=79`; 7.4% of points void-or-uncovered.** Raised
  2026-09-16 from the same build log. The pipeline header reports `SRTM elevation grid (131
  tile(s))` but `SrtmIngestStats` reports `tiles_used=79` — 52 staged tiles contributed nothing.
  Separately `points_void_or_uncovered=47484` of `points_expected=639216` (7.4%). The M7 entry
  already records 92.6% coverage as an accepted result, so this is likely the known gap rather
  than a regression, but the 131-vs-79 discrepancy is unexplained and worth one look: if the 52
  unused tiles are outside the region bbox that is fine and the header should say so; if they
  overlap it, coverage is being lost. `world-model`.

- [ ] **Pin `CLASSIFIER_VERSION` bump discipline with a test.** Raised 2026-09-16. The comment
  above `CLASSIFIER_VERSION` (`world-model/src/build/ingest_osm.py`) lists the conditions that
  force a bump; `638239a` met two of them and landed without one, and was caught only by reading a
  build log weeks later. Nothing mechanically enforces the rule. Options: hash the relevant
  functions'/dataclass' source and assert the digest matches a pinned value alongside the version
  (fails loudly on any edit, forcing a conscious bump), or derive the cache key from such a digest
  instead of a hand-maintained integer. The second is the real fix but changes the invalidation
  key's shape. `world-model`.


- [ ] **Landmark references must be LOS- and knowledge-gated, not ground-truth.** Raised
  2026-09-13, while scoping world-model tactical-landmark enrichment (ridges/valleys,
  settlements, road intersections, other aerial landmarks — see
  `plans/world-model-tactical-landmarks/plan.md` once it lands). World-model can compute
  "this unit is 500m from a road intersection, south of a large building," but per this
  project's no-omniscience invariant, Petrovich/the brain must never speak a landmark
  reference the crew has no actual basis for knowing. Two independent gates, both needed:
  1. **Line-of-sight**: can we (or Petrovich) actually see the landmark itself right now, using
     the generalized A↔B LOS primitive (`plans/world-model-los-generalization/plan.md`,
     `query.line_of_sight.line_of_sight_clear`) applied ownship/Petrovich → landmark position,
     not just ownship → contact.
  2. **Knowledge**: do we have a standing memory of that landmark (a prior perception/
     observation of it — this is squarely BL-8's future territory), or does the Mission
     Understanding / briefing (Mission Interpreter's schema, `plans/mission-interpreter/
     plan.md`) name it explicitly? If neither, the landmark is not known and must not be
     referenced, even if world-model's query layer can compute its existence and position from
     ground truth.
  **Not scoped to a milestone yet** — spans world-model (landmark data + LOS query),
  mission-interpreter (briefing-named landmarks as a knowledge source), and body-layer
  (the actual gating logic before a landmark reference reaches speech output, likely a
  `belief/` concern parallel to `percept.py`'s existing DCS-truth-stripping boundary). Revisit
  once world-model's landmark enrichment and a first Mission Understanding schema both exist.

- [>] **"Wingman brain" — a much later, far-future direction.** Raised 2026-09-13, deliberately
  deferred, not scoped. Combines observation + flight control + world perception from a
  *non-player-position* aircraft — i.e. an AI-controlled wingman with its own Petrobrain-style
  cognition, not just Petrovich riding along in the player's own cockpit. A materially different
  architecture from everything built so far: today's aircraft-layer/body-layer split assumes
  perception is anchored to the player's own ownship telemetry throughout (`OwnshipState`,
  `perception/geometry.py`'s bearing/range math, `aircraft_client`'s `/telemetry/latest`). A
  wingman brain would need perception/state for an aircraft that isn't the player's — a new
  telemetry source, not a reuse of the existing one. Do not start scoping this until the current
  three-layer architecture (world model, mission interpreter, body/brain layer) is mature and
  proven for the single-player-aircraft case first.
