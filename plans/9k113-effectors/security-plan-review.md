## Security Plan Review: 9k113-effectors (BL-B66)

Reviewed against `plans/9k113-effectors/plan.md` (fe45b625, the 2026-10-21 architect revision,
text above the `---` divider only) and `plans/9k113-effectors/explore-notes.md`.

### Dependencies Checked

No new runtime dependency. `grep -niE 'dependenc|...'` over the plan surfaces only the DCS-BIOS
discussion (§0, Decision 1): explicitly evaluated and recommended as **reference-only**, not a
runtime dependency — the investigator's own finding
(`aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`) plus the plan's own
reasoning (GPL-3.0, second install step, second patch-tracking cadence, buys no capability this
entry doesn't already have through `Export.lua`). Decision 1 is still formally open but both
outcomes keep the HTTP contract identical and neither introduces a package into any
`pyproject.toml`. No CVE search needed — nothing new is pulled into the dependency graph either way.

### Design Findings

**1. The `cockpit_switch` op is specified as a generic, unvalidated `(device, cmd, value)`
write-through to `performClickableAction`, with no stated allow-list — this contradicts an
explicit, standing architectural invariant for this exact subproject.** — **HIGH** —
`aircraft-layer/CLAUDE.md`'s own "What this is" section states the invariant this plan is adding
to: *"every write path carries only a small, fixed vocabulary (an opaque display string, a search
mode, a base64 WAV blob, or one of three allowed F10 command tokens) — no aircraft state, no
free-form commands, no code, **no general-purpose remote-exec surface**."* Every existing write
path honours this by construction:
   - `petrovich_search`'s `mode` is checked against exactly `{"forward", "boresight"}` before any
     DCS call (`handle_petrovich_search_command`, `Export.lua` L628-632) — unknown values are
     logged and dropped, never reach `GetDevice`.
   - F10 commands are validated against a fixed `ALLOWED_COMMANDS` vocabulary before enqueueing
     (`aircraft-layer/CLAUDE.md`, `f10_command_receiver.py`).

   The plan's own module list (§ Affected Modules, aircraft-layer) specifies `cockpit_switch` as
   `{"device", "cmd", "value"}` with "`400` on a malformed body" as the *only* stated check — that
   is a type/shape check, not a value check. Nothing in the plan restricts which `device`/`cmd`
   pairs the Lua dispatch or the HTTP API will accept; both are described as forwarding straight
   to `GetDevice(device):performClickableAction(cmd, value)`. That is exactly the "general-purpose
   remote-exec surface" the subproject's own doc says must not exist, and the plan does not
   discuss dropping that invariant — it reads as an oversight, not a deliberate, justified
   departure (root `CLAUDE.md`'s own "Do not reinvent the wheel": a departure from an existing
   convention needs a stated reason; none is given here).

   This is not a passive risk — the six args this entry names are not uniformly low-stakes. Arg
   673 is the weapon safety bar (ARMED/SAFE) and 955/885/761/773 are the guidance-unit power-up.
   Without an allow-list, any caller reaching the aircraft-layer HTTP port on the LAN — a bug in a
   future body-layer code path, a brain-layer tool call built carelessly on top of this facility
   later (the plan's own "Second-order effect" section anticipates `BL-B67`/`BL-B80` reusing this
   exact channel), a test harness pointed at the wrong host, a typo'd device/cmd literal — can
   flip **any** clickable device/command in the cockpit, not only the six this entry intends,
   including devices this entry never reasoned about (fuel, engine, other weapon stations). On a
   LAN-only, single-player project the attacker model is "a bug or a careless future caller," not
   a remote adversary, but the blast radius of a bug is still every switch in the cockpit instead
   of six named ones — and the fix is cheap.

   **Required fix**: constrain `cockpit_switch` to a fixed set of `(device, cmd)` pairs this entry
   actually needs — the six named in the plan (773, 761, 885, 955, 886, 673 on devices 6/`WEAP_SYS`
   and 7/`I9K113`) — and reject anything else, the same posture `petrovich_search`'s mode-enum and
   the F10 vocabulary already use. Two defensible places to enforce it, and the Lua side is the
   one that must not be skipped:
   - **`Export.lua`'s dispatch** (mirrors `handle_petrovich_search_command`'s mode check) — this is
     the layer that actually touches the sim, so it is the one that must hold the allow-list even
     if every layer above it is later found to validate correctly. `value` constrained to `{0, 1}`
     at the same point.
   - Optionally also the aircraft-layer HTTP API (`POST /command/cockpit_switch`), as defense in
     depth and to turn a bad request into an honest `400` instead of a silently-dropped/ignored
     Lua-side rejection — but this does not substitute for the Lua-side check, since the HTTP layer
     is not the layer with an unsandboxed host.

   The plan's own "general, reusable" framing for this facility (§0, "Second-order effect") still
   holds with an allow-list — `BL-B80`/`BL-B67` extend the allow-list with their own args when they
   land, rather than removing the one check that keeps this from being a blanket cockpit-write
   primitive.

