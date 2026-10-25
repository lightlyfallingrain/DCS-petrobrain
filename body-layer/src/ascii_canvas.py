"""Shared ASCII-canvas primitives for this codebase's debug/calibration
views -- extracted from `eyesight_view.py` (`plans/pov-view/plan.md`,
`BL-B99`) so `pov_view.py` can reuse the same cell grid and colour
constants instead of forking them or reaching across a module boundary
for `_`-prefixed names.

Pure move + rename, no behaviour change: `Canvas`/`wrap` and the colour
constants are exactly `eyesight_view.py`'s old `_Canvas`/`_wrap`/
`_RESET`/etc., with the leading underscore dropped so they are a real
public API rather than private-by-convention names shared across a
module boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

RESET: Final[str] = "\x1b[0m"
DIM: Final[str] = "\x1b[2m"
BOLD: Final[str] = "\x1b[1m"
GREEN: Final[str] = "\x1b[32m"
BLUE: Final[str] = "\x1b[34m"
GRAY: Final[str] = "\x1b[90m"
YELLOW: Final[str] = "\x1b[33m"

#: Watched contacts (user, 2026-09-25). 256-colour orange rather than one of
#: the eight basic codes, because the basic set has no orange and the nearest
#: -- bright yellow -- is too close to `YELLOW` to distinguish a watched
#: contact from an ordinary one at a glance, which is the entire point.
ORANGE: Final[str] = "\x1b[38;5;208m"

#: The 9K113 narrow optic's own colour (user's scheme, `plans/pov-view/
#: plan.md`, `BL-B99`) -- 256-colour brown/khaki, visibly distinct from
#: `GRAY` (sight wide) and `YELLOW`/`ORANGE` (believed markers).
BROWN: Final[str] = "\x1b[38;5;130m"


def wrap(text: str, *codes: str, color: bool) -> str:
    """Apply ANSI `codes` to `text`, or return it unchanged when `color` is
    `False` -- the one place either caller branches on colour support, so
    every caller can simply pass `color=` through without its own
    conditional."""
    if not color or not codes:
        return text
    return "".join(codes) + text + RESET


@dataclass
class Canvas:
    rows: int
    cols: int

    def __post_init__(self) -> None:
        self.glyph: list[list[str]] = [[" "] * self.cols for _ in range(self.rows)]
        self.codes: list[list[tuple[str, ...]]] = [
            [() for _ in range(self.cols)] for _ in range(self.rows)
        ]

    def set(self, row: int, col: int, glyph: str, *codes: str) -> None:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.glyph[row][col] = glyph
            self.codes[row][col] = codes

    def set_if_blank(self, row: int, col: int, glyph: str, *codes: str) -> None:
        if (
            0 <= row < self.rows
            and 0 <= col < self.cols
            and self.glyph[row][col] == " "
        ):
            self.set(row, col, glyph, *codes)

    def render(self, *, color: bool) -> list[str]:
        lines = []
        for row in range(self.rows):
            cells = [
                wrap(self.glyph[row][col], *self.codes[row][col], color=color)
                for col in range(self.cols)
            ]
            lines.append("".join(cells))
        return lines


__all__ = [
    "BLUE",
    "BOLD",
    "BROWN",
    "DIM",
    "GRAY",
    "GREEN",
    "ORANGE",
    "RESET",
    "YELLOW",
    "Canvas",
    "wrap",
]
