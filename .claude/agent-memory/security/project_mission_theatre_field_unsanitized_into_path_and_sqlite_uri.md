---
name: mission-theatre-field-unsanitized-into-path-and-sqlite-uri
description: multi-theatre-afghanistan Stage 5 fed mission["theatre"] (untrusted .miz content, zero validation anywhere in mission-interpreter) straight into a pathlib join and (transitively) a sqlite3 URI string -- demonstrated both pathlib absolute/UNC override and SQLite URI mode=ro override via query-string injection
type: project
---

`body-layer/src/logger.py`'s Stage 5 (`multi-theatre-afghanistan` plan) derives
`world_model_db = args.world_model_dir / f"{theatre.lower()}-full.sqlite"` where `theatre` comes
from `mission_data.theatre.value` — a string that originates at `mission-interpreter/src/
miz/reader.py:123`'s `theatre = str(mission.get("theatre", theatre_text)) or theatre_text`, the
**raw, unvalidated `.miz` Lua-table field**. Confirmed by reading the whole chain
(`miz/reader.py` → `world_enrich/enrich.py` → `schema/build.py`'s `Tagged(value=enriched.theatre,
epistemic_status="FACT", ...)` → body-layer's `_parse_theatre`, which validates `str`-ness only,
never content): no validation against a known theatre name or safe charset exists anywhere in
this chain.

**Why: Demonstrated, not theoretical.** Two confirmed exploits in this worktree's venv:
1. `pathlib`'s `/` operator discards the left operand entirely when the right operand looks
   absolute (POSIX leading `/`) or drive/UNC-rooted (Windows `C:/...`, `//host/share/...`) — a
   `theatre` value of `"/etc/passwd"` or `"//attacker-host/share/x"` makes `--world-model-dir` be
   silently ignored. The UNC form is the serious one on this project's actual Windows deployment
   target (AGENTS.md cross-machine workflow) — it's a forced-SMB-authentication / NTLM-leak vector
   triggered purely by loading a mission file.
2. The pre-existing (not touched by this diff, but newly fed attacker input by it)
   `open_world_model()` in `perception/geometry.py` builds a SQLite URI by plain string
   interpolation: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`. A `theatre` value
   containing a bare `?` truncates the filename there (SQLite's own URI query-string parsing) and
   lets an injected `mode=rwc` **override** the code's own trailing `?mode=ro` — reproduced live:
   `sqlite3.connect` created a brand-new empty file at the attacker-truncated path in
   read-write-create mode, defeating the read-only contract the body-layer/world-model seam
   depends on.

**How to apply:** Any time a field sourced from an externally-authored artifact (a `.miz`, a
mission-understanding compact JSON derived from one, anything upstream of mission-interpreter)
flows into a filesystem path or a `sqlite3` URI string anywhere in body-layer or world-model,
check for exactly this pattern before approving: (a) is the string validated against a known-good
set/charset before being used structurally, and (b) if it reaches `open_world_model`-style code,
is the URI built safely (ideally not by f-string interpolation at all — `urllib.parse.quote()` the
path component, or avoid `uri=True` entirely when the path isn't already trusted). The correct fix
here is registry-membership validation (`coordinates.projections.THEATRE_PROJECTIONS` keys) right
at the point `theatre` is read out of the mission-understanding artifact, before any path is built
— body-layer already imports world-model's `coordinates` package in-process elsewhere
(`perception/association.py`), so this is the existing coupling, not a new one. See
`plans/multi-theatre-afghanistan/security.md` for the full writeup (verdict: NEEDS FIXES).
