# Relative-distance grouping — explore notes

Started 2026-10-31, from the post-merge analysis of BL-B104's scenario flights. At 1 s polls (the DCS
rate) the two-groups-on-one-bearing scenario folds: the far group is seen first, alone, at 4.6 km
(along-line-of-sight σ ≈ 720 m); the near group's first look at 2.4 km six seconds later falls
inside the association gate and merges. One contact, one callout. BL-B104 Stage 8 (motion-aware
growth) does not touch this: the fold comes from first-look range uncertainty, not from growth
while unseen. Six other realistic approaches kept two contacts, because both groups were first seen
in the same look.

The main loop showed the gate's shape: 3σ ellipse from the summed covariances, ≈ ±820 m across and
≈ ±2.4 km along the line of sight; "same bearing" in practice means within ~8–15°.

## User, verbatim (2026-10-31)

> *"- Test flight updates: go for 1s*
> *- A stationary group under the nose is marked "lost" after 2 min unseen -> mission memory*
> *- callout: yes, that is a good idea*
>
> *- the accross ~241 m and along 720 m*
>   *- While this is based on the angular error and in that sense is correct, this would only really
>     hold true if angular position is the only way to judge distance.*
>   *- I reality an observer can fairly easily tell relative distance, though not exact numbers*
>     *- say that we have three units along more or less the same bearing. 2 km 2.5 km and 5 km*
>       *- at very low altitude (=low angle) telling apart 2 and 2.5 km becomes difficult by
>         elevation angle, but they can still be told apart by angular unit size. One is further
>         than the other.*
>       *- 2 or 2.5 km and 5 are easy to tell apart at any altitude by eihter the vertical angular
>         difference and/or the angular unit size*
>       *- also surrounding terrain features help judge the relative distances*
>   *-> the current along the line uncertainty and merge zone is too large. Groups should merge with
>     (near?) circular position uncertainty (map top-down view), since it's not a group when some
>     units are kilometers away, even if they fit the same FOV."*

## Reading (main loop, to confirm with the user)

- **Absolute vs relative distance are different judgements.** The absolute number ("4 kilometres")
  keeps today's error (±~700 m at 4 km, BL-B104 Q1). Telling which of two things is further, and
  whether a sighting is the thing seen before, is much more precise: angular size, depression
  difference and nearby terrain all give it.
- **Merge decisions use the relative judgement**, so the merge zone is near-circular in top-down
  map terms, not a long ellipse along the line of sight. Applies to both places groups are formed:
  within one look (`perception/clustering.py`: units in the same field of view kilometres apart are
  not one group) and across looks (`belief/association_over_time.py` gate).
- **Implication for the noise model**: if repeated looks at the same group each draw an independent
  ±700 m range error, a tight circular gate would split one group into several contacts. A real
  observer's repeat estimate of the same group is consistent with his earlier one (same size cue,
  same terrain reference) — so most of the along-line error should be per-object and stable, with
  only a small look-to-look part. To confirm.
- **Side items:** test flights at 1 s; a stationary group going "lost" under the nose should live
  on in mission memory; second-group callout wording (e.g. "second group, beyond") — separate
  backlog item.

## Confirmation (user, verbatim, 2026-10-31)

Asked: (1) absolute number keeps today's error, same/different-group uses relative judgement with a
near-circular merge zone, both within one look and across looks? (2) a repeat look gives a similar
range estimate (error mostly a stable per-group offset)? (3) how fine — proposed "different groups
at a distance ratio ≥ ~1.2", merge circle ≈ ±400 m at 2.4 km, ±700 m at 4.6 km.

> *"1 - yes*
> *2 - yes. Sighting reapeatedly at distance gives the same cues we already saw the previous time.
> Only way to make it more accurate is comparing to a map and we're not implementing that. Getting
> closer helps, as does a different angle to look from, triangulation by ownship movement.*
> *3 - I'm not sure about 2 and 2.5 km, they could legimately be of same group. And in other case
> not. Only actual flights will tell how it feels like."*

Reading:

- (1) confirmed as stated.
- (2) Range error on repeat looks is correlated: same cues, same estimate. It improves only by
  **closing** (error scales with distance), or by **a different viewing angle** — ownship has moved
  enough that the line of sight to the group has rotated, so the along-line errors of the two looks
  are no longer the same axis (triangulation). Comparing against a map is out of scope. So the
  look-to-look decorrelation should be driven by geometry change (range change, line-of-sight
  rotation), not by the count of looks.
- (3) No fixed rule from the user; 2 vs 2.5 km can be either. The relative-distance threshold and
  the merge-circle size are **tunables with a judgement default**, to be calibrated in flight
  (`#needs-flight`). The scenario tests must not hard-code a verdict for the ambiguous ~1.25 ratio
  case — only the clear ones (≈1.5 km+ apart at 2–5 km must stay two; one group must not split).

## Goal-check questions answered (user, verbatim, 2026-10-31)

