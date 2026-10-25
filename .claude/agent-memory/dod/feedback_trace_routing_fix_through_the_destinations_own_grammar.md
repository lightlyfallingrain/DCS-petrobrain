---
name: trace-routing-fix-through-the-destinations-own-grammar
description: a routing fix verified by tracing the call chain can still fail once the string reaches the destination's own parser -- run the actual string through the destination, don't just trace the path
metadata:
  type: feedback
---

**When a fix changes where a string is sent, run the exact string through what the destination
does with it, not just the call chain that gets it there.** `[[AA-B7]]`'s Reviewer verified
`command_matcher.opens_with_wake_word` end to end by reading code: `verb_anchored=False` ->
`voice_commands.classify_response` -> `"fallthrough"` -> `crew_console._act_on_voice_decision` ->
`handle_line` -> brain escalation. Every link was real and correctly read. But nobody ran
`"Petrovich, where is mark one?"` through `belief.utterance.parse_utterance` itself — which is
start-anchored (`^where(?:'s| is| was)\s+...`) and rejects the still-attached wake-word prefix,
so the escalated transcript hits `NO_SUCH_COMMAND` instead of answering the question. Caught only
by running `parse_utterance(store, "Petrovich, where is mark one?", 0.0)` directly and comparing
against the unprefixed string — `[[BL-B100]]`, `plans/aa-b7-wake-word/`.

**Why:** a call-chain trace proves the string *arrives*; it does not prove the destination's own
pattern-matching still recognises it once something upstream (here: a routing fix) changed what
the string contains at the boundary. This is the same class of gap this role's brief already names
for F10 ("Cancel Task spoke a raw task id, which only a human hearing it reveals") — a defect no
fixture or code trace catches, only running the actual value through the actual consumer does.

**How to apply:** whenever a fix moves a string across a boundary it did not own before (a new
routing decision, a new escalation path, a newly-reachable fallthrough), find the destination's own
string-matching code and run the fix's own worked examples through it directly — not just its unit
tests in isolation, the literal strings named in the plan/roadmap entry. If the destination is
start-anchored, prefix-sensitive, or otherwise narrower than "any text," check it specifically.
