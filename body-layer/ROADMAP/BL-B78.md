# BL-B78 — `speech.py`'s module docstring still documents the pre-brevity hedge register

- [ ] **BL-B78 — The "Stage 4b — the count clause" section of `body-layer/src/belief/speech.py`'s
  module docstring describes `_cardinality_phrase` as returning phrases *with* an article and
  connector — *"a handful of trucks"*, *"a couple of armor"*, and literally **"`_cardinality_phrase`
  returns `'a handful of'`"** — plus a paragraph headed *"The phrase carries its own connector"*.
  The function returns bare stems and has since the 2026-09-23 brevity conversion. Documentation
  only; no behaviour.** #status/open

  Found by the Reviewer during `[[BL-B77]]` (`plans/contacts-callout/review-bl-b77.md`), raised
  explicitly as optional and out of that item's stated scope, and filed rather than folded in so
  the approved change stayed the reviewed change.

  **It is the same defect `[[BL-B77]]` existed to cure, still live a few hundred lines above it.**
  That item's own finding was that a *docstring* agreeing with a stale literal is what let one
  hedge be spoken two ways through several reviews: a reader checking the register against its
  caller found them consistent, because both were wrong together. `BL-B77` corrected the function's
  own docstring. This paragraph is the module-level copy of the same claim, and it is now the
  remaining place in the tree where a reader can be told the register carries connectors.

  **The one sentence that is actively misleading** is the connector claim, because it reads as a
  *design rule* rather than a description: it says `"several"`/`"many"` take a bare noun while
  `"a handful"` requires `"of"`, which would tell a future caller to expect per-phrase grammar that
  no longer exists. A caller composing against that sentence would produce `"a handful of
  contacts"` — reintroducing exactly what `BL-B77` removed.

  **What must not be touched while fixing it.** The surrounding prose carries two live user
  directions that are still correct and are not about the register's spelling:

  - *"Petrovich is Russian, we don't expect perfect grammar. Value/effort is low on fine tuning
    grammar beyond obvious mistakes."* (2026-09-19) — so `"couple armor"` (a mass noun taking a
    count word) and `"three T-72"` stay deliberately unpolished, and the worked examples that
    illustrate that stay too, with their wording brought to what is actually spoken.
  - The distinction the same paragraph draws between a line heard as an *accent* and a line heard
    as a *defect*. `"a handful trucks"` is cited there as the second kind — a missing word. That
    example predates the stems and needs re-grounding rather than deleting, since the lesson is the
    one worth keeping.

  Scope: prose in one docstring. No test, no constant, no spoken output changes. Rideable into any
  body-layer change that touches `speech.py` — `[[X-T4]]`'s contacts callout is the obvious one,
  since it reads this same register.
