#!/usr/bin/env bash
# M5 recon, deep-dive pass 2 -- builds on probe_syria_roadnet_files.sh.
#
# That first probe (see world-model/research/2026-09-03-m5-roadnet-file-recon.md
# and .../2026-09-03-m5-roadnet-files-probe-raw.txt) captured only the first
# 512 / last 256 bytes of Syria.rn4 / Syria.routes. Decoding those bytes
# locally (offline, from the already-synced hex dump -- no DCS access needed
# for that step) established:
#   - a clean, consistent 8xint32 header (magic=2, const=48, a byte-count
#     field, 5 zero ints) followed by a length-prefixed class-name string
#     ("landscape4::lRoadNetwork" / "landscape4::lRoutesFile"), identical
#     across Syria/Caucasus/airfield files;
#   - Syria.rn4 additionally carries a length-prefixed STRING TABLE of road/
#     taxiway type names (count given by a header field -- confirmed exactly
#     23 for Syria.rn4 by counting both the field value and the strings
#     present in the 512-byte sample);
#   - Syria.routes' data region, once correctly offset, decodes cleanly as
#     an array of little-endian float64 (x, y, z) triples whose values
#     (x~214985, y~18.7, z~-45080, with tiny consecutive deltas between
#     triples) are exactly the right order of magnitude and shape for a
#     dense DCS-coordinate road-centerline polyline sample.
#
# What's still unverified because only head/tail bytes were captured:
#   - the full Syria.rn4 string table (only visible up to the 512-byte cutoff
#     in the first probe -- want the complete list, and the header fields
#     that immediately follow it, decoded as int32);
#   - the .rn4 per-record binary structure after the string table (attempted
#     by hand from the printed hex dump and produced implausible values --
#     almost certainly a manual hex-transcription alignment error, not a
#     format finding; needs a real byte-exact read, hence this script);
#   - whether the .routes float64-triple structure holds up away from the
#     very start of the file (only the first ~4 triples were decoded);
#   - whether a comparable magic/header exists in candidate terrain-mesh/
#     elevation files identified from the filename listing
#     (world-model/data/raw/dcs/2026-09-02/DCS-files.txt): a single large
#     per-terrain `Scenes/Syria.scn5`, and `surface/Syria.{tile,ng5,surface5,
#     onlay.sup4}` -- none of these have been opened at all yet. Elevation/
#     mesh extraction is *not* blocking (M4 already has a working live
#     land.getHeight + SRTM3 pipeline) -- this is purely to check whether a
#     cheaper static source exists.
#
# This script does real parsing work in place (WSL/Windows side) using
# python3, so multi-GB files never need to leave the DCS machine. It only
# reads small byte ranges via seek -- it does not load whole files into
# memory, and it is strictly read-only.
#
# This is the canonical, version-controlled copy. To run it: copy this file
# into win-mac-sync/run-wsl/ (use the wsl-probe-sync skill), run it there in
# WSL bash on the Windows DCS machine, then sync the output back. See
# world-model/WORKFLOW.md for the cross-machine convention.
#
# Requires:
#   DCS_INSTALL_PATH  - DCS World install dir (Windows or WSL-style path)
#   python3 on PATH in the WSL shell used to run this script
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="$(cd "$script_dir/../wsl-output" && pwd)"

require_env() {
  local var_name="$1"
  if [ -z "${!var_name:-}" ]; then
    echo "ERROR: $var_name is not set." >&2
    exit 1
  fi
}
require_env DCS_INSTALL_PATH

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH in this shell -- this script needs it for byte-exact struct decoding." >&2
  exit 1
fi

to_wsl_path() {
  local p="$1"
  if [ -d "$p" ]; then echo "$p"; return; fi
  if command -v wslpath >/dev/null 2>&1; then wslpath -u "$p"; return; fi
  echo "$p"
}

install_path="$(to_wsl_path "$DCS_INSTALL_PATH")"
syria_path="$install_path/Mods/terrains/Syria"

if [ ! -d "$syria_path" ]; then
  echo "ERROR: resolved Syria terrain path does not exist: $syria_path" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_file="$output_dir/syria_terrain_files_deep_probe_${timestamp}.txt"

py="$script_dir/_probe_syria_terrain_files_deep.py"
cat > "$py" << 'PYEOF'
import math
import struct
import sys
import zlib

def read_at(path, offset, length):
    with open(path, 'rb') as f:
        f.seek(offset)
        return f.read(length)

