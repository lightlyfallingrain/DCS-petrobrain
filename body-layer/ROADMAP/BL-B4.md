# BL-B4 — `alt_ok` has no hysteresis counterpart

- [ ] **BL-B4 — `alt_ok` has no hysteresis counterpart to `range_ok`'s `ENGAGEMENT_LEAVING_HYSTERESIS` —
  found during the watch-reporting performance-review fix, 2026-09-24.** #status/open The short-circuit that
  skips `line_of_sight_clear` when `range_ok and alt_ok` is already `False` (performance fix,
  `contacts.py`) means any tick where ownship altitude oscillates right at `envelope.alt_min_m`
  now discards an in-progress LOS mask dwell (`los_masked_since_sim = None` on the skip path),
  which didn't happen before (LOS ran unconditionally every tick pre-fix). Traced as fail-safe,
  not a correctness bug: resetting the dwell only pushes `masked_for_s` back toward 0, which keeps
  `los_ok` (and `current_engaged`) `True` longer, never shorter — it can delay a warning clearing,
  never drop or falsely clear one. Fix (not done in `watch-reporting`, deliberately, per the fix
  review): a matching hysteresis margin on `alt_min_m` for symmetry with the range side.
