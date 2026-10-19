# BL-15 Stage 1 — user decisions on the plan's open questions

User answers, 2026-10-19, to `plan.md` "Decisions Requiring User Input".

1. **Live theatre has no built store.** *"wrong terrain model is as useless as not terrain model. Log
   missing model, have Petrovich say "system error, terrain model not found", after silence mode
   ends (intercom may not be on in early seconds of flight)."*
   - **Changes the plan's default**: do not keep the previous theatre's store. A store for the wrong
     theatre is dropped, not retained.

   **REVISED same day**, once told that running perception with no terrain store at all means
   rewiring the eyesight source (forest occlusion reads the store): *"Not worth the cost. On failure
   to load world model, log error. Have Petrovich respond to every player command with "system
   error, world model not loaded". On error loud refusal is better."* And, on holding the line until
   the intercom is on: *"I used the initial silence mode as proxy for intercom is working. Let's
   drop this. The above - say error message as response to everything - covers this."*

   So the degraded mode is **a loud refusal, not a reduced crew member**: no world model → log the
   error, no perception, and every player command answered with *"system error, world model not
   loaded"*. No queued one-off announcement.
2. **Process starts with a mission already running → no reset on first poll.** *"yes"*
3. **Nothing spoken at reset.** *"silence fine"*
4. **`silenced` mute survives a reset.** *"yes"*
5. **Log files: a new set per mission**, not a marker line. *"per mission"*

Security's risk item (a forged mission-start datagram can wipe belief mid-flight; loopback-only,
self-healing): **ACCEPTED** — *"Accept the risk, it's not like there's anything else sending DCS or
Petrobrain signals on my computer."*
