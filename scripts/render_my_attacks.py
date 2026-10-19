"""Problem 7 - render both attack documents as a human would see them.

Attack 1 is rendered from the PDF itself with pypdfium2, so the image is the
real page a PDF viewer draws.

Attack 2 is an email, so there is no page to rasterize. The renderer below
reproduces what a mail client shows: the displayed headers, the message body
it renders, and an attachment chip for the attached file - the attachment's
*contents* are not shown, which is exactly the point of the attack.

    python scripts/render_my_attacks.py
"""

from __future__ import annotations

import email
import email.policy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

import tools

ATTACK_DIR = tools.DATA_DIR / "my_attacks"
EVIDENCE_DIR = tools.OUTPUT_DIR / "red_team_evidence"


def _font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def render_pdf(src: pathlib.Path, dst: pathlib.Path) -> None:
    doc = pdfium.PdfDocument(str(src))
    doc[0].render(scale=1.4).to_pil().save(dst)
    print(f"wrote {tools.relative_to_root(dst)}")


def render_eml(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Draw the email the way a mail client presents it."""
    message = email.message_from_bytes(src.read_bytes(), policy=email.policy.default)
    body = message.get_body(preferencelist=("html", "plain")).get_content()
    attachments = [
        part.get_filename()
        for part in message.iter_attachments()
        if part.get_filename()
    ]

    width, height = 860, 720
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    subject_font, label_font, body_font = _font(21, True), _font(14), _font(15)

    y = 28
    draw.text((36, y), message["Subject"], font=subject_font, fill="#1d2733")
    y += 38
    for name in ("From", "To", "Date"):
        if message[name]:
            draw.text((36, y), f"{name}:", font=label_font, fill="#5b6673")
            draw.text((96, y), message[name], font=label_font, fill="#1d2733")
            y += 22
    y += 10
    draw.line((36, y, width - 36, y), fill="#d7dde4", width=1)
    y += 22

    for line in body.splitlines():
        draw.text((36, y), line, font=body_font, fill="#1d2733")
        y += 21

    if attachments:
        y += 18
        draw.line((36, y, width - 36, y), fill="#d7dde4", width=1)
        y += 18
        draw.text((36, y), f"{len(attachments)} attachment", font=label_font,
                  fill="#5b6673")
        y += 24
        for name in attachments:
            draw.rounded_rectangle((36, y, 320, y + 44), radius=6,
                                   outline="#c9d1da", fill="#f4f7fa")
            draw.text((52, y + 14), f"[file]  {name}", font=label_font,
                      fill="#1d2733")
            y += 54

    image.save(dst)
    print(f"wrote {tools.relative_to_root(dst)}")


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    render_pdf(
        ATTACK_DIR / "a1_harborstitch_quote.pdf",
        EVIDENCE_DIR / "attack_1_rendered.png",
    )
    render_eml(
        ATTACK_DIR / "a2_eastrock_quote.eml",
        EVIDENCE_DIR / "attack_2_rendered.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
