# Todo

## User priority tasks
Prioritize any open task here over any other task in this file or roadmap files.

- [x] Create integrity audit skill, see instructions @todo/integrity-audit-skill.md — `.claude/skills/integrity-audit/SKILL.md` created 2026-09-08. 6-phase diagnostic audit (inventory → cross-file consistency → staleness → genericity leaks → duplication/dead mechanisms → memory hygiene → classify+report); never self-edits config, writes dated report to `audits/system-integrity/`.
- [x] claude workflow changes — `AGENTS.md` updated 2026-09-08: new "Auto-Advance" section (proceed through Architect → Implementer → Reviewer → (loop) → DoD without stopping between stages) and Escalation Rules extended with the local/reversible/non-material autonomy criterion. Existing `UserPromptSubmit` hook already injects "apply automatically, no user input needed" each turn — left as-is per user decision to observe first; hook mirror-update deferred unless AGENTS.md alone proves insufficient.
    - [x] move automatically to next stage in worklfows: architecht -> implementor -> reviewer -> (loop back to implementer if fixes are needed) -> DoD. If there is genuine ambiguity or need for user input/verification/perception, stop and hand to user. In normal cases, proceed to next step in workflow.
    - [x] If multiple reasonable technical approaches exist, choose one when the tradeoff is local, reversible, and does not materially affect product behavior, future architecture, dependencies, cost or risk. Escalate consequential or difficult-to-reverse decisions or where there is ambiguosity about expected behaviour.


## Current Focus

World Model Builder good-enough, gate lifted 2026-09-06 (user decision: move to rest of chain to test/improve end-to-end). Aircraft layer (DCS I/O + API, per `docs/concept/division-or-responsibility.md`) — **done, merged to main 2026-09-07** (`51654ec`). PB-1 (text-only perception logger / BL-0 + BL-1 scaffolding) — **done, ready to merge 2026-09-08**. World Model's own backlog (M9 OSM, incremental per-layer builds) stays deferred/unscheduled — see `world-model/ROADMAP.md`.

**PB-1.5 (done, merged to main 2026-09-09).** `feature/pb1.5-naked-eye-detection`. A second,
independent perception channel: `NakedEyePerceptionSource` reports plausibly-visible ground objects
from `LoGetWorldObjects`, gated by FOV + angular-size + terrain-LOS, and quantised to ED's own
callout vocabulary (12 clock bearings, 24 range buckets, coarse class). New modules
`object_model.py`, `visibility.py`, `naked_eye_source.py`, `reporting_names.py` plus ED's committed
595-row DCS-type→reporting-name mapping. 102 body-layer tests.

