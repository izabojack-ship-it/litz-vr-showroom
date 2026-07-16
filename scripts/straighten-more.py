"""扶正冷室產品圖：對齊 250 參考的底座傾角（約 -1.5°）。"""
from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MACHINES = ROOT / "media" / "machines"
ORIG_COMMIT = "91085b5"
MARGIN = 0.015
TARGET_W = 1600
THUMB_W = 480
# 對齊 250 參考視覺（略帶透視、底座看起來正）
TARGET_TILT = -1.5


def load_git(name: str) -> Image.Image:
    data = subprocess.check_output(
        ["git", "show", f"{ORIG_COMMIT}:media/machines/{name}"], cwd=ROOT
    )
    return Image.open(BytesIO(data)).convert("RGB")


def load_730() -> Image.Image:
    im = Image.open(ROOT / "展間照片" / "ZDC-730TCS.png")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    rgba = im.convert("RGBA")
    bg.paste(rgba, mask=rgba.split()[-1])
    arr = np.asarray(bg).astype(np.int16)
    black = (arr[:, :, 0] < 18) & (arr[:, :, 1] < 18) & (arr[:, :, 2] < 18)
    arr[black] = 255
    return Image.fromarray(arr.astype(np.uint8))


def content_bbox(im: Image.Image, thresh: int = 245) -> tuple[int, int, int, int]:
    arr = np.asarray(im)
    mask = (arr < thresh).any(axis=2)
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def blue_mask(arr: np.ndarray) -> np.ndarray:
    b = arr[:, :, 2].astype(int)
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    return (b > 60) & (b > r + 12) & (b > g + 5) & (b < 220)


def measure_tilt(im: Image.Image) -> float:
    arr = np.asarray(im.convert("RGB"))
    x0, y0, x1, y1 = content_bbox(im)
    blue = blue_mask(arr)
    w = x1 - x0

    def avg_foot(xa: int, xb: int) -> float | None:
        vals = []
        for x in range(xa, xb, 2):
            col = blue[y0:y1, x]
            idx = np.where(col)[0]
            if len(idx) < 3:
                continue
            vals.append(float(y0 + int(idx.max())))
        if len(vals) < 6:
            return None
        return float(np.median(vals))

    left = avg_foot(x0 + int(w * 0.12), x0 + int(w * 0.30))
    mid = avg_foot(x0 + int(w * 0.40), x0 + int(w * 0.58))
    if left is None or mid is None:
        return 0.0
    dx = max(40.0, (x1 - x0) * 0.28)
    return float(np.degrees(np.arctan((left - mid) / dx)))


def rotate_same_size(im: Image.Image, deg: float) -> Image.Image:
    return im.rotate(
        deg, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(255, 255, 255)
    )


def find_rotation(src: Image.Image) -> float:
    best = 0.0
    best_score = 1e9
    for deg in np.linspace(-4.0, 8.0, 121):
        trial = rotate_same_size(src, float(deg))
        t = measure_tilt(trial)
        score = abs(t - TARGET_TILT)
        if score < best_score:
            best_score = score
            best = float(deg)
    return best


def tight_pad(rgb: Image.Image) -> Image.Image:
    x0, y0, x1, y1 = content_bbox(rgb)
    pad = 10
    crop = rgb.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(rgb.width, x1 + pad),
            min(rgb.height, y1 + pad),
        )
    )
    cw, ch = crop.size
    target_h = max(780, min(900, int(TARGET_W * ch / cw)))
    max_w = int(TARGET_W * (1 - 2 * MARGIN))
    max_h = int(target_h * (1 - 2 * MARGIN))
    scale = min(max_w / cw, max_h / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (TARGET_W, target_h), (255, 255, 255))
    canvas.paste(crop, ((TARGET_W - nw) // 2, (target_h - nh) // 2))
    return canvas


def save_pair(im: Image.Image, base: str) -> None:
    im.save(MACHINES / f"{base}.jpg", "JPEG", quality=91, optimize=True)
    th = max(1, int(im.height * THUMB_W / im.width))
    im.resize((THUMB_W, th), Image.Resampling.LANCZOS).save(
        MACHINES / f"{base}_thumb.jpg", "JPEG", quality=90, optimize=True
    )


def process(base: str, src: Image.Image) -> None:
    before = measure_tilt(src)
    deg = find_rotation(src)
    rgb = rotate_same_size(src, deg)
    after_rot = measure_tilt(rgb)
    out = tight_pad(rgb)
    save_pair(out, base)
    print(
        f"{base}: {before:+.2f} -> rot {deg:+.2f} -> {after_rot:+.2f} "
        f"(final {measure_tilt(out):+.2f}) {out.size}"
    )


def main() -> int:
    ref = load_git("ZDC-250TCSA.jpg")
    print(f"REF 250 tilt={measure_tilt(ref):+.2f} (target {TARGET_TILT})")
    for base in ("ZDC-420TCSA", "ZDC-560TCSA", "ZDC-900TCSA"):
        process(base, load_git(f"{base}.jpg"))
    process("ZDC-730TCS", load_730())
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
