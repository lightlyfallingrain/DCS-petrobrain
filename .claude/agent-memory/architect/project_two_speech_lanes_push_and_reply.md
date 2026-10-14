---
name: two-speech-lanes-push-and-reply
description: body-layer already has two producers into CrewConsole._print — the push lane (CalloutScheduler.tick) and the immediate reply lane — so new spoken output picks a lane rather than needing a new mechanism; anything pilot-requested belongs on the reply lane and must only share busy_until_sim
metadata:
  type: project
---

**Established while planning `BL-14`'s advisory channel, 2026-10-14.** The question "does this new
spoken output go through `CalloutScheduler` or beside it?" has a standing answer, and the answer is
structural rather than a judgement call.

`CrewConsole._print` is the **single output funnel** (stdout, speech log, overlay, then
`speech_client.push_speech`). Two producers reach it:

| lane | path | arbitration |
|---|---|---|
| **push** (spontaneous) | `drain_events` → `CalloutScheduler.tick` | the full apparatus: one line per tick, `busy_until_sim`, `CALLOUT_MAX_AGE_S` 10 s, `WATCH_REPORT_MIN_GAP_S` 8 s, group-keeper suppression, signature dedup, the observability gate |
| **reply** (pilot-requested) | every `_handle_*` → `_print` directly | none; `note_reply` is called *afterwards* purely to charge occupancy |

**Why the lane matters more than it looks.** Every push-lane mechanism is tuned for *volume
reduction on spontaneous reports*, and several **drop** rather than defer. Routing requested output
through `tick` silently subjects it to all of them. `callouts.py`'s own module docstring already
forbids the merge in the other direction: *"This gate is for the push path only… do not 'complete'
this gate by wiring it to the pull path."*

**How to apply.** New spoken output that the pilot asked for — a reply, a report, a standing
commanded mode's guidance — goes on the reply lane, rendering straight through `belief.speech` into
`_print`. It does **not** need a new `Event` kind, a new exemption, or a new sink.

Three things that fall out, each of which saved real design work:

- **No-omniscience gating comes free on the reply lane**, because the observability gate lives only
  on the push path. `BL-14`'s *"losing sight does not interrupt the run and is not announced"* needed
  no mechanism at all. `_OBSERVABILITY_EXEMPT_KINDS` stays a one-member set.
- **The one thing a new lane must still respect is occupancy.** Read `scheduler.busy_until_sim`
  before speaking; `_print` then charges via `note_reply` (extend with `max`, never preempt).
  `note_urgent` *resets* instead, and only because `AudioPlaybackSender.interrupt` has genuinely
  destroyed what was in flight — do not copy it for anything that has not.
- **Ordering in the poll loop is the priority mechanism.** Calling a new drain *before*
  `drain_events` makes it win the tick, and the scheduler's candidates are **deferred, not
  dropped**, because the belief store is the backlog. That is cheaper and safer than adding a
  priority band to `callout_priority`.

**Also: `_print`'s audio sink is a synchronous HTTP POST per line on the poll thread**, so any
high-rate lane needs a change-driven (not timer-driven) emit rule or it starts blocking the 1 Hz
poll loop. The poll rate is 1 Hz, not 5 Hz — `logger.py` carries a test
(`test_no_stale_five_hertz_claims_remain_in_src`) guarding that exact confusion.

`silenced` gates `push_speech` only, applies even to `bypass_gate=True`, and is cleared by *any*
recognised command — so a mode started by a command cannot begin while muted, which usually
dissolves the "should this be exempt from silence" question before it has to be answered.