*The milestone's central question was answered, and the answer was negative.* A purpose-built live
probe (`aircraft-layer/dcs-export/Export.probe-pb15.lua`, flown as an OBSERV OFF / OBSERV ON A/B)
established that **DCS's ambient contact callout has no Lua-readable companion** — `list_indication(6)`
produced zero change events across the whole sight-off segment while `GROUND, 11 O'CLOCK` and
`GROUND, 12 O'CLOCK` appeared on screen, and the HelperAI tree is not even instantiated until the
sight comes on. So the synthetic filter is not a fallback awaiting a better signal; it is the only
implementation. Full findings: `aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`.
Also recovered from the module's own Lua: ED's detection constants (`HelperAI.lua`) and the composed
callout vocabulary (`HelperAI_lengths_ng.lua`), both in
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`.

*Key decisions:* the channel deliberately models a **binocular-aided** observer (`medres` 0.008 rad
x 4.0), not the unaided eye — the user's choice, so "naked-eye" is now a misnomer the code docstrings
warn about. `NAKED_EYE_RANGE_CAP_M` was raised 2500 → 5000 m so the per-type size curve, not the cap,
does the discriminating (infantry 900 m, truck 3000, T-72 3500, SA-3 4500; only ships cap).

*One live bug, found and fixed:* the first sortie reported the ownship itself as a contact —
`LoGetWorldObjects` is unfiltered and includes the player's aircraft, which neither channel excluded.
Fixed in both channels (`association.exclude_ownship`); the scope channel had the same latent bug.

*Open follow-ups, none blocking:* tier calibration against the user's "if the player can see a unit,
Petrovich should too" standard (infantry at 900 m is the tightest); identity-based rather than
proximity-based ownship exclusion; ground-unit classification coverage at 60.1% by deliberate choice.
All in Backlog.

*Does this change the next milestone?* **No architectural change for PB-2/BL-2.** Both channels
already flow through the uniform `PerceptionSource` interface, so "the synthetic channel is primary"
is a framing and priority shift, not a contract change. What it does raise is the priority of the
scope channel's known defects — the user confirmed that channel stays, being needed for future
acquire/lock/fire gameplay.

**PB-2 / BL-2 (done, merged to main 2026-09-09).** Contact memory and data association over
time. All stages complete: -1 (aircraft-layer `is_ownship` flag, replacing the old
`association.exclude_ownship`/`OWNSHIP_ECHO_EXCLUSION_RADIUS_M` proximity heuristic), 0
(scope-channel type-namespace repair — `association._type_match_score` now resolves DCS type
names through `reporting_names` before scoring, and `hybrid_source.py` emits one `Observation`
per distinct HelperAI list-text leaf), 1 (belief core — `belief/percept.py`'s `Percept`
projection structurally drops all DCS truth fields; `belief/contacts.py`'s `ContactStore`;
`belief/association_over_time.py`'s three-valued spatial+class gating), 2 (decay/certainty
ladder — `observed`/`tracked`/`estimated`/`lost` — and detected/lost/reacquired lifecycle events
in `belief/decay.py`/`events.py`), 3 (`emit_mode` on both sources, `--console` pipeline wiring),
4 (`belief/tools.py`'s `get_contacts`/`describe_contact`/`get_contact_history`/`find_contact` —
the brain API's body, minus a transport — plus `belief/console.py`'s debug REPL), 5
(cross-channel fusion validated by fixture). All five review passes approved with zero required
fixes; DoD ran the file-level gate (`plans/pb2-contact-memory/dod-check.md`) pending Stage 6.

**Stage 6 (live acceptance) passed 2026-09-09.** User flew a real sortie against `--console`.
One real bug found and fixed live: `--console`'s poll thread queried a `world_model_conn` opened
on the main thread — `sqlite3.Connection` is thread-affine, so this crashed on first poll.
Fixed by opening the connection and building sources on the poll thread itself
(`_run_console_poll_loop`), with a new regression test that drives a real sqlite connection
across a real thread boundary (the class of bug `test_logger.py`'s fakes structurally couldn't
catch). Two small live-testing UX fixes followed: the poll loop's periodic contact-count print
was flooding the REPL (`output=None` in console mode; state now queried on demand via
`contacts`/`stats`), and the REPL now prints a command-help banner at startup
(`belief.console.HELP_TEXT`). User confirmed live: naked-eye already discriminating
`OP_SRSAM`/`OP_MRSAM` at range, contact/certainty/decay output looked correct (`estimated`
aging via `last seen Ns ago`), `stats` reporting plausible counts (91 contacts / 179
observations / 91 events over one sortie segment).

*Does this change the next milestone?* Per the plan's "Second-Order Effects": unblocks BL-3
(world enrichment — `Contact` is the record it enriches, `project_from_bearing_range` is the
explicit stub BL-3 replaces) and BL-5 (`tools.py` already returns the frozen response shape,
BL-5 reduces to attaching a transport) cheaply; narrows future DCS-truth access (the `Percept`
boundary is now the thing any later feature must justify crossing); complicates BL-4 (must build
policy on the `certainty` table/bare attention enum landed here, not restate them) and BL-9
(belief-vs-truth visualisation should read the observation log, not source internals). One
real backlog item surfaced during Stage 5 fixture validation, not by live evidence: BL-2's
`certainty`/classification fusion is last-writer-wins, not quality-weighted (see Backlog) —
live sortie evidence didn't surface this as an actual problem this time, but it's unresolved.
Six other independent items were raised alongside this milestone and filed to Backlog rather
than folded in: aircraft-layer export-throttle split, live FPS measurement for
`LoGetWorldObjects`, a DCS radio-panel SRS-fallback output channel, and a much-later attention
direction/detection-cones milestone.

*Confirmed:* `PerceptionSource` needs no protocol change — BL-2 consumes both channels through the
existing interface. But planning found three defects in already-merged PB-1/PB-1.5 code that BL-2
would otherwise inherit, all verified against the source: `Observation.id` collides across channels
(both mint `OBS_{n}` from their own counter); the source-level on-change debounce would starve a
decaying belief layer (a statically visible tank emits once, then ages to "lost" while Petrovich
stares at it); and `derived_world_position` carries exact DCS truth into records belief code reads.

*Core design decision:* contact identity never consults `object_id` or any truth field — identity
is geometric, from perceived attributes only. Not conservatism about the 2026-09-09 id-stability
evidence: a passthrough of the DCS key would make Petrovich incapable of confusing two identical
trucks, which is the omniscience CLAUDE.md forbids. Consequence: unstable ids would degrade the
observation *rate*, never corrupt belief.

*Staging:* **-1** aircraft-layer ownship flag (prerequisite, own branch) → **0** scope-channel
repair → **1** belief core → **2** decay/certainty/lifecycle → **3** emission policy → **4**
tools+console → **5** fusion validation → **6** live sortie (user-only). Stages 0–5 are
fixture-testable.

*User decisions on the plan's three escalations (2026-09-09), recorded in the plan:*
1. Stage-0 scope-channel repair **is in scope**, with the emphasis note that the scope channel
   matters for future target acquisition/firing — so for now it is repaired and *fixture*-validated
   while BL-2's live acceptance rides on the naked-eye/binocular channel. Stage 6(a) is best-effort,
   not a gate.
2. Ownship: **flag it in the aircraft layer per the Backlog item, and do it first** (the plan had
   recommended accept-as-caveat; user chose the stronger fix). BL-2 is the layer that turns the 50 m
   window from a silent gap into a *wrong belief* — a contact goes "lost" exactly when the aircraft
   is closest to it — so fixing it first means BL-2 is never built or tuned against that artefact.
3. BL-2 **does** emit a minimal one-line `summary` per contact. Settles `plans/body-layer/plan.md`
   §10 decision 4 for BL-2's scope.

*Next action:* stage -1 on branch `feature/ownship-flag` (created off `main`, currently empty — no
commits). Spec is the Backlog item below. Needs a live sortie leg to verify `LoGetPlayerPlaneId()`,
since the flag's correctness cannot be established from fixtures.

*Session note:* PB-1's completion does not invalidate or change downstream assumptions for BL-2, but
BL-2 should consume both detection channels (scope + naked-eye) rather than being built against the
scope-only channel and reworked later.

**BL-2.5 (in progress, started 2026-09-09).** `feature/dcs-text-panel-output`. In-cockpit text
mirror: a small scrolling DCS overlay window fed by a new write-back channel through the aircraft
layer, so live sortie testing can be read in-cockpit instead of alt-tabbing to an external log.
Promoted from the Backlog to an interim milestone ahead of BL-3 by user decision, 2026-09-09.

Two Investigator passes settled the DCS-internals questions
(`aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md`); ED's Hook-state API doc is
vendored at `aircraft-layer/research/reference/Sim_ControlAPI.md`. The Export environment cannot
write to screen at all, so the channel is a **GUI/Hook-state overlay** (`Saved Games/DCS/Scripts/
Hooks/`) built on DCS's own `AutoScrollText` widget, fed by loopback UDP from the collector —
modelled directly on SRS's installed overlay, which is the same pattern working in production. The
`net.dostring_in` → `trigger.action.outText` bridge was rejected: it needs an `autoexec.cfg` opt-in
ED itself labels obsolete/unsafe, and shares DCS's global message queue.

Transport: body-layer → `POST /text/push` (new) → collector → loopback UDP 7792 → Hook script. This
is the **aircraft layer's first inbound/write path**; `aircraft-layer/CLAUDE.md`'s "read-only
telemetry pipeline" framing is rewritten as part of the milestone. Wire schema is deliberately
content-only (`{"text": ...}`) so BL-10's SRS-fallback channel can reuse the transport with a
different producer.

Stages: 1 aircraft-layer transport (no DCS) · 2 overlay Hook script (needs DCS, cheap smoke check) ·
3 body-layer wiring (fixture-tested) · 4 live acceptance sortie (**user-only**, folded together with
the backlogged `LoGetWorldObjects` FPS measurement). Full plan, decisions, and risks:
`plans/dcs-text-panel-output/plan.md`.

**Stages 2 and 4 passed live 2026-09-09** — contact events render in-cockpit during a real sortie.
Reviewer approved stages 1/3 with no required fixes (`plans/dcs-text-panel-output/review.md`).
Seeing it live, the user raised that the result imitates DCS's native radio message panel rather
than being it, and **decided to keep the overlay and restyle it** rather than take the
`net.dostring_in` → `trigger.action.outText` path (rationale recorded in the plan's
"Output-target decision, revisited after live acceptance"). Refinement pass in progress: strip the
window chrome copied from SRS, plus two defects the live screenshot exposed — overlay lines carry
no contact id, and the window clips its last line. Needs one more short confirmation sortie
before DoD.

**Aircraft layer (done, 2026-09-07):** `feature/aircraft-layer-telemetry` merged to main. Export.lua → Windows collector → LAN `/telemetry/latest` API, live-tested against cockpit instruments (bank/IAS/heading/alt all match), 5 Hz export-rate bug found+fixed, `altitude_radar_m` stays null (deprioritized — use `altitude_agl_m` instead, confirmed equivalent), `/telemetry/since` dropped as unneeded scope. `aircraft-layer/CLAUDE.md` + `WORKFLOW.md` document the subproject. Full history: `plans/aircraft-layer/implementation.md`.

**PB-1 (done, 2026-09-08):** `feature/pb1-perception-logger` ready to merge. Stages 1–3 (live spike, BL-0 harness, world_objects endpoint) completed earlier; stages 4–9 (hybrid HelperAI perception source + association + text logger) completed with zero Reviewer required fixes across two review passes. Live acceptance test (stage 7) ran end-to-end on real Mi-24P sortie with manually-placed ground targets; two observations logged with plausible bearing/range values in an ambiguous-candidate scenario (4 Ural trucks clustered together). The original architecture (two-tier branching on geometry source) was completely falsified by Session 4's live spike; pivoted to single hybrid implementation (HelperAI text as real detection gate, `LoGetWorldObjects` geometry via association algorithm). Full history: `plans/pb1-perception-logger/plan.md`, `implementation.md`, `review.md`, `dod-check.md`. Key lessons harvested to `NOTES.md`: live spikes resolve DCS architectural unknowns better than desk research; PYTHONPATH/venv gaps only surface in end-to-end deployment; ambiguous-scene live testing essential for association validation.

- [x] M0 — record installed DCS version + confirm Syria terrain present, in `world-model/research/`.
- [x] M1 (recon) — prove DCS x/z ↔ lat/lon transform for Syria against a known real-world control point; measure error. pydcs tmerc params confirmed against live install; real-world residual ~1.0-1.3km (terrain-placement error, not projection defect). See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M1 (implement) — `src/coordinates/` built per plan, control-point tests pass. Windows/WSL probes run: pydcs Syria tmerc params confirmed against live `coord.LOtoLL` (sub-meter match, 226 points); real-world residual ~1.0-1.3km vs published ARPs, explained as DCS terrain-placement error. See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M2 — Raster understanding. `src/raster/` (Pillow DDS loader + empirical registration), `tools/inspect_raster.py` diagnostic, control-point + held-out-point tests pass. See `world-model/ROADMAP.md` M2 entry and `plans/m2-raster-understanding/`.
- [x] M3 — OSM overlay. `src/osm/` (Overpass API fetch + in-memory parse), `tools/inspect_osm_overlay.py` diagnostic overlay, tests pass, held-out Gemerek validation. Attribution rendered onto output PNG. Spatial-storage choice deferred to M5. See `world-model/research/2026-09-03-m3-osm-overlay.md` and `plans/m3-osm-overlay/`.
- [x] M4 — DCS elevation. `src/elevation/` (`land.getHeight` live-mission probe via io/lfs, SRTM3 `.hgt` parsing), `tools/inspect_elevation.py` diagnostic, control-point + real-fixture tests pass. 100-point Gemerek grid vs SRTM3: mean delta +13.89m, west-edge outlier traced to real terrain-mesh-resolution mismatch, not a bug. `MissionScripting.lua` io/lfs edit intentionally left in place (more probes expected M5+). See `world-model/research/2026-09-03-m4-dcs-elevation.md` and `plans/m4-dcs-elevation/`.
- [x] M5 — First persistent model. `src/store/` (stdlib `sqlite3` + R*Tree, JSON geometry), `src/roadnet/` (DCS-native `.routes` binary parser), `src/dcs_data/` (towns/beacons Lua parsers), `src/query/describe_position`. Region: Latakia (`latakia-20km`). Real store: 3,266 roads, 338 settlements, 117 water, 108 named places, 1,681-point elevation/surface_type probe grid at 100% coverage, 8.57 MB `.sqlite`. Two real defects found+fixed: `pyproj.Transformer` per-call rebuild (perf), roadnet resync denormalized-float validation gap (correctness). `.rn4` graph decoding, airfield taxiways/structures, Latakia SRTM tile, full-theatre resync audit deferred to M6+. See `world-model/research/2026-09-04-m5-first-persistent-model.md` and `plans/m5-first-persistent-model/`.
- [x] M6 — Terrain semantics. Ridge/valley classification over `latakia-20km`'s elevation grid. `ridge=12, valley=12` at tuned thresholds, `confidence: "low"` on every feature — a real grid-resolution-vs-feature-scale limitation, not a bug. See `world-model/research/2026-09-05-m6-terrain-semantics.md`.
- [x] M7 — Full theatre pipeline. Scaled to the whole Syria theatre: SRTM-primary elevation, OSM dropped (deferred to a future milestone via geofabrik.de extracts), M6 terrain classifier out of scope. Real `syria-full.sqlite`: `road=14833` (exact match to independent census), 35 airfields, 1,182 named places, 461 MB, full rebuild 449.3s, `describe_position` p99 803ms (tail flagged as a follow-up, not blocking). All 8 theatre-spread control points within tolerance; SRTM-vs-DCS-probe spot-check mean delta -7.19m/stddev 11.52m, tighter than M4's baseline. `surface_type` stays `"unavailable"` theatre-wide — accepted, documented gap. See `world-model/research/2026-09-06-m7-stages-1-2-3-full-build-results.md` and `plans/m7-full-theatre-pipeline/`.
- [x] M8 — Incremental probe store. `src/probe_store/` (schema, writer, reader, paths), separate `-probe.sqlite` per theatre, ATTACH-based probe-then-base fallback in `describe_position`, tri-state coverage keyed `(kind, chunk_ix, chunk_iz)`, locked chunk/probe spacing, drift detection on both write and read paths. All 244 tests pass (241 base + 3 new from required fix). Two-store separation prevents "newest grid wins" silent failure; read-path drift protection closes reviewer-found cross-theatre/stale-lattice gap. Fixture-only testing; no live-mission channel (deferred to Runtime). See `plans/m8-incremental-store/plan.md`, `plans/m8-incremental-store/implementation.md`, `plans/m8-incremental-store/review.md`, and `world-model/docs/M8_PROBE_STORE.md`.

## Milestones

Full sequence lives in `world-model/ROADMAP.md` (M0 through M9, World Model side). Aircraft layer / Mission Interpreter / Runtime work now in scope — see root `CLAUDE.md` "Current priority" (gate lifted 2026-09-06).

- [x] **PB-1.5 — Naked-eye visual detection channel.** Done, merged to main 2026-09-09. Live acceptance passed. See Current Focus.
- [~] **BL-2.5 — In-cockpit text mirror (DCS overlay output channel).** Interim milestone, scheduled between BL-2 and BL-3 by user decision 2026-09-09. In progress. See Current Focus and `plans/dcs-text-panel-output/plan.md`.
- [ ] **BL-2.6 (label provisional) — Classification refinement.** *Scheduled next, after BL-2.5 and before BL-3 (user decision, 2026-09-09).* Fire an event when a contact's identification becomes more specific — `something → tank → T-72`, `unknown group → SAM site → SA-6`. User's framing: these transitions are exactly the information DCS internals do not give, and they make the system useful for gameplay rather than only for observing it.
  Not just an event. Investigation 2026-09-09 found the data can't currently support it:
  1. **Naked-eye classification is range-independent.** `perception/naked_eye_source.py` emits
     `object_model.profile_for(...).op_class` — a fixed bucket per DCS type, from a table of
     eight (`OP_ARMORED`, `OP_TRUCK`, `OP_SRSAM`, `OP_MRSAM`, `OP_SPAAG`, `OP_ZU23`,
     `OP_INFANTRY`, `OP_SHIP`). A T-72 reads `OP_ARMORED` at 6 km exactly as at 200 m, so there
     is no `something` stage and no refinement on closure. Arguably an anti-omniscience gap in
     its own right: naked-eye at 6 km should not reliably separate armour from a truck.
     Grading specificity by observation quality (range, angular size, dwell, channel) is the
     real work here.
  2. **The `tank → T-72` half is producible today** — the scope/HelperAI channel passes
     Petrovich's own indication text through verbatim (`perception/hybrid_source.py`), which
     carries specific type names. A naked-eye `OP_ARMORED` contact later seen on the scope
     genuinely refines.
  3. **…but it would oscillate.** `Contact.last_class_raw` is a single last-writer-wins string,
     so the next naked-eye tick overwrites `T-72` back to `OP_ARMORED` and back again, firing
     spurious refine/de-refine events. **This absorbs the existing backlog item** on BL-2's
     last-writer-wins certainty/classification fusion — theoretical until now, load-bearing the
     moment this event exists. Needs a specificity ordering so a better classification is never
     overwritten by a worse one.
  **Grading is the intent, confirmed by the user 2026-09-09.** Making Petrovich *worse* at long
  range is the goal, not a cost to be minimised: it is the anti-omniscience principle applied to
  classification. Expect BL-2's existing live behaviour to change visibly and PB-1.5's calibration
  to be revisited — that is an accepted consequence, not a regression to guard against.
  `CONTACT_CLASSIFICATION_CHANGED` is already named in `body-layer/src/belief/events.py` and
  `docs/concept/PETROBRAIN_RUNTIME.md`'s event model as a post-BL-2 candidate, so this pulls a
  planned event forward rather than inventing one. Needs an Architect pass; label to be confirmed
  with the plan (BL-2.6 follows BL-2.5's interim precedent, but it is contact-memory work, so
  the architect should confirm the family fits).

(World Model M9 moved to Deferred below, 2026-09-06)

## Backlog

- [x] **Aircraft layer should flag the ownship; body layer filters it out in detection logic.**
  *(User decision, 2026-09-09 — supersedes the earlier "omit or flag" framing recorded here.)*
  **Done — PB-2 Stage -1** (`is_ownship` flag, `association.exclude_ownship`/
  `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` heuristic removed). See Current Focus PB-2 entry.

  **Aircraft layer**: add an ownship marker to each `/world_objects/latest` entry —
  `Export.lua` can identify the player's own object via the DCS export API
  (`LoGetPlayerPlaneId()`). **Flag it, do not omit it**: ownship's entry is still wanted in the
  snapshot, so dropping it at the source is not acceptable. This is a wire-format addition to
  `aircraft-layer/src/schema/world_objects.py`'s `WorldObjectSample` and affects every consumer of
  that endpoint.

  **Body layer**: filter on that flag inside the detection logic, and **delete
  `association.exclude_ownship` and `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` entirely** — the flag makes
  the 50 m proximity check unnecessary, not merely redundant.

  **Why it matters.** The 2026-09-09 fix (`549aee6`) drops any world object within 50 m of
  ownship. It is correct for the bug it fixes and has no false positives in practice, but it is a
  heuristic standing in for an exact answer, and it carries a false-*negative* window: any genuine
  object within 50 m is silently dropped. The concrete high-risk case is **troop insertion and
  extraction** — a core Mi-24P mission that routinely puts the aircraft within 50 m of real
  objects; also close formation, and hovering directly over a target. An identity flag closes that
  window completely and is robust regardless of what `LoGetWorldObjects`'s `pairs()` key means.

  Not done during the bug fix because it is an aircraft-layer change affecting every consumer,
  where the body-layer-side fix was contained and shippable. Worth doing when aircraft-layer is
  next touched.

- [x] **Settle whether `LoGetWorldObjects`'s `object_id` is stable across polls** — **closed 2026-09-09 by live evidence.** PB-1.5's acceptance sortie emitted 2 observations in 70 s; unstable ids would have re-emitted every object every tick. The prediction recorded below ("the next live sortie settles it for free") held. Original entry: — needs a live
  capture, described in `plans/pb1.5-naked-eye-detection/debug.md` "Needs live DCS".
  `world_objects.py`'s own docstring calls it "the numeric key from Lua `pairs()` iteration" and a
  "within-one-poll identifier only until verified live", and Lua does not guarantee `pairs()`
  order. Both perception channels' debounce keys on it.

  The 2026-09-09 debugging established the debounce mechanism is *not* broken given a stable id —
  the live log's irregular repetition was the FOV gate flapping on a meaningless near-zero-baseline
  bearing, fully explained by the ownship bug. So this is unconfirmed rather than known-broken, and
  was deliberately not "fixed" speculatively. **The next live sortie settles it for free**: with the
  ownship echo gone, if real contacts re-emit on every poll instead of once, the ids are unstable.
  Watch for that during acceptance testing.

- [>] **Direction (raised 2026-09-09; parked by user decision 2026-09-09): stop consuming DCS's
  detection at all, and own perception end-to-end.** After the PB-1.5 live probe
  (`aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`), the user's position is
  that this "heavily leans towards entirely dropping the current naked-eye DCS detection logic,
  possibly even suppressing the texts in the radio callouts, and implementing our own detection
  mechanism based on all world objects."

  **Why the probe pushes this way.** DCS's ambient channel is unusable as an input: it emits no
  Lua-readable signal (probe Finding 1), it is text-only with no audio (Session 5 part 3), its
  reports lag well behind what the player can plainly see (Finding 5), and the one channel that
  *is* readable — the HelperAI target list — only exists while the sight is on and is gated on it.
  So every path that treats DCS as the detection authority is either unreadable, late, or
  sight-coupled. PB-1.5 already builds the alternative.

  **What it would change.** PB-1.5's `visibility.py` stops being a fallback that stands in for a
  missing signal, and becomes the primary, intended detection mechanism. That retroactively
  reframes the plan's Decision 1, which the user accepted "for now" expecting to revisit it —
  the revisit would resolve *toward* the synthetic filter rather than away from it. It also makes
  the range/tier constants product-critical rather than provisional, and raises whether the scope
  channel stays a second source or becomes just one more input to our own model.

  **Open questions — all four answered by the user 2026-09-09:**
  1. *Can DCS's radio callout texts be suppressed?* **Needs investigation, deferred.** Any approach
     touching module files fights integrity checks and is overwritten by updates; DCS's `SUBTITLE`
     option (Session 2 finding) is an unverified lead. Investigator task if/when this is revived.
  2. *Is suppression wanted?* **Only if possible, and low priority — deferred.** Not a blocker for
     anything else here.
  3. *Does the HelperAI scope channel survive as a distinct source?* **Yes — it stays.** The user
     needs it for later gameplay: commanding Petrovich to acquire a target, lock it, and fire.
     Those are a future, currently-deferred milestone, but they depend on the scope channel, so it
     is not collapsed into our own model and not dropped. **Consequence: the association namespace
     bug (backlog item below) matters more than its "PB-1 code, already merged" framing suggests —
     it is on the path to a wanted feature, not a dead branch.**
  4. *What does this do to BL-2/PB-2?* **Very little.** BL-2 (contact memory and association —
     persistent contact identities, detected/lost/reacquired, observation-vs-belief split, decay,
     behind a debug console that is the ancestor of the brain API; see `plans/body-layer/plan.md`)
     consumes `Observation` records through the `PerceptionSource` interface regardless of which
     channel produced them, and was never going to consume the DCS ambient channel because that
     channel is not readable. The only real change is emphasis: our own synthetic channel becomes
     BL-2's main source of contacts, with the scope channel as the second. No interface change.

  **Net remaining scope of this item**, once the deferrals above are taken out: adopt PB-1.5's
  filter as the primary detection mechanism rather than a fallback, and stop treating DCS's ambient
  output as an input we are waiting on. Both are framing/documentation changes plus calibration —
  no new machinery.

  **Parked 2026-09-09 (user decision), going straight to PB-2 instead.** No longer `[?]`/"decision
  needed": the four questions above were all answered, which settled every architectural call this
  item was going to make — there is no module boundary to draw and no interface to change, so the
  *Architect* pass named in the original heading is no longer required. What remains is (1) a
  framing/documentation pass reclassifying `visibility.py` from fallback to primary mechanism, and
  (2) calibration of the tier/range constants against the "if the player can see a unit, Petrovich
  should too" standard. Calibration is the only real work and needs live sorties, so it is better
  folded into a milestone that is flying anyway than run as its own. Do not start without the
  user's instruction.

- [ ] **`association.py` matches across two different DCS name namespaces and scores 0 on most real
  units** — *priority raised 2026-09-09: the user confirmed the scope channel is needed for later
  gameplay (commanding Petrovich to acquire/lock/fire), so this is on the path to a wanted feature
  rather than dead code.* — found 2026-09-09 while validating PB-1.5's `object_model.py`. `HybridPerceptionSource`
  matches HelperAI's detection text against `LoGetWorldObjects` candidates via
  `association._type_match_score`, but the two feeds speak **different vocabularies**: HelperAI
  emits Petrovich's *reporting* names (`"Slava cruiser"`, `"SA-3 launcher"`, `"Tarantul III
  corvette"`, `"SA-3 Low Blow radar"`) while `LoGetWorldObjects` emits DCS *type* names
  (`MOSCOW`, `5p73 s-125 ln`, `MOLNIYA`, `snr s-125 tr`). Measured scores for those four real
  pairs: **0, 0, 0, 0**. `"Ural truck"` vs `Ural-375` scores 1 — the only case that works, and
  only because the two names coincidentally share a word.

  This is not theoretical: those are exactly the units the PB-1 spike log actually captured
  (`aircraft-layer/research/2026-09-08-...`, Session 5 part 2, Finding 6). PB-1's live acceptance
  test passed because it used Ural trucks — the single type where the coincidence holds. So the
  scope channel's association is likely near-nonfunctional for ships, SAM sites and most armour,
  and this was invisible until now.

  **The fix is already in the repo**: PB-1.5 committed ED's complete 595-row type→reporting-name
  mapping (`body-layer/src/perception/data/dcs_type_to_reporting_name.tsv` +
  `reporting_names.py`). `association.py` should resolve each `LoGetWorldObjects` type name to its
  reporting name before scoring, so both sides speak the namespace HelperAI actually uses.

  Not fixed under PB-1.5 — it is PB-1 code, already merged to `main`, and a behaviour change to
  the scope channel deserves its own before/after evidence and live re-test rather than riding
  along in a milestone about a different channel. Related to, but distinct from, the multi-contact
  gap flagged in `plans/pb1.5-naked-eye-detection/plan.md` Risks (`hybrid_source.py` reads only
  `middle_list_text` and may be discarding real simultaneous rows). Both are worth doing in one
  pass over `hybrid_source.py`/`association.py`.

