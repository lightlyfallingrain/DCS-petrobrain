# Attack-run sortie feedback, 2026-10-15

First flight of `BL-14`'s attack-run guidance (merged `6301ec7`). Captured verbatim per the standing
rule before any diagnosis — the user's own words are the specification.

**Logs:** `body-layer/logs/dcs-{speech,belief-truth,detection-trace}-20261015-164451.jsonl`, copied
to the session scratchpad. The attack run begins at `now_sim ≈ 580` — the speech log shows
`"target, unit, twelve o'clock."` → token `engage`, acted, at `now_sim=580.012`, preceded by
`"follow unit, twelve o'clock."` → `follow` at `563.143`.

**Scenario, in the user's words:** *"Target single armor on flat desert."* — so a single vehicle, no
group, no terrain masking to speak of. That matters for observation 3 below: flat desert is close to
the best case for line of sight, which makes a frequent *"obstructed"* qualifier surprising rather
than marginal.

---

## §1 — The guidance callout repeats when nothing has changed

> *"guidance callout keeps repeating even when nothing changed (same callout repeats, maybe
> something changed underneath, but not in what I hear)"*

**This contradicts a direction already given and already built.** `docs/acceptance/2026-10-14-attack-run-guidance-direction.md`
§10 says cadence is *"when there is change"*. The parenthesis is the precise observation and the one
that locates the defect: **something underneath probably did change, but nothing the pilot can
hear.** So the change-detection is comparing a richer internal state than the utterance it produces
— two different o'clock values, or two different qualitative words, that render to the same spoken
string.

The fix shape that follows: **compare what would be said, not what is believed.** Suppressing on
equality of the rendered utterance is the only comparison that matches what the pilot experiences.

## §2 — Guidance keeps running after the pilot flies past or turns away

> *"guidance keeps running when I fly past or turn away -> if obstructed by cockpit mask, no call
> out."*

Two statements. The first is the symptom: an attack run that does not end when the geometry says the
run is over. The second is the user's own proposed rule: **if the target is behind the cockpit mask,
say nothing.**

Note this is a *guidance* suppression rule, not a target-loss rule — `[[BL-14]]`'s existing
behaviour on losing sight is to keep guiding from the remembered or projected position (direction
§7, §19). The user is distinguishing *"I cannot see it because something is in the way"* (keep
guiding, qualified) from *"it is behind me"* (stop talking).

**Open and not to be assumed:** whether the run should also *end* when he turns away, or merely go
silent until he comes round again. §2's words say only "no call out".

## §3 — *"obstructed"* fires with the unit in plain sight

> *"even when unit in plain sight, often I get '..., obstructed'"*

**On flat desert, against a single vehicle.** The `", obstructed"` qualifier comes from direction
§19 and is meant for a target the crewman cannot currently see.

**A likely mechanism is already on record from today's earlier investigation, and it is worth
checking first:** the same morning's sortie reported `live LOS coverage: 420/5106 gate-4 evaluations
had no live verdict this sortie`. `BL-11` Stage 4 made terrain LOS **fail-closed** — no live verdict
is treated as masked. If the attack-run guidance reads the same LOS verdict, then *"no answer yet"*
renders as *"obstructed"*, which on flat desert would be wrong far more often than terrain would
explain. **This is a hypothesis with evidence behind it, not a conclusion** — the join-miss rate for
the *attack target specifically* has to be measured in this sortie's own trace.

## §4 — New: announce reaching the 12 o'clock sector

> *"when change from 1 or 11 to 12 o'clock -> add call out 12 o'clock, so that I don't over shoot
> the turn. After that the left/right callouts."*

**This is a new requirement, not a defect**, and the reason given is the design input: the pilot is
*turning* when he hears the last o'clock call, and without a marker for arriving at 12 he overshoots
through it.

The existing register (direction §1, §6) switches from o'clock positions to qualitative
*"come left"/"a bit right"* once the target is inside the 12 o'clock sector — but **the switch
itself is currently silent**, which is exactly the gap. The sector boundary is a real event for the
pilot and it is not spoken.

So: **on the 1 → 12 or 11 → 12 transition, say "twelve o'clock", then continue with the left/right
register.** Ordering matters — the announcement precedes the qualitative guidance rather than
replacing it.

---

## §5 — §3 diagnosed: the target was out of *range*, not obstructed

**Settled from the 2026-10-15T17:55 sortie's own logs**, the first flown with ownship attitude on
every speech row. The attack target was rejected at the **`range_or_size`** gate, never at
`cockpit_mask`:

```
 98.7 … 113.8   range_or_size   2607 m -> 2357 m     "..., obstructed."
