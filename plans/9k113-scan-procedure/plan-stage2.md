# BL-B89 Stage 2 — pointing the 9K113 at a known place

Base: `main` at `406c1ce6` (`feature/9k113-scan-procedure`'s own tip; Stage 1 and `[[BL-B98]]`'s
fix merged into it). Supersedes Stage 2's one-paragraph sketch in `plan.md` — that section now
points here.

**Revised 2026-10-25**, per `explore-notes.md`'s "Stage 2 plan decisions, 2026-10-25 (verbatim)":
*"Correction: look x o'clock. -> scan not in line, but that 30 deg sector near to far. S shape
when needed by FOV."* plus approval of the four other open decisions below. The correction
replaces this plan's "point-aim along one exact line" mechanism for `look <o'clock>`/
`look <compass bearing>` with a bounded run of Stage 1's own sector-search geometry — see
"`look <o'clock>`/`look <compass>`: a sector, near-to-far, S-shape" below, which supersedes the
struck "fork collapses" section and the "pointed" `OpticState` design that followed from it.
Everything **not** touching that mechanism (vocabulary/matcher design, OBSERV gating, the
confirm-band reuse, attack-run refusal, supersession) is unchanged and still in force.

### Goal

Let the pilot aim the 9K113 at a named place by voice — an o'clock hour, a compass bearing, or
one of the sight's own sectors (left/right/ahead) — instead of only the idle search cycle Stage 1
built, and have Petrovich search that place, report what he finds (or doesn't), and resume
whatever he was doing before.

### What's already built — read before assuming any of this is new

- **The sight-vs-eyes split for guidance during an attack run already exists and needs no new
  code.** `optic_policy._apply_guidance`'s sight ceiling is re-derived from `state.home_phase`
  on *every* call: a sight-ranked `requested_optic` is silently capped to `BINOCULAR_OPTIC`
  whenever `home_phase is not OpticPhase.SIGHTING` (`optic_policy.py` lines ~2598-2609). This is
  exactly the explore-notes answer 5 rule ("during attack run, keep the sight on the target. If
  OBSERV off, eyes/binoculars on the target") — **already shipped, before this plan, for the
  attack-run case.** Stage 2 adds nothing here; see "Attack-run interaction" below for what that
  means for a *pointing* command issued mid-run.
- **`ScanPlan.fixed_look_at`** (`perception/gaze.py`) is the attack-run's own continuous-aim
  mechanism (`body.py`'s `_scan_plan_for`). **Not reused by this stage** — the 2026-10-25 Correction
  (below) replaced Stage 2's original "aim at one exact direction" design with a bounded run of
  Stage 1's own sector-search geometry, so this is no longer the precedent it once was. Left here
  only so a reader does not go looking for a connection that no longer exists.
- **The confirm-band mechanism** (`belief.voice_commands.classify_yes_no`/`PendingConfirmation`/
  `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S`, `crew_console.handle_transcript`) already
  handles "ask, then act on yes" with a timeout and a late-answer grace period — reused for the
  OBSERV-off case below via one new, narrowly-scoped `PendingConfirmation` payload, not a new
  mechanism.
- **The once-per-poll drain pattern** (`drain_pending_positional_replies`, Voice-latency
  instrumentation) — a queued effect that waits for a later condition (there: the speech channel
  clearing) and is checked once per poll, dropped on `self.refused`, never forced out early. The
  deferred point request below is the same shape with a different condition.
- **Slotted voice commands already parse exactly the pieces this needs**: `parse_clock` (o'clock
  hour), `vocabulary.parse_sector_word` (the 8 compass words), `vocabulary.parse_relative_word`
  (`left`/`right`/`ahead`/`full`), `vocabulary.parse_range_km` (an optional distance) — all four
  already exist, are already slot-parsed (not enumerated phrases) for `follow`/`report`/
  `select_target`, and `command_matcher.py` already has the exact ordering precedent
  (`follow`'s/`report`'s/`select_target`'s own slot-resolution branches, tried before the generic
  phrase table, in that order, for the documented reason: a clock-only phrase would otherwise
  collide with another family under the plain word-sequence score).

### Vocabulary design

**Measured, not assumed — a naive approach collides badly.** Adding `look`/`sight`/`what is at`
as ordinary literal `PHRASES` entries (the shape every existing sector/bearing token uses) was
tried against the real matcher (`audio-adapter/src/command_matcher.py::match_transcript`, patched
in a scratch script, not committed) before writing this section:

| transcript | naive literal-phrase result | why it's wrong |
|---|---|---|
| `"look one o'clock"` | `report_clock_1` @ 0.67, **ambiguous=True** | no `look`-family phrase exists to compete, so it drifts onto `report`'s nearest phrase |
| `"sight two o'clock"` | `report_clock_2` @ 0.67, **ambiguous=True** | same failure |
| `"look two o'clock three kilometres"` | no match at all | the combinatorial clock × distance space cannot be enumerated, same reason `follow`/`report` are slot-parsed instead |
| `"what is at two o'clock"` | `point_place` @ 0.60 (borderline, the exact `MATCH_FLOOR`) | works, but by luck of the literal phrase overlapping, not by design |

This is the same failure `follow`/`report`/`select_target` were built to avoid (their own module
comments: "9 clock hours × ... is in the hundreds/thousands, far past what a closed grammar can
list"). **Decision: `look`/`sight`/`what is [at]` get a dedicated slot-resolution branch in
`command_matcher.py`, in the same place and the same shape as `follow`'s/`report`'s/
`select_target`'s — not a `PHRASES` entry.**

**One token, dispatched by which `where`-slot fired** — the user's own final word on this
("`look <o'clock>` collapses," see below) means the sector form and the point form are one
command, not two:

```
_POINT_VERBS = ("look", "sight")   # "what" handled separately, see below

def _parse_point_slots(text) -> dict | None:
    slots = {}
    relative = parse_relative_word(text)   # left / right / ahead / full
    if relative is not None:
        slots["relative"] = relative
    clock = parse_clock(text)
    if clock is not None:
        slots["clock"] = clock
    sector = parse_sector_word(text)        # compass word
    if sector is not None:
        slots["sector"] = sector
    distance = parse_range_km(text)
    if distance is not None:
        slots["distance_km"] = distance
    return slots if slots else None
```

tried in `match_transcript` at the same point `follow`/`report`/`select_target` are, before the
generic phrase table, with the same `_where_slot_count(...) > 1` guard (`clock`+`sector`+
`relative` together is a detected recognition error, same shape an illegal bearing already
returns — asks again rather than guessing).

**`"what"` is not added to `_POINT_VERBS`.** It already anchors via the *existing* literal phrase
`"what do you see"` (the `report`/`describe` zero-slot fallback) — `"what"` is not in
`_REPORT_VERBS` (`("report", "describe")`), so it never enters `report`'s own slot branch either.
Giving `_parse_point_slots` a second, `"what"`-anchored entry point (verb-anchor on `"what"`,
require a `where` slot to fire, fall through unchanged — including to `"what do you see"` — when
none does) reaches `"what is at two o'clock"` and `"what do you see"` correctly without disturbing
either existing path: the first produces a `where` slot and resolves to `point`; the second
produces none and falls through exactly as before. Order this branch anywhere relative to
`follow`/`report`/`select_target` — `"what"` doesn't collide with any of their verb sets.

**What this means for the vocabulary tables** (`audio-adapter/src/vocabulary.py`):
- Remove `"look ahead"`, `"look left"`, `"look right"` from `PHRASES["scan_ahead"/"scan_left"/
  "scan_right"]` — `look` is no longer an alias of `scan`.
- No new `PHRASES` entries for the point family itself (it's slot-resolved, like `follow`), but
  `"look"`/`"sight"` need to reach `VERB_ANCHOR_WORDS` (derived from `PHRASES`' first words) and
  `to_prompt()`'s whisper bias (the "prompt in sync by construction" rule) — add one minimal
  calibration phrase each (e.g. `"point": ("look", "sight")`, unused for matching, read only by
  the derivation and the prompt builder) rather than skip the bias.
- **This is a vocabulary change** — `/command-map` needs a redraw at merge (the coordinator's own
  note); flagging it here so the Implementer doesn't have to rediscover it.

~~**`look <sector>` vs `look <place>`: the fork collapses for o'clock/compass.** The open question
this plan started with — is `"look one o'clock"` Stage 1's 30°-wedge sector or Stage 2's exact
point, swept near-to-far? — turned out not to need an answer. A point-scan along the bearing line
(near-to-far, "two proper sweeps of the area," answer 3) *covers* the sector reading: anything a
30°-wedge sweep centred on that hour would have found, a near-to-far sweep along the hour's own
centre line also finds, provided the sweep itself has some lateral width (which it must anyway —
Stage 1's own wide-optic FOV is not a zero-width ray). So: **`relative` slot (`left`/`right`/
`ahead`/`full`) → Stage 1's commanded-sector shape** (no exact aim line, bias the sight's own
search cycle to that wedge, unchanged from Stage 1); **`clock` or `sector` (compass) slot → Stage
2's pointing shape** (exact aim line, near-to-far two-sweep, optional distance narrows the start).
One token, dispatch on which slot fired, no separate "is this a sector or a point" judgement call
anywhere in the code.**~~

**STRUCK 2026-10-25 — wrong, corrected by the user directly.** *"Correction: look x o'clock. ->
scan not in line, but that 30 deg sector near to far."* The "exact aim line" half of this argument
is not what an o'clock/compass `look` does; it is Stage 1's own 30°-wedge **sector** search,
bounded to a fixed number of sweeps instead of run forever. See the replacement section
immediately below, which also settles what `relative` does (left as Stage 1's own open-ended
mechanism, not given the same bound) and why that asymmetry is deliberate, not an oversight.

### `look <o'clock>`/`look <compass>`: a sector, near-to-far, S-shape (correction 2026-10-25)

**The geometry already exists and already produces exactly this shape — confirmed by reading the
code, not assumed.** A single commanded o'clock hour already resolves, via
`_sight_commanded_sector`'s existing `ScanPlan.commanded_legs`-with-one-entry branch, to a 30°-wide
wedge centred on that hour: `_gaze_for_clock_hour`'s `half_width_deg` is `FOCUS_CONE_HALF_WIDTH_DEG`
(`perception/gaze.py`, `15.0`), i.e. a wedge spanning the full 30° between adjacent hours — this
*is* "that 30 deg sector," already built, not a new table. And `optic_policy.search_pattern`
(called by `_sight_in_regard_sweep` for every sight search leg) already produces the S-shape "when
needed by FOV": its own docstring derives the row count from `ceil(depression_spread /
fov_full_width_deg)` and alternates azimuth direction per row (`band_index % 2`) — one row when the
sight's FOV covers the whole near-to-far depression spread (typical at low AGL, per that
docstring's own worked example), several alternating rows when it doesn't. **Stage 2 adds no new
sweep-shape code; it reuses `_sight_commanded_sector` + `_sight_in_regard_sweep` + `search_pattern`
verbatim**, wrapped in a bound this idle-cycle machinery doesn't have on its own (see "The sweep
itself" below): run it for a fixed sweep count, not forever.

**`relative` (`left`/`right`/`ahead`/`full`) keeps Stage 1's own, unbounded mechanism —
deliberately not given the same bound.** Explore-notes item 2 names this directly: *""look
left/righ" -> the 9K113 left/right scan that Stage 1 implemented"* — i.e. `look left` sets
`ScanPlan.commanded_sector` exactly as `scan left` already can, and the sight's idle search cycle
runs against that sector exactly as it does today, open-ended, superseded only by a later command
(see "Supersession" below). Nothing in the user's answers equates `look left`/`look ahead` with a
bounded "two sweeps then report clear" lifecycle — that shape (answer 3, "two proper sweeps... say
'<where> clear'... continue") was described for the pointing/place case throughout, and the
Correction narrows only the *geometry* of the o'clock/compass case, not whether `relative` also
gets bounded. **So the asymmetry is a direct reading of the transcript, not an architect's
preference**: `look <relative>` is a standing scan mode (reuse, zero new state); `look <o'clock>`/
`look <compass>` is a one-shot bounded search with its own start/sweep-count/clear-or-report/resume
lifecycle (new, bounded state — see below). A `distance_km` slot given alongside a `relative` word
is ignored — `relative`'s own mechanism has no notion of a range band to narrow, consistent with
leaving it unchanged.

**Compass bearing width: 45°, not 30° — by the same derivation the o'clock wedge already uses,
not a separate judgement call.** `_gaze_for_clock_hour`'s 30° wedge is exactly the spacing between
adjacent o'clock hours (12 per 360°) — each hour owns the slice of compass between its neighbours.
`parse_sector_word`'s 8 compass points are spaced 45° apart, so the same reasoning gives each one a
45°-wide wedge (half-width `22.5`), not the o'clock figure. This needs one new, small helper
alongside `_gaze_for_clock_hour` — a body-relative wedge centred on an absolute compass bearing,
converted from true to body-relative using the same heading subtraction `body._active_gaze`
already does for a compass-absolute `scan north`/`scan bearing 320` — left to the Implementer to
place next to `_gaze_for_clock_hour` rather than pinned here, since it is a one-line variant of an
existing conversion, not a new geometric idea.

### `scan`/`look` split (explore-notes items 1-3)

- **`scan <where>` is unchanged.** Petrovich's own existing logic still decides which optic
  (eyes/binoculars/9K113) serves it — today's `scan_*` feeding both the naked-eye gaze claim and
  the sight's commanded sector (`_commanded_or_default_sector` reading `ScanPlan.commanded_sector`/
  `commanded_legs`) is correct as built and needs no change.
- **`look <where>`/`sight <where>`/`what is [at] <where>` are a new, explicit request for the
  9K113.** This is additive — a new command surface, not a rewire of `scan`'s own dispatch.
  **Revised by the 2026-10-25 Correction**: for a `relative` `where` (left/right/ahead), `look`
  *does* touch `ScanPlan` — it sets `ScanPlan.commanded_sector` exactly as `scan left` already can
  (see "`look <o'clock>`/`look <compass>`" below for why this is the deliberately-reused, unbounded
  half of the design). There is still no risk of the two channels fighting: `look` and `scan` write
  the same field through the same existing path, never two competing writers. For a `clock`/compass
  `where`, `look` drives the sight through the new bounded mechanism instead (also built on the
  sector-wedge shape, not `ScanPlan`) — see "State" below.

### OBSERV gating for an explicit `look`

Because `look`/`sight`/`what is at` are an *explicit* request to use the 9K113, the command itself
is the pilot decision that satisfies `BL-B64`'s "OBSERV ON only on pilot command" — Petrovich is
not deciding to turn OBSERV on by himself, the pilot's own `look` command is the decision. So:

- **OBSERV already on**: dispatch the point/sector request immediately, same poll.
- **OBSERV off**: ask first, reusing the confirm band exactly as it already works elsewhere —
  see "OBSERV-off confirm flow" below. (explore-notes items 4-5, verbatim.)

### OBSERV-off confirm flow

**Reuse, not a new mechanism** — `PendingConfirmation` already carries a second,
mutually-exclusive payload beside its ordinary `token`/`slots` pair: `contact_pick`, for a
different kind of pending question ("only one candidate survived revalidation — confirm it, don't
silently act"). This plan adds a **third**, same shape: `observ_request: dict[str, int | str] |
None` — the point command's own parsed slots, carried across the confirm round trip, checked by
the affirm branch before falling to the ordinary `handle_command(pending.token, ...)` re-dispatch.

```
PendingConfirmation(
    token=None,               # not a command token to re-run as-is
    description="need observ",
    pending_since_sim=now_sim,
    observ_request=point_slots,
)
```

`render_confirm_request("need observ")` → `"Need observ, confirm?"` — the existing formatter,
unchanged, happens to produce exactly the user's own wording. No new speech-rendering code.

**On affirm** (`handle_transcript`'s existing pending-confirmation block, one new branch ordered
before the existing `contact_pick`/`token` checks):

```
if pending.observ_request is not None:
    lines = self._handle_observ_on()
    if self.sight_ready:   # _handle_observ_on didn't refuse (GUIDANCE_NOT_READY)
        self.pending_point_request = PendingPointRequest(
            slots=pending.observ_request, requested_sim=now_sim,
        )
    return lines
```

If the guidance unit itself isn't warmed up yet, `_handle_observ_on()` already returns
`render_unable("GUIDANCE_NOT_READY")` unchanged (`"Unable, guidance unit not ready."`) — the look
is simply dropped, no new unable reason needed, and no `pending_point_request` is queued (nothing
to wait for).

**`"observ on"` spoken during the confirm window counts as the "yes," not a second,
independent dispatch.** `classify_yes_no`'s own rule 2 ("a resolved command token is never an
answer") would otherwise swallow it — `"observ on"` resolves to the real `observ_on` token,
`matched_command=True`, so ordinarily it falls through *past* the confirm check to be evaluated on
its own merits, which would dispatch `_handle_observ_on()` a second, independent way while the
`pending_point_request`-worthy confirmation is simply dropped (cleared unconditionally the moment
any transcript arrives inside the window, answered or not). **Fix, scoped to this one pending-
confirmation kind only** (not a change to `classify_yes_no` itself, which stays exactly as its four
review rounds left it, for every other confirm use): in the pending-confirmation block, when
`pending.observ_request is not None`, also treat `token == "observ_on"` as confirmed, in addition
to `classify_yes_no`'s own "affirm" outcome:

```
if pending.observ_request is not None and (answer == "affirm" or token == "observ_on"):
    ...  # the branch above
```

This calls `_handle_observ_on()` exactly once either way (via this branch, never falling through
to the ordinary dispatch afterward — the function returns from inside the pending-confirmation
block regardless of which condition fired it).

**"no" cancels the look, silently** — `answer == "negative"` already returns `[]` unconditionally
for every confirm kind; inherited unchanged, no new wording. (Flagged as a Decision below only
because the user's own instruction didn't say whether a cancelled look should get an
acknowledgement — the existing silent-drop is the default, consistent with every other confirm's
negative branch.)

**No answer / timeout — inherited unchanged.** `CONFIRM_WINDOW_S` (15 s) elapses, the pending
confirmation (and with it the point request) is silently dropped, `_confirmation_expired_sim` is
set, and `CONFIRM_LATE_ANSWER_GRACE_S` (20 s) catches a delayed yes/no with "Say again?" rather
than misreading it as a fresh, unrelated command. No new timeout constant for this half.

**A second timeout *is* new**: once OBSERV is confirmed on and `pending_point_request` is queued,
waiting for the sight to actually be usable. See "What 'ready' means" below.

### What "ready" means — flagged, not assumed

The user's own words were "use sight when observ ready (lamp lit)." Two different things in this
codebase could be meant, and they are not the same wait:

1. **`self.sight_ready`** (`CrewConsole`, synced from `sight_effector.sight_ready`) — the
   guidance-unit *power-up* lamp. This is checked **synchronously, inside `_handle_observ_on`
   itself**, before OBSERV is even allowed to transition — if it's false, `_handle_observ_on`
   already refuses with `GUIDANCE_NOT_READY` and nothing is queued (see above). By the time the
   affirm branch above queues a `pending_point_request` at all, this lamp was already lit.
2. **`home_phase is OpticPhase.SIGHTING`** (actually, **does nothing** on its own) — entering
   OBSERV only sets `observ_transition`; `decide()`'s own phase cycle moves `home_phase` into
   `SIGHTING` at its *next* phase boundary (one poll, ordinarily), per `_handle_observ_on`'s own
   docstring. This is the wait that's actually still outstanding once the affirm branch returns.

**Recommendation: the drain condition is (2), not a second check of (1).** The lamp was already
checked at the door; what the pointing request is actually waiting for is the phase cycle catching
up, which is normally one poll and never more than a few. **Flagged because the user's wording
("lamp lit") names (1), and if a re-check of (1) was intended instead of (2), the two are not
interchangeable** — (1) could already be true for several polls before (2) catches up, so waiting
on (1) alone would try to point a sight phase that isn't `SIGHTING` yet.

### State — a new deferred-action queue, and the bounded-sweep tracking question

**`CrewConsole.pending_point_request: PendingPointRequest | None`**, drained once per poll
(`drain_pending_point_request(now_sim)`, called from `body.py` alongside `drain_events`/
`drain_brain`/`drain_pending_positional_replies` — the same place, same pattern). Unchanged from
before the Correction — it only carries the parsed `where`/`distance_km` slots across the
OBSERV-wait, same as any other deferred action:

```
@dataclass(frozen=True)
class PendingPointRequest:
    slots: dict[str, int | str]
    requested_sim: float

def drain_pending_point_request(self, now_sim: float) -> list[str]:
    if self.refused or self.pending_point_request is None:
        return []
    if self.home_phase is not OpticPhase.SIGHTING:
        if now_sim - self.pending_point_request.requested_sim > POINT_READY_TIMEOUT_S:
            self.pending_point_request = None
            return [render_unable("GUIDANCE_NOT_READY").text]  # or a dedicated reason, see Decisions
        return []
    slots = self.pending_point_request.slots
    self.pending_point_request = None
    return self._start_point(slots, now_sim)   # the actual dispatch, see below
```

`POINT_READY_TIMEOUT_S` is a new tunable (`tuning.py`, a few seconds — the ordinary wait is one
poll; this is a backstop against something else intervening, e.g. a violated `sight_steady`
triggering `_force_observ_off` between the affirm and the next poll boundary).

**What `_start_point` actually does now differs by which `where`-slot fired — this is the
Correction's structural change, not a detail.**

- **`relative` fired**: `_start_point` is a thin wrapper over the *existing* commanded-sector
  dispatch — set `ScanPlan.commanded_sector` to the named sector, exactly as `scan left` already
  can. **No new `OpticState`/`CrewConsole` field at all.** The sight's idle search cycle picks this
  up through `_sight_commanded_sector` unchanged, and runs it open-ended (see "Supersession" for
  what ends it). The only `look`-specific behaviour left is the OBSERV-gating/confirm wrapper
  already described above.
- **`clock` or `sector` (compass) fired**: `_start_point` begins the **bounded** procedure — the
  commanded wedge (the hour's 30°, or the compass bearing's 45°, see above) is searched for a
  fixed number of complete sweeps, then it reports and resumes. This needs **one new piece of
  state** tracking "a bounded commanded look is active, here is its wedge, here is how many
  complete sweeps it has run, here is what to resume once it ends" — left for the Implementer to
  place (a new `OpticState` field, or a `CrewConsole`-level record parallel to
  `pending_point_request`; either way it must appear in the Co-moving Fields table below, built by
  grepping every construction site once it is named, per root `CLAUDE.md`'s rule). **What it must
  *not* be**: a single `(look_azimuth_deg, look_elevation_deg)` aim line — that was the struck
  design. The wedge itself is expressed exactly the way Stage 1 already expresses one: a
  `(center_deg, half_width_deg)` pair fed to `_sight_in_regard_sweep`/`search_pattern`, not a point.

### The sweep itself

- **No distance given → near to far, the wedge's own full wide-optic reach** (answer 2, unchanged
  from the explore notes' earlier settlement) — `near_m=SIGHT_SEARCH_NEAR_M`,
  `far_m=SIGHT_SEARCH_WIDE_FAR_M` (Stage 1's own wide-optic band edges, reused directly: this is
  the same reach Stage 1's idle `wide_near`+`wide_far` legs cover between them, run here as one
  continuous near-to-far sweep against the commanded wedge instead of the idle cycle's two separate
  legs), with `SIGHT_WIDE_OPTIC`. `search_pattern`'s own band-count derivation already produces the
  S-shape exactly when the FOV needs it (see above) — no new shaping code.
- **A distance given → the sweep narrows to a band around that range** instead of the full
  near-to-far reach — pass a `near_m`/`far_m` pair centred on the stated distance to the same
  `_sight_in_regard_sweep` call, width left to the Implementer as a new tunable (e.g.
  `POINT_DISTANCE_BAND_HALF_KM`, a kilometre or so either side — tunable, not hardcoded, per root
  `CLAUDE.md`'s rule).
- **Two proper sweeps of the area** (answer 3) — a tunable sweep count (`POINT_SWEEP_COUNT`,
  default 2), not hardcoded, consistent with root `CLAUDE.md`'s tuning rule and this feature's own
  established posture (Stage 1's band edges are already tunable). One "sweep" is one full traversal
  of `search_pattern`'s own generated step list for the commanded wedge/band — the same
  lap-completion idea `_idle_sight_search`'s own leg-cycling already detects for the idle cycle
  (stepping off the last generated step), reused as a counter bound to `POINT_SWEEP_COUNT` instead
  of triggering a glance-away.
- **Nothing found after both sweeps**: `"<where> clear."` (answer 3) and **resume whatever the
  previous action was** — the idle search cycle at whatever leg it was on, a standing `scan_area`
  task, or a watch, per the same "resume, don't restart" principle `[[BL-B98]]` just fixed for the
  glance-away case. `<where>` renders the same way the sector/clock/bearing labels already do
  elsewhere in `crew_console.py` (`_RELATIVE_SCAN_LABELS`/`_SECTOR_SCAN_LABELS`/
  `_CLOCK_REPORT_LABELS` — reused, not a new label table).
- **Something found**: report through the normal callout path (unchanged — `choose_sighting_look`/
  the existing classification-driven callout mechanism), then **go back to scanning** — target
  count makes no difference (answer 4), so this is not a new "stay and track" behaviour, just the
  ordinary report-then-resume the idle cycle already does for any other sight look. Mid-sweep, a
  found contact does not consume one of the two sweeps — the sweep count only tracks completed
  *searches*, not interruptions by a report.
- **Readback on command**: a short acknowledgement naming the place (e.g. `"Two o'clock."`),
  mirroring `scan`'s own existing readback shape (`render_scan_readback`/`_describe_token_for_
  confirm`'s "a plain human phrase for the command" convention) — reuse, not new wording design.
  Applies to both the `relative` and the bounded clock/compass forms alike.

### Attack-run interaction

**Already correct, structurally, before this plan.** `_apply_guidance`'s sight-ceiling re-check
(see "What's already built" above) means: if an attack run is engaged, its own `requested_optic`
governs the sight regardless of any standing `look` — a sight-ranked request is capped to
binoculars whenever `home_phase is not SIGHTING`, and the attack run's own gaze claim (answer 5)
already wins the sight when `OpticPhase.SIGHTING` applies. **What this plan decides is only what
happens to a `look` command issued *while* a run is engaged**, which the existing mechanism does
not itself answer (it governs what the sight does once a decision is made, not whether a new
`look` command is accepted at all).

**Approved 2026-10-25** (task item 1, matches the recommendation below): refuse, don't queue.
`"unable, attack run"` (a new `render_unable` reason, e.g. `ATTACK_RUN_ENGAGED`) — the same "say
again vs unable" shape as `ON_GROUND`/`GUIDANCE_NOT_READY`: the command is heard and understood, it
just cannot be actioned right now, because the sight is already committed to the run's own target
and nothing a `look` command could ask for would be allowed to displace it anyway
(`_apply_guidance` would silently override it the very next poll even if queued). This applies to
every `where`-slot alike (`relative`, `clock`, compass) — the refusal is about the sight being
unavailable, not about which mechanism would have handled the request.

### Supersession — a new command replaces a pending-or-running look

User direction, verbatim (explore-notes item 6): *"new command replaces if it is look or scan
command. Effector sequences and commands to trigger tham can fire."*

| command class | effect on a pending/running `look` |
|---|---|
| `look_*`, `scan_*` (any sector/clock/bearing) | **replaces** — clears `pending_point_request`, or the active commanded sector/bounded search, and starts the new one |
| `observ_on`, `observ_off`, `weapons_armed`, `weapons_safe` (effector-trigger commands) | **run normally, no dispatch-level cancel** — `observ_off` ends the look as a *side effect* of `[[BL-B98]]`'s own rule (`home_phase` leaves `SIGHTING`, aim resets to boresight), not because this plan taught it to; see below |
| `report`, `describe`, `where_is_it` | **run without cancelling** — pure queries, no task state changes |
| `mark_here`, `mark_target` | **run without cancelling** — same reasoning, they write mission memory, not the sight's task |
| `cancel_task`, `cancel_scan`, `cancel_watch` | **cancel the look** — these are explicitly destructive of standing state, and both a commanded-sector `look` and a bounded clock/compass `look` are exactly that kind of standing state |
| `watch_nearest`, `follow`, `select_target`, `engage`, `disengage`, `drop_target`, `step` | **task-changing → replace/cancel** — consistent with answer 5's own attack-run priority; `engage` in particular hands the sight to `_apply_guidance` regardless (see above), so a standing bounded look would be moot even if left running |

**One case flagged, not defaulted**: `silence` is neither destructive of task state nor a query —
it only gates `_print`'s own output. **Approved 2026-10-25** (task item 2, matches the
recommendation below): `silence` does not cancel a pending/running look (consistent with it
leaving `scan_area`/`watch_contact` tasks alone today) — the look continues to run and resume as
normal, just without the spoken readback/report while silenced (the existing silence gate already
suppresses speech regardless of its source).

**`observ_off` during a *running* `relative` look**: unchanged from today's `scan left` behaviour
— `ScanPlan.commanded_sector` is untouched by OBSERV going off; only the sight's own idle search
stops reaching for it (`_sight_commanded_sector` is only consulted while `home_phase is SIGHTING`).
**`observ_off` during a *running* bounded clock/compass look**: checked against `[[BL-B98]]`'s own
rule directly — `body.py`'s `run_once` OBSERV-observed-off branch nulls the aim fields
unconditionally on the `home_phase` on→off edge, which already fires regardless of whether
`home_phase` got there via the idle search cycle or a bounded commanded look (the branch doesn't
distinguish the two, by construction). So a running bounded look is torn down correctly with
**no new code**, provided the new sweep-tracking field (named in "State" above) is included
wherever `[[BL-B98]]`'s reset `replace()` call already resets the other sighting fields — this
plan's own Co-moving Fields concern below, not a new mechanism.

---

## Co-moving Fields

Trigger: a new sweep-tracking field for the bounded clock/compass look, co-moving with
`sight_search_leg`/`search_step_index`/`home_phase`, at least one of which (`home_phase`) is
externally written (pilot command) and at least one (the idle-cycle fields) is internally decided.
**`relative` needs no new field at all** (it reuses `ScanPlan.commanded_sector` unchanged, which
already has its own co-moving-fields history from Stage 1/`scan_*`) — this table covers only the
bounded form. **Build the actual table by grepping every `OpticState(`/`replace(state` construction
site once the field is named** (per root `CLAUDE.md`'s "build the table by grepping every
construction site, not by enumerating transitions from the phase narrative") — Stage 1's own table
already names the two fresh-construction sites (`GLASSING`/`SEARCHING` entry in `body.py`) that
must carry the new field forward; this plan adds the following transitions to check against it:

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| bounded-look state (wedge, sweeps completed, resume target) | internal (`_start_point`) | `look <clock/compass>` accepted (OBSERV already on) | state set: wedge = the hour's 30°/bearing's 45° `(center_deg, half_width_deg)`, sweeps completed = 0, resume target = whatever was running before (idle leg, `scan_area`/watch task), `sight_search_leg`/`search_step_index` reset for the first step of the new wedge |
| bounded-look state | internal (`drain_pending_point_request`) | OBSERV-wait clears, deferred look starts | same post-state as the immediate path above — the deferred and immediate paths must produce an identical result, or a test covering only one will miss the other |
| bounded-look state | internal | one full traversal of the wedge's step list completes | sweeps completed increments; state stays active (not cleared) while `sweeps completed < POINT_SWEEP_COUNT` |
| bounded-look state | internal | `POINT_SWEEP_COUNT` sweeps complete, nothing found | state cleared, resumes the idle cycle/task at the recorded resume target — **not** reset to `wide_near` unconditionally, the same "resume, don't restart" principle `[[BL-B98]]` fixed |
| bounded-look state | internal | something found mid-sweep | state cleared after the report, same resume rule; the interrupting report does **not** count as a completed sweep |
| bounded-look state | external (`home_phase` on→off, any cause) | OBSERV off | state cleared, aim nulled to boresight — **already covered by `[[BL-B98]]`'s existing `replace()` call**, provided the new field is added to that same call rather than left out of it |
| bounded-look state | external (a new `look`/`scan` command) | supersession (see table above) | state cleared or replaced by the new request's own state, never left stale alongside a new aim |
| `pending_point_request` | internal/external mix (confirm affirm, poll drain, supersession) | any of the above | at most one of `pending_point_request` (waiting on OBSERV) and the active bounded-look state is set at a time — they are sequential phases of one request, never concurrent |

---

### Tests

- **Vocabulary/matcher** (`audio-adapter/tests/test_command_matcher.py`): `"look two o'clock"`,
  `"sight two o'clock, three kilometres"`, `"what is at two o'clock"` all resolve to the point
  token with the expected slots; `"what do you see"` still resolves to `report_all` unchanged;
  `"look left"`/`"look right"`/`"look ahead"` resolve to the point token with `relative` set and
  no longer alias `scan_left`/`scan_right`/`scan_ahead`; `"scan left"` is unaffected; a
  two-where-slot transcript (`"look left two o'clock"`) is a detected error (`token=None,
  verb_anchored=True`), not a guess.
- **OBSERV-off confirm flow** (`test_crew_console.py`): OBSERV off → `look` → `"Need observ,
  confirm?"` → `"yes"`/`"confirm"`/`"observ on"` each independently drive the same affirm branch,
  exactly once (`_handle_observ_on` called once, not twice, for the `"observ on"` case); `"no"`
  drops it silently; the existing `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S` timeout tests
  extended to cover this pending-confirmation kind rather than duplicated.
- **Deferred look drain**: queued after affirm, `home_phase` not yet `SIGHTING` → still pending;
  `home_phase` reaches `SIGHTING` → drains and starts the look same poll; `POINT_READY_TIMEOUT_S`
  elapses first → dropped with the fallback unable line. Covers both a `relative` and a bounded
  clock/compass look queued this way.
- **`look <relative>` (open-ended, no bound)**: sets `ScanPlan.commanded_sector` exactly as
  `scan left` does; the sight's idle search cycle covers it unbounded until superseded — no sweep
  count, no "clear" report, same test shape Stage 1 already has for a commanded sector.
- **`look <o'clock>`/`look <compass>` (bounded)**: the commanded wedge is the hour's 30°/bearing's
  45° `(center_deg, half_width_deg)`; near-to-far with no distance uses
  `SIGHT_SEARCH_NEAR_M`/`SIGHT_SEARCH_WIDE_FAR_M`; a distance given narrows the band instead; two
  `POINT_SWEEP_COUNT` sweeps (one full traversal of the generated step list each) then `"<where>
  clear"` and resume (asserted against whatever the previous state was — idle leg, standing
  `scan_area`, or watch — not reset to a fixed leg); a found contact mid-sweep reports then
  resumes without consuming a sweep, independent of how many targets were present.
- **Supersession**: a second `look`/`scan` command while one is pending-on-OBSERV, running
  open-ended (`relative`), or running bounded (clock/compass) replaces it cleanly (no stale aim, no
  double-queued request); `observ_on`/`weapons_armed` while either form is running leave it running;
  `cancel_scan`/`select_target` cancel it; `observ_off` while a bounded look is running tears the
  aim down to boresight via the existing `[[BL-B98]]` test shape, extended to the new sweep-tracking
  field rather than only an idle-cycle one.
- **Attack-run interaction**: `look` issued while an attack run is engaged → `"unable, attack
  run"`, no `pending_point_request` queued, no change to the run's own sight claim. Covers both
  `relative` and clock/compass forms.
- **Compass-bearing wedge conversion**: the new absolute-bearing-to-body-relative helper produces
  the same `(center_deg, half_width_deg)` a hand-worked example would, across a few headings —
  the one genuinely new piece of geometry this stage adds, so it earns its own direct test rather
  than only being exercised through the command path.

### Risks & Unknowns

- **The "ready" ambiguity (above) is still the single largest risk of a wrong first cut**, and is
  not resolved by this revision. If the Implementer builds against reading (1) (`self.sight_ready`)
  instead of (2) (`home_phase is SIGHTING`), the failure is subtle — it will often *look* correct in
  a quick test (the lamp and the phase usually line up within one poll) and only diverge under a
  slow effector sequence or a near-simultaneous OBSERV-off/on.
- **Two deferred-queue shapes now exist on `CrewConsole`** (`_pending_positional_replies`,
  `pending_point_request`) plus the ordinary `_pending_confirmation` — worth a `grep` sanity check
  that `drain_pending_point_request` is wired into `body.py`'s poll loop alongside the other two
  drains and not forgotten, the same class of gap `[[BL-B98]]` itself was.
- **The `relative`/bounded asymmetry is a direct reading of the transcript (above), not a
  judgement call left open** — unlike the struck "sector/point collapse," this one does not need a
  sign-off, but it is worth the Implementer re-reading "the geometry already exists" section's own
  quote of explore-notes item 2 before changing it, since a future reviewer unfamiliar with that
  item could plausibly "fix" the asymmetry into uniform bounded behaviour and break `look left`'s
  parity with `scan left`.
- **"One sweep" needs a precise definition the moment the Implementer writes it**: this plan defines
  it as "one full traversal of `search_pattern`'s generated step list for the commanded wedge/band."
  If `_idle_sight_search`'s existing lap-completion detection is reused rather than a fresh counter,
  double-check it is being asked about the *bounded wedge's* step list, not the idle cycle's
  three-leg lap — the two are different lengths and a conflated counter would complete a "sweep"
  too early or too late.
- **Vocabulary removal is a live-mapping change**: any sortie muscle-memory for "look left" meaning
  a naked-eye/binocular sector scan (if the pilot has been using it that way) now gets the 9K113
  instead. Worth a one-line callout in the eventual acceptance card.

### Second-order effect

Gives `[[BL-B66]]` (the 9K113 effector entry) a second standing-state shape to carry through its
own slew-rate model — not just the idle search cycle's phases and an open-ended commanded sector,
but a *bounded* commanded look with its own wedge/sweep-count/resume lifecycle. The new
sweep-tracking field this stage adds should be named with that in mind (the same state
`[[BL-B66]]`'s own warm-up/OBSERV/slew co-moving fields will need to reference), rather than as a
private detail of this stage alone.

### Decisions Requiring User Input

- **"Ready" means `home_phase is SIGHTING`, not a re-check of `self.sight_ready`** — recommended
  above; still unconfirmed by this round of answers (the four approvals below did not cover it),
  since the user's own wording ("lamp lit") names the other one and the two are not interchangeable
  (see "What 'ready' means").

**Approved 2026-10-25, no longer open:**
- `look` during an engaged attack run is refused, `"unable, attack run"` (task item 1).
- `silence` does not cancel a pending/running look (task item 2).
- A cancelled-by-"no" look gets no acknowledgement — silent drop (task item 3).
- One `look` command covers both sectors and places (task item 4) — realised, after the
  Correction, as the `relative`-vs-bounded-clock/compass split above rather than the struck
  "exact aim line" design; the single-token, slot-dispatched vocabulary from "Vocabulary design"
  is unchanged by the Correction.
