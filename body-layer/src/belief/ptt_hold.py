"""`PttHoldGate`: should Petrovich *start* a new routine utterance right
now, given whether the player currently holds the ICS (intercom) or
RADIO trigger (`body-layer/ROADMAP/BL-B133.md`)?

**User direction, verbatim:** *"when player presses ICS / RADIO trigger,
while either is pressed, Petrovich does not start talking. This prevents
him speaking while I'm speaking."* Then, resolving the two open
questions: *"1 - say urgent ones even when I hold trigger 2 - let it
play"* -- an urgent line (`SpeechWorker.enqueue(bypass_gate=True)`) is
never held, and a line already *playing* when the trigger goes down
plays to the end. Only the start of the *next* routine line waits.

**Lives beside `SpeechWorker`, decided over `CrewConsole._print`'s own
gate (the SPU-8 intercom-open precedent).** `SpeechWorker._run` is
already the one place that decides *when* a queued line actually starts
(`client.push_speech` is called from there, not from `_print`), on its
own background thread -- so gating there needs no change to `_print`'s
synchronous, immediate-return `enqueue` contract, and blocking there
blocks neither the poll thread nor whichever thread calls `_print`. The
"when" stays in this one module/class (root `CLAUDE.md`, "Behaviour as
actions and params") rather than being duplicated at a second gate.

**Failure posture: unknown reads as released, never as held forever.**
Two distinct unknowns, both resolved the same way, both logged once
(not once per poll):

- **Unavailable** -- `GET /ptt/state` raises `AircraftLayerError`
  (network down, aircraft-layer not running). `ConnectionReporter`'s
  existing transition-only `report_failure`/`report_success` is reused
  here exactly as `SpeechWorker` already reuses it for the audio-adapter
  seam -- the "log once per outage" mechanism already exists, so this
  does not invent a second one.
- **Stale** -- checked only when the sample currently reads *held*, and
  keyed off **`GET /telemetry/latest`'s own `received_wall_clock_s`**
  (`telemetry_received_wall_clock_s`, supplied by the caller -- `body.py`
  wires this to the same telemetry its poll loop already reads every
  poll, so this adds no second request), **not** the PTT sample's own
  timestamp. `Export.lua` sends a `ptt` line only on change
  (`aircraft-layer/src/api/server.py`'s `_handle_ptt_state` docstring) but
  telemetry every tick regardless of value -- so a steadily *held*
  trigger's own `received_wall_clock_s` ages exactly like a dead
  collector's last cached sample, and cannot tell the two apart (review
  fix 1, `plans/bl-b133-ptt-speech-hold/review.md`: this is what the
  previous PTT-sample-keyed version actually got wrong -- a routine, genuinely
  held trigger longer than the bound released early, which is precisely
  the behaviour U1 exists to prevent). Telemetry refreshing is a property
  of the feed, independent of PTT value, so its own age tells "the
  collector/DCS side has stopped updating" without being confused by an
  ordinary long intercom/radio call. What this bound guards against is
  the collector process surviving a crashed/ended mission while the last
  PTT sample it cached happened to read "held": nothing would ever
  refresh that sample, and the gate would hold Petrovich mute for the
  rest of the process's life -- `PTT_FEED_STALE_AFTER_S` is how long
  telemetry itself may go unrefreshed before that cached "held" is
  distrusted. `body._reset_mission_state` also calls `reset_for_new_
  mission()` on this gate directly, so a genuine DCS mission (re)start
  clears a stuck `held=True` state at the actual lifecycle event, rather
  than this bound being the only backstop.

**The release side is debounced, the press side is not, and the
debounce only ever applies to a genuine held-to-released *transition*.**
A full press transits the intercom stop for 19-32 ms on its way to the
radio stop (`audio-adapter/src/ptt_source.py`'s own measured figure,
`INTERCOM_DEBOUNCE_S`) -- and the same mechanical transit happens on
release, in reverse. Starting to hold early is harmless (it only delays
a line that was going to wait anyway), so the press edge needs no
debounce; letting go early on a transit blip would not be harmless --
it could open a half-second window to start a routine line that the
trigger is about to re-claim -- so once this gate has observed `held`,
it requires the *released* reading to persist for `PTT_RELEASE_
DEBOUNCE_S` before it reports `False`, with any intervening `True`
sample resetting that window (ordinary hysteresis, not a one-shot
timer). **A gate that has never observed `held` reports a `released`
sample as released immediately** -- the debounce exists to guard a real
release edge, not to delay every poll of an already-settled state by
one window on principle (a fresh `PttHoldGate`, or one that has been
reading "released" for a while, must not report "held" for no reason
other than its own initialization)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

import tuning
from aircraft_client import AircraftLayerError
from connection_reporter import ConnectionReporter

#: How long a `held=False` reading must persist before `is_held()` reports
#: released -- guards the release-side mechanical transit (see module
#: docstring). Same order of magnitude as `audio-adapter`'s measured
#: press-side transit (19-32 ms); 0.1 s is a deliberate round number a few
#: times that, not a second measurement of this specific edge.
PTT_RELEASE_DEBOUNCE_S: float = tuning.real(
    "belief.ptt_hold.PTT_RELEASE_DEBOUNCE_S",
    0.1,
    lo=0.0,
    hi=1.0,
    status="agreed-guess",
)

#: Above this age, the *telemetry* feed (not the PTT sample itself --
#: see module docstring's "Stale" paragraph) is considered dead, and a
#: cached `held=True` PTT sample is no longer trusted: `is_held()`
#: reports released instead. Telemetry refreshes every tick regardless
#: of PTT value, so this bound is "how long the collector/DCS side may
#: go unresponsive," not "how long a call may last" -- a genuine hold of
#: any length is unaffected as long as telemetry keeps arriving. Short
#: enough that a dead collector cannot silence Petrovich for the rest of
#: a sortie.
PTT_FEED_STALE_AFTER_S: float = tuning.real(
    "belief.ptt_hold.PTT_FEED_STALE_AFTER_S",
    120.0,
    lo=10.0,
    hi=600.0,
    status="agreed-guess",
)

logger = logging.getLogger(__name__)


class PttSource(Protocol):
    """The subset of `aircraft_client.AircraftLayerClient`'s interface
    this gate needs -- a `Protocol` so a test double can stand in
    without inheriting from the real client, same pattern `belief.
    speech_worker.SpeechClient` already uses for the audio-adapter seam."""

    def get_ptt_state_latest(self) -> dict[str, Any] | None: ...


class PttHoldGate:
    """`is_held()` -- should the *start* of a new routine utterance wait?
    Single caller: `SpeechWorker._run`, from its own background thread.
    Not thread-safe for concurrent callers (none needed -- see that
    caller)."""

    def __init__(
        self,
        client: PttSource,
        *,
        telemetry_received_wall_clock_s: Callable[[], float | None],
        reporter: ConnectionReporter | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        """`telemetry_received_wall_clock_s` -- the live mission's own
        telemetry feed freshness (review fix 1): a callable returning the
        most recent `GET /telemetry/latest` sample's own
        `received_wall_clock_s`, or `None` if none has ever been
        received. Keyword-only and required, not defaulted -- staleness
        detection silently doing nothing because a caller forgot to wire
        it is exactly the kind of broken-config failure this project's
        "fail loud, not recover" rule exists for (root `CLAUDE.md`,
        "Workflow"). `None` (never received) is treated as at least as
        stale as any bound -- see `_is_stale`."""
        self._client = client
        self._telemetry_received_wall_clock_s = telemetry_received_wall_clock_s
        self._reporter = reporter
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        #: The last *confirmed* (debounced) state -- `False` until this
        #: gate has actually observed `held`, so a fresh instance (or one
        #: that has settled released) never owes a release debounce it
        #: never earned (see module docstring).
        self._confirmed_held = False
        self._released_since: float | None = None
        #: Log the stale condition once per episode, like `ConnectionReporter`'s
        #: own transition-only posture -- reset the moment a fresh (non-stale)
        #: sample is read, so a later episode logs again.
        self._stale_warned = False

    def is_held(self) -> bool:
        """True if the player is currently holding the ICS or RADIO
        trigger and the *start* of a new routine line should therefore
        wait. Never raises -- every failure mode below resolves to
        `False` (see module docstring's "Failure posture")."""
        try:
            payload = self._client.get_ptt_state_latest()
        except AircraftLayerError as exc:
            if self._reporter is not None:
                self._reporter.report_failure(exc)
            else:
                logger.warning(
                    "ptt state unavailable -- treating as released", exc_info=True
                )
            self._released_since = None
            return False

        if self._reporter is not None:
            self._reporter.report_success()

        if payload is None:
            # The trigger has not moved at all this collector process's
            # lifetime -- the ordinary startup state, not an unknown.
            self._confirmed_held = False
            self._released_since = None
            self._stale_warned = False
            return False

        held_now = bool(payload.get("intercom")) or bool(payload.get("radio"))

        # Staleness only matters for a *held* reading -- an untouched
        # trigger's timestamp ages indefinitely in the ordinary idle case
        # (see module docstring), and that case already reports released
        # below with no need to look at the age at all. Keyed off the
        # *telemetry* feed's own freshness (review fix 1), not this PTT
        # sample's own timestamp -- see `_is_stale`.
        if held_now and self._is_stale():
            if not self._stale_warned:
                self._stale_warned = True
                logger.warning(
                    "telemetry feed stale (no update in over %.0fs) while "
                    "ptt reads held -- treating as released",
                    PTT_FEED_STALE_AFTER_S,
                )
            self._confirmed_held = False
            self._released_since = None
            return False
        self._stale_warned = False

        if held_now:
            self._confirmed_held = True
            self._released_since = None
            return True

        if not self._confirmed_held:
            # Already settled released (or never held at all) -- nothing
            # to debounce, see module docstring's last paragraph.
            self._released_since = None
            return False

        now = self._monotonic()
        if self._released_since is None:
            self._released_since = now
        if (now - self._released_since) < PTT_RELEASE_DEBOUNCE_S:
            return True
        self._confirmed_held = False
        self._released_since = None
        return False

    def _is_stale(self) -> bool:
        """True if the *telemetry* feed -- not the PTT sample -- has not
        refreshed within `PTT_FEED_STALE_AFTER_S` (review fix 1). This is
        what actually distinguishes "the collector/DCS side died" from
        "the player is still genuinely holding the trigger": `Export.lua`
        sends telemetry every tick regardless of PTT value, so a live
        mission's telemetry age stays near zero through an arbitrarily
        long hold, while a dead mission's telemetry age grows without
        bound -- the PTT sample's own `received_wall_clock_s` cannot make
        this distinction (module docstring's "Stale" paragraph)."""
        received = self._telemetry_received_wall_clock_s()
        if not isinstance(received, (int, float)) or isinstance(received, bool):
            # No telemetry has ever been received this process's
            # lifetime -- at least as stale as any bound.
            return True
        return (self._wall_clock() - received) > PTT_FEED_STALE_AFTER_S

    def reset_for_new_mission(self) -> None:
        """Clean slate on a genuine DCS mission (re)start
        (`body._reset_mission_state`, review fix 1) -- a cached
        `held=True` PTT sample from the mission that just ended, or a
        release debounce window already in progress, must not carry into
        the new one. Equivalent to a freshly constructed gate's own
        starting state."""
        self._confirmed_held = False
        self._released_since = None
        self._stale_warned = False