- [ ] **Incremental per-layer pipeline builds** — `build_region` currently deletes and recreates the entire `.sqlite` on every call, forcing a full rebuild of all layers each time. User-requested capability: run individual pipeline sections (e.g., roads only, elevation only, validation only) and *add* that data into an existing store, allowing staged builds and partial re-runs when debugging a single layer. Deferred post-M7 (raised during M7 DoD acceptance testing, explicitly not blocking). Considered for M8 and **explicitly dropped** from it (2026-09-06) to keep that milestone scoped to the probe store — this remains open and unscheduled for a later milestone. M9 (OSM) would benefit from it; see `plans/m9-osm-geofabrik/plan.md` design decision 4. See `plans/m7-full-theatre-pipeline/` for context and `world-model/src/build/pipeline.py`'s `build_region` implementation.

- [ ] **Aircraft-layer: split the export throttle so `LoGetWorldObjects`/HelperAI can poll slower than self-data.** Raised 2026-09-09 during PB-2 work. `aircraft-layer/dcs-export/Export.lua`'s `EXPORT_INTERVAL_S = 0.2` (5 Hz) is a single shared throttle (`last_export_t` in `LuaExportAfterNextFrame`) gating self-data (attitude/IAS/heading), `LoGetWorldObjects`, and the HelperAI poll together — there's no way today to slow one feed without slowing all three. User's reasoning: ground units tracked by `LoGetWorldObjects` move slowly and don't need 5 Hz; self-data (and any future threat-reaction signal) may still want a faster rate. Fix: two independent interval constants/throttle states instead of one. Not urgent — no measured FPS cost yet to react to (see next item) — but a clean, low-risk refactor once someone's in `Export.lua` anyway. Confirmed BL-2's contact-decay timescales (30s position half-life, 120s lost-threshold, `plans/pb2-contact-memory/plan.md` Stage 2) are ~2 orders of magnitude slower than either 5 Hz or a candidate 2 Hz, so this change has no effect on belief quality — it's purely an export-cost/latency tradeoff.

