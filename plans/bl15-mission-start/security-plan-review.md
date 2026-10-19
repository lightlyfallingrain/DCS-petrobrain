## Security Plan Review: bl15-mission-start (BL-15 Stage 1)

Scope reviewed: the new Hook→collector→poll mission-start signal channel, the belief/mission-memory
reset mechanism, and Stage 3's theatre-string-driven world-model store switching. Stage 2 (Mission
Interpreter dispatch) is out of scope — not planned here.

Calibrated per root `CLAUDE.md` scope: single-player, LAN-only, single user. The relevant trust
boundary throughout this subsystem is "any process on the same machine," not "any network peer" or
"an adversarial mission author with no local access" — every existing inbound/outbound channel in
this stack (F10 commands, text overlay, audio playback, LAN telemetry API) already accepts that
boundary with no authentication, and this plan does not widen it.

### Dependencies Checked

No new dependency. `/extract-plan-deps` found no dependency statement in the plan (nothing to
check — the plan's own prose has no "dependenc/pip install/pyproject" hits), and the Affected
Modules section uses only stdlib already present in both subprojects (`socket`/`json` in
aircraft-layer, `sqlite3`/`argparse` already in body-layer's `logger.py`). Confirmed by reading the
Affected Modules list directly — nothing there names a third-party package.

### Design Findings

- **New loopback-UDP Hook→collector channel (mission-start-hook → `MissionStartCache`) — LOW —
  matches the existing, already-accepted `F10CommandReceiver` pattern.** Read
  `aircraft-layer/src/collector/f10_command_receiver.py` as the precedent: binds `127.0.0.1`
  explicitly, rejects non-JSON/non-dict/malformed payloads before anything is enqueued. The plan
  states the new Hook script sends "over loopback UDP" and the cache/listener "mirror[s]
  `f10_command_receiver.py`'s receiver shape" — same trust boundary, same posture. No action
  required beyond what the plan already specifies; the Implementer should carry over the same
  reject-malformed-payload discipline `F10CommandEvent.from_dict`/`F10CommandParseError` use, not
  just "same shape" by analogy — call this out explicitly at Reviewer/deep-analysis time rather
  than assuming it from the plan's wording alone.

- **Forged mission-start datagram → belief/mission-memory wipe — see Risk Communication below.**
  Any local process that can reach `127.0.0.1:<new-port>` can send a well-formed
  `{"sequence": N, "theatre": ...}` datagram and force `_reset_mission_state` to run, discarding
  live belief, tasks, and mission memory. This is a materially different consequence than the
  existing F10/audio/text channels being locally spoofable (those act a command or play a sound;
  this destroys state), so it does not simply inherit the existing channels' acceptance by
  analogy — it gets its own risk entry below rather than being waved through on precedent alone.

- **`theatre` string → filesystem path → `sqlite3` URI (Stage 3) — the known vulnerability class,
  correctly reused from the approved fix, not reintroduced.** Agent memory
  (`project_mission_theatre_field_unsanitized_into_path_and_sqlite_uri.md`) records that this exact
  pattern — an externally-sourced `theatre` string feeding
  `world_model_dir / f"{theatre.lower()}-full.sqlite"` and, transitively,
  `perception/geometry.py:65`'s `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` — was
  demonstrated exploitable (pathlib absolute/UNC override; SQLite URI `mode=rwc` override via a
  `?` in the string) during `multi-theatre-afghanistan`, and fixed by a `THEATRE_PROJECTIONS`
  registry-membership check placed **before** the path is built
  (`body-layer/src/logger.py:3013-3019`, confirmed still present and still ordered correctly on
  this branch — `open_world_model` itself, `perception/geometry.py:56-65`, is *still* the
  unsafe-f-string version; it is safe only because every caller validates membership first).
  This plan's source for `theatre` is now a DCS Hook/mission-scripting read instead of a
  `.miz`-derived mission-understanding artifact, but it is exactly as untrusted — a mission
  author (or a forged datagram per the point above) controls the string either way. **The plan
  explicitly commits to the same mitigation**: "run the exact two guards `main()` already runs at
  startup — `theatre in THEATRE_PROJECTIONS` ... and the built-region mismatch guard ... before
  opening anything." That is the correct fix, reused rather than reinvented, and `THEATRE_PROJECTIONS`'s
  keys are a small fixed set of plain theatre names (`Syria`, `Afghanistan`, ...) with no path
  metacharacters, so membership is a sufficient guard as long as the order holds.
  **Required verification at Mode 2 (deep analysis), not a plan rejection now**: confirm the
  implemented Stage 3 runtime-switch code path performs the `THEATRE_PROJECTIONS` membership check
  *before* constructing `world_model_dir / f"{theatre.lower()}-full.sqlite"` and before calling
  `open_world_model` on it — the same ordering bug class (check-after-use) is exactly what made the
  original finding exploitable, and a runtime code path added later is a second place that ordering
  has to be gotten right independently of `main()`'s already-correct one.

- **`net.dostring_in` usage — CLEAN.** The new Hook script's only new bridge call is the
  hardcoded expression `"return env.mission.theatre"` (per the investigator's note and this plan's
  own text), not a string built by interpolating any mission-derived value into the *code* being
  executed. Matches this project's standing "only hard-coded strings ever cross `net.dostring_in`"
  posture (`aircraft-layer/CLAUDE.md`, `petrobrain-f10-commands-hook.lua` precedent). No injection
  surface here.

- **`GET /mission_start/latest` — CLEAN, no new risk class.** LAN-exposed, unauthenticated, same as
  every other `/latest` endpoint on this API (`/telemetry/latest`, `/world_objects/latest`, etc.) —
  already an accepted posture for this project's scope, not something this plan changes.

- **Stage 3's degrade-on-failure path (store missing / fails mismatch guard → keep old
  theatre/store, log loudly, never crash, never silently misapply) — CLEAN, matches this
  project's established fail-closed-but-continue pattern** (the same posture already approved for
  other guarded stores — see `project_store_writer_fail_closed_geometry_guard.md` and
  `project_terrain_cache_resumable_fail_closed_approved.md` in agent memory). No concern.

