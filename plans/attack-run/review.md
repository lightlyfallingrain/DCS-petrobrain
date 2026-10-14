### Review Summary

Reviewed `feature/bl14-attack-run` at `a880e20a7cd89010d9c7f5df64de25bdb9a85db6` (fast-forwarded
from a stale worktree base `f25c57c`, which was a strict ancestor — clean fast-forward, no
divergence). Scope: BL-14 Stages 1–3 only (selection/drop-target + audio-adapter vocabulary; the
inert ownship-relative observation channel; the pure, unwired alignment derivation and renderers).
Stages 4–7 are correctly absent.

Full read of `plans/attack-run/plan.md` (1122 lines), `docs/acceptance/2026-10-14-attack-run-
guidance-direction.md` (539 lines, the user's own words, which outrank the plan), and
`plans/attack-run/implementation.md`. Read every changed file in `body-layer/src/belief/
attack_run.py`, `percept.py`, `contacts.py`, `speech.py` (the `render_alignment` family),
`crew_console.py` (`_resolve_attack_target`/`_handle_select_target`/`_handle_drop_target`/
`drain_attack_run`), `perception/naked_eye_source.py`, `perception/geometry.py`,
`perception/estimation.py`, `perception/clustering.py`, `perception/detection_trace.py`, and
`audio-adapter/src/command_matcher.py`/`vocabulary.py`. Ran all gates myself rather than trusting
the implementer's report; mutated the two highest-risk pinned tests from source.

The implementation matches the plan's Stage 1–3 scope closely, correctly declines to build
anything from Stage 4 onward, and the two "Notable Discoveries" in `implementation.md` (the false
plan premise on Decision 16, and the circular-import resolution for `render_alignment`'s word
tables) are accurately reported and correctly handled in the code.

### Verification — run myself

**body-layer/** (from `cd body-layer`, using the main checkout's venv by absolute path, confirmed
resolving `belief.attack_run` to *this* worktree's `src` before running anything):

- `ruff format --check src tests`: pass (126 files already formatted)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 58 source files`
- `pytest tests -q`: **1790 passed, 4 xfailed** — matches the implementer's report exactly

**audio-adapter/** (same pattern):

- `ruff format --check src tests`: pass (29 files)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 15 source files`
- `pytest tests -q`: **261 passed, 1 skipped** — matches the implementer's report exactly

### The five specific questions — findings

**1. `Contact.last_percept` — proportionality and surface widening.**

(a) *Proportionate.* `ContactStore` already has an accepted "full memory, never pruned" posture —
`BL-B23` (`body-layer/ROADMAP/BL-B23.md`) deliberately left `_contacts` itself untouched when it
fixed the *clustering*-cost quadratic blowup: "`_contacts` itself is untouched: nothing is
deleted, a `lost` contact stays full memory and remains answerable." `last_percept` is a single
object reference, **overwritten, not appended**, each `record()`/`from_percept()` call — O(1) per
contact, not O(n) growth like `contributing_observation_ids`' list already is. Against that
existing precedent, one more whole-object reference per contact is in line with, not a departure
from, how this store already treats memory. A narrower field (just `RelativeDirection` +
`ownship_at_observation` + `t_sim`) would save a handful of bytes per contact and buys nothing —
the implementer's stated reason for the whole object (grep-fence purity: `contacts.py` never has
to write a field literally named anything containing `relative_direction`) is a real, load-bearing
constraint, not an excuse. Not a required fix.

(b) *Does not widen the truth-derived surface the way the prompt's framing suggested.* I checked
this directly against `percept.py`: **`Percept` does not carry `derived_world_position`** — that
field exists only on `Observation`, and `Percept` is deliberately "stripped of every DCS truth
field" (its own docstring). So `last_percept` gives no belief code a one-hop path to ground truth
via that field; the only genuinely truth-adjacent field it newly reaches is `relative_direction`
itself, which is exactly the field the grep fence (next finding) is built to contain. The premise
in the review brief ("a `Percept` carries `derived_world_position` and now `relative_direction`")
is factually wrong about `Percept`; it is true only of `Observation`, which never crosses into
`belief/`.

**2. The grep fence — mutation-tested, holds.**

Confirmed by injecting a real leak (`contact.last_percept.relative_direction` appended to
`tools.py`, outside the two sanctioned files) and running
`test_belief_never_references_relative_direction_except_sanctioned_readers`: it failed with the
exact assertion the fence promises (`tools.py references relative_direction`). The fence is a
structural protection against the realistic failure mode — a future contributor reaching
`contact.last_percept.relative_direction` from inside some other `belief/` module — because that
access necessarily writes the literal string `relative_direction`, which the regex catches. It
would not catch a deliberately obfuscated access (`getattr(contact.last_percept, "relative" +
"_direction")`), but that is true of every grep fence in this codebase, including the pre-existing
`derived_world_position` one it mirrors, and is not a new weakness this feature introduces. The
architect's "structural, not merely informational" claim holds for the realistic case; it was not
weakened into a naming convention, and I verified that by breaking it, not by reading it.

**3. `render_alignment`'s tier-2 `NotImplementedError` — unreachable by construction, not just by sequencing.**

Traced every call site: `attack_run.decide` is the *only* caller of `render_alignment`, and it
passes `tier=1` as a hardcoded literal — there is no parameter, branch, or state field anywhere
that could make it pass `2`. `drain_attack_run` (unwired) calls only `decide`. No other code in
either subproject calls `render_alignment` at all except the test that explicitly expects the
`NotImplementedError`. So the guard cannot be reached from any live path today, independent of
Stage 5/6 sequencing — it is unreachable by construction, which is better than the brief's
question assumed.

One real improvement available, offered as optional: `tier: int` could be narrowed to
`tier: Literal[1]` now (widened to `Literal[1, 2]` when Stage 6 adds the second branch), which
would make the guard a type error at the call site rather than a runtime raise, and is a one-line,
structurally cheap change.

**4. `body-layer/CLAUDE.md` in the diff — belongs.**

The diff adds three "Module map" entries documenting new files this feature introduces
(`attack_run.py`), the new `tasks.py` `TaskKind`, and the new `attack_target_task` on `tools.py`.
This is the same category as the `docs/STRUCTURE.md`/`ROADMAP/BL-14.md` registrations the
implementer also made — documentation of the feature's own new surface, not cross-cutting
bookkeeping unrelated to this milestone. It belongs in these commits per `AGENTS.md`'s own
distinction (cross-cutting convention edits take their own worktree; documentation of a feature's
own new modules does not).

Minor, optional: `BL-14.md`'s top checkbox still reads `[ ] ... NOT STARTED` even though a
"2026-10-14 update — Stages 1-3 implemented" section was appended below it. The appended section
does answer CLAUDE.md's Milestone Completion question ("does not change what the next milestone
should be"), but the stale top-line status is a minor accuracy gap for the next reader skimming
just the checkbox. Not required — BL-14 genuinely isn't done yet.

**5. The three singled-out tests — present, and mutation-confirmed to fail when broken.**

- **Oblique heading + banked case**
  (`test_decide_oblique_heading_and_banked_ownship_does_not_mix_axes`): present. **Mutated**
  `_tier1_alignment` to route through `body_relative_direction(..., bank_deg=ownship.bank_deg)`
  instead of `alignment_direction` (i.e. reintroduced exactly the bank-mixing bug the plan's
  Decision 3 exists to prevent). Result: `level[0]` (13.93°) vs `banked[0]` (6.32°) — the test
  failed immediately with the expected assertion. Restored the file; suite green again (18/18 in
  `test_attack_run.py`).
- **9°-heading-apart re-rotation pin**
  (`test_decide_re_rotates_against_current_heading_not_the_observed_one`): present. **Mutated**
  `_tier1_alignment` to undo yaw using the *current* heading instead of the heading recorded at
  the observing poll (defeating the whole point of carrying an offset rather than a frozen angle).
  Result: `az_a - az_b` collapsed from the expected `9.0°` to `0.0°` — the test failed with the
  exact diagnostic. Restored; suite green.
- **Banked case is covered by the same test as the oblique-heading case** (one function,
  `heading_true_deg=37.0` plus `bank_deg=0.0` vs `bank_deg=60.0`), satisfying both the "oblique"
  and "banked" requirements in one assertion pair — not two separate tests, but both conditions
  are genuinely exercised, confirmed by the mutation above which only the banked half of that test
  would have caught.

Both mutations were reverted (`git diff --stat` confirms no residual change to `geometry.py` or
`attack_run.py`), and the full `test_attack_run.py` suite was re-run clean afterward.

### Specification-rule trace (direction document → code)

All verified directly against the acceptance document's §§1–11, not the plan's paraphrase:

- **Qualitative only, no degrees in spoken strings** — confirmed: `render_alignment`'s phrases are
  all from the word tables (`"come left"`, `"a bit right"`, `"higher"`, `"a little lower"`,
  o'clock words). No `f"{deg}"` or numeric interpolation anywhere in the rendered text.
- **Silence is the signal; one `"lined up"`, then nothing** — confirmed via
  `test_decide_dead_ahead_and_level_lines_up_and_speaks_once` and `_should_emit`'s change-driven
  gate (text-or-threshold, baselined against the last *spoken* value, not the previous sample —
  §10's own named slow-drift guard).
- **Range spoken once, never again** — `render_target_readback` deliberately omits range
  (`"Target, armour, 2 o'clock."`), with the full readback including range correctly deferred to
  `engage`'s own Stage-5 readback per its own docstring. Correct staging, not an omission.
- **Aligned is the conjunction of azimuth band and elevation gate** —
  `render_alignment`: `"Lined up."` only when *both* `_alignment_phrase_for` calls return `None`.
  Confirmed directly and by `test_render_alignment_elevation_only_fires_without_azimuth_word`.
- **Fine-grained elevation reachable by parameter alone, one helper, same table shape both axes** —
  confirmed by `test_both_axes_share_one_table_lookup_helper`, which swaps in a two-row elevation
  table and gets the finer phrase with no renderer change. `_alignment_phrase_for` is the one
  shared helper; nothing branches on "the vertical axis is coarse."
- **Three constants, one place, named, with reasoning, nobody tuned them** — all three
  (`ATTACK_RUN_LINED_UP_AZIMUTH_DEG=5.0`, `ATTACK_RUN_ELEVATION_GATE_DEG=10.0`,
  `ATTACK_RUN_CHANGE_THRESHOLD_DEG=3.0`) declared once in `attack_run.py` with extensive
  docstring reasoning tracing to the plan's Decision 11/11 REVISED, and pinned unchanged by
  `test_the_three_constants_are_unchanged_assumptions` — exactly the plan's proposed values.
- **`silence` mutes guidance, no exemption (§16)** — `drain_attack_run` calls `self._print`
  (no `bypass_gate=True`), which is the ordinary channel every other speech line goes through and
  which `self.silenced` already gates. No special-casing needed or added; correct by reuse.
- **No world-model elevation query (§17)** — confirmed: `_tier1_alignment` takes the target's own
  altitude from `Cluster.centroid_alt_m`/`percept.ownship_at_observation`, never from
  `geometry.elevation_at`. No new world-model call site in this diff.

### Other checks

- **Module responsibility**: `belief.speech` has zero import of `belief.attack_run` (confirmed by
  grep); `belief.attack_run` imports `render_alignment`/`OutgoingSpeech` from `belief.speech` and
  passes its own word tables in as data arguments — no circular import, exactly as the
  implementation notes claim, and I verified the import statements directly rather than trusting
  the claim.
- **No invariant violations found**: no DCS-install writes; no unverified forum/community claims
  encoded as fact; the one new perception datum (`RelativeDirection`) is produced in `perception/`
  and crosses the belief boundary through `percept_of` exactly like every other field, preserving
  the no-omniscience boundary's existing shape rather than adding a second path around it.
- **New files staged**: confirmed via the fast-forward diffstat and `git status --porcelain`
  (clean) — all new files (`attack_run.py`, `test_attack_run.py`, `group_view.py`,
  `test_group_view.py`, `crew_console.py`'s `group-collapse`-era additions, etc.) are committed on
  the branch already; nothing left to stage.
- **Leftover debug code / TODOs**: none found in the diff's new code. The one explicit, documented
  gap (watched-only callouts enrolling the attack-run target before Decision 5's Stage-5
  suppression gate lands) is called out in `implementation.md` and traced to the plan's own
  staging — a stated, deliberate gap, not an oversight.
- **Parallel-treatment grep check** (the standing check from this role's own memory): grepped for
  `relative_direction_set` (detection_trace's own call site) and `perturbed_relative_direction`
  (the new mechanism's own call site) rather than trusting the file list — both are wired at
  exactly one call site each, in `naked_eye_source.py`, matching the plan's single-channel scope
  (the naked-eye channel is the only one with a geometric gate chain to instrument; the
  scope/hybrid channel correctly gets neither, per `body-layer/CLAUDE.md`'s own note on why the
  detection trace is naked-eye-only).

### Required Fixes

None.

### Optional Refinements

- Narrow `render_alignment`'s `tier: int` to `Literal[1]` now (future `Literal[1, 2]` at Stage 6),
  turning the tier-2 guard into a type error rather than a runtime `NotImplementedError` at the
  one call site that could ever pass the wrong value. Cheap, and strictly stronger than what
  exists; not required because the guard is already unreachable by construction, verified above.
- Update `BL-14.md`'s top-line checkbox/status word (still `NOT STARTED`) now that Stages 1–3 are
  implemented, so a reader skimming only the checkbox doesn't contradict the appended update
  section below it. Cosmetic; the milestone genuinely isn't complete.

### Verdict

**APPROVED**

### Review Confidence

Full read of the plan, the acceptance direction document, the implementation notes, and every
changed source file in both touched subprojects. All four verification gates run directly from
inside each subproject against this worktree's own `src` (confirmed by import resolution before
running). Both of the two highest-risk pinned tests (re-rotation, bank-stabilisation) were
mutation-tested from source, not read-and-trusted: each failed with the expected diagnostic when
the mechanism it claims to protect was reintroduced as a bug, and each was cleanly reverted
afterward. The grep fence was mutation-tested the same way. No part of this review rests on the
implementer's account alone where a cheap independent check was available.
