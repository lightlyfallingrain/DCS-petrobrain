---
name: project_sam_site_geometry
description: Real-world SAM emplacement spacing figures found/not-found for the group-cohesion installation cap, and where to look next
metadata:
  type: project
---

Session 2026-10-01, body-layer/research/2026-10-01-sam-site-geometry.md: researched real SAM site
geometry after the user flagged the 236-838m DCS-sortie S-300 spacing (used to justify a proposed
1000m cohesion cap in plans/group-cohesion-redesign/plan.md §3) as worthless — mission-author test
placement, not real doctrine.

**Found with real numbers:** S-75/SA-2 flower site — launcher spacing ~60-100m, site diameter
~160-230m (geimint.blogspot.com imagery analysis, ausairpower.net corroborates). S-125/SA-3 —
~60m launcher spacing (secondary-source only, no primary imagery measurement with error bar).

**Gap, confirmed real not a search miss (multiple distinct queries each):** no numeric spacing
figure exists anywhere consulted for SA-6/Kub TEL-radar distance, Buk TELAR-TELAR/TAR distance,
S-300 TEL-radar distance, Tunguska/Pantsir battery vehicle dispersion. These are the
Syria/Mi-24P-relevant mobile systems that most need a number.

**Why:** classic open-source SAM-site analysis (geimint, ausairpower) is Cold-War/Vietnam-era,
fixed-radar star-site focused (SA-2/3/5). Modern mobile TELAR systems (Buk, S-300, Tunguska) don't
have the same imagery-geolocation literature from that era.

**Next source to try, not yet attempted:** post-2022 Ukraine-war OSINT imagery geolocation
(Oryx, Bellingcat, Covert Shores) — these systems have been repeatedly destroyed/geolocated in
the field since 2022 and would likely have real measured field-deployment spacing. Worth a
dedicated search before re-opening this question.

**RUSI Bronk IADS report (static.rusi.org/20191118_iads_bronk_web_final.pdf)** — strong candidate
primary source on dispersion doctrine distances specifically — WebFetch returned it as unreadable
binary (not a 403, genuinely unparseable by the tool). Ask user to open directly and paste the
dispersion/survivability section if this question reopens.

**DCS-community practical numbers (not real-world, but the "what mission authors actually do"
half of the question):** letsflyvfr.com DCS mission-editor tutorial gives 200-800m "disperse
components," 200-600m for SA-6-type battery, 1-2km SHORAD offset from protected asset, 0.5-1km
AAA/MANPADS ring. Unsourced itself (community tutorial), but useful as the DCS-authoring-norm
data point distinct from real doctrine.

**Single-vehicle systems (Osa/Tor/Tunguska/Shilka) are not "installation" cases at all** — each
one is its own radar+launcher, so inter-vehicle spacing within a same-type battery is a different
question (battery-mate cohesion among single-vehicle platforms) from "components of one fixed
site." Don't conflate these when a cohesion-cap question comes up again.
