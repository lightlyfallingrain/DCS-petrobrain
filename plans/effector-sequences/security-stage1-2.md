## Security Deep Analysis: BL-B90 Stages 1-2 (effector registry/sequence loader, engine, wiring)

Branch `feature/effector-sequences`, reviewed at `f452db83896eadd52f0ee5ba73150339c046b86d`
(checked out detached in-worktree; the worktree's own prior tip, `f4e552c1...`, is not an
ancestor of this tip, so `git checkout --detach` was used rather than a fast-forward merge; tree
clean before and after).

Diff reviewed: `git diff 8f2dc3f3 f452db83 -- body-layer aircraft-layer` (excludes `71dd23ce`'s
merge of `main`, already reviewed as `fix/guidance-ready-edge`).

**Threat model applied (root `CLAUDE.md`, 2026-10-21): single-user, LAN-only. Realistic attackers
are (1) malicious code in a dependency and (2) an infected LAN machine port-scanning.** Sequence
files are user-edited local config, not network input — the question for this pass is whether a
malformed or hostile file, or the new wiring around it, can turn into code execution, a write
outside the intended lane, or a crash that kills the poll loop (the "what a LAN port scanner
reaches" lens applies to the unchanged HTTP surface, not to this stage's local-file surface).

### Dependency Status

No dependency change — confirmed, `git diff` on both `pyproject.toml` files is empty. Imports in
every new module (`effector_registry.py`, `effector_sequences.py`, `effector_engine.py`,
`render_switch_reference.py`) are stdlib (`tomllib`, `re`, `hashlib`, `pathlib`, `dataclasses`,
`enum`, `itertools`) plus this project's own `tuning`/`aircraft_client`/`belief.*` modules.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `effector_sequences.py` (whole file) | Markdown-table parser: `_parse_tables`/`_parse_header`/`_parse_data_table`, regex-based | No `eval`/`exec`/`loadstring`/`dostring`/`subprocess`/`os.system`/`pickle`/`yaml.load`/`__import__` anywhere — grepped the full diff, zero hits. Every parsed cell is either matched against a closed regex (`_WAIT_ROW_RE`, `_CONDITION_RE`, `_SEPARATOR_CELL_RE` — none has a nested-quantifier/catastrophic-backtracking shape; all are linear, bounded by a fixed small alphabet) or looked up by exact string equality in the registry `dict`. No path is read from file *content* at any point — see next row. | None. |
| `effector_sequences.py` L417-421, `effector_registry.py` L316-319 | File discovery: `sequences_dir.iterdir()` / `aircraft_dir.glob("*.md")`, registry paths built from a fixed `DEFAULT_SEQUENCES_DIR`/`DEFAULT_RAW_DUMP_DIR` (both anchored to `Path(__file__).resolve().parent...`) plus **the directory's own name on disk**, never from text parsed out of a file's body | No path-traversal surface: nothing constructs a filesystem path from a header cell, a row cell, or any other parsed content. A sequence file's `aircraft` header value is used only to *validate against* the directory it was found in (`aircraft_dir_name(sequence_file.aircraft) != aircraft_dir.name` → file error), never to build a new path. The registry's own `aircraft_dir.name` comes from `Path.iterdir()`, i.e. what the local filesystem already has, not from parsed text. | None. |
| `effector_sequences.py` `load_sequences`, `effector_registry.py` `load_registry`/`_resolve_entry`/`load_registries_by_aircraft` | D5 non-fatal posture — every documented error path returns `(..., errors)` rather than raising | Verified by reading, not just trusting the docstrings: `_load_one_file` catches `OSError` on read; `_read_toml` catches `OSError`/`tomllib.TOMLDecodeError`; every validation branch in `_parse_header`/`_parse_data_table`/`_resolve_entry` returns a `SequenceError`/`RegistryError` value, never raises or asserts on attacker-shaped (here: user-editable) input. The two `assert` statements present (`effector_sequences.py:321`, `load_sequences` docstring's own tuple-unpack) guard an already-validated invariant (`op in ("=", "!=")`, matched by the same regex one line above) and an internal post-condition on `parsed`/`entries` built by this module's own code — not reachable from file content. `logger._load_effector_config` (the one caller) does not wrap its two loader calls in `try/except` at all, and does not need to: both loaders' own contract is "never raises on bad content," and this call happens once at `main()` startup, before the poll loop exists — even an unanticipated bug raising here would fail at startup, not mid-flight, and could not kill a running poll loop. | None. |
| `effector_engine.py` `advance()` | Whether a sequence file can write any `(device, cmd, value)`, or only registry-resolved ones | **Only registry-resolved.** `row.effector`/`row.value`/`row.condition.effector`/`row.condition.value` are all validated at *load* time against `EffectorDef.values` (`effector_sequences._parse_data_table`, confirmed above) — a row naming an effector or value not in the registry is already dropped as a `SequenceError` and never reaches `SequenceFile.rows`. At execution time, `advance()` only ever calls `client.write_cockpit_switch(effector_def.device, effector_def.cmd, value)` where `effector_def = registry.get(row.effector)` and `value = effector_def.values[row.value]` — both looked up from the already-resolved `EffectorDef`, never read as a number out of the markdown file. A sequence file has no way to name an arbitrary device/cmd/arg/value; it can only select among the finitely many `(effector, value)` pairs the curated `effectors.toml` already resolved to real DCS numbers. This is the same "write channel is already generic, but only a curated name reaches it" shape `security-stage0`/`BL-B66`'s pass already accepted for the registry-resolved write op — this stage extends it with a loader indirection, not a new write surface. | None. |
| `effector_engine.py` L371-391 (D9 write-failure handling) | `client.write_cockpit_switch` raising `AircraftLayerError` | Caught, logged, retried next poll — does not propagate out of `advance()`, cannot crash the poll loop that calls it (`logger.py`'s crew-text poll block). Matches the "crash kills a poll loop" scope item. | None. |
| `aircraft-layer/src/schema/cockpit_switch.py` `to_api_dict` | New `"args"` map on `GET /cockpit_switch/latest`'s response | Purely a derived read-only re-keying of six fields the class already carried and already served — confirmed by diff, no new `Export.lua` read, no new POST handler, `server.py` untouched (`git diff` on it is empty). No change to bind address, no change to auth posture (there was none before; still none). This is a response body shape change on an existing GET, not a new attack surface. | None. |
| `effector_sequences.py` `petrovich_says` field (`SwitchRow.petrovich_says`) | Potential prompt-injection / spoken-text path flagged by `security-stage0` as "the point to re-examine ... if a later stage pipes label into an LLM-visible surface" | **Not yet a live surface.** Grepped the full diff: `petrovich_says` is parsed and stored on `SwitchRow` but has **no reader anywhere in `effector_engine.py` or `logger.py`** this stage — a switch row's own `petrovich-says` cell is silently inert (never spoken), and the only other shape that could carry it, a say-only row, is explicitly rejected at load time ("say-only rows arrive with the guidance-unit-ready trigger"). The one spoken line this stage adds, `CONFIG_ERROR_LINE` (`crew_console.py:1034`), is a hard-coded `Final[str]` constant — confirmed by reading it — never built from a file's name, line number, or error reason (those go only to `logger.error`/stderr, never to `_print`/TTS). So neither this stage's config-error line nor its (currently unused) `petrovich-says` cells reach spoken or brain-facing text yet. | None this stage. Re-check the moment a future stage wires `petrovich_says` (or the say-only row, D7's `guidance-unit-ready` seam) into `CrewConsole._print` — that is the point `security-stage0` already flagged, and it is still correctly unflagged here. |
| `render_switch_reference.py` | New dev tool, static TOML read, `--write` to a fixed path | Same posture as `generate_effector_registry.py`/`generate_defaults.py`: three hard-coded module-level path constants (`_RAW_DUMP_PATH`/`_CURATED_PATH`/`_OUTPUT_PATH`), no CLI path override, no content-derived path, no execution of anything read. | None. |

### Readback feed trust

`EffectorRunState.advance`'s `readback` argument is the `args` map from `GET /cockpit_switch/latest`
— i.e., whatever the aircraft-layer collector on the LAN reports. This is the same trust boundary
every other body-layer↔aircraft-layer reader already accepts (aircraft-layer is a trusted LAN peer,
unauthenticated by design, per the standing single-user/LAN-only posture) — this stage adds a new
*consumer* of an existing feed, not a new trust relationship. An infected LAN machine able to spoof
aircraft-layer's HTTP responses could already feed body-layer false telemetry before this stage;
this stage's worst case from that same attacker is a wrong effector write (e.g. a switch flipped
that shouldn't be) or a stalled sequence — not code execution, not an escape from the registry's
finite `(device, cmd, value)` set (see the `advance()` finding above).

### Other points from the task brief, checked directly

- **Arbitrary device/cmd/arg/value write from a sequence file** — no; only registry-resolved
  `EffectorDef` entries are ever written, and a row naming anything else is dropped at load time.
  See table above.
- **D5 non-fatal posture, path to a raise that kills body-layer** — none found; both loaders
  collect errors by contract, and the one call site is startup-only, before the poll loop exists.
- **New aircraft-layer field, bind address/auth** — `"args"` map is a read-only derived view on an
  existing GET response; `server.py` is untouched; no bind/auth change.
- **New dependency** — none.
- **Secrets/credentials** — none present in this diff.

### Verdict

**APPROVED.** No findings requiring a fix. No finding in this report carries an unfiled
risk-matrix block — the one forward-looking note (`petrovich_says`/say-only-row prompt-injection
re-check) restates `security-stage0`'s own already-filed caveat for a future stage, rather than
raising a new one; there is nothing here to mint an ID for.

### Memory and graph queries run

`python3 .claude/scripts/memory-search.py` for `effector`/`sequence`/`cockpit_switch` terms:
"not indexed yet." Broader `security` search surfaced `project_bl_b66_9k113_effectors_deep_analysis`
(the prior `cockpit_switch`-touching pass this one builds on — its "only registry-resolved writes,
never arbitrary code execution" finding and its settled "no allow-list needed" user override are
both still true and unchanged here) and confirmed no other prior memory on this TOML/markdown
loader shape. `.claude/scripts/gq.sh "effector sequence files security"` returned the BL-B90
community cluster (`tuning.py`, the concept doc, the acceptance sortie note) — nothing contradicts
the direct code reading above.

No new memory file written from this pass: the one reusable lesson (parsed free text only reaching
spoken/brain-facing surfaces once a later stage wires it in, so the load-bearing check is "grep for
a reader, not just for a writer") is already captured in `security-stage0.md`'s own forward-looking
note; a second occurrence of that exact shape would be the point to promote it into a general
`security` memory.
