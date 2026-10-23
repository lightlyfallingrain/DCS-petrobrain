# BL-B91 — effector-registry TOML renderer does not escape control characters in free-text fields

**Filed by:** Security deep analysis, `plans/effector-sequences/security-stage0.md`, 2026-10-23.
**State:** `[x]` done — fixed 2026-10-23: `_toml_string`/`_toml_key` now escape every TOML
basic-string short escape (`\b \t \n \f \r \" \\`) and emit `\uXXXX` for any other codepoint
below U+0020 or DEL (U+007F), so a control character in `label`/`name` round-trips through
`tomllib` instead of breaking the parse; see `plans/effector-sequences/implementation.md` for
the round-trip tests. #status/done

`body-layer/tools/generate_effector_registry.py`'s `_toml_string`/`_toml_key` escape `\` and `"`
only. The two free-text fields sourced from ED's own Lua (`label`, the `hint = _("...")` string;
and `name`, the `elements["..."]` key) are not restricted to a safe character class the way every
other field is (`device`/`cmd`/`arg` are regex-constrained to `-?\d+` before they ever reach the
renderer). A literal control character — most concretely a raw newline — in either field
reproduces verbatim into the generated TOML and breaks the surrounding basic string.

**Demonstrated, not theoretical** (reproduced by this security pass): a `label` containing
`'evil\nlabel = "INJECTED"\n[elements.pwn]\nx=1'` renders as a value that spans multiple raw lines
and crashes `tomllib.loads` with `Illegal character '\n'` — it does **not** inject a working new
key (TOML's own grammar refuses an unescaped literal newline inside a basic string, so the parser
fails closed rather than accepting attacker-chosen keys). The practical effect is a hard parse
failure of `body-layer/config/effectors-raw.toml` at body-layer startup, not code execution and not
a file write outside the intended path.

**Why this is filed as low-severity, not blocking:** the two fields' content comes from ED's own
shipped `clickabledata.lua` — the single user's own local DCS install, not network-reachable or
remotely influenced, and not plausibly containing a raw control character (English UI hint text).
Severity stays low because nothing in this project's threat model (malicious dependency code, a LAN
port scanner) can reach these fields; this is defense-in-depth against a corrupted/patched ED file
producing an unreadable config rather than a clean, obvious error.

**Fix, when picked up:** `_toml_string`/`_toml_key` should escape (or reject as "unhandled" rather
than guess at) any codepoint below U+0020 other than tab, the same fail-closed posture the parser
already applies to every numeric field — raise `UnhandledElement` for the offending element instead
of emitting a string the renderer cannot make syntactically valid.

**Options presented to the user (2026-10-23 security review):**
- (A) Ignore — accept the risk as documented above.
- (B) Add to backlog — this entry.
- (C) Fix now.
- (D) Stop.

Not yet decided by the user as of filing; left `[ ]` open pending that call.
