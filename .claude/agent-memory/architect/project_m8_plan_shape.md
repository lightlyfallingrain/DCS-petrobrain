---
name: m8-plan-shape
description: M8 is incremental-probe-store only (two-SQLite split, user-proposed and adopted); OSM/Geofabrik split off as M9, deferred and unscheduled
metadata:
  type: project
---

Planned 2026-09-06 after M7. Originally drafted as one milestone with two tracks;
**the user split it**: M8 = incremental store only
(`plans/m8-incremental-store/plan.md`), M9 = OSM/Geofabrik
(`plans/m9-osm-geofabrik/plan.md`), deferred entirely and unscheduled pending a
fresh Architect pass.

**The load-bearing decision — two SQLite files per theatre, not one.** The user
proposed it against my original `grid.tier`-column design; evaluated and adopted.
The decisive argument is a **lifecycle mismatch**, not the bug class: the base
store's documented contract is "always rebuilt from `data/raw/`, never patched in
place", while probe-tier data is *not rebuildable from anything on disk* (its
source is a live DCS mission that no longer exists). Non-reproducible data must
not live in a file whose lifecycle is delete-and-recreate. Secondary wins: it
makes [[grid-tier-hazard]] structurally impossible rather than merely avoidable,
and leaves every M7-validated read path untouched. Reads use `ATTACH DATABASE` so
`describe_position` keeps its single-`conn` signature; writes open only the probe
store. The probe store holds exactly one grid per kind, enforced by
`UNIQUE(kind)`.

**Why this is worth remembering:** I reached for the in-file column first. The
better answer came from asking which data is reproducible and which is not —
storage-boundary questions in this project are usually lifecycle questions.

**Probe-tier kinds must be addable without a schema migration** (user requirement,
added last). Raster data keys off `grid.kind`, vector data off the generic
`StoredFeature` shape — both already mirrored the base store, so no change was
needed there. The narrowness was in the *coverage* axis: chunk coverage is keyed
`(kind, chunk_ix, chunk_iz)`, never chunk alone, because a chunk-only row asserts
"probed" without saying *for what* — a fourth kind added later would inherit
false coverage everywhere, and fixing that would need the very migration the
requirement forbids.

**All decisions closed 2026-09-06, plan is final and ready to implement.** Locked:
two stores; 5,000 m chunks / 100 m probe spacing; `<region>-probe.sqlite`;
base-store per-layer append **dropped** from M8 (the `todo/todo.md` "Incremental
per-layer pipeline builds" backlog item stays open and unscheduled — do not
assume it exists). `build_region` is untouched by M8.

**How to apply:** when planning anything that writes to the world model, ask
first whether the data can be regenerated from `data/raw/`; that answer decides
which store it belongs in. Also reusable from this pass: most of `src/osm/`
survives a source-format change (its dataclasses are format-agnostic; only
`load_features` is Overpass-specific), and `describe_position`'s OSM fields are
already wired and merely starved of data. Related: [[m5-storage-decision]].
