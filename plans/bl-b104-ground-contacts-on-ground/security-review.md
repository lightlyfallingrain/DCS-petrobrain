## Security Deep Analysis: bl-b104-ground-contacts-on-ground

Security, 2026-10-30. Branch `feature/bl-b104-ground-contacts-on-ground`, HEAD fast-forwarded
cleanly from `54633ef8` to the expected tip `0c2a1792` (strict ancestor, clean tree before and
after). Deep analysis for the batch (Stages 1-5, 7, 8), after Reviewer's APPROVED. Diff:
`git diff main...HEAD`. Inputs: `plan.md`, `implementation.md`, `review.md`.

Scope, per this role's own remit: computer/network security only — arbitrary code execution,
access to the computer, what a LAN port scanner reaches, LLM prompt injection, dependency/
framework risk, secrets. Player-facing correctness (classification accuracy, the E5 fold, scenario
scope) is Reviewer's territory and was already resolved there (two Required Fixes, both
independently reconfirmed, verdict APPROVED) — not re-litigated here.

### Dependency Status

No dependency change. Both touched subprojects remain stdlib-only (aircraft-layer) / `pyproj`
transitive-only (body-layer, via the pre-existing world-model seam) — confirmed by reading
`implementation.md`'s own Checks sections and `git diff main...HEAD -- '**/pyproject.toml'`
(no hits). Nothing to CVE-check.

### Attack-surface review

