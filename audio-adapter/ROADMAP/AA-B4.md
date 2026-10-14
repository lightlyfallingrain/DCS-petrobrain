# AA-B4 — Anchor a verb on its position in the sentence, not on the word alone

- [ ] **AA-B4 — Make a verb anchor on sentence position (or on a parseable target slot), so a
  command verb can be added without widening the set of ordinary sentences that anchor.**
  #status/open User direction, 2026-10-14, chosen from three options with the measured collision in
  front of him: *"Add attack, fix the anchoring properly."*

  ## Why this exists

  `BL-14`'s attack run needed `engage`, and the user's own spec
  (`docs/concept/Attacking target.md`) names **`attack`** and **`attack-run`** as synonyms for it.
  They were deliberately **not** shipped. `VERB_ANCHOR_WORDS` is derived from
  `vocabulary.PHRASES` rather than hand-listed (correctly — see `command_matcher.py`'s own
  reasoning), so adding either phrasing makes `"attack"` an anchor word, and:

  | pair | `difflib.SequenceMatcher` ratio | vs `VERB_FLOOR` = 0.5 |
  |---|---|---|
  | `"tanks"` vs `"attack"` | **0.545** | over |
  | `"trucks"` vs `"attack"` | **0.500** | exactly on it |
  | `"tanks"` vs `"engage"` | 0.182 | nowhere near — which is why `engage` ships |

  Measured twice independently (the implementer, then the orchestrator). So `"the tanks are on the
  ridge"` — an ordinary thing to say over an intercom — starts anchoring as a command attempt, and
  an existing pinned adversarial test for exactly that sentence flips.

  **The user's reason for fixing the rule rather than accepting the collision**: the anchor floor
  exists to protect free speech, so widening the anchor set to honour a synonym trades the
  protection for the vocabulary. Two of the most common nouns the pilot says are the ones it lands
  on.

  ## What the fix has to respect — read this before designing it

  `command_matcher.py`'s module docstring has the reasoning the fix must not break, and it cuts
  against the obvious "just raise the floor":

  - **The two floors guard asymmetric costs and are set as a pair.** A false *anchor* costs one
    extra phrase-scoring pass that usually rejects it anyway. A false *rejection* at the anchor is
    worse and irreversible — it discards the transcript before `_phrase_match_ratio`, the actual
    defence, ever runs, so a command the pilot really spoke falls through as free speech instead of
    executing. That is why `VERB_FLOOR` (0.5) sits *below* `MATCH_FLOOR` (0.6).
  - **There is a real transcript pinning the low floor**: `"skin bearing 315"`, from the user's own
    recorded corpus (a mishearing of *"scan bearing three one five"*), fails to anchor at all at
    0.6, since `ratio("skin", "scan")` = 0.5. Raising the floor to dodge `attack` would discard that
    command.
  - **The phrase-sequence score is the real defence**, not the anchor. `"look at that"`,
    `"watch out"` and `"report says otherwise"` all anchor today and are rejected downstream.

  ## Two candidate shapes, neither chosen

  1. **Positional**: a verb anchors only sentence-initially (optionally after the wake word). `"attack
     armor 2 o'clock"` anchors; `"the tanks are on the ridge"` does not, because `tanks` is not the
     first word. Cheap, and it removes the whole collision class rather than this instance.
  2. **Slot-conditional**: a verb anchors only when followed by something the slot parser can read
     as a target. Stronger, and closer to what `BL-13`'s slotted grammar already knows how to do.

  Both need checking against the corpus the existing tests pin, including the real mishearings.

  ## One thing to establish first, because it may shrink the problem

  The claim driving this item is that the flipped test means *"the tanks are on the ridge"* would
  get **"say again"** instead of falling through to free speech. **That is asserted, not measured.**
  `command_matcher.py`'s own docstring says a false anchor *"costs one extra phrase-scoring pass
  that almost always rejects it anyway"* — in which case the final observable is unchanged and only
  the intermediate `verb_anchored` flag differs. Run the sentence end to end with `attack` added
  before designing anything: if phrase scoring already rejects it, this item is much smaller than it
  looks, and the honest fix might be to re-pin the test on the *final* observable rather than on the
  intermediate flag.

  ## Done when

  `attack` and `attack-run` are live synonyms for `engage`, the adversarial corpus still rejects
  ordinary sentences end to end, and `"skin bearing 315"` still anchors.

  Related: `BL-14` (`body-layer/ROADMAP/BL-14.md`) ships `engage` only and records this gap;
  `plans/attack-run/implementation.md` has the measurement in context;
  `.claude/agent-memory/implementer/feedback_new_verb_synonym_can_silently_widen_anchor_set.md` is
  the lesson from finding it.
