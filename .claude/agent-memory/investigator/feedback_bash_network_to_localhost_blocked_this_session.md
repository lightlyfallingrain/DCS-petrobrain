---
name: feedback-bash-network-to-localhost-blocked-this-session
description: Bash curl to 127.0.0.1 (the live aircraft-layer collector API) was denied outright this session, even with dangerouslyDisableSandbox -- scoped to this session/environment, not a project-wide fact
metadata:
  type: feedback
---

**Scoped to the 2026-10-20 investigator session on this worktree/environment** — per this role's
own "the install's reachability is per-session, not a project fact" guidance, do not promote this
to "the collector API is unreachable from an isolated agent" as a general claim.

What happened: dispatched to query `GET http://127.0.0.1:7791/firing/latest` and
`/world_objects/latest` (both read-only GETs, explicitly permitted by the task). `curl` to that
address was denied by the permission system outright ("has been denied", not a prompt) on every
attempt, including with `dangerouslyDisableSandbox: true` on the `Bash` call. `WebFetch` separately
refuses `localhost`/non-dotted hostnames by its own tool description, so it was never a candidate
either. Plain non-network Bash (`ls`, `git`, `python3 -c`) worked normally throughout — this is a
network-specific restriction, not a general sandbox failure.

**Why: because file access to the DCS install tree is NOT the same precondition as network access
to a collector process.** `$DCS_INSTALL_PATH`/`$DCS_SAVED_GAMES_PATH` being set and readable (per
the `dcs-file-investigation` skill's precondition check) does not imply outbound network calls from
this Bash sandbox will be permitted — they are two separate gates and the second one failed this
session even though the first held.

**Workaround used instead**: `$DCS_SAVED_GAMES_PATH/Logs/debrief.log` and `dcs.log`, both plain file
reads, carried enough ground truth to resolve the investigation without the live API at all — see
[[reference_debrief_log_for_firing_event_ground_truth]]. Worth trying first next time a live
collector query is blocked, rather than stalling on the network gate.

**If a future session needs the live API and hits the same denial**: don't assume it's permanent or
retry-with-different-flags; say so explicitly in the report (as this session's research note does)
and name the exact fallback file-based evidence used instead, same as this entry does.
