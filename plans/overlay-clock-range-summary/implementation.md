### Implementation Summary

Added a clock-position/range fragment to `belief.tools._contact_summary`'s one-line summary,
rendered whenever `relative_now` (BL-3's `relative_geometry()` output) is available -- appended
after the existing classification/certainty/recency/watched content, never replacing it, per the
plan's Decision 1. `describe_contact`/`get_contacts`/`find_contact` (via the shared
`_contact_result`) thread `facts["relative_now"]` (already computed once by
`_add_enrichment_facts`) into the summary without a second `relative_geometry()` call.
`console.format_event_for_overlay` needed no code change -- it already reads `summary` verbatim,
so the overlay/console `show`/`contacts` output picks the fragment up automatically. Confirmed
this with a new integration test.

### Files Changed
- `body-layer/src/belief/tools.py` -- added `_format_range_km(range_m: float) -> str` (1-decimal
  km, e.g. `"3.0 km"`); `_contact_summary` gained an optional `relative_now: dict[str, object] |
  None = None` parameter, appending `", <clock> o'clock, <range> km."` when supplied (after the
  "Being watched." suffix, if present); `_contact_result` now builds `facts` first and passes
  `facts.get("relative_now")` into `_contact_summary`, reusing the one `relative_geometry()` call
  `_add_enrichment_facts` already made.
- `body-layer/src/belief/console.py` -- no logic change; added a one-line docstring note on
  `format_event_for_overlay` acknowledging `summary` now also carries the clock/range fragment
  when present, so a future reader doesn't wonder where it comes from.
- `body-layer/tests/test_tools.py` -- imported `_contact_summary`/`_format_range_km` directly
  (plan explicitly names testing `_contact_summary`); added unit tests for km rounding, the
  no-`relative_now` no-op case, the with-`relative_now` fragment (including after "Being
  watched."), and an integration test through `describe_contact` with enrichment confirming the
  summary's suffix matches `facts["relative_now"]` and `_format_range_km`.
- `body-layer/tests/test_console.py` -- added an integration test confirming
  `format_event_for_overlay` picks up the `o'clock`/`km` fragment when enrichment is supplied, for
  free, with no change to that function itself.

### Tests Added
- `test_format_range_km_rounds_to_one_decimal` -- km rounding at exact and near-boundary values.
- `test_contact_summary_without_relative_now_is_unchanged` -- no-enrichment-means-no-change guard
  on the summary string itself.
- `test_contact_summary_with_relative_now_appends_clock_and_range` -- exact fragment format and
  placement.
- `test_contact_summary_appends_fragment_after_being_watched_suffix` -- fragment ordering when
  both "Being watched." and `relative_now` are present.
- `test_describe_contact_summary_includes_clock_range_when_enriched` -- integration: summary's
  suffix matches the same `facts["relative_now"]` values threaded through `_contact_result`.
- `test_format_event_for_overlay_includes_clock_range_when_enriched` -- integration: the overlay
  line inherits the fragment via `summary` with zero `console.py` code change.

### Checks
- ruff format --check body-layer/src body-layer/tests: pass
- ruff check body-layer/src body-layer/tests: pass
- mypy body-layer/src (strict, run via `cd body-layer && mypy src` per this subproject's
  CWD-only config discovery): pass
- pytest body-layer/tests -q: 291 passed (285 baseline + 6 new)

### Notable Discoveries
- Float formatting confirms `3050.0 / 1000 == 3.0499999999999998...` in IEEE-754, so
  `f"{...:.1f}"` rounds it *down* to `"3.0 km"`, not up to `"3.1 km"` as naive half-up rounding
  would suggest -- the km-rounding test picks unambiguous values (3040/3060) to avoid asserting
  on that float-representation quirk.
- `console.py`'s "no code change" prediction held exactly as the plan expected -- confirmed with
  a real integration test rather than just trusting the prose, per this project's
  verify-before-claiming discipline.
