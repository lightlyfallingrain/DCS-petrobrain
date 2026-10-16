# MI-B2 — A malformed `.miz` escapes as `RecursionError`/`TypeError` instead of `MizParseError`

- [ ] **MI-B2 — `miz/reader.py:70-79` catches only `SyntaxError`, so two reachable malformed-input
  shapes crash with an unhandled exception instead of this subproject's own parse error.**
  #status/open Filed 2026-10-16 from the whole-subproject security survey
  (`mission-interpreter/research/2026-10-16-security-audit.md`, Findings 2 and 3, bundled because
  they share one fix site).

  | input shape | what happens today |
  |---|---|
  | deeply nested Lua table | the vendored parser (`_vendor/dcs_lua/parse.py`) has no recursion-depth limit → uncaught `RecursionError` |
  | a Lua table with mixed `str`/`int` keys | `_as_ordered_list`'s `sorted(value.keys())` → uncaught `TypeError` |

  **Both are low severity and neither is a vulnerability**: this is an offline tool the pilot runs on
  his own files, and the outcome is a stack trace rather than a wrong Mission Understanding. The fix
  is to catch both alongside `SyntaxError` and re-raise as `MizParseError`.

  **Why it is still worth filing.** This subproject's inputs are the only ones in the project it did
  not write — a third-party sample mission (Bagram) has already been consumed — so *"the user wrote
  every input"* is not true here, and a clean parse error is the difference between a usable message
  and a traceback the pilot has to interpret. The same survey confirmed the genuinely dangerous
  shapes are absent: no `extractall` (so no zip-slip), no `eval`/`pickle`/`yaml.load`, no SSRF
  (both HTTP clients hit fixed localhost URLs, never mission-derived ones).

  **Deliberately not filed**, from the same survey, so the decision is visible rather than
  forgotten: no size cap on individual `.miz` zip-member reads (single-member zip-bomb). Judged not
  worth it at current scope.
