---
name: poll-loop-has-no-5hz-spec
description: body-layer's poll loop is not specified at 5 Hz — the default is 1.0 s fixed-DELAY (sleep after work), so the observed ~1.44 s period is correct behaviour and BL-B30's premise is wrong
metadata:
  type: project
---

`logger.py:999` `_DEFAULT_POLL_INTERVAL_S = 1.0`; `--poll-interval-s` help text is *"seconds between
poll ticks"*; `stop_event.wait(poll_interval_s)` is the **last** statement of the loop body
(`logger.py:1192`, `:1552`), so the period is work + 1.0 s, not 1.0 s. 5 Hz is **aircraft-layer's**
`Export.lua` `EXPORT_INTERVAL_S = 0.2`, never body-layer's consumption rate.

**Why:** `body-layer/BACKLOG.md` `BL-B30` and
`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` §2 both assert "specified at
5 Hz, observed at 0.7 Hz, about seven times slower" and name four suspected causes. The measured 1.44 s
median is exactly work (~0.44 s) + the 1.0 s default. The suspected causes together account for the
0.44 s; the default accounts for the 1.0 s.

**How to apply:** before diagnosing any "the loop is too slow" report, read the default and check
whether the interval is a delay or a period. The security-relevant half is that `belief/decay.py`
half-lives, `events.py` `EVENT_COOLDOWN_S`, `perception/motion.py:91` ("objects arrive at 5 Hz") and
`gaze.py`'s `FOCUS_DWELL_S = 2.0` were all calibrated against a tick rate the loop does not have — a
gate run at a seventh of its calibration rate is uncharacterised. Same family as
[[project_elapsed_time_inflation_quadratic_dt_composition]]: a timing assumption that composes wrongly
and is invisible without measuring the loop itself.
