## Security Plan Review: dcs-driven-los (X-B29)

Reviewed branch `feature/dcs-driven-los`, tip `5c755b144758aa71da9690bab503a2283ec5d8e4` (verified
via `git rev-parse feature/dcs-driven-los` before reading; the agent worktree itself landed on
`main`, so the plan and the Lua/Export sources cited below were read from a `git archive` snapshot
of that tip, not the worktree's checkout). Also read `plans/dcs-driven-los/plan.md` on `main` far
enough to confirm it differs from the branch version (the branch's §7–§17 revisions are absent on
`main`) — noted per the task's instruction, not touched.

### Dependencies Checked

No new dependency. The plan adds a new Lua Hook listener (stdlib `LuaSocket`, already vendored and
in use by `Export.lua`), a new FastAPI endpoint on the existing collector (`aircraft-layer/src/api/
server.py`, existing stack), and schema/client additions in already-present packages. `/extract-
plan-deps`-equivalent grep over the plan found no `pip install`, new package, or new library
language. **No CVE check required.**

### Design Findings

**1. The headline question — is a validated `string.format("%d", clamped_fov)` splice into a
`dostring_in` snippet injection-proof? Yes, for code injection specifically, conditional on the
clamp being genuinely total — and the plan's own statement of "total" is incomplete in a way that
matters.** — **Medium** — must be addressed before Implementer starts, not blocking the plan itself

- **`%d` output is injection-safe by construction, independent of how strange the input is.**
  Lua 5.1's `string.format("%d", x)` (a thin wrapper over C `sprintf`) can only ever emit an
  optional leading `-` followed by decimal digits, or raise a Lua error. There is no way for a
  `%d` conversion to emit a quote, bracket, `]==]`, `end`, `;`, or any other character that could
  close the surrounding fixed template early or open a new statement — regardless of whether the
  underlying number is huge, negative, zero, or garbage. This holds **only if `FIXED_TEMPLATE` has
  exactly one `%d` and nothing else is ever interpolated** — see Finding 3.
- **The actual exploitable-shaped risk is not injection, it is clamp totality against NaN/Inf —
  and a naive clamp is known to fail exactly this case.** §17 states "the clamp must be total... a
  non-number, a NaN, a negative, an absurd value... all have to come out as a legal integer in
  `[5, 180]`" but does not specify *how*. The obvious Lua idiom,
  `math.max(MIN, math.min(MAX, x))`, **silently fails for NaN**: every comparison against NaN is
  false in IEEE 754, so `math.min`/`math.max` built from `<`/`>` pass NaN through unchanged. This is
  the exact class of bug the task brief points at (today's unguarded `array.frombytes()` truncation
  killing the audio worker thread on an untotaled edge case) — an implementer who clamps with the
  idiomatic one-liner reproduces that failure mode here.
  - Whether `tonumber()` on an inbound string can even produce a Lua NaN/Inf here is itself
    platform-dependent: Lua 5.1's `tonumber` delegates to the C runtime's `strtod`, and C99-
    conformant `strtod` (new MSVC Universal CRT, glibc) parses `"nan"`/`"inf"`/`"infinity"`
    case-insensitively; pre-2015 MSVC CRT does not. DCS's bundled Lua/CRT version is not something
    this review can determine from source — **the implementer must test this directly against the
    actual Windows DCS install** (`tonumber("nan")`, `tonumber("inf")` from a debug print in the
    Hook state) rather than assume either behavior.
  - **Consequence if the clamp fails on NaN:** casting a Lua NaN to a C `int` for `%d` formatting is
    undefined behavior in C; in practice (x86/SSE2) this deterministically yields `INT_MIN`
    (`-2147483648`), not a crash — but that is still a legal-looking, very wrong integer spliced
    into `PB_LOOK_FOV_DEG`. The poll snippet (per §9b) is a fixed literal that is not stated to
    re-validate the global it reads — so a corrupted FOV would flow straight into the wedge-vs-
    bearing comparison.
  - **This is where it actually matters for the design's own stated safety property.** §10 is
    explicit that cost is bounded by the query *cone*, and that the whole point of cone-scoping is
    to avoid the measured ~4.3–4.9 ms, frame-stuttering full-bubble query. A FOV of `-2147483648`
    half-angle, read into whatever bearing-difference comparison the fixed poll snippet uses, is at
    minimum a degenerate wedge and at worst (depending on how the comparison is written —
    `abs(diff) <= fov_half_deg` with a negative `fov_half_deg` would normally admit *nothing*, but
    a modular/wrapped bearing comparison could behave differently) a path back toward exactly the
    unbounded query this plan exists to close.
  - **Mitigated, not eliminated, by `MAX_SIGHTLINES_PER_CALL = 128`.** §10 keeps this cap as "a
    blow-up guard, not a policy" — and it is the actual backstop here: even a fully-degenerate wedge
    is bounded at ~3.2 ms per §10's own table, not unbounded. This is why the finding is Medium, not
    a plan-blocking Reject — the cost-safety property survives via the independent cap even if the
    clamp has this gap. It does **not** excuse leaving the clamp gap in; it changes the consequence
    from "frame stutter" to "silently wrong, degenerate LOS coverage for however long until the next
    pushed value," which is its own (smaller) correctness problem the plan's own honesty requirement
    (`hour_used`/`fov_half_deg_used` in the trace, §9b/§12) is designed to make visible rather than
    silent.

  **What the implementer owes, concretely** (this is additive detail on top of §17's own "what the
  implementer owes this decision," not a reopening of it):
  - Write the clamp with explicit NaN/Inf checks before any comparison — e.g. `if type(x) ~=
    "number" then return DEFAULT end; if x ~= x then return DEFAULT end` (the standard Lua
    self-inequality NaN test) `; if x == math.huge then return MAX end; if x == -math.huge then
    return MIN end` — then the ordinary bounds clamp. Do not rely on `math.min`/`math.max` alone.
  - Test the clamp directly against `0/0`-style NaN, `math.huge`, `-math.huge`, a non-numeric
    string, `nil`, a table, and a huge finite number — not just in-range values — exactly as §17
    already asks, but the test list above should include NaN/Inf explicitly since that is the
    specific case a naive implementation gets wrong.
  - Wrap the clamp-and-format call in `pcall` (mirroring `Export.lua`'s own `safe_call` pattern)
    so that even an unanticipated error path fails to the default FOV rather than throwing out of
    the per-frame Hook poll loop — the same silent-failure risk the task brief names explicitly.

**2. No existing precedent in this codebase for splicing a runtime value into a `dostring_in`
code string — this would be the first.** — informational, supports Finding 1's "must get right"
framing rather than being a separate blocker

`petrobrain-f10-commands-hook.lua`'s `REGISTRATION_CODE`/`POLL_CODE` and `petrobrain-mission-
telemetry-hook.lua`'s `VELOCITY_CODE` are all checked — none contains a `string.format` call or any
other runtime-value interpolation into the executed string; they are genuinely fixed literals, as
their docstrings claim. `Export.lua`'s `handle_petrovich_search_command` — the precedent §9/§16
leans on for "a runtime value already selects among audited literals" — is not actually the same
mechanism: `mode` there is checked against a closed string set and used only to **branch** between
direct `performClickableAction` calls in the Export state; it never flows into a Lua code string at
all, let alone one passed to `dostring_in`. So the precedent establishes that a validated LAN value
may drive real cockpit behavior through a closed set — true, and a fair precedent for "commands,
not strings" — but it does **not** establish that this codebase has ever formatted a runtime value
into a `dostring_in` snippet before. §17's splice is new ground. That is consistent with the user
having made an informed tradeoff knowingly (the architect's recommendation is recorded and the
decision stands per the task framing) — recorded here only so the next reader does not
over-read the precedent as closer than it is.

**3. The single-substitution-point invariant has no structural enforcement, only a stated
intent and a recommended test.** — **Low**, recommend fixing in this feature (not blocking)

§17 says "The template is a module-level constant with exactly one substitution point... adding a
second substitution later is the change that would make this genuinely unsafe, so say so at the
definition site." Nothing described makes that mechanically checkable beyond reading the constant.
**Recommended action:** add a unit test that counts `%` directives in `FIXED_TEMPLATE` (e.g. via
`string.gmatch(FIXED_TEMPLATE, "%%[a-zA-Z%%]")`) and asserts there is exactly one `%d` and no other
specifier, so a future edit that adds a second substitution point fails CI rather than being caught
only by a reviewer reading a comment. Cheap, and it is exactly the kind of guard the plan's own
"say so at the definition site" asks for but doesn't mechanize.

**4. Validation order (body-layer → collector → Hook) is defense-in-depth, not defense-only-once —
confirmed sound, no finding.**

Per §9b/§12: body-layer validates `hour: 0..11` / `fov_half_deg: 5..180` before `POST`; the
collector range-validates again (generalizing the existing `_VALID_SEARCH_MODES` tuple-membership
pattern to a range check — same pattern already shipped for `petrovich_search`); the Hook validates
and clamps a third time before the splice. Three independent layers, each capable of catching a
different class of malformed input (a body-layer bug, a collector bug, a corrupted/malformed UDP
datagram) — this is the right shape and nothing in the plan skips a layer. The Hook's own clamp
(Finding 1) is the layer that actually matters for the injection question, since it's the one
immediately adjacent to the splice, but all three being independently total is still worth the
three-line cost.

**5. Repeated/duplicate directives — one real cost-as-safety risk not covered by the plan's own
text.** — **Low/Medium**, recommend addressing in this feature

The plan specifies push-on-change on the *sending* side (body-layer only re-POSTs when the resolved
hour/FOV differs, §9b) but says nothing about how the Hook's receive-side loop handles a burst of
queued UDP datagrams in one frame. `Export.lua`'s existing `poll_command_socket` pattern drains
*every* queued datagram in a `while true do ... receivefrom() ... end` loop per frame, and for
`petrovich_search` that's cheap because the handler only does direct `performClickableAction` calls
— no bridge round trip. If the new look-direction listener mirrors that same drain loop but calls
`net.dostring_in` once per received datagram (to push `PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG`), then a
burst of duplicate or retried datagrams in a single frame — a body-layer retry bug, a flaky network
layer, or simply two logically-distinct pushes landing in the same frame — would trigger multiple
bridge calls in one frame. Finding 3 in this plan's own risk list (referenced via §14, "the 18–20
ms payload-indifferent bridge tail... is not ours") suggests each `dostring_in` call carries a fixed
overhead regardless of payload; N queued duplicate directives in one frame could cost N× that tail,
which is a frame-stutter risk from the project's **own** code (a retry bug), squarely inside this
review's scope per the task's framing ("do not build threat models requiring an attacker already on
the user's machine — but do treat a malformed value from this project's own code as an ordinary
case").

**Recommended action:** in the new Hook's receive loop, drain the socket fully but **coalesce to at
most one `dostring_in` setter call per frame** (keep only the last-received value, matching the
"push on change" intent the sender already has), rather than firing one bridge call per datagram
received that frame.

**6. No-omniscience — verified against current code, not accepted on the plan's assertion.**

Checked `body-layer/src/detection_trace_writer.py` and `body-layer/src/belief/percept.py` directly.
`detection_trace_writer.py`'s own docstring confirms it is the one deliberately-dual-sighted module
(reads both `perception.detection_trace.DetectionTrace`, ground truth, and `belief.contacts.
Contact`, belief) and is explicitly read-only/one-directional: "No ground-truth field is ever passed
into `ContactStore.ingest`, `Percept`, or any `Contact` field." Grepped `belief/percept.py` and
`perception/visibility.py` for any existing `los`/`terrain_clear`/`building_clear` reference —
none exists yet (expected, pre-implementation), and the existing module docstring for `visibility.
check_visibility` independently confirms the gate ordering the plan relies on: gate 0 is gaze,
evaluated first; `TERRAIN_LOS` is the last gate recorded (`_record(GateOutcome.TERRAIN_LOS)`),
consistent with "~10 of 172 units ever reach the LOS gate." The plan's claim that
`detection_trace_writer.py` needs no change because the new field arrives on the ground-truth
(`DetectionTrace`) side holds against the actual architecture, not just the plan's narrative — LOS
remains a perception-side fact about true position, never becomes a belief-side channel.

**7. Unauthenticated LAN command channel — accepted, consistent with stated project scope, no new
finding beyond what's already true of `petrovich_search`.**

The collector's command surface is already unauthenticated LAN/loopback by design
(single-user, stated scope). The new listener adds one more UDP-received, numeric-only command on
top of an already-shipped pattern (`try_open_command_socket`, non-blocking `receivefrom()`). It is
bound to `127.0.0.1` per §14, same box as DCS — no new network exposure. The worst a malformed
directive can do, given Findings 1 and 5 are fixed, is a bounded-cost degenerate wedge for one push
interval, self-correcting on the next valid push and visible in the trace (`hour_used`,
`fov_half_deg_used`) rather than silent. That is an acceptable risk profile for this project's
stated scope.

### Verdict

**APPROVED, with two required fixes to carry into the Implementer handoff** (not a plan rejection —
the design is sound; these are implementation-level "must get right" items the plan itself already
flagged as load-bearing but under-specified):

1. The Hook-side FOV clamp must explicitly handle NaN and ±Infinity (self-inequality / `math.huge`
   checks) before any min/max comparison, not rely on `math.min`/`math.max` alone, and must be
   wrapped so no error path leaves the previous value in place silently (Finding 1). Verify
   `tonumber("nan")`/`tonumber("inf")` behavior against the actual DCS-bundled Lua/CRT before
   assuming either outcome.
2. The new Hook's receive loop must coalesce multiple queued look-direction datagrams per frame to
   at most one `dostring_in` setter call, not one per datagram (Finding 5).

Recommended, non-blocking: a unit test asserting `FIXED_TEMPLATE` contains exactly one `%d` and no
other format specifier (Finding 3).

### Rejection Reason (if applicable)

Not applicable — approved. The two required fixes above are Implementer-stage requirements, not
grounds to send the plan back to Architect; §17's decision (splice over digit-dispatch) stands as
the user's informed call and is not being re-litigated here.