- [ ] **Aircraft-layer: measure `LoGetWorldObjects` FPS cost live before tuning its poll rate.** Raised 2026-09-09 alongside the throttle-split item above; same trigger, kept separate since one is a code change and the other is a measurement task that should land first and inform it. `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`'s "Unresolved" section already flags this: no confirmed, quantified per-call cost of `LoGetWorldObjects` at realistic unit counts (~50–200) exists — only qualitative forum/Tacview-wiki folklore ("can be inefficient, ED has partially optimized it," no hard numbers). The current 5 Hz was picked as "conservative starting rate," not a measured-safe one, and there's no native radius/category filter at the API level, so cost scales with total map object count regardless of poll rate. User proposed 2 Hz as a guess balancing slow-moving-ground-unit tracking against staying responsive to being fired at; before committing to that or any number, fly with world-objects export on/off at 5/2/1 Hz and diff FPS/frame-time to settle it empirically. Also worth checking live whether "being fired at" is even served by `LoGetWorldObjects`'s poll rate at all — nothing currently reads it for threat/launch detection (that's position/identity data, not an event stream), so the urgent-callout-latency reasoning may want its own dedicated signal later (e.g. RWR export) rather than riding on the ground-scene poll rate.

- [~] **DCS radio message text panel as an SRS fallback / dev-visibility output channel.**
  **Promoted out of the backlog: this is now BL-2.5, an interim milestone scheduled ahead of
  BL-3 (user decision, 2026-09-09).** Status and detail live in Current Focus, not here.
  Plan: `plans/dcs-text-panel-output/plan.md`.
  Original entry: Raised 2026-09-09. SRS (voice) is the intended eventual output channel for Petrovich's messages, but is not yet implemented; even once it exists, a text-panel fallback is wanted for when the SRS server isn't connected. Concrete near-term value: mirror the body-layer log output to DCS's in-game radio message text panel now, during development — makes live sortie testing (BL-2 acceptance, PB-1.5 calibration, etc.) far easier to observe in-cockpit instead of only in an external log file. Needs investigation: how to write to that panel from outside mission-scripting context (likely `trigger.action.outText` or similar, callable only from mission/hook Lua, not obviously from the Export environment aircraft-layer currently uses) — probably an aircraft-layer-side addition (new outbound path, mirroring the existing inbound Export.lua polling) or a separate hook script. Investigator task before implementation, per project convention for unverified DCS-internals questions.

