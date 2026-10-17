# AC-B9 — Three Hook scripts failed to load, and nothing downstream could tell

- [x] **AC-B9 — A `[[ID]]` wikilink inside a Lua `--[[ … ]]` header comment is a syntax error.
  Three Hooks carried one, none of them loaded, and Petrovich detected nothing for a whole
  sortie.** #status/done Filed and fixed 2026-10-17
  (`fix/lua-hook-wiki-link-brackets`, merged `a9c3be3e`).

  **Symptom as the user reported it**: *"Petrovich detects no targets at all now. My desert
  mission, units in plain view."*

  **Cause.** Lua 5.1 does not nest long brackets. This repo's Obsidian link convention
  (`docs/DOC_CONVENTIONS.md`) writes an ID as `[[BL-B73]]`, and that form reached the Lua long
  comments three Hook scripts use as headers. The link's `]]` closes the comment early; the `[[`
  then raises `nesting of [[...]] is deprecated`. `dcs.log`, 2026-10-17 18:30:22, three
  consecutive `Failed to load` lines:

  | file | line | link |
  |---|---|---|
  | `petrobrain-firing-events-hook.lua` | 81 | `[[BL-B74]]` |
  | `petrobrain-line-of-sight-hook.lua` | 104 | `[[BL-B73]]` |
  | `petrobrain-mission-telemetry-hook.lua` | 55 | `[[BL-B72]]` |

  All three arrived on 2026-10-15/16 with `AC-B7`/`AC-B8` — the first Hook headers written after
  the ID-link convention became habitual.

  **Why one dead Hook blinded him completely.** With the line-of-sight Hook unloaded,
  `GET /line_of_sight/latest` served no samples, so every candidate reached
  `perception.visibility`'s gate 4 with `live_los_clear=None`, and that gate is fail-closed by
  design (`plans/bl11-stage4-fail-closed/plan.md`: no verdict is treated as blocked). The
  detection trace is unambiguous:

  | sortie | `live_los_clear` verdicts | admitted |
  |---|---|---|
  | `dcs-detection-trace-20261015-175509.jsonl` | 4553 `true` | 104 |
  | `dcs-detection-trace-20261017-213342.jsonl` | **0 — absent on all 23744 rows** | **0** |

  230 of those rejections were `terrain_los` at ranges down to 348 m, in flat desert. **Gate 4
  behaved exactly as specified**; the fault was entirely upstream of body-layer.

  **The other two were down too, and nobody noticed.** `petrobrain-mission-telemetry-hook.lua`
  carries unit velocity and `life`/`life0` (`[[AC-B7]]`), so motion detection and burning-unit
  emitters were dead the same sortie; `petrobrain-firing-events-hook.lua` is `[[AC-B8]]`'s whole
  channel. Each degrades independently and silently by design — the `AircraftLayerError` →
  `None` fallbacks in `naked_eye_source.py` exist so one dead feed cannot take a poll down. That
  is right, and it is also why three dead feeds produced no symptom anyone could read except the
  blackout itself.

  **The transferable finding: nothing distinguishes "the Hook is dead" from "nothing is out
  there."** DCS reports a load failure once, in `dcs.log`, at mission load. No endpoint, no trace
  row and no callout says a feed never started rather than returned empty. The fix below closes
  the *cause*; the detectability gap is `[[AC-B10]]`.

  **Fix.** Links replaced with plain backticked IDs, in line comments as well as block ones (a
  reflow moves text between them). Comment text only; no executable Lua changed. Guard:
  `aircraft-layer/tests/test_dcs_export_lua_syntax.py` — a pure-Python ban on the form in any
  `.lua`, always run, plus a real `loadfile` parse of every `dcs-export/*.lua` under a Lua 5.1
  interpreter (`luajit`/`lua5.1`), skipped where neither is installed. Both checks were falsified
  against the broken files before being accepted. The rule is recorded in
  `docs/DOC_CONVENTIONS.md`, next to the convention that caused it.

  **Why no existing check caught it — and the uncomfortable half.** `test_line_of_sight_hook_lua.py`
  and its siblings are static *text* checks; the subproject has no DCS process to run a Hook
  against, which its own docstring explains. Reading a file as text cannot notice it is not valid
  Lua. But **this subproject already documented the right check** — `aircraft-layer/CLAUDE.md`'s
  Commands section carries `for f in aircraft-layer/dcs-export/*.lua; do luac5.1 -p "$f" || echo
  "FAIL $f"; done`, and has since long before this incident. It was never run, because it is a
  manual command in a document and `luac5.1` is not installed on the Mac dev machine where these
  files are edited. So the guard added here is not a new idea; it is the documented one moved
  into `pytest`, where it runs whether or not anyone remembers it, and widened to accept any
  Lua 5.1-compatible interpreter. `luajit` reproduced DCS's failure exactly: same three files,
  same three lines.

  **Deployment**: the fixed Hooks must be recopied to `Saved Games\DCS\Scripts\Hooks\` — a merge
  does not reach the DCS install (`aircraft-layer/WORKFLOW.md`).

  Related: `[[AC-B7]]`, `[[AC-B8]]`, `[[AC-B10]]`, `[[BL-B72]]`, `[[BL-B73]]`.
