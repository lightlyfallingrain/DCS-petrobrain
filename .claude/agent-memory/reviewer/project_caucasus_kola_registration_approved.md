---
name: caucasus-kola-registration-approved
description: APPROVED clean review of feature/multi-theatre-caucasus-kola; technique for verifying registry-only theatre-addition commits against the real DCS install rather than trusting the research note.
metadata:
  type: project
---

`feature/multi-theatre-caucasus-kola` (45bac42) registered `THEATRE_PROJECTIONS["Caucasus"/"Kola"]`
and `REGIONS["caucasus-full"/"kola-full"]` plus Kola's town/beacon counts, following
`plans/multi-theatre-afghanistan/plan.md`'s already-exercised pattern directly from a dated
recon note (`world-model/research/2026-10-05-kola-caucasus-theatre-recon.md`) with no fresh
Architect plan — a reasonable call since the pattern was already fully exercised end-to-end by
Afghanistan and every number traces to the note. APPROVED, no required fixes.

**Verification technique, worth reusing for the next registry-only theatre addition** (this is
now the second time this shape of commit has been reviewed — see [[project_multi_theatre_afghanistan_review]]):
don't just check the diff matches the research note — independently re-derive the numbers against
ground truth the note itself used:
- Ran the real `parse_towns_lua`/`parse_beacons_lua` against the actual installed
  `/mnt/f/Games/DCS World/Mods/terrains/{Kola,Caucasus}/` files to reproduce town/beacon counts,
  rather than trusting the note's stated counts.
- Grepped the three beacon entries the new self-consistency test hardcodes
  (`beacons.lua`'s `position`/`positionGeo`) directly out of the real files and confirmed the
  test's literals match byte-for-byte.
- Wrote a throwaway script using the registered `coordinates.dcs_to_wgs84` against *every* beacon
  in each theatre (not just the test's 1-3 sample points) and got rms/max residuals matching the
  note's claimed rounded-value fit to the fourth decimal (Kola rms 0.0363 vs. note's 0.0364;
  Caucasus rms 0.0383 vs. note's 0.0385) — confirms the registered parameters aren't just
  plausible on the sampled points, they hold across the full beacon set.
- Hand-recomputed `centre_x/z`/`half_extent_x/z_m` from the note's own stated padded raw-union
  bounds and matched the diff's `REGIONS` entries to within a harmless 0.05 m rounding artifact.
- Ran `tools/derive_m9_osm_clip_bbox.py <region>` against the snapshot and diffed its output
  character-for-character against RUN.md's `osmium extract -b` commands.
- Perturbed `false_easting` by 102 m and reran the new parametrized test to confirm it's not
  vacuous (residual jumped to 101.6 m against a 0.2 m threshold).

This is strictly more verification than reading the diff and the note side by side — every number
had an independent source, not just internal consistency with the note that authored the commit.

Minor finding (optional, not blocking): `world-model/ROADMAP.md`'s backlog line still says
"Caucasus/Kola themselves remain backlog" post-merge of this commit — same roadmap-lag pattern
flagged in other reviews ([[project_group_detectability_roadmap_lag]],
[[project_group_reporting_stage4_review]]). Not a blocker here since the commit makes no
milestone-completion claim.
