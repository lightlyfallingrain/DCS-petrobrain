# AC-B12 — Split Export.lua into loaded modules, and read only what Petrobrain needs

- [x] **AC-B12 Part 1 — split `Export.lua` into several files loaded with `dofile` — DoD-PASSED
  2026-11-16 on `feature/ac-b12-export-modules` (tip `590eebb1`), merge sha filled in by the merge
  step.** #status/done #needs-flight Filed 2026-11-16 by user direction. Architect plan:
  `plans/ac-b12-export-modules/plan.md`. **Branch to fly: `main`, after this DoD's merge.**

  **Part 2 ("read only what is needed") is not built here** — explicitly out of this plan's scope,
  staged to follow per feed. Re-filed below as its own open item so this entry's `[x]` reflects
  Part 1 alone.

  **Why now.** Lua 5.1, which DCS runs, allows at most 200 active locals per function, and a file's
  top level counts as one function. `aircraft-layer/dcs-export/Export.lua` is one 2,832-line file
  with 193 top-level locals on `main` before BL-16's takeover revision; that revision
  (`feature/bl16-takeover-fix`) landed at **exactly 200** by grouping its state into one table and
  deleting unused constants (`.claude/agent-memory/implementer/project_export_lua_200_local_ceiling.md`).
  BL-16's next stage (altitude/heading/speed goals) adds more state and would hit the ceiling at
  once. Lua 5.1 also caps a function at 60 upvalues, the next wall for the same reason.

  **The limit is on code layout, not on data.** One table can hold any number of args or readings
  as a single local.

  **The user's direction, verbatim:**

  > *"option 2."* — split into several files loaded from Export.lua, chosen over grouping state
  > into tables or `do ... end` scoping, which only buy time.
  >
  > *"Also, we don't need to read all flight data all the time. Only read what Petrobrain needs at
  > any moment."*

  ## Part 1 — split into modules

  - `Export.lua` becomes a short loader: `dofile(lfs.writedir() .. "Scripts\\Petrobrain\\<module>.lua")`
    per subsystem. Each file is its own chunk with its own 200-local budget. This is the usual way
    DCS add-ons hook Export.lua (DCS-BIOS, Tacview).
  - Group by subsystem, e.g. transport and telemetry, Petrovich indication, the 9K113 sight/servo,
    the AI-pilot wheel (BL-16), PTT/ICS, the inbound command listener, watched/read args. The plan
    decides the exact cut.
  - Inside a module, constants and state go in tables, so a module does not re-approach the ceiling.
  - **Deployment changes from one file to a folder.** `aircraft-layer/WORKFLOW.md`'s deploy steps
    and the version check (`EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION`, which today catches a
    stale single file) must cover every module, so a half-updated folder is caught the same way.
  - Probes stay standalone single files, as now.
  - Behaviour must not change. The live risk is deployment, so acceptance is one short check
    flight confirming every feed still reports.

  ## Part 2 — read only what is needed

  **Existing mechanism, reuse it:** cockpit args are already read by need since
  `plans/effector-sequences/plan.md` Stage 4 — body-layer declares a small continuous set
  (`watch_args`, read at the 5 Hz tick, sent only on change) and asks for one-shot reads
  (`read_args`, answered the same frame). Extend that principle to the feeds still pushed
  unconditionally every tick — telemetry, world objects, the HelperAI indication, the AI-pilot-wheel
  status and the rest — so each is read and sent only while body-layer has a use for it. Which feeds
  are always-on (e.g. ownship telemetry) is a plan-time decision. Not a second mechanism beside
  `watch_args`.

  ## Order

  Part 1 first, before BL-16 Stage P2, with no behaviour change. Part 2 can follow per feed.

  **Scheduled 2026-11-16 (user): *"schedule AC-B12 before BR-2"*.** Queue: BL-16 takeover fix
  (`feature/bl16-takeover-fix`) merges → **AC-B12** → BR-2's Stage 5 re-plan. Role sequence is the
  refactor one: Architect → Implementer → Reviewer → Security → Definition of Done. **BR-2 was
  dequeued later the same day (user: *"dequeue BR-2"*): nothing is queued after AC-B12.**

  **Also carries `[[AC-B13]]`** (filed 2026-11-16): release any open AI-pilot-wheel press and clear
  the takeover state on `LuaExportStop`. A small behaviour fix, the one exception to Part 1's "no
  behaviour change"; it lands in the AI-pilot-wheel module's own stop hook.

  ## DoD, 2026-11-16

  Reviewer APPROVED (round 2, after one required fix — `commands.lua`'s dispatch table now guards
  each handler-owning module on non-`nil` instead of taking all five ops down if one module fails
  to load). Performance Reviewer: APPROVED — MONITOR (cross-module helper calls move from upvalue
  to global lookup, ~100-300 ns/frame; two to three orders of magnitude below this file's own
  accepted per-frame closure-allocation pattern, no credible risk in this project phase). Security:
  APPROVED (one low/low finding — generic helper names now live as bare globals in the Export Lua
  state — presented to the user as a Risk Communication item, decided **option A, no change,
  nothing filed**: self-inflicted only, requires the user's own future action — chaining a second
  Export-side add-on into the same Lua state — to become reachable at all).

  `aircraft-layer`: `luac5.1 -p` clean on all 9 Lua files (loader + 8 modules); `ruff format`/
  `ruff check`/`mypy --strict` clean; `pytest` 795 passed, 0 skipped, 0 failed (confirmed the
  139 Lua-interpreter-backed tests across the 7 affected files ran, not skipped). Full report:
  `plans/ac-b12-export-modules/dod.md`.

  **Acceptance boundary.** The split's one real risk — a multi-file deploy going half-stale, or a
  load-order surprise live in DCS — cannot be retired on a dev machine. The version-handshake logic
  itself was run for real (loopback socket standing in for Export.lua, against the actual collector
  code) and both the match and mismatch paths fire correctly; AC-B13's `on_stop` fix has a passing
  Lua unit test. What only a live session can confirm: every feed still reporting after a real
  `Petrobrain\` folder deploy, a clean `dcs.log`, and — the prize — that a mission restart
  mid-correction-hold releases the AI-wheel press rather than leaving it stuck. Card published:
  https://claude.ai/artifact/5Q1za4baC6VNYaRoScNuyc
  (`docs/acceptance/2026-11-16-ac-b12-export-modules-sortie.md`). **Branch to fly: `main`.**

  **Milestone-completion question.** Yes — this unblocks `BL-16` Stage P2 (altitude/heading/speed
  goals), which was going to add state to a file already at the hard 200-local ceiling with zero
  headroom; P2's new state now has a home in the `ai_pilot_wheel` module. It also gives Part 2
  ("read only what is needed," below) a natural per-feed home once a feed lives in its own module —
  still not built, still a plan-time decision per feed, not promised for any particular next
  milestone.
