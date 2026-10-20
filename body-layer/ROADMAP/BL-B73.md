# BL-B73 — Gun fire makes its firer visible out to the player bubble

- [x] **BL-B73 — While a unit is firing a gun or autocannon, admit it at `PRESENCE` out to
  `PLAYER_BUBBLE_RADIUS_M` and through tree cover, using `S_EVENT_SHOOTING_START`/`_END` over the
  mission-scripting bridge.** #status/done #needs-flight Split out of `[[BL-B72]]` at Architect
  stage, 2026-10-15 — `plans/emitter-visibility/plan.md` Stage B, Decision 2. Same user direction
  and same acceptance document (`docs/acceptance/2026-10-15-firing-unit-visibility.md`).

  **Delivered 2026-10-16** (`feature/emitter-events`, DoD @ `aafb20a`): `perception/emitters.py`
  folds `[[AC-B8]]`'s firing snapshot into the same `dict[int, Emitter]` the burning channel
  (`[[BL-B72]]`) already produces, `EmitterKind.FIRING` and `targets_ownship` thread through, and
  `CONTACT_FIRING_SEEN` gets its own event kind and priority so a `PRESENCE`-only firing contact is
  no longer buried at the lowest threat band — `"taking fire, two o'clock"` when `targets_ownship`,
  `"something firing, two o'clock, far"` otherwise. `visibility.py` itself is unchanged in Stage B,
  confirmed by Security at the byte level (`git diff` empty across all three stage commits). All
  mechanical checks pass at this tip (body-layer: ruff/mypy 60 files/pytest 2041+4xfail). Security
  APPROVED, Performance APPROVED-MONITOR (`plans/emitter-visibility/security-stage-b.md`,
  `performance-stage-b.md`).

  **`#needs-flight`, not fully closed**: same outstanding sortie as `[[AC-B8]]` — whether
  `S_EVENT_SHOOTING_START` retriggers mid-burst — plus the cockpit judgement no fixture reaches:
  whether *"taking fire"* vs. *"something firing, far"* reads right in the moment, and whether a
  firing section's clustering (one `count_bucket` cluster at range, per `[[BL-B72]]`'s existing
  cardinality answer) looks sane with several units shooting at once. Clear this tag once flown.

  **The gate change is `[[BL-B72]]`'s and is already paid for by it.** What this entry adds is the
  *event channel*: a production firing-events Hook (the 2026-09-25 probe already confirmed
  `world.addEventHandler` is reachable from the `"scripting"` state, `register: ok=true`), a
  collector-side emitter state machine with a latch and a watchdog, and the schema/receiver/endpoint
  triple. Blocked on `[[AC-B8]]`.

  **Two things the plan establishes that are easy to get wrong:**

  - **A sub-poll burst must be latched.** `START` and `END` can arrive in the same 1 Hz drained
    batch; discarding that as already-over makes short bursts invisible. The collector holds the
    entry for `FIRING_MIN_VISIBLE_S`. Unrelated to `[[BL-B63]]`, which is a *rate* split.
  - **The existing threat path cannot prioritise this contact.** `threat.envelope_for()` keys on
    classification, and a `PRESENCE`-only contact matches no envelope, so it lands in
    `callouts.py`'s lowest threat band — burying the most urgent thing in the scene. A
    `CONTACT_FIRING_SEEN` event kind with its own priority is required, not a reuse.

  **The event names the player as its target when it is shooting at us**, confirmed live by the
  closed probe, so *"taking fire, two o'clock"* versus *"something firing, two o'clock, far"* needs
  no inference.

  Related: `[[BL-B72]]` (the shared emitter bypass and the burning emitter), `[[BL-B74]]` (the SAM
  half, which shares this entry's channel), `[[AC-B8]]` (the channel itself), `[[BL-2]]` (what
  decays afterwards).

  **A live sortie exercised the `#needs-flight` cockpit-judgement question above and found a real
  defect, not a pass.** `docs/acceptance/2026-10-20-sortie-feedback.md` F6/F6-follow-up, fixed on
  `fix/taking-fire-visible-shooter` (DoD-passed, not yet flown): a Leopard-2A5 at 1,073 m firing at
  ownship, admitted
  as an ordinary ungated contact (no emitter bypass needed to see it — the opposite of the
  bypass-needed case this entry's own fixture coverage exercised), never produced "taking fire" at
  all. Root cause: `targets_ownship_by_object_id` and the provenance fold both read the
  `targets_ownship`/firing facts only when `VisibilityResult.emitter_kind is not None` — i.e. only
  when the bypass had actually fired — discarding the fact for the easiest-to-see shooters.
  Same-shaped gap for the "firing at others" wording, fixed in the same branch's second half
  (`PROVENANCE_EMITTER_FIRING_VISIBLE`): a visible unit firing at something other than ownship was
  reported as an ordinary contact instead of "…, firing." Full account:
  `plans/taking-fire-visible-shooter/{debug,implementation,review,review-2}.md`. Classification
  tier is unaffected by either fix (asserted in tests); `visibility.py`/`emitters.py`/`gaze.py` are
  untouched.

  **`#needs-flight` carries forward, narrower than before.** This sortie closed the "does the
  bypass-needed wording read right" half implicitly (it was the visible/no-bypass half that broke);
  what is still outstanding is this *fix* itself (not yet flown) plus the two questions this entry
  already carried: whether `S_EVENT_SHOOTING_START` retriggers mid-burst, and whether a multi-unit
  firing section's clustering looks sane in the moment. All three can likely clear on one sortie.
