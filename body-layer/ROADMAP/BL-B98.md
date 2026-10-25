# BL-B98 — 9K113 sight returns to dead-ahead after a glance-away instead of staying at its last position

- [~] **BL-B98 — The 9K113 sight resumes dead ahead `(0.0, 0.0)` on every glance-away-triggered
  resume, not at its last position.** #status/in-progress Folded into `[[BL-B89]]` on
  `feature/9k113-scan-procedure` (user direction 2026-10-25, below). Found during the BL-B89 Stage 1 review
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

  **User direction, 2026-10-25** (verbatim):

  > *"fold in BL-B98 fix, it fits well with this feature. The sight does/must reset when OBSERV
  > switches to OFF, but not when it remains ON regardless of not using it actively. There was an
  > earlier fix to write 0 to the exis commands to stop it from moving, when not using the sight,
  > but that does not mean resessing it to boresight, just stopping movement."*

  So the rule is:

  1. **OBSERV on→off (any cause): the sight's believed aim resets to boresight `(0, 0)`.**
  2. **While OBSERV stays on, the aim persists** — through a glance-away, a binocular excursion,
     an idle period, anything that is not OBSERV going off. Resume picks up where it was.
  3. **A zero axis command is "stop moving", not "go to boresight".** The 2026-10-24 F1 fix
     (`e1d16037`, write 0 to both slew axes once on OBSERV off) halts slew; nothing may read a
     zero axis write, or an idle/`None` look, as the sight having recentred.

  **Fixed on `feature/9k113-scan-procedure`** (debugger, 2026-10-25 —
  `plans/9k113-scan-procedure/debug-bl-b98.md`). Root cause: `_start_glance_away`
  (`body-layer/src/belief/optic_policy.py`) nulled the aim unconditionally on every entry, though
  both its call sites only ever fire while OBSERV stays on; removed the nulling so `_back_to_home`/
  `_enter_binocular_search` resume from the real last position. A second gap closed in the same
  fix: `body.py`'s observed-edge OBSERV-off transition (`run_once`) now also resets the aim to
  `None`/boresight, matching `_force_observ_off`'s manoeuvre-triggered path, so a glance-away
  interrupted by a genuine OBSERV-off (any cause) does not leak the pre-glance position into the
  next OBSERV-on. Full `pytest`/`ruff`/`mypy` green; two pre-existing tests that pinned the buggy
  dead-ahead resume updated, one new regression test added. Status stays `[~]` here; the merge
  into `[[BL-B89]]`'s branch marks this done.
