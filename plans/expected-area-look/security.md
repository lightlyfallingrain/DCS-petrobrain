## Security Deep Analysis: expected-area-look (BL-B111)

**Base:** `feature/expected-area-look` fast-forwarded from `main@b92d59c9` to tip
`27eaed47dbc4f8e273f321f8e9d831c2e0d3e81f` (clean worktree, strict ancestor, ff-only — no
divergence). Inputs present and read in full: `plans/expected-area-look/plan.md`,
`implementation.md`, `review.md` (Reviewer APPROVED, no required fixes).

Scope per root `CLAUDE.md`'s Security remit: computer/network security only (code execution,
computer access, LAN port-scanner exposure, LLM prompt injection, dependency/framework risk,
secrets). Player-facing correctness (belief/phase behaviour, physical-limit respect, callout
wording) is Reviewer's territory and is not re-judged here.

### Dependency Status

No dependency change. Neither `aircraft-layer/pyproject.toml` nor `body-layer/pyproject.toml`
is touched by this diff (`git diff main..tip -- '*/pyproject.toml'` is empty); `aircraft-layer`
stays stdlib-only, `body-layer`'s declared deps (`pyproj`, `pillow`, `osmium`) are unchanged.

### Surfaces examined

1. **New Hook op `probe_points`, `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`**
   — added to the Hook's *existing* 7797 UDP listener (no new socket, no new port a LAN scanner
   would find). Code execution surface: `SET_PROBES_TEMPLATE` is a fixed module-level string
   with exactly `2 + 2*MAX_PROBE_POINTS` (= 14, `MAX_PROBE_POINTS=6`) `%d` conversions and no
   other `%` specifier, confirmed by direct inspection and by `test_line_of_sight_hook_lua.py`'s
   own mechanical assertion (`directives == ["%d"] * 14`, confirmed in `review.md`). Every value
   spliced into it (`seq`, `n`, and each `x`/`z`) passes through `_safeClampInt` — the same
   NaN-self-inequality-guarded, `±math.huge`-guarded, type-checked clamp `_applyLookDirection`'s
   `hour`/`fov_half_deg` already use (prior clearance:
   `.claude/agent-memory/security/project_xb29_los_two_percent_d_splice_approved.md`). A `%d`
   conversion of a finite integer can only produce digits and an optional leading `-`, so there
   is no way for any of these 14 substitutions to close the template string early or inject a
   new Lua statement into the `dostring_in`-bridged chunk. This is a direct, same-shape extension
   of the already-cleared pattern, not a new one — and the memory record above explicitly
   flagged that a *coordinate*-carrying extension (unlike the two small bounded integers it
   covered) would need its own look, because floats/world coordinates don't have the same
   "`%d` only emits digits" guarantee and don't have a natural small range the way an hour or a
   FOV half-angle does. That re-review is this one: `PROBE_COORD_ABS_MAX = 2000000` bounds each
   coordinate to ±2,000,000 (comfortably wider than any DCS theatre, per the Hook's own comment)
   and `_safeClampInt` is still used — not `%f`/`%g` — because the Hook truncates to integer
   coordinates before splicing, so the "only digits" guarantee holds unchanged. The boundary
   condition the prior memory asked for is satisfied; **this clearance now covers the coordinate
   case too, with the stated bound, and should be the new reference point if a further extension
   (floats, non-`%d` splice) is proposed.**

   Fail-closed verified by reading the spliced chunk directly: a failed `land.getHeight` or
   `land.isVisible` pcall emits an empty token, never a guessed `"1"`/`"0"` — correctly the
   opposite of `terrainClear`'s own fail-*open* behaviour for the unit-sightline gate, which is
   the right asymmetry for a "was this remembered place visible" query (an unanswered probe must
   never read as "seen clear"). This is a correctness property with a security-adjacent
   consequence (a mis-guessed "clear" would be a wrong-fact-into-belief issue, not an RCE one) —
   noted for completeness, verdict unaffected either way.

2. **New HTTP endpoint `POST /command/probe_points`, `aircraft-layer/src/api/server.py`** —
   shape/bounds validation before forwarding: `seq` bounded to `[0, 2**31-1]` and type/bool-
   excluded; `points` bounded to a list of at most `MAX_PROBE_POINTS` (6) `[x, z]` integer pairs,
   each coordinate bounded to `±2_000_000`, booleans excluded from the integer check (Python's
   `bool` is an `int` subclass — a known trap this codebase has hit before, correctly guarded
   here with `isinstance(coord, bool)` checks on both `seq` and each coordinate). The bound check
   on `len(points_raw)` happens before iterating the list contents, so an oversized list is
   rejected cheaply rather than walked. This is the collector-side layer of the same three-deep
   defence (`body-layer → collector → Hook`) `_LOOK_DIRECTION_*` already documents, with matching
   constants on both the Python and Lua side (`MAX_PROBE_POINTS` imported from
   `schema.line_of_sight`, not redeclared) — a mismatch here would validate a shape the Hook then
   silently reclamps differently; no such mismatch found.

   **Pre-existing finding, reproduced (not newly introduced) — `AC-B11`.** This new handler's
   body-read is the same unbounded-`Content-Length` shape every POST handler on this server
   already has:
   ```python
   length = int(self.headers.get("Content-Length", "0") or "0")
   raw_body = self.rfile.read(length) if length > 0 else b""
   ```
   `AC-B11` (`aircraft-layer/ROADMAP/AC-B11.md`) already tracks this across five existing
   handlers and was last corrected 2026-10-29 to say the handler count "stays five unless some
   other feature adds a new POST handler." This feature adds exactly that — `_handle_command_
   probe_points` is a sixth POST handler with the identical shape. **Not a new risk and not
   blocking**: `AC-B11`'s own probability/impact read (low/low — single-user LAN, `ThreadingHTTPServer`
   so one stuck handler doesn't block others, no code execution or data exposure, resource-
   nuisance only) applies unchanged to this sixth instance; nothing about `probe_points` makes it
   worse than the other five. **Filed under the existing ID rather than a new one** — see
   "Findings and their IDs" below; `AC-B11.md`'s own count correction is left to a follow-up
   docs-only edit since this dispatch asked me not to edit the roadmap.

3. **`aircraft-layer/src/schema/line_of_sight.py` (`ProbeAnswers`/`LineOfSightSnapshot`)** —
   parses the Hook's own answer sub-wire (`"<seq>|<i>:<0|1|>;..."`) over the collector's loopback
   UDP receive path (not LAN-facing; the Hook and collector are the same trust boundary this
   project has always treated as one unit — see `aircraft-layer` audit memory below). Every
   parse step raises a typed `LineOfSightParseError` on anything unexpected (bad index, index out
   of `[0, MAX_PROBE_POINTS)`, flag not one of `""`/`"0"`/`"1"`) and a malformed `probes` sub-wire
   is dropped on its own without rejecting the rest of the (valid) LOS payload — correct
   isolation, no silent widening of trust. No `eval`/`exec`/deserialization of any kind; this is
   a hand-rolled string parser over a small fixed-grammar wire format, the same style the rest of
   this module already uses.

4. **`body-layer/src/aircraft_client.py` (`post_probe_points`), `command_sender.py`
   (`send_probe_points`)** — plain JSON-encode-and-send, raise-on-failure, no new validation
   responsibility claimed (explicitly deferred to the two layers above it, matching
   `send_look_direction`'s own documented division of labour). No issue.

5. **`body-layer/src/expected_area_log.py`** — new per-run JSONL writer, path taken verbatim
   from the `--expected-area-log PATH` CLI argument (same pattern as the six existing per-run
   writers: `GroupTraceLogWriter`, `SpeechLogWriter`, etc.). This is a user-supplied CLI argument
   on the user's own machine, not a path built from any network- or mission-derived data — matches
   the body-layer full-audit's standing "no path traversal: every path is a local CLI argument or
   repo data file, none built from feed data" clearance (`project_body_layer_full_audit_2026_10_05`),
   re-confirmed rather than assumed. Unbuffered, fails closed on write error (disables itself and
   reports once to stderr, never crashes the poll loop) — same posture as every other per-run log
   writer this codebase already has.

6. **`.claude/skills/sortie-log-triage/scripts/triage.py` (`expected_area_report`)** — reads a
   local JSONL file the user names on the command line and prints aggregate counts. No network
   input, no code execution, no new attack surface; a local analysis tool over a trusted local
   log.

7. **LLM prompt injection** — no new path from received text (speech transcript, mission
   briefing text, contact name) into anything a model reads or a tool call acts on. This feature
   adds no new consumer of free-form text at all: the entire new surface is integer coordinates
   and small bounded fields (`seq`, `n`, `x`, `z`, a check "kind" string drawn from a fixed
   internal vocabulary, never from mission data). Grepped the touched belief-layer files
   (`expected_area.py`, `contacts.py`, `callouts.py`, `body.py`, `optic_policy.py`,
   `measure_expected_area_look.py`) for `eval`/`exec`/`subprocess`/`os.system`/`pickle`/
   `dostring` — none found outside the Hook's own `dostring`/`dostring_in` calls already covered
   in (1).

### Grep sweep and prior-audit cross-check

`/security-grep`-style sweep (manual, targeted at the touched files) found nothing new: no
hardcoded secrets, no new `subprocess`/`os.system`, no new broad `except Exception` without
`exc_info`/justification beyond this codebase's already-accepted pattern
(`project_body_layer_full_audit_2026_10_05`'s "five broad handlers, four log with exc_info"
finding — this feature adds none new). Cross-checked against two prior full-subproject audits
rather than re-deriving from scratch: `project_aircraft_layer_full_audit_2026_09_26.md`
(dostring_in call sites, unsupervised daemon threads — unaffected by this diff) and
`project_body_layer_full_audit_2026_10_05.md` (no socket bound in body-layer, no path traversal,
no prompt-injection path, degenerate-geometry guards — all re-confirmed still true for the new
code rather than assumed to still hold).

### Findings and their IDs

- **`AC-B11`** (existing, open, `aircraft-layer/ROADMAP/AC-B11.md`) — now reproduced by a sixth
  POST handler (`_handle_command_probe_points`). Not filed as a new item; cited under its
  existing ID. Its probability/impact rating (low/low) is unchanged by this sixth instance.
  **Not filed as a roadmap edit here** — this dispatch asked me not to edit the roadmap; a
  follow-up docs-only commit should update `AC-B11.md`'s handler count from five to six and name
  `probe_points` alongside the other five.
- No other finding rose to a level needing an ID. Everything else in this report is either a
  re-confirmation of an already-cleared pattern (the `%d`-only splice, extended here to cover the
  coordinate case the prior memory had explicitly left open) or a clean result.

### Verdict

**PASS**

No confirmed exploitable vulnerability, no probable risk, no new dependency, no new network
surface (same socket, same port), no code-execution path reachable from received data beyond the
already-cleared `%d`-only splice pattern (now explicitly re-verified for the coordinate case),
and no prompt-injection path (this feature introduces none). The one reproduced finding
(`AC-B11`, unbounded `Content-Length`) is pre-existing, already tracked, rated low/low under this
project's stated LAN-only threat model, and not blocking — consistent with how its prior four
instances were treated.

### Memory

Updated `.claude/agent-memory/security/project_xb29_los_two_percent_d_splice_approved.md` is left
as-is (it correctly flagged the coordinate case as needing its own review, which this is) and a
new memory file records this review's result and the AC-B11 reproduction, so a future pass does
not re-derive the `%d`-splice argument from scratch for `probe_points`.
