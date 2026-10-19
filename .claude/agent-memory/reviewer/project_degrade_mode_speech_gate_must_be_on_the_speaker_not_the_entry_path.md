---
name: project_degrade_mode_speech_gate_must_be_on_the_speaker_not_the_entry_path
description: BL-15 Stage 3 loud-refusal mode gated the three command-dispatch entry points but not the proactive speech paths (drain_events/drain_brain); correctness today is incidental, not structural.
metadata:
  type: project
---

`plans/bl15-mission-start/` Stage 3 added `CrewConsole.refused` (loud-refusal
mode: every player command answered "system error, world model not loaded"
while the live mission's theatre can't be resolved to a loaded store). The
gate was added at the top of the three command-dispatch entry points
(`handle_command`/`handle_line`/`handle_transcript`) via a shared
`_refusal_response` helper — correct, and mutation-confirmed load-bearing.

**But `drain_events` (lifecycle-event callouts) and `drain_brain`
(asynchronous brain-layer replies) have no such gate at all**, and both run
unconditionally every poll regardless of `refused`. Today this is safe only
because `_enter_refusal_mode` is reachable solely via `_maybe_switch_theatre`,
called solely from `_check_for_new_mission` *after* `_reset_mission_state`
has already emptied `ContactStore`/`TaskStore`/`_pending_escalations` — so by
the time refusal starts, there is nothing left for `drain_events`/`drain_brain`
to speak about, and `runner.sources = []` means nothing new is ever ingested
either. The invariant ("refusal is only ever entered immediately after a full
reset") is real but is enforced by nothing except the current call-graph
shape across two functions in one file — not asserted, not tested, and would
fail *silently* (no crash, no test red, just Petrovich quietly speaking about
contacts that no longer exist) if a future change ever reached refusal mode
by a different path.

**Lesson for degrade/refusal-mode reviews generally: find every way the
system can *speak*, not just every way it can be *commanded*, and ask whether
the degrade gate covers all of them structurally** — i.e. on the thing that
produces output (the speaking method itself), not merely on the entry points
a human operates. A gate placed only on command dispatch leaves any
autonomous/proactive output path (scheduled callouts, async reply drains,
background pushes) silently ungated, and whether that currently matters
depends on an invariant elsewhere in the call graph that nobody wrote down.
Trace that invariant explicitly before approving — don't stop at "I checked
the three entry points the brief named."

See `plans/bl15-mission-start/review.md`'s "Batch 2" section, item (a), for
the full trace and the recommended four-line fix (an explicit `if
self.refused: return []` at the top of both methods).
