# BL-B98 — 9K113 sight returns to dead-ahead after a glance-away instead of staying at its last position

- [ ] **BL-B98 — The 9K113 sight resumes dead ahead `(0.0, 0.0)` on every glance-away-triggered
  resume, not at its last position.** #status/open Found during the BL-B89 Stage 1 review
  (`plans/9k113-scan-procedure/review.md`, Required Fix 1), pre-existing — not this stage's
  defect to introduce, but newly measured by this stage's own tests.

  Against the settled acceptance item, `docs/acceptance/2026-10-20-sortie-feedback.md` F4/F5:
  *"1 - eyes/binocular when beyond 9K113 limits. Leave 9K113 at last position."*

  **Root cause.** `_start_glance_away` (`body-layer/src/belief/optic_policy.py`) nulls both
  `look_azimuth_deg`/`look_elevation_deg` to `None` on entry, for every glance-away, regardless
  of trigger. The two functions that later resume `SIGHTING` —
  `_back_to_home` and `_enter_binocular_search` — both carry the aim through unchanged rather
  than re-deriving it, which only delivers "stays at last position" when the aim was never
  nulled in the first place (a mid-lap interruption reaching `_back_to_home` directly, bypassing
  `_start_glance_away`). On the glance-away-resume path — both the pre-existing
  `SIGHT_MAX_DWELL_S` trigger and `BL-B89`'s new lap-completion trigger, since both share
  `_start_glance_away` unmodified — the aim is already `None` by the time either resume function
  runs, so both default to dead ahead `(0.0, 0.0)` instead.

  Measured directly by `BL-B89` Stage 1's own `TestSightSearchLegs`
  (`plans/9k113-scan-procedure/implementation.md`, "Notable Discoveries": the implementer's first
  draft of that test assumed "stays at last position" and failed against the real code).

  Fix is to have `_start_glance_away` preserve the aim (or have the resume functions re-derive it
  from state captured before the null) rather than discarding it — scope and approach not yet
  decided; this entry only files the defect.
