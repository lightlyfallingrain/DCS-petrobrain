# BL-B31 — Nothing notices when the live LOS feed is absent

- [ ] **BL-B31 — Nothing notices when the live LOS feed is absent and the offline fallback takes
  over.** #status/open Security flagged this before the flight as low/low; the flight upgraded it.

  On 2026-10-05 **only 23 % of admitted contacts used a live DCS verdict**; the other 77 % silently
  used world-model's offline SRTM primitive with the 12 m terrain tolerance the user has ruled
  obsolete for live use. Every degradation path (no feed, stale skew, malformed verdict, duplicate
  unit name) converges on "absent" — correct behaviour, and completely silent.

  It *is* visible per-poll in the detection trace's `live_los_clear`/`hour_used`/`fov_half_deg_used`
  fields, but only to someone who goes looking. A whole sortie can run on the fallback while the
  pipeline reports success.

  Wanted: something that notices — a periodic log line when the live-verdict share over the last N
  polls drops below a threshold is probably enough. **It must not become a callout**; the pilot
  cannot act on it mid-flight.

  **SUPERSEDED 2026-10-06 by the unit-id probe — the structural cause below is the wrong one.**
  `aircraft-layer/research/2026-10-06-unit-id-join-results.md`: `unit_name` is never null and never
  duplicated in either flown mission (units 50/50, statics 94/94 join by name), so the
  nameless/duplicate mechanism described below **did not reproduce in the mission it was diagnosed
  from**. The real cause is that the LOS Hook walks `coalition.getGroups()` only, so **68.8 % of
  objects are statics it never enumerates** — see [[BL-11]] Stage 4, rewritten. The paragraph below is
  kept because the *reasoning error* is the instructive part: it explained the range anomaly
  correctly and was still wrong about why.

  **2026-10-05 security audit — the 77 % has a structural cause, not a timing one, and it is worse
  than "unobserved".** Scheduled as [[BL-11]] Stage 4.

  The LOS join key is `unit_name` (`perception/naked_eye_source.py:1066`, drop at `:1118`), and
  aircraft-layer's own schema declares that field `str | None`, **`None` for scenery and statics**
  (`aircraft-layer/src/schema/world_objects.py:109`). A nameless object can therefore **never**
  receive a live verdict — not an outage, a permanent hole — and falls through to the
  building-blind SRTM primitive forever. Objects sharing a name are dropped too
  (`name_counts[name] > 1`). Buildings and statics cluster close in, which is the only explanation
  offered so far that predicts the *sign* of the sortie note's §3 anomaly correctly (no-verdict
  rows median 3,820 m vs with-verdict 6,750 m). It means the building-occlusion capability [[X-B29]]
  was built for is structurally unavailable for exactly the population whose occlusion matters
  most — a `5p73 s-125 ln` behind a village building gets admitted and called out.

  **Verify before acting**: `DetectionTrace` carries `object_type` but not `unit_name`, so no
  existing trace can confirm it. Add `unit_name` plus a `los_join` reason enum, fly once, reduce.

  **The observable gap is total, not partial.** `naked_eye_source.py:348/976` stamps the same
  provenance string on every naked-eye `Observation` whichever primitive gated it;
  `visibility.py:785-790`'s two branches return identical `VisibilityResult`s; and
  `Contact.live_los_clear`'s `None` — the only in-principle signal — reaches the engagement gate
  and nothing else, never `tools.py`, `belief_truth_log.py`, or any counter.

  **Which way it fails**: the engagement gate (`belief/contacts.py:1357-1366`) fails open and is
  *right* to (it over-warns about something already seen). The **admission** gate fails open into
  a weaker instrument — one that cannot see buildings and carries 12 m of terrain slack. Same word,
  different thing. Yes, contacts are admitted with no verdict at all: 11,268 of 14,703, and nothing
  records it.

  **Interaction with [[BL-B30]]**: if the loop is slow *because* the fallback is doing SQLite work per
  candidate, these are one problem seen from both ends and fixing availability would fix the rate.
  A hypothesis, not a finding.
