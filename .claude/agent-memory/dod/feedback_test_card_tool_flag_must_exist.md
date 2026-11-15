---
name: test-card-tool-flag-must-exist
description: A test card's reduction/inspection command can name a flag the tool does not have; run --help on the named tool before trusting the card, not just the pilot-facing steps.
metadata:
  type: feedback
---

BL-B112's `test-card.md` Case 5 told the tester to run
`python3 .claude/skills/sortie-log-triage/scripts/triage.py --mission-memory <path>` after landing.
Running `triage.py --help` showed no `--mission-memory` flag exists at all — the script's own
comments explicitly note mission-memory is *not* one of the logs it reduces. The command would
have failed on the user's first attempt, exactly the failure class this role's own instructions
already name repeatedly ("five acceptance cards... never executed").

**Why this one is a distinct sub-case worth naming**: every prior instance involved a command that
ran but did the wrong thing (wrong port, inverted args, wrong console). This one never got that
far — the flag itself doesn't exist, caught by `--help`, not by running the full command and
reading garbage output. **How to apply:** for any card command that invokes a project script/tool
with flags, run `<tool> --help` (or read its `argparse` block) first, before running the full
command with real-looking arguments — it is faster and catches this exact class without needing a
live log file to test against. Fixed by replacing the card's command with a direct
`python3 -c "..."` JSONL read, verified against a synthetic fixture matching
`mission_memory/entries.py`'s `encode_entry` shape (`kind`/`t_sim`/`payload` keys).
