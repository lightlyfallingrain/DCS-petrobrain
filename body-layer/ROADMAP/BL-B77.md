# BL-B77 — One hedge, two registers: the group line's hardcoded `"A couple of contacts."`

- [ ] **BL-B77 — `render_group_disclosure`'s undifferentiated-pair branch speaks a hardcoded
  `"A couple of contacts."` while `_cardinality_phrase` — the shared hedge register every other
  caller uses — returns the bare stems `"couple"`/`"handful"`/`"several"`/`"many"`. Unify: the group
  line reads the register, for both the logic and the words.** #status/open User direction,
  2026-10-16: *"group line has a hardcoded 'A couple of contacts.' -> unify, use hedge logic and
  words there too. Fix this first."*

  **Why it is a prerequisite rather than a cleanup**, and why the user put it first: the
  `[[X-T4]]` contacts callout (`plans/contacts-callout/plan.md`) reuses `_cardinality_phrase`
  verbatim by his own direction (*"use the existing hedge vocabulary"*). Shipping that while this
  literal stands would put **three** phrasings of one hedge in the cockpit — the register's
  `"couple contacts"`, the group line's `"A couple of contacts"`, and whichever of the two a reader
  of the code assumed. The contacts plan originally proposed filing this as a follow-up; that
  recommendation was overruled in the same message that answered its two open decisions.

  ## What is actually wrong

  | site | what it speaks |
  |---|---|
  | `_cardinality_phrase` (`speech.py:1686`) | `"couple"` (2–3), `"handful"` (4–5), `"several"` (plural default), `"many"` (16+) — bare stems, by the 2026-09-23 articles direction |
  | its own docstring | describes the register as `"a couple of"` / `"a handful of"` — the pre-brevity wording, never updated |
  | `render_group_disclosure`'s bare-word branch | the literal `"A couple of contacts."`, asserted by `body-layer/tests/test_speech.py:2642` |

  So the inconsistency is **three-way**, not two-way: the function, its documentation of itself, and
  the one caller that bypasses it. The docstring half is what let it survive — a reader checking the
  register against the group line finds them agreeing, because the docstring agrees with the literal
  and not with the code it documents.

  **The brevity direction this is measured against** (user, 2026-09-23, quoted in `speech.py`'s own
  module docstring): *"English articles carry no information in a report and cost speaking time …
  `"a couple of contacts"` becomes `"couple contacts"`."* The literal is the exact phrase that
  direction names, left unconverted.

  ## Scope, deliberately narrow

  - `render_group_disclosure`'s bare-word branch calls `_cardinality_phrase` and composes its stem,
    rather than carrying its own string.
  - The `"Group."` branch beside it is **in scope for inspection, not necessarily for change** — it
    is a bare word with no hedge at all, which may be correct (a group Petrovich believes in is one
    thing, not a count). Decide it explicitly rather than by omission.
  - `_cardinality_phrase`'s **docstring** is corrected to the words the function returns. No
    behaviour change there, and the function itself must not move — user direction for `[[X-T4]]`
    was *"use the existing hedge vocabulary"*.
  - `test_speech.py:2642`'s expectation changes with the behaviour. **The changed line is the
    deliverable, so the test must be read as a specification rather than updated to match output** —
    this project's own recurring defect shape is a test edited until it passes.

  ## What a flight has to confirm

  Nothing new is computed, so there is no new belief to be wrong about. What changes is one spoken
  phrase, which means the acceptance question is purely *does it still read as a crew member
  speaking* — rideable on any sortie that produces a two-member undifferentiated group, alongside
  `[[X-T4]]`'s own acceptance rather than needing its own.

  Related: `[[X-T4]]` (the callout that made this load-bearing), `[[BL-W39]]`
  (`collapse(group, depth)`, which the composition clause already reads).
