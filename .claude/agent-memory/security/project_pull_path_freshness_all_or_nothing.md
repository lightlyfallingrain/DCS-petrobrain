---
name: pull-path-freshness-all-or-nothing
description: BL-13's summary hedges staleness only when EVERY in-scope contact is stale, and that hedge is the first thing the word budget drops — the mixed case is the steady state.
metadata:
  type: project
---

BL-13 (`plans/crew-query-path/`, Stages 1–3) is the first **pull** path. Decision D's presence-claim
argument holds — belief-only, `lost` dropped, `_callout_may_speak` correctly not applied. The gap
is the **freshness** half, and it is a gap in the plan's argument rather than an implementation slip.

**The mechanism, so it is recognisable elsewhere:** `speech.render_report_summary` prefixes
*"Last I saw, "* only when `all(_is_stale(...))`. In-scope contacts run to `LOST_THRESHOLD_S` =
120 s while `OBSERVED_WINDOW_S` = 16 s (one whole scan cycle), so **one** contact refreshed in the
current cycle strips the qualifier from the whole answer, two-minute-old SAM included. The only
partial hedge (`_summary_deferral_clause`) names one stale contact, says *"still checking"* (an
inspection in progress, not a memory), and is the **first** clause the 25-word budget drops —
demonstrated: a 1-fresh + 3-stale scene with two SAM tiers rendered at 22 words with no freshness
signal at all.

**Why this is the same error twice.** It is `[[rate_a_fallback_by_how_often_it_fires]]`'s rule
applied to a *qualifier* instead of a fallback: the all-stale condition was reasoned about as the
case of interest without asking how often the healthy, mixed state occurs. **Ask of any all-or-
nothing honesty marker: what fraction of normal operation falls in the partial case?** Here it is
most of it.

**How to check a renderer like this in future, in two commands:** run the shipped renderer on a
mixed-staleness scene and on a scene whose parts overflow the budget. Both took one `python -c`
against `body-layer/.venv` with `sys.path` set to `src` + `../world-model/src`. Do not reason about
it from the drop-order comment — the comment is accurate and the behaviour is still wrong.
