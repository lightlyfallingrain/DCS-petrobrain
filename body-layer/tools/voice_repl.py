#!/usr/bin/env python3
"""Drive the voice command path from the keyboard, with no audio and no DCS.

Stage 2 of `plans/inbound-speech/plan.md` is deliberately testable without
hardware: body-layer receives `{transcript, confidence, token, match_ratio,
verb_anchored, ambiguous}` and decides what to do with it. This script builds
a `CrewConsole` over an empty `ContactStore` and drops you into its REPL, so
the act/confirm/say-again bands can be exercised by typing.

It exists because the obvious route -- `python -m logger --crew-text` -- needs
`--aircraft-layer-url`, `--theatre` and `--world-model-db`, all three
required, which means a running aircraft layer and therefore the Windows box.
That would gate a behaviour that has no hardware in it on hardware being
available, the same wrong dependency `tools/speak_samples.py` was written to
avoid.

Needs both `PYTHONPATH` entries and this subproject's own interpreter, same
as the live logger -- `belief.tasks` reaches `perception.geometry`, which
imports the world-model seam, which pulls in `pyproj`. What it does *not* need
is a running aircraft layer, a world-model database, or a theatre:

    PYTHONPATH=src:../world-model/src .venv/bin/python tools/voice_repl.py

Type `!voice` with no arguments for the usage line, or `help`. The contact
store starts empty, so commands that need a contact (`watch_nearest`) will
correctly report having nothing to watch -- that is the band behaviour under
test, not a failure.
"""

from __future__ import annotations

import sys

from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.tasks import TaskStore


def main() -> int:
    store = ContactStore()
    console = CrewConsole(store=store, tasks=TaskStore())
    now_sim = 0.0

    print("Petrovich voice-path REPL -- no audio, no DCS.")
    print(
        "  !voice <token|-> <match_ratio> <confidence> "
        "<verb_anchored:0|1> <ambiguous:0|1> <transcript...>"
    )
    print("  !time <seconds>   advance simulated time (for confirm expiry)")
    print("  quit\n")

    while True:
        try:
            line = input(f"[t={now_sim:6.1f}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("quit", "exit"):
            return 0
        if line.startswith("!time"):
            parts = line.split()
            if len(parts) != 2:
                print("usage: !time <seconds>")
                continue
            try:
                now_sim += float(parts[1])
            except ValueError:
                print("usage: !time <seconds>")
                continue
            print(f"  (simulated time is now {now_sim:.1f}s)")
            continue
        console.handle_line(line, now_sim)


if __name__ == "__main__":
    sys.exit(main())
