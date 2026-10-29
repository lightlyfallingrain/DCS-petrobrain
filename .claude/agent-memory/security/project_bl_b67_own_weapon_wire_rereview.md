---
name: bl-b67-own-weapon-wire-rereview
description: BL-B67 revised plan (S_EVENT_SHOT own-weapon segment on the firing-events wire) re-reviewed APPROVED with one non-blocking amendment -- bound the type field in the parser, not just the Hook
metadata:
  type: project
---

Re-review of `plans/bl-b67-atgm-run/plan.md` at `e523f2b3` (revised from `858625061c`, which
dropped the fire-button feed/`GET /fire_button/latest` for `S_EVENT_SHOT` + the weapon object over
the existing `petrobrain-firing-events-hook.lua` bridge).

**Verdict: APPROVED**, same as the prior review of the earlier design. The revision narrows the
attack surface (one fewer GET endpoint, one fewer per-frame cockpit push) rather than widening it.

**One real but non-blocking gap, not yet filed as a backlog ID** (the plan is Mode 1 — not yet
implemented, so there is no code location to anchor a backlog item to; flag for the Implementer
instead): `weapon:getTypeName()` is DCS-sourced free text crossing the Hook→collector wire as the
new `<type>` field (`OWN_SHOT:<t>:<seq>:<type>:<category>:<guidance>:<exists01>`). The plan states
a Hook-side 48-char truncation + `:;|` replacement, but names no parser-side bound in
`schema/firing.py`. This project's own existing pattern (`_parse_entry`'s treatment of
`initiator` — another DCS-sourced free-text field) is "the parser defends itself, does not trust
the sender." Recommended fix at Stage 5: `_parse_entry`'s own-weapon sibling independently caps
`<type>`'s length and rejects embedded `:`/`;`/`|`, instead of relying solely on the Hook-side
mitigation — matters because the plan's own "deployed-Hook version skew" risk means an old Hook
predating the cap could still send a four-segment payload with an unbounded/unsanitized type
string.

Not severity-raising on its own: UDP loopback-only, consumed only by a 3-valued enum lookup
(`family_of`) and a log line, never speech. Still worth insisting on at Implementer/Reviewer time
since it is a concrete, cheap fix against this project's own stated defense-in-depth posture.

See [[project_cockpit_write_vocabulary_invariant]] for the unrelated-but-adjacent effector-write
bound this plan reuses unchanged (no new write primitive).
