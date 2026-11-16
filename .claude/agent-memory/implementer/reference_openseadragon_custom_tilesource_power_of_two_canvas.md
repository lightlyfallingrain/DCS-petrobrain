---
name: reference_openseadragon_custom_tilesource_power_of_two_canvas
description: OpenSeadragon's own tile-level convention (level 0 = most zoomed out, maxLevel = full native res) already matches a server's own "k = maxLevel - level" mosaic math -- no inversion needed. Declaring the logical canvas as a power-of-two multiple of the tile size, rather than the mosaic's true pixel extent, sidesteps OpenSeadragon's cropped-edge-tile handling when every server tile is always a full square.
metadata:
  type: reference
---

Found/confirmed while building `raster-chart-viewer`'s `static/index.html` (OpenSeadragon 4.1.1, a
custom plain-object `TileSource`, `plans/raster-chart-viewer/plan.md` Stage 5).

**Level direction already matches, in both directions, with no code needed to reconcile them.**
OpenSeadragon's own convention: level 0 is the single most-zoomed-out tile, `maxLevel` is full
native resolution. A server mosaic defined as "`k` doublings out from full res, `k = maxLevel -
level`" (this project's `cache.compose_view_tile`) lines up with that exactly — `getTileUrl(level,
x, y)` can pass `level` straight through to the server with no sign flip or `maxLevel - level`
translation on the client side. Easy to second-guess this and get it backwards while debugging
something unrelated (happened once during this feature's real-data smoke check) — if tile content
looks "zoomed the wrong way", the bug is very unlikely to be here; reread the server's own
`k = grid.max_level - level` definition before touching the client.

**Declaring the TileSource's `width`/`height` as `2^maxLevel * tileSize` (a power-of-two square),
not the mosaic's real pixel extent, avoids reconciling two different edge-tile contracts.**
OpenSeadragon's default behaviour for a non-power-of-two image expects the edge row/column's tiles
to be *cropped* (smaller than `tileSize`) at the true image boundary. A server that always returns
a full `tileSize` x `tileSize` image (blank-padded past real coverage, as this one does for sparse
sheets) conflicts with that expectation for any real mosaic whose pixel extent isn't an exact
power-of-two multiple of the tile size — which is the common case, not the exception (e.g.
Afghanistan's RasterCharts grid is 48x64 tiles; 48 isn't a power of two). Declaring a slightly
larger, power-of-two logical canvas means every tile OpenSeadragon ever requests — in-bounds or in
the padding past the real grid — gets the identical full-square shape, so the cropped-edge-tile
code path never has to run at all.

**Caveat — the pan/zoom rendering itself was never exercised in a real browser** when this was
written (no browser available in that environment); verified only that every endpoint the page
calls serves correctly end-to-end plus a `node --check` syntax pass on the inline script. If a
residual edge-tile visual artifact exists despite the above, a real browser check is what would
catch it, not more reasoning about the mechanism.
