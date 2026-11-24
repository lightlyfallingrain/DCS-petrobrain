---
name: bl16-pedal-near-limit-guard-regression
description: review outcome for BL-16 LV-1's 2026-11-24 pedal-sign debug pass (commits 844213f1/d0b4d6cc) -- CHANGES REQUIRED, collective-near-pedal-limit guard now protects the wrong side
metadata:
  type: project
---

Reviewed `844213f1` (fix) + `d0b4d6cc` (debugger memory) on `feature/bl16-lift-vector-law`,
on top of `74c1060b`. Full review in `plans/flight-lift-vector/review-debug-1124.md`.

**Superseded 2026-11-24 (debugger second pass, `plans/flight-lift-vector/debug-2026-11-24b.md`):
the sign flip approved below was wrong and is reverted -- positive pedal command = RIGHT.** The
"lots of left pedal" came from the take itself, not the loop; the re-fly showed the flip backwards.
The guard fix (side derived from the coefficient's sign) survives and now selects the positive side.

**The pedal-sign diagnosis and fix are correct and well-evidenced** (as judged then): "positive pedal command is
physically LEFT" rests on two genuinely independent facts (the 2026-11-20 calibration's solid,
isolated-input measurement, and the sortie's direct pilot observation), and the new
`TestBallCentringPedalSign` toy-plant test is grounded in that same calibration fact rather than
circular — confirmed by reverting `k_ball_pedal` to `+0.3` and watching both new tests fail as
claimed.

**Required fix found**: `law_update`'s collective-near-pedal-limit guard
(`state.t_y >= profile.pedal_limit_positive - profile.pedal_near_limit_margin`) was not updated
when `pedal_limit_positive`/`pedal_limit_negative`'s magnitudes swapped — it still names
`pedal_limit_positive` specifically, which is now the generous/left side, not the scarce/right
side the guard exists to protect. Confirmed by mutation against the real law: `t_y` near the new
scarce limit got no cap; `t_y` near the new abundant limit got capped unnecessarily. Zero test
coverage of `collective_rate_cap_near_pedal_limit` exists in either test file, before or after
this fix.

Verdict: **CHANGES REQUIRED**, routed back through Implementer → Reviewer per the standing
change-request re-entry rule. See [[feedback_sign_flip_must_grep_every_near_limit_guard]] for the
generalised lesson.
