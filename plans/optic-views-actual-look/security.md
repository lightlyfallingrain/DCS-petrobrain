## Security Deep Analysis: fix/optic-views-actual-look

### Address
HEAD was `fee96cdc` at dispatch (a mismatch against the stated tip `332f4a9c`). It was a strict
ancestor of `332f4a9c4c6462b30a19dceb4cccc4a26b60e120` with a clean tree, so `git merge --ff-only
332f4a9c` was performed; HEAD is now `332f4a9c4c6462b30a19dceb4cccc4a26b60e120`.

### Dependency Status
No dependency change. No new imports in the diff.

### Scope of the change
`body-layer/src/body.py`: a new private helper `_resolve_active_gaze(runner)` consolidates three
previously-independent (and two of them buggy) readers of "where is Petrovich actually looking" —
`_render_eyesight_frame`, `_render_pov_frame`, and `_speech_log_sink` — onto one resolution. All
three are local, in-process read paths over the runner's own already-computed simulation state
(`SightHead.world_az_true_deg/world_el_deg`, `OpticState.actual_aim_*`, `runner.scan_plan`) feeding
a console debug view and a `.jsonl` log line. No network, no file I/O beyond the existing log
writer, no deserialization, no new external input.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body.py`, `_resolve_active_gaze`, sight-tier branch | 4 `assert`s on `SightHead`/`OpticState`/`last_ownship_state` fields being non-`None` | Pre-existing pattern, carried over verbatim from the deleted code in `_render_pov_frame` (the diff shows this is a move, not new logic) and documented as unreachable in practice because `run_once`'s optic-decision gate guarantees `sight_head.mode == "free"` whenever `runner.optic` is a sight optic. All inputs are internal simulation state computed earlier in the same poll — not attacker- or network-controlled, so even a hypothetical violation is a local crash of a debug console loop, not an exploitable condition. Consistent with this project's existing accepted pattern for this exact code (see `plans/pov-view/plan.md`). | None — false positive, no change in risk posture from before this fix |
| `_speech_log_sink` | writes `gaze_label`/`gaze_center_deg` derived from `_resolve_active_gaze` into the belief-truth/speech `.jsonl` log | Only the *value* changes (can now be an optic name instead of an o'clock label); field names, schema, and the log writer are unchanged. No new write path, no new file opened, no attacker-influenced content — `gaze_label` is one of a small fixed set of optic names, never free text sourced from outside the process. | None |
| `_render_eyesight_frame` / `_render_pov_frame` | console-only debug rendering | No change to what is read from DCS/the Hook; same inputs as before, now routed through a shared function instead of two independent (one of them broken) derivations. | None |

### LAN / attack-surface check
This change touches no listening socket, no HTTP endpoint, no IPC boundary, and no code path
reachable by a port scanner or another LAN host. It is pure in-process Python computing a display
value from the runner's own prior state and writing it to a local debug console and a local log
file. No prompt-injection surface (no LLM reads these values) and no new secrets.

### Verdict
APPROVED

### Findings filed
No findings. Nothing in this diff rises to even a low-risk item under the Risk Communication
Format — it is a display/logging correctness fix with no new attack surface, no new dependency,
and no change to any network- or filesystem-reachable boundary. Not filed, intentionally: there is
nothing here that a backlog ID would track.
