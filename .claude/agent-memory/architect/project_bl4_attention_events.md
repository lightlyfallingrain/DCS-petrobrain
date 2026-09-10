---
name: project_bl4_attention_events
description: BL-4 attention/events plan design — 4-state attention, area = center+radius (no place resolution), cooldown vs classification lockout distinction, ack via ContactStore set not Event mutation
metadata:
  type: project
---

Plan: `plans/bl4-attention-events/plan.md`, branch `feature/bl4-attention-events`, branched from
main (post BL-2.6/BL-3 merge), 2026-09-10.

**Resolved without escalation, both from existing doc evidence:**
- Attention states = exactly 4 (`ignore`/`normal`/`watch`/`priority`), matching BL-5's already-
  written `set_attention` signature in `plans/body-layer/plan.md` §3.3. Runtime doc's `TRACK` is
  explicitly threat-priority-table territory (BL-6+), not BL-4.
- Event-queue ownership: BL-4 builds the full ack/unacknowledged mechanism + console commands
  (`events`, `ack <id>`); BL-5 only wraps it as `poll_events`/`acknowledge_event` tools. Same
  precedent as BL-2 building `watch_contact`/`unwatch_contact` ahead of BL-4/BL-5 wrapping.

**Design choices worth remembering if revisited:**
- `AttentionArea` = center `GeoPosition` + radius + optional cardinal sector, resolved via
  bearing/range from ownship (reusing `perception.geometry.bearing_deg`/`project_from_bearing_
  range`) — deliberately NOT a place-name/polygon type. `find_place` (natural-language place ->
  position) stays BL-5/BL-6 work; BL-4's `watch_area` console command takes raw bearing/range, not
  a place string. This is a real seam BL-5 must bridge later — flagged in the plan, not solved.
- `effective_attention`: a contact's direct `"ignore"` always wins over area membership (explicit
  suppression shouldn't be overridden by wandering into a watched area); otherwise take the
  higher-ranked of direct mark vs. best-matching area. Judgment call, reversible, not escalated.
- Event cooldown (`EVENT_COOLDOWN_S`, per-contact-per-kind, suppresses re-*emission*) is a
  **different mechanism** from classification's existing 30s contradiction lockout (suppresses
  re-*promotion* of a value). Don't conflate them if debugging chatter later.
- Acknowledged-event tracking lives as a `set[str]` on `ContactStore`, not a mutable field on
  `Event` (which stays `frozen`) — avoids touching existing `Event` construction sites/tests.
- `Attention` type moves from `contacts.py` to new `belief/attention.py`, alongside `AttentionArea`
  and `effective_attention` (takes `Contact` under `TYPE_CHECKING`, same import-cycle pattern as
  `decay.py`'s `certainty_of`).

See also [[project_bl2_contact_memory_design]] (the `last_emitted_*` comparison pattern this
milestone extends a third time — lifecycle, classification, now attention) and
[[project_bl26_classification_refinement]] (the classification lockout this cooldown must not be
confused with).
