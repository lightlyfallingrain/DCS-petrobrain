---
name: grep-fence-literal-text-not-runtime-access
description: a belief/ grep fence (mirroring test_belief_source_never_references_derived_world_position) checks literal source text, not runtime field access -- store the whole upstream object under a differently-named field to satisfy it, and use a word-boundary regex when the fenced name is a substring of other legitimate names
metadata:
  type: feedback
---

When a plan asks for a grep-style fence restricting which `belief/` files may
"mention" a field name (e.g. BL-14's `Percept.relative_direction`, fenced to
`percept.py` + `attack_run.py`), the fence is almost always implemented as a
literal-text search over each file's source (mirroring
`test_contacts.test_belief_source_never_references_derived_world_position`),
not a check of which code paths actually dereference the field at runtime.

Two consequences, both discovered while implementing `plans/attack-run/plan.md`
Stage 2:

1. **A non-exempted module (e.g. `contacts.py`) can still legitimately need to
   carry the forbidden field through, as long as it never writes the literal
   name.** The plan's Decision 16 claimed "`ContactStore` already keeps the
   latest percept per contact" -- it did not; `Contact` only ever pulled
   individual fields out of a `Percept`. The fix was `Contact.last_percept:
   Percept | None`, storing the *whole* object under a name (`last_percept`)
   that does not contain the fenced substring, rather than a dedicated
   per-field store. `contacts.py` never writes `relative_direction` anywhere
   in its own source; the one sanctioned consumer reaches the field via
   `contact.last_percept.relative_direction`.

2. **A naive substring check false-positives on legitimately similar names.**
   `relative_direction` is a substring of `body_relative_direction` and
   `alignment_direction`, both of which `contacts.py`/`geometry.py` already
   use. The fence test must use a word-boundary-aware regex
   (`\brelative_direction\b|\bRelativeDirection\b`), not `"relative_direction"
   in text` -- `_` is a word character in Python regex, so `\b` correctly
   does not fire inside `body_relative_direction`.

**How to apply:** when a plan specifies a grep fence on a field/type name,
before writing the storage mechanism, check whether any *other* legitimately
named thing in the codebase contains that name as a substring (search the
whole fenced directory). Write the fence test with a word-boundary regex from
the start rather than a bare substring check, and design any new field that
must carry the fenced value through a non-exempted module under a name that
does not contain the fenced substring.
