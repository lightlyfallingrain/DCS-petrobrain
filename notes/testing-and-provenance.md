# Testing & Provenance

- **Control-point tests must use externally-published ARPs, not DCS-derived points.** Early approach using pydcs's hardcoded `Damascus` point inflated the residual by ~1741m (the pydcs point itself was imprecise vs. live `coord.LOtoLL` output). M1 control points use SkyVector/eAIP real-world ARPs instead, avoiding circularity (Finding 3 of M1 verification note). Lesson: when validating a DCS extraction pipeline against external truth, ensure the external truth is actually independent, not recalculated from the same source.

- **Confidence field distinguishes third-party-fitted from live-install-verified parameters.** Syria's registry entry is `confidence="confirmed"` because Finding 1 reproduced 226 live DCS points to sub-cm residual; future theatres can be added with `confidence="provisional"` without code changes. This protects against silently encoding unverified community claims as fact, per project invariant (docs/CONVENTIONS.md).
