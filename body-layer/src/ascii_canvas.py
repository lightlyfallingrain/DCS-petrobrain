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

#: Ground-truth marker glyphs, shared between `eyesight_view.py`'s top-down
#: view and `pov_view.py`'s forward-POV twin so the two can never render a
#: ground-truth "seen"/"not seen" marker differently (`plans/pov-view/
#: review.md` Required Fix 1 -- `pov_view.py` had reinvented its own `.`/`x`
#: pair instead of reusing these). Deliberately distinct from the optic
#: FOV's own dot glyph (plain `.`), which the user specified directly
#: ("draw the current optic's FOV with dots '.'") and must not be confused
#: with either of these.
GROUND_TRUTH_SEEN_GLYPH: Final[str] = "·"
GROUND_TRUTH_NOT_SEEN_GLYPH: Final[str] = "×"

#: Per-optic background tints for `pov_view.py`'s optic-FOV highlight
#: (user amendment, 2026-10-25: "the optics FOV highlight could use
#: background color instead" -- a disc painted as `.` dots hides whatever
#: glyph already occupied the cell; a background tint does not). Dim
#: 256-colour backgrounds, deliberately darker than the matching
#: foreground constant above (`BLUE`/`GRAY`/`BROWN`) so a bold yellow/
#: orange marker label or the ground-truth `·`/`×` glyph stays readable
#: painted on top of one. `BG_BROWN` reuses `BROWN`'s own 256-colour index
#: (130) as a background instead of a foreground -- one "brown" in the
#: palette, not two unrelated numbers.
BG_BLUE: Final[str] = "\x1b[48;5;24m"
BG_GRAY: Final[str] = "\x1b[48;5;240m"
BG_BROWN: Final[str] = "\x1b[48;5;130m"


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
        self.bg: list[list[str | None]] = [[None] * self.cols for _ in range(self.rows)]

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

    def set_bg(self, row: int, col: int, code: str) -> None:
        """Paint a background tint on one cell, independent of its
        glyph/foreground layer -- composes with whatever `set`/
        `set_if_blank` already put there (or will put there later; order
        between the two does not matter), rather than overwriting it.
        `pov_view.py`'s optic-FOV highlight is the one caller; `eyesight_
        view.py` never calls this, so its `render_frame` and tests are
        unaffected by this layer's existence (additive, `bg` defaults
        `None` everywhere)."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.bg[row][col] = code

    def render(self, *, color: bool) -> list[str]:
        lines = []
        for row in range(self.rows):
            cells = []
            for col in range(self.cols):
                codes = self.codes[row][col]
                bg_code = self.bg[row][col]
                if bg_code is not None:
                    codes = (*codes, bg_code)
                cells.append(wrap(self.glyph[row][col], *codes, color=color))
            lines.append("".join(cells))
        return lines


__all__ = [
    "BG_BLUE",
    "BG_BROWN",
    "BG_GRAY",
    "BLUE",
    "BOLD",
    "BROWN",
    "DIM",
    "GRAY",
    "GREEN",
    "GROUND_TRUTH_NOT_SEEN_GLYPH",
    "GROUND_TRUTH_SEEN_GLYPH",
    "ORANGE",
    "RESET",
    "YELLOW",
    "Canvas",
    "wrap",
]
