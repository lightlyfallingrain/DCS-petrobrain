## Security Deep Analysis: guidance-ready-edge

### Base verification
HEAD at dispatch was `6dfece18` (`origin/main`), a strict ancestor of the expected tip
`dc93b5619915891584f67f5131fe615282e8b178`. Tree was clean. Fast-forwarded with
`git merge --ff-only dc93b5619915891584f67f5131fe615282e8b178` — confirmed, now at that tip.

### Dependency Status
No dependency change. No new import in any of the four touched files
(`body-layer/src/belief/crew_console.py`, `body-layer/src/belief/sight_effector.py`,
`body-layer/src/logger.py`, `body-layer/tests/test_logger.py`).

### Scope of the change
This is an in-process state-machine fix: `GuidanceUnitState.guidance_unit_ready_announced: bool`
(a one-shot latch) is replaced by `guidance_unit_ready_prev_observed: bool | None`, and
`CrewConsole.drain_guidance_unit_ready` now speaks "Guidance unit ready." exactly on an observed
off→on edge of the real 960 cockpit lamp, rather than on the first poll that ever reads it lit. The
call site in `logger.py` moved from inside `if is_sight_ready:` to run every poll unconditionally,
so the unlit state is tracked too.

No new input source is introduced. `ready_observed` was already derived from the same cockpit
switch readback (`refresh_cockpit_switch_readback` in `sight_effector.py`) before this change; the
fix only changes which transition of an already-trusted, already-bounded `bool | None` value
triggers a canned, hardcoded string being written to `CrewConsole.output`. There is no LLM
involved in this path (`_print` writes a literal string, not model-generated text), no file path
construction, no network I/O, no deserialization, and no new listening surface.

### Grep sweep (scoped to the four changed files)
`eval(`, `exec(`, `os.system`, `subprocess`, `pickle`, `yaml.load`, `socket.`, `bind(` — no hits in
any of the touched files.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/crew_console.py` `drain_guidance_unit_ready` | edge predicate on `bool \| None` | Pure boolean logic over an already-bounded value; no attacker-reachable input shapes this transition beyond what already existed (the lamp bit itself). | None |
| `body-layer/src/belief/sight_effector.py` `GuidanceUnitState` field rename | dataclass field rename, default `None` | `reset_for_new_mission` re-runs `__init__`, confirmed by Reviewer to reset this field correctly on mission restart — no stale-state carryover across missions. | None |
| `body-layer/src/logger.py` call-site move out of `if is_sight_ready:` | now runs every poll | Expands the call frequency of an in-process method, not the attack surface — no new external trigger, no new exception path observed (reviewed; Reviewer's mutation test exercised this). | None |

### LAN/port-scanner and prompt-injection relevance
Not applicable. This change touches no socket, no HTTP endpoint, and no text that an LLM reads —
the spoken string is a hardcoded literal (`self._print(["Guidance unit ready."], now_sim)`),
unconditionally the same text regardless of any external data. There is no path by which a
LAN-local attacker or a malicious dependency could influence this code's behavior beyond what was
already true of the cockpit-switch readback it depends on (unchanged by this fix).

### Verdict
APPROVED

### Required Fixes
None.

### Passed to Reviewer
None — Reviewer already approved this change (`plans/guidance-ready-edge/review.md`), and nothing
observed here is a player-experience/correctness concern beyond what Reviewer's own mutation
testing already covered.

### Findings filed
No findings were produced that need a backlog ID — this deep analysis found no exploitable
vulnerability, no probable risk, and no low-risk finding requiring a risk-matrix decision. Nothing
to file.
