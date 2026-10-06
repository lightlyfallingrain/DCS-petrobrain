---
name: phrase-table-single-word-false-positive-class
description: Bare single-word transcripts fuzzy-matching a short phrasing is an accepted, pre-existing class in audio-adapter — probe the baseline table before calling a new synonym a finding.
metadata:
  type: project
---

`command_matcher.match_transcript` rejects ordinary *sentences* well (word-sequence scoring, not
character streams) but a **bare single word** at `MATCH_FLOOR` 0.6 collides freely with any short
phrasing. Measured on the pre-change table (`896369e`, 2026-10-06): `"shop"` → `stop_talking`
0.75, `"support"` → `report_all` 0.615, `"hollow"`/`"fallow"` → `follow` 0.833. `"record"` →
`report_all` is deliberate (whisper mishears "report").

So adding `"describe"` producing `"descend"` → `report_all` 0.667 and `"prescribe"` → 0.823 is one
more instance, not a new weakness.

**Why:** `VERB_FLOOR` (0.5) sits *below* `MATCH_FLOOR` on the stated grounds that a false
rejection is the worse, irreversible error — a real command discarded as free speech. The
false-positive rate is a tuned acceptance, and re-litigating it per synonym is cost without signal.

**How to apply:** when reviewing a new phrase/synonym, run the same probe against **both** the
baseline and the branch table (stdlib only, no venv needed — `sys.path.insert(0, "src")` then
`match_transcript`), and report a new collision only with the baseline comparison attached. Report
it as a note for the user, not a required fix. The one thing worth saying out loud is when the
colliding word is a real cockpit word (`"descend"` was), because the consequence is an
*unsolicited* callout — which matters more when a spontaneous-callout defect is live.
