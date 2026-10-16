# Security Audit: mission-interpreter (whole subproject)

Date: 2026-10-16. Scope: `[[X-B9]]`'s remaining half (user, 2026-09-25) — a survey for real
exposure in a single-user, LAN-only, offline tool, not a hardening audit against a remote
attacker. `mission-interpreter`'s own job is parsing files it did not write, which is why it gets
the full-subproject pass `world-model/research/2026-10-05-security-audit.md` already got.

Base: `main` @ `8c30148a` (fast-forwarded cleanly from the worktree's stale `origin/main` base;
tree was clean, no divergence).

## What was read

`mission-interpreter/CLAUDE.md`, `plans/mission-interpreter/plan.md`,
`mission-interpreter/ROADMAP/mission-interpreter-roadmap.md`, `todo/backlog/X-B9.md`,
`todo/backlog/X-B8.md`, and all production source under `mission-interpreter/src/` — `miz/`
(reader, tree, dictionary), `_vendor/dcs_lua/` (vendored Lua parser), `filter/` (crew_available,
threat_signals), `world_enrich/` (world_model_client, enrich, schema), `synth/` (ollama_client,
prompts), `player_intent/main.py`, `runtime/compile.py`, plus `body-layer/src/belief/
mission_phase.py` (the consumer side of the MI-6 artifact crossing into the runtime). Checked the
knowledge graph (`gq.sh "trigger zone hidden author-only knowledge"`) and agent memory
(`memory-search.py`) before concluding anything was undecided — no record of the one open question
below (Finding 3) being settled either way.

## Confirmed clean (no finding)

- **No zip-slip / path traversal.** `miz/reader.py`'s `_read_zip_members` never calls
  `ZipFile.extractall`/`.extract()` or writes any zip-member content to the filesystem.
  `mission`/`l10n/DEFAULT/dictionary`/`theatre` are read by fixed member name via
  `archive.read(name)` straight into memory; kneeboard images are passed through as **zip-member
  path strings only** (`reader.py:106-112`), never read as bytes, never used to construct a
  filesystem path. This fully matches the module docstring's claim.
- **No SSRF / request-injection in either HTTP seam.** `WorldModelClient`/`OllamaClient`
  (`world_enrich/world_model_client.py`, `synth/ollama_client.py`) both hit fixed, code- or
  CLI-arg-supplied `base_url`s (`127.0.0.1:7792`/`127.0.0.1:11434` by default) — never a URL or
  host derived from mission content. Query parameters go through `urllib.parse.urlencode`, so a
  crafted place name or briefing string cannot break out of the query string.
- **No `subprocess`/`os.system`/`eval`/`exec`/`pickle`/`yaml.load` anywhere in this subproject's
  own code** (checked across `src/`, excluding the vendored parser, which was also read in full
  and contains none either).
- **The coordinate-leak boundary holds on direct code reading.** `filter/threat_signals.py`
  derives `ThreatSignal(kind, x, z)` from exactly the four author-only markers, matching
  `crew_available.py`'s partition exactly (`_is_author_only` mirrors `_is_crew_available`'s
  negation). `world_enrich/enrich.py:141-158`'s `enrich_threat_signals` resolves that raw
  coordinate through `WorldModelClient.get_describe_position` into a `WorldRef` and the resulting
  `EnrichedThreatSignal` dataclass (`world_enrich/schema.py`) has **no x/z field at all** — the
  raw coordinate cannot be carried further even by accident. `synth/prompts.py`'s
  `_threat_signal_line`/`_place_name` read only `WorldRef.name_matches[0]["name"]` or
  `WorldRef.position["nearest_settlement"]["name"]`, never any numeric field. This matches the
  documented invariant and its regression test (`test_synth_synthesize.py`) exactly as claimed.
- **`crew_available.py`'s group-hiding is structural, not a filter that can be bypassed by an
  unanticipated input shape.** `CrewAvailableMission` has no raw-passthrough field
  (`RawMission.raw`/`.trig_raw` are simply absent from its shape), so there is no back door for a
  hidden group to re-enter even if `_is_crew_available` had a bug — the worst a bug there could do
  is wrongly keep or wrongly drop a *visible* group's presence, not resurrect a hidden one via a
  catch-all field. `trigrules`/`trig_raw` are likewise never surfaced on `CrewAvailableMission`.
