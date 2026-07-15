"""透過管理後台上架真人介紹影片（zh/en/th）並發布。"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8990"
PASSWORD = "litz-admin"
VIDEO_DIR = Path(r"C:\鋁台精機\真人介紹\build\video")

# 影音檔名前綴 → 機台 id
MAPPING = {
    "01_ZDC-180TCSA": "z1-right",
    "02_ZDC-250TCSA": "z1-center",
    "03_ZDC-420TCSA": "z1-left",
    "04_ZDC-560TCSA": "z2-left",
    "05_ZDC-730TCS": "z2-right",
    "06_ZDC-900TCSA": "z5-left",
    "07_ZDC-1100TCM": "z5-right",
    "08_ZHC": "hot-press-1",
    "09_PMC": "gravity-cast-1",
}

LANGS = ("zh", "en", "th")


def main() -> int:
    # 確認檔案齊全
    missing = []
    jobs: list[tuple[str, str, Path]] = []
    for prefix, machine_id in MAPPING.items():
        for lang in LANGS:
            path = VIDEO_DIR / f"{prefix}_{lang}.mp4"
            if not path.exists():
                missing.append(str(path))
            else:
                jobs.append((machine_id, lang, path))
    if missing:
        print("缺少檔案：")
        for m in missing:
            print(" ", m)
        return 1

    print(f"準備上傳 {len(jobs)} 支影片…")
    login = requests.post(f"{BASE}/api/auth/login", json={"password": PASSWORD}, timeout=30)
    if login.status_code != 200:
        print("登入失敗：", login.status_code, login.text)
        return 1
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("登入成功")

    ok = 0
    for i, (machine_id, lang, path) in enumerate(jobs, 1):
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"[{i}/{len(jobs)}] {machine_id} / {lang} ← {path.name} ({size_mb:.1f} MB)")
        with path.open("rb") as f:
            res = requests.post(
                f"{BASE}/api/admin/machines/{machine_id}/upload",
                params={"kind": "presenter", "lang": lang},
                headers=headers,
                files={"file": (path.name, f, "video/mp4")},
                timeout=300,
            )
        if res.status_code != 200:
            print("  失敗：", res.status_code, res.text[:300])
            return 1
        videos = res.json().get("content", {}).get("presenterVideos", {})
        print("  OK →", videos.get(lang, "?"))
        ok += 1

    pub = requests.post(f"{BASE}/api/admin/publish", headers=headers, timeout=60)
    if pub.status_code != 200:
        print("發布失敗：", pub.status_code, pub.text)
        return 1
    info = pub.json()
    print(f"發布完成 version={info.get('version')} at={info.get('updatedAt')} 上傳成功 {ok}/{len(jobs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
