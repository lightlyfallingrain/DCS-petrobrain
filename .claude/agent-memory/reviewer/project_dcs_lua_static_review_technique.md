---
name: project_dcs_lua_static_review_technique
description: How to review unverified DCS-side Lua/.dlg artifacts without a live DCS session
metadata:
  type: project
---

When a plan lands a new DCS Hook-state script / `.dlg` widget file marked "UNVERIFIED against a
live DCS session" (e.g. BL-2.5's `petrobrain-overlay-hook.lua`/`petrobrain-overlay.dlg`,
2026-09-09), do not treat "unverified" as automatically un-reviewable. `$DCS_INSTALL_PATH` and
`$DCS_SAVED_GAMES_PATH` are readable, read-only, on any box with DCS installed (check both env
vars are set first — the `dcs-file-investigation` skill covers this). Real, currently-installed
reference implementations sit right there and can be diffed against the new code line-by-line:

- SRS's actual overlay: `$DCS_SAVED_GAMES_PATH/Mods/services/DCS-SRS/Scripts/
  DCS-SRS-OverlayGameGUI.lua` + `.../UI/DCS-SRS-Overlay.dlg`, and its loader
  `$DCS_SAVED_GAMES_PATH/Scripts/Hooks/DCS-SRS-hook.lua`.
- DCS's own shipped UI widgets/skins that use the same widget class:
  `$DCS_INSTALL_PATH/Scripts/UI/gameMessages.dlg`/`gameMessages.lua` (real `AutoScrollText`
  usage — `addText`/`clear`/`calcSize`/`getTextLinesCount` all appear here as real, currently-used
  calls) and `$DCS_INSTALL_PATH/dxgui/skins/skinME/*.skin.lua` (base-skin defaults, e.g.
  `auto_scroll_text.skin.lua`'s `textWrapping` split between its outer and `skins.text` sub-skin).
- `$DCS_INSTALL_PATH/Scripts/JSON.lua` itself, when a plan/implementer claims DCS ships a JSON
  codec — confirm the file exists, confirm what `loadfile(...)()` actually returns
  (`return OBJDEF:new()` at EOF, exposing `:decode`/`:encode`), and confirm SRS's own file loads
  it the same way, rather than trusting the claim.

This turned a "cannot verify" boundary into a thorough review for BL-2.5: every claim in the
plan/implementation.md about SRS's/DCS's real files checked out exactly, including a documented
deviation (loading `Scripts/JSON.lua` instead of hand-rolling a decoder) that was independently
confirmed correct. Reserve "Stage 2 is user-only, unverified" for what genuinely can't be checked
without a running DCS process (does the window actually render, does `AutoScrollText` wrap as
predicted) — not for the widget API shape, skin structure, or file-loading mechanics, all of which
are checkable from the shipped Lua source.

See also [[project_pb2_belief_invariants]] for the general pattern of grepping real installed
files rather than trusting a plan's claims about DCS internals at face value.

**Follow-up (BL-2.5 restyle pass, 2026-09-09)**: this technique also catches citation drift, not
just missing citations. Diffing the implementer's own quoted claim about `gameMessages.dlg`'s
`layout.data.anchorInfos` ("top/left both `type=\"min\"`") against the real file found `left`/
`right` are actually `type="max"` — a minor mis-transcription that didn't change any actual number
(the position constants were hardcoded, not parsed from the anchor data) but would have gone
unnoticed without re-reading the cited file directly rather than trusting the implementer's summary
of it. Always re-read the cited source file yourself; don't just check that a citation exists.

Also: two things only the *full post-change file* (not just the diff hunks) can establish —
(1) call-graph nil-safety for a new helper function (trace every call site back to confirm the
widgets/state it touches are always initialized first — here, `apply_content_size()`'s two call
sites both post-date `window`/`message_text` assignment, confirmed by reading `onSimulationFrame`'s
full guard structure, not visible from the hunk alone); (2) pcall/error-containment chains, since a
function can be "protected" by an ancestor's `pcall` without wrapping itself. Read the whole file
when a diff introduces a new function with error-handling claims in its own comment — verify the
claim against the actual call sites, don't take the comment's word for it (here it was close, not
wrong — one level looser than literally stated).

Widget.lua's binding return order is worth confirming directly rather than assumed: `calcSize()`/
`getSize()` return `(width, height)` and `setSize`/`setBounds`/`setPosition` are independent (no
documented side effect from one on the other), which settles "does repeated resizing accumulate
drift" — no, each call is an idempotent absolute set, not a relative adjustment.