def file_size(path):
    import os
    return os.path.getsize(path)

def hexdump(b, base=0, width=16):
    lines = []
    for i in range(0, len(b), width):
        chunk = b[i:i+width]
        hexpart = ' '.join(f'{c:02x}' for c in chunk)
        asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        lines.append(f'{base+i:08x}: {hexpart:<{width*3}} {asc}')
    return '\n'.join(lines)

def parse_landscape4_header(b):
    """Common header shared by .rn4 and .routes: 8xint32, then a
    length-prefixed class name string. Returns (header_ints, classname, next_offset)."""
    ints8 = struct.unpack_from('<8i', b, 0)
    off = 32
    namelen = struct.unpack_from('<I', b, off)[0]
    off += 4
    name = b[off:off+namelen].decode('ascii', errors='replace')
    off += namelen
    return ints8, name, off

def rn4_string_table(path, max_strings=64):
    """Read Syria.rn4 header + full string table (road/taxiway type names)."""
    head = read_at(path, 0, 4096)
    ints8, name, off = parse_landscape4_header(head)
    field_after_name = struct.unpack_from('<I', head, off)[0]
    off += 4
    strcount = struct.unpack_from('<I', head, off)[0]
    off += 4
    strings = []
    for i in range(min(strcount, max_strings)):
        if off + 4 > len(head):
            # grow the read window if the table is bigger than 4KB
            head = read_at(path, 0, len(head) + 8192)
        slen = struct.unpack_from('<I', head, off)[0]
        off += 4
        s = head[off:off+slen].decode('ascii', errors='replace')
        off += slen
        strings.append(s)
    print(f"  header 8xint32: {ints8}")
    print(f"  class name: {name!r}")
    print(f"  field immediately after class name: {field_after_name}")
    print(f"  string-table count field: {strcount}")
    print(f"  strings ({len(strings)} read):")
    for s in strings:
        print(f"    - {s}")
    print(f"  binary data region starts at byte offset: {off}")
    return off

def rn4_stride_analysis(vals, strides=(2, 4, 8, 16, 32)):
    """Score candidate record strides (in int32 units) by column regularity:
    a real fixed-size record layout should show at least some columns that
    are constant (marker/type fields) or follow a simple monotonic/paired
    pattern (indices), whereas a wrong stride or genuinely unstructured data
    should look uniformly noisy in every column. This is a cheap, purely
    local (no-DCS-access-needed) heuristic to narrow down the stride before
    trusting a specific field layout."""
    print("  stride regularity scan (no assumed record size trusted a priori):")
    best = None
    for stride in strides:
        n_rows = len(vals) // stride
        if n_rows < 2:
            continue
        rows = [vals[i * stride:(i + 1) * stride] for i in range(n_rows)]
        const_cols = 0
        for col in range(stride):
            column = [r[col] for r in rows]
            if len(set(column)) == 1:
                const_cols += 1
        const_frac = const_cols / stride
        print(f"    stride={stride} int32 ({stride*4} bytes): {n_rows} full rows, "
              f"{const_cols}/{stride} constant columns (frac={const_frac:.2f})")
        # A small stride tested against few int32s trivially looks "regular"
        # (fewer rows = less chance to disprove constancy), so require a
        # minimum number of rows before trusting a candidate, and on a tie
        # in constant-column fraction prefer the SMALLER stride (strides are
        # tried ascending here, so plain '>' keeps the first/smallest one) --
        # more rows at a smaller stride is stronger, not weaker, evidence.
        if n_rows >= 4 and const_cols >= 1 and (best is None or const_frac > best[1]):
            best = (stride, const_frac, n_rows)
    if best:
        print(f"  best-scoring stride candidate: {best[0]} int32 ({best[0]*4} bytes) "
              f"-- {best[1]:.2f} constant-column fraction over {best[2]} rows (>=4 rows "
              f"required to reduce small-sample noise; heuristic only, NOT a confirmed "
              f"record layout -- needs a larger sample / cross-theatre check to promote "
              f"to 'reproduced-locally')")
    else:
        print("  no stride in the scanned set showed any constant column -- "
              "no confident stride recommendation from this heuristic")
    return best

