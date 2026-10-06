# Review — `fix/los-hook-statics` (tip `301e869`)

Reviewed: `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`,
`aircraft-layer/src/schema/line_of_sight.py`, `aircraft-layer/CLAUDE.md`,
`plans/los-hook-statics/implementation.md`, plus the branch's effect on body-layer's
`_resolve_los_by_unit_name` (unchanged, deliberately).

**Live behaviour is not verified by this review and cannot be.** Nothing below asserts the Hook
works in the sim. The verdict covers correctness-by-reading, the mechanical sweeps, and whether the
instrumentation makes one sortie decisive. The acceptance step is a sortie by the pilot on branch
`fix/los-hook-statics`.

---

### Review Summary

The structural claim of the change holds. `considerCandidate(obj, isStatic)` is genuinely one
filter, both populations call it, and a static's wire entry is byte-identically shaped to a unit's —
so body-layer's unchanged `unit_name` join is safe. Three things are better than the implementation
log claims, and three are worse. The three required fixes are all small.

**Verified true:**

- **One filter, no drift.** `considerCandidate` is the sole bubble/wedge/name test for both loops.
  Nothing after the `candidates` append branches on `isStatic`: the entry is
  `c.name .. ":" .. b .. ":" .. t` in one loop over one list, and the wire string carries no
  unit/static discriminator. A static is indistinguishable from a unit on this wire. **Confirmed by
  reading the only two writers of `candidates` and the single `parts` builder**, not by the file
  list.
- **Boundaries preserved exactly.** The old inline filter used `rangeM <= 10000.0` and
  `delta <= fovHalfDeg`; the extracted function uses `if rangeM > 10000.0 then return end` and
  `if delta > fovHalfDeg then return end`. Both inclusive-at-the-boundary, same as before. An
  extraction is the classic place to flip a boundary; this one did not.
- **The counter semantic shift is not merely acceptable — it is what makes `cap_hit` exact.** In the
  old code `getName()` failure or an empty name incremented `unitsInWedge` without appending a
  candidate, so `sightlines_computed < units_in_wedge` conflated "the cap bit" with "a name
  failed". Fetching the name before the counters makes `#candidates == objectsInWedge`
  unconditionally, so the comparison the Hook now logs as `cap_hit` is a pure cap test. Given the
  whole point of the sortie is to decide whether 128 binds, the confounded version would have been
  unusable. The fields are observability-only: the only consumers are `line_of_sight_receiver.py`'s
  log line and the API echo — **no code branches on them** (grepped `units_in_bubble|units_in_wedge`
  across all `*.py`; every non-test hit is a docstring, a log format, or `to_dict`). Keeping the
  names is right.
- **The `isExist`-advisory trade for statics is safe, and more decisively than argued.** The
  implementation log reasons that a dead static's verdict "is simply never joined". Stronger than
  that: body-layer's `_resolve_los_by_unit_name` iterates over **`GET /world_objects/latest`'s own
  object list** and looks each live object's name up in the verdict dict. A verdict for a name not
  in that list is unreachable — it is never consulted, not merely discarded. So there is **no path
  where a dead static's stale position produces a verdict body-layer attaches to a live contact**,
  including a remembered one (contacts receive LOS only via a fresh `Percept`, which requires the
  object to be in `objects`). The one residual, name collision, is already handled:
  `name_counts[name] > 1` drops to unresolved. Carry the dead Shilka; the cost is a wasted pair of
  engine calls.
- **The splice is not the dangerous class, and the guard test is unaffected — both halves checked
  mechanically.** The guard's regex is anchored on `local SET_LOOK_TEMPLATE = "…"`; re-running it
  against the post-change file extracts exactly the same template and exactly
  `['%d', '%d']`. The new site is a separate statement three lines away and cannot be captured by
  it. `grep 'string\.format'` finds exactly one new real call site (`:303`), two of the other `%d`
  hits being prose in the header. Its argument is `MAX_SIGHTLINES_PER_CALL`, a module-level integer
  literal in this same file, never anything inbound — `%d` can only emit `-?[0-9]+`. Correct to
  splice; correct that the existing guard does not cover it.
