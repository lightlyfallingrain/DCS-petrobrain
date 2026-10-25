# BL-B99 — Petrovich POV debug view: optic FOV and detections, in angle space

- [x] **BL-B99 — An optional ASCII "Petrovich's point of view" debug view, the forward-looking twin
  of the top-down `--eyesight-view`.** #status/done #needs-flight Merged `7796206d` from
  `feature/pov-view` (2026-10-25). Run with `--pov-view` (`run-scripts/run-body-layer.sh
  --pov-view`). Perf/security waived by the user (*"skip perf and sec as this is debug tool
  only"*). DoD: `plans/pov-view/dod-check.md`; live check
  `docs/acceptance/2026-10-25-bl-b99-pov-view.md` (card https://claude.ai/artifact/NVKCE77Z2sNqgHQS29B3aL).
  Milestone check: no change to what is next; when `[[BL-B89]]` merges, re-check
  `body._render_pov_frame`'s per-optic boresight table against BL-B89's gaze/optic changes
  (textual merge is clean apart from the backlog index). Debug,
  testing and calibration instrument, so it may show ground truth, exactly as `eyesight_view.py`
  does (user, 2026-09-25: *"Can break no-omniscience boundary because the whole purpose is
  testing, debugging and calibration."*).

  **User request, 2026-10-25** (verbatim):

  > *"We have the top-down ASCII graph of scanning sectors and detection. That's a good debug tool.
  > We need to have a similar optional tool for Petrovich POV that shows the optic FOV and what
  > Petrivich detects.
  > Ignore all units outside player bubble.
  > Use the existing symbols from the top-down graph.
  > This makes it much easier to debug and fine tune the optics scanning logic."*

  Example given:

  ```
      -90         -60         -30         0           30          60          90
  +10 -------------------------------------------------------------------------- +10
      |             |           |         |            |           |           |
      |             |           |         |            |           |           |
      |             |           |         |            |           |           |
    0 |             |           |         |            |           |           | 0
      |             |           |         |       ..   |           |           |
      |     x       |           |         |      ..A.  |           |           |
      |             |           |         |      .T..  |           |           |
  -10 |         x   |           |         |       ..   |           |           | -10
      |             |           |         |            |           |           |
      |             |           |         |            |           |           |
      |             |           |         |            |           |           |
  -20 -------------------------------------------------------------------------- -200
  ```

  > *"Visualization of Petrovich scan and POV:*
  > *- eyes: green border highlight on the sector he sees*
  > *- optics: draw the current optic's FOV with dots '.'*
  >   *- binoculars: blue*
  >   *- 9K113 wide: gray*
  >   *- 9K113 narrow: brown*
  >
  > *No need to draw terrain or horizon. Angles is graph are relative to boresight. Axis either
  > airframe relative or boresight so that z axis is world z axis aligned, your call on that."*

  **Main-loop call on the axis frame (the user left it open):** azimuth relative to the airframe's
  heading (the top-down view's own convention, `0` dead ahead, positive clockwise), elevation
  relative to the horizon (world-vertical aligned, roll and pitch removed). Reason: the 9K113 sight
  is gyro world-stabilised and a target's depression angle is a world quantity (`atan(-AGL/range)`),
  so a horizon-levelled frame keeps a ground target still on the canvas while the airframe pitches
  and rolls. Revisit if it reads wrong in flight.

  The `-200` on the example's last line is read as a typo for `-20`.
