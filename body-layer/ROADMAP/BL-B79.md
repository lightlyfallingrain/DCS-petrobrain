# BL-B79 — `remember_location`'s `label` needs a bound before any dispatcher calls it

- [ ] **BL-B79 — `mission_memory.tools.remember_location`'s `label: str | None` parameter (the
  brain-facing `TOOL_SET` tool, `plans/bl8-mission-memory/plan.md` Decision 5) has no length cap,
  no character filtering, and no provenance marking. Bound it, and consider flagging a
  model-authored memory entry as such on read-back, before any code dispatches a `ToolSpec.fn`
  generically.** #status/open

  Found during BL-8's security deep analysis (`plans/bl8-mission-memory/security-review.md`),
  immediately after the implementer's own agent-memory note
  (`.claude/agent-memory/implementer/project_tool_set_has_no_dispatcher_yet.md`) established that
  `belief.tool_api.TOOL_SET` is registered but **undispatched** — nothing in this repo calls a
  `ToolSpec.fn` generically yet (independently re-confirmed by grep:
  `grep -rn "tool_api\|TOOL_SET" brain-layer/ body-layer/src/logger.py body-layer/src/belief/
  brain_client.py body-layer/src/belief/brain_reply.py` returns nothing). That is why this is
  filed rather than a required fix: there is no live call path to exploit today.

  **The gap, for whoever builds that dispatcher.** `remember_location`'s `label` is the one
  genuinely free-form field anywhere in mission memory that the *brain* — not the pilot — fully
  controls: the pilot-voice path (`crew_console._handle_mark_here`/`_handle_mark_target`, via the
  `mark_here_fn`/`mark_target_fn` closures in `logger.py`) never supplies a label at all, since the
  fixed-vocabulary voice commands have nothing to carry open text yet (Decision 6). Once a
  dispatcher lets the brain call `remember_location(..., label=...)`, nothing between the tool call
  and the JSONL write bounds that string's length or content — contrast `belief/brain_reply.py`'s
  validation discipline for the structured-reply path (`pick`/`confirm`/`unable`), which this new
  surface does not share at all.

  **Two concrete risks, both activate only once the dispatcher exists:**

  1. **Unbounded growth.** A confused or looping model could call `remember_location` repeatedly
     with long labels; `MissionMemory`'s in-memory list and the JSONL sink both grow without limit
     (the mark-index counter itself is a plain Python `int` and cannot overflow, but disk/memory
     cost is real).
  2. **Self-referential context amplification.** A label written now is exactly what
     `recall_memory`/`get_contact_history`'s memory-chain fold hands back to the brain later as
     context, with no code-side check that it was ever true — a hallucination written to memory
     once can be re-presented as an established fact on a later turn. Not externally-triggerable
     prompt injection (the label's author and reader are the same brain process, and no
     DCS-originated or mission-author text has a path into `label` today — every other field is
     the bounded `OP_*`/cardinality vocabulary), but worth a stated bound and, ideally, a
     provenance tag distinguishing a brain-authored note from an observed one on read-back.

  Not fix-now: same shape as `[[BL-B35]]`'s unbounded `response.read()` — a real gap with no
  current exploit path, filed so it is a named requirement for the dispatcher's own plan rather
  than something discovered after it ships.
