### Implementation Summary (fix/group-undermerging, 2026-10-01, follow-up)

Follow-up fix to the previous round's `"a armor"` -> `"an armor"` patch, which corrected the
wrong half of the bug. `"armor"` is a mass noun; it takes no indefinite article in any form, so
`"an armor"` is not English either. The real defect was adding an indefinite article to a
count==1 class/type noun inside group-composition rendering at all — a behaviour that existed
only in `_group_composition_clause`'s count==1 branch (via `_with_indefinite_article`) and
nowhere else in this module's singular vocabulary.

**Decision (point 2 of the task): count nouns and mass nouns are treated identically — no
indefinite article at all**, not a selective fix that keeps the article for count nouns
(`"truck"`, `"Shilka"`) and drops it only for mass nouns (`"armor"`, `"infantry"`). This isn't a
new rule invented for this fix; it's bringing one outlier function in line with a convention
every other part of this module already follows:

- `_contact_report_text`'s own single-contact line never prepends an article (`"armor, 2
  o'clock, 2 kilometres."`, not `"an armor..."`).
- `_identification_lead`'s `"armor 11 o'clock... is BTR-80"` is bare.
- The user's own worked examples (`plans/group-cohesion-redesign/explore-notes-delta-
  taxonomy.md`) never use an article in a composition/list context, and critically, **count
  nouns are exactly as bare as mass nouns there**: `"AAA in the group"`, `"Shilka and zsu"`,
  `"SRSAM, Shilka, armor 2 o'clock 2.5 km"`. The only article anywhere in that file is `"there's
  a zsu"`, which is a different sentence frame (an existential singular announcement, not a
  composition clause) and is not evidence for treating count nouns specially inside
  `_group_composition_clause`.

So there was no count-noun/mass-noun split worth maintaining in this one function. Removed
`_with_indefinite_article` and `_VOWEL_INITIAL_CLASS_WORDS` entirely rather than growing the
exception set, per the task's explicit instruction.

### Files Changed
- `body-layer/src/belief/speech.py` — deleted `_VOWEL_INITIAL_CLASS_WORDS` and
  `_with_indefinite_article`; `_group_composition_clause`'s count==1 branch now appends
  `_unit_type_display(value, level)` directly (bare noun, no article). Updated two docstring
  worked examples that still showed the old articled form (`render_group_disclosure`'s
  "Differentiated but mixed" bullet: `"A tank and a truck"` -> `"Armor and truck"`).
- `body-layer/tests/test_speech.py` — fixed five assertions that had pinned the bug as expected
  output (not just the two the task named):
  - `test_group_composition_clause_singular_uses_indefinite_article` (renamed
    `test_group_composition_clause_singular_is_bare_noun`) — `"a truck"` -> `"truck"`.
  - `test_group_composition_clause_counts_members_exactly` — `"two armor and a truck"` ->
    `"two armor and truck"`.
  - `test_render_group_disclosure_differentiated_group_gives_composition` — `"Two armor and a
    truck."` -> `"Two armor and truck."`.
  - `test_render_group_disclosure_first_differentiation_is_full_once` — `"A truck and
    something."` -> `"Truck and something."`.
  - `test_render_group_disclosure_mixed_pair_uses_the_composition_clause` — `"An armor and a
    truck."` -> `"Armor and truck."` (the task's first named case).
  - `test_render_group_disclosure_new_class_arrival_is_a_delta` — `"An armor, in the group."` ->
    `"Armor, in the group."` (the task's second named case).
  - `test_render_group_disclosure_air_defence_repeat_arrival_is_a_delta` — `"A ZSU-23-4 Shilka,
    in the group."` -> `"ZSU-23-4 Shilka, in the group."`.
- `body-layer/tests/test_callouts.py` — `test_2c_transcript_fixture_renders_four_lines_not_seven`
  (an end-to-end fixture spanning three group members): `"Three infantry, a BTR-70 and a truck,
  ..."` -> `"Three infantry, BTR-70 and truck, ..."`.

No tests added — this is a rendering-vocabulary correction over existing coverage, not new
behaviour; the real content-impact checks (delta taxonomy branch selection, cardinality,
threat-leading) are unchanged and were already asserted by the tests above.

### Checks (body-layer/)
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (no issues, 53 source files)
- `pytest tests -q`: pass — 1367 passed, 4 xfailed (matches stated baseline)

### Notable Discoveries
- **Every assertion the previous round's green suite missed was in `_group_composition_clause`'s
  blast radius, not just the two the task named.** Five test assertions across two files had the
  bug pinned as expected output: the two named in the task, plus
  `test_group_composition_clause_singular_uses_indefinite_article` (whose own *name* asserted
  the bug was correct behaviour), `test_group_composition_clause_counts_members_exactly`, the
  "Two armor and a truck"/"A truck and something" full-disclosure-composition cases, and one
  end-to-end fixture test in `test_callouts.py`. Confirms this task's point 4: a green suite is
  not evidence of correct wording when the wording itself was never independently checked
  against the specification (the user's own worked utterances) — only against whatever the
  implementation happened to produce at write time.
- **`plans/group-undermerging/review.md` does not exist and never has** (`git log --all` on the
  path returns nothing), despite being cited as the source of "Finding 1"/"Finding 2" in several
  docstrings and comments already in this file before this round (`_undifferentiated_phrase`,
  the `OutgoingSpeech.content_signature` entry, and the previous round's own commit message).
  Either the review was conducted but its document was never committed, or the citation was
  aspirational. Flagging rather than fixing — writing that review document is Reviewer's job, not
  Implementer's, and I did not want to fabricate review content to make the citation resolve.
