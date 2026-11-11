---
name: bl-b111-expected-area-look-cost
description: Measured per-poll cost of BL-B111's expected-area look (resolve_checks, probe_points_for, area_visibility) -- all negligible under MAX_OPEN_CHECKS=2; one redundant GET found, one log-writer frequency drift flagged for future precedent use
metadata:
  type: project
---

Performance review of `BL-B111` (`plans/expected-area-look/plan.md`,
`feature/expected-area-look` @ `27eaed47`). Full report: `plans/expected-area-look/performance.md`.
Measurement script: `plans/expected-area-look/perf_probe_b111.py` (run from `body-layer/` with
`PYTHONPATH=src:../world-model/src`).

## Everything on this hot path is bounded by `MAX_OPEN_CHECKS = 2`, not by contact/candidate count

Unlike almost every other per-contact cost finding in this codebase (`look_target_for`,
`group_salient_ids`, `choose_look`'s O(k²)), `_resolve_expected_area_checks`'s own loop iterates
`runner.store.checks`, capped at 2 by `ContactStore.ingest`'s own cap check before a third check
opens. **Measured directly** (fresh venv, no venv existed in the worktree --
`python3.12 -m venv .venv` + `pyproj>=3.6` + `numpy>=1.26,<2.5` matches `pyproject.toml` exactly):

| function | cost |
|---|---|
| `probe_points_for` | 2.14 µs/call |
| `area_fits_one_look` | 1.52 µs/call |
| `a_out_of_view` | 0.07 µs/call |
| `area_visibility` | 0.38 µs/call |
| `resolve_checks` (1 check) | 13.2 µs/call |

At the worst case of 2 concurrent checks, the feature's own new code costs **~35 µs/poll —
0.0035% of the 1.0 Hz budget**. Composing in the already-measured reused primitives
(`look_target_for` ~5.75 µs, cockpit-mask `is_visible` ~1.44 µs, `profile_for`/`tier_ranges`
~1.9 µs, each called once per check) adds at most another ~18 µs at 2 checks. Still three orders
of magnitude under budget.

## Found but not NOW: a second `GET /line_of_sight/latest` per poll while a check is open

`body.py:1602`'s `_resolve_expected_area_checks` calls `aircraft_client.get_line_of_sight_latest()`
directly, but `perception/naked_eye_source.py:740` already fetches the same endpoint once per poll
for `NakedEyePerceptionSource.poll`. Gated correctly behind `if not checks: return`, so this only
fires during the rare window a check is open (not a per-poll cost at scale) -- unlike the
`[[feedback_gated_http_call_before_the_gate]]` defect shape, the fetch here *is* correctly placed
after the gate, not before it. Still a real, avoidable redundant round trip while a check is open.
Flagged LATER: fix by threading the one sample `naked_eye_source` already pulled through to
`body.py`, picked up opportunistically next time this path is touched, not worth a standalone
change-request cycle on its own.

## `ExpectedAreaLogWriter` is the first instance of the open-append-close JSONL pattern at
## per-check-per-poll frequency, not per-utterance

`[[project_speech_log_writer_is_the_reusable_low_frequency_jsonl_pattern]]` pre-approves
`SpeechLogWriter`'s open-append-close-per-write shape only at per-utterance/per-clip frequency,
explicitly flagging that a per-poll/per-tick call site would need buffering instead.
`expected_area_log.py`'s `ExpectedAreaLogWriter` is called once per *open* check per poll (not
per-utterance) -- a real frequency drift from every prior instance of this pattern. Approved here
anyway because both axes are tightly bounded: `MAX_OPEN_CHECKS` (2) rows/poll ceiling, and only for
the duration one check stays open (≤ 17 s worst case). Defaults off, true no-op when absent. **Do
not cite this file as blanket precedent for the pattern at an actually-unbounded per-poll
frequency** -- the bound that makes it safe here is `MAX_OPEN_CHECKS`, not the pattern itself.

## Harness note: `Observation.range_m` alone does not widen `area_fits_one_look`

A sanity-check attempt using a very distant contact (`range_m=50_000`) to prove the "does not fit
one look" branch reachable *failed* -- `area_half_width_deg` is `atan(sigma_cross / range)`, so a
larger range alone *shrinks* the angle unless `sigma_cross` also scales with it. Use a close range
with a large declared `PositionUncertainty.sigma_cross_m`/`sigma_down_m` instead to force the wide
branch. Worth remembering before writing any future harness against this module.

See [[project_bl_b110_expected_area_check_sector_and_location_gain_cost]] for the sibling BL-B110
measurements this feature's reused primitives come from, and
[[project_body_layer_poll_loop_serial_unpooled_gets]] for the pre-existing no-connection-pooling
debt `post_probe_points`/`get_line_of_sight_latest` both inherit (not introduced here).
