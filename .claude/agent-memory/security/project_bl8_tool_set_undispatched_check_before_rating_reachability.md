---
name: bl8-tool-set-undispatched-check-before-rating-reachability
description: before rating a TOOL_SET tool's risk, grep whether anything actually dispatches ToolSpec.fn -- it may be registered but unreachable
metadata:
  type: project
---

`belief.tool_api.TOOL_SET` (BL-5's registry) is, as of BL-8 (2026-10-17), still a "name ->
description -> callable" registry that **nothing in the repo calls generically**. Confirmed by
grep: `grep -rn "tool_api\|TOOL_SET" brain-layer/ body-layer/src/logger.py body-layer/src/belief/
brain_client.py body-layer/src/belief/brain_reply.py` returns nothing. The live brain seam today
is `belief/escalation.py`'s structured-reply path (`pick`/`confirm`/`unable`/`ask`), validated by
`brain_reply.validate_brain_reply` — a different, already-built mechanism with its own validation
discipline that `TOOL_SET` entries do not share.

**Why this matters for a security pass specifically**: BL-8 added `remember_location`, a
brain-facing tool with a fully unbounded `label: str | None` parameter and no validation anywhere
between the tool call and the JSONL write. Read in isolation that looks like a live gap worth a
required fix. It is not live — there is no dispatcher, so no exploit path exists yet. The correct
verdict was "filed as a backlog item for whoever builds the dispatcher" (`BL-B79`), not a required
fix, matching the `BL-B35` fix-when-reachable precedent.

**How to apply next time**: before rating any `ToolSpec.fn`'s risk (missing bounds, missing
auth, anything), grep for an actual caller the way above — do not assume registration in
`TOOL_SET` means the brain can currently invoke it. The implementer's own agent-memory note
(`.claude/agent-memory/implementer/project_tool_set_has_no_dispatcher_yet.md`) says the same thing
from the signature-design angle; this is the security-reachability angle on the identical fact.
When a dispatcher eventually reads `TOOL_SET` generically, every tool registered there (not just
`remember_location`) becomes newly reachable in one commit — that commit is the one that should
trigger a focused look at argument validation across the whole registry, not a per-tool
afterthought.

See also [[bl8-mission-memory-security-review]] (`plans/bl8-mission-memory/security-review.md`).
