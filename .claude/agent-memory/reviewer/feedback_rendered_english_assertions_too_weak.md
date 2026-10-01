---
name: feedback-rendered-english-assertions-too-weak
description: a test's assertion checking "doesn't look like branch X or Y" instead of the actual rendered string misses real grammar/nonsense defects
metadata:
  type: feedback
---

On `fix/group-undermerging` (`plans/group-cohesion-redesign/`), `belief/speech.py`'s
`_group_composition_clause` hard-codes the indefinite article `"a"` for every count==1 phrase
(`f"a {_unit_type_display(value, level)}"`). Two of the vocabulary's class words are vowel-initial
("armor", "infantry"), so this produces "a armor"/"a infantry" — confirmed live in the implementer's
own pinned test (`assert speech.text == "A armor, in the group."`). Only one hard-coded article site
in the whole module; easy to miss by reading since most class words are consonant-initial.

A second, more structural defect in the same review: the "first differentiation → full disclosure"
taxonomy branch renders a mixed differentiated/undifferentiated group as `"A ground and a truck."`
(`_unit_type_display(None, "presence")` returns `"ground"`, then gets its own counted noun phrase) —
directly contradicting the plan's own worked example for that exact branch (`"AAA in the group"`).
This is pre-existing code (unchanged in substance, just moved into a new helper), but the plan cites
this scenario by name as proof the branch is correct, so it's squarely in scope. **Caught only by
actually running the rendered string**, not by reading: the implementer's own test for this branch
(`test_render_group_disclosure_first_differentiation_is_full_once`) asserts only
`"in" not in speech.text or "o'clock group" not in speech.text` and
`not speech.text.startswith("Now leading")` — negative checks ruling out *other* branches' shapes,
never a positive check of what this branch actually says.

**Why:** a test that asserts "this isn't shaped like the wrong branch" instead of "this is the right
text" can pass forever while the actual content is nonsense English. This is the same family as
[[feedback_boundary_only_tested_via_fixture]] and the terrain-side tie-break fixture blind spot
(see [[m5-stage3-probe-chunking-review]] lineage) — a test shape that structurally cannot catch the
defect it exists to guard against.

**How to apply:** whenever a plan gives worked *utterance* examples (not just rule descriptions) as
the spec, grep the diff's own new tests for exact-string assertions against those examples. A test
that checks shape/membership of the string (`"X" not in text`, `startswith`) rather than equality
against (or a clear derivation from) a worked example is a signal to actually run the code and read
the output as English, not trust the assertion passing. Build a tiny throwaway repro script (Write +
`.venv/bin/python`, delete after) rather than reasoning about string concatenation by eye — this is
how both defects above were actually confirmed, not guessed.
