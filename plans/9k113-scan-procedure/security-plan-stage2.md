## Security Plan Review: 9k113-scan-procedure (BL-B89 Stage 2)

Plan: `plans/9k113-scan-procedure/plan-stage2.md`. Precedent: Stage 1's
`plans/9k113-scan-procedure/security-plan.md` (APPROVED).

### Dependencies Checked

No new dependency. `grep -niE 'dependenc|pip install|third.?party|stdlib only|new package|wheel|pyproject'`
over `plan-stage2.md` found nothing — the plan's own "Affected Modules"/narrative touches only
existing `audio-adapter` (`vocabulary.py`, `command_matcher.py`) and `body-layer`
(`belief/crew_console.py`, `belief/voice_commands.py`, `tuning.py`) modules. No new package
import, no new file format, no new network client.

### Design Findings

This stage is a new voice-command surface (slotted `look`/`sight`/`what is at`) plus a reused
confirm band and a reused OBSERV-on effector sequence. Walking it against the in-scope
categories:

- **Code execution / deserialization** — none. No `eval`/`exec`, no new parser of untrusted
  binary data, no new deserialization path. The spoken distance/slots are read off a Whisper
  transcript (already-reviewed STT boundary, unchanged by this plan) by closed-vocabulary
  lookups, not interpreted as code at any point.

- **Parsing and bounds of the spoken distance/slots — checked against the actual functions, not
  assumed:**
  - `parse_clock` (`audio-adapter/src/vocabulary.py:988`) only recognises a number word from the
    closed `_CLOCK_WORD_TO_HOUR` table (forward hours only, by construction — no rear-hemisphere
    hour can resolve). A huge, negative, or NaN "distance" cannot reach it; there is no numeric
    parsing here at all, only a dictionary lookup over a fixed vocabulary.
  - `parse_range_km` (line 1045) is a bounded integer lookup: `1 <= value <= 20`, explicitly
    checked, `None` otherwise — "three" heard as "thirty" cannot occur because "thirty" is not in
    `_RANGE_NUMBER_WORDS` and digit strings are range-checked the same way. No float, no negative,
    no NaN path exists; the slot type is `int`, never a raw string handed downstream.
  - `parse_sector_word`/`parse_relative_word` (lines 1133/1162) are membership tests against
    fixed 8-word and 4-word tuples. Nothing outside those literal words can produce a value.
  - The new `_where_slot_count(...) > 1` guard (precedent already in `command_matcher.py:628`,
    reused verbatim per the plan) rejects a transcript carrying two conflicting `where` slots as a
    detected recognition error rather than guessing — the same shape already proven for
    `follow`/`report`/`select_target` (`command_matcher.py:705,729,765`).
  - **Conclusion: there is no reachable "huge/negative/NaN distance" case.** Every slot value that
    can exist is drawn from a small closed table or a pre-bounded integer range before it is ever
    stored in the `slots` dict the plan threads through `PendingPointRequest`/
    `PendingConfirmation.observ_request`. The one new piece of geometry (the 45°-wide compass
    wedge helper) is a pure, deterministic conversion of an already-bounded compass word — no new
    input surface.

