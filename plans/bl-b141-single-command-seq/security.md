## Security Deep Analysis: BL-B141 / BL-B117 / BL-16 M4 (batch on `fix/bl16-flight-epoch-bound`)

Video game add-on context: Petrobrain is a hobby add-on for the DCS World flight-simulation game;
the SAU channel writes and command-counter changes below are simulated cockpit systems, nothing
here controls real hardware.

Scope: two commits, reviewed and batched per the main loop's instruction —

1. `26bfa514` — BL-B141 single body-layer command counter (`_next_flight_seq` → `_next_command_seq`,
   widened to mint the wire `seq` for `ai_pilot_goal`'s set/`hvrt_step` and the CBTM one-shot, not
   just the `flight` channel); BL-B117 `ai_pilot_wheel.lua`'s `on_stop()` clearing
   `ai_pilot_parked_active` and six overlay text fields.
2. `03b67fcb` — BL-16 M4: new `controls_to_petrovich_edge`/`CONTROLS_TO_PETROVICH` trigger, three
   new curated SAU OFF-button effectors in `effectors.toml`, new `controls-to-petrovich.md`
   sequence, and a new optional `step-delay-s` sequence-file header param (parsed `float`,
   range-checked).

Threat model: single-user, LAN-only (root `CLAUDE.md`/role file). Realistic attackers are (1)
malicious code in a dependency and (2) an infected LAN machine port-scanning. Neither commit touches
a dependency, a listening socket, or anything reachable from the network beyond the pre-existing
aircraft-layer↔body-layer LAN HTTP seam.

### Dependency Status

No dependency change in either commit. Confirmed by diff stat — no `pyproject.toml`/`requirements`
touched in either commit.

### Prior-finding check (memory / graph)

- `.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md` and its
  siblings (`project_nan_infinity_int_conversion_at_lua_action_boundary.md`,
  `project_nan_infinity_comparison_not_just_int_conversion.md`) — the recurring NaN/Infinity-at-a-
  numeric-boundary class. Checked below against `step-delay-s`; not reachable from either command
  counter change (both are plain Python `int` increments with no parse step).
- `.claude/agent-memory/security/project_effector_sequence_config_files_are_local_not_a_wire_
  boundary.md` — `config/sequences/<aircraft-dir>/*.md` files (which `step-delay-s` lives in) are
  read once at startup, local-file-only, edited only by the user/developer; confirmed still true
  here — `load_sequences`'s only call site is still `body.py` process startup (grepped: one hit).
  No new call site made this directory reachable from the network, brain, or voice path.
- `plans/flight-lift-vector/security.md` (prior deep analysis on this same feature's earlier
  stages) and `[[BL-B135]]` — non-finite floats at wire boundaries; not implicated here since
  neither commit adds a wire-boundary numeric parse (the one new parse, `step-delay-s`, is local
  config, see below).
- `[[AC-B23]]` (rejected) — sender checks on `/command/*`; not re-raised, per user direction on
  file.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/effector_sequences.py:470-493` (`_parse_header`) | New numeric parse (`step-delay-s`) at a config-file boundary | `float(raw_step_delay)` is wrapped in `try/except ValueError`, and the parsed value is checked with `math.isfinite(...)` and `< 0` before acceptance — the exact guard this project's recurring NaN/Infinity class is usually missing. Boundary is local-file-only (not LAN/brain/voice), per the memory above, so this is the lighter "crash-safety" bar, not the LAN-boundary bar — and it already clears the LAN-boundary bar too. | None. Reviewer's `review-m4-sau.md` correctly notes the *test* coverage gap (no dedicated `nan`/`inf` test case) — that is a test-completeness finding, not a vulnerability; the code path is already correct. Not filed as a security backlog item (see "Not filed" below). |
| `body-layer/src/body.py` (`_next_command_seq`, both commits) | Counter widening — one `int` counter now shared across three wire channels instead of one | Plain `+= 1` on a Python `int` (arbitrary precision, no overflow), no parse of external input, no new network reachability. Strictly reduces risk vs. the prior per-channel counters (eliminates any chance of two different channels independently reusing the same `seq` value). | None. |
| `body-layer/src/belief/flight_authority.py` (`controls_to_petrovich_edge`) | New derived-state comparison (`prev.fd_mode != "m1" and new.fd_mode == "m1"`) | Pure function over already-validated internal enum-like string state (`fd_mode`), no external input parsed, no new boundary. | None. |
| `body-layer/config/sequences/mi-24p/effectors.toml` (3 new OFF-button effectors) + `controls-to-petrovich.md` | New curated switch writes, reachable only from the existing local-config/startup-loaded sequence mechanism | Same trust boundary as every other `effectors.toml`/`*.md` sequence entry — local file, loaded once at startup, not reachable from the network. Fires only from an internal `fd_mode` transition, not from any request body. | None (player-experience correctness of *which* switches/values is Reviewer's domain, not this pass's). |
| `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` (`on_stop()`, BL-B117) | New field resets on mission stop | Pure cleanup of in-module Lua globals on a DCS lifecycle hook (`LuaExportStop`), no new `net.dostring_in`, no new external input taken. | None. |
| Pattern sweep (type:ignore/noqa, eval/exec/loadstring/dofile, pickle/yaml.load, subprocess/os.system, net.dostring_in, open(...,"w"/"a")) over the five changed files | — | Zero hits in the changed lines. The one `except KeyboardInterrupt: pass` found by the sweep (`body.py:6812`) pre-exists this batch (not in either commit's diff) — not this feature's finding per the "pre-existing hit" rule. | None. |

### Verdict

**APPROVED**

### Required Fixes (if any)

None.

### Passed to Reviewer

None — no player-experience correctness findings surfaced in this batch beyond what
`review-m4-sau.md` already recorded (the `step-delay-s` nan/inf test-coverage gap, itself a
test-completeness note, not a behavioural defect).

### Closing step — finding disposition

One item surfaced that could be read as a backlog candidate and was deliberately **not filed**:

- **`step-delay-s` lacks a dedicated nan/inf test case** (noted first in `review-m4-sau.md`,
  confirmed here). Not filed as a security backlog item because the underlying code is already
  correct (`math.isfinite` + `< 0` guard verified by reading, not merely by trusting the comment) —
  this is a test-coverage gap on a local-config, non-wire boundary, squarely in ordinary
  code-quality/test-completeness territory the Reviewer/Implementer loop owns, not a security
  finding with a probability/impact matrix. If the user wants it tracked anyway, it is a one-line
  `BL-B` test-completeness backlog item, not a security one.

No other finding in this report lacks an ID or an explicit "not filed, intentionally" — the single
item above is the only one not accompanied by a verdict of "no action required."
