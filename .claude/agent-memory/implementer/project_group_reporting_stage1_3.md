---
name: project_group_reporting_stage1_3
description: group-reporting Stages 1-3 -- name collision, Stage3 not audible, exact per-class counts
metadata:
  type: project
---

`plans/group-reporting/plan.md` Stages 1-3 (body-layer), 2026-09-28.

- **Plan named a new Stage 3 function `render_group_report`, colliding with an already-existing
  `belief.speech.render_group_report(facts_list)`** (the pre-existing speech-time, report-space
  aggregation `belief.callouts.group_candidates` already uses, which Stage 4 -- not this dispatch
  -- retires). Implemented the new one as `render_group_disclosure` instead. Check for name
  collisions against the actual module before trusting a plan's own function names verbatim,
  especially when the plan itself says the same name twice for two different things.
- **Plan's Implementation Plan section says Stage 3 "changes what the pilot hears," but also
  scopes `CalloutScheduler` integration to Stage 4 explicitly.** Those two claims are in tension --
  built Stage 3's renderer fully tested but wired into no live speech path, and flagged the
  tension explicitly in `implementation.md` rather than improvising a partial Stage 4 wiring (e.g.
  into `CrewConsole._handle_report`) to make the "audible" claim true. See [[feedback_dont_improvise_scope_to_satisfy_plan_framing]].
- **Group-level per-class member counts should be exact, never hedged like single-contact
  cardinality.** A group's composition is a real groupby over already-identified `Contact`s with
  stable identity -- not an estimate of how many real objects one unresolved percept/cluster
  stands for, which is what `_cardinality_phrase`'s hedging exists to protect against. Diverges
  from the plan's own illustrative worked-example table (which showed a bare "Tanks and trucks"
  with no numbers at 3km, numbers only at 1km) -- that table is illustrative, not a literal spec;
  the plan's actually-binding decisions (mixed-precision register, threat-leads, never pair exact
  count with vague class) are all still honored.
- Cohesion test design: single-link union-find over `Contact.position.x/.z`, threshold =
  `ratio * median(nearest-neighbour gap over ALL currently tracked contacts)` -- no separate
  "outer horizon" constant needed despite the plan's hedgy phrasing ("within some outer horizon");
  read it as "all currently tracked contacts," not a literal second radius to invent.
- Split/merge reconciliation: greedy assignment sorted by descending `|cluster ∩ old_group|`
  overlap count (not fraction) claims cluster-to-group pairs; unclaimed old groups are simply
  dropped (no event). This is the same pattern `plans/group-contact-model/plan.md` Stage 3 used
  for object-id clusters, reused as a *pattern* only since these members already have identity.
