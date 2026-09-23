---
name: project_binocular_optic_stage2_3b_review
description: Binocular-optic Stage 1-3b (82b1b29..e91b9ee) review outcome — the D4 "any command lowers binoculars" rule was only wired for one of two live command paths
metadata:
  type: project
---

Reviewed 2026-09-23, APPROVED WITH MINOR FIXES. `belief/optic_policy.py`'s core
decision (purity, `perception`/`belief` layering, `phase_started_sim: float | None`
guards, elevation sign conventions across `Gaze`/`within_optic_fov`/`look_target_for`/
`search_pattern`, the Stage 3b envelope-vs-step split) all checked out clean on direct
code reading, and the Stage 3b tripwire (`TestSweepFindsAnOffsetContact`) was verified
genuine by empirically forcing `look_sweep`'s half-width to 0 and re-running it (red,
as expected) — see [[feedback_regression_test_empirical_check]].

**The real finding: D4 ("a player command lowers the binoculars, unconditionally...
not a special case per command") was only half-wired.**
`CrewConsole._note_player_command()` (what `logger.py`'s poll loop reads via
`commands_handled` to call `lower_binoculars`) is called only inside
`handle_f10_command`. Free-form utterances via `_act` (`set_attention`/
`describe_contact`, reachable from typed `handle_line` *and* from voice's
`"fallthrough"` disposition, which also routes through `handle_line`) never call it —
so typing/saying "watch that contact" doesn't lower binoculars, but selecting the
equivalent F10 token does. The existing regression test
(`test_a_player_command_lowers_the_binoculars`) doesn't catch this: it tests the
counter-increment and the `lower_binoculars` function separately, never the actual
end-to-end poll-loop wiring, so the gap had zero test coverage in either direction.

**Technique worth reusing**: when a feature adds "does X trigger Y" as a design rule
stated to be command-surface-agnostic, grep every call site of the triggering
mechanism (`_note_player_command` here) rather than trusting the one test named after
the rule — the test existing does not mean the wiring it claims to guard is complete.

Also flagged (both doc-only, both required before merge per project convention):
plan.md's own Stage 3b header still said "NOT BUILT" despite being merged; no
`body-layer/ROADMAP.md` entry exists for this milestone at all (recurring finding
class — see [[m10-junction-review]], [[project_group_detectability_roadmap_lag]]).
