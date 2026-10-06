"""Per-run log filenames -- `BL-11` Stage 5.

**The three JSONL log writers all opened their file with `"a"` and never
rolled it**, so one path accumulated every sortie ever flown. The detection
trace alone writes one row per candidate per poll -- ~290 KB/poll, ~50 MB a
minute, 1-3.5 GB a sortie -- and the 2026-10-05 analysis consequently had
to locate byte offset 2,448,471,603 to find that flight's region at all
(`body-layer/research/2026-10-05-performance-review.md` finding 6). A debug
artifact that cannot be addressed by sortie is one that stops being read.

`per_run_log_path` stamps the run's start time into the filename, so each
run writes its own file and the previous sortie stays where it was.

**Timestamped rather than truncate-on-open, deliberately.** Truncating
would also remove the byte-offset archaeology, and is one line shorter --
but it silently destroys the previous flight's log, and the user reads
these after landing. Two sorties in one evening would leave only the
second, with nothing to say the first had ever been recorded. A new name
per run costs disk the user can see and delete.

Applied at the CLI boundary (`logger.main`), not inside the writers: a
writer handed an exact path still writes exactly there, which is what keeps
them straightforward to test and what lets `tools/` read a specific file.
That boundary (`logger._per_run_log_paths`) is also where `~` gets expanded
and the resolved path's parent directory gets created -- `per_run_log_path`
below renames and nothing more, and the writers `open(..., "a")` unguarded,
so the `mkdir` has to happen between them or a missing `logs/` is a startup
crash.
"""

from __future__ import annotations

import time
from pathlib import Path

#: `strftime` format for the stamp inserted into a log filename. Sortable
#: as text, no characters that need quoting in a shell, and second
#: resolution -- two runs started in the same second would collide, which
#: in practice means starting the logger twice within one second against
#: the same path, and the fallback then is the old append behaviour rather
#: than a lost file.
RUN_STAMP_FORMAT = "%Y%m%d-%H%M%S"


def run_stamp(when: float | None = None) -> str:
    """`when` (epoch seconds, default now) as a `RUN_STAMP_FORMAT` stamp in
    local time -- local because the reader correlating a log against a
    sortie they remember flying thinks in their own clock."""
    return time.strftime(RUN_STAMP_FORMAT, time.localtime(when))


def per_run_log_path(path: Path, when: float | None = None) -> Path:
    """`path` with this run's stamp inserted before its suffix:
    `logs/trace.jsonl` -> `logs/trace-20261006-143500.jsonl`.

    A path with no suffix simply gains the stamp at the end. The directory
    and every other component are left exactly as given -- this renames the
    file, it never relocates it, so a user who passed an explicit
    `--detection-trace /big/disk/trace.jsonl` still writes to `/big/disk`.
    """
    return path.with_name(f"{path.stem}-{run_stamp(when)}{path.suffix}")
