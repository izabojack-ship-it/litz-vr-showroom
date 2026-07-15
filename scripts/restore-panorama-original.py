"""還原展區全景至原始素材品質。

參考圖效果 = AI 放大原圖直接顯示。先前切片重拼／邊緣貼回都會破壞色帶連續性。
本腳本預設直接複製原圖；可選 --tone 僅做全幅色調匹配（不位移、不貼回、不模糊牆面）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
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


def imwrite_unicode(path: Path, bgr: np.ndarray, *, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
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


def restore_zone(
    zone_id: str,
    *,
    source_dir: Path | None = None,
    tone: bool = False,
    shift: int = 0,
    quality: int = 95,
) -> Path:
    zone = _zone(zone_id)
    src = _resolve_source(zone, source_dir)
    out = PANOS / zone["file"]
    print(f"[info] 來源：{src}")

    if not tone and shift == 0:
        # 直接複製原圖位元組，零處理損失
        shutil.copy2(src, out)
        bgr = imread_unicode(out)
        print("[info] 模式：原始素材直接還原（零處理）")
    else:
        rgb = np.asarray(Image.open(src).convert("RGB"))
        f = rgb.astype(np.float32)
        if shift != 0:
            f = _restore.align_seam_left_down(f, shift)
            print(f"[info] 幾何微調 shift={shift}px")
        if tone:
            f = _restore.tone_match(f)
            print("[info] 色調匹配")
        bgr = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        imwrite_unicode(out, bgr, quality=quality)

    thumb = cv2.resize(bgr, (320, 160), interpolation=cv2.INTER_AREA)
    THUMBS.mkdir(parents=True, exist_ok=True)
    imwrite_unicode(THUMBS / zone["file"], thumb, quality=85)

    h, w = bgr.shape[:2]
    print(f"[ok] {zone_id} → {out} ({w}×{h})")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="還原展區全景至原始素材")
    parser.add_argument("--zone", default="zone-1")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--tone", action="store_true", help="僅加色調匹配（不模糊）")
    parser.add_argument("--shift", type=int, default=0, help="色帶垂直微調 px")
    parser.add_argument("--quality", type=int, default=95)
    args = parser.parse_args()
    restore_zone(
        args.zone,
        source_dir=args.source,
        tone=args.tone,
        shift=args.shift,
        quality=args.quality,
    )


if __name__ == "__main__":
    main()
