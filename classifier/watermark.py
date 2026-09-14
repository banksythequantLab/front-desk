#!/usr/bin/env python3
"""
Ring watermark simulator.

Since 2026-06-08 every image the Ring Partner API returns (snapshots, clips,
live video) carries a server-side watermark that cannot be removed: Ring logo
top-left, Device ID / App Name / timestamp top-right. Ring's own release notes
warn that models may need retraining to account for it.

So every frame our classifier will ever see in production is watermarked. If we
tune the classifier on clean images we are tuning on a distribution that does
not exist. This module stamps the same furniture onto local test images so the
eval set matches reality.

This is an APPROXIMATION of Ring's overlay - position and content follow the
documented layout, but exact font, opacity and pixel offsets are unverified.
Re-measure against a real watermarked snapshot once an app is registered, and
treat any accuracy delta between simulated and real as unexplained until then.

Usage:
    python watermark.py in.jpg out.jpg
    python watermark.py --batch raw_dir stamped_dir
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

DEFAULT_DEVICE_ID = "ava1.ring.device.DCV7GCLVM5FRXKNE6O7N3DHLT7ZKMT6SJAY56XAWNSV7BNKIGG3VTVB4N3X67EVKE3VO45TDZ2LRD5OZ5LJXZRCHBLNQJQ3P"
DEFAULT_APP_NAME = "Front Desk"

SHORTEN_DEVICE_ID = 24  # Ring's exact rendering is unverified; we truncate
MARGIN = 14
LINE_GAP = 3


def _font(size):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def stamp(img, device_id=DEFAULT_DEVICE_ID, app_name=DEFAULT_APP_NAME,
          when=None, opacity=205):
    """Return a copy of img with a Ring-style watermark burned in."""
    img = img.convert("RGB")
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    scale = max(11, int(h * 0.022))
    font = _font(scale)
    logo_font = _font(int(scale * 1.25))

    # --- logo, top-left -------------------------------------------------
    logo = "RING"
    lw, lh = _text_size(draw, logo, logo_font)
    pad = int(scale * 0.4)
    draw.rounded_rectangle(
        [MARGIN, MARGIN, MARGIN + lw + pad * 2, MARGIN + lh + pad * 2],
        radius=pad, fill=(10, 10, 12, 150))
    draw.text((MARGIN + pad, MARGIN + pad), logo,
              font=logo_font, fill=(255, 255, 255, opacity))

    # --- metadata, top-right --------------------------------------------
    when = when or datetime.now(timezone.utc)
    short_id = device_id[-SHORTEN_DEVICE_ID:] if len(device_id) > SHORTEN_DEVICE_ID else device_id
    lines = [short_id, app_name, when.strftime("%Y-%m-%d %H:%M:%S UTC")]

    y = MARGIN
    for line in lines:
        tw, th = _text_size(draw, line, font)
        x = w - MARGIN - tw
        # shadow first so the text survives a bright sky behind it
        draw.text((x + 1, y + 1), line, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, opacity))
        y += th + LINE_GAP

    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def main():
    ap = argparse.ArgumentParser(description="Stamp Ring-style watermarks onto images")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--batch", action="store_true", help="treat src/dst as directories")
    ap.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    ap.add_argument("--app-name", default=DEFAULT_APP_NAME)
    args = ap.parse_args()

    if not args.batch:
        stamp(Image.open(args.src), args.device_id, args.app_name).save(args.dst, quality=92)
        print(f"wrote {args.dst}")
        return

    os.makedirs(args.dst, exist_ok=True)
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    n = 0
    for name in sorted(os.listdir(args.src)):
        if os.path.splitext(name)[1].lower() not in exts:
            continue
        out = os.path.join(args.dst, os.path.splitext(name)[0] + ".jpg")
        stamp(Image.open(os.path.join(args.src, name)),
              args.device_id, args.app_name).save(out, quality=92)
        n += 1
    print(f"stamped {n} image(s) -> {args.dst}")


if __name__ == "__main__":
    sys.exit(main())