114.8 onward    admitted        2322 m -> closing    "Lined up."
```

The crossover sits at ~2,330 m, which is exactly `7 m / 0.003` — the naked-eye **presence**
threshold (`LOWRES_ANGULAR_RADIUS_RAD`) for a 7-metre vehicle. Attitude was nose-down throughout
(pitch −6.8° to −11.2°), which *clears* the cockpit mask rather than tripping it, so the mask
hypothesis is dead and the earlier bank and pitch theories with it.

**The defect is the word, not the perception.** Guidance renders every non-observation as
`", obstructed"` regardless of cause, collapsing three different situations into one:

| cause | truthful meaning | observed in |
|---|---|---|
| cockpit mask | behind the airframe, cannot see | 45 rear calls, 16:44 sortie |
| terrain LOS | something is in the way | by construction |
| **range/size** | **too far to make out** | this block, and the user's *"plain sight"* complaint |

The user could see it plainly on screen; Petrovich's naked-eye model genuinely cannot resolve a 7 m
vehicle past ~2.3 km. Both are correct, and the sentence was wrong.

## §6 — What to say, and which optic to reach for

> *"first of all, use binoculars. If still too far, use the "...last I saw" or similar that's already
> used in the describe."*

So the answer is **not** a new phrase for "too far". It is an **escalation ladder**: reach for a
better instrument first, and only fall back to remembered-sighting language when even that cannot
resolve the target. Binoculars (×2.42 presence) take the same 7 m vehicle from ~2.3 km to ~5.6 km,
which covers the whole of this sortie's problem block.

**Reuse the existing remembered-sighting phrasing from `describe`** rather than minting a new form —
the user named it explicitly, and it already carries the right epistemic claim: this is what I saw,
not what I see.

> *"Not automatically. If OBSERV is ON already, then yes. If OFF, then not. Also, distance dependent,
> if target within naked eye range, then not."*

**The 9K113 is never reached for autonomously by designating a target.** The rule is a cheapest-
sufficient-optic ladder with a hard gate on the sight:

1. **Naked eye** if the target is within naked-eye range — do not escalate at all.
2. **Binoculars** when the naked eye cannot resolve it.
3. **9K113** only if **OBSERV is already ON**. If OBSERV is OFF, designating a target must not turn
   it on — that stays the pilot's command (§6 of the direction document).
4. Otherwise, speak from belief using the `describe` remembered-sighting phrasing.

Note how this interacts with what already shipped: `BL-B64` made the sight a selectable optic and
OBSERV a voice command, so step 3 costs almost nothing — but the gate matters, because an attack run
that silently switched Petrovich to a 3°-field sight would change what he can see of everything else
without the pilot asking for it.

---

## §7 — The ladder runs both ways: least capable optic that can see the target

> *"for guidance using other than ATGM - use the least capable optic that can see the target. Switch
> from more capable to less capable as range decreases."*
>
> *"In ATGM case, 9K113 is a must, but can switch from narrow to wide when wide is enough for precise
> guidance."*

**This generalises §6 and corrects its shape.** §6 read as a one-way escalation — reach for something
better when the naked eye cannot resolve the target. It is really a **standing rule with a minimum,
evaluated continuously in both directions**: at every moment, use the *least* capable optic that can
still see the target.

| case | floor | rule |
|---|---|---|
| guidance, non-ATGM | naked eye | least capable optic that resolves the target; **de-escalate as range closes** |
| ATGM run | **9K113 (mandatory)** | narrow while narrow is needed; **widen to wide as soon as wide suffices** |

**Why least-capable rather than best-available, stated because the code will otherwise drift the
other way:** a more capable optic is a *narrower* one. The 9K113 narrow is 6° of field against the
naked eye's 180°. Reaching for magnification he does not need costs Petrovich everything else he
would have noticed — the whole point of the optic model since binoculars stopped being the default
(`optics.py`'s own module docstring). **Capability and awareness trade against each other, so the
cheapest sufficient instrument is the correct one, not a compromise.**

The ATGM floor is the exception that proves it: during a missile run the sight is mandatory
regardless of range, because the guidance channel *is* the sight (`BL-14` explore: *"ATGM guidance
is with 9K113 only, there is no naked eye channel"*). Even there the same instinct applies one level
down — widen from narrow to wide the moment wide is precise enough.

**The engineering risk this creates, which the plan must address rather than discover:** a threshold
crossed by a closing range will be crossed repeatedly if range oscillates, and every switch costs the
1 s hands-busy interval during which Petrovich sees nothing. **Hysteresis is not a refinement here,
it is load-bearing** — the same conclusion the 9K113's slew deadband reached for the same reason.
A ladder that thrashes at the boundary would be worse than one that never de-escalates at all.

---

## §8 — `", obstructed"` means DCS line of sight, and nothing else

> *"'...obstructed' for DCS LOS, be it terrain or buildings."*

**This answers the open question §5 raised** — whether the qualifier has any caller left once the
other two causes are routed elsewhere. It does, and exactly one:

| cause | what Petrovich does |
|---|---|
| **DCS line of sight** — terrain or buildings | **say `", obstructed"`** — this is the word's only remaining caller |
| cockpit mask — behind the airframe | **silence** (§2) |
| range/size — too far to resolve | **change optic** (§6, §7); if even that is not enough, the remembered-sighting phrasing `describe` already uses |

So the word recovers the meaning it was given in the 2026-10-14 direction (§19) — *something is in
the way* — rather than standing in for every reason Petrovich is not currently looking at the
target. All three causes are now distinguishable to the pilot, and each says something he can act
on: nothing to do about terrain, turn to fix the mask, wait or close for range.

**Note which LOS this is.** The live DCS verdict (`candidate.live_los_clear`, joined from the
aircraft-layer Hook per `X-B29`), **not** world-model's offline primitive, which is testing-only by
standing user direction of 2026-10-05. `BL-11` Stage 4 made that gate fail-closed, so **a missing
live verdict currently reads as masked** — and would therefore speak `", obstructed"` under this
rule. That interaction deserves checking: the 2026-10-15T16:44 sortie reported
`420/5106 gate-4 evaluations had no live verdict`, roughly 8%, which is the rate at which this
qualifier could fire for "no answer yet" rather than for real terrain.

---

## §9 — The attack target has first claim on DCS line of sight

> *"during an attack run the current target is *the* thing to LOS and must take priority over any
> other DCS LOS checks."*

**This is the answer to §8's open interaction, and it comes from the other end than expected.** §8
noted that the live LOS gate is fail-closed since `BL-11` Stage 4 — a *missing* verdict reads as
masked and would speak `", obstructed"` for *"no answer yet"*. The 16:44 sortie put that rate near
8% across all gate-4 evaluations.

The fix is not to soften the fail-closed rule, which exists for good reason. It is to **guarantee
the one contact that matters always has a fresh verdict**: during an attack run the target is not
one candidate among many competing for a budgeted LOS batch — it is the thing the batch exists for.

**Where this lands is a cross-subproject question the plan must answer**, because the raycast is not
ours: `X-B29` moved it into the DCS-side Lua Hook, and body-layer consumes
`GET /line_of_sight/latest` joined by `unit_name` under `LOS_MAX_AGE_S = 3.0`. So priority can be
expressed in at least two places —

- **aircraft-layer**, ordering or reserving a slot in the Hook's own batch so the target is always
  raycast; or
- **body-layer**, requesting the target explicitly rather than taking whatever the latest snapshot
  happens to contain.

— and they have different costs and different failure modes. The first needs the export side to know
which contact is the attack target, which is a new coupling between Petrovich's intent and the Hook.
The second cannot conjure a verdict that was never computed.

**Three things worth settling with it:**

1. **What "priority" means when the verdict is simply stale** rather than absent — `LOS_MAX_AGE_S`
   is 3.0 s, three poll cycles at the LOS feed's own 1 Hz. During a closing attack run a 3-second-old
   terrain verdict may already be wrong.
2. **Whether the target should also be raycast more often**, not merely first. This is the same
   freshness argument `BL-B63`'s selective fast lane makes for telemetry and the current target —
   and if so, the two belong together rather than being solved twice.
3. **What Petrovich says if the verdict is genuinely unavailable** even with priority. Silence and
   `", obstructed"` are both wrong: one hides a real obstruction, the other invents one. This is the
   residue of the fail-closed rule and it needs an answer, even if the answer is "cannot happen once
   priority is in place" — in which case say what enforces that.

---

## §10 — The too-far phrasing is announced once, not appended every line

**Supersedes the plan's Decision 3** (reuse `_spoken_age_phrase` on every qualifying line), which
I accepted on the user's behalf under *"proceed independently"* and flagged as risky in the same
breath — *"Come left, under a minute old."* every tick reads as clutter in the one register meant
to be terse. The user's own replacement:

> *"let's modify like this:*
> - *initial: `"<attack_run_text> <what> <where> last seen <time> ago"` where `<time>` is rounded to
>   something sensible like "moment" "minute" "couple of minutes"*
> - *guidance after initial -> guidance only, no appended text*
> - *reacquired -> `"eyes on, <normal guidance text>"`*
> - *after that `"<normal guidance text>"`*"

**It is a four-state register, and the announcements are on the transitions:**

| state | spoken |
|---|---|
| **losing sight** (entering unresolved) | `"<guidance> <what> <where> last seen <time> ago"` — the full claim, once |
| **while unresolved** | guidance only, nothing appended |
| **regaining sight** (reacquired) | `"eyes on, <guidance>"` — once |
| **while seen** | guidance only |

**This is the same shape §4 already establishes**, and the consistency is the point: the sector
crossing is announced on the transition and then the register continues plainly. Losing and
regaining sight are transitions of the same kind. A pilot needs to be *told something changed*; he
does not need it restated every three seconds, which is exactly what §1 was about.

**The time words are coarse by intent** — *"moment"*, *"minute"*, *"couple of minutes"*. Petrovich
is not reading a clock; he is saying how stale his last look was. Whatever `_spoken_age_phrase`
currently renders, the buckets must land on words like these rather than on a precise-sounding
phrase, which is the same instinct that made the guidance register qualitative rather than numeric
(2026-10-14 direction §9).

**One thing to get right, because it is the fourth instance of this class in two features:** the
"have I already announced the loss?" and "have I already said eyes on?" flags are **co-moving state
on `AttackRunState`**, written on transitions and reset on a re-point. They belong in the plan's
Co-moving Fields table — a new target's first callout must never open with *"eyes on"* or with a
last-seen clause inherited from the previous target.

---

## What this leaves open for `/explore`

- **§2:** does flying past *end* the run, or only silence it? And is "behind the cockpit mask" the
  right trigger, or is it really "behind me" — the mask is an occlusion model, not a bearing test,
  and the two differ at the edges.
- **§3:** confirm the fail-closed-LOS hypothesis against this sortie's trace before designing
  anything. If it is right, the fix may belong to the LOS join rather than to the guidance.
- **§1:** confirm that the repeated utterances really are identical strings in the log, rather than
  near-identical ones the ear merges.
