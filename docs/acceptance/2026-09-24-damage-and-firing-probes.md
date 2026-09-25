# Damage and firing probes

Not a sortie card. **Three reconnaissance steps, cheapest first**, answering two questions that
gate how Petrovich can ever perceive being shot at, and whether he can answer *"is it dead yet?"*.

Each step can make the next unnecessary. Do them in order.

**Branch: `main`** — the probes are already merged.

```sh
git checkout main && git pull
```

| | question |
|---|---|
| **Damage** | can he tell a damaged unit from a healthy one, and does "smoking" have a readable threshold? |
| **Firing** | does a ground AAA unit firing raise *anything* our code can see? |

Background and the full evidence trail:
`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`.

---

## Why this matters

You said it in the explore conversation: *"any type of air defence is a threat. Priority danger
only if it engages us. Most likely case is AAA and there Petrovich can see the tracers visually
with naked eyesight."*

That only works if *something* tells the code a gun is firing. The documentation search found a
hard fact and a hard gap:

- **Confirmed, from primary text:** `S_EVENT_SHOT` explicitly excludes machine-gun and autocannon
  fire — *"those are handled by shooting_start"*. A shot-event design would have missed AAA
  entirely.
- **Unconfirmed, and load-bearing:** whether ground AAA (a ZU-23, a Shilka) raises
  `S_EVENT_SHOOTING_START` at all. Every worked example found was an aircraft cannon.

If the answer is no, the naked-eye/LOS channel is not a backstop — it is the only route, and the
tracer idea is built on nothing.

---

## Not testable here, and why

- **Nothing about watch-reporting.** That work is in progress on `feature/watch-reporting` and is
  not on this card.
- **The body-layer pipeline is off during Step 2.** `Export.probe-weapons.lua` replaces the
  production `Export.lua`, so the collector, the overlay and Petrovich's whole belief loop are dead
  for that sortie. Put the real `Export.lua` back afterwards. Step 3's probe is a Hook script and
  does *not* conflict — it can ride along with a normal session.
- **"Smoking" has no API.** There is no `isSmoking` flag anywhere. Step 3 tests whether the life
  *fraction* correlates with the smoke you can see, which is a different and weaker claim.

---

## Step 1 — read a debrief log · costs nothing

**Do:** find any already-flown mission where AAA fired. Open
`Saved Games\DCS\Logs\debrief.log`, search for `events =`, and read the `type` strings in that
table.

**Expect:** entries shaped like `type = "shooting start"` or similar, naming the firing unit. The
one local debrief log in the repo is the Free Flight quick-start — nothing fired, so it shows only
`mission start`, `group change option`, `under control`. That is what "no combat" looks like.

**Record:** does any shooting-typed event appear for a *ground* gun? Copy the entry verbatim.

> If this shows a shooting event for ground AAA, the engine raises it and Step 3 only has to
> confirm our handler receives it. If no combat debrief exists, skip to Step 2.

**Bring back the file itself** — drop it in `win-mac-sync/from-windows/dcs-logs/` and I will read
it.

---

## Step 2 — are tracers just objects? · one sortie, pipeline off

The cheapest possible answer to the whole firing question. If `LoGetWorldObjects()` already returns
in-flight weapon objects, **no event handler is needed at all** — a tracer becomes an ordinary
object in the feed the naked-eye channel already gates on field of view, angular size and terrain
line of sight.

Tacview renders individual AAA rounds, which says the engine tracks them. It does not say this Lua
surface exposes them. Hence the look.

**Do:**

1. Back up the production `Export.lua`.
2. Copy `aircraft-layer/dcs-export/Export.probe-weapons.lua` over
   `Saved Games\DCS\Scripts\Export.lua`.
3. Fly where a ground AAA unit (ZU-23-2 or Shilka, set to engage) actually fires — at you or at a
   decoy — and **hold there while it shoots**.
4. Restore the real `Export.lua`.

**Expect:** `Saved Games\DCS\Logs\aircraft_layer_probe_weapons.log`, one line a second:

```
[1281.40] count=214
[1282.40] count=231 NEW: weapons.shells.ZU_23_HE, ...
```

A count spike plus new names while it fires means weapon objects are in the feed. A flat count and
no new names while tracers are visibly in the air means they are not — **a real and useful
negative**, closing the cheap route.

**Record:** does the count move while it fires? What names appear, verbatim? Those names are what a
filter would key on.

---

## Step 3 — the prize · life fraction and firing events, one sortie

**This is the measurement worth more than the rest.** It answers both remaining questions at once,
and one line of its output settles a third.

**Do:**

1. Copy `aircraft-layer/dcs-export/petrobrain-damage-events-probe-hook.lua` to
   `Saved Games\DCS\Scripts\Hooks\`. It needs the same `autoexec.cfg` opt-in everything else does
   (`net.allow_dostring_in = { "scripting" }` — already in place).
2. Fly with a ground AAA unit set to engage.
3. **Shoot a ground unit until it visibly starts smoking — do not kill it.** Note roughly when the
   smoke starts.
4. Then kill it, and keep flying a few seconds.
5. Remove the probe Hook afterwards.

**Expect**, in `Saved Games\DCS\Logs\dcs.log`, under `PetrobrainDamageProbe`:

```
register: ok=true result=registered
DAMAGED t=1281.4 units=214 name:type:life:life0:fraction -> Unit_7:ZU-23:1.800:3.000:0.600
EVENTS n=2 -> S_EVENT_SHOOTING_START|t=1281.4|init=AAA-1|weapon=-|target=-;...
```

The probe resolves event ids to names at runtime by reversing DCS's own `world.event` table, so the
log prints `S_EVENT_SHOOTING_START` rather than a bare number that could be misread.

**Read the `register:` line first.** It alone answers whether `world` is reachable from the
scripting state — a question never probed before, independent of whether any event ever arrives.
`ok=false` means the bridge does not expose event registration and the whole event route is dead.

**Record:**

- Did registration succeed?
- Does any event name the **AAA unit** as `init=` while it fires? Which event, and roughly how
  often — one per burst, or many per second?
- At the moment smoke visibly started, what was that unit's `fraction`? Try it on two different
  unit types if you can — the question is whether the threshold is *consistent*, not what it is
  once.
- After the kill: does the unit keep appearing at all, or vanish?

---

## Bring back

- **Step 1** — any shooting-typed debrief entry, verbatim; or "no combat debrief exists".
- **Step 2** — did object count move during firing, and what names appeared.
- **Step 3** — the `register:` line; whether any event named the firing AAA unit; the life fraction
  when smoke started, on as many unit types as you managed.
- The log files themselves into `win-mac-sync/from-windows/` beat any summary — `dcs.log`,
  `aircraft_layer_probe_weapons.log`, `debrief.log`.

**Anything that surprises you is worth more than anything on this list.** Several of this project's
most important corrections arrived that way rather than in answer to a question — the tracer idea
itself came from you, not from the code.
