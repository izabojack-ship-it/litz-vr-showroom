"""重新以羽化模式（色調 + 地面混合）處理指定展區全景。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\高將機械\machine-ai-upscale\output")
ZONES_JSON = ROOT / "js" / "zones.json"
PANOS = ROOT / "media" / "panoramas"
THUMBS = ROOT / "media" / "thumbs"

spec = importlib.util.spec_from_file_location(
    "restore", ROOT / "scripts" / "restore-panorama-seams.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> None:
    zone_ids = sys.argv[1:] or ["zone-1", "zone-2", "zone-3", "zone-4"]
    zones = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    targets = [z for z in zones if z["id"] in zone_ids]
    if not targets:
        raise SystemExit(f"no zones matched: {zone_ids}")

    for zone in targets:
        src = SOURCE / zone["file"]
        if not src.exists():
            print(f"[skip] missing source: {src}")
            continue

        arr = np.asarray(Image.open(src).convert("RGB"))
        fixed, shift = mod.process(arr, 0)
        mod.save_jpeg(Image.fromarray(fixed), PANOS / zone["file"], quality=98)
        thumb = Image.fromarray(fixed).resize((320, 160), Image.Resampling.LANCZOS)
        mod.save_jpeg(thumb, THUMBS / zone["file"], quality=85)
        print(f"[ok] {zone['id']} {zone['file']} feather (shift {shift}px)")


if __name__ == "__main__":
    main()
