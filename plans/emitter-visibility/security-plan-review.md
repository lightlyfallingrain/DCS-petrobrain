## Security Plan Review: emitter-visibility (BL-B72 Stage A / AC-B7)

**Retroactive.** This gate normally runs after Architect and before Implementer; here it was
skipped because the user's "go ahead and implement" arrived in the same message as the four
architect decisions. Implementation, two Reviewer passes, Performance Reviewer, and Security's own
deep-analysis pass (`plans/emitter-visibility/security.md`, APPROVED) all happened first. This
review reconstructs the plan-stage gate against `plans/emitter-visibility/plan.md` as originally
written, and separately says whether running on time would have changed anything.

### Dependencies Checked

- `/extract-plan-deps` found no dependency-posture prose in the plan at all — this plan's authors
  did not write an explicit "no new dependency" sentence, unlike some other plans in this repo.
- Checked anyway, against the plan's own "Affected Modules" section and the actual diff
  (`git diff main...HEAD -- '*/pyproject.toml'` — empty, no subproject's manifest changed):
  Stage A adds two fields to an **existing** `pcall`-based Lua read, an **existing**
  `net.dostring_in`/`VELOCITY_CODE` bridge call, and a new pure-Python module
  (`body-layer/src/perception/emitters.py`) with no imports beyond this project's own code. No new
  package, no new third-party wheel, no new endpoint, no new client library.
- **Verdict: CLEAN. No dependency change.** The plan's silence on dependencies was accurate, just
  unstated — worth noting as a documentation gap for future plans in this project's own convention
  (most plans here state the posture explicitly to make it checkable), not a security finding.

### Design Findings

1. **The plan's central security-relevant act is a deliberate, named bypass of two visibility
   gates (range/size, forest) that every prior feature in this codebase treated as absolute.**
   This is exactly the class of design decision this review exists to catch before code is
   written. The plan does not treat it casually: it specifies the bypass is **conditional on
   already-failing** (gates 0/1/2/4 — gaze, cockpit mask, optic FOV, terrain LOS — are explicitly
   listed as unchanged) and pairs it with a **structural tier clamp** (`("lowres",
   NAKED_EYE_PRESENCE_CONFIDENCE)`, `_achieved_tier` never called) that forces detection-only,
   explicitly stated as "the invariant that makes this detection-only... an emitter must never
   lower what Petrovich can see." That is the correct shape of mitigation for a gate-bypass
   design — the risk is named, bounded by an invariant stated in the plan itself, and the plan
   lists a non-interaction test obligation (group-salience must not widen for an emitter's
   neighbours) rather than leaving it to be discovered later. **Low residual risk as designed** —
   this is the project's own no-omniscience invariant, not a classic security boundary, but the
   plan treats it with the rigor a security reviewer would ask for.
2. **No untrusted input introduced.** The new data (`getLife()`/`getLife0()`) is read from DCS's
   own simulation state via the same same-machine, loopback-only `net.dostring_in` bridge every
   other perception feed already uses. Nothing here crosses a trust boundary that wasn't already
   crossed by the existing `/unit_velocity/latest` feed — riding on it (the plan's own
   Decision 1 recommendation, accepted) was the right call for exactly this reason: a new endpoint
   would have been a new attack surface to evaluate, and reuse avoids creating one.
3. **No new file-system paths, no new IPC surface, no new deserialization path.** The schema
   change (`UnitVelocitySample.life`/`life0`) extends an existing colon-delimited wire format
   parsed by an existing parser; the plan does not specify the exact fail-safe behavior for a
   malformed field (that detail was an implementation choice, confirmed sound by the deep-analysis
   pass: fails to `"nil"`→`None`, never a guessed `0`, and the one raise path is caught by the
   receiver). A plan-stage reviewer could have asked for that fail-safe explicitly rather than
   leaving it to the implementer to get right, but it is not a defect in what the plan proposed.
4. **The plan itself names two risks a security-minded design review would otherwise have raised
   independently**, which is worth recording as the plan having done its own job rather than this
   review finding something new: `MAX_SIGHTLINES_PER_CALL = 128`'s nearest-first truncation
   silently neutering the far-emitter case the feature exists for (fail-closed, so it fails safe,
   just confusingly), and this being the first exception to the forest gate's documented
   "flat and binary" description elsewhere in the repo (a consistency/documentation risk, not an
   exploitable one, and the plan already prescribes the fix — a numbered sub-decision at merge).
5. **No auth/access-control gap.** Single-player, LAN-only project; the data this feature exposes
   (a unit is burning) is strictly a subset of information Petrovich's existing perception already
   has access to in principle (the theatre-wide `getLife()` read is explicitly flagged by the plan
   itself as "a provenance concern, not a leak," correctly reasoned: the emitter map is intersected
   with the bubble-filtered candidate list before any gate sees it).

No finding here rises to "known CVE," "high-risk design pattern without justification," or
"missing safeguard the plan should have specified but didn't" at a severity that would block.

### Verdict

**APPROVED**

### Would this have changed the plan, had it run on time?

**No material change.** The gate-bypass design, its mitigation (tier clamp), and the two named
risks (sightline truncation, forest-gate precedent) were already present in the plan's own text —
exactly what this review would have asked the Architect to justify, already justified. The one
real security-shaped catch that happened on this feature — `Observation.provenance` almost
crossing wholesale into `Percept`, widening the no-truth-carrying-field boundary — is not something
a plan-level review would have caught, because the plan describes that boundary at the conceptual
level ("provenance rides on a field that already exists") without committing to the exact
`Percept`-side shape; that commitment only exists once code is written, which is precisely why this
project's sequence puts a second Security pass (deep analysis) after Reviewer rather than relying
on the plan-stage pass alone. It was caught by Reviewer at the right stage, not missed by this one.

No action required before DoD on this gate's account; the implementation-level gate
(`plans/emitter-visibility/security.md`) already stands APPROVED and is the one that matters for
code that shipped.