**Lua side (`Export.lua`, `petrobrain-line-of-sight-hook.lua`).** Both changes are additive reads
of trusted DCS engine state (`obj.Type.level1`/`.level2`, one more `pcall`'d `land.getHeight`),
encoded the same way every existing field is, with `nil`/`""` on failure and never a fabricated
value. No `eval`/`loadstring`/`dostring` touched by this diff, no new write path, no new listener.
Clean.

**Python schema parsing (`aircraft-layer/src/schema/world_objects.py`,
`aircraft-layer/src/schema/line_of_sight.py`).** Both add type-checked optional fields
(`category`/`subcategory`/`agl_m`) with the project's established tri-state discipline
(absent/`null` → `None`, never a guessed value) and both raise their own typed
`*ParseError` for a wrong JSON type. `line_of_sight.py`'s new `agl_m` path is the safer of the
two: `float(agl_raw) if isinstance(agl_raw, int | float) else None`, which never raises (not even
on NaN/Infinity — `float()` of an existing float never throws), and the one place `agl_m` is
later compared (`domain.surface_domain`'s `agl_m <= HELI_SURFACE_AGL_MAX_M`) is NaN-safe by
construction (`NaN <= x` is `False`), which resolves a helicopter to air — the correct, documented
unknown-stays-air fallback, not a crash.

### Required Fixes

**Finding 1 (new, introduced by this feature): `category`/`subcategory` conversion is not
NaN/Infinity-safe, at both the parse site this feature added and at the LAN-HTTP boundary into
body-layer, where it is reachable without a live DCS at all.**

- `aircraft-layer/src/schema/world_objects.py`'s new `_optional_int` type-checks `raw` (rejects
  `bool`, rejects non-`int|float`) but then calls `int(raw)` unconditionally. Reproduced directly
  against the committed code:

  ```
  $ python3 -c "
  import sys; sys.path.insert(0, 'aircraft-layer/src')
  from schema.world_objects import WorldObjectSample
  data = {'id':1,'type':'x','coalition':'blue','lat':0.0,'lon':0.0,'alt_m':0.0,
          'heading_true_rad':0.0,'is_ownship':False,'unit_name':None,
          'category': float('nan'), 'subcategory': None}
  WorldObjectSample.from_dict(data)
  "
  CRASHED: ValueError cannot convert float NaN to integer
  ```

  `int(float('inf'))` raises `OverflowError` the same way. Neither is `WorldObjectParseError`, so
  neither is caught by this feature's own `except WorldObjectParseError` — it propagates out of
  `_handle_line` through `_handle_connection`'s read loop in `aircraft-layer/src/collector/server.py`,
  past `serve_forever`'s `except OSError` (wrong exception type), and would kill that server's
  accept loop entirely. On the collector side this is reached only from the loopback
  (`127.0.0.1`) `Export.lua` socket — DCS's own `Type.level1`/`.level2` values are a small,
  trusted enum (1-6), so this path is not realistically reachable from the stated threat model
  (malicious dependency / infected LAN host) without DCS itself misbehaving. Noted for
  completeness, not the operative risk.

- **The operative risk is the same pattern, unguarded, at the actual LAN boundary.**
  `body-layer/src/perception/association.py`'s `WorldObjectCandidate.from_dict` (this feature's
  new lines, ~274-276) does:

  ```python
  is_surface=surface_domain(
      None if category_raw is None else int(category_raw),
      None if subcategory_raw is None else int(subcategory_raw),
      agl_m,
  )
  ```

  with `category_raw = data.get("category")` straight off the raw dict decoded from
  `GET /world_objects/latest`'s HTTP response body — `aircraft-layer/src/api/server.py`'s
  `TelemetryAPIServer` binds `0.0.0.0` (LAN-facing by design, confirmed:
  `DEFAULT_HOST = "0.0.0.0"` with the comment "LAN-facing by design, unlike
  `collector.server.DEFAULT_HOST`"), and Python's `json.loads` accepts the non-standard `NaN`/
  `Infinity`/`-Infinity` literals by default. No `isinstance` check guards this `int()` call at
  all (unlike `line_of_sight.py`'s own `agl_m` parsing two lines away in the same feature, which
  does exactly the right thing) — this is the one of the three new fields that departs from the
  pattern the feature itself establishes elsewhere.

  **Effect, traced through the call chain**: `WorldObjectCandidate.from_dict` is called inside a
  bare list comprehension in `naked_eye_source.py`'s poll method (around line 737), with no
  try/except around it — unlike the two `AircraftLayerError` catches immediately above it in the
  same function for the velocity/LOS joins. A `ValueError`/`OverflowError` here propagates out of
  that whole comprehension, so **no candidate from this poll is processed at all** (the entire
  `all_candidates` list construction fails, not just the one bad object). This is caught by
  `body.py`'s poll-cycle-level `except Exception as exc:` (the "deliberately bare-ish... a dead
  collector is not a defect" handler around line 4221) — so it does **not** crash the whole
  process; the poll loop keeps running — but it does mean **that poll's naked-eye perception is
  dropped entirely**, logged once as "crew-text poll cycle failed; continuing". If a LAN peer
  serving this endpoint (an infected host that has supplanted or is impersonating the real
  aircraft-layer, or — more mundanely — a stale/mismatched aircraft-layer build with a latent bug
  of its own) returns a `category`/`subcategory` of `NaN`/`Infinity` on every poll, Petrovich's
  naked-eye channel goes effectively blind for as long as that keeps happening, with no distinct
  signal beyond a repeated generic log line — a real, if narrow, availability risk exactly in the
  "what a LAN port scanner reaches" / "crashes that kill a poll loop" category this role's scope
  names, and new: neither `category` nor `subcategory` existed on the wire before this feature.
  No code execution, no file/credential access, no omniscience leak — belief math downstream
  never runs for the affected poll, it simply doesn't get this tick's data.

  - **Probability**: low in this project's actual deployment (single user, LAN-only, no
    adversary currently on the network) — but not zero, and cheap to close, so worth fixing now
    rather than carrying as an accepted risk.
  - **Impact**: low-medium — denial of naked-eye perception for the affected poll(s), self-healing
    once bad data stops, no escalation path to code execution or data exposure.

  - **Required**: guard both conversions the same way `line_of_sight.py`'s own `agl_m` parsing
    already does two lines above in this same diff — check `isinstance(category_raw, int | float)
    and not isinstance(category_raw, bool)` and `math.isfinite(category_raw)` (or equivalently
    wrap in `try: int(...) except (ValueError, OverflowError): category = None`) before calling
    `int()`, in both call sites (`aircraft-layer/src/schema/world_objects.py`'s `_optional_int`
    and `body-layer/src/perception/association.py`'s `from_dict`), treating a non-finite or
    out-of-range value as `None` rather than raising — consistent with this feature's own stated
    discipline ("never fabricated or defaulted to a guessed value") and with the safe pattern it
    already uses for `agl_m`. Add a test case for each (NaN/Infinity on `category`/`subcategory`)
    alongside the existing optional-field tests in `test_world_objects_schema.py` and
    `test_association.py` — neither currently covers this input, confirmed by `grep`.

  Not filed as a backlog item — this blocks DoD and is small enough to fix in the same
  Implementer→Reviewer re-entry loop `AGENTS.md` prescribes for a security change request, not
  deferred.

### No-omniscience fence

Checked: `category`/`subcategory`/`agl_m` never reach a player-facing surface directly — their
only consumer is `perception.domain.surface_domain`, which collapses them to a `bool | None`
domain classification consumed by the same visibility/clustering gates every other candidate
already goes through (confirmed by reading `domain.py` and its callers in `association.py`/
`naked_eye_source.py`). No new field crosses `belief/percept.py`'s boundary; this matches
Reviewer's own read and is not a security-specific concern beyond Finding 1 above.

### Verdict

**NEEDS FIXES**

One Required Fix (Finding 1): the new `category`/`subcategory` integer conversion at the
LAN-HTTP boundary into body-layer (`association.py`) and, defensively, at the aircraft-layer
ingest parser (`world_objects.py`) must reject non-finite values instead of raising an uncaught
`ValueError`/`OverflowError`. Routes to Implementer → Reviewer (review of the fix) → Security
re-check (quick, scoped to the two touched functions) → DoD, per `AGENTS.md`'s change-request
loop. Everything else in this batch — the Lua wiring, the dependency posture, the no-omniscience
boundary, the `agl_m` parsing path, the LAN API's binding posture (unchanged by this feature) — is
clean.

### Re-check (Reviewer, 2026-10-30, commit `bff85e99`)

Finding 1 is **closed**. Both call sites named above (`aircraft-layer/src/schema/world_objects.py`
`_optional_int`, `body-layer/src/perception/association.py` `WorldObjectCandidate.from_dict` via
the new `_finite_int`) now guard with `math.isfinite()` before `int()`, exactly as required.
Re-ran the original repro from this finding against the fixed code — `WorldObjectSample.from_dict`
with `category: float('nan')` now returns `category=None` instead of raising. Confirmed the four
new tests actually exercise the fix by reverting each guard in turn and re-running: all four go
red with the predicted `ValueError`/`OverflowError` (mutation-tested, not just read). No new
boundary issue introduced — the body-layer side's broader non-numeric/bool absorption at
`_finite_int` is scoped to a site that had no prior type guard at all and matches
`surface_domain`'s existing unknown-stays-`None` contract, not a new gap. Full detail and the
mechanical checks (both subprojects, fresh venvs, all pass) in `review.md`'s "2026-10-30 —
Security-fix round" section. Verdict: **APPROVED**, clears to DoD.
