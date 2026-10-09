# BL-B16 — Cross-channel contact duplication

- [ ] **BL-B16 — Cross-channel contact duplication — continuity maps are per-channel, not shared.** #status/open Found
  2026-09-10 during the object-permanence fix's live acceptance: a real civilian bus was tracked as
  two separate contacts, one per channel (naked-eye and scope/HelperAI), because each
  `PerceptionSource` instance keeps its own `object_id → observation_id` continuity map, not a
  shared cross-channel store, even though the underlying DCS `object_id` namespace is global.
  Candidate fix: a shared, cross-channel map (owned where — `belief/`? a new shared perception-layer
  component?). Not investigated or scoped yet.
