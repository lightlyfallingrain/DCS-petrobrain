# BL-W33 — Binocular optic — Stages 1 through 3b

- [x] **Binocular optic — Stages 1 through 3b. DONE, merged 2026-09-23** #status/done (`e91b9ee`,
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


**Closed by [[BL-W7]]'s sortie, 2026-09-25** — this entry's own "Unflown as of merge" sentence above predates that closure and is left unedited (see [[BL-W7]] for why), but live acceptance is no longer outstanding.
