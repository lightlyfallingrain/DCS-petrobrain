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