**2. ARMED is gated correctly — pilot-commanded only, no automatic trigger.** — not a finding,
confirmed clean. §3/Co-moving Fields table states `weapon_safety_commanded` is set only by
`_handle_engage`'s existing spoken attack-run command or the two new "weapons armed"/"weapons on"
voice commands — "**Not** on any internal attack-run state" (explore-notes point 7, carried
verbatim into the plan). SAFE is pilot-commanded only by the same table. This matches the task
brief's requirement exactly and needs no change.

**3. Failure modes around a dropped cockpit write are handled by raising, not swallowing — correct
posture, consistent with precedent.** — not a finding. The plan explicitly adopts
`trigger_petrovich_search`'s raise-on-failure posture ("a dropped write is a real behavioural gap")
rather than the opaque-display-string swallow-to-`None` posture used elsewhere. Combined with every
switch write being an absolute set rather than a relative toggle (confirmed live by the 2026-10-17
probe's restore pass), a failed or partially-applied power-up sequence is safe to retry from
wherever it left off — re-asserting an already-ON switch is a harmless no-op, so there is no
"half-sequenced and stuck" state the plan leaves unaddressed. Low residual risk, not blocking: the
plan does not spell out what `power_up_stage` does on a raised exception mid-`advance()` (does the
poll loop retry next poll, or does the stage silently stall) — worth the Implementer stating
explicitly, but not a design gap given the idempotent-write property above.

**4. `weapon_safety_observed`/`observ_observed` readback lag is named and deliberately deferred,
not silently ignored.** — not a finding. §3 and the Co-moving Fields table both flag that no
consumer in this entry reads the confirmed-state readback, and explicitly hand `BL-B67` the
obligation to check it before trusting ARMED/sight-engaged state before firing a real missile.
This is the right way to carry a risk forward — named, not buried.

**5. Transport/socket exposure is unchanged from existing precedent.** — not a finding. The inbound
command socket (`COMMAND_HOST = "127.0.0.1"`, `COMMAND_PORT = 7793`, `Export.lua` L162-163) is
loopback-only — only the collector process on the same box can reach it. The LAN-reachable surface
is the HTTP API, which is the same exposure model every other write path in this subproject already
has (`/command/petrovich_search`, `/text/push`, `/audio/play`). This plan does not widen that
surface; finding 1 above is about what is accepted once a caller reaches it, not who can reach it.

### Verdict

REJECTED

### Rejection Reason

Finding 1 must be addressed before Implementer starts: `Export.lua`'s `cockpit_switch` dispatch
needs a fixed allow-list of `(device, cmd)` pairs (the six args this entry names) and a `value`
range check (`{0, 1}`), mirroring the mode-enum check `handle_petrovich_search_command` already
uses. This is a small, well-precedented addition — not a redesign — and keeps the new channel
inside the "small, fixed vocabulary, no general-purpose remote-exec surface" invariant
`aircraft-layer/CLAUDE.md` already states for every other write path in this subproject. Everything
else in the plan (ARM/SAFE gating, failure posture, deferred-readback risk, dependency posture) is
sound and needs no change.