def rn4_sample_records(path, data_start, n_ints=512, mid_sample=True):
    size = file_size(path)
    print(f"  file size: {size}")
    chunk = read_at(path, data_start, n_ints * 4)
    vals = struct.unpack_from(f'<{len(chunk)//4}i', chunk, 0)
    print(f"  first {len(vals)} int32 after string table (raw, unaligned to any assumed record size):")
    print(f"    {vals}")
    rn4_stride_analysis(vals)
    if mid_sample:
        mid = size // 2
        mid -= mid % 4  # keep 4-byte aligned, NOT record-aligned (record size unknown)
        chunk2 = read_at(path, mid, n_ints * 4)
        vals2 = struct.unpack_from(f'<{len(chunk2)//4}i', chunk2, 0)
        print(f"  {len(vals2)} int32 sampled from file-relative-midpoint offset {mid} (record alignment NOT guaranteed here):")
        print(f"    {vals2}")
        rn4_stride_analysis(vals2)

def routes_header_and_data_start(path):
    head = read_at(path, 0, 256)
    ints8, name, off = parse_landscape4_header(head)
    print(f"  header 8xint32: {ints8}")
    print(f"  class name: {name!r}")
    # Observed layout from the first probe's manual decode:
    #   int32 field3, int32=11464, int32=1, int32=6, 8 bytes of 0xFF (sentinel),
    #   int32=0, int32=343, then float64 (x,y,z) triples begin.
    # Read generically and print the raw ints/bytes so this can be checked
    # rather than assumed.
    ints_after = struct.unpack_from('<6i', head, off)
    print(f"  6 int32 immediately after class name: {ints_after}")
    off2 = off + 6 * 4
    sentinel = head[off2:off2+8]
    print(f"  next 8 bytes (expected 0xFF sentinel): {sentinel.hex()}")
    off2 += 8
    trailing = struct.unpack_from('<2i', head, off2)
    print(f"  next 2 int32: {trailing}")
    off2 += 8
    print(f"  float64 data region starts at byte offset: {off2}")
    return off2

# Known-plausible Syria DCS-coordinate envelope, generously bounded (see
# 2026-09-03-m5-recon.md nodesMap.lua maxX~248852, Gemerek testbed x~461320,
# and the hand-decoded first triples x~214985/z~-45080/y~18.7). Used only to
# score candidate byte offsets / reject obviously-garbage floats -- NOT used
# to silently "correct" data, always reported alongside raw values.
PLAUSIBLE_X = (-100_000.0, 600_000.0)
PLAUSIBLE_Z = (-600_000.0, 600_000.0)
PLAUSIBLE_Y = (-500.0, 9_000.0)
SMOOTH_DELTA_M = 2_000.0  # generous consecutive-point-distance ceiling for "smooth polyline"

def _safe_unpack_triple(chunk, i):
    """Decode one (x,y,z) float64 triple, returning None (not raising) if the
    bytes don't even form valid/finite floats -- avoids the OverflowError
    crash seen when an unpack succeeded but produced a huge finite float
    whose *square* overflows a Python float during distance calculation."""
    try:
        x, y, z = struct.unpack_from('<3d', chunk, i * 24)
    except struct.error:
        return None
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        return None
    return x, y, z

def _triple_plausible(t):
    x, y, z = t
    return (PLAUSIBLE_X[0] <= x <= PLAUSIBLE_X[1]
            and PLAUSIBLE_Z[0] <= z <= PLAUSIBLE_Z[1]
            and PLAUSIBLE_Y[0] <= y <= PLAUSIBLE_Y[1])

def _safe_distance(a, b):
    """(dx**2+dy**2+dz**2)**0.5 but never raises OverflowError -- huge
    (but finite) coordinate garbage would otherwise overflow float squaring.
    Returns None (not a huge number) when the delta itself isn't computable,
    so callers can treat it as 'not scoreable' rather than 'huge'."""
    try:
        dx, dy, dz = a[0] - b[0], a[1] - b[1], a[2] - b[2]
        return (dx**2 + dy**2 + dz**2) ** 0.5
    except OverflowError:
        return None

