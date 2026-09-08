I want you to create a reusable skill for auditing the integrity and internal coherence of this project's Claude Code operating environment.

The goal is to detect configuration drift and process degradation as the project and its agentic development system evolve.

The skill should inspect the Claude system as a whole rather than reviewing individual files independently. It should identify cases where different parts of the system have become inconsistent, stale, redundant, incomplete, or no longer reflect how the project actually works.

In particular, I want it to be capable of detecting things such as:

* contradictory instructions or workflow definitions across Claude configuration, agents, skills, hooks, project instructions, and other relevant files
* stale assumptions about project structure, components, paths, commands, tools, agents, or workflows
* project-specific assumptions that have accidentally leaked into mechanisms intended to be generic
* duplicated rules that have diverged or could become competing sources of truth
* mechanisms that no longer appear to serve a useful purpose
* gaps where the system's intended behaviour is not actually enforced or represented
* deterministic checks or automation that no longer cover the parts of the project they are supposed to cover
* accumulated agent memory that has become obsolete, contradictory, redundant, or has effectively been superseded by permanent rules, documentation, or automation
* recurring process problems that suggest a lesson should be promoted from memory into a rule, skill, hook, or other more reliable mechanism
* anything else that indicates the Claude development system is gradually becoming internally inconsistent as it evolves

The audit should distinguish definite integrity problems from possible improvements. It should not treat complexity itself as a defect, nor assume that more automation, more rules, or more agents are desirable.

For every significant finding, explain the evidence, why it matters, and what corrective action you recommend.

The result should be a concise system-integrity report that I can review and then decide what changes, if any, should be made.

This is primarily a diagnostic and advisory mechanism, not an autonomous rewriting mechanism. Do not silently redesign or modify the Claude system as part of the audit.

Design the skill itself in whatever way best achieves this outcome while fitting naturally into the existing Claude Code environment and conventions. Examine the current setup first so that the skill complements the mechanisms already present rather than duplicating them unnecessarily.

