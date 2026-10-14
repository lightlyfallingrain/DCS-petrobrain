## Security Deep Analysis: attack-run (BL-14, Stages 1-7)

**Scope.** Whole-feature pass, immediately before DoD, per root `CLAUDE.md`'s once-per-feature
cadence. Addressed `feature/bl14-attack-run` at tip `468c7b3` (confirmed by `git rev-parse HEAD`
after fast-forwarding this worktree from a stale `f25c57c` base — see Handoff). Read
`docs/acceptance/2026-10-14-attack-run-guidance-direction.md` (§18 particularly), `plans/attack-run/
plan.md` (all three amendment passes), `plans/attack-run/implementation.md`, `plans/attack-run/
review.md` (three sections: Stage 1-3, Stage 4-5, Stage 4-5 fix), the full feature diff
(`git diff 59ea38b~1..468c7b3`), and the relevant source directly: `attack_run.py`, `percept.py`,
`contacts.py`, `speech.py`, `naked_eye_source.py`, `clustering.py`, `geometry.py`, `crew_console.py`,
`tasks.py`, `logger.py`, `belief_truth_log.py`, `voice_commands.py`, `command_matcher.py`,
`vocabulary.py`, and the fence test `test_attack_run.py`.

### Dependency Status

No dependency change. The feature is pure in-process Python across `body-layer` and `audio-adapter`
(new slot parsers in `command_matcher.py`/`vocabulary.py`); no new package in either subproject's
`pyproject.toml`.

### The no-omniscience boundary — the five questions this review exists for

**1. Is the fence sound, or has it become a naming convention?** Sound. The literal-text grep fence
(`test_belief_never_references_relative_direction_except_sanctioned_readers`, word-boundary regex)
restricts `relative_direction`/`RelativeDirection` to `percept.py` and `attack_run.py`. I independently
confirmed `Contact.last_percept` carries the whole `Percept` object specifically so no other
`belief/` module ever needs to write the literal field name (`contacts.py:654,724` only ever assigns
`self.last_percept = percept`, never touches `.relative_direction` itself) — this is the
implementer's own documented workaround (agent-memory
`feedback_grep_fence_literal_text_not_runtime_access.md`) and the Stage 1-3 review already
mutation-tested the fence by injecting a real leak into `tools.py` and confirming the exact failure.
I did not re-run that mutation but traced the same code paths and agree with its conclusion. The
fence's one acknowledged weakness — a deliberately obfuscated access via
`getattr(x, "relative" + "_direction")` — is shared by every grep fence in this codebase, including
the pre-existing `derived_world_position` one it mirrors, and is not a new weakness this feature
introduces. I also checked for the *unrealistic* leaks the brief asked about and found none reachable
today: no module reflects over `Percept`'s fields (`dataclasses.fields`/`asdict`), no module prints
or logs `Contact`/`Percept` wholesale (`repr(contact)`, f-string interpolation, `json.dumps` of
either), and `Contact`'s own `@dataclass` default `repr=True` is never invoked anywhere in `src/`
today. **Recommendation, not required:** add `field(repr=False)` to `Contact.last_percept`
(this codebase already uses that pattern elsewhere, e.g. `CrewConsole.silenced`) as defense-in-depth
against a future debug `print(contact)` silently dumping `relative_direction` into a terminal or log
nobody gated.

