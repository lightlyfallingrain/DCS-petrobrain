---
name: verify-effector-registry-against-raw-dump
description: How to check a curated effectors.toml entry's device/cmd/arg and button-vs-toggle shape without a reachable DCS install
metadata:
  type: feedback
---

When a Reviewer task asks to check a curated `body-layer/config/sequences/<aircraft>/
effectors.toml` entry's correctness (device/cmd/arg, or whether a control is a pure ON button
with a separate OFF vs. a toggle) and `dcs-file-investigation`'s own precondition
(`DCS_INSTALL_PATH`/`DCS_SAVED_GAMES_PATH`) is unset in the reviewing worktree, don't treat that
as "cannot verify" — the generated raw dump is itself derived from the installed tree on a prior
occasion and carries enough to answer most of these questions:

1. `config/effectors-raw/<aircraft-dir>.toml` — grep the element name (e.g. `SAU-H-ON-PTR`).
   Each entry gives `device`/`cmds`/`cmd_names`/`args`/`values` (including `momentary: true/false`
   and `kind: "discrete"` vs. a continuous/relative shape) and `shape`. A dedicated `*-ON-PTR`
   command name (e.g. `autopilot_commands.ButtonHon`) plus a *separate* `*-OFF-PTR` element with
   its own distinct command name (`ButtonHoff`) is the "pure ON button, not a toggle" signature —
   confirmed, not inferred, once both elements are present in the dump.
2. `switch-reference.md` (generated from the same raw dump) is a faster first read for the
   device/cmd/arg table itself, but it's downstream of the raw dump — cross-check against the raw
   dump directly when the question is about *shape* (momentary/toggle), since that's exactly the
   information the generator read to produce the table, not something layered on top.
3. Independent corroboration: `grep` the relevant `aircraft-layer/research/*.md` recon notes for
   the same device/cmd/arg numbers — a prior Investigator pass may have documented the identical
   finding from a direct file read on the Windows box, which turns "the generated dump says X"
   into "two independent file reads say X."

State plainly in the review that this is a file-level confirmation of already-generated data, not
a fresh read of the installed tree — the gap is real (a DCS version bump between dump generation
and today could have changed something), but it is a much stronger answer than "unverifiable."

See [[project_effector_trigger_mission_start_ordering]] for the companion check from the same
review pass.
