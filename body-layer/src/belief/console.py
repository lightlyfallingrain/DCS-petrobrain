"""Line parser + pretty-printer over `belief.tools` -- `plans/
pb2-contact-memory/plan.md` Stage 4's debug console, the literal ancestor of
§3.3's brain tool set (`plans/body-layer/plan.md`'s BL-2 summary: "every
command added here should be one that later becomes a brain tool").

Owns **no belief logic**. Every command below maps 1:1 to a `belief.tools`
function; this module's job is only to split an input line into a command +
argument, call the matching tool, and format whatever it returns as text.
If a future command needs new belief-state logic, that logic belongs in
`tools.py` (or a `belief/` module `tools.py` itself calls), never inline
here -- see `tools.py`'s own module docstring on why `set_attention`/
`stats`/`list_areas` have tool functions despite not all being one of
§3.3's original four.

    contacts [all|visible|watched]              -> tools.get_contacts
    show <id>                                   -> tools.describe_contact
    history <id>                                -> tools.get_contact_history
    find <text>                                 -> tools.find_contact
    watch <id>                                  -> tools.set_attention
    unwatch <id>                                 -> tools.set_attention
    attention <id>                               -> tools.get_attention_state
    attention <id> <level>                      -> tools.set_attention
    watch-area <bearing> <range_m> <radius_m> [sector] -> tools.watch_area
    unwatch-area <id>                           -> tools.unwatch_area
    areas                                       -> tools.list_areas
    events                                      -> tools.list_events
    ack <id>                                    -> tools.acknowledge_event
    stats                                       -> tools.get_stats
    place <text>                                -> tools.find_place
    situation                                   -> tools.get_situation
    position                                    -> tools.describe_our_position
    scan-area <bearing> <range_m> <radius_m> <reason> [sector] -> tools.scan_area
    task-status <id>                            -> tools.get_task_status
    cancel-task <id>                            -> tools.cancel_task

`events`/`ack <id>` map to `tools.list_events`/`tools.acknowledge_event`
directly, which is exactly `tools.poll_events`'s own semantics (BL-5,
`plans/bl5-tool-api/plan.md` Decision 4) -- documented here, not
duplicated as a separate command.

`watch <id>`/`unwatch <id>` (BL-2 Stage 4) are kept as aliases over the
general `attention <id> <level>` command (BL-4, `plans/
bl4-attention-events/plan.md`) -- both call `tools.set_attention` with
`level="watch"`/`"normal"` respectively, so their output is byte-for-byte
unchanged from before BL-4.

`watch-area` resolves its bearing/range argument against `enrichment.
ownship` (`perception.geometry.project_from_bearing_range`) -- it is
therefore unavailable (returns an error line, not a crash) until `Console.
enrichment` has been set, same guard shape as every other enrichment-
dependent field elsewhere in this module. It never resolves a place name
(`find_place` is BL-5/BL-6 work, see `tools.watch_area`'s own docstring).

`place`/`situation`/`position` (BL-5) require live ownship telemetry the
same way `watch-area` does -- `Console.enrichment` must be set, or they
return an error line rather than crashing, same guard shape as every other
enrichment-dependent command in this module.

`scan-area`/`task-status`/`cancel-task` (BL-6, `plans/
bl6-commands-inspect-adapt/plan.md`) map to `tools.scan_area`/
`tools.get_task_status`/`tools.cancel_task`, the same 1:1 dispatch rule as
every other command here -- with one deliberate exception. `scan-area`'s
handler, after calling `tools.scan_area` (which stays pure, no DCS I/O),
also calls `Console.aircraft_client.trigger_petrovich_search` if a client
is configured -- the one place in this module a command does more than
call a single `belief.tools` function and format the result, mirroring
where BL-2.5 put its own live side effect (`logger.
ConsolePerceptionRunner.run_once`'s overlay push), not inside `tools.py`.
A failed live trigger is caught (`AircraftLayerError`) and degrades to "the
belief-state task was still registered, no live command fired" -- it never
raises through to the caller. `task-status`'s handler may additionally
fetch `Console.aircraft_client.get_petrovich_wheel_latest()` as a
display-only diagnostic line (Petrovich's live AI-Wheel state); this is
never stored on the `PendingIntent` returned by `tools.get_task_status`
and never changes that function's own return contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TextIO

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.attention import SECTORS, Attention, AttentionArea, Sector
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.events import CONTACT_CLASSIFICATION_CHANGED, Event
from belief.tasks import PendingIntent, TaskStore
from belief.tools import (
    ContactFilter,
    ContactResult,
    ToolResult,
    acknowledge_event,
    cancel_task,
    describe_contact,
    describe_our_position,
    find_contact,
    find_place,
    get_attention_state,
    get_contact_history,
    get_contacts,
    get_situation,
    get_stats,
    get_task_status,
    list_areas,
    list_events,
    scan_area,
    set_attention,
    unwatch_area,
    watch_area,
)
from perception.geometry import GeoPosition, project_from_bearing_range

#: Printed once at REPL startup (`logger.py`'s `main()`) -- kept in sync with
#: the module docstring's command table above by hand; both list the same
#: commands because `handle_line`'s dispatch is the single source of truth
#: for what actually exists.
HELP_TEXT = """\
Petrovich belief console -- commands:
  contacts [all|visible|watched]  list contacts (default: all)
  show <id>                       full detail for one contact
  history <id>                    a contact's sighting/event history
  find <text>                     search contacts by classification text
  watch <id>                      mark a contact watched
  unwatch <id>                    clear a contact's watched mark
  attention <id> [<level>]        show, or set, a contact's attention (ignore/normal/watch/priority)
  watch-area <bearing_deg> <range_m> <radius_m> [sector]  watch an area
  unwatch-area <id>                clear a watched area
  areas                           list watched areas
  events                          list unacknowledged events
  ack <id>                        acknowledge an event
  stats                           observation/contact/event counts
  place <text>                    look up a named place in the world model
  situation                       aggregate sitrep
  position                        our own current position
  scan-area <bearing_deg> <range_m> <radius_m> <reason> [sector]  ask Petrovich to search an area
  task-status <id>                 a scan task's current status
  cancel-task <id>                 cancel a still-pending scan task
