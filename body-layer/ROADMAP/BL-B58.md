# BL-B58 — A within-group fold's position drift can widen a cluster enough to absorb an unrelated contact

- [ ] **BL-B58 — [[BL-12]] Stage 3's within-group ambiguity fold (D5 at contact grain) moves a
  contact's fused position toward the folded percept (`fold_position` is a real weighted fuse, not
  a no-op); the next `tick()`'s position-only cluster can widen enough to absorb a previously
  separate, correctly-identified contact into the same `Group` — not itself an ambiguous candidate
  for anything, and not individually failing any gate.** #status/open Found by the Implementer
  during Stage 3 (2026-10-12), via a plan-unlisted test (`test_callouts.py`'s 2C fixture), confirmed
  and characterised by the Reviewer the same stage round.

  **Reproduced independently, not just read off the implementer's log.** Running the fixture
  directly: at t=12 a 2-o'clock infantry pair folds onto `GROUP_1`'s two nearest members
  (`CONTACT_1`/`CONTACT_2`, 12/1-o'clock infantry inflated 12s unseen) instead of founding
  `CONTACT_6`/`CONTACT_7` — accepted failure mode 2 (undercount), per the plan's own Q5. The fold's
  position drift then pulls `CONTACT_4` (a correctly-identified BTR-70, never itself a candidate)
  into the same cluster on the very next `reconcile()`, via `_cluster_contacts`'s ordinary
  single-link union-find over fused positions — not via Stage 1's displacement test or D6's
  identity-matching gate, neither of which this path goes through (the absorbed cluster already
  overlaps 3/4 members with the existing `Group`, so it resolves via phase 1's plain
  highest-overlap match, which carries no class/air-defence/displacement check at all).

  **Bounded within one incident, not an unbounded single-tick runaway — measured, not argued.**
  Continuing the fixture for ten further polls with fresh, nearby infantry percepts: each one folds
  onto the existing group (repeating the undercount) and nudges the folded-onto contact's position,
  but `centroid_uncertainty_m` stabilises (258 m -> 242 m) and group membership does not keep
  growing past the four members the first incident produced — re-observation shrinks covariance
  faster than drift widens it, once the group *is* being seen. The risk is **repeat-incident**, not
  single-tick exponential: each time a group's members go unobserved long enough for covariance to
  inflate (ordinary, e.g. masked by terrain or out of the FOV wedge) *and* an ambiguous percept
  happens to land nearby when visibility returns, one more absorption of this shape can occur,
  independently, on its own schedule.

  **Significantly amplified by this fixture's own fallback, not a pure artifact either.** The
  fixture's observations declare no `position_uncertainty`, so both sides of the gate fall back to
  the isotropic `_FALLBACK_UNCERTAINTY_RADIUS_M` (300 m) — a path `association_over_time.py`'s own
  comment says "should not happen in production," since both real sources (naked-eye, scope/hybrid)
  declare their own. At the fixture's short ranges (280-500 m), real declared naked-eye uncertainty
  (`naked_eye_sigma_m`, `BEARING_SIGMA_DEG=3.0`, `RANGE_FRACTIONAL_SIGMA=0.17`) is far tighter
  (~50-90 m one-sided) than the 300 m fallback, so this fixture's absorption at 500-900 m would not
  reproduce at these ranges with a real declared uncertainty. **But at the ranges this project's own
  measurements already cite as typical naked-eye operating range** (`plans/
  contact-duplication-ambiguity-runaway/debug.md`: ~590 m one-sided gate at 1200 m range; `[[BL-12]]`
  roadmap entry: 600 m gate after 30 s unseen), declared uncertainty alone is already comparable to
  or wider than this fixture's fallback — so the mechanism (fold -> drift -> wider cluster -> absorbs
  an unrelated, previously-separate contact) is not confined to the fixture's artifact; it would
  recur at realistic mid-range engagement distances with entirely real, declared uncertainty, just
  without the fixture's own extra ~3x amplification at *these particular* close ranges.

  **D6's own gate is unaffected — checked directly, not assumed.** The absorption happens through
  `reconcile`'s phase 1 (overlap match) and `_cluster_contacts` (position-only single-link), neither
  of which is a resolution path D6 or amendment A3 touch; D6's hard air-defence-confirmation test
  (Stage 1 test 3) only gates phase 2 (property match — re-identifying a cluster with *zero* member
  overlap against a remembered group), which this path never reaches, and
  `Group.air_defence_composition` is recomputed fresh from the matched cluster's actual current
  members every `reconcile()` call regardless of phase (`groups.py` phase 1/3 construction, read
  directly) — so it is never stale or carried over. The practical risk is therefore not a stale or
  bypassed air-defence flag; it is that **cluster *membership itself* can be corrupted by this
  drift**, in either direction — an air-defence-classified contact could be swept into (or a
  previously-included one swept out of) a group via spurious position drift unrelated to either
  unit's real movement, which would then correctly but misleadingly update that group's reported
  `air_defence_composition` to match the corrupted membership. Not reproduced with an actual
  air-defence contact in this round (time-boxed); flagged here as the concrete next check before
  this is closed.

  **None of the plan's three named Stage 3 failure modes individually describes this.** Failure mode
  1 ("within-group record swapping... the group-level answer stays correct") is the one that comes
  closest and explicitly does not cover it: here the group-level answer becomes wrong — a correctly
  individually-identified unit gets reported as part of a group it does not belong in.

  **Options, costs, or-mark for the user (orchestrator: put this to them, no recommendation forced
  here beyond the relative cost read):**

  1. **Accept as-is for Stage 3; widen [[BL-12]] Stage 4's planned speech-time extent guard** (plan
     amendment A6: "do not speak a heading or a single bearing for a group wider than one believable
     bearing") **to also suppress composition-based disclosure lines** (not just heading/bearing)
     once a group's extent exceeds the same bound. Cheapest — Stage 4 is not built yet, so this is a
     scope addition to unbuilt work, not a new mechanism on a merged stage. Does not fix the
     underlying membership corruption, only stops it from being *spoken* past a width bound; the
     wrongly-grouped contact's own individual disclosure (if it has one) is unaffected.
  2. **Bound how far a single fold-driven `Contact.record` call may move a fused position**,
     independent of the covariance-driven fuse. New mechanism, new calibration question (what bound,
     relative to what), delays nothing already merged but is real design work the plan did not
     scope and the implementer correctly declined to add unprompted.
  3. **Require cohesion to be re-checked before a cluster absorbs a member via plain overlap-match**,
     e.g. excluding a newly-added member whose own gap to the pre-existing cluster fails the same
     pair backstop `_cluster_contacts` already applies pairwise within one cluster-formation pass.
     Most architecturally correct (closes the gap at its source, `_cluster_contacts`/`reconcile`
     rather than downstream at speech time) and the most expensive — touches the clustering
     mechanism this whole milestone's Stage 0 already revised once, and needs its own review pass.

  Related: [[BL-12]] Stage 3 (where this was found), [[BL-B50]] (membership flipping on consecutive
  ticks — a sibling instability in the same reconcile machinery), amendment A6 in `plans/
  group-contact-identity/plan.md` (the Stage 4 extent guard option 1 would widen).
