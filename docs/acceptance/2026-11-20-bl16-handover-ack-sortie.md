# BL-16 mode 1 handover — take-ack seq fix + telemetry wire fix

**Branch to fly: `main`, after merge.** `git checkout main && git pull` in the repo root.

DoD passed on `fix/handover-ack-seq`, tip `666b4d98` (Security APPROVED). Two defects fixed from
the 2026-11-19 sortie feedback (`docs/acceptance/2026-11-19-mode1-handover-feedback.md`):

1. **The real root cause**: `core.lua` wrote every wire number as `%.5f`, so a sequence counter
   went out as `-1.00000` — valid Lua, invalid against the schema's strict `int` fields. Every
   `flight_control` telemetry line has been silently dropped since 2026-11-18 (`307d6a81`), and
   `ai_pilot_wheel` lines dropped from the first goal/combat-trim command onward. This alone would
   explain "unable, not flying" in **both** mode 1 and mode 2, independent of anything else below.
2. **A real, secondary defect**: the take-ack seq compared two unrelated counters, so a voice
   "take" could never confirm; the ack timeout left Lua still flying the axes with belief back at
   "pilot"; "I have controls" from that state was a silent no-op.

## Redeploy first — this is a Lua-side fix

Copy the whole `aircraft-layer/dcs-export/Petrobrain/` folder to
`Saved Games\DCS\Scripts\Petrobrain\` (not just the three changed files — standard practice here,
`aircraft-layer/WORKFLOW.md`). The three files that actually changed are `core.lua`,
`flight_control.lua`, `ai_pilot_wheel.lua`; copying the whole folder is what the project always
does and avoids a stale sibling file. Watch the collector's startup log for the `Export.lua`
version match (same `WORKFLOW.md` section) to confirm the deploy actually took.

## Setup

```sh
git checkout main
```

Air start, mode 1 (unparked, raw axes), straight and level — same conditions as the 2026-11-19
sortie that found this.

**Pre-flight check (can be done sitting on the ramp, before takeoff) — confirms defect 1 is
actually fixed:**

```sh
curl -s http://<collector-host>:7791/flight_control/latest
curl -s http://<collector-host>:7791/ai_pilot_wheel/latest
```

**Expect:** both return a real JSON object (not `null`), and the Windows collector console shows
no `dropping malformed ... line` warnings. If either is still `null` or the warning is still
there, stop — the deploy did not take (most likely the old `Petrobrain/` folder is still in
`Saved Games`), and nothing below will work either.

## Test blocks

### 1. Take controls — the prize

**Do:** "you have controls."
**Expect:** Petrovich confirms ("You have controls.") within about 2 seconds — not "Unable, not
ready." Before this fix, the take ack could never match and this always timed out.
**Record:** did it confirm, and roughly how long did it take?

### 2. Fly a command after taking controls

**Do:** immediately after block 1 confirms, "turn right two zero."
**Expect:** the aircraft actually turns — not "Unable, not flying."
**Record:** did the turn happen as commanded?

### 3. Give controls back

**Do:** "I have controls."
**Expect:** Petrovich says "You have controls." (the recovery phrase, Decision 13) and the stick
visibly answers to your input again.
**Record:** did control actually come back, and did it speak?

### 4. Repeat the full cycle once more

**Do:** "you have controls" → wait for confirmation → a command → "I have controls."
**Expect:** same as blocks 1–3, with no leftover confusion from the first cycle (no stray "Unable,
not ready"/"not flying" from a stale state).
**Record:** anything different the second time through.

### 5. The safety nets (observe only — do not force them)

These two paths exist for when the take ack is late or lost; with defect 2 actually fixed, you
should not be able to trigger them in ordinary flying, so there is nothing to deliberately do
here. **If** "unable, not ready" or "unable, not flying" appears at any point during blocks 1–4,
that is itself the finding — note exactly what you said and what Petrovich said back, since it
would mean one of the two root causes is not fully closed.

## Also clears — batch this with the same flight

The last two sorties flown before this fix (mode-2 P3+P4 align/break, and the mode-1 break/rotor
batch, both merged 2026-11-19) were marked `#needs-flight` and **could not actually have produced
working telemetry**, since defect 1 above has been silently dropping `flight_control`/
`ai_pilot_wheel` lines since 2026-11-18 — before either of those merged. If you have time on the
same flight: repeat a couple of commands from those two cards (break left/right, CBTM align) and
note whether they now behave differently than the 2026-11-19 attempt. One flight can plausibly
clear all three `#needs-flight` entries at once; say which commands you tried from those cards if
you do.

## Bring back

- Did "you have controls" confirm within ~2 s, every time you tried it?
- Did a command actually fly after taking controls?
- Did "I have controls" visibly give the stick back, and did it speak?
- Did `/flight_control/latest` and `/ai_pilot_wheel/latest` return real data pre-flight?
- Did anything from the mode-2 P3+P4 or mode-1 break cards behave differently now, if you tried it?
- **Anything that surprises you is worth more than anything on this list.**
