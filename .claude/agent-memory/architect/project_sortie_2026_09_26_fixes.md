---
name: sortie-2026-09-26-fixes
description: Plan design for the crossing-callout/binocular/command-lowering sortie fixes — gate placement, defect scoping, and the Decision 2a sizing call
metadata:
  type: project
---

Plan: `plans/sortie-2026-09-26-fixes/plan.md`, on `fix/sortie-2026-09-26`. Binding spec:
`plans/sortie-2026-09-26-fixes/decisions.md` (Decisions 1-3, 2a — the user added Decisions 2a and 3
*mid-task*, after the initial brief; always re-read `decisions.md` before trusting an earlier read of
it on this branch).

**Fix A gate placement is load-bearing for Decision 3 (briefing-derived belief is pull-only).**
The observability gate went inside `ContactStore.tick`'s sixth block (the sole producer of
`CONTACT_RANGE_CROSSED`), not into `belief/speech.py::route_event`. Reason: `tick` only ever produces
*spontaneous* events; a future pull-only query answer ("where are the trucks?") would go through the
already-separate `describe_contact`/`render_contact_report` path, which never touches `Event`/
`route_event` at all. Gating the shared renderer instead would have required threading an
origin/reason flag through `Event` just to keep query answers un-suppressed — unnecessary complexity
for a feature not yet built. **If a future change makes queries route through `route_event`, revisit
this gate.**

**Fix C's cross-subproject seam turned out not to exist.** The task brief assumed disposition
classification (`act`/`confirm`/`say_again`/`fallthrough`) was computed in `audio-adapter`; code
reading showed it's computed in `belief.voice_commands.classify_response` (body-layer side) — 
`audio-adapter` only supplies raw match signals. The actual bug was narrower than expected too:
`handle_command` and the `say_again`/initial-`confirm` paths already correctly gate on
"understood" — the only real defect was `_handle_utterance` calling `_note_player_command()`
*before* checking `parse.disposition == "handled"`, so a `fallthrough` utterance the free-text parser
also failed to understand still burned the interrupt. **Lesson: when a task brief predicts an
expensive cross-subproject seam, trace the actual call graph before planning around the assumption —
it collapsed from "flag as a decision for the user" to a one-line move.**

**Decision 2a (sector coverage) sized out as a separate follow-on plan**, not folded into this
branch. The distinction that matters: eligibility (may he look again — Stages 2/3 here) vs. coverage
(whom does he look at next among several candidates — a `choose_look` selection-fairness redesign
with real starvation-bound and give-up-condition tradeoffs). Proposed name:
`plans/optic-sector-coverage/plan.md`, recommended for its own Explore-with-user pass given the open
lived-judgment questions (what "starve the rest of his behaviour" means, what a give-up condition
looks like).

**Two new placeholder timing constants**, same "documented, explicitly revisitable" style as
`belief/decay.py`'s existing half-lives: `CALLOUT_OBSERVABILITY_GRACE_S` (decay.py, proposed 10.0s)
and `OPTIC_RETRY_INTERVAL_S` (optic_policy.py, proposed `4 * SCAN_CYCLE_PERIOD_S` ≈ 64s). Neither is
tuned — both need a flown sortie's feedback.
