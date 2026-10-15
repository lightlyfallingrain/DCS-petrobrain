## Security Deep Analysis: emitter-visibility Stage A (BL-B72 + AC-B7)

Reviewed `feature/emitter-visibility` @ `1053265e9bec7411fc1a423d8142b9d64546c17c`. Worktree
created detached at the named tip (the branch was already checked out elsewhere, by the
performance reviewer running concurrently per the dispatch). Read the acceptance document, the
plan, both review passes (initial + fix-pass), the implementer's account, and the full diff
(28 files). Rebuilt both subprojects' venvs from the pinned versions and ran every check myself
rather than trusting reported counts — all matched exactly (body-layer: 2000 passed/4 xfailed;
aircraft-layer: 262 passed; both pre-existing `ruff format` findings reproduced in the exact files
named by the implementer/reviewer).

### Dependency Status

No dependency change. Reuses the existing `/unit_velocity/latest` feed and `net.dostring_in`
bridge, already shipping since 2026-09-13/09-22.

### The no-omniscience invariant — the angle this feature attacks it from

This is the first perception path where the target's own behaviour, not the observer's instrument
or geometry, decides whether it is seen — and the first deliberate, named bypass of gates that
every prior feature treated as absolute. Checked each claim directly against the code rather than
the account of it:

1. **Exactly two gates bypassed, only when they would otherwise reject.** Read `check_visibility`
   (`body-layer/src/perception/visibility.py`) directly: gate 3 (range/size, line ~1001) and gate 5
   (forest, line ~1028) each gate the bypass behind `if emitter is None: reject` — i.e. the bypass
   only ever *prevents* a rejection that would otherwise have happened, never widens an already-
   passing case. Gates 0 (gaze)/1 (cockpit mask)/2 (optic FOV), earlier in the function, and gate 4
   (terrain LOS, fail-closed on `candidate.live_los_clear`), sitting between the two bypassed
   gates, contain zero references to `emitter` — confirmed by reading that span of the file
   directly (lines ~1007–1024), not by trusting the diff's framing. An emitter can never improve a
   result beyond what the ordinary tier calculation would give it: the clamp only fires `if
   range_bypassed or forest_bypassed`, and otherwise falls through to the unmodified
   `_achieved_tier(...)` call — "never lowers" is also structurally enforced, not just tested.

2. **Detection only, and I could not find a path around the tier clamp.** Whenever either bypass
   fires, `achieved_tier`/`achieved_confidence` are hard-set to `NAKED_EYE_GATING_TIER_NAME`/
   `NAKED_EYE_PRESENCE_CONFIDENCE` and `_achieved_tier` is skipped entirely — there is no
   conditional path inside that clamp that could escalate tier based on range or size. Clustering
   cannot launder this either: `_build_observation`'s cluster-level fold only grants an emitter
   provenance when **every** member resolved the **same** emitter kind (`len(member_emitter_kinds)
   == 1`), and `Cluster.classification_level`/`classification_raw` are computed independently of
   provenance — an emitter-admitted member still only contributes its own clamped `PRESENCE` tier
   to the cluster's classification fold, it cannot inherit a better-seen neighbour's tier through
   the cluster path, because the cluster's classification is folded from each member's own
   (clamped) `VisibilityResult`, not upgraded by provenance. Belief fusion: `Contact.record` writes
   `is_burning` directly from `percept.emitter_kind` and does **not** touch
   `last_class_raw`/classification fusion at all — grepped the `record`/`from_percept` diff hunks
   directly, confirmed no classification-affecting write is conditioned on `emitter_kind`.

3. **The `Percept` boundary — closure verified by mutation, not by reading.** The first
   implementation let `Observation.provenance` (free-form `str`) cross into `Percept` wholesale and
   weakened `test_percept_has_no_truth_carrying_field` to match; Reviewer caught this and rejected
   it; the fix-pass commit (`607ba78`) replaced it with a closed `Percept.emitter_kind: str | None`
   populated through `_EMITTER_KIND_BY_PROVENANCE.get(observation.provenance)` — a `dict.get` with
   no override, so any provenance value not explicitly registered resolves to `None`. I re-ran the
   reviewer's own mutation independently (re-added `provenance: str | None` to `Percept` while
   leaving `emitter_kind` in place) rather than accepting the reported red/green: `test_percept.py`
   failed exactly as claimed (`test_percept_has_no_truth_carrying_field` and
   `test_percept_of_maps_emitter_provenance_to_emitter_kind`), reverted cleanly, full suite green
   again. The closure holds. **What stops the next feature widening it again**: nothing mechanical
   beyond the restored forbidden-set test itself and the convention it now documents — this is a
   process risk worth naming for `BL-B73`/`BL-B74`, not a defect in what's shipped (see
   Recommended, below).

4. **`is_burning` traced end to end.** `getLife()`/`getLife0()` (DCS ground truth) → Lua
   `lifeFields` (fails to the literal `"nil"` string on any `pcall` failure or non-number result,
   never a guessed `0`) → `UnitVelocitySample.life`/`life0` (`None` on `"nil"` or a legacy 4-field
   entry) → `burning_emitters` (pure predicate, `life/life0` in `[0.0, FIRE_LIFE_FRACTION_MAX]`) →
   `Emitter(kind=BURNING)` → `check_visibility`'s bypass/clamp → `PROVENANCE_EMITTER_BURNING` →
   `Percept.emitter_kind` → `Contact.is_burning`. Every hop is a perceivable, bounded signal (a
   life fraction crossing a physically-measured band), never a raw hit-point number leaking past
   the predicate — `Contact`/`Percept`/`Observation` never carry `life`/`life0` themselves, only the
   already-collapsed `bool`-shaped `emitter_kind`/`is_burning`. Confirmed by grepping for
   `life`/`life0` outside `aircraft-layer/src/schema/unit_velocity.py` and
   `perception/emitters.py`: no hit in `belief/` or in `perception/naked_eye_source.py` beyond the
   `burning_emitters(...)` call site.

