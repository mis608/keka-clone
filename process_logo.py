"""One-off: prepare EKKAA brand logo assets for the HRMS app.

- Removes the solid black background (luminance-based alpha)
- Crops to content, splits the standalone "E" mark from the wordmark lockup
- Saves: ekkaa-logo-full.png, ekkaa-mark.png (square), favicon.png
  into both static/img/ and deploy-ready/static/img/
"""
import os
from PIL import Image, ImageChops

SRC = r"C:\Users\Sunil Kumar\Downloads\new-logo.png"
ROOT = r"c:\Users\Sunil Kumar\keka-hrms-clone"
TARGETS = [
    os.path.join(ROOT, "static", "img"),
    os.path.join(ROOT, "deploy-ready", "static", "img"),
]

if not os.path.exists(SRC):
    raise SystemExit(f"ERROR: source logo not found: {SRC}")

im = Image.open(SRC).convert("RGBA")
w, h = im.size
px = im.load()
corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
print("source size:", (w, h))
print("corner pixels (r,g,b,a):", corners)

# If corners are already transparent, keep original alpha; else strip black bg
bg_transparent = all(c[3] < 10 for c in corners)
print("background already transparent:", bg_transparent)

if not bg_transparent:
    lum = im.convert("L")
    mask = lum.point(lambda v: 255 if v > 30 else 0)
    final_a = ImageChops.multiply(im.split()[3], mask)
    im.putalpha(final_a)

# Crop to visible content
bbox = im.getbbox()
print("content bbox:", bbox)
im = im.crop(bbox)
cw, ch = im.size
print("cropped size:", (cw, ch))

# Locate empty horizontal bands; the mark/wordmark gap sits mid-image
alpha = im.split()[3]
apx = alpha.load()
gaps = []
start = None
for y in range(ch):
    empty = all(apx[x, y] < 10 for x in range(0, cw, 3))
    if empty and start is None:
        start = y
    elif not empty and start is not None:
        gaps.append((start, y - 1))
        start = None
if start is not None:
    gaps.append((start, ch - 1))
big = [(a, b) for (a, b) in gaps if (b - a) >= ch * 0.02]
print("gaps:", gaps)
print("big gaps:", big)

# Mark/wordmark gap: topmost big gap starting between 35% and 70% of height
cut = None
for a, b in big:
    if ch * 0.35 <= a <= ch * 0.70:
        cut = (a + b) // 2
        break
if cut is None:
    cut = int(ch * 0.54)  # safe fallback measured from the artwork
print("cut line:", cut, f"({cut / ch:.0%} of height)")

mark = im.crop((0, 0, cw, cut))
mark = mark.crop(mark.getbbox())  # trim mark to its own box


def resize_w(img, target_w):
    r = target_w / img.width
    return img.resize((target_w, max(1, round(img.height * r))), Image.LANCZOS)


full_s = resize_w(im, 640)

# Square canvas for the mark so it centers cleanly in rounded tiles
mark_s = resize_w(mark, 256)
side = max(mark_s.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(mark_s, ((side - mark_s.width) // 2, (side - mark_s.height) // 2), mark_s)
favicon = canvas.resize((64, 64), Image.LANCZOS)

for d in TARGETS:
    os.makedirs(d, exist_ok=True)
    full_s.save(os.path.join(d, "ekkaa-logo-full.png"))
    canvas.save(os.path.join(d, "ekkaa-mark.png"))
    favicon.save(os.path.join(d, "favicon.png"))
    print("saved ->", d)

print("full:", full_s.size, "| mark:", canvas.size, "| favicon:", favicon.size)

# Sanity: sample a few opaque pixels of the mark (expect teal ~ (14,90,110) and yellow dots)
mp = mark.load()
samples = [mp[x, y] for y in range(0, mark.height, 10) for x in range(0, mark.width, 10) if mp[x, y][3] > 200]
if samples:
    avg = tuple(round(sum(c[i] for c in samples) / len(samples)) for i in range(3))
    print("avg opaque mark color (should be teal-ish):", avg, "| opaque samples:", len(samples))
print("DONE")