**2. Does the truth-derived value leak into speech/belief/log beyond what the guidance was admitted
for?** No new leak, and it is the same sanctioned shape the codebase already has. `drain_attack_run`
threads `attack_run_target_contact_id`/`attack_run_tier`/`attack_run_azimuth_deg`/
`attack_run_elevation_deg` through `_print` into `logger._speech_log_sink`, which calls
`BeliefTruthLogWriter.write_speech` — and that writer only exists when `--belief-truth-log` is
explicitly passed (`logger.py`'s `belief_truth_writer` is `None` otherwise). `belief_truth_log.py`'s
own module docstring already declares it "the second module in this codebase deliberately allowed to
hold both ground truth and belief at once" — this feature's tier-1-exact azimuth/elevation is
consistent with that existing, opt-in, debug-only exception, not a new crossing of the no-omniscience
boundary into anything reachable by default or by the player. The separate `--speech-log`
(`SpeechLogWriter`, inbound-transcript recognition log) does **not** carry any attack-run field — I
confirmed `speech_log.py`'s only caller writes recognised-transcript rows, unrelated to
`write_speech`. **Recommendation, not required:** one line on `write_speech`'s
`attack_run_azimuth_deg`/`attack_run_elevation_deg` parameters noting explicitly that tier-1 values
are truth-exact by design (`RELATIVE_DIRECTION_SIGMA_DEG = 0.0`), so a future reader of this
already-sanctioned log does not mistake precision for a bug.

**3. Is `AttackRunState.last_known_target_alt_m` belief-by-another-name?** Confined correctly
(referenced nowhere outside `attack_run.py`), and its indefinite retention is deliberate user
direction, not an implementation choice — §24's *"If LOS broke, we use remembered position... it
does not go silent"* and Decision 17 REVISED's *"the vertical from the remembered relative
height"* both specify exactly this. It never re-enters `Contact`/belief, is reset to the fresh default
only on `engage`/`disengage` (via `AttackRunState()`/`None` in `logger.py:1805/1807`), and tier 1
succeeding always refreshes it regardless of whether that tick speaks (`attack_run.py:416-420`) — so
it is as fresh as the most recent real look, by construction. **One real gap, flagged below as a
risk rather than a defect**, since the direction document settles the behaviour, not a bound on it.

**4. Can tier 2's projection silently pull a truth value in?** No. Traced `_tier2_alignment`
(`attack_run.py:263-321`) end to end: horizontal comes from `contact.position.x/z` (world-anchored
belief), `contact.motion`/`group.heading_deg` (belief), and `contact_growth_rate_mps` (belief, the
shared per-class speed table) — never a DCS-truth read. `ownship.alt_m` is used as the vertical
placeholder only when `last_known_target_alt_m is None`, and in that exact branch
`elevation_deg` is forced to `None` before it reaches the caller (`attack_run.py:318-320`) — the
placeholder participates in the discarded computation, never the spoken one. Confirmed this is a
fail-open, not a fail-silent-wrong: the honest "no elevation word" case, as Decision 4 REVISED
specifies.

**5. `Cluster.centroid_alt_m` — where does it reach?** Confined to the one path the plan describes.
It is the mean of real per-unit altitudes (`clustering.py:368`, new field), consumed only inside
`naked_eye_source.py`'s `relative_direction` branch (`:1010`) — gated on `live_los_clear is True`,
the same bound the datum's own no-omniscience argument depends on. It does **not** reach
`DerivedWorldPosition` (which has no altitude field at all) or change the existing flat-altitude
substitution (`ownship_state.alt_m`) used for `derived_world_position`'s own truth-bearing/range
computation at `:960`. No second channel of real altitude opened into the ordinary world-anchored
reporting path.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `crew_console.py:1908-1913`, `:2126-2131` (`_handle_select_target`/`_handle_engage`) | Re-selecting a different attack-run target while one is already active | **Reachable today, real consequence.** See below. | **Required fix** |
| `clustering.py:362` (`_extent_count`'s `math.floor`) | Pre-existing, untouched by this diff; a NaN `extent_rad`/`unit_rad` would raise `ValueError` the way the forest-occlusion fix addressed for a different function | Pre-existing hazard, not introduced or worsened by `centroid_alt_m` (new field feeds a different, floor-free path — see Q5) | Not a BL-14 finding; note only |
| `belief_truth_log.py` (`write_speech`'s new `attack_run_*` params) | Truth-exact tier-1 azimuth/elevation reaches a debug log | Consistent with that module's own pre-existing sanctioned exception; flag-gated, opt-in | Recommendation only (docstring note) |
| `attack_run.py:189` (`last_known_target_alt_m`) | Unbounded-age memory outside belief's decay rules | Deliberate per user direction (§24); no staleness bound stated anywhere | Flag for the user (risk, not a defect) |
| `tasks.py:196` (`TaskStore.create`) / `tools.py:1094` (`attack_target_task`) | No same-kind-task cancellation on create, mirroring pre-existing `watch_contact_task` | Unbounded `TaskStore` growth under repeated `select target`/`engage`-with-descriptor | Low risk, inherited pattern — see below; fixed as a side effect of the required fix |
| `command_matcher.py`/`vocabulary.py` (`parse_step_count`) | Arbitrary-magnitude digit string parsed via `int(word)` | Python's arbitrary-precision `int` and the `len(scored) < count` early-exit (`crew_console.py:2086`) before any indexing make this safe — no crash, no resource cost tied to the magnitude | None — confirmed safe |
| `geometry.py` (`body_relative_direction`/`alignment_direction`/`signed_angular_delta_deg`) | New geometry never calls `math.floor`/`int` on a value that could be NaN/inf | The forest-occlusion crash class (`math.floor(nan)` → `ValueError`) does not reproduce anywhere in this feature's new code | None — confirmed safe |
| `logger.py:1757-1806` (poll loop) | `drain_attack_run` runs inside the existing broad `except Exception` | An exception inside tier-1/tier-2 derivation is caught, logged (`logger.exception`), and the poll loop continues — not a silent daemon-thread death | None — confirmed safe |
| `crew_console.py` (`_print`/`silenced`), `voice_commands.py` (`CANCEL_TOKENS`) | `silence`/`stop_talking` and `drop_target`/`disengage`'s `ACT_FLOOR_CANCEL` (0.80) | Guidance routes through the same `_print` → `silenced` gate as every other output (§16's "no exemption" holds by construction); the two destructive commands correctly joined the higher-floor misfire-protection set | None — confirmed correct |

#### Required fix in detail — stale target silently remains "the" active one

`_handle_select_target` and `_handle_engage`'s descriptor branch both call `tools.attack_target_task`
unconditionally, which calls `TaskStore.create` — which never cancels or supersedes an existing
`attack_target` task. `TaskStore.tasks` is insertion-ordered
(`tasks.py:190-194`, "Every task, insertion order"), and every reader of "the current attack-run
target" — `_active_attack_target_task` (`crew_console.py:1952-1961`), used by `drain_attack_run`,
`_handle_step`, `_handle_engage`'s bare form, and `drain_events`'s `_WATCHED_ONLY_KINDS` suppression
— resolves it via `next(task for task in self.tasks.tasks if task.kind == "attack_target" and
task.status != "cancelled")`, i.e. the **oldest** still-active one, not the most recently selected.

**Reachable today, by ordinary voice commands, with no malicious intent required:**
`"select target armor"` (selects contact A, task1 created) then later, with no intervening
`disengage`/`drop target`/`cancel`, `"select target two o'clock"` (resolves to a different contact
B, task2 created, task1 still `"pending"`). `_resolve_attack_target`/`describe_contact` resolve and
speak the readback against B — the pilot hears confirmation that B is now the target. But
`_active_attack_target_task()` still returns task1, so every subsequent `step`, `engage` (bare
form), and tier-1/tier-2 alignment guidance continues to operate on **A**, and A's own routine
callouts stay suppressed (`attention="priority"`, never demoted back) indefinitely, with no
mechanism short of `drop target`/`cancel` to clear it. The same ordering applies to
`"engage armor"` then later `"engage two o'clock"`.

**Why this is a required fix rather than a flagged risk.** This is exactly the failure class the
plan's own language is written to prevent — *"Petrovich talking in the seconds before release"*
about the wrong contact, here extended to *guiding toward* the wrong contact while the pilot
believes, on the strength of a spoken readback, that he re-targeted. It is reachable with the
feature's own primary commands under ordinary, expected use (re-selecting mid-run is not an edge
case a pilot would avoid — nothing in the spec or the direction document says "drop target before
selecting a new one"), not a theoretical or adversarial path, and it defeats the one invariant tier
1/tier 2 are built around: that silence (and by extension, guidance) means one consistent thing
about one consistent contact.

**Fix shape** (for the Implementer, not prescribed in detail): before minting a new `attack_target`
task, cancel any existing active one — mirroring `cancel_task`'s existing "undo the belief-state
effect" logic (return the old contact's attention to `"normal"`) — or mutate the existing task's
`contact_id`/`descriptor` in place the way `_handle_step` already does
(`target_task.contact_id = next_id`, `crew_console.py:2093`), which avoids the `TaskStore` growth
noted below as a side effect. Add a test exercising `select target X` → `select target Y` (different
contacts) with no intervening cancel, asserting the active task's `contact_id` is Y and A's
attention has returned to `"normal"`.

#### Low-risk finding — unbounded `TaskStore` growth under repeated selection

Every `select target`/`engage`-with-descriptor call that does not hit the bug above (i.e., even a
*correct* fix that still creates-rather-than-reuses) leaves one more `PendingIntent` in
`TaskStore._tasks` forever (`"Holds every PendingIntent ever created"`, no pruning). This mirrors
`watch_contact_task`'s own pre-existing shape exactly, so it is not a new pattern this feature
introduces, and in a single-player session the growth is bounded by how many times one pilot speaks
a selection command per sortie — not an externally-exploitable resource-exhaustion vector. Noted
because the required fix above, if implemented as "cancel-then-create" rather than "mutate in
place," should also address this for `attack_target` specifically; not required to fix independently.

### Verdict

**NEEDS FIXES** — one required fix (stale-target ambiguity above). Everything else in the no-
omniscience boundary audit (the five questions this review exists for) is sound, confirmed by
independent tracing rather than by reading the plan's own claims, and the remaining findings are
either pre-existing/out of scope, already-sanctioned exceptions, or recommendations that do not
block.

### Required Fixes

1. **Prevent a stale `attack_target` task from silently remaining "active" after re-selecting a
   different target** — `crew_console.py`'s `_handle_select_target`/`_handle_engage` (descriptor
   branch), via `tools.attack_target_task`/`belief.tasks.TaskStore`. See "Required fix in detail"
   above for reachability, consequence, and fix shape. Re-enters the loop: Implementer → Reviewer
   (review of the fix) → DoD, per `AGENTS.md`'s change-request rule.

### Optional Refinements (not blocking)

1. `Contact.last_percept` — add `field(repr=False)` as defense-in-depth against a future bare
   `print(contact)`/log statement exposing `relative_direction` via the default dataclass `repr`.
2. `belief_truth_log.write_speech`'s `attack_run_azimuth_deg`/`attack_run_elevation_deg` parameters —
   one docstring line stating these carry tier-1-exact values by design.
3. `plans/attack-run/plan.md`'s Risks section — one line noting `last_known_target_alt_m` has no
   staleness bound (unlike tier 1's `ATTACK_RUN_RELATIVE_MAX_AGE_S`), so a very long obstructed
   stretch during which the target changes altitude substantially will guide the vertical axis off
   an arbitrarily old remembered value. This is the user's own stated design (§24); recorded here so
   a sortie that notices it is read as expected behaviour, not a new defect.
