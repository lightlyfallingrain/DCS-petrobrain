# BL-W29 — Internal identifiers were being read aloud

- [x] **Internal identifiers were being read aloud — fixed 2026-09-23** #status/done (`fix/spoken-vocabulary`).
  The sortie produced *"unit at 12 o'clock, 2 kilometres is OP_LRSAM"* and *"...is
  OP_GROUPSOMETHING"*: this codebase's own `op_class` bucket names, spoken to the pilot.

  **The cause is worth more than the fix.** `_OP_CLASS_DISPLAY` carried a comment stating that
  every `op_class` the object model assigns had an entry, and that was true when written.
  `OP_LRSAM` arrived later with the aspect-profile work and was never added, and the unmapped
  fallback returned the value *verbatim* — so a vocabulary gap became an intelligibility failure
  rather than a specificity one. The comment was the only thing enforcing the invariant, and a
  comment cannot fail. `test_speech.py` now derives the class set from `object_model` itself, so
  the next class added there fails a test instead of reaching the audio channel.

  A second stale claim fell with it: `OP_GROUPSOMETHING` was documented as unreachable at `class`
  level. The transcript disproved it.

  **Wording decided with the user, from the same transcript:**
  - The three SAM tiers are spoken apart — *short range SAM* / *medium range SAM* / *long range
    SAM* — rather than all collapsing to "SAM". The difference between a short-range and a
    long-range SAM is the difference between a threat you can fly around and one you cannot, so
    flattening them discards the most decision-relevant part of the call.
  - `AAA` is spoken *"triple A"*. Not a mis-reading fix like the `Mi-XX` entries: the letters are
    pronounced correctly and are still the wrong thing to say.
  - `OP_GROUPSOMETHING` is *"group"*.

  **One over-reach caught by the existing tests, worth recording.** The first fix replaced *every*
  unmapped class value with a generic word, which would have reduced *"BMP-2"* to *"contact"* — a
  `class`-level value is not always an `OP_*` bucket; it can be a raw DCS type name or scope/hybrid
  free text, and those are already sayable. The rule is narrower than it first looked: suppress the
  `OP_` prefix specifically, pass everything else through.

  Also fixed from the same transcript: *"1 kilometres"* → *"1 kilometre"*. Only exactly 1 takes the
  singular, which is why it is an equality check and not a less-than-or-equal one.

