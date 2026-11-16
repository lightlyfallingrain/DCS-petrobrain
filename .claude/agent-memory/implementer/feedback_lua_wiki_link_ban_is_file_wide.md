---
name: lua-wiki-link-ban-is-file-wide
description: Obsidian [[ID]] wiki links in a Lua dcs-export file fail test_no_nested_long_bracket_in_block_comment even outside the --[[ ]] header block -- write IDs as plain `BL-Bxxx` everywhere in that file.
metadata:
  type: feedback
---

`aircraft-layer/tests/test_dcs_export_lua_syntax.py::test_no_nested_long_bracket_in_block_comment`
scans an entire `dcs-export/*.lua` file for `[[...]]`-shaped text and fails on any match -- not
just inside the `--[[ ... --]]` header comment block. I added `[[BL-B118]]` in two `--:`
single-line comments well past the header block's own `--]]` close and the test still failed,
with the exact message naming the 2026-10-17 incident (three Hooks failed to load because Lua 5.1
does not nest long brackets).

**Why:** a future edit could move that single-line comment's text into a block comment, or a
different Hook script's layout could put a `--:` comment before its own header closes -- the check
is deliberately conservative rather than tracking which region is "safe" at the moment it runs.

**How to apply:** when writing or editing any `aircraft-layer/dcs-export/*.lua` file and citing a
project ID (`BL-B118`, `AC-B12`, etc.), always write it in plain backticks, never as an Obsidian
`[[ID]]` wiki link, anywhere in the file -- not only inside the header comment. Catch this with
`grep -n '\[\[' dcs-export/<file>.lua` before running the test suite, since the failure message
itself is clear once you hit it, but catching it first saves a round trip.