def routes_score_offset(path, offset, n_triples=40):
    """Score one candidate byte offset for 'looks like the real (x,y,z)
    float64 triple array start': fraction of decoded triples that are both
    individually plausible (within Syria's known coordinate envelope) and
    smoothly connected to their predecessor (small consecutive-point
    distance, as a road-centerline polyline should be). Never raises --
    unreadable/garbage offsets simply score 0.0."""
    try:
        chunk = read_at(path, offset, n_triples * 24)
    except OSError:
        return 0.0, 0, 0
    triples = []
    for i in range(len(chunk) // 24):
        t = _safe_unpack_triple(chunk, i)
        if t is not None:
            triples.append(t)
    if not triples:
        return 0.0, 0, 0
    plausible = [t for t in triples if _triple_plausible(t)]
    plausible_frac = len(plausible) / len(triples)
    smooth = 0
    scoreable = 0
    prev = None
    for t in triples:
        if prev is not None:
            d = _safe_distance(t, prev)
            if d is not None:
                scoreable += 1
                if d <= SMOOTH_DELTA_M:
                    smooth += 1
        prev = t
    smooth_frac = (smooth / scoreable) if scoreable else 0.0
    score = plausible_frac * smooth_frac
    return score, len(triples), len(plausible)

def routes_find_data_start_bruteforce(path, lo=64, hi=160):
    """Scan every byte offset in [lo, hi) as a candidate float64-triple data
    start and pick the best-scoring one by routes_score_offset. Addresses
    the earlier crash: the hand-derived/header-arithmetic offset (99) was
    trusted without verifying it actually produced plausible, smoothly
    connected points -- this replaces that trust with a measurement."""
    print(f"  brute-force offset scan [{lo}, {hi}):")
    results = []
    for off in range(lo, hi):
        score, n, n_plausible = routes_score_offset(path, off)
        results.append((score, off, n, n_plausible))
    results.sort(key=lambda r: (-r[0], r[1]))
    print("    top 5 candidates (score, offset, n_triples_decoded, n_plausible):")
    for score, off, n, n_plausible in results[:5]:
        print(f"      score={score:.3f} offset={off} n={n} plausible={n_plausible}")
    best_score, best_off, _, _ = results[0]
    if best_score == 0.0:
        print("  WARNING: no candidate offset in the scanned window scored above 0.0 -- "
              "the data region may start outside [lo, hi), or the file layout differs "
              "from the .routes files probed so far. Falling back to the header-arithmetic "
              "offset with no confidence.")
        return None
    print(f"  best offset: {best_off} (score={best_score:.3f})")
    return best_off

def routes_sample_triples(path, data_start, n_triples=200, mid_sample=True, label=""):
    size = file_size(path)
    print(f"  file size: {size}")
    def decode_and_report(offset, count, tag):
        chunk = read_at(path, offset, count * 24)
        xs, ys, zs = [], [], []
        deltas = []
        skipped = 0
        prev = None
        for i in range(len(chunk) // 24):
            t = _safe_unpack_triple(chunk, i)
            if t is None:
                skipped += 1
                prev = None
                continue
            x, y, z = t
            xs.append(x); ys.append(y); zs.append(z)
            if prev is not None:
                d = _safe_distance(t, prev)
                if d is not None:
                    deltas.append(d)
            prev = t
        if not xs:
            print(f"    [{tag}] no data decoded (offset={offset})")
            return
        print(f"    [{tag}] offset={offset} n={len(xs)}"
              + (f" (skipped {skipped} non-finite/undecodable)" if skipped else ""))
        print(f"      x range: {min(xs):.2f} .. {max(xs):.2f}")
        print(f"      y range: {min(ys):.2f} .. {max(ys):.2f}")
        print(f"      z range: {min(zs):.2f} .. {max(zs):.2f}")
        if deltas:
            print(f"      consecutive-point distance: min={min(deltas):.3f} max={max(deltas):.3f} "
                  f"mean={sum(deltas)/len(deltas):.3f}")
        else:
            print("      consecutive-point distance: none computable (all deltas skipped)")
        print(f"      first 3 triples: {list(zip(xs[:3], ys[:3], zs[:3]))}")
    decode_and_report(data_start, n_triples, "start-of-file")
    if mid_sample:
        mid = size // 2
        mid -= (mid - data_start) % 24  # keep 24-byte record-aligned relative to data_start
        decode_and_report(mid, n_triples, "file-midpoint (24-byte aligned to data_start)")

def probe_unknown_file(path, label, head_len=1024, tail_len=256):
    print(f"--- {label}: {path} ---")
    import os
    if not os.path.isfile(path):
        print("  (not found)")
        return
    size = file_size(path)
    print(f"  size: {size}")
    head = read_at(path, 0, min(head_len, size))
    print(f"  first {len(head)} bytes:")
    print(hexdump(head))
    # Look for the landscape4:: magic string anywhere in the head sample.
    if b'landscape4' in head:
        idx = head.index(b'landscape4')
        print(f"  FOUND 'landscape4' substring at head offset {idx}")
    else:
        print("  no 'landscape4' substring in head sample")
    # Look for zlib stream magic bytes (0x78 followed by a valid FLEVEL byte)
    # -- precedent: .tif.clipmap files are zlib-chunked (see agent memory
    # clipmap-container-format.md). Check the first 2 bytes and also scan
    # for zlib headers anywhere in the head sample (in case of a preamble).
    zlib_candidates = [i for i in range(len(head) - 1)
                        if head[i] == 0x78 and head[i+1] in (0x01, 0x5e, 0x9c, 0xda)]
    if zlib_candidates:
        print(f"  possible zlib stream header(s) (0x78 0x01/5e/9c/da) at offsets: {zlib_candidates[:10]}")
        try:
            d = zlib.decompressobj()
            out = d.decompress(head[zlib_candidates[0]:])
            print(f"  zlib test-decompress from first candidate offset succeeded, "
                  f"produced {len(out)} bytes from {len(head)-zlib_candidates[0]} input bytes "
                  f"(partial stream, decompress may be incomplete): {out[:64]!r}")
        except zlib.error as e:
            print(f"  zlib test-decompress from first candidate offset FAILED: {e}")
    else:
        print("  no zlib stream header found in head sample")
    if size > tail_len:
        tail = read_at(path, size - tail_len, tail_len)
        print(f"  last {len(tail)} bytes:")
        print(hexdump(tail, base=size - tail_len))
    print()

def main():
    syria_path = sys.argv[1]

    print("=" * 70)
    print("PART 1 continued: Syria.rn4 full string table + record sampling")
    print("=" * 70)
    rn4_path = f"{syria_path}/roads/Syria.rn4"
    data_start = rn4_string_table(rn4_path)
    rn4_sample_records(rn4_path, data_start)
    print()

    print("=" * 70)
    print("PART 1 continued: Syria.routes header + wider float64 triple sampling")
    print("=" * 70)
    routes_path = f"{syria_path}/roads/Syria.routes"
    data_start2 = routes_header_and_data_start(routes_path)
    print(f"  (header-arithmetic offset {data_start2} is a HINT ONLY -- not trusted "
          f"without verification; see brute-force scan below)")
    best_off = routes_find_data_start_bruteforce(routes_path)
    if best_off is not None:
        print(f"  using brute-force-scored offset {best_off} for sampling below "
              f"(header-arithmetic offset {data_start2} sampled too, for comparison)")
        routes_sample_triples(routes_path, best_off)
        if best_off != data_start2:
            print(f"  --- for comparison, header-arithmetic offset {data_start2} ---")
            routes_sample_triples(routes_path, data_start2, mid_sample=False)
    else:
        print(f"  falling back to unverified header-arithmetic offset {data_start2}")
        routes_sample_triples(routes_path, data_start2)
    print()

    print("=" * 70)
    print("PART 2: terrain mesh / elevation file candidates (unread until now)")
    print("=" * 70)
    probe_unknown_file(f"{syria_path}/Scenes/Syria.scn5", "Scenes/Syria.scn5 (single monolithic per-terrain scene file)")
    probe_unknown_file(f"{syria_path}/surface/Syria.tile", "surface/Syria.tile")
    probe_unknown_file(f"{syria_path}/surface/Syria.ng5", "surface/Syria.ng5")
    probe_unknown_file(f"{syria_path}/surface/Syria.surface5", "surface/Syria.surface5")
    probe_unknown_file(f"{syria_path}/surface/Syria.onlay.sup4", "surface/Syria.onlay.sup4")
    # A normal map clipmap is derived-from-heightfield (not raw elevation),
    # but worth a quick look for comparison since it's the closest thing to
    # "terrain shape" data in clipmaps/.
    import glob
    normalmap_samples = sorted(glob.glob(f"{syria_path}/clipmaps/normalmap/**/*.tif.clipmap", recursive=True))[:1]
    for p in normalmap_samples:
        probe_unknown_file(p, "clipmaps/normalmap sample (derived slope data, NOT raw elevation)")

if __name__ == "__main__":
    main()
PYEOF

python3 "$py" "$syria_path" > "$out_file" 2>&1
rm -f "$py"

echo "Wrote $out_file"