### Risk Communication

**Finding:** A forged (or merely locally-spoofed) UDP datagram on the new mission-start port causes
a full belief/mission-memory reset mid-flight, exactly as if a genuine `onSimulationStart` had
fired.
**Location:** the new Hook→collector loopback channel (`aircraft-layer/src/collector/` — the new
`MissionStartCache`/listener) and `body-layer`'s `_check_for_new_mission`/`_reset_mission_state`.
**Probability:** low — requires a process already running on the same machine as the DCS/collector
box, which in this project's actual deployment (single user, their own LAN) means the player's own
machine. No remote network exposure (loopback-bound).
**Impact:** medium in isolation (silently destroys live belief/mission-memory, which the pilot would
notice as Petrovich "forgetting" everything mid-sortie) but low in this project's actual threat
model — the attacker capability required ("run arbitrary code on your own flight-sim PC") already
grants far more direct ways to disrupt the session, and single-player/LAN-only scope means there is
no other party who could exploit this. Also self-healing: belief/mission memory rebuilds from the
next poll onward, so the failure mode is "lost history," not "wrong/dangerous state."
**Recommended action:** accept as-is for this milestone, matching the same acceptance already
implicitly given to the F10-command, text-overlay, and audio-playback channels (all equally
loopback-spoofable, by the same local-attacker standard). Do not add authentication or a
shared-secret handshake to a loopback single-user channel — that would be effort disproportionate
to a threat model this project has already decided not to defend against elsewhere.

Options:
  (A) Ignore — document acceptance of this risk (recommended, consistent with existing channels)
  (B) Add to todo.md — fix in a future session (e.g. source-port/PID pinning) if the threat model
      ever changes (multiplayer, shared machine)
  (C) Fix now — add sender verification before this ships
  (D) Stop — do not proceed until resolved

### Verdict

APPROVED

No new dependency, no unpatched CVE, no high-risk design pattern introduced without justification.
The one real injection-class risk this plan touches (`theatre` → path/SQLite URI) is not a new
hazard this plan creates — it is the already-diagnosed, already-fixed hazard from
`multi-theatre-afghanistan`, and the plan explicitly commits to reusing that exact fix rather than
building a parallel, unvalidated path. The one genuinely new risk (forged local datagram triggering
a belief wipe) is low-probability/self-healing under this project's single-user/LAN-only scope and
is surfaced above for the user's explicit accept/defer/fix call, per the Risk Communication format,
rather than silently waved through.

**Carried into Mode 2 (deep analysis, after Reviewer):** verify the implemented Stage 3 runtime
theatre-switch path performs the `THEATRE_PROJECTIONS` membership check strictly before building
the candidate store path and before calling `open_world_model`, and that the new aircraft-layer
schema module (`schema/mission_start.py`) rejects malformed/wrongly-typed payloads before
enqueueing, mirroring `F10CommandEvent.from_dict`/`F10CommandParseError` rather than merely
resembling its shape.
