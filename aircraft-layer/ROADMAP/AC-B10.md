# AC-B10 — A dead Hook and an empty scene are indistinguishable downstream

- [ ] **AC-B10 — Make a Hook that never loaded observable from outside DCS.** #status/open
  Filed 2026-10-17, out of `[[AC-B9]]`.

  **The gap, stated as the thing that actually happened.** Three Hook scripts failed to load on
  2026-10-17. DCS said so once, in `dcs.log`, at mission load. Nothing else said anything: the
  collector served its endpoints, `GET /line_of_sight/latest` returned its normal empty-cache
  shape, body-layer's `AircraftLayerError` → `None` fallbacks did exactly what they are designed
  to do, and Petrovich flew a whole sortie seeing nothing while every component reported itself
  healthy. The blackout was diagnosed by reading a 23744-row detection trace and comparing it
  against a two-day-old one.

  **The independent-degradation design is correct and is not what should change.** One dead feed
  must not take a poll down (`naked_eye_source.py`'s velocity, firing and LOS joins each fall
  back to `None` on a transport error). What is missing is not resilience but a *signal*: the
  degraded state is silent, and silence is also what a genuinely empty scene looks like.

  **Candidate shapes, cheapest first — not yet decided:**

  - **Liveness on the feed itself.** A Hook that loaded registers its presence once; the
    collector serves "this feed has never reported" distinctly from "this feed reported
    nothing". That distinction is the whole feature, and it is one bit per feed.
  - **A body-layer startup assertion.** `logger.py` already computes
    `LiveLosCoverage.no_verdict` and warns on the first nonzero transition
    (`_warn_live_los_coverage_gap_once`). That machinery fired correctly here and nobody was
    reading the console. A *startup* check — "the LOS feed has produced zero verdicts in the
    first N polls while candidates exist" — is a different and louder claim than a per-poll
    coverage warning.
  - **Say it in the cockpit.** The pilot is the one person guaranteed to be present. A single
    "I can't see anything out there" from Petrovich on sustained zero-verdict would have ended
    this in thirty seconds. Needs the `/explore` conversation before anyone builds it — it is a
    crew-behaviour decision, not a telemetry one, and a false positive in a genuinely empty
    scene is worse than silence.

  **Do not fold this into a pre-flight checklist item.** A checklist is a thing someone must
  remember at the moment attention is on flying, which is the failure mode this project already
  has written rules about.

  Related: `[[AC-B9]]`, `[[AC-B7]]`, `[[AC-B8]]`.
