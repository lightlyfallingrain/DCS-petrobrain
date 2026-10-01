# Explore — clock handles, landmark anchoring, and the threat scope that actually matters (user, 2026-10-01)

Third round of answers on the group-cohesion work. Settles the clock-handle question this session
raised, adds a capability the user wants *now* rather than later, and — most consequentially —
narrows which air-defence systems this project should be designed around at all.

## 1. Clock handles are fine, because they are ownship-relative by design

The worry raised here was that "the 2 o'clock group" stops being a usable handle once the aircraft
turns. The user's answer:

> *"Always use relative to ownship, so that is fine and movement from sector to sector is expected.
> Alternative would be enabling group naming, but that's another story and we'll see about that at
> a later stage."*

So a clock bearing is **a description recomputed at speak time, never an identifier**. A group
moving from 2 o'clock to 9 o'clock as the pilot turns is correct behaviour, not drift to be
corrected. Group *naming* — a stable handle a group keeps across utterances — is deferred, not
rejected.

## 2. Landmark anchoring, wanted now

> *"Could add nearby information already now, 'group 10 o'clock, 2 km, south of <village>' then
> later 'group south of <village> has tanks and armor, 9 o'clock, 1.5 km'."*

Two distinct uses, and the second is the interesting one:

- **As extra position detail** on a callout: *"group 10 o'clock, 2 km, south of \<village\>"*.
- **As the thing that makes a later reference recognisable** — *"group south of \<village\> has
  tanks and armor"* — which is a **stable handle in everything but name**, and partly answers the
  clock-handle problem without building group naming. A village does not move when the pilot turns.

This is buildable now: `world-model` already holds 23 044 `named_place` rows for Syria, and
body-layer already imports world-model's query package in-process (the one deliberate cross-
subproject import). `belief/enrichment.py` already reaches `describe_position`. The missing piece is
disclosure policy — when a landmark earns a mention — not data or plumbing.

Note what this shares with the terrain work: *"trucks moving north, towards \<village\>"* from the
delta-taxonomy notes is the same mechanism. Landmark anchoring now has two independent consumers
asking for it, which is the strongest argument for building it once, properly.

## 3. The threat scope: Cold War SHORAD, not modern long-range SAM

The most consequential answer of the three, because it redirects effort rather than adding it.

> *"I'll likely fly mostly cold-war era missions, since the Hind is a Soviet cold war era aircraft.
> 70's 80's, with something more modern every now and then. The Hind also is not the tool to take
> out anything like S-300 or Patriot. Anti-radiation missiles, fired from jets at altitude and safe
> distance are. For helicopters SHORAD is the important factor, though longer range SAM encounters
> are possible."*

So:

- **SHORAD is the design centre** — Shilka, ZU-23, SA-8/Osa, SA-9, SA-13/Strela-10, SA-15/Tor,
  SA-6/Kub, and the SA-2/SA-3 fixed sites of the era.
- **Long-range modern SAM (S-300, Patriot) is an encounter, not a target.** Petrovich should still
  perceive and report one — the pilot needs to know it is there to stay away from it — but no
  effort goes into modelling it well, and the investigator's own recommendation to ignore the
  S-300 evidence gap is accepted on exactly these grounds.
- Era is roughly **1970s-80s**, with occasional modern missions.

**This retires the research hole** the SAM-geometry note flagged as most serious. The missing
real-world spacing figures were for Buk, mobile S-300, Tunguska and Pantsir — none of which is this
aircraft's problem. Post-2022 Ukraine OSINT geolocation, offered as the way to close that gap, is
**explicitly dropped**: *"Ignore the OSINT and S-300."*

## 4. Settled, from the same message and the one before it

- **Installation cohesion cap: a single ~500 m value.** Approved. Covers typical DCS-authored site
  dispersal (community guides: 200-800 m general, 200-600 m for an SA-6-type battery) and the
  documented fixed-site doctrine (S-75 site diameter 160-230 m) with margin. Revisit after a sortie
  with a realistically placed site, not before.
- **Single-vehicle systems are excluded from the installation rule entirely.** An Osa, Tor,
  Tunguska or Shilka is its own radar and launcher; two of them a kilometre apart are two threats.
  Whether they are battery-mates is the ordinary size-relative test's job, not a flat cap's.
- The 236-838 m measurement from the 2026-10-01 sortie is discredited and must not be reused.

## Open

- Whether the ~500 m cap wants an era or family qualifier once Cold War SHORAD is the design
  centre — the fixed S-75/S-125 sites it is most defensible for are *also* the ones squarely in
  scope, which argues it is about right, but this has not been checked against an actual Cold War
  mission's unit placement.
- When a landmark earns a mention in a callout, and how its name is chosen when several are nearby.
  That is disclosure policy and belongs in the plan's own taxonomy work, not here.
