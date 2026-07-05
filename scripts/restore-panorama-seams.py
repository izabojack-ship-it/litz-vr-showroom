"""360° 環繞接縫平滑化（保留幾何與銳利度）。

重要發現：原圖左右邊界幾何本來就對齊（偏差僅約 2px），牆面與色帶跨接縫是連續的。
真正的接縫來自：
  1. 兩側亮度/色調落差
  2. 地面 AI 放大產生的水波假紋理，左右不一致

因此絕不做幾何位移（會破壞原本對齊的色帶），只做：
  1. 色調匹配（每欄加色，寬過渡，不糊化）
  2. 地面（水平線以下）寬幅混合去縫（地面平滑，混合看不出模糊）
上半牆面/色帶完全不動，保持銳利。
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\高將機械\machine-ai-upscale\output")
PANOS = ROOT / "media" / "panoramas"
THUMBS = ROOT / "media" / "thumbs"
ZONES_JSON = ROOT / "js" / "zones.json"
THUMB_SIZE = (320, 160)
JPEG_QUALITY = 98

TONE_TRANS = 2500       # 色調匹配過渡寬度（每側）
FLOOR_START = 0.55      # 地面混合起始高度（影像高度比例，水平線以下）
SEAM_FEATHER = 88       # 接縫羽化寬度（每側像素，僅最外緣）
SEAM_GAMMA = 2.2        # 線性光混合 gamma
SEAM_CHROMA_BLEND = 0.42   # 色度混合強度（低於亮度，避免洗色）
SEAM_CHROMA_RESTORE = 0.68 # 羽化後補回飽和度比例
BAND_SHIFT = 12         # 上半色帶接縫微調量（px）：左側（視角左）上移
BAND_TRANS = 1200       # 色帶微調過渡寬度（每側）
SEAM_STRIP = 160        # 自動偵測時取左右邊界寬度
SEAM_BAND_TOP = 0.08    # 色帶對齊區域（高度比例）
SEAM_BAND_BOTTOM = 0.52
SEAM_SEARCH = 120       # 自動搜尋位移範圍（±px）


def _luminance(arr: np.ndarray) -> np.ndarray:
    return 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]


def detect_seam_left_down_shift(arr: np.ndarray) -> int:
    """依接縫色帶特徵加權比對，取誤差最小的垂直位移（正=左側下移，負=左側上移）。"""
    h, w = arr.shape[:2]
    y0 = int(h * SEAM_BAND_TOP)
    y1 = int(h * SEAM_BAND_BOTTOM)
    left = _luminance(arr[y0:y1, 0]).astype(np.float32)
    right = _luminance(arr[y0:y1, w - 1]).astype(np.float32)
    gy = np.abs(np.diff(_luminance(arr[y0:y1, :3]), axis=0, prepend=0)).mean(axis=1)
    weight = gy + np.percentile(gy, 40)
    span = y1 - y0
    lo = -min(SEAM_SEARCH, h // 8)
    hi = min(SEAM_SEARCH, h // 4)
    best_score, best_shift = 1e18, 0
    for shift in range(lo, hi + 1):
        if shift >= 0:
            diff = np.abs(left[shift:] - right[: span - shift])
            wts = weight[: span - shift]
        else:
            s = -shift
            diff = np.abs(left[: span - s] - right[s:])
            wts = weight[: span - s]
        score = float(np.sum(wts * diff) / (np.sum(wts) + 1e-6))
        if score < best_score:
            best_score, best_shift = score, shift
    return best_shift


def align_seam_left_down(arr: np.ndarray, shift_px: int | None = None) -> np.ndarray:
    """接縫左側（x≈0）垂直微調：正=下移，負=上移。"""
    if shift_px is None:
        shift_px = detect_seam_left_down_shift(arr)
    if shift_px == 0:
        return arr.copy()
    out = arr.copy()
    h, w = out.shape[:2]
    t = min(max(BAND_TRANS, w // 3), w // 2)
    ar = np.arange(h)
    ye = int(h * FLOOR_START)
    yw = np.ones(h, np.float32)
    yw[ye:] = 0.0
    ramp = int(h * 0.12)
    for k in range(ramp):
        yw[ye - 1 - k] = k / ramp
    for x in range(t):
        xr = 1.0 - x / t
        s = shift_px * xr * yw
        yy = np.clip(ar - s, 0, h - 1).astype(int)
        out[:, x] = arr[:, x][yy]
    return out


def tone_match(arr: np.ndarray) -> np.ndarray:
    out = arr.copy()
    h, w = out.shape[:2]
    t = min(TONE_TRANS, w // 3)
    r0 = out[:, :30].mean(axis=(0, 1))
    l0 = out[:, w - 30:].mean(axis=(0, 1))
    mid = (r0 + l0) * 0.5
    for x in range(w - t, w):
        r = 0.5 * (1.0 + np.cos(np.pi * (w - 1 - x) / t))
        out[:, x] += (mid - l0) * r
    for x in range(0, t):
        r = 0.5 * (1.0 + np.cos(np.pi * x / t))
        out[:, x] += (mid - r0) * r
    return out


def band_align(arr: np.ndarray) -> np.ndarray:
    """僅上半色帶區小幅垂直微調，於地面以上生效並向下漸退為 0（保留地面不動）。"""
    out = arr.copy()
    h, w = out.shape[:2]
    t = min(BAND_TRANS, w // 3)
    ar = np.arange(h)
    ye = int(h * FLOOR_START)
    yw = np.ones(h, np.float32)
    yw[ye:] = 0.0
    ramp = int(h * 0.12)
    for k in range(ramp):
        yw[ye - 1 - k] = k / ramp
    for x in range(w - t, w):        # 視角左半（x 近 W）：上移
        xr = 1.0 - (w - 1 - x) / t
        yy = np.clip(ar + (BAND_SHIFT * xr) * yw, 0, h - 1)
        out[:, x] = arr[:, x][np.round(yy).astype(int)]
    for x in range(0, t):            # 視角右半（x 近 0）：下移
        xr = 1.0 - x / t
        yy = np.clip(ar - (BAND_SHIFT * xr) * yw, 0, h - 1)
        out[:, x] = arr[:, x][np.round(yy).astype(int)]
    return out


def _feather_weight(i: int, wd: int) -> float:
    t = i / max(wd - 1, 1)
    return 0.5 * (1.0 + np.cos(np.pi * t))


def _rgb_to_ycbcr(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return y, cb, cr


def _ycbcr_to_rgb(y: np.ndarray, cb: np.ndarray, cr: np.ndarray) -> np.ndarray:
    cb = cb - 128.0
    cr = cr - 128.0
    r = y + 1.402 * cr
    g = y - 0.344136 * cb - 0.714136 * cr
    b = y + 1.772 * cb
    return np.stack([r, g, b], axis=-1)


def _chroma_mag(cb: np.ndarray, cr: np.ndarray) -> np.ndarray:
    return np.hypot(cb - 128.0, cr - 128.0)


def _scale_chroma(cb: np.ndarray, cr: np.ndarray, scale: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dcb, dcr = cb - 128.0, cr - 128.0
    return 128.0 + dcb * scale, 128.0 + dcr * scale


def _chroma_aware_blend_pair(
    lc: np.ndarray, rc: np.ndarray, w: np.ndarray, *, gamma: float = SEAM_GAMMA
) -> tuple[np.ndarray, np.ndarray]:
    """亮度對齊接縫、色度輕混合，再補回飽和度避免接縫發灰。"""
    y_l, cb_l, cr_l = _rgb_to_ycbcr(lc)
    y_r, cb_r, cr_r = _rgb_to_ycbcr(rc)

    y_l_lin = np.power(np.clip(y_l / 255.0, 0.0, 1.0), gamma)
    y_r_lin = np.power(np.clip(y_r / 255.0, 0.0, 1.0), gamma)
    y_mean_lin = (y_l_lin + y_r_lin) * 0.5
    inv = 1.0 / gamma
    y_new_l = np.power(y_l_lin * (1.0 - w) + y_mean_lin * w, inv) * 255.0
    y_new_r = np.power(y_r_lin * (1.0 - w) + y_mean_lin * w, inv) * 255.0

    cw = w * SEAM_CHROMA_BLEND
    cb_mean = (cb_l + cb_r) * 0.5
    cr_mean = (cr_l + cr_r) * 0.5
    cb_new_l = cb_l * (1.0 - cw) + cb_mean * cw
    cr_new_l = cr_l * (1.0 - cw) + cr_mean * cw
    cb_new_r = cb_r * (1.0 - cw) + cb_mean * cw
    cr_new_r = cr_r * (1.0 - cw) + cr_mean * cw

    sat_l = _chroma_mag(cb_l, cr_l)
    sat_r = _chroma_mag(cb_r, cr_r)
    sat_target_l = np.maximum(sat_l, sat_r * 0.92)
    sat_target_r = np.maximum(sat_r, sat_l * 0.92)
    restore = w * SEAM_CHROMA_RESTORE

    sat_n_l = _chroma_mag(cb_new_l, cr_new_l)
    sat_n_r = _chroma_mag(cb_new_r, cr_new_r)
    scale_l = np.clip(
        (sat_n_l * (1.0 - restore) + sat_target_l * restore) / (sat_n_l + 1e-6), 1.0, 1.45
    )
    scale_r = np.clip(
        (sat_n_r * (1.0 - restore) + sat_target_r * restore) / (sat_n_r + 1e-6), 1.0, 1.45
    )
    cb_new_l, cr_new_l = _scale_chroma(cb_new_l, cr_new_l, scale_l)
    cb_new_r, cr_new_r = _scale_chroma(cb_new_r, cr_new_r, scale_r)

    nl = _ycbcr_to_rgb(y_new_l, cb_new_l, cr_new_l)
    nr = _ycbcr_to_rgb(y_new_r, cb_new_r, cr_new_r)
    return nl, nr


def seam_feather(arr: np.ndarray) -> np.ndarray:
    """接縫最外緣窄帶羽化：亮度對齊 + 色度補回，看起來像無接縫。"""
    out = arr.copy()
    h, w = out.shape[:2]
    y_floor = int(h * FLOOR_START)
    wd = min(SEAM_FEATHER, max(40, w // 180))
    for i in range(wd):
        edge = _feather_weight(i, wd)
        lc = out[:, i].astype(np.float64)
        rc = out[:, w - 1 - i].astype(np.float64)
        mismatch = np.mean(np.abs(lc - rc), axis=1) / 255.0
        boost = np.clip(mismatch * 1.8, 0.0, 0.3)
        wall_w = np.minimum(edge * 0.88 + boost[:y_floor], 1.0)
        floor_w = np.minimum(edge * 1.12 + boost[y_floor:], 1.0)
        if y_floor > 0:
            nl, nr = _chroma_aware_blend_pair(lc[:y_floor], rc[:y_floor], wall_w)
            out[:y_floor, i] = nl
            out[:y_floor, w - 1 - i] = nr
        if y_floor < h:
            nl, nr = _chroma_aware_blend_pair(lc[y_floor:], rc[y_floor:], floor_w)
            out[y_floor:, i] = nl
            out[y_floor:, w - 1 - i] = nr
    return out


def floor_blend(arr: np.ndarray) -> np.ndarray:
    return seam_feather(arr)


def process(arr: np.ndarray, shift_override: int | None = None) -> tuple[np.ndarray, int]:
    """接縫處理：色調匹配 + 接縫窄帶羽化（不做幾何位移）。"""
    f = arr.astype(np.float32)
    f = tone_match(f)
    if shift_override is not None and shift_override != 0:
        f = align_seam_left_down(f, shift_override)
        shift = shift_override
    else:
        shift = 0
    f = seam_feather(f)
    return np.clip(f, 0, 255).astype(np.uint8), shift


def atomic_write_bytes(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, path)
    except Exception:
        os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_jpeg(im: Image.Image, path: Path, *, quality: int) -> None:
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    atomic_write_bytes(path, buf.getvalue())


def main() -> None:
    zones = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    PANOS.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)

    for zone in zones:
        src = SOURCE / zone["file"]
        if not src.exists():
            print(f"[skip] missing source: {src}")
            continue

        arr = np.asarray(Image.open(src).convert("RGB"))
        shift_override = zone.get("seamShift")
        if shift_override is None:
            shift_override = 0
        fixed, shift = process(arr, shift_override)

        save_jpeg(Image.fromarray(fixed), PANOS / zone["file"], quality=JPEG_QUALITY)
        thumb = Image.fromarray(fixed).resize(THUMB_SIZE, Image.Resampling.LANCZOS)
        save_jpeg(thumb, THUMBS / zone["file"], quality=85)

        print(f"[ok] {zone['id']} {zone['file']} seam feathered (tone + floor, shift {shift}px)")


if __name__ == "__main__":
    main()
