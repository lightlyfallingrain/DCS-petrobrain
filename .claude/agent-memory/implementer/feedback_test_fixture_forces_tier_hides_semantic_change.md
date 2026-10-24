---
name: test-fixture-forces-tier-hides-semantic-change
description: a test helper built to force one code path (e.g. tier 2 only) can silently encode an old semantic assumption that a later redefinition of that path's meaning invalidates -- run the suite, don't trust the plan's test-impact list
metadata:
  type: feedback
---

On `plans/attack-run-los/plan.md` (body-layer, 2026-10-24), the plan's own test-impact assessment
said "this alone should not break any passing test" for the F2 fix (redefining attack-run's
loss/regain register from `cause == "too_far"`-keyed to `tier != 1`-keyed). Running the suite found
5 failures.

**Why:** `test_attack_run.py`'s `_contact_at` helper is explicitly documented to force tier 2
regardless of range ("these cause-taxonomy tests are about `_no_look_cause`, not tier selection").
Several transition-register tests used it (or a tier-1-then-briefly-stale scenario) to simulate
"regaining sight" via cause/range alone, with no genuine tier-1 look ever occurring. Under the old
`cause`-keyed register this coincidentally worked; under the new `tier`-keyed register it is
*exactly* the bug being fixed (a tier-2-only contact can never be "resolved" anymore, by design).

**Why:** The plan reasoned about which tests exercise the mechanism being changed by reading test
*names/docstrings*, not by checking what each test's fixture actually produces (tier 1 vs tier 2).
A fixture built for an unrelated purpose (forcing tier 2 to isolate `_no_look_cause`) had been reused
by other tests in a way that happened to also pin the old transition-register semantics.

**How to apply:** When a plan changes what a boolean/register is *keyed on* (not just a threshold),
don't trust "this shouldn't break anything" from the plan — grep every test that constructs the
state being re-keyed and check what each one's fixture actually produces for the new key, not just
what cause/value it sets. Run the full affected test file before writing new tests, every time,
even when the plan says not to bother. Five tests failed here; all five were legitimate consequences
of the fix (confirmed via live mutation runs that reverting the fix makes them fail again), not
false positives — they were updated to describe the new, specified behaviour rather than worked
around.

Related: root `CLAUDE.md`'s "treat the plan's test-impact list as a hypothesis, not a checklist"
instruction (`.claude/agents/implementer.md`) — this is a concrete instance of exactly that failure
mode, in the "missing entry" (silent) direction rather than the "phantom test" (loud) direction.
