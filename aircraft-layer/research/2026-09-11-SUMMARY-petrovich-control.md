# Petrovich command & perception — what is established, 2026-09-11

**Read this first.** One day's investigation on the Windows/DCS box turned BL-6
from "we don't know if Petrovich can be influenced at all" into "every
mechanism is proven; the design needs rewriting". This is the consolidated
picture. Detail and evidence live in:

- `2026-09-11-command-injection-surface.md` — the effector: verbs, IDs, calibration
- `2026-09-11-petrovich-detection-readout.md` — the perception side and the wheel
- `mi24p-command-surface.md` — the full enumerated command/indicator reference
- `logs/2026-09-11/` — raw probe logs (the primary record; several conclusions
  were overturned by re-reading them)

DCS 2.9.29.27278. Every ID below is **positional** and must be re-derived after
a DCS update.

---

## 1. The two verbs — and they are not interchangeable

```lua
GetDevice(7):SetCommand(3061, value)                  -- 9K113 sight axes
GetDevice(30):performClickableAction(3015, 1) .. (…, 0)  -- AI wheel
GetDevice(0):get_argument_value(874)                  -- cockpit arguments
```

**`performClickableAction` works only on controls that have a clickable
element**; the sight axes have none, so they need `SetCommand`. The wheel
commands do have one, and `SetCommand` does nothing for them. Getting this
backwards cost two flights.

`GetDevice` / `performClickableAction` / `SetCommand` / `get_argument_value` are
all confirmed present and callable from the `Export.lua` state.

---

## 2. Pointing the sight — solved, and simpler than expected

```lua
GetDevice(7):SetCommand(3061, azimuth_deg / 60.0)            -- point
azimuth_deg = GetDevice(0):get_argument_value(874) * 136.36  -- read back
```

- **Positional and exactly linear** — ratio `0.440000` at five measured points,
  settling inside 0.25 s and holding flat. `look_at(bearing)` is **one write**,
  no control loop.
- Azimuth stops **±60°** ↔ gauge `±0.44`. Elevation gauge `-0.75 … +1.0`;
  **elevation limits in degrees are still unmeasured.**
- The optics really move — the pilot confirms the HUD crosshair moves in
  missile mode.
- **The AI axis (3060/3061) is positional; the player axis (3025/3026) is not**
  — it accumulates, and ±0.5 runs to ~99% deflection. Never assume one
  channel's behaviour from the other.
- **Authority is event-scoped.** Our command held 9/9 even while Petrovich was
  `SEARCHING`/`TRACKING`, and he resumes when we stop asserting — but he takes
  the sight back when the list is scrolled or a target selected.

Args 874/876 are therefore a readout of **where Petrovich is looking**, in
degrees, every frame — a perception input, not just control feedback.

---

## 3. Reading his mind — both channels work

**`list_indication(6)` — contacts, classified.** A five-row sliding window:

```
upper_upper_list_text / upper_list_text / middle_list_text (selected)
                      / lower_list_text / lower_lower_list_text
```

`upper_list_text` is registered under the element name **`"LeftCenter"`** (an ED
naming slip) — parsers must special-case it. Values are real unit types:
`T-90A`, `BTR-70`, `MTLB`, `ZIL heavy truck`, `Soldier AK`.

**A list longer than five rows is fully enumerable**: press `NEXT TGT`,
re-read, repeat. Traversal **wraps**, so terminate by **cycle detection** on a
repeated row-set. A missing `upper_*` row means the head of the list, a missing
`lower_*` row the tail — so list *position* is recoverable too. Confirmed live:
8 contacts walked in 9 presses.

**`list_indication(10)` — the wheel: his state and his live options.** The down
slot carries the engagement state machine:

```
OBSERV. OFF  ->  WAITING  ->  SEARCHING  ->  TRACKING
                                   (centre becomes FIRE once tracking)
```

**Parser warning that cost a whole flight:** Lua's `gmatch("[^\n]*")` yields an
**empty match between every line**. A parser that clears its pending key on a
non-matching line will drop every value. Use `"[^\n]+"`.

---

## 4. Driving the wheel

```lua
GetDevice(30):performClickableAction(<cmd>, 1)   -- press
GetDevice(30):performClickableAction(<cmd>, 0)   -- release
```

| | id |
|---|---|
| `ShowMenu` (toggle) | 3001 |
| `Right` / `Left` / `Up` / `Down` | 3002 / 3003 / 3004 / 3005 |
| **centre** (`Select_or_fireEXT`, "AI Wheel - Center") | **3015** |

- **Near slot = short press; far slot = long press** (`long_press_time = 0.5`).
- **A press executes that slot outright** — no cursor-then-commit.
- The centre slot holds **two** options split by a short dash divider
  (`SRCH BRST | SRCH FWD`): **short = `SRCH BRST`, long = `SRCH FWD`**.
