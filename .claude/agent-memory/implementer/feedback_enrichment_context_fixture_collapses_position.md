---
name: enrichment-context-fixture-collapses-position
description: body-layer tests/test_speech.py's _enrichment_context fixture fakes project_terrain_aware as an identity stub, so any contact's relative_now range collapses to 0 ("very close") regardless of the observation's own range_m -- do not assert a literal range figure through it
metadata:
  type: feedback
---

`tests/test_speech.py`'s (and `test_console.py`'s matching) `_enrichment_context(monkeypatch)`
fixture monkeypatches `belief.enrichment.project_terrain_aware` to
`lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer` -- it returns
`observer` (ownship's own position) unconditionally, ignoring `bearing`/`rng` entirely. This is a
stand-in for a real world-model `.sqlite` (the real function walks a bearing/range ray against
real terrain), not a faithful re-derivation of the observation's geometry.

**Consequence**: any `describe_contact`/`_contact_report_text` call routed through this fixture
gets a `relative_now["range_m"]` of (close to) `0.0`, which `_format_range_km`'s
`_VERY_CLOSE_RANGE_M` (500 m) branch renders as the literal string `"very close"` -- **not** the
observation's own `range_m` (e.g. `1000.0` renders as `"1 kilometre"` everywhere else in this
codebase, but as `"very close"` once this fixture is in the chain). This surprised me on a first
attempt at `test_route_event_contact_firing_seen_visible_firing_at_others_says_type_and_range`:
I wrote `assert speech.text == "BMP-2, 12 o'clock, 1 kilometre, firing."` and it failed with
`"BMP-2, 12 o'clock, very close near Jableh (~200 metres), firing."` instead.

**How to apply**: this project already has the right workaround, just not named anywhere --
`test_route_event_contact_detected_includes_clock_range_when_enriched` asserts
`speech.text.startswith("BMP-2, ")` / `"o'clock" in speech.text` / `"Jableh" in speech.text`
rather than the literal rendered string. Any new speech test that both (a) needs `relative_now`
populated (so it must pass `_enrichment_context(monkeypatch)`, since without enrichment
`relative_now` is absent and most render functions return `None`/omit clock+range entirely) and
(b) cares about the range wording specifically, should use the same loose
`startswith`/`in`/`endswith` style rather than pinning an exact range figure -- the figure is a
fixture artifact, not something the production code under test controls. If a test genuinely
needs to assert a *specific* range figure, it must supply its own `project_terrain_aware` stub
that actually projects along `bearing`/`rng` (or avoid enrichment and assert on the
range-figure-free, enrichment-less rendering instead).

See also: `plans/taking-fire-visible-shooter/implementation.md`'s "Tests Added" section for the
worked example.
