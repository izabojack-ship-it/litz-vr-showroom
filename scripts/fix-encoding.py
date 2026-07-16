"""Restore UTF-8 corrupted index.html / lobby.js and bump cache versions."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOOD_REV = "5a463b1"


def restore(rel: str) -> str:
    data = subprocess.check_output(["git", "show", f"{GOOD_REV}:{rel}"], cwd=ROOT)
    text = data.decode("utf-8")
    if "鋁台精機" not in text and rel.endswith(".html"):
        raise SystemExit(f"{rel} from {GOOD_REV} missing brand text")
    (ROOT / rel).write_bytes(data)
    print(f"restored {rel} ({len(data)} bytes)")
    return text


def main() -> int:
    restore("index.html")
    restore("js/lobby.js")

    idx = ROOT / "index.html"
    t = idx.read_text(encoding="utf-8")
    t = (
        t.replace("machine97", "machine99")
        .replace("machine98", "machine99")
        .replace("hall250716c", "hall250716e")
        .replace("hall250716d", "hall250716e")
        .replace("hall250716b", "hall250716e")
    )
    idx.write_text(t, encoding="utf-8", newline="\n")
    print("title:", t.split("<title>")[1].split("</title>")[0])

    lobby = ROOT / "js" / "lobby.js"
    lt = lobby.read_text(encoding="utf-8")
    lt = lt.replace(
        "const MEDIA_VERSION = 'hall250716c';",
        "const MEDIA_VERSION = 'hall250716e';",
    )
    lobby.write_text(lt, encoding="utf-8", newline="\n")
    print("MEDIA_VERSION line:", next(l for l in lt.splitlines() if "MEDIA_VERSION =" in l))

    # sanity
    assert "鋁台精機" in idx.read_text(encoding="utf-8")
    lobby.read_text(encoding="utf-8")
    print("UTF-8 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
