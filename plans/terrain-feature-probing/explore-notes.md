# Explore — what "ridge" and "valley" mean for a callout (user, 2026-10-01)

Held before choosing a replacement for the discrete-Laplacian detector, after
`world-model/research/2026-10-01-terrain-features-full-build-inspection.md` showed the first
full-theatre extraction is noise at landform scale. The user's own words are quoted where the
phrasing carries the reasoning; everything here overrides earlier assumptions in `plan.md`.

## What the words mean

> *"Valley is the concave shape between hills/mountains. It can have a flat bottom, but being
> between hills is the important part. Not kilometres wide flat bottom, while technically being a
> valley, it's meaningless in the Mi-24 flight profile scale. In that sense Bekaa not being valley
> is correct."*

**This reverses finding 4 of the inspection note.** The Bekaa floor classifying as `neither` was
read there as the detector's central failure; it is not. A kilometres-wide flat basin is not what
the pilot means by "valley" at this flight profile. The real defects are the ones the same note
records as 2 and 3 — fragmentation, zigzag polylines, and parasitic ridge/valley pairing — plus
the measure itself (see "threshold" below).

> *"Anything V or U shaped is a valley and inverse V or U ridge."*

Valley may or may not carry a river — drainage is a correlate, not the definition.

## The scale that matters

> *"In flying the Mi-24 I'm mostly interested in about 5 km radius around the helicopter. What
> landforms are there? How do they affect LOS? Can I see a target? Where do I need to be to attack
> it (LOS) or where to fly for cover (no LOS)."*

So the consumer is **LOS and ownship-relative position**, inside ~5 km. Not a gazetteer, not
theatre-scale geography.

> *"Minor changes in altitude and very shallow gradients are meaningless."*

> *"I can see 'slow rolling hills ahead' but I can see over them. A unit might hide behind some
> when I'm far, but closer the hills do not meaningfully obstruct the view. So, meaningful are
> formations that are sharp and/or high -> I or they can hide behind it."*

**A form earns the label by being maskable-behind: sharp and/or high.** Worked during the
conversation, ownship at 200 m AGL against a vehicle on the ground, the height a form must rise
above local ground to break LOS is **range-independent** — it depends only on where it sits along
the sightline: 150 m at a quarter of the way, 100 m half way, 50 m at three quarters, 20 m close to
the target. The pilot's own "far hills hide them, close ones don't" is look-down angle, not a
property of the hill.

Practical threshold: **~50–150 m of rise over a short horizontal run**, scale-free. The current
detector classifies on 20 m of curvature between adjacent 500 m cells — an order of magnitude below
anything that masks, which is why it labels wiggles. **The measure is wrong, not just the number:
per-cell concavity has no notion of relief amplitude, steepness, or connectivity.**

## Flight profiles (user's own numbers)

| situation | AGL |
|---|---|
| hiding in valleys | 100–200 m |
| crossing a ridge | 50–100 m |
| cruising in a valley | 200–300 m |
| cruising above it all | 200–500 m above the ridges |

## Names

> *"Names only matter where a map (aviation VFR chart) actually has a name for it. Names matter
> more in navigation, in target detection relative to ownship guidance matters more."*

So: **relative descriptors, not a gazetteer.** "Next valley", "the ridge between us" — no naming
layer needed for the contact-report consumer.

## The analogue — water flow, not rooms and doorways

The "rooms and doorways" analogue offered during the conversation was **rejected**, with the reason:

> *"Your rooms and doorways analogue would be correct in very high mountains, but that's not the
> usual case. A helicopter can fairly easily climb to altitude and fly over a mountain, unless it's
> many kilometres tall. Better analogue is water flow, if we think of miniature land forms. Water
> naturally flows on lower ground, along valleys. But given sufficient force it can rise over bumps
> and flow to next lower form of ground."*

Terrain is not an enclosure a helicopter is trapped inside; it is a surface with preferred low paths
that can always be left by climbing. That maps onto **drainage lines and divides** (flow
accumulation over the DEM, with the ridge being the divide between two drainages) — which has the
two properties the Laplacian lacks: channels are **continuous and connected**, and a divide is
defined **between** two specific valleys. Candidate direction for the architect, not a settled
decision.

## Scope — what Petrovich says, and when

> *"[Terrain belongs in the] contact report. At later stage, when hopefully we get Petrovich to fly
> the helicopter, I'd like to be able to instruct like 'fly along the valley', 'cross the ridge to
> the right and dip into the valley'."*

**Terrain qualifies a contact report. It is not Petrovich's own subject and he does not volunteer
cover advice.** This confirms `plan.md`'s existing item 6 ("Not this plan: navigation") and gives it
the user's own reason: navigation phrasing arrives when Petrovich flies, not before.

## "Next valley"

> *"'target 2 o'clock, next valley' = adjacent valley over one divide. 'turn left at next valley' =
> next 'intersection' along the route, but this would be Petrovich flying territory, so later."*

Confirms Stage 3's adjacency reading, and sharpens it: **adjacency is across exactly one divide** —
which a drainage/divide model defines naturally, and a scatter of curvature blobs does not.
Route-relative ordering ("next intersection along the route") is explicitly deferred with
navigation.
