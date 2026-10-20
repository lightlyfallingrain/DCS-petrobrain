# BL-B89 — 9K113 scanning procedure: points of interest, not band sweeps

- [ ] **BL-B89 — Re-sequence the sight's search cycle to the way the user actually scans with the
  9K113: wide S-scans find points of interest, then narrow visits them by priority.** #status/open
  User direction, 2026-10-20 (`docs/acceptance/2026-10-20-sortie-feedback.md`, "F5 — boresight-relative
  limits: explore answers", quoted in full there). The sequencing was agreed the same day:
  `feature/9k113-narrow-search` merges as built, and this is the next item, with a plan and a mock first.

  The procedure, in the user's words, condensed:
  - **Scanning a sector (typically forward):** wide S-scan near→mid (close threats and targets),
    then a wide S-scan far (anything worth a closer look). Then narrow: first units not yet
    identified that might be inside identification range, then the same for class, then a narrow
    far sweep for detection. *"Do not linger on any given target longer than necessary … If it's too
    far or blocked, then move on."* Then a quick naked-eye all-round sweep, then back to wide. *"No use
    rescanning a known unit if it has not moved across expected classification/identification
    range, except a quick check for position."*
  - **Pointing at a known place:** slew there, wide to orient and detect, narrow to identify and
    estimate distance, then use wide and narrow to move between targets.
  - *"it's not really about a band, more like points of interest to scan around. The wide S-scans
    purpose is to find the points of interest."*

  Mostly a re-sequencing of pieces that already exist: S-sweeps, least-capable-optic looks
  (`sight_look_optic`), the stall cooldown (`[[BL-B85]]`), range-crossing re-look rules, and the
  glance-away. **Pointing (user, 2026-10-20):** o'clock or compass bearing, with an optional
  distance, for now. Landmarks, waypoints and player-set marks come later: *"yes, absolutely, once
  we get them in reliably. Not quite there yet."*