- [ ] **BL-2's `certainty`/classification fusion is last-writer-wins, not quality-weighted.**
  **Absorbed into BL-2.6 (classification refinement), scheduled next — see Milestones.**
  It stops being theoretical there: without a specificity ordering, refinement events
  oscillate. Found 2026-09-09 during PB-2 Stage 5 (cross-channel fusion validation), reported as an expected consequence of Stage 2's design rather than a bug — `decay.certainty_of` is a pure function of `now_sim - last_seen_sim` with no notion of which contributing observation had tighter position uncertainty or which channel produced it, and `Contact.last_class_raw` is likewise overwritten by whichever observation arrives most recently. Concrete failure mode: a tight naked-eye/binocular observation followed by a wider-uncertainty scope observation of the same contact fully resets `certainty` to `"observed"` and overwrites the classification, even though the earlier observation was better. Not fixed under PB-2 — Stage 2's certainty ladder is explicitly a placeholder pure-recency design (per its own review), and reworking it to be quality-weighted is a real design question (what "better" means across two channels with different uncertainty models) rather than a quick patch. Worth revisiting once real sortie data shows whether this actually degrades perceived contact quality in practice, or stays theoretical. See `body-layer/tests/test_cross_channel_fusion.py` for the fixture that surfaced this.

## Deferred

