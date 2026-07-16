"""Deskew/pad cold-chamber product photos; rebuild ZDC-730TCS from source PNG."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MACHINES = ROOT / "media" / "machines"
THUMB_W = 320
TARGET_W, TARGET_H = 1600, 1043


def content_bbox(im: Image.Image, thresh: int = 248) -> tuple[int, int, int, int]:
    arr = np.asarray(im.convert("RGB"))
    mask = (arr < thresh).any(axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (0, 0, im.width, im.height)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def estimate_tilt_deg(im: Image.Image) -> float:
    arr = np.asarray(im.convert("RGB"))
    h, w, _ = arr.shape
    region = arr[h // 2 :, :, :]
    b = region[:, :, 2].astype(int)
    r = region[:, :, 0].astype(int)
    g = region[:, :, 1].astype(int)
    blue = (b > 80) & (b > r + 20) & (b > g + 10)
    xs: list[int] = []
    ys: list[int] = []
    for x in range(0, w, 6):
        col = blue[:, x]
        idx = np.where(col)[0]
        if len(idx):
            xs.append(x)
            ys.append(int(idx.min()))
    if len(xs) < 12:
        return 0.0
    slope = float(np.polyfit(np.array(xs, float), np.array(ys, float), 1)[0])
    return float(np.degrees(np.arctan(slope)))


def deskew_and_pad(im: Image.Image, rotate_deg: float | None = None) -> Image.Image:
    rgb = im.convert("RGB")
    if rotate_deg is None:
        rotate_deg = estimate_tilt_deg(rgb)
    if abs(rotate_deg) >= 1.5:
        rgb = rgb.rotate(
            rotate_deg,
            resample=Image.Resampling.BICUBIC,
            expand=True,
            fillcolor=(255, 255, 255),
        )
        print(f"  rotated {rotate_deg:.2f} deg")
    else:
        print(f"  tilt {rotate_deg:.2f} deg (skip)")

    x0, y0, x1, y1 = content_bbox(rgb)
    pad = 8
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(rgb.width, x1 + pad)
    y1 = min(rgb.height, y1 + pad)
    crop = rgb.crop((x0, y0, x1, y1))

    margin = 0.06
    max_w = int(TARGET_W * (1 - 2 * margin))
    max_h = int(TARGET_H * (1 - 2 * margin))
    scale = min(max_w / crop.width, max_h / crop.height)
    nw, nh = max(1, int(crop.width * scale)), max(1, int(crop.height * scale))
    crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (255, 255, 255))
    canvas.paste(crop, ((TARGET_W - nw) // 2, (TARGET_H - nh) // 2))
    return canvas


def save_pair(im: Image.Image, base: str) -> None:
    full = MACHINES / f"{base}.jpg"
    thumb = MACHINES / f"{base}_thumb.jpg"
    im.save(full, "JPEG", quality=90, optimize=True)
    th = max(1, int(im.height * THUMB_W / im.width))
    im.resize((THUMB_W, th), Image.Resampling.LANCZOS).save(
        thumb, "JPEG", quality=85, optimize=True
    )
    print(f"  wrote {full.name} {im.size}, {thumb.name} ({THUMB_W}, {th})")


def load_730_source() -> Image.Image:
    src = ROOT / "展間照片" / "ZDC-730TCS.png"
    im = Image.open(src)
    if im.mode in ("RGBA", "LA") or ("transparency" in im.info):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    arr = np.asarray(im).astype(np.int16)
    black = (arr[:, :, 0] < 18) & (arr[:, :, 1] < 18) & (arr[:, :, 2] < 18)
    arr[black] = 255
    return Image.fromarray(arr.astype(np.uint8))


def main() -> int:
    for base in ("ZDC-420TCSA", "ZDC-560TCSA", "ZDC-900TCSA"):
        print(f"Processing {base}")
        out = deskew_and_pad(Image.open(MACHINES / f"{base}.jpg"))
        save_pair(out, base)
        print(f"  new tilt ~{estimate_tilt_deg(out):.2f} deg")

    print("Processing ZDC-730TCS from 展間照片")
    im730 = load_730_source()
    out730 = deskew_and_pad(im730, rotate_deg=estimate_tilt_deg(im730))
    save_pair(out730, "ZDC-730TCS")

    for old in ("ZDC-730TCSA.jpg", "ZDC-730TCSA_thumb.jpg"):
        p = MACHINES / old
        if p.exists():
            p.unlink()
            print("removed", old)

    pres = ROOT / "media" / "presenter"
    oldv = pres / "ZDC-730TCSA.mp4"
    newv = pres / "ZDC-730TCS.mp4"
    if oldv.exists():
        if newv.exists():
            newv.unlink()
        oldv.rename(newv)
        print("renamed presenter video -> ZDC-730TCS.mp4")

    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
