"""把 560/420/900 扶到底座接近水平（目視可接受）。"""
from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MACHINES = ROOT / "media" / "machines"
ORIG = "91085b5"
TARGET_W = 1600
MARGIN = 0.02
THUMB_W = 480


def load_orig(name: str) -> Image.Image:
    data = subprocess.check_output(
        ["git", "show", f"{ORIG}:media/machines/{name}"], cwd=ROOT
    )
    return Image.open(BytesIO(data)).convert("RGB")


def content_bbox(im: Image.Image, thresh: int = 245):
    arr = np.asarray(im)
    mask = (arr < thresh).any(axis=2)
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def blue_foot_points(im: Image.Image):
    arr = np.asarray(im)
    x0, y0, x1, y1 = content_bbox(im)
    b = arr[:, :, 2].astype(int)
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    blue = (b > 55) & (b > r + 10) & (b > g + 4) & (b < 210)
    xs, ys = [], []
    # 取底座中段，避開最右透視端
    for x in range(x0 + int((x1 - x0) * 0.12), x0 + int((x1 - x0) * 0.62), 3):
        col = blue[y0:y1, x]
        idx = np.where(col)[0]
        if len(idx) < 4:
            continue
        xs.append(x)
        ys.append(y0 + int(idx.max()))  # 底座底緣
    return np.array(xs, float), np.array(ys, float)


def measure_deg(im: Image.Image) -> float:
    xs, ys = blue_foot_points(im)
    if len(xs) < 12:
        return 0.0
    slope = float(np.polyfit(xs, ys, 1)[0])
    return float(np.degrees(np.arctan(slope)))


def find_best_rotation(src: Image.Image) -> float:
    """搜尋使底座底緣斜率最接近 0 的角度（正=逆時針）。"""
    best_deg, best_abs = 0.0, 1e9
    for deg in np.linspace(-8, 8, 161):
        trial = src.rotate(
            float(deg),
            resample=Image.Resampling.BILINEAR,
            expand=False,
            fillcolor=(255, 255, 255),
        )
        t = measure_deg(trial)
        if abs(t) < best_abs:
            best_abs = abs(t)
            best_deg = float(deg)
    return best_deg


def tight_pad(rgb: Image.Image) -> Image.Image:
    x0, y0, x1, y1 = content_bbox(rgb)
    pad = 12
    crop = rgb.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(rgb.width, x1 + pad),
            min(rgb.height, y1 + pad),
        )
    )
    cw, ch = crop.size
    target_h = max(800, min(920, int(TARGET_W * ch / cw)))
    max_w = int(TARGET_W * (1 - 2 * MARGIN))
    max_h = int(target_h * (1 - 2 * MARGIN))
    scale = min(max_w / cw, max_h / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (TARGET_W, target_h), (255, 255, 255))
    canvas.paste(crop, ((TARGET_W - nw) // 2, (target_h - nh) // 2))
    return canvas


def save_pair(im: Image.Image, base: str) -> None:
    im.save(MACHINES / f"{base}.jpg", "JPEG", quality=92, optimize=True)
    th = max(1, int(im.height * THUMB_W / im.width))
    im.resize((THUMB_W, th), Image.Resampling.LANCZOS).save(
        MACHINES / f"{base}_thumb.jpg", "JPEG", quality=90, optimize=True
    )
    # debug overlay for local check
    dbg = im.copy()
    draw = ImageDraw.Draw(dbg)
    xs, ys = blue_foot_points(im)
    if len(xs):
        for x, y in zip(xs[::8], ys[::8]):
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 0, 0))
    dbg.save(MACHINES / f"{base}_debug.jpg", "JPEG", quality=80)


def process(base: str) -> None:
    src = load_orig(f"{base}.jpg")
    before = measure_deg(src)
    deg = find_best_rotation(src)
    rgb = src.rotate(
        deg, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(255, 255, 255)
    )
    after = measure_deg(rgb)
    out = tight_pad(rgb)
    save_pair(out, base)
    print(
        f"{base}: orig {before:+.2f}° -> rotate {deg:+.2f}° -> {after:+.2f}° "
        f"final {measure_deg(out):+.2f}° size={out.size}"
    )


def main() -> int:
    for base in ("ZDC-420TCSA", "ZDC-560TCSA", "ZDC-900TCSA"):
        process(base)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