- **The confirm path — can a "yes" trigger anything beyond OBSERV on?** Read against the actual
  affirm branch the plan specifies (`handle_transcript`'s pending-confirmation block,
  `body-layer/src/belief/crew_console.py:4028-4051` for the existing shape; the plan's new
  `observ_request` branch is ordered the same way, checked before the `contact_pick`/`token`
  branches). The new branch's body is exactly two calls: `self._handle_observ_on()`, then —
  conditionally, only if that call did not itself refuse — `self.pending_point_request =
  PendingPointRequest(slots=pending.observ_request, ...)`. `pending.observ_request` is the
  original, already-bounded `slots` dict parsed at the time `look` was first spoken, not
  re-parsed from the affirming utterance; the affirming "yes"/"observ on" carries no payload of
  its own. So a "yes" here can do exactly one of: (a) turn OBSERV on (an existing, already-
  reviewed effector sequence, gated by `_handle_observ_on`'s own `GUIDANCE_NOT_READY` refusal), or
  (b) additionally queue a deferred point request using slots that were fixed before the confirm
  round-trip started. There is no path from the affirm branch to any other effector (weapons,
  observ_off, a different sector) — it is a narrower action set than the general
  `pending.token` → `handle_command(pending.token, ...)` dispatch used by every *other* confirm
  kind, not a wider one.
  - The one piece of new control flow here — treating `token == "observ_on"` as an additional
    affirm condition, scoped to `pending.observ_request is not None` only (per the plan's own
    "fix, scoped to this one pending-confirmation kind only") — still only reaches the same
    two-call body above. It does not let `"observ on"` (or anything else) smuggle in a different
    action; it only changes which spoken words count as yes for *this* confirmation.
  - "No" and timeout both drop the pending request with no dispatch at all (inherited, unchanged
    code paths) — nothing to assess beyond what Stage 1's review already covered for
    `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S`.

- **Access to the computer / file paths** — none. No new file I/O. `config/defaults.toml`
  regeneration is the existing `tools/generate_defaults.py --write` mechanism, unchanged in kind.

- **LAN port-scanner surface** — none. No new listener, endpoint, or socket. The `look`/`sight`
  vocabulary change reaches `audio-adapter`'s existing `POST /transcribe` path (already reviewed)
  with no change to that endpoint's own bounds (body size, auth posture) — this plan only changes
  what `match_transcript` can return, not how the HTTP surface accepts input.

- **LLM prompt injection** — none. Nothing in this stage is text an LLM reads. The transcript is
  consumed entirely by deterministic closed-vocabulary matching
  (`command_matcher.py`/`vocabulary.py`) and dataclass-typed state; no free text reaches a brain-
  layer prompt as a result of this plan. (Contrast: if a future stage let a spoken place name
  resolve to an arbitrary landmark string fed into a brain prompt, that would need this check
  again — explicitly out of scope here, since places are restricted to o'clock/compass only.)

- **Dependency/framework CVEs** — n/a, no new dependency.

- **Secrets/credentials** — none introduced or referenced.

- **Tunable bounds** (`POINT_READY_TIMEOUT_S`, `POINT_SWEEP_COUNT`, `POINT_DISTANCE_BAND_HALF_KM`
  per the plan's "State"/"The sweep itself" sections): all three are local-config-only, requiring
  a hand edit to `config/tuning.toml` on the single user's own machine to change — not externally
  reachable, consistent with Stage 1's review of the same tunable-bounds category. Worst case of a
  pathological value (e.g. `POINT_SWEEP_COUNT` tuned absurdly high) is a long-running or
  never-clearing bounded look, not a crash, not privilege escalation, not a listener change — a
  correctness/availability-of-the-cockpit concern, not a security one in this single-user/LAN
  threat model. Per the X-T26 convention referenced in the plan, each needs declared `lo`/`hi` and
  a `#:` comment at implementation time; whether the chosen bounds are *sensible* (e.g. whether
  `POINT_SWEEP_COUNT`'s `hi` is tight enough to avoid an absurdly long standing look) is a
  correctness/tuning judgement, passed to Reviewer below.

### Passed to Reviewer

The following are player-experience/correctness matters, not security findings, and carry no
verdict here:
- Whether the `relative`-vs-bounded-clock/compass asymmetry correctly reflects the user's
  transcript (the plan itself flags this as the risk most likely to be "fixed" into uniform
  behaviour by a future reviewer unfamiliar with the explore-notes).
- The "ready" ambiguity — `self.sight_ready` vs. `home_phase is SIGHTING` — which the plan
  resolves as "wait for both," and whether the Implementer actually wires the drain condition
  that way rather than the single-lamp reading the plan itself calls out as the likely wrong-cut.
- Whether `POINT_SWEEP_COUNT`'s/`POINT_DISTANCE_BAND_HALF_KM`'s chosen default values and bounds
  make sense operationally (not a security bound, a gameplay-pacing one).
- The co-moving-fields table (new sweep-tracking state threaded through every `OpticState`/
  `replace()` construction site) — whether it is actually built and checked per root
  `CLAUDE.md`'s rule, since a missed site here would produce a stale-aim bug, not a security gap.
- Compass-bearing wedge conversion correctness (45° vs. 30°, body-relative conversion) — a
  geometry correctness question, not a parsing/bounds one; already confirmed above that it has no
  untrusted-input surface.

### Verdict

APPROVED
