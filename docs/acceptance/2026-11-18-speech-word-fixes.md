# speech-word-fixes acceptance sortie (2026-11-18)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/PqQ7et63fDCyxYR2MU9gsp
**Card source:** `docs/acceptance/2026-11-18-speech-word-fixes-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge (`git checkout main && git pull`).

**What is under test:** `[[BL-B129]]` — six fixes to the flight voice commands, found by running
`phrase_bench.py` against a corpus of the user's own recorded voice (`plans/speech-word-fixes/
plan.md`). This card is **text-level verified, not microphone-verified**: every phrase below was
run through the real `rule_patterns`/`command_matcher` pipeline directly against the real
`flight.lua` rule set (not a hand-built fixture), and the results below are pasted straight from
that run, not predicted from reading the code. What that run *cannot* exercise is whisper's own
speech-to-text step — whether these exact words, spoken aloud through the headset, come out as
this exact text. That part is `#needs-flight` on `body-layer/ROADMAP/BL-B129.md`.

## Do / expect / record

1. **Do:** say "altitude three hundred."
   **Expect:** Petrovich holds 300 m and reads it back ("300 meters" or "300 meters barometric").
   **Verified (text-level):** `set_altitude`, `altitude_m=300`. ✓
   **Record:** did he hold 300 m, or say "say again"?

2. **Do:** say "hold altitude."
   **Expect:** he holds the current altitude and reads it back ("Holding N meters").
   **Verified (text-level):** `hold_altitude`. ✓
   **Record:** did he hold, or say "say again" / mishear it as "hold out"? (This is the exact
   defect D1 fixed — "alt" used to get heard as "out" 2 times in 4 on the bench.)

3. **Do:** say "turn left three zero" (not "turn left thirty" — digits, not number words; D2 was
   measured and explicitly not shipped, so "thirty" still does not work).
   **Expect:** a 30° left turn, readback "30 left."
   **Verified (text-level):** `turn_heading_relative`, `direction=left`, `degrees=30`. ✓
   **Record:** did it turn 30° left?

4. **Do:** say "turn heading two seven zero."
   **Expect:** turns to heading 270, readback "Heading 270."
   **Verified (text-level):** `turn_heading`, `heading_deg=270`. ✓ — **this is the D6 fix**: before
   it, the real shipped rule silently required the word "heading" twice ("turn heading heading two
   seven zero") and this exact phrase would have failed.
   **Record:** did it turn to 270, or say "say again"?

5. **Do:** say "turn heading to seven zero" (deliberately say "to" instead of "two" — this is the
   D3 homophone fix, for when whisper hears "to" instead of "two").
   **Expect:** same result as #4 — heading 270.
   **Verified (text-level):** `turn_heading`, `heading_deg=270`. ✓
   **Record:** did "to" resolve to 270, or get rejected / resolve to something else?

6. **Do:** say "right" alone (HVRT translate, while in the operator seat with AI hover mode active).
   **Expect:** translates right, readback "Right."
   **Verified (text-level):** `hvrt_translate_right`. ✓

7. **Do:** say "alright" alone, in the same HVRT context as #6.
   **Expect:** same as #6 — translates right, readback "Right." (This is the D4 fix — before it,
   "alright" was the one WRONG-command case on the bench, resolving to the legacy `point` command
   instead.)
   **Verified (text-level):** `hvrt_translate_right`. ✓
   **Record:** did "alright" do the same thing as "right", or trigger `point`/something else?

8. **Do:** say "right four five" or "right forty five" — deliberately **without** the word "turn".
   **Expect:** "say again" — **never** a silent `point` command. This is the D5 fix: before it, a
   dropped "turn" (a real whisper failure mode, not a hypothetical) made this resolve to `point`
   with no indication anything had gone wrong.
   **Verified (text-level):** `token=None` (falls through to "say again"). ✓
   **Record:** did it say "say again", or silently do something (check the belief/attention state
   for an unexpected `point` task)?

9. **Do:** say "heading two seven zero" — **without** "turn" or "fly" in front of it.
   **Expect:** this is **not** `turn_heading` — the verb is required now (D6). It falls through to
   the legacy bearing-report path (`scan_bearing_deg`-style), not a flight command.
   **Verified (text-level):** resolves to `scan_bearing_deg`, not `turn_heading`. ✓
   **Record:** did the aircraft actually turn (wrong — would mean the verb requirement is not
   enforced in the live pipeline), or did it just report a bearing / do nothing flight-wise
   (right)?

## Numbers — say digits, not number words

Composed number words ("thirty", "forty-five") are **not** recognized — D2 (a prompt-bias
experiment to make whisper write numerals directly) was tried and measured worse on every count,
so it was not shipped. Say numbers **digit by digit**: "three zero" for 30, "two seven zero" for
270, "four five" for 45.

## UNVERIFIED — not run by this DoD pass

Every phrase above was verified against the real matching code with the exact text typed in — it
was never spoken, captured by a microphone, or passed through whisper. The speech-to-text step
(does saying these words aloud actually produce this text) needs a live DCS session with the
headset and is marked `#needs-flight` on `body-layer/ROADMAP/BL-B129.md` rather than held open as a
merge blocker (testing debt accepted in batches, 2026-10-26/2026-11-15 user direction).

## Bring back

- Any phrase above that didn't do what's expected — say exactly what you said and what happened.
- Whether "to" (item 5) and "alright" (item 7) sounded natural to say, or felt like you were
  performing for the matcher rather than talking normally — that's worth knowing even if they
  worked.
- Anything that surprises you is worth more than anything on this list.