- **Nil-safety survived the extraction.** The old loop's `if unit and …` guard is gone, but
  `unit:isExist()` is now inside a `pcall`, so a nil unit fails there and is skipped rather than
  erroring. Equivalent.
- **Robustness genuinely added:** an empty-string name is now rejected. Previously it would have
  produced an entry the Python parser rejects with `empty unit_name`, killing the **whole**
  snapshot, not just that object. Defensive rather than observed, but real.

---

### Required Fixes

- **No `unit_enum_failures` counter, and the new `pcall`s turned a logged failure into silence.**
  This is the one asymmetry that can make the sortie read as clean when it is not.
  `coalition.getStaticObjects` failing on a side increments `staticEnumFailures`, which is logged —
  and the implementation log is right that this counter is the point of that line. The unit side now
  has the identical failure mode with **no counter and no log line**: `pcall(coalition.getGroups, coa)`
  returning `okG == false` silently yields fewer units, and so do `grp:getUnits()`, `unit:isExist()`
  and `unit:getID()`. *Before* this change those were unprotected, so such an error propagated out of
  the chunk, `net.dostring_in` reported failure, and `pollAndSend` logged
  `LOS poll failed: ok=… result=…`. The failure was loud. It is now invisible, and it biases exactly
  the number the sortie exists to measure — a side whose units vanish *understates* candidate count
  and can mask the cap. Add a `unitEnumFailures` counter incremented in the `else` of the per-side
  `getGroups` `pcall` (the per-group/per-unit ones may fold into it or be skipped) and emit it on the
  same `env.info` line. One counter, mirroring one that already exists.

