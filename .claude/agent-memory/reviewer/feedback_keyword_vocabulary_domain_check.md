---
name: feedback_keyword_vocabulary_domain_check
description: How to review hand-authored DCS object_type keyword tables (association.py, object_model.py, and future ones) for real defects hiding behind "unvalidated vocabulary" plan licenses
metadata:
  type: feedback
---

When reviewing a hand-authored keyword-matching table against `object_type` (or similar DCS
identifier strings), don't stop at "the plan licenses this as an unvalidated starting
vocabulary, so thin coverage is acceptable." Separate two distinct risk classes that get
conflated under that license:

1. **Thin coverage** — the table just doesn't have many entries yet. Plan-licensed in this
   project (`association.py`'s `_type_match_score`, `object_model.py`'s `_KEYWORD_PROFILES` both
   carry this caveat explicitly). Not a required fix by itself; a backlog item with the real
   number recorded is enough.
2. **Domain mismatch** — a whole keyword category is built from a wrong assumption about what
   the underlying string actually looks like (e.g. `object_model.py`'s `OP_SHIP` keywords were
   English hull-class descriptors — "cruiser", "frigate" — but real DCS ship `object_type`
   values are hull/proper-noun model names like "Slava", "leander-gun-achilles"; the keywords
   were structurally unreachable against real data, not just sparse). This is a real bug, not an
   accepted unvalidated-vocabulary risk, and should be a required fix even when the plan already
   licensed "hand-authored, unvalidated" for the table as a whole.

**How this gets missed**: a hand-authored fixture test (`test_ship_keyword` asserting against
`"Grisha corvette"`, a fabricated string containing the keyword by construction) will pass even
when the real-world match rate for that category is 0% — the test validates the lookup function,
not that the keywords are shaped like real data. When reviewing this kind of table, check whether
at least one test uses a plausible *real* identifier string for each keyword category, not just a
string engineered to contain the keyword.

**Where DCS's own canonical type-name mapping lives**: `HelperAI_reporting_names.lua` (ED's own
DCS-type → reporting-name file, present in the DCS install) is a good verification source for
"does this keyword actually match real type strings" — cite it via whatever research doc
discusses it, not via the gitignored local sync path directly.

See [[project_body_layer_research_dir_convention]] for where to record this class of finding.
