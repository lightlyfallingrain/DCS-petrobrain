---
name: overlay-speech-callouts-addendum
description: Addendum fixing CONTACT_DETECTED/REACQUIRED lifecycle callout content in belief/speech.py
metadata:
  type: project
---

Same-day addendum to `plans/overlay-speech-callouts/plan.md` (routing mechanism already merged/
approved separately) fixed what `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
branches actually said — extracted shared `_contact_report_text(facts)` in `belief/speech.py`,
reused by both `render_contact_report` (id-less) and the two lifecycle branches (id-prefixed).
`CONTACT_LOST`/`CONTACT_CLASSIFICATION_CHANGED` stayed untouched by design.

Two pre-existing tests in `test_crew_console.py` (not named in the addendum's own Affected Modules
list) had hardcoded the exact broken `f"{contact_id} BMP-2."` output and failed once the fix
landed — full-suite run (not just the addendum's named test file) is what caught this; see
[[verify_full_suite_not_just_new_files]].

`facts["semantic"]` is `list[dict]` via `asdict(SemanticFact)` (not a list of `SemanticFact`
objects) — `tools.py`'s `describe_contact` converts it before putting it in `facts`. Confirmed by
grepping `tools.py` rather than assuming from the dataclass definition; `_contact_report_text`'s
`max(semantic, key=lambda fact: fact["confidence"])` mirrors `console.py`'s
`format_event_for_overlay` exactly, both reading dict keys not attributes.

Reused `test_console.py`'s `_enrichment_context`/`_FakeInfo`/`_FakeDescription` fixture pattern
verbatim (copied, not imported — per-test-file fixture convention) into `test_speech.py`, which had
no enrichment test fixtures of its own before this addendum.
