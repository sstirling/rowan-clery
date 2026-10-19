"""Geometry and text-fit audit of a generated .pptx, as a stand-in for eyeballing.

No renderer is available on this machine, so this reads the shapes back out of the
file and checks the things a visual pass is actually for:

  1. anything off the slide, or inside the 0.5" margin
  2. overlapping text-bearing shapes
  3. text estimated to overflow its own box
  4. titles that drift between slides sharing a layout

Text fit is an ESTIMATE. Average glyph width is approximated per font family, so treat
flagged items as "look at this", not as proof. Courier New is monospace at exactly
0.6em, so its estimates are tight; Calibri and Cambria are averages.
"""
import collections
import math
import sys
from pptx import Presentation
from pptx.util import Emu

EMU = 914400.0
SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN = 0.5

# Average advance width as a fraction of font size.
WIDTH = {"Courier New": 0.600, "Cambria": 0.478, "Calibri": 0.472,
         "Georgia": 0.510, "Arial": 0.500, None: 0.500}
LINE = 1.22  # line height as a multiple of font size


def inches(v):
    return (v or 0) / EMU


def est_text_height(shape):
    """Estimated rendered height of a shape's text, in inches."""
    tf = shape.text_frame
    box_w = inches(shape.width)
    if box_w <= 0:
        return 0.0
    total = 0.0
    for para in tf.paragraphs:
        runs = para.runs
        if not runs:
            total += 0.14
            continue
        size = max((r.font.size.pt if r.font.size else 18) for r in runs)
        face = next((r.font.name for r in runs if r.font.name), None)
        wpc = WIDTH.get(face, WIDTH[None])
        # pptxgenjs text boxes carry 0.05" internal padding each side unless margin:0;
        # assume the tighter case so this does not cry wolf.
        usable = max(box_w - 0.04, 0.4)
        chars_per_line = max(int(usable * 72 / (size * wpc)), 1)
        text = "".join(r.text for r in runs)
        lines = 0
        for seg in text.split("\n"):
            lines += max(1, math.ceil(len(seg) / chars_per_line))
        total += lines * size * LINE / 72
    return total


def rects_overlap(a, b, pad=0.0):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw - pad and bx < ax + aw - pad and
            ay < by + bh - pad and by < ay + ah - pad)


def main(path):
    prs = Presentation(path)
    problems = collections.defaultdict(list)
    titles = collections.defaultdict(list)

    for idx, slide in enumerate(prs.slides, start=1):
        layout = slide.slide_layout.name
        boxes = []
        for sh in slide.shapes:
            x, y = inches(sh.left), inches(sh.top)
            w, h = inches(sh.width), inches(sh.height)
            name = sh.name or sh.shape_type
            if x < -0.01 or y < -0.01 or x + w > SLIDE_W + 0.01 or y + h > SLIDE_H + 0.01:
                problems[idx].append(
                    f"OFF-SLIDE  {name}: x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}")
            elif x < MARGIN - 0.01 or y < MARGIN - 0.01 \
                    or x + w > SLIDE_W - MARGIN + 0.01 or y + h > SLIDE_H - MARGIN + 0.01:
                # The footer and slide number deliberately sit low; ignore those.
                if not (y > 6.8 and h < 0.45):
                    problems[idx].append(
                        f"TIGHT MARGIN  {name}: x={x:.2f} y={y:.2f} "
                        f"right={x+w:.2f} bottom={y+h:.2f}")
            if not sh.has_text_frame or not sh.text_frame.text.strip():
                continue
            need = est_text_height(sh)
            if need > h * 1.06 + 0.02:
                problems[idx].append(
                    f"TEXT OVERFLOW?  {name}: needs ~{need:.2f}\" in {h:.2f}\" "
                    f"({sh.text_frame.text.strip()[:48]!r})")
            boxes.append(((x, y, w, h), name))
            if "title" in (sh.name or "").lower():
                titles[layout].append((idx, round(x, 2), round(y, 2), round(h, 2)))

        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                (ra, na), (rb, nb) = boxes[i], boxes[j]
                # Chips, badges and stat pairs are intentionally stacked on their own
                # backing shape; only flag text-on-text collisions.
                if rects_overlap(ra, rb, pad=0.06):
                    problems[idx].append(f"OVERLAP  {na}  x  {nb}")

    print(f"{path}: {len(prs.slides)} slides\n")
    if problems:
        for idx in sorted(problems):
            print(f"--- slide {idx} ---")
            for p in problems[idx]:
                print(f"    {p}")
    else:
        print("no geometry problems found")

    print("\n--- title consistency by layout ---")
    for layout, rows in sorted(titles.items()):
        pos = {(x, y, h) for _, x, y, h in rows}
        flag = "" if len(pos) == 1 else "   <-- DRIFT"
        print(f"  {layout:<20} {len(rows):>2} slides, {len(pos)} distinct position(s){flag}")
        if len(pos) > 1:
            for r in rows:
                print(f"      slide {r[0]}: x={r[1]} y={r[2]} h={r[3]}")


if __name__ == "__main__":
    main(sys.argv[1])
