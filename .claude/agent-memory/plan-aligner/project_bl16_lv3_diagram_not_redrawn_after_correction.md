---
name: bl16-lv3-diagram-not-redrawn-after-correction
description: BL-16 LV-3 amendment — a diagram-review correction ("not never bank"; pedal band gated to commanded heading changes only) was carried into the plan's prose (sections C, E) but the mermaid diagram the user actually reviewed and corrected was never redrawn to match; a Risks entry "fixed" by the same correction's blanket find/replace became nonsensical instead of rewritten.
metadata:
  type: project
---

LV-3 amendment (`plans/flight-lift-vector/plan.md`, "LV-3 amendment (2026-11-27)"): the user
reviewed the Design Overview diagrams and sent two corrections (`explore-notes.md` "LV-3 diagram
review corrections", 2026-11-28) — bank is not "never" in hover (crosswind, sideways translate
still use it; only turning-to-heading uses pedal), and the ±0.3 hover pedal band applies only
during a commanded heading change, any pedal setting is allowed while just holding heading. The
correction note says "carried into `plan.md` LV-3 sections C and E" and both sections were
correctly updated with inline "Corrected 2026-11-28" boxes.

But diagram 2 — the exact `stateDiagram-v2` the user was looking at when they sent the correction —
was never touched. Its hover regime note still reads verbatim `pedal owns heading (yaw-rate loop),
never bank` and, unconditioned, `pedal within +-0.3 of the learnt hover pedal`. Both are precisely
what the correction overturned. A reader who trusts the diagram (the whole point of the
diagram-review step in `AGENTS.md`/"Diagram review after Architect") carries the wrong rule forward
even though the prose below it is correct.

Same pass, a second instance of a near-identical shape: the U13 answer (full pedal range, removing
the old +0.5 cap) carries a blanket instruction — "where the plan above says... '+0.5', read full
range" — which textually covers the Risks & Unknowns entry about a hover pedal need exceeding the
+0.5 clamp. But substituting "full range" for "+0.5" turns that sentence into a tautology ("if
hover needs more than the full range, it cannot hold heading") and destroys the risk's actual
content (the artificial half-travel cap, not the physical travel limit). A blanket substitution
instruction can textually apply and still produce nonsense; it is not a substitute for rereading
the sentence after applying it.

**Why:** a scoped correction reliably reaches text the correction note names (sections C, E) or
text literally containing the flagged phrase (the find/replace on "+0.5"), but not diagrams or
summaries that assert the same idea in different words, and a literal substitution does not check
whether the resulting sentence still means something.

**How to apply:** when a plan carries a same-day correction from diagram review, grep the whole
amendment for every diagram node/note using the corrected concept, not just the named prose
sections — diagrams are exactly the artifact the user looked at, so they are the most likely place
to still show the pre-correction reading. When a correction instructs a blanket text substitution
("wherever it says X, read Y"), re-read each hit after the substitution for sense, not just for
coverage — a hit that becomes vacuous or self-contradicting needs a rewrite, not a word swap. Same
family as [[project_bl16_lv1_amendment_rpm_correction_not_backpropagated]] and
[[project_lift_vector_u8_floor_removed_but_not_grepped_everywhere]] — this project's plan.md keeps
producing same-day correction boxes that don't reach every assertion of the old reading; the
diagram case is the one none of the prior two caught, since prior passes only grepped prose.
