---
name: tool-set-has-no-dispatcher-yet
description: belief.tool_api.TOOL_SET's ToolSpec.fn signatures answer to no caller as of BL-8 -- checked by grep before assuming a generic-dispatch constraint
metadata:
  type: project
---

As of BL-8 Stage 5 (2026-10-17, `plans/bl8-mission-memory/plan.md`), `belief/tool_api.py`'s
`TOOL_SET` is still exactly what its own docstring calls it: "a `name -> description -> callable`
registry, deliberately transport-agnostic ... not a replacement for [an adapter]." Nothing in the
repo actually calls a `ToolSpec.fn` generically. Checked directly:
`grep -rn "tool_api\|TOOL_SET" brain-layer/ body-layer/src/logger.py body-layer/src/belief/
brain_client.py body-layer/src/belief/brain_reply.py` returns nothing — the brain seam that exists
today is `belief/escalation.py`'s `BrainClient`/structured replies, a different, already-built
mechanism, not a tool-call dispatcher reading `TOOL_SET`.

**Why this matters for the next addition.** `test_tool_api.py`'s own tests only check that each
`fn` is callable and each `name`/`description` is non-empty -- nothing exercises a call. So a new
tool's function signature is a free design choice today, not one constrained by an existing
dispatcher's calling convention. BL-8's `recall_memory`/`remember_location` took keyword-only
filter/mode arguments because that read best for their own callers, not because any dispatcher
required it.

**How to apply:** before assuming a `ToolSpec.fn`'s signature must match some existing calling
shape, grep for an actual caller the way above, rather than inferring one from `TOOL_SET`'s own
"frozen contract" framing (which is about the *name/description* surface being frozen, not the
`fn` signature). When brain-layer HTTP wiring eventually reads `TOOL_SET` generically, that will be
the first real constraint on these signatures -- flag it to whoever builds that wiring, since
`recall_memory`'s `center: GeoPosition | None` parameter and `remember_location`'s `anchor`
discriminator are both choices that assumed no such caller existed yet.
