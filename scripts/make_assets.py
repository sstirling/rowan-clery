#!/usr/bin/env python3
"""Turn the full-size source artwork into the small assets the pages inline.

    python scripts/make_assets.py            # build them all
    python scripts/make_assets.py logo       # or just one, by name

Run by hand when the artwork changes. The outputs are committed, so the daily build
never reprocesses them — it only base64-inlines the committed files.

Why this exists rather than a one-line ImageMagick call:

  * **No third-party dependency.** The whole pipeline is stdlib-only, and the daily job
    runs on an Ubuntu runner where neither Pillow nor macOS `sips` is available. So this
    decodes, resamples and re-encodes PNG by hand on top of `zlib`.

  * **Some sources key their background by flood fill from the border, not by "make white
    transparent".** RUclery.png is RGB on a near-white field, but the artwork contains its
    own near-white: the clipboard paper and the owl\'s eyes. Keying every white pixel
    punches a hole through the drawing. Filling inward from the edge only removes
    background that is actually connected to the edge.

  * **Resampling is done in premultiplied alpha.** Averaging straight RGB across the
    boundary between opaque artwork and transparent background drags the edge toward
    whatever colour the transparent pixels happen to carry, producing a pale halo.
    Premultiplying first, averaging, then dividing back out is the correct order.

Binary masks are built at full resolution and only then box-filtered down, so the
downsample is what produces the anti-aliased edge. That is cheaper and cleaner than
trying to feather a mask at full size.

Not built here: `assets/owl-callout.png`. That file is a flattened mockup — the
transparency checkerboard and a paper texture are baked into its pixels, and a raster
frame cannot stretch to fit an arbitrary paragraph. Its design is reproduced in CSS
instead (`.callout` in site/css/chrome.css), using colours sampled from it:
cream #fcf3e3, gold #fdb00d, brown #4a1b03.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys
import zlib
from collections import deque

# A pixel counts as background only if every channel is at least this bright. The source
# field is dithered around 253-255, and the lightest gold in the artwork is far below
# this, so there is a wide margin either side.
WHITE = 242

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ---- decode -------------------------------------------------------------------


def read_png(path: pathlib.Path) -> tuple[int, int, bytearray]:
    """Decode a non-interlaced 8-bit RGB or RGBA PNG to (width, height, RGBA bytes)."""
    raw = path.read_bytes()
    if raw[:8] != PNG_MAGIC:
        raise SystemExit(f"{path}: not a PNG")

    idat, meta = bytearray(), {}
    pos = 8
    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        kind = raw[pos + 4 : pos + 8]
        if kind == b"IHDR":
            keys = ("w", "h", "depth", "ctype", "comp", "filter", "interlace")
            meta = dict(zip(keys, struct.unpack(">IIBBBBB", raw[pos + 8 : pos + 8 + length])))
        elif kind == b"IDAT":
            idat += raw[pos + 8 : pos + 8 + length]
        elif kind == b"IEND":
            break
        pos += 12 + length

    if meta.get("depth") != 8 or meta.get("ctype") not in (2, 6) or meta.get("interlace"):
        raise SystemExit(
            f"{path}: need a non-interlaced 8-bit RGB/RGBA PNG, got {meta}. "
            "Re-export the logo in that form."
        )

    w, h, channels = meta["w"], meta["h"], 3 if meta["ctype"] == 2 else 4
    stride = w * channels
    buf = zlib.decompress(bytes(idat))
    expected = h * (stride + 1)
    if len(buf) != expected:
        raise SystemExit(f"{path}: decompressed to {len(buf)} bytes, expected {expected}")

    # Undo the per-scanline filters (PNG spec 9.2). Each line is prefixed with its type.
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ftype = buf[pos]
        pos += 1
        line = bytearray(buf[pos : pos + stride])
        pos += stride
        if ftype == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 255
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ftype == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                c = prev[i - channels] if i >= channels else 0
                b = prev[i]
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif ftype != 0:
            raise SystemExit(f"{path}: unknown filter type {ftype} on row {y}")
        out[y * stride : (y + 1) * stride] = line
        prev = line

    if channels == 4:
        return w, h, out
    rgba = bytearray(w * h * 4)
    for i in range(w * h):
        rgba[i * 4 : i * 4 + 3] = out[i * 3 : i * 3 + 3]
        rgba[i * 4 + 3] = 255
    return w, h, rgba


# ---- key the background -------------------------------------------------------


def clear_border_background(w: int, h: int, px: bytearray) -> int:
    """Set alpha to 0 on the near-white region connected to the image border.

    Flood fill inward from every edge pixel. Near-white that is enclosed by artwork —
    the clipboard, the eyes — is never reached, so it keeps its alpha.
    """
    def is_white(x: int, y: int) -> bool:
        i = (y * w + x) * 4
        return px[i] >= WHITE and px[i + 1] >= WHITE and px[i + 2] >= WHITE

    seen = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        if not seen[y * w + x] and is_white(x, y):
            seen[y * w + x] = 1
            queue.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while queue:
        x, y = queue.popleft()
        if x + 1 < w:
            push(x + 1, y)
        if x:
            push(x - 1, y)
        if y + 1 < h:
            push(x, y + 1)
        if y:
            push(x, y - 1)

    for i, flagged in enumerate(seen):
        if flagged:
            px[i * 4 + 3] = 0
    return sum(seen)


# ---- resample -----------------------------------------------------------------


def box_resize(w: int, h: int, px: bytearray, tw: int, th: int) -> bytearray:
    """Area-average down to tw x th, averaging in premultiplied alpha."""
    out = bytearray(tw * th * 4)
    for oy in range(th):
        y0, y1 = oy * h // th, max(oy * h // th + 1, (oy + 1) * h // th)
        for ox in range(tw):
            x0, x1 = ox * w // tw, max(ox * w // tw + 1, (ox + 1) * w // tw)
            sr = sg = sb = sa = 0
            for y in range(y0, y1):
                base = y * w * 4
                for x in range(x0, x1):
                    i = base + x * 4
                    a = px[i + 3]
                    # Premultiply: a transparent pixel must contribute no colour at all.
                    sr += px[i] * a
                    sg += px[i + 1] * a
                    sb += px[i + 2] * a
                    sa += a
            n = (y1 - y0) * (x1 - x0)
            o = (oy * tw + ox) * 4
            alpha = sa // n
            if sa:
                out[o] = min(255, sr // sa)
                out[o + 1] = min(255, sg // sa)
                out[o + 2] = min(255, sb // sa)
            out[o + 3] = alpha
    return out


# ---- encode -------------------------------------------------------------------


def _filter_row(line: bytes, prev: bytes, bpp: int) -> bytes:
    """Pick the scanline filter with the smallest sum of absolute differences.

    The heuristic the PNG spec itself recommends. On flat-colour artwork it roughly
    halves the result against storing every row unfiltered.
    """
    n = len(line)
    best = None
    for ftype in range(5):
        enc = bytearray(n)
        for i in range(n):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ftype == 0:
                v = line[i]
            elif ftype == 1:
                v = line[i] - a
            elif ftype == 2:
                v = line[i] - b
            elif ftype == 3:
                v = line[i] - ((a + b) >> 1)
            else:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                v = line[i] - (a if pa <= pb and pa <= pc else b if pb <= pc else c)
            enc[i] = v & 255
        # Signed-byte magnitude: the spec's cost estimate for a candidate filter.
        score = sum(v if v < 128 else 256 - v for v in enc)
        if best is None or score < best[0]:
            best = (score, ftype, enc)
    return bytes([best[1]]) + bytes(best[2])


def write_png(path: pathlib.Path, w: int, h: int, px: bytearray) -> None:
    stride = w * 4
    rows = bytearray()
    prev = bytes(stride)
    for y in range(h):
        line = bytes(px[y * stride : (y + 1) * stride])
        rows += _filter_row(line, prev, 4)
        prev = line

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        PNG_MAGIC
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


# ---- framing -------------------------------------------------------------------


def alpha_bbox(w: int, h: int, px: bytearray) -> tuple[int, int, int, int]:
    """The smallest box containing every pixel that is not fully transparent."""
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        row = y * w
        for x in range(w):
            if px[(row + x) * 4 + 3]:
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    if x1 < 0:
        raise SystemExit("image is entirely transparent")
    return x0, y0, x1 + 1, y1 + 1


def crop(w: int, h: int, px: bytearray, box: tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    cw, ch = x1 - x0, y1 - y0
    out = bytearray(cw * ch * 4)
    for y in range(ch):
        src = ((y + y0) * w + x0) * 4
        out[y * cw * 4:(y + 1) * cw * 4] = px[src:src + cw * 4]
    return cw, ch, out


def pad_to_square(w: int, h: int, px: bytearray):
    """Centre the artwork on a transparent square.

    A favicon is rendered into a square slot. Handing the browser a 1359x1157 image and
    letting it letterbox leaves the mark smaller than it needs to be and off-centre.
    """
    side = max(w, h)
    if side == w == h:
        return w, h, px
    out = bytearray(side * side * 4)
    ox, oy = (side - w) // 2, (side - h) // 2
    for y in range(h):
        dst = ((y + oy) * side + ox) * 4
        out[dst:dst + w * 4] = px[y * w * 4:(y + 1) * w * 4]
    return side, side, out


# ---- what gets built -------------------------------------------------------------

#: name -> (source, output, target width, key the background?, trim?, square?)
#: Widths are chosen against how each asset is actually displayed, with enough headroom
#: for a 3x screen, and no more: every page is rewritten and committed on every run, so
#: an oversized inline asset is re-stored in git twice a day, three times over.
JOBS = {
    # Masthead wordmark, displayed 34px tall.
    "logo": dict(source="RUclery.png", out="site/assets/logo.png",
                 width=144, key=True, trim=False, square=False),
    # Favicon, rendered into a square slot at 16-32px.
    "favicon": dict(source="assets/Fierce Golden-Eyed Owl Emblem.png", out="site/assets/favicon.png",
                    width=64, key=False, trim=True, square=True),
    # The owl that overhangs the left edge of a callout box, displayed ~46px.
    "emblem": dict(source="assets/Fierce Golden-Eyed Owl Emblem.png", out="site/assets/emblem.png",
                   width=120, key=False, trim=True, square=False),
    # Section rules. Wide and short, so they cost very little even at 3x.
    "divider": dict(source="assets/divider-dots.png", out="site/assets/divider-dots.png",
                    width=1000, key=False, trim=True, square=False),
    "divider-center": dict(source="assets/divider-dots-center.png",
                           out="site/assets/divider-dots-center.png",
                           width=420, key=False, trim=True, square=False),
}


def build(name: str, spec: dict, root: pathlib.Path) -> None:
    source = root / spec["source"]
    if not source.exists():
        raise SystemExit(f"{source}: not found")
    w, h, px = read_png(source)
    note = f"{w}x{h}"

    if spec["key"]:
        cleared = clear_border_background(w, h, px)
        if not cleared:
            raise SystemExit(f"{name}: nothing was keyed — is the background already transparent?")
        kept = sum(
            1 for i in range(w * h)
            if px[i * 4 + 3] and px[i * 4] >= WHITE and px[i * 4 + 1] >= WHITE and px[i * 4 + 2] >= WHITE
        )
        note += f", keyed {100 * cleared / (w * h):.0f}% background (kept {kept:,} px of white inside the art)"

    if spec["trim"]:
        box = alpha_bbox(w, h, px)
        w, h, px = crop(w, h, px, box)
        note += f", trimmed to {w}x{h}"

    if spec["square"]:
        w, h, px = pad_to_square(w, h, px)
        note += f", squared to {w}x{h}"

    tw = spec["width"]
    th = max(1, round(h * tw / w))
    small = box_resize(w, h, px, tw, th)

    out = root / spec["out"]
    write_png(out, tw, th, small)
    size = out.stat().st_size
    print(f"{name:15} {note}")
    print(f"{'':15} -> {spec['out']}  {tw}x{th}, {size / 1024:.1f} KB "
          f"(~{size * 4 // 3 / 1024:.1f} KB inlined)")

    # Re-read it to prove the file we just wrote is decodable, not just plausible.
    vw, vh, _ = read_png(out)
    assert (vw, vh) == (tw, th), f"wrote {tw}x{th} but read back {vw}x{vh}"


def main() -> int:
    root = pathlib.Path(__file__).parent.parent
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("names", nargs="*", choices=list(JOBS) + [[]],
                        help="which assets to build (default: all)")
    args = parser.parse_args()

    total = 0
    for name in (args.names or JOBS):
        build(name, JOBS[name], root)
        total += (root / JOBS[name]["out"]).stat().st_size
    print(f"\n{'total':15} {total / 1024:.1f} KB on disk, ~{total * 4 // 3 / 1024:.1f} KB inlined")
    return 0


if __name__ == "__main__":
    sys.exit(main())
