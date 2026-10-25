---
name: sibling-grammar-untouched-by-a-routing-fix-may-be-intended
description: Before flagging that a fix only patched one of two grammars checked on the same text (e.g. parse_utterance vs _match_radio_check_or_greeting in body-layer's handle_line), re-read the upstream routing decision -- it may already have decided the untouched grammar should keep failing this input.
metadata:
  type: feedback
---

On `BL-B100` (`body-layer/src/belief/utterance.py`'s `_VOCATIVE_PREFIX`), I nearly filed a required
fix for a sibling gap: `crew_console.handle_line` checks `_match_radio_check_or_greeting` on the raw
(vocative-prefixed) text *before* falling through to `_handle_utterance`/`parse_utterance`, which is
the only one of the two grammars `BL-B100` patched. A wake-prefixed `"Petrovich, radio check"`
therefore still escalates to the brain instead of being recognised as `radio_check`.

That is not a bug, it is AA-B7's own explicit, already-reviewed design: *"'[hey, ]Petrovich' at
start is intentionally the keyword that means free text for the brain"* (user, 2026-10-25,
`AA-B7.md`). Any wake-prefixed utterance, including one that would otherwise match a zero-slot
command, is *meant* to reach the brain as free text — the previous review already traced
`_match_radio_check_or_greeting` as part of AA-B7's routing chain and approved it staying
unreachable for that input.

**Why: a routing decision ("send X here") and a destination grammar's own ability to parse X are
two different claims, and a fix to the second can legitimately leave some inputs still escalating
by design** — not every "this sibling path wasn't touched" is a missed parallel-treatment case
([[feedback_check_for_an_existing_general_mechanism_before_scoping_a_new_one]]-adjacent, but the
inverse: here the asymmetry *is* the intended behaviour, not an oversight).

**How to apply:** before writing "fix X should have also covered sibling grammar Y", check whether
an earlier, already-approved decision record (the originating ROADMAP entry, an explore/decided
block) already settled that Y should keep rejecting this class of input. If so, say explicitly that
you checked this and it is consistent with that decision — don't silently drop the thought, and
don't file it as required without first finding (or failing to find) that record. Verify any such
claim end-to-end (ran `CrewConsole.handle_transcript` directly with the exact wake-prefixed line)
rather than trusting the trace alone — this is also where DoD's own
`feedback_trace_routing_fix_through_the_destinations_own_grammar` memory applies: a routing trace is
not the same claim as running the destination parser.
