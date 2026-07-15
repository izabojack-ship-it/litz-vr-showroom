"""僅更新本機展間背景全景（鋁台展間20260715v2），不改機台設定。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(r"C:\鋁台精機")
SRC = ROOT / "展間照片" / "鋁台展間20260715v2"
PANOS = ROOT / "media" / "panoramas"
THUMBS = ROOT / "media" / "thumbs"

MAPPING = [
    ("第一", "冷式壓鑄機第一展區.jpg"),
    ("第二", "冷式壓鑄機第二展區.jpg"),
    ("第三", "冷式壓鑄機第三展區.jpg"),
    ("第四", "熱式壓鑄機展區.jpg"),
    ("第五", "重力鑄造機展區.jpg"),
]


def imread_unicode(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    return img


def imwrite_unicode(path: Path, bgr: np.ndarray, quality: int = 85) -> None:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError(f"cannot write {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    buf.tofile(str(path))


def main() -> None:
    src_files = [p for p in SRC.iterdir() if p.is_file()]
    print("sources:")
    for p in src_files:
        print(" ", repr(p.name))

    width = height = None
    for key, dst_name in MAPPING:
        matches = [
            p
            for p in src_files
            if key in p.name and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        if len(matches) != 1:
            raise SystemExit(f"expected 1 match for {key}, got {matches}")
        src = matches[0]
        dst = PANOS / dst_name
        print(f"copy {src.name} -> {dst_name}")
        shutil.copy2(src, dst)
        bgr = imread_unicode(dst)
        h, w = bgr.shape[:2]
        print(f"  size {w}x{h}")
        if width is None:
            width, height = w, h
        elif (w, h) != (width, height):
            print(f"  WARN size differs from first: {w}x{h}")
        thumb = cv2.resize(bgr, (320, 160), interpolation=cv2.INTER_AREA)
        imwrite_unicode(THUMBS / dst_name, thumb, quality=85)
        del bgr  # free memory

    assert width and height
    for zones_path in (ROOT / "js" / "zones.json", ROOT / "js" / "zones.js"):
        text = zones_path.read_text(encoding="utf-8")
        text = re.sub(r'"width":\s*\d+', f'"width": {width}', text)
        text = re.sub(r'"height":\s*\d+', f'"height": {height}', text)
        zones_path.write_text(text, encoding="utf-8")
        print(f"updated dims in {zones_path.name} -> {width}x{height}")

    # bump cache so local browser reloads backgrounds
    for path in (ROOT / "js" / "lobby.js", ROOT / "index.html"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("hall250715e", "hall250715v2").replace(
            "hall250715v2", "hall250715v2"
        )
        # if already e or other, force to v2
        text = re.sub(r"hall250715[a-z0-9]+", "hall250715v2", text)
        path.write_text(text, encoding="utf-8")
    print("MEDIA_VERSION -> hall250715v2")
    print("done (local only, no deploy)")


if __name__ == "__main__":
    main()
