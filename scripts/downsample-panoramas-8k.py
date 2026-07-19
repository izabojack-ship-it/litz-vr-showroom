"""將啟用中的展區全景縮成 8192x4096，並可備份原 32K 檔。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
PANOS = ROOT / "media" / "panoramas"
ARCHIVE = PANOS / "_archive_32k"
TARGET = (8192, 4096)
QUALITY = 90

FILES = [
    "冷式壓鑄機第一展區.jpg",
    "冷式壓鑄機第二展區.jpg",
    "冷式壓鑄機第三展區.jpg",
    "熱式壓鑄機展區.jpg",
    "重力鑄造機展區.jpg",
]


def main() -> int:
    ARCHIVE.mkdir(exist_ok=True)
    for name in FILES:
        src = PANOS / name
        if not src.exists():
            raise SystemExit(f"missing: {src}")

        print(f"Loading {name} ({src.stat().st_size / 1e6:.1f} MB)...")
        with Image.open(src) as im:
            im = im.convert("RGB")
            print(f"  src size={im.size}")
            bak = ARCHIVE / name
            if im.size == (32000, 16000) and not bak.exists():
                print(f"  archiving 32k -> {bak.relative_to(ROOT)}")
                im.save(bak, format="JPEG", quality=95, optimize=False, subsampling=0)
            print(f"  resizing to {TARGET}...")
            out = im.resize(TARGET, Image.Resampling.LANCZOS)

        out.save(
            src,
            format="JPEG",
            quality=QUALITY,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
        out.close()
        print(f"  done -> {src.stat().st_size / 1e6:.2f} MB")

    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
