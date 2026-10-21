---
name: project_bl_b66_9k113_effectors_deep_analysis
description: BL-B66 (9K113 effectors) Stages 1-4+4b deep security analysis — APPROVED; cockpit_switch's missing allow-list is a recorded user override, not reopened; filed AC-B11 for the unbounded-Content-Length pattern it extends
metadata:
  type: project
---

`plans/9k113-effectors/security-review.md`, tip `da1812f62de4a28ed016d52f1b37bbd5fe11cda7`.
**APPROVED**, no required fixes.

**Why this one is worth remembering beyond the verdict**: it's the first deep-analysis pass run
under the revised, narrowed Security scope (root `CLAUDE.md`/`.claude/agents/security.md`, merged
2026-10-21 — computer/network security only, player-experience correctness is Reviewer's). The
plan review (Mode 1) had correctly REJECTED this plan's `cockpit_switch` op for missing an
allow-list — a genuine departure from `aircraft-layer/CLAUDE.md`'s standing "no general-purpose
remote-exec surface" invariant — and the user then explicitly overrode that rejection: *"Allow any
cockpit switch... This is LAN only and switch behaviour is limited to DCS."* That override is
recorded in `aircraft-layer/CLAUDE.md`'s "What this is" section and in
[[project_cockpit_write_vocabulary_invariant]]. **Do not re-raise the missing allow-list as a
finding on this or any future `cockpit_switch`-touching entry** — it is settled, not overlooked.

**What this pass actually verified (not just read the plan's account of)**: `GetDevice(device):
performClickableAction(cmd, value)` is a cockpit-control write, never code execution — grepped the
whole diff for `eval|exec(|loadstring|dostring|subprocess|os.system|pickle|yaml.load|__import__`,
zero hits. The command socket is still loopback-only (`COMMAND_HOST = "127.0.0.1"`, confirmed by
reading the two lines directly, not trusting the plan review). `handle_cockpit_switch_command`'s
`GetDevice` call is wrapped in `safe_call` (`pcall`), so a bad `device` id cannot crash the
per-frame export loop — the "crash kills a poll loop" scope item this role now watches for.

**One finding, filed rather than left in prose**: every `POST` handler on
`aircraft-layer/src/api/server.py`'s `TelemetryAPIServer` (five now, including this entry's new
`/command/cockpit_switch`) reads `Content-Length` with no upper bound before `rfile.read` — a
genuine "what a LAN port scanner reaches" item, low/low on this project's single-user/LAN-only
threat model, pre-existing shape this entry's new handler extends rather than invents. Filed as
**`AC-B11`** (`aircraft-layer/ROADMAP/AC-B11.md`) rather than left as a prose risk-matrix nobody
schedules — this role's own closing-step rule, after `BR-B3` sat unfiled for three weeks the one
time it wasn't.

See also [[project_cockpit_write_vocabulary_invariant]] for the plan-review side of this same
entry's story, and [[project_aa6_piper_http_server_default_bind_download_endpoint]]/
[[project_brain_layer_wide_bind_no_benefit]] for the general "check what a server actually binds
and accepts, not just what this project's call site needs" pattern this pass reused.
