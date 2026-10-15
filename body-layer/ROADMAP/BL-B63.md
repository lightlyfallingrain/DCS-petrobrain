# BL-B63 — A selective fast lane for ownship telemetry and the currently-selected target

- [ ] **BL-B63 — A narrow fast-poll path carrying only ownship telemetry and the currently-selected
  target's geometry, separate from the 1 Hz perception tick, scoped to whatever has a selected
  target (attack-run today, 9K113 missile guidance later) rather than a general rate split.**
  #status/open

  Filed at Architect stage during the `BL-14` attack-run amendment pass, 2026-10-14, from §21 of
  `docs/acceptance/2026-10-14-attack-run-guidance-direction.md`, and **reshaped by a second round
  of user direction the same day** after the first filing had the split backwards. The user's own
  words for the corrected shape: *"for body layer poll rate, we should have a selective more
  frequent poll: ownship telemetry and current target data. Not all world objects, just ownship
  and current target. Could be that 5 Hz. We'll need both anyway for 9K113 missile guidance to be
  precise."*

  **What this is not.** Not a general "telemetry fast, world objects slow" rate split — that was
  the first reading and is corrected here. There is no case in this filing for raising the rate of
  *bulk* world-object polling at all.

  **Scoped by construction, not by a flag.** A "currently-selected target" only exists while an
  attack run (or, later, a missile engagement) has one. The fast lane turns on with that state and
  off with it — no global rate change, no cost when nothing is selected.

  **Dependency on `aircraft-layer/ROADMAP/AC-B3.md`, checked and stated the right way round.**
  Aircraft-layer already exports everything at 5 Hz (`EXPORT_INTERVAL_S = 0.2`,
  `aircraft-layer/dcs-export/Export.lua:143`); `body-layer/src/logger.py`'s crew poll loop is the
  only throttle between that and guidance, polling ownship telemetry and every source once per
  iteration at one shared `_DEFAULT_POLL_INTERVAL_S = 1.0` (`logger.py:1123`). So a body-side
  selective fast poll gets 5 Hz target data **today, with no aircraft-layer change** — `AC-B3`
  becomes a prerequisite only if it lands and slows *bulk* world-object export for FPS reasons,
  at which point the selected target would need its own fast publication carved back out on the
  export side. `AC-B3`'s own entry carries the matching correction note.

  **The constraint that matters is not "can the aircraft-layer export fast enough" — it already
  does — but "can the existing perception tick run 5× more often", and it cannot, though the
  figures that would have said so most dramatically are stale and are corrected here rather than
  carried forward.** `BL-B26`'s originally filed 1,579 ms worst tick and `group_salient_ids`'s
  originally filed ~300 ms/poll both predate `BL-11` (2026-10-06):
  `group_salient_ids` is now **1.1 ms median, 5.5 ms max** (`BL-11` Stage 2, `BL-B30`), and the
  realised poll-work median across the whole tick is **12.6 ms**, down from 330 ms (`BL-11`'s
  live-acceptance-debt entry). At 12.6 ms median there is real headroom inside a 200 ms (5 Hz)
  budget — so "a 5 Hz full tick is impossible" no longer follows from those specific numbers.

  **The architectural case for a narrow path survives the correction on different grounds.**
  `BL-11`'s figure is a median against one bench scale; enrichment-cache misses still cost ~42 ms
  each at a measured 2.3% miss rate (`BL-11` Stage 3b); nothing bounds the worst tick the way the
  median is now bounded. Running the *whole* perception tick — clustering, group reconciliation,
  enrichment, callout scheduling — five times more often multiplies a cost that is not guaranteed
  flat, to refresh work that, for every contact except the one selected, a fast lane has no reason
  to touch at all. That argument does not need the old 1,579 ms figure to be true.

  **Whether a narrow path falls out of the existing design: yes for the ownship half, open for the
  target half.** `plans/attack-run/plan.md` Decision 16's relative-observation design already
  needs nothing from clustering, group reconciliation, enrichment or callout scheduling to refresh
  — it re-rotates a carried offset against *current* ownship attitude, which is one
  `get_telemetry_latest()` call and a trig re-derivation, not a perception tick. A fast
  ownship-telemetry poll is a clean fit entirely outside the heavy loop. The target half is less
  settled: aircraft-layer's API has no per-object filter (`aircraft-layer/src/api/server.py`'s
  `/world_objects/latest` always returns the full cached snapshot), so a fast poll of "just the
  current target" means either filtering the existing bulk payload client-side at 5 Hz (cheap, on
  these figures — the heavy cost was never the HTTP/JSON step) or a new filtered endpoint. Whether
  the fast lane is a second loop or a sub-tick inside the existing one is the same open design
  question, left to whoever builds this.

  **Amended 2026-10-15 — this became a hard dependency of a named stage, one stage earlier than this
  entry expects, and on correctness grounds rather than performance ones.**
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §12 establishes that the 9K113 is slewed by a
  joystick-like device whose axes command angular **speed**, not a desired angle — *"The axis input
  is the slew speed. Not desired angle, but angular speed of slew… we need a constant inspect and
  adapt loop"* — so pointing the sight is a closed loop. **A rate-commanded loop closed at the
  current 1 Hz would overshoot every time.** That makes this fast lane a **hard dependency of the
  9K113 effector stage (`[[BL-B66]]`)**, not the optional optimisation the rest of this entry reads
  as, and it arrives *before* the missile-guidance consumer named below rather than with it. The
  mechanism asked for is unchanged; what changes is that **loop rate is now a correctness property**
  for that consumer, so "an optimisation for a tighter-budget future consumer" (below) no longer
  describes the whole picture. Still accurate for `[[BL-14]]`, which needs nothing here.

  **Why framed as a reusable seam rather than an attack-run-specific optimisation.** The user names
  9K113 missile guidance as the second consumer explicitly — *"We'll need both anyway for 9K113
  missile guidance to be precise"* — which makes this a known future requirement, not speculative
  scope.

  **Why filed rather than built.** `BL-14`'s own staleness budget already closes with re-rotation
  alone at the existing 1 Hz rate — the register and the dynamics co-vary (angular rate peaks
  during turn-in, where the words are coarse; the geometry calms exactly where the words get fine)
  — so this is an optimisation for a tighter-budget future consumer, not a prerequisite for
  `BL-14`. No stage in that plan depends on it.

  Related: `aircraft-layer/ROADMAP/AC-B3.md` (the export-side half, and its correction note
  pointing here), `plans/attack-run/plan.md` Decision 16 and its §21 amendment note (the measured
  9.2°/s figure, the re-rotation design this fast lane would sharpen rather than replace), `BL-B26`
  and `BL-B30`/`BL-11` (the tick-cost figures corrected above), `BL-14`.
