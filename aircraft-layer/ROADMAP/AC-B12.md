# AC-B12 — Split Export.lua into loaded modules, and read only what Petrobrain needs

- [ ] **AC-B12 — Split `Export.lua` into several files loaded with `dofile`, and extend "read by
  need" to every feed, before BL-16's next stage.** #status/open Filed 2026-11-16 by user
  direction.

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
  refactor one: Architect → Implementer → Reviewer → Security → Definition of Done.

  **Also carries `[[AC-B13]]`** (filed 2026-11-16): release any open AI-pilot-wheel press and clear
  the takeover state on `LuaExportStop`. A small behaviour fix, the one exception to Part 1's "no
  behaviour change"; it lands in the AI-pilot-wheel module's own stop hook.
