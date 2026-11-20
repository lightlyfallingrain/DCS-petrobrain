---
name: self-fork-blocks-further-forking
description: Calling Agent with subagent_type "fork" turns the current run itself into that fork inline (no separate async worker) and permanently disables any later fork call in the same run -- plan fork usage accordingly.
metadata:
  type: feedback
---

Dispatching `Agent({subagent_type: "fork", ...})` does not spin up a separate asynchronous
worker the way a plain subagent does. The tool result says "Fork started — that fork is you,"
and the very next turn's execution *is* the fork, continuing inline in the same conversation
with the directive injected as a `<fork-boilerplate>`-wrapped user turn. Once that has happened,
every subsequent `Agent({subagent_type: "fork", ...})` call in the same run fails immediately
with `"Fork is not available inside a forked worker."` — there is no way to fork a second time
after the first self-fork lands.

**Why:** discovered mid-review (BL-16 sortie-1120 batch, 2026-11-20) when three `Agent` fork
calls were sent in one message (Lua review / Python review / full-suite run). The first
succeeded and silently became "me" for the rest of the turn; the second and third both errored
with the message above, because by the time they were evaluated the run was already a forked
worker.

**How to apply:** don't batch multiple `subagent_type: "fork"` calls in one message expecting
them to run as independent parallel workers — only the first one actually "forks" (and does so
by becoming the current execution, not a separate process); the rest cannot run as forks at all.
If genuinely independent parallel investigation is needed, use `subagent_type: "general-purpose"`
(or another non-fork agent type) for every call after the first, or don't call fork more than
once per run. A non-fork `Agent` call still works fine after a self-fork has happened — only
further *fork* calls are blocked.
