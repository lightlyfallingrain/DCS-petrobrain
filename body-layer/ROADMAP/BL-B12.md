# BL-B12 — Coalition/IFF for contact reports

- [>] **BL-B12 — Coalition/IFF for contact reports — deferred, inferred not omniscient.** #status/deferred Raised 2026-09-10:
  the new contact-report format (`belief/speech.py`'s `render_contact_report`) has a
  FRIENDLY/ENEMY/HOSTILE/UNKNOWN slot, always `"UNKNOWN"` for now — no coalition/IFF perception
  channel exists (`perception.association`'s own docstring: "no coalition/IFF filtering"), and
  reading `LoGetWorldObjects`'s real ground-truth coalition straight into `Contact` would violate
  the no-omniscience invariant `percept.py` enforces on purpose. **User decision: when built, infer
  coalition from unit-type vocabulary (which types each side is known to field) and world position
  (whose controlled terrain the contact sits in) — not from DCS truth.** Terrain-control data
  doesn't exist in world-model yet either. Not scoped to a specific BL-x milestone. **Do not start
  without the user's instruction.**
