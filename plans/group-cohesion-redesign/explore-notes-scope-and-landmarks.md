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
- ~~When a landmark earns a mention in a callout, and how its name is chosen when several are
  nearby.~~ **Answered below (2026-10-01, fourth round).**

## 5. When a landmark earns a mention (user, 2026-10-01)

> *"when it is promenent and close enough to be a reference. Villages are great. Large cities are
> not because they themselves span kilometers. Road where there are only few is good, road where
> there are many is noise. River, valley, mountain, ridge, lake, sea - all good, though if there's
> many nearby it can be confusing which one, but using a combination might work well -> 'in valley,
> south of village'."*

Two independent tests, both of which a landmark candidate must pass:

- **Extent** — the feature's own size must be small relative to the precision the reference is
  meant to convey. A village localizes; a city spanning kilometres does not, because "near
  Damascus" is a worse answer than the range/bearing already given.
- **Local uniqueness** — one road among few nearby is a reference; one road among many is noise.
  Same for rivers, valleys, mountains, ridges, lakes, seas: all good kinds, all useless in a
  cluttered area where several of the same kind sit close together.

**The extent test is the same principle `belief.groups`' cohesion rule already uses** — grouping
compares spacing to unit size, landmark selection compares usefulness to feature size, and neither
works as an absolute-metre threshold. One idea, two applications; worth building once rather than
inventing a second ad-hoc rule.

**Combination resolves ambiguity, and should be designed in from the start, not bolted on as a
fallback**: *"in valley, south of village"* chains two individually-weak references into one
unambiguous one, and reads like how a crew member actually talks rather than a single engineered
"perfect" landmark.

### What this means against the actual world-model data (checked, not assumed)

- `query.describe.SettlementInfo.subtype` is already `"city"`/`"town"`/`"village"`/`"built_up"`
  (`world-model/src/query/describe.py`), and `NamedPlaceInfo.subtype` already carries a `place=*`
  value (`city`/`town`/`village`/...) or `None` for a DCS-native `towns.lua` entry. **The extent
  test is answerable today** — village/town vs. city is already a stored distinction, not a gap
  that needs a guessed area threshold. This resolves the open question the dispatch raised about
  whether anything distinguishes a village from a city: something does, already.
- **The local-uniqueness test has no existing query support.** `describe_position` returns the
  *nearest* feature of each kind (`RoadInfo`, `WaterInfo`, `NamedPlaceInfo`, ...), singular — there
  is no "how many of this kind within radius R" query. Building the uniqueness test needs a new
  world-model query (count or list candidates of a kind within a radius), not just a disclosure
  policy on top of what exists. This is a real, if small, addition to `world-model/src/query/`, not
  only a body-layer decision.
- Kind coverage against what's named: village/town/city → `settlement`/`named_place` (26,182 /
  23,044 rows respectively); road → `road`; river/lake/sea → `water`/`coastline`; valley/ridge →
  the terrain-landform work (`feature/terrain-landform-features`), whose adjacency/bearing/callout
  stages (3-5) are **not yet built**. Mountain has no obviously corresponding kind yet in the
  reviewed schema — flagged, not resolved here.

### Dependency this creates, and what not to block on

Valley and ridge as landmark kinds depend on `feature/terrain-landform-features` Stages 3-5, unbuilt
as of this note. **Landmark anchoring should not be designed to block on them** — village/road/water
coverage is available today and is most of the value (villages are explicitly called out as the best
case). Valley/ridge/mountain join later as the terrain work lands, additively.
