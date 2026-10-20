---
name: reject-not-clamp-can-empty-every-fallback
description: When reviewing a "reject, not clamp" filter added to fix an out-of-envelope bug, check the altitude/parameter extreme where EVERY producer the filter touches goes empty at once, not just the altitude named in the original defect report.
metadata:
  type: project
---

On `9k113-narrow-search`'s security re-review (`bb6364b0`, `plans/9k113-narrow-search/
security-review.md` Required Fix 1), the fix filtered `_sight_in_regard_sweep`'s steps through
`within_field_of_regard` ("reject, not clamp" — the established pattern, see
`.claude/agent-memory/implementer/feedback_declared_bound_check_at_selection_not_at_consumer.md`).
The security review's own table stopped at 1500 m AGL (the worst case it measured). Driving the
real production legs through `decide()` at higher altitudes (2000/3000/4000/5000 m AGL) found that
**all three in-regard legs simultaneously go empty above ~3.6–4 km AGL** for a free scan or a
commanded "ahead" scan — and because neither of those two sectors ever produces an out-of-regard
binocular remainder (`_sight_out_of_regard_sweep` returns `[]` by construction for them), the whole
idle search cycle has nothing left to step through and falls to the full-exhaustion fallback
(`_idle_sight_rest`, holding a fixed aim). Filed as `BL-B86`, not a required fix — the fallback was
already verified safe (bounded loop, no crash/hang), but the *magnitude* (full stop, not a
degraded band) was undersold by the implementer's own "what the pilot will notice" note.

**Why:** a "reject, not clamp" filter is correct per-step, but its real effect is only visible by
composing across the full range of the input it gates (here: altitude), because every producer it
touches can empty out together at some extreme even though each extreme individually "only drops
some steps." The existing fallback chain (leg-advance → full-rest) hides this behind a safe-looking
degradation, so reading the code alone won't surface it — it has to be driven.

**How to apply:** whenever a Reviewer verifies a newly-added `within_X`/regard-style reject filter,
after confirming it fixes the reported case, sweep the bounding parameter (altitude, range, whatever
the geometry turns on) well past the reported worst case and check (a) whether every producer the
filter touches can go empty at once, and (b) whether the surrounding mechanism has anywhere left to
fall back to when they do. If there's a fallback, verify it's actually safe by running it (not just
reading that it exists) — but also report the magnitude of the degradation as a finding, even when
it's not a blocker, since "the fallback never crashes" and "the fallback never crashes AND the
feature stops doing its job above X" are different findings and only the first one is usually
checked.

See also `[[reviewer-verify-by-mutation]]` (the broader "drop each entry / drive it past its
assumed range" method this is one instance of).
