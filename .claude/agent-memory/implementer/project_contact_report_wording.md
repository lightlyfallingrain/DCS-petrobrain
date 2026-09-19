---
name: contact-report-wording
description: What the "Contact report fine tuning" roadmap item's cheap wording changes actually became, and where the roadmap's own examples were wrong.
metadata:
  type: project
---

Implemented body-layer/ROADMAP.md's 4 cheap "Contact report fine tuning" items on
`feature/contact-report-wording` (2026-09-19): spelled-out units, per-token TTS acronym
respelling, "very close" under 0.5 km, and "on"/"next to" short-range feature wording.

**The roadmap's own worked examples were unverified and one was simply wrong.** "LR" (item 2's
example) does not occur anywhere in the real sayable vocabulary — checked `_OP_CLASS_DISPLAY`/
`_OP_CLASS_DISPLAY_PLURAL` and the 377-entry `dcs_type_to_reporting_name.tsv` catalogue, zero
hits — so it was left out of `_TTS_TOKEN_RESPELL` rather than added on faith. "MI-8" (same
example) also isn't the literal string; the real catalogue holds `"Mi-8"` mixed-case. Lesson:
even a roadmap item written from live-testing notes can carry examples that were paraphrased
rather than transcribed — grep the actual vocabulary before building a table keyed on a prose
example, per [[feedback_verify_keyword_vocab_against_real_strings]].

Only `belief.speech.OutgoingSpeech.text` ever reaches TTS (via `crew_console.py`'s `_print` ->
`srs_client`). `belief.tools.py` has its own separate, differently-named `_format_range_km` used
only by console-debug text (`_contact_summary`) — never touches TTS, correctly out of scope for
a "spell units for TTS" task even though the function name is identical to the one in speech.py.
