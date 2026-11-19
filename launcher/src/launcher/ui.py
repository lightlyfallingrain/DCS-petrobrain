"""The curses screen: settings, one line per service, expandable options and log.

Keys (user's spec, 2026-11-17): up/down move; Space toggles an option or expands/collapses;
Enter toggles a service or expands/collapses; a digit toggles service N; Ctrl-C stops everything
and exits. Options toggle only while their service is OFF (user, 2026-11-19).
"""

from __future__ import annotations

import curses
import signal
import threading
from dataclasses import dataclass
from pathlib import Path

from launcher.helpparse import HelpOption, parse_help
from launcher.procs import RunState, ServiceProcess, read_help
from launcher.services import (
    OptionState,
    Service,
    build_args,
    env_key,
    option_state,
    script_flags,
)

LOG_LINES_SHOWN = 10
HINT = "up/down move  Space/Enter expand/toggle  1-9 service on/off  Ctrl-C stop all and quit"

Segment = tuple[str, int]  # text, curses attribute


@dataclass
class Row:
    segments: list[Segment]
    key: tuple[str, ...] | None = None  # None: not selectable


class App:
    def __init__(
        self,
        services: tuple[Service, ...],
        scripts_dir: Path,
        env: dict[str, str],
        version: str,
        notice: str,
    ) -> None:
        self.services = services
        self.scripts_dir = scripts_dir
        self.env = env
        self.version = version
        self.notice = notice
        self.procs = {s.name: ServiceProcess(s, scripts_dir) for s in services}
        self.expanded: set[tuple[str, ...]] = set()
        self.options: dict[str, list[HelpOption]] = {}
        self.help_error: dict[str, str] = {}
        self.loading: set[str] = set()
        self.enabled: dict[str, set[str]] = {s.name: set() for s in services}
        self.in_script: dict[str, set[str]] = {}
        for s in services:
            try:
                self.in_script[s.name] = script_flags(
                    (scripts_dir / s.script).read_text()
                )
            except OSError:
                self.in_script[s.name] = set()
        self.cursor_key: tuple[str, ...] = (
            ("svc", services[0].name) if services else ("settings",)
        )
        self.green = self.red = self.yellow = 0

    # ---- actions -------------------------------------------------------------------------------

    def visible_options(self, name: str) -> list[HelpOption]:
        svc = next(s for s in self.services if s.name == name)
        return [o for o in self.options.get(name, []) if o.flag not in svc.hidden]

    def start(self, name: str) -> None:
        enabled = [
            o for o in self.visible_options(name) if o.flag in self.enabled[name]
        ]
        self.procs[name].start(build_args(name, enabled, self.env))

    def toggle_service(self, name: str) -> None:
        proc = self.procs[name]
        state = proc.state
        if state is RunState.OFF:
            self.start(name)
        elif state is RunState.ON:
            proc.stop_async()

    def toggle_option(self, name: str, flag: str) -> None:
        if self.procs[name].state is not RunState.OFF:
            return
        opt = next((o for o in self.visible_options(name) if o.flag == flag), None)
        if opt is None:
            return
        if (
            option_state(name, opt, self.in_script[name], self.env)
            is not OptionState.TOGGLEABLE
        ):
            return
        self.enabled[name] ^= {flag}

    def toggle_expand(self, key: tuple[str, ...]) -> None:
        self.expanded ^= {key}
        if key[0] == "opt" and key in self.expanded:
            self.load_options(key[1])

    def load_options(self, name: str) -> None:
        if name in self.options or name in self.loading:
            return
        self.loading.add(name)
        svc = next(s for s in self.services if s.name == name)

        def work() -> None:
            text = read_help(svc, self.scripts_dir)
            opts = parse_help(text)
            if not opts:
                lines = [ln for ln in text.splitlines() if ln.strip()]
                self.help_error[name] = lines[-1] if lines else "no --help output"
            self.options[name] = opts
            self.loading.discard(name)

        threading.Thread(target=work, daemon=True).start()

    def activate(self, key: tuple[str, ...], enter: bool) -> None:
        kind = key[0]
        if kind == "svc":
            if enter:
                self.toggle_service(key[1])
        elif kind == "optrow":
            self.toggle_option(key[1], key[2])
        else:
            self.toggle_expand(key)

    # ---- rendering -----------------------------------------------------------------------------

    def status_segment(self, name: str) -> Segment:
        state = self.procs[name].state
        if state is RunState.ON:
            return ("ON", self.green | curses.A_BOLD)
        if state is RunState.STOPPING:
            return ("STOPPING", self.yellow | curses.A_BOLD)
        return ("OFF", self.red | curses.A_BOLD)

    def rows(self) -> list[Row]:
        dim = curses.A_DIM
        rows: list[Row] = [Row([(" * settings", 0)], ("settings",))]
        if ("settings",) in self.expanded:
            if not self.env:
                rows.append(Row([("   | (no petrobrain.env found)", dim)]))
            for k, v in self.env.items():
                rows.append(Row([(f"   | {k}={v}", 0)]))
        rows.append(Row([("", 0)]))
        for i, svc in enumerate(self.services, start=1):
            name = svc.name
            rows.append(
                Row(
                    [(f" {i} - {name:<24}", 0), self.status_segment(name)],
                    ("svc", name),
                )
            )
            rows.append(Row([("     |-> options", 0)], ("opt", name)))
            if ("opt", name) in self.expanded:
                rows.extend(self.option_rows(name))
            rows.append(Row([("     |-> log", 0)], ("log", name)))
            if ("log", name) in self.expanded:
                tail = list(self.procs[name].log)[-LOG_LINES_SHOWN:]
                if not tail:
                    rows.append(Row([("       | (no output yet)", dim)]))
                for line in tail:
                    rows.append(Row([(f"       | {line}", 0)]))
            rows.append(Row([("", 0)]))
        return rows

    def option_rows(self, name: str) -> list[Row]:
        dim = curses.A_DIM
        if name in self.loading or name not in self.options:
            return [Row([("       | loading --help ...", dim)])]
        opts = self.visible_options(name)
        if not opts:
            return [
                Row([(f"       | no options: {self.help_error.get(name, '')}", dim)])
            ]
        locked = self.procs[name].state is not RunState.OFF
        out: list[Row] = []
        for opt in opts:
            state = option_state(name, opt, self.in_script[name], self.env)
            key = ("optrow", name, opt.flag)
            if state is OptionState.IN_SCRIPT:
                text = f"       | [=] {opt.flag:<28} - set in run script"
                out.append(Row([(text, dim)], key))
                continue
            label = opt.flag
            if opt.takes_value and state is OptionState.TOGGLEABLE:
                label = f"{opt.flag} {self.env[env_key(name, opt.flag)]}"
            box = "[x]" if opt.flag in self.enabled[name] else "[ ]"
            desc = opt.help
            if state is OptionState.NO_VALUE:
                desc = f"needs {env_key(name, opt.flag)} in petrobrain.env"
            text = f"       | {box} {label:<28} - {desc}"
            attr = dim if locked or state is not OptionState.TOGGLEABLE else 0
            out.append(Row([(text, attr)], key))
        return out

    def header(self, width: int) -> list[Row]:
        rule = "=" * min(width - 1, 70)
        return [
            Row([(rule, 0)]),
            Row([(f"Petrobrain {self.version}".center(len(rule)), curses.A_BOLD)]),
            Row([(rule, 0)]),
            Row([(f" {HINT}", curses.A_DIM)]),
            Row([(f" {self.notice}", self.yellow) if self.notice else ("", 0)]),
        ]

    def draw(self, scr: curses.window) -> None:
        height, width = scr.getmaxyx()
        scr.erase()
        head = self.header(width)
        body = self.rows()
        keys = [r.key for r in body if r.key is not None]
        if self.cursor_key not in keys and keys:
            self.cursor_key = keys[0]
        cursor_at = next((i for i, r in enumerate(body) if r.key == self.cursor_key), 0)
        room = max(1, height - len(head))
        top = max(0, cursor_at - room + 3) if cursor_at >= room - 2 else 0
        for y, row in enumerate(head + body[top : top + room]):
            if y >= height:
                break
            x = 0
            selected = (
                y >= len(head) and row.key is not None and row.key == self.cursor_key
            )
            for text, attr in row.segments:
                if x >= width - 1:
                    break
                try:
                    scr.addnstr(
                        y,
                        x,
                        text,
                        width - 1 - x,
                        attr | (curses.A_REVERSE if selected else 0),
                    )
                except curses.error:
                    pass
                x += len(text)
        scr.refresh()

    def move(self, delta: int) -> None:
        keys = [r.key for r in self.rows() if r.key is not None]
        if not keys:
            return
        i = keys.index(self.cursor_key) if self.cursor_key in keys else 0
        self.cursor_key = keys[max(0, min(len(keys) - 1, i + delta))]

    # ---- loop ----------------------------------------------------------------------------------

    def run(self, scr: curses.window, autostart: list[str]) -> None:
        curses.curs_set(0)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            self.green, self.red, self.yellow = (
                curses.color_pair(n) for n in (1, 2, 3)
            )
        scr.timeout(200)
        for name in autostart:
            self.start(name)
        try:
            while True:
                self.draw(scr)
                ch = scr.getch()
                if ch == curses.KEY_UP:
                    self.move(-1)
                elif ch == curses.KEY_DOWN:
                    self.move(1)
                elif ch in (curses.KEY_ENTER, 10, 13):
                    self.activate(self.cursor_key, enter=True)
                elif ch == ord(" "):
                    self.activate(self.cursor_key, enter=False)
                elif ord("1") <= ch <= ord("9"):
                    n = ch - ord("1")
                    if n < len(self.services):
                        self.toggle_service(self.services[n].name)
        except KeyboardInterrupt:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            self.notice = "Ctrl-C: stopping all services ..."
            self.draw(scr)
            self.stop_all()

    def stop_all(self) -> None:
        threads = [
            threading.Thread(target=p.stop_and_wait, daemon=True)
            for p in self.procs.values()
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
