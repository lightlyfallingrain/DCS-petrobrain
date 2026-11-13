---
name: br2-brain-tool-calls-design
description: BR-2 plan (2026-10-31) -- tool calls ride escalate/poll and run on body's poll thread (no tool server); wake-prefixed lines are acted on body-side today; handle_command resets mentions and one-shot signals, so brain dispatch has poll-order hazards
metadata:
  type: project
---

`plans/brain-tool-calls/plan.md` (BR-2) settled the brain's tool path. Four findings outlive it.

**1. No body tool server is needed.** Tool calls ride the existing `POST /escalate` / `GET
/replies/poll` seam as continuation rounds (same `utterance_id`, full `steps` resent, brain-layer
stateless), and body executes each tool inside `drain_brain` on the poll thread.
**Why:** `ContactStore` is mutated by the poll thread and is not thread-safe, so a server thread
would have to marshal onto the poll thread anyway; BR-1's "~a day for a tool server" note assumed
otherwise. **How to apply:** before proposing any cross-process callback into body state, check
which thread owns that state.

**2. "Petrovich, ..." was being answered by body, not the brain, whenever `parse_utterance` could
match after `[[BL-B100]]` stripped the vocative.** And body cannot tell a wake-prefixed voice line
from unanchored speech -- both arrive `verb_anchored=False`; the fuzzy wake match lives only in
audio-adapter. **How to apply:** routing by wake word needs an explicit `addressed` field on the
transcript wire, not inference.

**3. `handle_command` resets per-dispatch state on entry** (`_pending_mentions`,
`attack_run_transition`, `where_is_it_requested`/`_slots`, ...). A brain-dispatched command must plant
its `Mention` straight into `_referent_memory` before the call, and its one-shot signals can be
clobbered by a transcript dispatched later in the same poll (`drain_brain` ~4163 runs just before
`_poll_transcripts` ~4166, after the consumers at ~3799-4051). **How to apply:** any new caller of
`handle_command` from a drain must check poll-loop order against the signal consumers.

**4. `ToolSpec.fn` signatures are unfit for model calls** (leading server context, `GeoPosition`
params). Decided convention: `BrainTool.invoke(ctx, args)` adapters in `tool_api.py` (the one
`belief/` file allowed to import `mission_memory`), params as handles (`contact_ref`/`place_ref`/
`memory_ref`) that must have been *offered* this turn -- never coordinates.

Related: [[br1-brain-layer-design]], [[d10-structured-candidates]], [[two-speech-lanes-push-and-reply]],
[[reply-lane-never-defers-against-busy-until-sim]], [[crew-query-path-design]].