- The wheel is **stateful and multi-page** (search / target / CM). Select
  presses **by label, never by position**, and identify the page by a stable
  feature — the centre label changes to `FIRE` while still on the search page.

Petrovich's full labelled vocabulary (from `Mi_24P_op` / `Mi_24P_pilot`, *not*
the `Mi_24P_AI_Menu` profile — searching only the latter hid all of this for
several iterations):

| id | label |
|---|---|
| 3015 | AI Wheel - Center |
| 3020 | **Designate custom AI attack point** |
| 3017 | **Turn to sight heading** (commands the *pilot* to turn) |
| 3018 | Evasion turn (180°) |
| 3008 | Prepare Weapons Systems |
| 3016 | ATGM launch align |
| 3021 | Fix Sight Gyro |
| 3014 | Request Aircraft Control |
| 3019 | Cycle Missile Type |

---

## 5. Operational semantics (pilot-supplied)

- **`MARK TGT`** numbers targets 1, 2, 3… for multi-select. The marker is not in
  the row text, which is why probing it by row/azimuth saw nothing.
- **`SELECT TGT`** → `TRACKING`, list closes, centre becomes `FIRE`. Only a new
  scan command leaves tracking. Firing needs the *helicopter* boresight on the
  target within a few degrees.
- **Nothing happens automatically on target destruction** — a new search must be
  commanded.
- **Never toggle `OBSERV.` casually**: every `ON` costs the **~10 s gyro
  alignment**. And **Petrovich turns it off himself under hard manoeuvring** to
  protect the gyros — so observation is **state to observe, never state we own**.
- **DCS race:** after `SRCH PILOT LOS` populates the list, `CLOSE LIST` reopens
  almost immediately while he is still scanning.

---

## 6. The gap that still blocks a *directed* scan

| search | directable from code? |
|---|---|
| `SRCH PILOT LOS` | **No** — takes the pilot's LOS from a mid-screen crosshair, i.e. wherever the *human* is looking (TrackIR) |
| `SRCH 9K113 LOS` | Would be exactly right — but **appears broken**: pressing down, short or long, only toggles `OBSERV.` (pilot; weak contrary probe evidence) |
| `SRCH FWD` / `SRCH BRST` | Triggerable, **not aimable** |

So we can aim his optics precisely and read everything he sees, but we cannot
yet tell him **to search a bearing we choose**.

**Both routes were tested, and both are closed.**

1. **Aiming the sight does not drive detection.** Five flights. The sight goes
   exactly where commanded, with or without Petrovich searching, and nothing
   looks through it on our behalf. We move the glass; no one looks.
2. **`DesignateAttackPoint` does not aim him.** Tested alongside the three
   commands bound to nothing (`Deprecated2` 3007, `SelectTarget` 3009,
   `UnselectTarget` 3010). None left the sight near our aim; none produced
   detections. They are not no-ops — 3020 *stops* a search, 3009 starts one and
   drives the sight to both limits, 3010 turns observation off — they simply do
   not mean "look here".

**A third route was identified and deliberately rejected:** the player's view is
readable and writable (`LoGetCameraPosition` / `LoSetCameraPosition`), so
`SRCH PILOT LOS` could be aimed by moving the pilot's head from code. Rejected
on design grounds — puppeting the human's eyes to manufacture Petrovich's
perception is the opposite of what this project is for. See the detection note.

**So there is currently no way to make Petrovich search a bearing we choose.**
What we *can* do is read everything he perceives, know his state, aim his optics,
and trigger his own searches (`SRCH FWD`, `SRCH BRST`) — just not direct them.

---

## 7. What this means for BL-6

`plans/bl6-commands-inspect-adapt/plan.md` was written on two premises that are
now **false**:

- *"Petrovich has no scan command"* — he has several, plus attack-point
  designation and a sight-heading turn.
- *"There is no outcome signal, so success must be inferred from belief state"* —
  his state, his gaze in degrees, and his classified contact list are all
  directly readable.

The plan's "virtual scan" framing solves a problem that no longer exists. The
body-layer half (`PendingIntent`/`TaskStore`) remains sound, but **the milestone
needs an Architect revision before implementation**, and the revision should
also carry two design constraints this investigation surfaced:

- **Observation and engagement are different acts.** `SELECT TGT` commits
  Petrovich to tracking and, weapons free, to firing. A `list_contacts()` that
  merely reads must not select or mark.
- **Enumerating the list is not read-only** — it moves his selection, and
  scrolling hands the sight back to him.

## 8. Method notes worth keeping

Four flights were wasted on probe faults, not DCS behaviour. The recurring
lesson: **never conclude "no effect" from a test that had no room to produce
one**, and **verify an effect by the thing that actually changes** — a slot
label that never changes (`NEXT TGT`, `SELECT TGT`) cannot report its own
success. Also: simulating Lua string iteration in Python validated a parser that
never worked; the raw dump found what the simulation hid.