- Spatial storage/library choice — resolved by M5: stdlib `sqlite3` + R*Tree, JSON geometry (not GeoPackage/SpatiaLite/PostGIS). See `world-model/research/2026-09-04-m5-first-persistent-model.md`.
- M9 — OSM augmentation (geofabrik). **Deferred, value reassessed 2026-09-06.** OSM's original role split ("DCS = where, OSM = what") is now partly absorbed: DCS-native gives exact roads/named places/elevation, and M8's live-probe path can fill point-level `surface_type`/water ground-truth incrementally with zero new dependency. Remaining unique OSM value is narrow — settlement **boundary polygons** (DCS only gives town-center points) and semantic **tags** (road class/ref, land-use, POI type) that neither DCS nor probing produce. Not worth the new-dependency/`.osm.pbf`-parsing cost (see `plans/m9-osm-geofabrik/plan.md` open dependency decision) while no downstream consumer (Mission Interpreter/Runtime, both not yet built) needs settlement-extent reasoning or richer naming. Revisit only when such a consumer's requirements actually call for it — user decides when.

- **Attention direction and detection cones (much-later milestone).** Raised 2026-09-09 during PB-2 work; deliberately deferred, not started. Today's perception channels (naked-eye/binocular quantised filter, HelperAI scope text) both implicitly assume Petrovich is looking everywhere at once within range/FOV gates — no notion of *where* his attention is actually pointed, or which of several distinct real optical modes he's using. Future design should model this properly:
  - **Distinct optical modes**, each with its own field-of-view/acuity/movement-tradeoff, not one blended model:
    - **Peripheral vision** — very wide FOV, poor at classification/ID, but picks up *movement* near-instantly; unexpected motion (i.e. not the wingman) should be able to grab focus for threat triage even outside the current focus area.
    - **Naked-eye focus** — narrower than peripheral, good at detection/ID at closer range, tracks smoothly through maneuvering.
    - **Binoculars** — zoom, much better detection/ID at range, very narrow FOV, unusable during aggressive maneuvering.
    - **APS-17** (or whatever the in-game equivalent is) — its own distinct mode, binocular-like but with its own optics/operating logic — needs its own investigation before modeling.
  - **Attention/scan state**: focus can be on a specific target, a specific direction/sector, or a full-visibility scan; state needs to persist and drive which optical mode is "active" for perception-source gating.
  - **Scanning loop logic**, e.g.: wide peripheral scan → focus on something interesting → classify → binoculars for ID/detail → classify → return to wide scan; interrupted periodically by a full-area sweep for emergent threats even while working a directed search (pilot-requested sector, or mission brief expected-threat direction/clock bearing) — loop back to the priority sector afterward.
  - Why this matters for what's already built: `NakedEyePerceptionSource`'s FOV/angular-size/LOS gating (PB-1.5) and BL-2's belief layer both currently treat "can Petrovich see it" as a single binary gate, not as a function of current attention mode/direction — this milestone would change what feeds `Percept`/`Observation` in the first place, upstream of everything BL-2 built. Not a BL-2 change; a future perception-layer milestone, likely well after BL-4 (attention/relevance policy, which currently only has the bare `watch`/`unwatch` enum from PB-2 Stage 4 to build on).
