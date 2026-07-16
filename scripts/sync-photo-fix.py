"""同步型號更名與產品圖路徑到正式站，並保留既有介紹影片。"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

PROD = "https://litz-vr-showroom.onrender.com"
PASSWORD = "LitzVR987473!x"
LOCAL_PUBLISHED = Path(r"C:\鋁台精機\content\published\machines.json")


def login() -> str:
    r = requests.post(f"{PROD}/api/auth/login", json={"password": PASSWORD}, timeout=60)
    r.raise_for_status()
    return r.json()["token"]


def wait_layout(timeout_sec: int = 600) -> None:
    print("等待 Render 部署（layout 出現 ZDC-730TCS）…")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            h = requests.get(f"{PROD}/api/health", timeout=30)
            layout = requests.get(f"{PROD}/js/machines.layout.json", timeout=30)
            if h.status_code == 200 and layout.status_code == 200:
                text = layout.text
                if "ZDC-730TCS" in text and "ZDC-730TCSA" not in text:
                    print("layout 已更新為 ZDC-730TCS")
                    return
                print("服務可用，layout 尚未更新，繼續等待…")
        except Exception as e:
            print("waiting…", e)
        time.sleep(15)
    raise TimeoutError("Render 部署逾時")


def main() -> int:
    wait_layout()
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    local = json.loads(LOCAL_PUBLISHED.read_text(encoding="utf-8"))
    remote = requests.get(f"{PROD}/api/admin/machines", headers=headers, timeout=60)
    remote.raise_for_status()
    by_id = {m["id"]: m["draft"] for m in remote.json()["machines"]}

    for mid, content in local.get("machines", {}).items():
        current = by_id.get(mid) or {}
        body = {
            "intro": content.get("intro") or current.get("intro") or "",
            "photos": content.get("photos") or current.get("photos") or [],
            "presenterVideo": current.get("presenterVideo") or "",
            "presenterVideos": current.get("presenterVideos") or {},
            "catalogUrl": content.get("catalogUrl")
            or current.get("catalogUrl")
            or "",
            "casesUrl": content.get("casesUrl") or current.get("casesUrl") or "",
            "contactUrl": content.get("contactUrl")
            or current.get("contactUrl")
            or "https://www.zitai.com/zh-tw/contact.html",
        }
        r = requests.put(
            f"{PROD}/api/admin/machines/{mid}",
            headers={**headers, "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        print(f"PUT {mid} photos={body['photos']}")

    pub = requests.post(f"{PROD}/api/admin/publish", headers=headers, timeout=120)
    pub.raise_for_status()
    print("published", pub.json())

    # verify public assets
    for path in (
        "/js/machines.layout.json",
        "/media/machines/ZDC-730TCS.jpg",
        "/media/machines/ZDC-560TCSA_thumb.jpg",
        "/media/machines/ZDC-420TCSA_thumb.jpg",
        "/media/machines/ZDC-900TCSA_thumb.jpg",
        "/css/lobby.css?v=machine97",
    ):
        r = requests.get(f"{PROD}{path}", timeout=60)
        print(f"GET {path} -> {r.status_code} ({len(r.content)} bytes)")
        if r.status_code != 200:
            return 1
    layout = requests.get(f"{PROD}/js/machines.layout.json", timeout=30).text
    assert "ZDC-730TCS" in layout and "ZDC-730TCSA" not in layout
    print("正式站驗證通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
