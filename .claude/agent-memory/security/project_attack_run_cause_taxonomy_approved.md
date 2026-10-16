---
name: attack-run-cause-taxonomy-approved
description: BL-B70's attack-run no-look cause taxonomy (masked/obstructed/too_far/unknown) — security deep analysis found nothing material; strengthens no-omniscience disclosure rather than loosening it
metadata:
  type: project
---

`plans/attack-run-sortie-fixes/plan.md` (BL-B70) replaced attack-run guidance's "tier 2 always
says obstructed" rule with a cause taxonomy (`attack_run._no_look_cause`: `masked`/`obstructed`/
`too_far`/`unknown`), computed from the same primitives `perception.visibility.check_visibility`
already gates on, in the same gate order. Security deep analysis (`plans/attack-run-sortie-fixes/
security.md`, 2026-10-16) found no material finding: pure functions, no I/O, no new dependency, no
new external input-trust surface (`Contact`/`OwnshipState` are the same internal belief-store
objects every other `belief/` module reads), no injection surface in the new speech-render
functions (plain string assembly from internal vocabulary, never executed or used as a format
string downstream).

**Checked explicitly against two memory lessons that looked applicable and did not reproduce:**
- [[project_exemption_from_a_gate_check_both_transitions]] — the `MASKED` cause's silence is a
  single unconditional `return state, None` preceding every other branch, with no
  direction-dependent sub-case, so there is no asymmetric-transition shape to find (unlike the
  `EventKind`-keyed exemption that memory describes, which *did* have one).
- [[project_bl_b64_field_of_regard_unenforced]] — no "enforcement deferred to a later stage that
  never landed" shape here; the taxonomy and its consumer (`decide`) land in the same commit.

**The feature is a net tightening of the no-omniscience invariant**, not a new risk: it stops a
target merely beyond naked-eye presence range, or behind the cockpit mask, from being misreported
as `"obstructed"` (an incorrect claim about *why* Petrovich has no look) or spoken over at all
(`MASKED` is now silent). The one accepted gap — `UNKNOWN` sounding identical to a live look — was
already raised and resolved by the user in the plan's own Decisions section, not a new finding.

Also confirms the `BL-B64`-class fresh-construction bug (the plan's own F4) did not recur: every
emit/memory-update site in this diff uses `replace()`, and `defaults.toml`/`tuning.py` correctly
dropped the removed `ATTACK_RUN_CHANGE_THRESHOLD_DEG` entry with no new tuning constant beyond the
one already reviewed (`ATTACK_TARGET_LOS_MAX_AGE_S`).

Related: `[[project_bl_b64_field_of_regard_unenforced]]`,
`[[project_exemption_from_a_gate_check_both_transitions]]`.