"""

_CONTACT_FILTERS: tuple[ContactFilter, ...] = ("all", "visible", "watched")
_ATTENTION_LEVELS: tuple[Attention, ...] = ("ignore", "normal", "watch", "priority")

#: `_contact_result`'s `facts` keys, in display order, for `show <id>`'s
#: multi-line block -- listed explicitly (rather than iterating the dict)
#: so the block's order is stable regardless of `dict` insertion order.
_SHOW_FACT_KEYS: tuple[str, ...] = (
    "classification",
    "certainty",
    "visible",
    "last_seen_ago_s",
    "position",
    "relative_now",
    "semantic",
    "motion_when_seen",
    "sources",
    "attention",
    "attention_source",
)


@dataclass
class Console:
    """Holds the `ContactStore` every command reads/mutates through
    `belief.tools`. `handle_line` returns the formatted lines it printed
    (mirroring `logger.PerceptionLogger.run_once`'s return-what-was-produced
    shape) so tests can assert on output without capturing stdout."""

    store: ContactStore
    output: TextIO | None = None
    #: BL-3's addition (`plans/bl3-world-enrichment/plan.md`) -- optional,
    #: `None` (the default) leaves every command's output byte-for-byte
    #: BL-2's original, same guard as `belief.tools`' own `enrichment`
    #: parameter. `logger.ConsolePerceptionRunner` updates this in place
    #: each poll (`_run_console_repl`), since it is built lazily once
    #: `run_once` has real ownship telemetry.
    enrichment: EnrichmentContext | None = None
    #: BL-6's `belief.tasks.TaskStore` -- `scan-area`/`task-status`/
    #: `cancel-task` all read/mutate this, same "Console holds every store a
    #: dispatched command needs" shape as `store` above. Defaults to a fresh
    #: empty store rather than being required, so every existing `Console(
    #: store=...)` call site (tests included) keeps working unchanged.
    tasks: TaskStore = field(default_factory=TaskStore)
    #: Optional live aircraft-layer client (BL-6), mirroring `enrichment`'s
    #: None-means-unchanged pattern: `None` (the default) is a true no-op --
    #: `scan-area`'s handler never touches the aircraft layer for the live
    #: trigger unless this is set, and every other command ignores it
    #: entirely. `logger.py`'s `main()` wires a real `AircraftLayerClient`
    #: in here for `--console`, the same instance already used for
    #: telemetry (no separate URL/flag), mirroring `--overlay`'s own
    #: wiring of `ConsolePerceptionRunner.overlay_client`.
    aircraft_client: AircraftLayerClient | None = None

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        lines = _dispatch(
            self.store, self.tasks, line, now_sim, self.enrichment, self.aircraft_client
        )
        if self.output is not None:
            for formatted in lines:
                print(formatted, file=self.output)
        return lines


def _dispatch(
    store: ContactStore,
    tasks: TaskStore,
    line: str,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
    aircraft_client: AircraftLayerClient | None = None,
) -> list[str]:
    stripped = line.strip()
    if not stripped:
        return []
    command, _, rest = stripped.partition(" ")
    command = command.lower()
    rest = rest.strip()

    if command == "contacts":
        return _handle_contacts(store, rest, now_sim, enrichment)
    if command == "show":
        return _handle_show(store, rest, now_sim, enrichment)
    if command == "history":
        return _handle_history(store, rest)
    if command == "find":
        return _handle_find(store, rest, now_sim, enrichment)
    if command == "watch":
        return _handle_watch(store, rest)
    if command == "unwatch":
        return _handle_unwatch(store, rest)
    if command == "attention":
        return _handle_attention(store, rest)
    if command == "watch-area":
        return _handle_watch_area(store, rest, enrichment)
    if command == "unwatch-area":
        return _handle_unwatch_area(store, rest)
    if command == "areas":
        return _handle_areas(store)
    if command == "events":
        return _handle_events(store)
    if command == "ack":
        return _handle_ack(store, rest)
    if command == "stats":
        return _handle_stats(store)
    if command == "place":
        return _handle_place(rest, enrichment)
    if command == "situation":
        return _handle_situation(store, now_sim, enrichment)
    if command == "position":
        return _handle_position(enrichment)
    if command == "scan-area":
        return _handle_scan_area(
            store, tasks, rest, now_sim, enrichment, aircraft_client
        )
    if command == "task-status":
        return _handle_task_status(tasks, rest, aircraft_client)
    if command == "cancel-task":
        return _handle_cancel_task(store, tasks, rest)
    return [f"unknown command: {command}"]


def _handle_contacts(
    store: ContactStore,
    rest: str,
    now_sim: float,
    enrichment: EnrichmentContext | None,
) -> list[str]:
    filter_arg: ContactFilter | None
    if not rest:
        filter_arg = None
    elif rest == "all":
        filter_arg = "all"
    elif rest == "visible":
        filter_arg = "visible"
    elif rest == "watched":
        filter_arg = "watched"
    else:
        return [
            f"unknown filter: {rest} (expected one of {', '.join(_CONTACT_FILTERS)})"
        ]
    results = get_contacts(store, now_sim, filter=filter_arg, enrichment=enrichment)
    if not results:
        return ["no contacts"]
    return [_format_contact_line(result) for result in results]


def _handle_show(
    store: ContactStore,
    rest: str,
    now_sim: float,
    enrichment: EnrichmentContext | None,
) -> list[str]:
    if not rest:
        return ["usage: show <id>"]
    result = describe_contact(store, rest, now_sim, enrichment=enrichment)
    if result is None:
        return [f"no such contact: {rest}"]
    return _format_contact_block(result)


def _handle_history(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: history <id>"]
    entries = get_contact_history(store, rest)
    if not entries:
        return [f"no history for {rest}"]
    return [_format_history_entry(entry) for entry in entries]


def _handle_find(
    store: ContactStore,
    rest: str,
    now_sim: float,
    enrichment: EnrichmentContext | None,
) -> list[str]:
    if not rest:
        return ["usage: find <text>"]
    results = find_contact(store, rest, now_sim, enrichment=enrichment)
    if not results:
        return [f"no matches for '{rest}'"]
    return [_format_contact_line(result) for result in results]


def _handle_watch(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: watch <id>"]
    found = set_attention(store, rest, "watch")
    return [f"watching {rest}" if found else f"no such contact: {rest}"]


def _handle_unwatch(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: unwatch <id>"]
    found = set_attention(store, rest, "normal")
    return [f"no longer watching {rest}" if found else f"no such contact: {rest}"]


def _handle_attention(store: ContactStore, rest: str) -> list[str]:
    """`attention <id>` (no level) queries `tools.get_attention_state`;
    `attention <id> <level>` sets the contact's direct mark via `tools.
    set_attention` -- the same command name doubles as read and write,
    distinguished only by argument count, since both operate on the same
    "one contact's attention" concept."""
    parts = rest.split(maxsplit=1)
    if not parts:
        return ["usage: attention <id> [<level>]"]
    if len(parts) == 1:
        contact_id = parts[0]
        state = get_attention_state(store, contact_id)
        if state is None:
            return [f"no such contact: {contact_id}"]
        return [_format_attention_state(state)]
    contact_id, level_arg = parts
    level_arg = level_arg.strip().lower()
    if level_arg not in _ATTENTION_LEVELS:
        levels = ", ".join(_ATTENTION_LEVELS)
        return [f"unknown attention level: {level_arg} (expected one of {levels})"]
    found = set_attention(store, contact_id, level_arg)
    if found:
        return [f"{contact_id}: attention = {level_arg}"]
    return [f"no such contact: {contact_id}"]


def _format_attention_state(state: dict[str, object]) -> str:
    line = f"{state['contact_id']}: direct={state['direct']} effective={state['effective']}"
    if "direct_source" in state:
        line += f" direct_source={state['direct_source']}"
    if "area_id" in state:
        line += f" area_id={state['area_id']}"
    return line


def _handle_watch_area(
    store: ContactStore, rest: str, enrichment: EnrichmentContext | None
) -> list[str]:
    usage = ["usage: watch-area <bearing_deg> <range_m> <radius_m> [sector]"]
    parts = rest.split()
    if len(parts) not in (3, 4):
        return usage
    if enrichment is None:
        return ["watch-area requires live ownship telemetry (not available yet)"]
    try:
        bearing_deg = float(parts[0])
        range_m = float(parts[1])
        radius_m = float(parts[2])
    except ValueError:
        return usage
    sector: Sector | None = None
    if len(parts) == 4:
        sector_arg = parts[3].upper()
        if sector_arg not in SECTORS:
            return [
                f"unknown sector: {parts[3]} (expected one of {', '.join(SECTORS)})"
            ]
        sector = sector_arg
    ownship = enrichment.ownship
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    center = project_from_bearing_range(observer, bearing_deg, range_m)
    area = watch_area(store, center, radius_m, sector=sector)
    return [f"watching area {area.id}"]


def _handle_unwatch_area(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: unwatch-area <id>"]
    found = unwatch_area(store, rest)
    return [f"no longer watching area {rest}" if found else f"no such area: {rest}"]


def _handle_areas(store: ContactStore) -> list[str]:
    areas = list_areas(store)
    if not areas:
        return ["no areas"]
    return [_format_area_line(area) for area in areas]


def _format_area_line(area: AttentionArea) -> str:
    sector_part = f" sector={area.sector}" if area.sector is not None else ""
    return (
        f"{area.id}: level={area.level} radius_m={area.radius_m:.0f}"
        f"{sector_part} source={area.source}"
    )


def _handle_events(store: ContactStore) -> list[str]:
    events = list_events(store)
    if not events:
        return ["no unacknowledged events"]
    return [_format_event_line(event) for event in events]


def _format_event_line(event: dict[str, object]) -> str:
    return (
        f"{event['id']}: {event['kind']} contact={event['contact_id']} "
        f"t_sim={event['t_sim']}"
    )


def _handle_ack(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: ack <id>"]
    found = acknowledge_event(store, rest)
    return [f"acknowledged {rest}" if found else f"no such event: {rest}"]


def _handle_stats(store: ContactStore) -> list[str]:
    stats = get_stats(store)
    return [
        (
            f"contacts={stats['contacts']} "
            f"observations={stats['observations']} "
            f"events={stats['events']}"
        )
    ]


_ENRICHMENT_REQUIRED_MESSAGE = "requires live ownship telemetry (not available yet)"


def _handle_place(rest: str, enrichment: EnrichmentContext | None) -> list[str]:
    if not rest:
        return ["usage: place <text>"]
    if enrichment is None:
        return [f"place {_ENRICHMENT_REQUIRED_MESSAGE}"]
    results = find_place(enrichment, rest)
    if not results:
        return [f"no matches for '{rest}'"]
    return [_format_tool_result_line(result) for result in results]


def _handle_situation(
    store: ContactStore, now_sim: float, enrichment: EnrichmentContext | None
) -> list[str]:
    if enrichment is None:
        return [f"situation {_ENRICHMENT_REQUIRED_MESSAGE}"]
    result = get_situation(store, now_sim, enrichment)
    return [result["summary"]]


def _handle_position(enrichment: EnrichmentContext | None) -> list[str]:
    if enrichment is None:
        return [f"position {_ENRICHMENT_REQUIRED_MESSAGE}"]
    result = describe_our_position(enrichment)
    return [result["summary"]]


def _handle_scan_area(
    store: ContactStore,
    tasks: TaskStore,
    rest: str,
    now_sim: float,
    enrichment: EnrichmentContext | None,
    aircraft_client: AircraftLayerClient | None,
) -> list[str]:
    usage = ["usage: scan-area <bearing_deg> <range_m> <radius_m> <reason> [sector]"]
    parts = rest.split()
    if len(parts) < 4:
        return usage
    if enrichment is None:
        return [f"scan-area {_ENRICHMENT_REQUIRED_MESSAGE}"]
    try:
        bearing_deg = float(parts[0])
        range_m = float(parts[1])
        radius_m = float(parts[2])
    except ValueError:
        return usage

    # `reason` is free text; an optional trailing sector token is popped off
    # first if the last word matches one of `SECTORS` -- mirrors
    # `_handle_watch_area`'s sector parsing, just applied to the *last* token
    # of a variable-length tail instead of a fixed 4th argument, since
    # `reason` itself has no fixed length.
    reason_parts = parts[3:]
    sector: Sector | None = None
    sector_arg = reason_parts[-1].upper() if len(reason_parts) > 1 else ""
    if sector_arg in SECTORS:
        sector = sector_arg
        reason_parts = reason_parts[:-1]
    reason = " ".join(reason_parts)
    if not reason:
        return usage

    ownship = enrichment.ownship
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    center = project_from_bearing_range(observer, bearing_deg, range_m)
    task = scan_area(store, tasks, center, radius_m, reason, now_sim, sector=sector)
    lines = [f"scan task {task.id} created (area {task.area.id})"]
    if aircraft_client is not None:
        try:
            aircraft_client.trigger_petrovich_search("forward")
            lines.append("live Petrovich search triggered (forward)")
        except AircraftLayerError:
            lines.append(
                "live search trigger failed -- task still registered, no command fired"
            )
    return lines


def _handle_task_status(
    tasks: TaskStore, rest: str, aircraft_client: AircraftLayerClient | None
) -> list[str]:
    if not rest:
        return ["usage: task-status <id>"]
    task = get_task_status(tasks, rest)
    if task is None:
        return [f"no such task: {rest}"]
    lines = [_format_task_line(task)]
    if aircraft_client is not None:
        try:
            wheel = aircraft_client.get_petrovich_wheel_latest()
            if wheel is not None:
                lines.append(
                    f"petrovich wheel state (live, diagnostic only): {wheel['fields']}"
                )
        except AircraftLayerError:
            pass
    return lines


def _format_task_line(task: PendingIntent) -> str:
    line = (
        f"{task.id}: status={task.status} area={task.area.id} "
        f"reason={task.reason!r} deadline_sim={task.deadline_sim}"
    )
    if task.result_contact_ids:
        line += f" result_contact_ids={task.result_contact_ids}"
    return line


def _handle_cancel_task(store: ContactStore, tasks: TaskStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: cancel-task <id>"]
    found = cancel_task(store, tasks, rest)
    return [f"cancelled task {rest}" if found else f"no such task: {rest}"]


def _format_tool_result_line(result: ToolResult) -> str:
    return result["summary"]


def _format_contact_line(result: ContactResult) -> str:
    facts = result["facts"]
    return f"{facts['id']}: {result['summary']}"


def _format_contact_block(result: ContactResult) -> list[str]:
    facts = result["facts"]
    lines = [f"{facts['id']}"]
    for key in _SHOW_FACT_KEYS:
        if key in facts:
            lines.append(f"  {key}: {facts[key]}")
    lines.append(f"summary: {result['summary']}")
    return lines


def format_event_for_overlay(
    store: ContactStore,
    event: Event,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> str:
    """One line for BL-2.5's in-cockpit overlay mirror
    (`logger.ConsolePerceptionRunner`, `plans/dcs-text-panel-output/plan.md`):
    `"<id>: <kind>, <summary>"` for the event's contact, reusing
    `describe_contact`'s existing `summary` field rather than inventing new
    belief-reading logic here (this module owns no belief logic, see the
    module docstring).

    The leading `"<id>: "` matches `_format_contact_line`/
    `_format_contact_block`'s own `contacts`/`show <id>` rendering above --
    the one existing convention this module already has for writing a
    contact id into a line of text, reused rather than invented fresh.
    Without it, the overlay's fixed-duration message feed cannot distinguish
    six sightings of one re-firing contact from six distinct contacts (BL-2.5
    follow-up, live-acceptance screenshot finding, 2026-09-09) -- both render
    as identical `CONTACT_DETECTED: ...` lines.

    **`CONTACT_CLASSIFICATION_CHANGED` gets its own transition rendering**
    (`plans/classification-refinement/plan.md` Stage 4), and only that kind
    -- every other kind's line is left byte-for-byte alone, per BL-2.5's
    rejected restyle: `"<id>: CONTACT_CLASSIFICATION_CHANGED, <previous> ->
    <classification>, <summary>"`. This discharges BL-2.5's DoD "enrich
    mirrored lines" recommendation for this one new kind; it does not
    reopen the styling question for the three lifecycle kinds.

    Falls back to `"<contact_id>: <kind>"` if the contact is no longer found
    -- should not normally happen, since events are only ever derived from a
    contact that exists at tick time (`belief.contacts.ContactStore.tick`),
    but kept as a defensive fallback rather than an assumption this function
    bakes in.

    `enrichment` (BL-3, optional) appends one short semantic fragment --
    the highest-confidence `belief.enrichment.SemanticFact.text` among
    `facts["semantic"]`, if any -- to the mirrored line, whichever kind it
    is. `None` (the default) is a true no-op: the line is byte-for-byte
    BL-2.5's original, same overlay-restraint invariant as the rest of this
    module's optional fields.

    `result["summary"]` itself (read verbatim here, no separate handling
    needed) now also carries a clock-position/range fragment whenever
    `relative_now` is present in `facts` -- `belief.tools._contact_summary`'s
    addition (`plans/overlay-clock-range-summary/plan.md`), not something
    this function computes."""
    result = describe_contact(store, event.contact_id, now_sim, enrichment=enrichment)
    if result is None:
        return f"{event.contact_id}: {event.kind}"
    if event.kind == CONTACT_CLASSIFICATION_CHANGED:
        line = (
            f"{event.contact_id}: {event.kind}, "
            f"{event.previous_classification} -> {event.classification}, "
            f"{result['summary']}"
        )
    else:
        line = f"{event.contact_id}: {event.kind}, {result['summary']}"
    if enrichment is not None:
        semantic = result["facts"].get("semantic")
        if isinstance(semantic, list) and semantic:
            best = max(semantic, key=lambda fact: fact["confidence"])
            line += f" -- {best['text']}"
    return line


def _format_history_entry(entry: dict[str, object]) -> str:
    if entry.get("type") == "sighting":
        return (
            f"sighting source={entry['source']} "
            f"start_sim={entry['start_sim']} end_sim={entry['end_sim']}"
        )
    return f"event kind={entry['kind']} t_sim={entry['t_sim']} certainty={entry['certainty']}"
