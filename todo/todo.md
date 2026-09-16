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

## Cross-cutting / unscoped backlog

- [ ] **Stage 5 road junctions: pathological single-chunk stalls (48 min full-theatre).** Raised
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
