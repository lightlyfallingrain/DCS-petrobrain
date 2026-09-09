"""Line parser + pretty-printer over `belief.tools` -- `plans/
pb2-contact-memory/plan.md` Stage 4's debug console, the literal ancestor of
§3.3's brain tool set (`plans/body-layer/plan.md`'s BL-2 summary: "every
command added here should be one that later becomes a brain tool").

Owns **no belief logic**. Every command below maps 1:1 to a `belief.tools`
function; this module's job is only to split an input line into a command +
argument, call the matching tool, and format whatever it returns as text.
If a future command needs new belief-state logic, that logic belongs in
`tools.py` (or a `belief/` module `tools.py` itself calls), never inline
here -- see `tools.py`'s own module docstring on why `watch`/`unwatch`/
`stats` have tool functions despite not being one of §3.3's four.

    contacts [all|visible|watched]  -> tools.get_contacts
    show <id>                       -> tools.describe_contact
    history <id>                    -> tools.get_contact_history
    find <text>                     -> tools.find_contact
    watch <id>                      -> tools.watch_contact
    unwatch <id>                    -> tools.unwatch_contact
    stats                           -> tools.get_stats
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TextIO

from belief.contacts import ContactStore
from belief.events import Event
from belief.tools import (
    ContactFilter,
    ContactResult,
    describe_contact,
    find_contact,
    get_contact_history,
    get_contacts,
    get_stats,
    unwatch_contact,
    watch_contact,
)

#: Printed once at REPL startup (`logger.py`'s `main()`) -- kept in sync with
#: the module docstring's command table above by hand; both list the same
#: seven commands because `handle_line`'s dispatch is the single source of
#: truth for what actually exists.
HELP_TEXT = """\
Petrovich belief console -- commands:
  contacts [all|visible|watched]  list contacts (default: all)
  show <id>                       full detail for one contact
  history <id>                    a contact's sighting/event history
  find <text>                     search contacts by classification text
  watch <id>                      mark a contact watched
  unwatch <id>                    clear a contact's watched mark
  stats                           observation/contact/event counts
"""

_CONTACT_FILTERS: tuple[ContactFilter, ...] = ("all", "visible", "watched")

#: `_contact_result`'s `facts` keys, in display order, for `show <id>`'s
#: multi-line block -- listed explicitly (rather than iterating the dict)
#: so the block's order is stable regardless of `dict` insertion order.
_SHOW_FACT_KEYS: tuple[str, ...] = (
    "classification",
    "certainty",
    "visible",
    "last_seen_ago_s",
    "position",
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

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        lines = _dispatch(self.store, line, now_sim)
        if self.output is not None:
            for formatted in lines:
                print(formatted, file=self.output)
        return lines


def _dispatch(store: ContactStore, line: str, now_sim: float) -> list[str]:
    stripped = line.strip()
    if not stripped:
        return []
    command, _, rest = stripped.partition(" ")
    command = command.lower()
    rest = rest.strip()

    if command == "contacts":
        return _handle_contacts(store, rest, now_sim)
    if command == "show":
        return _handle_show(store, rest, now_sim)
    if command == "history":
        return _handle_history(store, rest)
    if command == "find":
        return _handle_find(store, rest, now_sim)
    if command == "watch":
        return _handle_watch(store, rest)
    if command == "unwatch":
        return _handle_unwatch(store, rest)
    if command == "stats":
        return _handle_stats(store)
    return [f"unknown command: {command}"]


def _handle_contacts(store: ContactStore, rest: str, now_sim: float) -> list[str]:
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
    results = get_contacts(store, now_sim, filter=filter_arg)
    if not results:
        return ["no contacts"]
    return [_format_contact_line(result) for result in results]


def _handle_show(store: ContactStore, rest: str, now_sim: float) -> list[str]:
    if not rest:
        return ["usage: show <id>"]
    result = describe_contact(store, rest, now_sim)
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


def _handle_find(store: ContactStore, rest: str, now_sim: float) -> list[str]:
    if not rest:
        return ["usage: find <text>"]
    results = find_contact(store, rest, now_sim)
    if not results:
        return [f"no matches for '{rest}'"]
    return [_format_contact_line(result) for result in results]


def _handle_watch(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: watch <id>"]
    found = watch_contact(store, rest)
    return [f"watching {rest}" if found else f"no such contact: {rest}"]


def _handle_unwatch(store: ContactStore, rest: str) -> list[str]:
    if not rest:
        return ["usage: unwatch <id>"]
    found = unwatch_contact(store, rest)
    return [f"no longer watching {rest}" if found else f"no such contact: {rest}"]


def _handle_stats(store: ContactStore) -> list[str]:
    stats = get_stats(store)
    return [
        (
            f"contacts={stats['contacts']} "
            f"observations={stats['observations']} "
            f"events={stats['events']}"
        )
    ]


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


def format_event_for_overlay(store: ContactStore, event: Event, now_sim: float) -> str:
    """One line for BL-2.5's in-cockpit overlay mirror
    (`logger.ConsolePerceptionRunner`, `plans/dcs-text-panel-output/plan.md`):
    `"<kind>: <summary>"` for the event's contact, reusing
    `describe_contact`'s existing `summary` field rather than inventing new
    belief-reading logic here (this module owns no belief logic, see the
    module docstring).

    Falls back to `"<kind> <contact_id>"` if the contact is no longer found
    -- should not normally happen, since events are only ever derived from a
    contact that exists at tick time (`belief.contacts.ContactStore.tick`),
    but kept as a defensive fallback rather than an assumption this function
    bakes in."""
    result = describe_contact(store, event.contact_id, now_sim)
    if result is None:
        return f"{event.kind} {event.contact_id}"
    return f"{event.kind}: {result['summary']}"


def _format_history_entry(entry: dict[str, object]) -> str:
    if entry.get("type") == "sighting":
        return (
            f"sighting source={entry['source']} "
            f"start_sim={entry['start_sim']} end_sim={entry['end_sim']}"
        )
    return f"event kind={entry['kind']} t_sim={entry['t_sim']} certainty={entry['certainty']}"