Questions from `alignment.md` (goal check, CONCERNS): Q1 overlapping-in-view units at very low
altitude — still one blob (2026-09-18 "separability is angular") with relative distance deciding
only whether *separately seen* things are one group? Q2 a ~1 km column moving along the line of
sight — one group if neighbour gaps are small? Q3 a group only ever seen from 4–5 km keeps ~±700 m
on the kneeboard however long he watches — acceptable? Q4 a group lost while only "something" —
into mission memory too?

> *"Q1 - yes*
> *Q2 - one group*
> *Q3 - accept, and this is optics dependent. With binoculars you see better and so can judge unit
> apparent size better. That'd give a better range estimate. 9K113 has stadimeter and magnification
> and stabilization. With it distance measurement is much more accurate though not exact.*
> *Q4 - keep them too in mission memory. Keep all groups in mission memory, regardless of
> identification level."*

Reading:

- Q1: angular overlap decides whether he can see two things; relative distance decides whether
  separately seen things are one group. The 2026-09-18 rule stands for the first question.
- Q2: group membership is by neighbour gap (chain), not total extent.
- Q3: the stable per-group range error scales with the optic — naked eye largest, binoculars
  smaller (better apparent-size judgement), 9K113 much smaller (stadimeter, magnification,
  stabilisation) but not zero. A look through a better optic is new information and may tighten the
  estimate; a repeat look through the same optic from the same geometry may not.
- Q4: mission memory keeps every group, at any identification level.

## Plan-escalation answers (user, verbatim, 2026-10-31)

Asked: (1) rewrite, not extend, the tests built on the independent-looks model (exact-offset pins in
`test_estimation.py`, `precise-position-belief` dwell-convergence assertions)? (2) binocular range
scale 0.7 x naked eye as a judgement default, `#needs-flight`? (3) does "regardless of
identification level" also mean regardless of confidence, or keep a low confidence bar so a single
glimpse is not remembered?

> *"1 - ok*
> *2 - ok*
> *3 - keep the confidence floor"*

Reading (main loop):

- (1) Rewrite them as statistical property tests.
- (2) Binocular 0.7, judgement default, `#needs-flight`.
- (3) Stage 4 drops only the `nameable` (identification-level) gate. `GROUP_ENTRY_CONFIDENCE_FLOOR`
  (0.5) stays, unchanged, as the first-entry gate. Effect at today's constants: a class-level claim
  starts at 0.6 and is admitted on founding; a presence-only claim starts at 0.3 and needs four
  reinforcing observations (+0.05 each) to reach 0.5 -- a few seconds of consistent sighting at
  1 s polls, so a single glimpse is not remembered. The key is not retired.

## Cross-optic amendment decision (user, verbatim, 2026-11-01)

Asked: the far group seen by eye, then held only in memory, near group 1.5 km closer later seen
through binoculars folds 5–67% across 3–5 km (0% when the far group is still in the binocular
view, ≤1% same-optic). Options: (1) accept as the honest limit, fence with a test; (2) binocular
scale 0.85 instead of 0.7; (3) re-look along the whole bearing on raising binoculars (own feature).

> *"1"*

Reading (main loop): ship the amendment as written. `BL-B108.md` states E1 for same-optic and
in-view only, with the memory-only cross-optic rate. Option 3 is a possible later feature, not
backlogged until flights show the case occurs.

## Memory-only fold, real rate 0–86%: user's answer (verbatim, 2026-11-01)

Told: the shipped model folds the memory-only cross-optic case up to 86% (far group glassed at
4.5–5 km, out of view, near group 1.5 km closer then seen by eye), not the 67% first quoted.
Options: (1) accept; (2) binocular 0.85; (3) re-look along the whole bearing on raising binoculars.

> *"3 but not whole bearing. Check the expected locations/area. That's what I'd do, look around the
> area a bit and that would tell me if a unit I see is the same one.*
>
> *Like: looking ahead, I see couple of dots. I raise binoculars to take a look. That becomes group
> A, I believe it's 4.5 km away, and I see it's right of village near a river. In a moment I fly
> over a ridge I was approaching low and then can see some more units ahead. They are also near the
> river, but a bit different side of the village. Naked eye look immedeiately tells group A has 3
> dots and this new group B has 2 dots and that they are separate. Raising the binoculars, I first
> check the near group that is B and then A. That gives me information on both and a clear visual
> that they are not the same group.*
>
> *Counter example. In the above example I fly over the ridge and spot more contancts between group
> A and the village. Looking with binoculars I see that they all are group A units, just spread
> wide. I check group B and see that it is separate."*

Reading (main loop, to confirm with the user):

- Same-or-different is settled by **looking where the remembered group should be**, not by the
  range numbers alone. A focused look at A's expected area (not the whole bearing): A seen there
  → the new sighting is a different group; A not there → it may be A.
- Cues a real observer uses, beyond range: **position relative to a visible landmark** (right of
  the village, by the river), **dot count / composition** (3 vs 2), and the glass look at each.
- Order: near group first, then A.
- Counter-example: units spread between A and the village are A's, found by glassing them — group
  membership by neighbour gap (goal-check Q2) still applies.
