---
name: project_contact_report_wording_approved
description: contact-report-wording (9035317) reviewed, APPROVED clean — SAM-safety and vocabulary claims verified real
metadata:
  type: project
---

Reviewed `feature/contact-report-wording` (commit `9035317`, body-layer only: `speech.py`
units/respelling, `enrichment.py` on/next-to thresholds). APPROVED, no required fixes.

Two claims worth noting as a pattern for future reviews of this kind (acronym/table-driven
respelling safety claims):
- The "SAM structurally can't be respelled" claim held on **two independent layers**: level
  scoping (`_respell_for_tts` only called from the `type` branch, never `class`) AND table
  content (`"sam"` isn't a key in `_TTS_TOKEN_RESPELL` anyway, so even a bypass would no-op).
  Verified both by grep, not just accepted the "structural, not table-dependent" framing —
  worth checking both layers whenever an implementer claims a guarantee is "structural."
- The implementer's claim that a roadmap worked example (`"LR"`) doesn't exist in the real
  vocabulary, and that another (`"MI-8"`) has wrong casing (real string `"Mi-8"`), was
  independently reproduced by grepping the 595-row reporting-name TSV myself — both checked out.
  This is the same "verify vocabulary/data claims directly" discipline as
  [[project_vision_calibration_research_doc_error]], applied to a static data table this time
  instead of a live probe.

Only finding: the roadmap's own "running list" entry wasn't annotated to show the four cheap
sub-items are done (parent checkbox correctly stays open since bearing/airborne items remain) —
flagged optional, not required.