- **The implementation log's justification for those `pcall`s is false, and should not stand in the
  record.** It states *"an error inside `onSimulationFrame` takes the mission with it"*. The chunk
  does not run in `onSimulationFrame` — it runs in the **mission-scripting state** via
  `net.dostring_in`, behind two layers of `pcall` (`dostring`'s own `pcall(net.dostring_in, …)` and
  `onSimulationFrame`'s `pcall(pollAndSend)`). A chunk error could never have taken the mission
  down; it produced a log line. The `pcall`s are still defensible — graceful degradation to "fewer
  candidates" instead of "no result at all", which is the behaviour the task asked me to confirm and
  which they do deliver — but the stated reason is wrong, and it is the reason a reader would use to
  justify the next unprotected call becoming a silent one. Correct the sentence; keep the change.

- **`PLAYER_BUBBLE_RADIUS_M` is now a declared-and-never-read local.** `grep` finds it at its
  declaration (`:235`) and in two comments; **zero code reads it**. The actual bound is the re-typed
  `10000.0` inside `considerCandidate`. This is pre-existing and the implementer flagged rather than
  hid it — but it is the same drift a performance pass already flagged for the cap, in this same
  file, and this branch just built the mechanism that fixes it and used it once, three lines above
  `LOS_CODE`'s body. A constant that reads as governing the bubble and governs nothing will be
  edited by someone who believes they have changed the bubble. Either splice it (one line, same
  shape as the cap) or delete the dead local. Minimal form is fine; leaving both is not.

---

### Optional Refinements

- **`HOUR_DEFAULT`/`FOV_DEFAULT_DEG` versus the chunk's `or 0`/`or 45`: leave them, and say why.**
  Unlike `PLAYER_BUBBLE_RADIUS_M` these are **live** — read at `:565`/`:566` as `_safeClampInt`
  fallbacks for a *bad inbound value*. The chunk's `or 0`/`or 45` cover a different situation: *no
  command has arrived yet this mission*. The two are equal today by coincidence, not by
  construction, and splicing would couple them so that retuning the "bad input" fallback silently
  moves the "no directive yet" wedge. Ruling: not a required fix, and arguably should stay
  duplicated. Worth one sentence in the header so the next reader does not "fix" it.
- **Ownship can still be admitted, on one path, and the branch overstates this.** The Lua comment and
  the implementation log both say a failed `getID()` "cannot silently let ownship through". It can —
  if `player:getID()` **and** `player:getName()` both fail, `playerId` and `playerName` are `nil`,
  the unit loop's `(not okI) or playerId == nil or …` admits, and `considerCandidate`'s
  `playerName ~= nil and …` test is a no-op. Both `pcall`s failing on an object whose `getPosition()`
  already succeeded is close to impossible, and the blast radius is small (an ownship verdict keyed
  by the player's own name, which body-layer's object-driven join almost certainly never consults).
  Returning `ERR|` would be worse than the hole — it drops the whole poll for every object. So:
  soften the claim to "unless both fail", and if you want the property to be observable, log once
  when both resolutions are `nil`. Not a blocker.
- **The cap instrumentation is sufficient to answer the question — with one cheap addition worth
  considering.** `cap_hit` plus the dedicated `LOS cap bit:` line (with `dropped=` count) answers
  *"is 128 binding"* by grep; `bridge_call_ms` on every poll next to
  `objects_in_bubble/objects_in_wedge/sightlines_computed` answers *"what does it cost"* and lets
  cost be regressed against candidate count; `statics_in_bubble`/`statics_in_wedge`/
  `static_enum_failures` prove the enumeration ran rather than silently no-op'd. The `?` fallback on
  a `string.match` miss is the right call — an unknown reported as unknown. What is missing is the
  **range of the farthest surviving candidate** when the cap binds, which is what converts
  "dropped 41" into "lost everything beyond N km". The dropped count alone is enough to retune the
  cap, so this does not cost a flight; it would just make the retune a decision rather than a guess.
  Note also that `candidates=` on the `env.info` line is now provably identical to
  `objects_in_wedge=` (see above) — harmless, but it is a redundant field, not a cross-check.
- **The new `CLAUDE.md` bullet is accurate and in scope; one ordering nit.** Adding it was right —
  the Hook was **absent**, not stale, unlike every sibling, and an undocumented shipped script is
  worse than a slightly-over-brief one. The bullet's `10 km bubble → wedge → not ownship` arrow puts
  ownship last; in code the ownship-*name* test is inside the shared filter **before** the wedge, and
  the ownship-*id* test is outside it and units-only. Reorder or drop the third arrow.
- **The `WORKFLOW.md` deploy gap should not block.** It is pre-existing, out of this branch's scope,
  and the information is not lost — the file's own header carries the deploy path and the
  `autoexec.cfg` requirement, and the new `CLAUDE.md` bullet repeats the path. It should become an
  `AC-B<n>` backlog item (this review does not edit `ROADMAP.md`/`BACKLOG.md`/`todo/` per its brief).

---

### Verdict

**APPROVED WITH REQUIRED FIXES** — three, all small: the missing `unit_enum_failures` counter, the
false `pcall` justification in the implementation log, and the dead `PLAYER_BUBBLE_RADIUS_M`. None
of them is a correctness defect in the shipped Lua; the first is the one that could cost a second
flight, which is why it is required rather than optional.

### Review Confidence

Full read of the Lua (both halves, line by line), the Python docstring diff, the `CLAUDE.md` bullet,
and the old enumeration loop for comparison. Mechanically re-verified rather than taken on report:
the `SET_LOOK_TEMPLATE` guard regex against the post-change file, the `string.format` call-site
inventory, the `units_in_*` consumer sweep across all `*.py`, the `PLAYER_BUBBLE_RADIUS_M` read
count, and body-layer's `_resolve_los_by_unit_name` join direction. **Not re-run** (per the
orchestrator's own stated verification): `luac5.1 -p`, the `GETGLOBAL` sweeps, and aircraft-layer's
ruff/mypy/pytest. **Not verifiable from here at all:** every live DCS behaviour — the statics
enumeration actually returning objects, `getStaticObjects` availability, heading convention, and
whether the cap binds.
