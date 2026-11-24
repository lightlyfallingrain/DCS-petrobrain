# PTT speech hold — test card (2026-11-24)

**Branch to fly: `main`**, once this feature merges (DoD passed; the merge follows this report).
`git pull` in the repo root to pick it up.

**What this measures:** whether Petrovich correctly holds off starting a routine line while you
are holding the ICS or RADIO trigger, speaks urgent lines immediately regardless, and never cuts
off a line already in progress. Source: `body-layer/ROADMAP/BL-B133.md`, `plans/
bl-b133-ptt-speech-hold/`.

## Setup

Normal flight, either seat, no special startup flags — this is the production crew pipeline, not
a probe. Give Petrovich time to accumulate a few routine callouts (contacts, status lines) before
testing so there is something queued to hold against.

## Test cases

1. **Hold ICS while Petrovich is about to say something routine, then release.**
   Press and hold the intercom trigger during normal flight until you expect a routine line
   (a contact callout, a status update) is about to come. Hold for a few seconds, then release.
   *Expect:* no new line starts while ICS is held. Shortly after release (a fraction of a second,
   not a noticeable delay), the line starts.

2. **Same with RADIO.**
   *Expect:* identical behaviour — either trigger holds routine speech, not just one of them.

3. **Trigger an urgent line while holding either trigger.**
   While holding ICS or RADIO, do something that should produce an urgent line — the clearest is
   a forced handback ("You have controls!") if one is available to trigger in your current setup;
   any line you know is marked urgent works. *Expect:* the urgent line speaks immediately, even
   though the trigger is still held down. It does not wait for release.

4. **Hold the trigger through a line already playing.**
   Let Petrovich start speaking a line, then press and hold ICS or RADIO partway through.
   *Expect:* the line already playing is **not** cut off — it finishes normally. Only the *next*
   line (if routine) waits for release.

5. **(Optional, if the flight runs long) A held trigger during a long radio exchange.**
   If you end up holding RADIO for an extended stretch (a couple of minutes or more) during a
   real exchange, note whether Petrovich ever starts talking over you anyway. By design, a held
   trigger is only trusted for as long as the telemetry feed itself keeps refreshing — this is
   the one open question in the implementation (see `belief/ptt_hold.py`'s module docstring), and
   a real long hold is the only way to probe it.

## Report back

- Test case 1 and 2: did holding either trigger correctly stop a routine line from starting? Did
  it start promptly after release, or was there a noticeable lag?
- Test case 3: did the urgent line speak while you were still holding the trigger?
- Test case 4: did an in-progress line ever get cut off by pressing the trigger mid-line?
- Test case 5, if you hit it: did Petrovich ever start talking over a long held trigger?
- Anything that surprises you is worth more than anything on this list.
