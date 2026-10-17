# BR-2 — The brain cannot call a single tool: `TOOL_SET` has no dispatcher

- [ ] **BR-2 — Wire a real tool-call path from brain-layer to body-layer's `TOOL_SET`.** #status/open
  Filed 2026-10-17 at user direction (*"Create own milestone item of the tool set for brain"*), from
  the BL-8 batch's own findings. **This is a milestone in its own right, not a stage of anything** —
  it is the single thing standing between a growing, documented, tested query surface and a brain
  that can use any of it.

  **The finding, established twice independently during BL-8.** `body-layer/src/belief/tool_api.py`'s
  `TOOL_SET` is a `name -> description -> callable` registry, frozen as a contract since BL-6 and now
  17 entries wide. **Nothing in this repo dispatches one.** Grepped during BL-8's security pass and
  again by DoD, across `brain-layer/`, `body-layer/src/logger.py`, `belief/brain_client.py` and
  `belief/brain_reply.py`: no call site resolves a tool name to its callable and invokes it. So every
  tool in that registry is reachable only from body-layer's own tests.

  Two consequences, both recorded at the time:

  - **BL-8's whole recall surface is inert.** `recall_memory`, `remember_location` and the
    `get_contact_history` memory fold were built, reviewed and merged (2026-10-17, `01f5e3d9`), and
    the brain cannot reach one of them. DoD's milestone-completion answer named this as *the real
    next dependency* rather than any BL-8 stage.
  - **`ToolSpec.fn` signatures are still a free design choice** — the implementer's own memory note
    (`.claude/agent-memory/implementer/project_tool_set_has_no_dispatcher_yet.md`) records this as a
    constraint for whoever builds the dispatcher: nothing yet depends on their shape, so the shape is
    decidable now and expensive to change later.

  **One already-filed item is gated on this milestone, and the ordering matters.** `[[BL-B79]]`
  (2026-10-17 security pass): `remember_location`'s `label: str | None` has no length cap or
  validation between the tool call and the write, unlike `belief/brain_reply.py`'s validated
  structured-reply path. It was correctly rated fix-when-reachable *because* no dispatcher exists —
  so **building the dispatcher is what makes `BL-B79` live.** Close it in this milestone, not after.

  **What this milestone has to decide**, none of it settled:

  - The transport. BR-1 already established an HTTP seam between brain-layer and body-layer
    (`belief/brain_client.py`); whether tool calls ride that or get their own path is open.
  - `ToolSpec.fn`'s calling convention and how arguments arrive from a model — the D10 trust boundary
    (`belief/brain_reply.py`) is the established pattern for re-validating anything a model returns
    against body-owned data, and a tool *call* is the same class of thing as a model *reply*: it must
    not be able to name a contact id or a command body did not offer.
  - Which tools the brain may call at all. 17 entries is not obviously the right exposed set, and
    `remember_location` is the first **write** tool — the registry has until now been read-only from
    the brain's side.
  - Ollama serialises generation (BR-1.2's performance verdict, APPROVED — MONITOR), so a tool call
    inside a model turn has a latency cost that was never measured because nothing could make one.

  **Prerequisite reading**: `plans/brain-layer/plan.md` (BR-1's two stages and the D10 boundary),
  `body-layer/src/belief/tool_api.py`'s own docstring (which records the BL-6 freeze, BL-7's
  rejection of `get_mission_phase`, and BL-8's extension to 17 with the fold-versus-extend
  reasoning), and `plans/bl8-mission-memory/plan.md` Decision 5.
