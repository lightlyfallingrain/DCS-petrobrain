# BL-B53 — The *what* slot takes seven singular words, and the user's own examples miss

- [ ] **BL-B53 — `report trucks near`, `report tanks near`, `report armour north` and
  `report air defence near` all silently drop the descriptor.** #status/open Found by DoD during
  [[BL-13]], 2026-10-10, measured on the shipped matcher.

  `DESCRIPTOR_WORDS` holds seven **singular** words (`armor`, `truck`, `infantry`, `sam`, `aaa`,
  `ship`, `group`). Plurals, the British spelling, and the natural two-word form *"air defence"* all
  fail to parse, so the query widens to the whole scene with no signal that a word was dropped.

  **The decisive detail: the user's own grammar request used "trucks" and "air defence."** So the gap
  is in the vocabulary, not in his phrasing — a pilot speaking normally will miss, and
  [[BL-13]]'s grammar was specified from words that do not currently work.

  **The degradation is honest** — wider, never wrong; he hears a general report rather than a false
  one. That is why this is backlog and not a defect gate. But it undercuts the feature's purpose: the
  point of the *what* slot is a narrow answer, and the commonest spoken forms do not reach it.

  Fix shape: plurals, `armour`, and multi-word `air defence`/`air defense` in `DESCRIPTOR_WORDS`,
  with the audio-adapter ↔ body-layer mirror-pair tests extended on both sides (that pair is
  hand-synced by the module-independence rule, so a one-sided addition drifts silently). Pairs with
  [[BL-B52]] and [[BL-B54]].

  Worth re-reading [[BL-13]]'s plan when this is taken: its grammar table is the specification these
  words were drawn from, and it should be corrected in the same pass so the next reader does not
  re-derive the gap.
