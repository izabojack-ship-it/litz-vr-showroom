"""扶正並緊裁冷室產品圖：單次適度旋轉（避免透視誤判），機台填滿畫面。"""
from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MACHINES = ROOT / "media" / "machines"
ORIG_COMMIT = "91085b5"
THUMB_W = 480
TARGET_W = 1600
MARGIN = 0.02
# 產品照多為 3/4 透視，底座線本來就不水平；只修正真實相機傾斜
MAX_CORRECT_DEG = 4.0
MIN_CORRECT_DEG = 0.8


def content_bbox(im: Image.Image, thresh: int = 246) -> tuple[int, int, int, int]:
    arr = np.asarray(im.convert("RGB"))
    mask = (arr < thresh).any(axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (0, 0, im.width, im.height)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def estimate_tilt_deg(im: Image.Image) -> float:
    arr = np.asarray(im.convert("RGB"))
    h, w, _ = arr.shape
    y0, y1 = int(h * 0.40), int(h * 0.90)
    region = arr[y0:y1, :, :]
    b = region[:, :, 2].astype(int)
    r = region[:, :, 0].astype(int)
    g = region[:, :, 1].astype(int)
    blue = (b > 70) & (b > r + 15) & (b > g + 8) & (b < 200)

    xs: list[float] = []
    ys: list[float] = []
    for x in range(int(w * 0.12), int(w * 0.88), 5):
        idx = np.where(blue[:, x])[0]
        if len(idx) < 4:
            continue
        xs.append(float(x))
        ys.append(float(y0 + int(idx.min())))
    if len(xs) < 18:
        return 0.0

    xs_a = np.array(xs)
    ys_a = np.array(ys)
    slope0 = float(np.polyfit(xs_a, ys_a, 1)[0])
    pred = slope0 * xs_a + (ys_a.mean() - slope0 * xs_a.mean())
    resid = np.abs(ys_a - pred)
    keep = resid <= max(5.0, float(np.median(resid)) * 2.2)
    if int(keep.sum()) < 14:
        keep = np.ones_like(keep, dtype=bool)
    slope = float(np.polyfit(xs_a[keep], ys_a[keep], 1)[0])
    return float(np.degrees(np.arctan(slope)))


def level_once(im: Image.Image) -> Image.Image:
    """只做一次有限角度扶正，避免把透視線硬掰成水平。"""
    rgb = im.convert("RGB")
    tilt = estimate_tilt_deg(rgb)
    # 透視造成的斜率通常 > 相機傾斜；取較保守值
    correct = float(np.clip(tilt, -MAX_CORRECT_DEG, MAX_CORRECT_DEG))
    if abs(correct) < MIN_CORRECT_DEG:
        print(f"  tilt {tilt:+.2f} deg (skip / too small)")
        return rgb
    print(f"  tilt {tilt:+.2f} deg -> rotate {correct:+.2f} deg")
    return rgb.rotate(
        correct,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(255, 255, 255),
    )


def tight_pad(im: Image.Image) -> Image.Image:
    rgb = im.convert("RGB")
    x0, y0, x1, y1 = content_bbox(rgb)
    pad = 6
    crop = rgb.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(rgb.width, x1 + pad),
            min(rgb.height, y1 + pad),
        )
    )
    cw, ch = crop.size
    target_h = int(round(TARGET_W * ch / max(cw, 1)))
    target_h = max(860, min(980, target_h))

    max_w = int(TARGET_W * (1 - 2 * MARGIN))
    max_h = int(target_h * (1 - 2 * MARGIN))
    scale = min(max_w / cw, max_h / ch)
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (TARGET_W, target_h), (255, 255, 255))
    canvas.paste(crop, ((TARGET_W - nw) // 2, (target_h - nh) // 2))
    return canvas


def save_pair(im: Image.Image, base: str) -> None:
    full = MACHINES / f"{base}.jpg"
    thumb = MACHINES / f"{base}_thumb.jpg"
    im.save(full, "JPEG", quality=90, optimize=True)
    th = max(1, int(im.height * THUMB_W / im.width))
    im.resize((THUMB_W, th), Image.Resampling.LANCZOS).save(
        thumb, "JPEG", quality=88, optimize=True
    )
    print(f"  wrote {full.name} {im.size}, thumb ({THUMB_W}x{th})")


def load_from_git(name: str) -> Image.Image:
    data = subprocess.check_output(
        ["git", "show", f"{ORIG_COMMIT}:media/machines/{name}"],
        cwd=ROOT,
    )
    return Image.open(BytesIO(data)).convert("RGB")


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


def process(base: str, source: Image.Image) -> None:
    print(f"Processing {base}")
    out = tight_pad(level_once(source))
    save_pair(out, base)


def main() -> int:
    for base in ("ZDC-420TCSA", "ZDC-560TCSA", "ZDC-900TCSA"):
        process(base, load_from_git(f"{base}.jpg"))
    process("ZDC-730TCS", load_730_source())
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
