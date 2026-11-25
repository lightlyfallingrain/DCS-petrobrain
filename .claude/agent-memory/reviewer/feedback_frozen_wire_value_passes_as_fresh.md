---
name: frozen-wire-value-passes-as-fresh
description: a fail-loud staleness check that gates on "did this poll's read parse" rather than "did this poll's read actually change" cannot detect a dead upstream feed whose last cached value keeps parsing fine -- reproduce by calling the function repeatedly with an unchanged wire dict across advancing sim time, not by reading the code
metadata:
  type: feedback
---

Found reviewing `BL-B124` Stage 4 (`plans/bl-b124-light-level/review-stages-4-5.md`,
`feature/bl-b124-light-level`). `body._resolve_sun_elevation_deg` treats "this poll's `GET
/firing/latest` parses a well-formed `mission_clock` sub-dict" as "fresh" and clears its own
unavailable-timer/error-latch on that basis. But `aircraft-layer`'s `EmitterTracker.snapshot()`
has no way to say "this is the same sample as last time because nothing new has arrived" versus
"this is a genuinely new sample" -- `_last_mission_clock` is simply whatever the most recent
`ingest()` call set it to, and if the Hook/collector feed dies outright while the collector's
HTTP API keeps serving the last snapshot, every subsequent `GET` returns the exact same
well-formed dict forever. The user's own explicit answer for this feature (Q6: "mission should
always have both readable. Error if not") is never honoured in this exact scenario -- the
grace/error path is built, tested for "absent/malformed," and never reached for "stale but
well-formed," which is the realistic way a live feed actually dies mid-sortie.

**Caught by reproduction, not by reading the diff**: wrote a small script calling
`_resolve_sun_elevation_deg` repeatedly with the *same* `mission_clock` dict while advancing the
ownship's `t_sim` by three minutes each call, across ~20 calls (~57 simulated minutes). The
resolved sun elevation never changed and `light_level_error_logged` stayed `False` the entire
time. Reading the function's own docstring and tests would not have surfaced this -- every test
in `TestResolveSunElevationDeg` either supplies a fresh sample once then simulates absence
(`None`) afterward, or tests absence directly; none supplies the *same* dict twice to check
whether "unchanged" is treated differently from "fresh."

**Why:** this is the same shape as `feedback_watchdog_backstop_conflates_failure_modes` --
a staleness/watchdog mechanism's docstring and tests cover the loud failure mode (the read fails
outright) and never consider the quiet one (the read keeps succeeding against data that stopped
updating). The two require different detection: "did this read fail" is cheap and obvious;
"did this read change" needs either a sequence number, a timestamp set at ingest (not at
snapshot-serve time -- `received_wall_clock_s` here is `time.time()` evaluated fresh on every
`GET`, so it already cannot answer "when did this last change" either), or a comparison against
a monotonically-advancing field the wire already carries (`dcs_model_time_s` was sitting right
there, unused for this purpose).

**How to apply:** whenever reviewing any "if the feed goes stale, fail loud" mechanism fed by a
polled snapshot (not a push/delta feed), ask specifically: does the staleness check have access
to a signal that can tell "unchanged" apart from "freshly re-sent but identical"? If the upstream
cache only ever stores "the most recent thing I received" with no sequence/ingest-timestamp, a
dead producer that stops updating is invisible to a consumer that just checks "did my read
succeed." Reproduce by feeding the same wire value repeatedly across a window far longer than the
staleness bound, not by reading the grace-window logic and assuming a dropped read is the only
way staleness happens.