- **Ollama client fails closed rather than silently triggering a multi-GB auto-pull**
  (`_ensure_model_pulled`), and distinguishes daemon-unreachable from bad-output rather than
  degrading in a way that could mask which. No API keys/secrets anywhere in this subproject.
- **MI-6 artifact consumption (`body-layer/src/belief/mission_phase.py`) fails loudly on
  malformed JSON** rather than guessing — every field is type-checked before use, and the
  mismatch guard described in the task brief (`TaggedTheatre`/`load_mission_understanding`'s
  required-`theatre`-field check) is real and matches what the brief said to expect.

## Findings

### 1. [Confirmed, unresolved question — not yet a known vulnerability] `TriggerZone.hidden` is parsed but never consulted by the author-only-knowledge filter

**Where:** `mission-interpreter/src/filter/crew_available.py:42-61` (`filter_crew_available`),
cross-referenced against `mission-interpreter/src/miz/tree.py:120-141` (`TriggerZone`).

`filter_crew_available`'s own docstring reasons explicitly about trigger zones and author-only
knowledge:

> "Trigger zones... are passed through unfiltered — a zone's geometry alone does not reveal a
> specific unit's existence... If a future mission is found where a zone's `name` itself leaks
> something (e.g. `"Ambush-Zone-3"`), that is a new, separate finding to handle explicitly — not
> assumed away here."

That reasoning never mentions `TriggerZone.hidden` — a field the parser deliberately typed
(`reader.py:271`, `node.get("hidden", False)`) and confirmed present and in real use in the one
real sample mission this subproject validated against
(`research/2026-09-12-miz-validation-against-real-sample.md` line 20: `"hidden"` is one of the
zone's real fields). `filter_crew_available` passes `mission.trigger_zones` through **completely
unfiltered regardless of each zone's own `hidden` value** (`crew_available.py:58`,
`trigger_zones=mission.trigger_zones`) — the field is read off every zone but checked by nothing.

**Why this is a real question, not a false positive:** this is exactly the "MI-1.5 is a
security-shaped boundary — what gets through on an input shape it did not anticipate" case the
task asked to look for. `Group.hidden` and `TriggerZone.hidden` are the same field name on two
different DCS object types. One is a hard author-only-knowledge marker this subproject's central
invariant depends on (`Group.hidden` → group dropped entirely). The other, identically-named
field on zones is currently inert. Two readings are both plausible and neither has been checked
against ED/Hoggit/pydcs source:

- **Benign reading:** DCS's zone `hidden` is purely an editor-canvas display toggle (whether the
  zone outline is drawn in the Mission Editor), carrying no author-secrecy meaning — in which case
  today's "pass zones through unfiltered" is correct as written and this finding closes as a
  false positive once confirmed.
