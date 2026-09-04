"""Region definitions and the offline build pipeline.

`region.py` defines DCS-space regions (`REGIONS` registry); `ingest_*.py`
modules convert one raw source each into `store.models.StoredFeature` rows;
`pipeline.build_region` assembles them into one region's `.sqlite`. See
`plans/m5-first-persistent-model/plan.md` "New — region definition and
build pipeline".
"""
