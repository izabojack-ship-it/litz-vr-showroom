"""360° 環景接縫修復 v2：幾何對齊優先，牆面零融合。

方法（不同於 GraphCut 貼回）：
  1. 在色帶區以相位相關 + 梯度掃描，偵測最佳垂直位移
  2. 僅對左半邊界做垂直重採樣（align_seam），讓弧形線條連續
  3. 全幅色調匹配，消除亮度差
  4. 僅地面區（水平線以下）做窄帶亮度混合；牆面／色帶完全不糊化
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\高將機械\machine-ai-upscale\output")
PANOS = ROOT / "media" / "panoramas"
THUMBS = ROOT / "media" / "thumbs"
ZONES_JSON = ROOT / "js" / "zones.json"
JPEG_QUALITY = 98

# 載入既有接縫工具
_spec = importlib.util.spec_from_file_location(
    "restore", ROOT / "scripts" / "restore-panorama-seams.py"
)
_restore = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_restore)


def imread_unicode(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return img


def imwrite_unicode(path: Path, image: np.ndarray, *, quality: int = 98) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError(f"無法寫入：{path}")
    buf.tofile(str(path))


def _zone(zone_id: str) -> dict:
    zones = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    for z in zones:
        if z["id"] == zone_id:
            return z
    raise SystemExit(f"找不到展區：{zone_id}")


def _resolve_source(zone: dict, source_dir: Path | None) -> Path:
    base = source_dir or SOURCE
    for p in (base / zone["file"], PANOS / zone["file"], ROOT / zone["file"]):
        if p.exists():
            return p
    raise SystemExit(f"找不到來源：{zone['file']}")


def detect_shift_gradient(
    arr: np.ndarray,
    *,
    band_top: float = 0.08,
    band_bottom: float = 0.52,
    strip: int = 600,
    search: int = 24,
) -> int:
    """梯度匹配：在色帶區掃描垂直位移，找左右邊界最吻合的整數像素值。"""
    h, w = arr.shape[:2]
    y0, y1 = int(h * band_top), int(h * band_bottom)
    left = _restore._luminance(arr[y0:y1, :strip])
    right = _restore._luminance(arr[y0:y1, w - strip :])
    span = y1 - y0
    best_s, best = 0, 1e18
    for s in range(-search, search + 1):
        if s >= 0:
            diff = np.abs(left[s:] - right[: span - s])
        else:
            ss = -s
            diff = np.abs(left[: span - ss] - right[ss:])
        score = float(np.mean(diff))
        if score < best:
            best, best_s = score, s
    return best_s


def _score_shift(arr: np.ndarray, shift: int, *, strip: int = 600) -> float:
    """評估位移後左右邊界吻合度（愈低愈好）。"""
    h, w = arr.shape[:2]
    y0, y1 = int(h * _restore.SEAM_BAND_TOP), int(h * _restore.SEAM_BAND_BOTTOM)
    test = _restore.align_seam_left_down(arr.astype(np.float32), shift)
    left = _restore._luminance(test[y0:y1, :strip])
    right = _restore._luminance(test[y0:y1, w - strip :])
    span = y1 - y0
    if shift >= 0:
        diff = np.abs(left[shift:] - right[: span - shift])
    else:
        ss = -shift
        diff = np.abs(left[: span - ss] - right[ss:])
    return float(np.mean(diff))


def choose_best_shift(arr: np.ndarray, hint: int | None = None) -> int:
    """綜合梯度掃描與 restore 偵測，選擇邊界誤差最小的位移。"""
    candidates = {
        detect_shift_gradient(arr),
        _restore.detect_seam_left_down_shift(arr),
    }
    if hint is not None:
        candidates.add(hint)

    best_s, best_score = 0, 1e18
    for s in candidates:
        for ds in (0, -2, -1, 1, 2):
            trial = int(np.clip(s + ds, -24, 24))
            sc = _score_shift(arr, trial)
            if sc < best_score - 0.05:
                best_score, best_s = sc, trial
            elif abs(sc - best_score) <= 0.05 and abs(trial) < abs(best_s):
                # 分數接近時偏好較小位移，避免過度扭曲色帶
                best_score, best_s = sc, trial
    return best_s


def blend_floor_only(
    arr: np.ndarray,
    *,
    floor_start: float = 0.55,
    blend_cols: int = 48,
) -> np.ndarray:
    """僅在地面區對左右邊界做窄帶亮度混合（牆面完全不動）。"""
    out = arr.copy()
    h, w = out.shape[:2]
    y0 = int(h * floor_start)
    wd = min(blend_cols, max(16, w // 200))

    for i in range(wd):
        t = i / max(wd - 1, 1)
        wgt = 0.5 * (1.0 + np.cos(np.pi * t))  # 中央權重大、邊緣小
        lc = out[y0:, i].astype(np.float64)
        rc = out[y0:, w - 1 - i].astype(np.float64)
        mean = (lc + rc) * 0.5
        out[y0:, i] = (lc * (1 - wgt) + mean * wgt).astype(np.float32)
        out[y0:, w - 1 - i] = (rc * (1 - wgt) + mean * wgt).astype(np.float32)
    return out


def repair(
    arr: np.ndarray,
    *,
    shift_override: int | None = None,
    floor_blend: bool = True,
) -> tuple[np.ndarray, int]:
    """v2 接縫修復主流程。"""
    # 1. 偵測最佳垂直位移（限制 ±24px，避免過度扭曲）
    if shift_override is not None:
        shift = int(np.clip(shift_override, -24, 24))
    else:
        shift = choose_best_shift(arr)
    print(f"[detect] best shift = {shift}px  (score={_score_shift(arr, shift):.2f})")

    f = arr.astype(np.float32)

    # 2. 幾何對齊（色帶區垂直位移，地面漸退為 0）
    if shift != 0:
        f = _restore.align_seam_left_down(f, shift)

    # 3. 色調匹配（寬過渡、不糊化）
    f = _restore.tone_match(f)

    # 4. 僅地面窄帶混合；牆面／色帶保持銳利
    if floor_blend:
        f = blend_floor_only(f)

    return np.clip(f, 0, 255).astype(np.uint8), shift


def seam_edge_score(arr: np.ndarray, *, strip: int = 400) -> float:
    """左右邊界色差（愈低愈好）。"""
    h, w = arr.shape[:2]
    l = arr[:, :strip].astype(np.float32)
    r = arr[:, w - strip :].astype(np.float32)
    return float(np.mean(np.abs(l - r)))


def process_zone(
    zone_id: str,
    *,
    source_dir: Path | None = None,
    shift: int | None = None,
) -> Path:
    zone = _zone(zone_id)
    src = _resolve_source(zone, source_dir)
    print(f"[info] 來源：{src}")

    arr = np.asarray(Image.open(src).convert("RGB"))
    before = seam_edge_score(arr)
    fixed, used_shift = repair(arr, shift_override=shift)
    after = seam_edge_score(fixed)
    print(f"[info] 邊界色差 {before:.2f} → {after:.2f}  shift={used_shift}px")

    out = PANOS / zone["file"]
    imwrite_unicode(out, cv2.cvtColor(fixed, cv2.COLOR_RGB2BGR), quality=JPEG_QUALITY)

    thumb = cv2.resize(
        cv2.cvtColor(fixed, cv2.COLOR_RGB2BGR),
        (320, 160),
        interpolation=cv2.INTER_AREA,
    )
    THUMBS.mkdir(parents=True, exist_ok=True)
    imwrite_unicode(THUMBS / zone["file"], thumb, quality=85)

    print(f"[ok] {zone_id} → {out} ({fixed.shape[1]}×{fixed.shape[0]})")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="環景接縫修復 v2（幾何對齊優先）")
    parser.add_argument("--zone", default="zone-1")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--shift", type=int, default=None, help="手動指定垂直位移（px）")
    args = parser.parse_args()
    process_zone(args.zone, source_dir=args.source, shift=args.shift)


if __name__ == "__main__":
    main()
