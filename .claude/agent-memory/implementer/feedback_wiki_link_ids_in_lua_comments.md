---
name: feedback-wiki-link-ids-in-lua-comments
description: Never write [[BL-XXX]] wiki-link style IDs in a Lua file's comments, even outside a block-comment header -- the project's own Lua test suite rejects it repo-wide, and it is an easy habit to carry over from Markdown.
metadata:
  type: feedback
---

When adding comments to `aircraft-layer/dcs-export/*.lua`, write cross-references as plain
backticked IDs (`` `BL-B80` ``), never as `[[BL-B80]]` wiki-link syntax -- even in an ordinary
`--` line comment, not just inside a `--[[ ... ]]` block header.

**Why:** `aircraft-layer/tests/test_dcs_export_lua_syntax.py::test_no_nested_long_bracket_in_
block_comment` scans the *whole file* for the `[[...]]` pattern, not just inside block comments,
because Lua 5.1 does not nest long brackets and a wiki link landing inside a `--[[` header breaks
the whole script silently (the 2026-10-17 incident the test's own failure message cites: three
Hooks failed to load and Petrovich saw nothing). The check does not try to distinguish "this one
is inside a line comment, so it's safe" from "this one would break a block comment" -- it just
forbids the pattern everywhere in the file.

**How to apply:** I wrote `[[BL-B80]]` twice in ordinary `--` comments while adding Stage 4b's
slew-trace logging (BL-B66) to `Export.lua` -- carried the habit straight over from writing
`body-layer/CLAUDE.md`-style prose in the same session, where `[[ID]]` is the normal cross-
reference form. `pytest` caught both immediately on the first full aircraft-layer run. Catch it
myself next time: grep any `.lua` file I just edited for `\[\[` before running the suite, the same
way I'd check for a stray `TODO`.
