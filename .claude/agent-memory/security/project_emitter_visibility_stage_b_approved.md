---
name: emitter-visibility-stage-b-approved
description: Security deep-analysis verdict for AC-B8/BL-B73 Stage B (gun-fire emitter visibility, new firing-event channel) — APPROVED, and the trust-boundary reasoning worth reusing on BL-B74 (SAM launch)
metadata:
  type: project
---

`plans/emitter-visibility/security-stage-b.md`, reviewed at tip `8303d3bdcbfd10d7f689abb5955c8a578c28de87`.
**APPROVED**, one non-blocking low/low finding only.

**Why this one is worth remembering beyond the verdict**: it is the first stage of this feature to
add a genuinely new transport surface (a DCS event channel into `firing_receiver.py`'s stateful
`EmitterTracker`), which is why it got a real look rather than a formality — Stage A added no new
channel at all. Two reasoning moves held up and are worth repeating on `BL-B74` (SAM launch, the
next stage, also event-driven):

1. **Separate the loopback-only ingest socket from the LAN-reachable read endpoint when judging
   trust boundary.** `FiringEventsReceiver` binds `127.0.0.1` only — not reachable over the LAN at
   all. The LAN-reachable half is `GET /firing/latest` on the existing no-auth `TelemetryAPIServer`,
   which is a *read*, not an ingest path, and carries the same posture every other read endpoint on
   that server already has. Judging "is this new channel exposed" by the receiver's own bind
   address, not by "the aircraft-layer API server is LAN-reachable" (true but the wrong layer),
   avoided both overstating and understating the exposure.
2. **A resource-bound question ("is the watchdog-raised map safe against a chatty/hostile
   stream") needs the realistic *and* the loopback-bounded-adversarial case stated separately, not
   just the realistic one** — the lesson from this role's own worst miss
   ([[rate-a-fallback-by-how-often-it-fires-when-nothing-is-wrong]], the SRTM LOS fallback that was
   rated low/low from failure-mode reasoning alone). Here: real mission cardinality bounds it in the
   ordinary case, **and separately** the loopback trust boundary bounds the adversarial case (an
   attacker able to flood this receiver already has arbitrary code execution on the same box, at
   which point this channel is not the interesting surface) — both stated explicitly rather than
   leaning on one to imply the other.

**Verification method that actually caught/confirmed things**:
- `git diff main..<tip> -- body-layer/src/perception/visibility.py` across **all** commits in the
  stage, not just the latest one — came back empty, confirming the plan's "nothing in visibility.py
  changes in Stage B" claim at the byte level rather than trusting the plan's own account of itself.
- Checked `_OBSERVABILITY_EXEMPT_KINDS`/`_WATCHED_ONLY_KINDS` directly for the new `CONTACT_
  FIRING_SEEN` kind — same check this role's Stage A memory flagged as worth repeating, and it is
  worth repeating again at `BL-B74`'s `CONTACT_LAUNCH_SEEN`/similar.
- Read the Lua sort-key splice (`petrobrain-line-of-sight-hook.lua`'s `MAX_SIGHTLINES_PER_CALL`
  mitigation) as a diff, confirming it reads a *trusted sibling Hook script's* global rather than
  new untrusted input, and degrades to pre-existing behaviour (`or {}`) when that script is absent.
- Relied on `plans/emitter-visibility/review-2.md`'s own documented mutation run for the
  `FIRING_WATCHDOG_S` 10.0→180.0 fix (reverting it fails both new tests for the stated reason)
  rather than re-running it myself — **no `.venv` exists in a fresh worktree** (git worktrees don't
  carry a subproject's venv), so I could not execute pytest. Stated this explicitly rather than
  silently asserting a fresh run; worth remembering that a Security dispatch into a brand-new
  worktree cannot run the subproject's own test suite unless one is created or an existing one is
  reused.

**Open item carried forward, not a blocker**: a literal `;` or `:` in a DCS unit name would corrupt
the semicolon-delimited `entries` field in the firing-event wire format, dropping the whole poll's
batch (fail-closed, not fail-open — no misattribution, just a lost poll). Same free-text-field-in-
a-delimited-wire shape as `unit_velocity.py`/`line_of_sight.py` already carry elsewhere in this
codebase, so not a new defect class; worth a look if `BL-B74`'s wire format reuses the same pattern
for `S_EVENT_SHOT`'s already-parsed-but-unused `x`/`z` fields plus whatever new fields the smoke-
trail tail needs.

See also [[emitter-visibility-stage-a-approved]] for the Stage A verification method this stage's
checks built on.
