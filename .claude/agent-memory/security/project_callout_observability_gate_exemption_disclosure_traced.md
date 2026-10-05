---
name: callout-observability-gate-exemption-disclosure-traced
description: The engagement-change exemption's "belief-derived only" premise was traced to ground and holds — don't re-derive it; the open question was the "Safe from" direction.
metadata:
  type: project
---

`fix/callout-observability-gate` (tip `24fa35d`, 2026-10-06) exempts
`CONTACT_ENGAGEMENT_CHANGED` from the speech-layer observability gate. The exemption's premise —
that the line invents no knowledge — was traced to ground and **holds**. Do not re-derive this
chain:

- unit type: `_contact_report_text` → `_classification_facts` (`belief/tools.py:206`) reads
  `contact.classification` (folded belief), never `last_class_raw`; confidence decays via
  `classification_confidence_at`.
- clock/range: `facts["relative_now"] = relative_geometry(enrichment.ownship, world_position)`
  (`belief/tools.py:354`), `world_position` resolved from `Contact.last_position`.
- `Contact.last_position` is a read-only property; `record`/`from_percept` via `fold_position`
  are its **only** writers, both reached only through `ContactStore.ingest`. Both perception
  channels are direction-constrained (`naked_eye_source` applies the cockpit mask;
  `hybrid_source` is bounded by `association.FORWARD_HEMISPHERE_HALF_WIDTH_DEG`), so **a
  contact's position cannot refresh while it is behind the mask**. An exempt line's clock hour is
  dead reckoning over a remembered position against current attitude, not a fresh fix.
- `hybrid_source` is not a truth channel: it reads the in-game HelperAI indication leaves, and
  `object_id` never leaves `perception/` (`perception/source.py:225`).
- `envelope_for` (`belief/threat.py:209`) is strictly belief-keyed with no fallback envelope.

Also verified sound and not worth re-checking: `_callout_may_speak` is called unconditionally in
`tick`'s per-contact loop (`belief/contacts.py:1226`, no `continue` above it), so
`last_observable_sim` is stamped for every contact every ticked frame and `callout_observable`
can never read a stale stamp; `_observability_tracked` is set before the loop; production never
mixes ownship-less ticks. The gate defers rather than consumes and sits *after* the
`CALLOUT_MAX_AGE_S` check, which is what bounds the deferral.

**The finding was elsewhere** — the `engaged=False` ("Safe from") transition, see
[[project_exemption_from_a_gate_check_both_transitions]]. Verdict: APPROVED WITH REQUIRED FIXES,
`plans/callout-observability-gate/security-review.md`.