- **Concerning reading:** it marks a zone the author deliberately hid from players (e.g. an
  ambush-trigger zone's geometry), in which case its current pass-through is a live gap in the
  one boundary this subproject exists to keep closed — a zone's geometry near the player's route,
  even without a name, narrows down "something is scripted to happen around here" in exactly the
  way MI-1.5 was built to prevent.

**Action:** this needs an `investigator` pass against pydcs source / Hoggit / the real sample's
zone-editing behavior before it can be marked resolved either way — not a code fix from this
audit, and not something to guess at. Recommend filing as a backlog item rather than blocking
anything in flight.

**Severity if the concerning reading holds:** low-moderate. Single-user/offline bounds the blast
radius (there is no other crew member or opponent this could be withheld from — it would only
matter if a captured community mission's hidden zones somehow make their way into anything spoken
to the player), but it is squarely inside the one invariant this subproject is contracted to
maintain, so it is worth settling rather than leaving as an accidental gap.

### 2. [Confirmed, low severity] No bound on Lua-table nesting depth — malformed/hostile `.miz` crashes with an unhandled `RecursionError`, not a clean `MizParseError`

**Where:** `mission-interpreter/src/_vendor/dcs_lua/parse.py`'s `object()`/`_object()` recurse
into `self.parse()` for every nested value with no depth limit (confirmed by reading the whole
421-line module); `mission-interpreter/src/miz/dictionary.py:25-53`'s `resolve_dict_keys` recurses
over the entire parsed tree the same way. `miz/reader.py:70-79` only catches `SyntaxError` around
`loads(...)` — a `RecursionError` from either path propagates uncaught out of `read_miz`.

A `.miz` whose `mission` Lua table nests tables deeply enough (not actually malicious-looking Lua,
just deeply bracketed — real missions don't do this, but nothing requires an input file to look
like a real mission) crashes the whole process with a bare Python traceback instead of the
subproject's own `MizParseError`. This is a real gap in "whatever the Lua parser does on malformed
input" — the exact class the task brief called out — but the vendored parser is explicitly treated
as an opaque third-party dependency this subproject does not edit in place
(`mission-interpreter/CLAUDE.md`'s Decision 1), so the fix belongs in `miz/reader.py`'s own
exception handling (catch `RecursionError` alongside `SyntaxError` and re-raise as
`MizParseError`), not in the vendored module.

**Severity:** low. Single-user, offline, one-shot CLI process — the worst outcome is a crash with
a confusing traceback instead of a clean error message on a malformed input file the user chose to
feed it themselves. No code execution, no data exposure. Worth a cheap fix (one `except` clause)
given how directly it falls inside this audit's stated surface, but not a blocker for anything.

### 3. [Confirmed, low severity] Mixed-type Lua table keys cause an unhandled `TypeError`, not a clean `MizParseError`

**Where:** `mission-interpreter/src/miz/reader.py:163-173` (`_as_ordered_list`):
`sorted(value.keys())` on a dict produced by the vendored parser. If a `group[]`/`units[]`/
`zones[]`-shaped table mixes string and integer keys (a malformed or deliberately crafted `.miz`
can do this trivially — the Lua grammar the vendored parser accepts allows arbitrary
string/integer keys in the same `{[1]=..., ["x"]=...}` object), `sorted()` raises `TypeError:
'<' not supported between instances of 'str' and 'int'`, uncaught by `read_miz`'s `except
SyntaxError` clause — same failure shape and same severity as Finding 2, different trigger.

**Severity:** low, same reasoning as Finding 2. Noting separately because the fix is different
(validate/coerce key types in `_as_ordered_list`, or catch `TypeError` alongside `SyntaxError` and
`RecursionError` in `reader.py`) even though the user-facing effect — an ugly crash instead of a
clean parse error on a bad input file — is the same.

### 4. [Unverified, informational] No size cap on `.miz` zip-member reads

**Where:** `mission-interpreter/src/miz/reader.py:99-105` — `archive.read(_MISSION_MEMBER)`/
`archive.read(_DICTIONARY_MEMBER)` read each named member fully into memory with no size check
against `ZipInfo.file_size` first. A `.miz` with a small compressed `mission`/`l10n/DEFAULT/
dictionary` member that inflates to a very large decompressed size (a classic single-member
"zip bomb") would be read in full before any parsing even starts, which could exhaust memory on a
sufficiently extreme crafted file.

**Severity:** informational given the stated scope. This is a single-user tool operating on files
the user deliberately downloads and feeds to it (the one documented precedent,
`research/samples/Mission 02-Bagram.miz`, is "real third-party campaign content" the user chose
to add) — not a service accepting uploads from anyone else. Not worth engineering effort now;
worth remembering if mission-interpreter is ever pointed at missions sourced less carefully (e.g.
an automated campaign-download pipeline).

## Not found

No hardcoded secrets, no credentials, no dependency with a known CVE introduced by this
subproject (the only third-party code is the vendored, no-further-dependency `dcs_lua` parser —
provenance pinned to a specific upstream commit, `_vendor/dcs_lua/__init__.py`), no command
injection, no deserialization of untrusted data via `pickle`/`eval`/`yaml.load`, no SSRF, and the
author-only-knowledge boundary holds for **groups** exactly as designed and tested. The one open
question (Finding 1) is about an *adjacent* field this subproject happens to also parse, not a
hole in the group-filtering mechanism itself.

## Recommended backlog items

- File Finding 1 (`TriggerZone.hidden` unconsulted) as a backlog item for an `investigator` pass
  against pydcs/Hoggit source on what DCS's zone-level `hidden` flag actually means, before
  deciding whether `crew_available.py` needs to filter on it.
- File Findings 2+3 (uncaught `RecursionError`/`TypeError` on malformed Lua input) as one small
  backlog item: catch both alongside `SyntaxError` in `miz/reader.py:70-79` and re-raise as
  `MizParseError` with a clear message, same posture the module already has for `SyntaxError`.
- Finding 4 (no zip-member size cap) is informational only — not recommended for the backlog at
  current scope; noted here so it isn't rediscovered as new later.
