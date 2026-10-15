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

## What this leaves open for `/explore`

- **§2:** does flying past *end* the run, or only silence it? And is "behind the cockpit mask" the
  right trigger, or is it really "behind me" — the mask is an occlusion model, not a bearing test,
  and the two differ at the edges.
- **§3:** confirm the fail-closed-LOS hypothesis against this sortie's trace before designing
  anything. If it is right, the fix may belong to the LOS join rather than to the guidance.
- **§1:** confirm that the repeated utterances really are identical strings in the log, rather than
  near-identical ones the ear merges.
