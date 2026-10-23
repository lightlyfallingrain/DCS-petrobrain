### Performance Review

**Scope:** `body-layer/tools/generate_effector_registry.py` (BL-B90 Stage 0), branch
`feature/effector-sequences`, tip `6d49503df7bccc038efad0798bed773a48780b9b`. Offline dev-time
generator, run manually after a DCS patch, never on a runtime hot path, never in CI. Reviewed at
the effort level that posture earns: a short pass for pathological regex backtracking or
quadratic scans over the real input sizes (`clickabledata.lua` 1205 lines / 749 `elements[`
heads; `command_defs.lua` 2196 lines / 49 tables), not a hot-path-grade audit.

### Method

Read the full generator (`generate_effector_registry.py`, 1128 lines) end to end, tracing every
function that scans more than a fixed-size slice of input: `_strip_lua_comments`,
`_extract_balanced`, `_split_top_level`, `parse_devices`, `parse_command_defs`,
`_parse_command_loop`, `scan_clickabledata`, `_find_ignored_statements`. All are single
left-to-right passes over either the whole file (comment stripping) or a span bounded by one
element/table's own extent (`_extract_balanced`'s matching-bracket scan, `_split_top_level`'s
argument split) — no function re-scans the full file once per element, and no regex combines
nested unbounded quantifiers (no `(a+)+`/`(.*)*` shape) that could backtrack catastrophically.

Measured rather than assumed: `n` here is a real count straight from the 2026-10-23 recon (749
elements), not a guessed one, so there was nothing to re-derive against `len()` before scaling —
the risk in question was scaling behaviour (linear vs. quadratic), which only a timed run answers.

Built a synthetic benchmark (`scan_clickabledata`/`parse_command_defs` against generated
`clickabledata.lua`/`command_defs.lua`-shaped text) at N = 200/400/800/1600/3200/6400 elements —
up to **8.5x** the real file's 749 — to confirm scaling empirically rather than by code-reading
alone:

| N (elements) | `parse_command_defs` | `scan_clickabledata` |
|---|---|---|
| 200 | 0.04 ms | 5.75 ms |
| 400 | 0.07 ms | 11.35 ms |
| 800 | 0.13 ms | 22.94 ms |
| 1600 | 0.27 ms | 48.89 ms |
| 3200 | 0.54 ms | 101.47 ms |
| 6400 | 1.08 ms | 222.40 ms |

Each doubling of N roughly doubles the time (linear), both functions. Extrapolating to the real
749-element file: ~21 ms for `scan_clickabledata`, under 1 ms for `parse_command_defs`. The
harness can fail: it asserts `heads == n` after every run (would catch the benchmark itself
generating a malformed fixture or the parser silently dropping elements), and the fixture
generator reuses the real helper-call/table forms (`default_button(...)`, `count =
start_command`), not a simplified stand-in, so a regression in the real regexes would show here
too.

### Findings

No credible risk identified. One note, not an action item:

#### Regex backtracking on adversarial input
- **Location:** `_RAW_ACTION_RE`/`_RAW_ARG_RE`/`_RAW_ARG_VALUE_RE`/`_RAW_CREW_RE` and friends
  (alternations with `[^{}]*`/`[^,\n]+`) could in principle backtrack badly on pathological
  nested-brace input.
- **Risk:** none at realistic scale, and not realistic input besides. The input is ED's own
  shipped `clickabledata.lua`, read once per invocation on the machine that has it installed —
  not adversarial, not attacker-controlled, and the benchmark above already exercises element
  counts 8.5x the real file with no super-linear growth.
- **Action:** MONITOR. Worth a second look only if a future DCS patch introduces deeply nested
  table literals this parser does not already handle (it would fail closed as "unhandled" first,
  per its own fails-closed design, before a timing problem would ever surface).

### Verdict

APPROVED

No performance concerns given this tool's posture (offline, dev-time, rare invocation, trusted
input, realistic sizes in the low thousands of lines). All hot functions scan in time linear in
input size, confirmed both by reading (single-pass, locally-bounded extraction) and by a timed
benchmark at up to 8.5x real scale.
