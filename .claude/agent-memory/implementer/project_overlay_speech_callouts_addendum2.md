---
name: overlay-speech-callouts-addendum2
description: Terser crew-text (addendum 2) implementation notes — rounding tie-boundaries, CONTACT_LOST no-template, id/coalition removal.
metadata:
  type: project
---

Implemented the third live-test round of `plans/overlay-speech-callouts/plan.md` (feature branch
`feature/overlay-speech-callouts`, commits 0b280f9/dacd642/ddf862e/c6baf64).

- `_format_range_km`/`_round_enrichment_fragment` tie-boundary inputs (1250m, 1750m, 450m) hit
  Python's `round()` ties-to-even, not round-half-up — pinned tests to actual output (`"1"`/`"2"`,
  `"~400m"`) rather than a guessed convention, since the plan itself flagged this as unspecified.
  Worth a live-acceptance check: a contact at exactly 1750m reads "2 km" but one at exactly 1250m
  reads "1 km" — not obviously symmetric to a listener.
- `CONTACT_LOST` moved to `_render_lifecycle_text` returning `None` — no structural change needed
  in `route_event`, its existing `if text is None: return None` ordering already leaves the event
  unacknowledged, same as `CONTACT_ATTENTION_CHANGED`.
- `CONTACT_CLASSIFICATION_CHANGED`'s new position line reads `result["facts"]["relative_now"]`,
  which only exists when an `EnrichmentContext` was passed to `route_event` — wrote both an
  enriched and unenriched test rather than assuming one case.
- `render_contact_report`'s format changed too (Design point 8's resolved fork) — the terser
  wording applies everywhere `_contact_report_text` is used, not just lifecycle lines; this was a
  deliberate architect call in the plan addendum, not something the Implementer decided.
- Full-suite check (per [[verify_full_suite_not_just_new_files]] habit) caught no surprises this
  time — all breakage was already anticipated in the plan's own "Affected Modules" list.
