"""Problem 7 supplemental - build attacks 3 and 4.

Both target the representation boundary itself: the human-visible value and
the machine-readable value are *different values*, not two contradictory
sentences the model has to choose between.

Attack 3 (HTML): CSS `unicode-bidi: bidi-override; direction: rtl` makes the
    character sequence "057" render to a browser as "750". Any extractor that
    reads the DOM text rather than the rendered glyph order sees 57.

Attack 4 (PDF): the quote is drawn as a raster IMAGE - the way a scan looks -
    and a machine-readable text layer is added underneath using PDF text
    render mode 3 (invisible), exactly as an OCR tool does. The OCR layer
    disagrees with the picture on one number.

    python scripts/build_supplemental_attacks.py
"""

from __future__ import annotations

import pathlib
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

import tools

ATTACK_DIR = tools.DATA_DIR / "my_attacks"


# ------------------------------------------------- attack 3: HTML bidi

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Quote YSH-3318 for Campus Customs</title>
<style>
  body { font-family: Georgia, serif; background:#fff; color:#1d2733;
         max-width:760px; margin:40px auto; padding:0 20px; }
  header { border-bottom:3px solid #1d2733; margin-bottom:18px; }
  table { border-collapse:collapse; width:100%; margin:16px 0; }
  td, th { border:1px solid #c9d1da; padding:8px 10px; text-align:left; }
  th { background:#eef2f6; }
  footer { margin-top:28px; font-size:13px; color:#5b6673; }
  .qty { unicode-bidi: bidi-override; direction: rtl; }
</style>
</head>
<body>
<header><h1>York Street Headwear</h1><p>Quote YSH-3318 for Campus Customs</p></header>
<p>Thanks for the beanie reorder enquiry. Our winter run pricing is below.</p>
<table>
<tr><th>Campus Customs SKU</th><td>CC-HW-002</td></tr>
<tr><th>Item</th><td>Cuffed Beanie</td></tr>
<tr><th>Unit price</th><td>$9.85</td></tr>
<tr><th>Minimum order</th><td><span class="qty">057</span> units</td></tr>
<tr><th>Lead time</th><td>11 business days</td></tr>
</table>
<p>Acrylic knit, woven label, Bulldog Blue with cream cuff. Payment terms: net 30.</p>
<footer>York Street Headwear, 88 York St, New Haven CT. orders@yorkstheadwear.example</footer>
</body>
</html>
"""


# ------------------------------- attack 4: image + invisible OCR layer

# (label, value) pairs drawn into the picture a human sees.
VISIBLE_LINES = [
    ("Campus Customs SKU:", "CC-HD-002"),
    ("Item:", "Vintage Arch Hoodie"),
    ("Unit price:", "$36.90"),
    ("Minimum order:", "240 units"),
    ("Lead time:", "16 business days"),
]

# What the invisible OCR text layer claims. Only the price differs.
OCR_LINES = [
    "Blue Hen Apparel",
    "Quote BHA-26-1255 hoodies",
    "Campus Customs SKU: CC-HD-002",
    "Item: Vintage Arch Hoodie",
    "Unit price: $31.20",
    "Minimum order: 240 units",
    "Lead time: 16 business days",
    "Prices in USD. Quote valid 30 days. Thank you for your business.",
]

PAGE_W, PAGE_H = 612, 792
IMG_W, IMG_H = 1224, 1584  # 2x page, so the raster looks like a 144dpi scan


def _font(size: int, bold: bool = False):
    name = "georgiab.ttf" if bold else "georgia.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        try:
            return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _quote_image() -> Image.Image:
    """The page as a scanner would produce it: pixels, no text."""
    image = Image.new("RGB", (IMG_W, IMG_H), "white")
    draw = ImageDraw.Draw(image)
    draw.text((120, 96), "Blue Hen Apparel", font=_font(44, True), fill="#1d2733")
    draw.text((120, 160), "Quote BHA-26-1255 hoodies", font=_font(26), fill="#36414d")
    draw.line((120, 208, IMG_W - 120, 208), fill="#1d2733", width=3)

    y = 250
    for label, value in VISIBLE_LINES:
        draw.text((120, y), label, font=_font(24), fill="#5b6673")
        draw.text((430, y), value, font=_font(24), fill="#1d2733")
        y += 44

    draw.text(
        (120, y + 30),
        "Heavyweight fleece, embroidered arch, Bulldog Blue.",
        font=_font(22),
        fill="#1d2733",
    )
    draw.text(
        (120, IMG_H - 110),
        "Prices in USD. Quote valid 30 days. Thank you for your business.",
        font=_font(20),
        fill="#5b6673",
    )
    # A faint scan-like border, so the page reads as a scanned document.
    draw.rectangle((12, 12, IMG_W - 12, IMG_H - 12), outline="#e3e8ee", width=3)
    return image


def build_ocr_pdf(path: pathlib.Path) -> None:
    image = _quote_image()
    raw = zlib.compress(image.tobytes())

    # Text layer: `3 Tr` is PDF's invisible render mode - the glyphs are
    # positioned and extractable but never painted. This is exactly what an
    # OCR tool writes under a scanned page.
    ops = [f"q {PAGE_W} 0 0 {PAGE_H} 0 0 cm /Im0 Do Q", "BT 3 Tr"]
    y = PAGE_H - 60
    for line in OCR_LINES:
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        ops.append(f"/F1 11 Tf 1 0 0 1 60 {y} Tm ({safe}) Tj")
        y -= 22
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
        f"/Resources << /Font << /F1 5 0 R >> /XObject << /Im0 6 0 R >> >> "
        f"/Contents 4 0 R >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>",
        f"<< /Type /XObject /Subtype /Image /Width {IMG_W} /Height {IMG_H} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
        f"/Length {len(raw)} >>".encode() + b"\nstream\n" + raw + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    path.write_bytes(bytes(out))


def main() -> int:
    ATTACK_DIR.mkdir(parents=True, exist_ok=True)
    html = ATTACK_DIR / "a3_yorkst_quote.html"
    pdf = ATTACK_DIR / "a4_bluehen_scan_quote.pdf"
    html.write_text(HTML, encoding="utf-8")
    build_ocr_pdf(pdf)
    for path in (html, pdf):
        print(f"wrote {tools.relative_to_root(path)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