5. **No attribution.** `_render_lifecycle_text`'s `CONTACT_BURNING_SEEN` branch renders exactly
   `f"Something burning, {clock} o'clock."` (`belief/speech.py`) — read directly, not quoted from
   a report. No unit-type claim, no range clause, no causal language. `plans/brain-layer/
   explore-notes.md` is untouched by this diff (confirmed: not in the changed-file list).

### Fail-safe on the transport boundary

The Lua hook fails every life read to the literal `"nil"` (never a guessed `0`), which the schema
parses to `None`, which `burning_emitters` treats identically to "no samples this poll" — a missing
or nil life value fails to **not burning**, never to visible. A malformed (non-`"nil"`,
non-numeric) life field is the one case that raises (`UnitVelocityParseError`), but this channel is
same-machine loopback UDP from the project's own Lua, not externally-reachable input, and the
receiver already catches `UnitVelocityParseError` and drops that poll's payload rather than
crashing (`collector/unit_velocity_receiver.py` line ~132) — confirmed by reading the except
clause directly, not assumed from the existing-feed pattern. No new failure surface.

### `net.dostring_in` / Lua side

Two extra `pcall`s per unit per second, inside the same existing `VELOCITY_CODE` string and the
same `"scripting"`-state call this feed already made — no new `net.dostring_in` call site, no new
autoexec gate, no new injected-code construction from external input (the string is a fixed
literal, confirmed unchanged except for the `lifeFields` addition, itself also a fixed literal).
Correctly defined *inside* `VELOCITY_CODE` rather than as a Hook-local function — the implementer's
own notable-discovery entry documents having caught the opposite mistake before it shipped.

### Grep-fence / pattern scan

Ran `/security-grep` across both subprojects plus the Lua tree. No new hit in any category
attributable to this feature: no `eval`/`exec`/`loadstring`, no new `subprocess`/`socket`/file-write
call, no new hardcoded-credential-shaped literal, no new unbounded remote-sized read. The only
`net.dostring_in` hits are the two pre-existing, expected call sites in
`aircraft-layer/dcs-export/`. `raise`/`assert` hits in changed files are all either
`UnitVelocityParseError` on malformed wire input (pre-existing pattern, now applied to two more
fields) or ordinary `assert isinstance(...)` narrowing already pervasive in `speech.py`/
`callouts.py` — no new crash path reachable from outside the local machine.

### `_OBSERVABILITY_EXEMPT_KINDS` / `_WATCHED_ONLY_KINDS` — checked against the recorded failure
pattern

This project's own retro (`.claude/agent-memory/security/`) records a prior miss where an
`EventKind`-keyed exemption set silently covered a transition it was never written for. Checked
`CONTACT_BURNING_SEEN` against both sets directly in `body-layer/src/belief/callouts.py`:
`_OBSERVABILITY_EXEMPT_KINDS = frozenset({CONTACT_ENGAGEMENT_CHANGED})` and `_WATCHED_ONLY_KINDS =
frozenset({CONTACT_MOTION_CHANGED, CONTACT_RANGE_CROSSED, CONTACT_ENGAGEMENT_CHANGED})` — neither
contains `CONTACT_BURNING_SEEN`. It is subject to the ordinary observability gate at speak-time
(`CalloutScheduler.tick`), as the implementer's own comment claims, and I confirmed by reading the
frozenset literals rather than the comment describing them.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/perception/visibility.py` ~991-1060 | gate bypass + tier clamp | Correct: exactly gates 3/5, tier clamp unconditional, gates 0/1/2/4 untouched | None |
| `body-layer/src/belief/percept.py` | closed `emitter_kind` mapping | Correctly closed, confirmed by mutation | None |
| `body-layer/src/belief/contacts.py`, `events.py` | `is_burning` write, one-directional event | No classification path touched; informational-only event, correctly excluded from threat routing | None |
| `body-layer/src/belief/speech.py` | wording | Matches accepted, attribution-free wording exactly | None |
| `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua` | life field read | Fixed-literal snippet, fail-safe to `"nil"`, no new bridge call site | None |
| `aircraft-layer/src/schema/unit_velocity.py` | malformed life field raises | Raises on genuinely malformed input, but caught by the receiver and this is a trusted same-machine channel, not externally reachable | None (informational) |
| `plans/forest-occlusion/plan.md` | merge-time note not yet added | Plan's own Risks section says this is needed "at merge" — not yet present | Recommended (housekeeping, not a vulnerability) |

### Verdict

**APPROVED.**

### Recommended (non-blocking)

1. **Add the numbered `Decision N REVISED` sub-decision to `plans/forest-occlusion/plan.md`** per
   that plan's own Risks section, before or at merge — it is documentation hygiene (that plan's
   "flat and binary, no directionality" description is now incomplete), not a vulnerability, and
   the reviewer already flagged it for DoD/merge to carry forward.
2. **No mechanical guard yet stops a future `Observation.provenance` producer from being folded
   wholesale into `Percept` again** beyond the restored `test_percept_has_no_truth_carrying_field`
   entry and the convention it documents. This boundary has now been pushed once in the space of
   one feature (caught by Reviewer, not by a structural check). Worth a one-line note in
   `belief/percept.py`'s module docstring for `BL-B73`/`BL-B74`'s authors pointing at the
   `_EMITTER_KIND_BY_PROVENANCE` pattern as the required shape, so the next emitter kind follows it
   by default rather than rediscovering the same argument. Not required before merge — the test
   itself is the real guard and it is confirmed live.
