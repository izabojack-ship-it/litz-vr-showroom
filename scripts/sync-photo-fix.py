"""?Œæ­¥?‹è??´å??‡ç”¢?å?è·¯å??°æ­£å¼ç?ï¼Œä¸¦ä¿ç??¢æ?ä»‹ç´¹å½±ç???""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

PROD = "https://litz-vr-showroom.onrender.com"
PASSWORD = "LitzVR987473!x"
LOCAL_PUBLISHED = Path(r"C:\?å°ç²¾æ?\content\published\machines.json")


def login() -> str:
    r = requests.post(f"{PROD}/api/auth/login", json={"password": PASSWORD}, timeout=60)
    r.raise_for_status()
    return r.json()["token"]


def wait_layout(timeout_sec: int = 600) -> None:
    print("ç­‰å? Render ?¨ç½²ï¼ˆCSS machine98 + ?°ç¸®?–ï???)
    deadline = time.time() + timeout_sec
    local_thumb = Path(r"C:\?å°ç²¾æ?\media\machines\ZDC-560TCSA_thumb.jpg")
    expect_size = local_thumb.stat().st_size
    while time.time() < deadline:
        try:
            css = requests.get(f"{PROD}/css/lobby.css?v=machine98", timeout=30)
            thumb = requests.get(
                f"{PROD}/media/machines/ZDC-560TCSA_thumb.jpg", timeout=30
            )
            if css.status_code == 200 and "112px" in css.text and thumb.status_code == 200:
                if abs(len(thumb.content) - expect_size) < 200:
                    print("CSS ?‡ç¸®?–å·²?´æ–°")
                    return
                print(
                    f"CSS å·²ä?ï¼Œç¸®?–å¤§å°ä?ä¸ç¬¦ï¼ˆremote={len(thumb.content)} local={expect_size}ï¼‰â€?
                )
            else:
                print("?å??¯ç”¨ï¼Œè?æºå??ªæ›´?°ï?ç¹¼ç?ç­‰å???)
        except Exception as e:
            print("waiting??, e)
        time.sleep(15)
    raise TimeoutError("Render ?¨ç½²?¾æ?")


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
        "/css/lobby.css?v=machine98",
    ):
        r = requests.get(f"{PROD}{path}", timeout=60)
        print(f"GET {path} -> {r.status_code} ({len(r.content)} bytes)")
        if r.status_code != 200:
            return 1
    layout = requests.get(f"{PROD}/js/machines.layout.json", timeout=30).text
    assert "ZDC-730TCS" in layout and "ZDC-730TCSA" not in layout
    print("æ­??ç«™é?è­‰é€šé?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
