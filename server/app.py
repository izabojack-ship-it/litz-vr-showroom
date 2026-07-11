"""VR 展間 API：產品內容後台 + 靜態檔案服務。"""
from __future__ import annotations

import copy
import io
import json
import os
import secrets
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from server.password import hash_password, verify_password

ROOT = Path(__file__).resolve().parents[1]
CONTENT = Path(os.environ.get("CONTENT_DIR", str(ROOT / "content")))
FILES_DIR = CONTENT / "files"
DRAFT_PATH = CONTENT / "draft" / "machines.json"
PUBLISHED_PATH = CONTENT / "published" / "machines.json"
LAYOUT_PATH = ROOT / "js" / "machines.layout.json"
ADMIN_CONFIG_PATH = CONTENT / "config" / "admin.json"
SEED_PUBLISHED_PATH = ROOT / "content" / "published" / "machines.json"

DEFAULT_ADMIN_PASSWORD = "litz-admin"
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO = {".mp4", ".webm"}
ALLOWED_PDF = {".pdf"}
THUMB_WIDTH = 320

_tokens: set[str] = set()

app = FastAPI(title="Litz VR Content API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def empty_manifest() -> dict:
    return {"version": 0, "updatedAt": utc_now(), "machines": {}}


def load_layout() -> dict:
    return load_json(LAYOUT_PATH, {"zones": {}})


def load_published() -> dict:
    return load_json(PUBLISHED_PATH, empty_manifest())


def load_draft() -> dict:
    draft = load_json(DRAFT_PATH, empty_manifest())
    published = load_published()
    if not draft.get("machines"):
        draft = copy.deepcopy(published)
        draft.setdefault("machines", {})
    return draft


def save_draft(data: dict) -> None:
    save_json(DRAFT_PATH, data)


def save_published(data: dict) -> None:
    save_json(PUBLISHED_PATH, data)


def load_admin_config() -> dict:
    return load_json(ADMIN_CONFIG_PATH, {})


def save_admin_config(data: dict) -> None:
    save_json(ADMIN_CONFIG_PATH, data)


def verify_admin_password(password: str) -> bool:
    cfg = load_admin_config()
    stored = cfg.get("passwordHash")
    if stored:
        return verify_password(password, stored)
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_pass:
        return password == env_pass
    return password == DEFAULT_ADMIN_PASSWORD


def set_admin_password(new_password: str) -> None:
    save_admin_config(
        {
            "passwordHash": hash_password(new_password),
            "updatedAt": utc_now(),
        }
    )


def init_admin_password() -> None:
    cfg = load_admin_config()
    if cfg.get("passwordHash"):
        return
    initial = os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    set_admin_password(initial)


PRESENTER_LANGS = ("zh", "en", "th")


def machine_defaults(machine_id: str) -> dict:
    return {
        "intro": "",
        "photos": [],
        "presenterVideo": "",           # 向下相容（等同 presenterVideos.zh）
        "presenterVideos": {},          # 三語真人介紹影片 {zh, en, th}
        "catalogUrl": "",
        "casesUrl": "",
        "contactUrl": "https://www.litz.com.tw/",
    }


def merge_machine_content(machine_id: str, source: dict) -> dict:
    base = machine_defaults(machine_id)
    raw = source.get("machines", {}).get(machine_id, {})
    base.update({k: v for k, v in raw.items() if v is not None})
    return base


def list_layout_machines() -> list[dict]:
    layout = load_layout()
    zones = layout.get("zones", {})
    zone_titles = {
        "zone-1": "冷式壓鑄機第一展區",
        "zone-2": "冷式壓鑄機第二展區",
        "zone-3": "熱式壓鑄機展區",
        "zone-4": "重力鑄造機展區",
        "zone-5": "第五展區",
    }
    items: list[dict] = []
    for zone_id, machines in zones.items():
        for machine in machines:
            items.append(
                {
                    "zoneId": zone_id,
                    "zoneTitle": zone_titles.get(zone_id, zone_id),
                    **machine,
                }
            )
    return items


def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登入")
    token = authorization.removeprefix("Bearer ").strip()
    if token not in _tokens:
        raise HTTPException(status_code=401, detail="登入已失效，請重新登入")


class LoginBody(BaseModel):
    password: str


class ChangePasswordBody(BaseModel):
    currentPassword: str
    newPassword: str
    confirmPassword: str


class MachineContentBody(BaseModel):
    intro: str = ""
    photos: list[dict | str] = Field(default_factory=list)
    presenterVideo: str = ""
    presenterVideos: dict[str, str] = Field(default_factory=dict)
    catalogUrl: str = ""
    casesUrl: str = ""
    contactUrl: str = ""


def make_thumb_bytes(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        w, h = im.size
        thumb_h = max(1, int(h * THUMB_WIDTH / max(w, 1)))
        im = im.resize((THUMB_WIDTH, thumb_h), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()


@app.post("/api/auth/login")
def login(body: LoginBody) -> dict:
    if not verify_admin_password(body.password):
        raise HTTPException(status_code=401, detail="密碼錯誤")
    token = secrets.token_urlsafe(32)
    _tokens.add(token)
    return {"token": token}


@app.get("/api/admin/account")
def admin_account(_: None = Depends(require_auth)) -> dict:
    cfg = load_admin_config()
    return {
        "passwordUpdatedAt": cfg.get("updatedAt"),
        "usingDefaultHint": not bool(cfg.get("passwordHash")),
    }


@app.post("/api/admin/change-password")
def admin_change_password(
    body: ChangePasswordBody,
    _: None = Depends(require_auth),
) -> dict:
    if body.newPassword != body.confirmPassword:
        raise HTTPException(status_code=400, detail="新密碼與確認密碼不一致")
    if len(body.newPassword.strip()) < 8:
        raise HTTPException(status_code=400, detail="新密碼至少 8 個字元")
    if not verify_admin_password(body.currentPassword):
        raise HTTPException(status_code=401, detail="目前密碼錯誤")
    set_admin_password(body.newPassword.strip())
    cfg = load_admin_config()
    return {"ok": True, "passwordUpdatedAt": cfg.get("updatedAt")}


@app.get("/api/auth/check")
def auth_check(_: None = Depends(require_auth)) -> dict:
    return {"ok": True}


@app.get("/api/health")
def health_check() -> dict:
    published = load_published() if PUBLISHED_PATH.exists() else {}
    return {
        "ok": True,
        "contentDir": str(CONTENT),
        "publishedVersion": published.get("version"),
        "publishedAt": published.get("updatedAt"),
        "filesDirExists": FILES_DIR.is_dir(),
    }


@app.get("/api/content/manifest")
def public_manifest() -> JSONResponse:
    data = load_published()
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/admin/machines")
def admin_list_machines(_: None = Depends(require_auth)) -> dict:
    draft = load_draft()
    published = load_published()
    machines = []
    for item in list_layout_machines():
        mid = item["id"]
        machines.append(
            {
                **item,
                "draft": merge_machine_content(mid, draft),
                "published": merge_machine_content(mid, published),
            }
        )
    return {
        "draftVersion": draft.get("version", 0),
        "publishedVersion": published.get("version", 0),
        "updatedAt": draft.get("updatedAt"),
        "machines": machines,
    }


@app.get("/api/admin/machines/{machine_id}")
def admin_get_machine(machine_id: str, _: None = Depends(require_auth)) -> dict:
    layout_item = next((m for m in list_layout_machines() if m["id"] == machine_id), None)
    if not layout_item:
        raise HTTPException(status_code=404, detail="找不到此機台")
    draft = load_draft()
    return {
        "layout": layout_item,
        "content": merge_machine_content(machine_id, draft),
    }


@app.put("/api/admin/machines/{machine_id}")
def admin_save_machine(
    machine_id: str,
    body: MachineContentBody,
    _: None = Depends(require_auth),
) -> dict:
    if not any(m["id"] == machine_id for m in list_layout_machines()):
        raise HTTPException(status_code=404, detail="找不到此機台")
    draft = load_draft()
    draft.setdefault("machines", {})
    draft["machines"][machine_id] = body.model_dump()
    draft["updatedAt"] = utc_now()
    save_draft(draft)
    return {"ok": True, "content": draft["machines"][machine_id]}


@app.post("/api/admin/machines/{machine_id}/upload")
async def admin_upload(
    machine_id: str,
    kind: str,
    lang: str = "zh",
    file: UploadFile = File(...),
    _: None = Depends(require_auth),
) -> dict:
    if not any(m["id"] == machine_id for m in list_layout_machines()):
        raise HTTPException(status_code=404, detail="找不到此機台")

    suffix = Path(file.filename or "").suffix.lower()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="檔案為空")

    rel_dir = f"{kind}/{machine_id}"
    target_dir = FILES_DIR / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]

    draft = load_draft()
    draft.setdefault("machines", {})
    content = merge_machine_content(machine_id, draft)

    if kind == "photo":
        if suffix not in ALLOWED_IMAGE:
            raise HTTPException(status_code=400, detail="照片請使用 JPG / PNG / WebP")
        full_name = f"{file_id}.jpg"
        thumb_name = f"{file_id}_thumb.jpg"
        full_path = target_dir / full_name
        thumb_path = target_dir / thumb_name

        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB")
            im.save(full_path, format="JPEG", quality=92, optimize=True)
        thumb_path.write_bytes(make_thumb_bytes(data))

        rel_full = f"{rel_dir}/{full_name}"
        rel_thumb = f"{rel_dir}/{thumb_name}"
        photos = list(content.get("photos") or [])
        photos.append({"full": rel_full, "thumb": rel_thumb})
        content["photos"] = photos

    elif kind == "presenter":
        if suffix not in ALLOWED_VIDEO:
            raise HTTPException(status_code=400, detail="影片請使用 MP4 / WebM")
        if lang not in PRESENTER_LANGS:
            raise HTTPException(status_code=400, detail="語言需為 zh / en / th")
        video_name = f"{lang}_{file_id}{suffix}"
        (target_dir / video_name).write_bytes(data)
        videos = dict(content.get("presenterVideos") or {})
        videos[lang] = f"{rel_dir}/{video_name}"
        content["presenterVideos"] = videos
        if lang == "zh":
            content["presenterVideo"] = videos[lang]  # 向下相容

    elif kind == "catalog":
        if suffix not in ALLOWED_PDF:
            raise HTTPException(status_code=400, detail="型錄請使用 PDF")
        pdf_name = f"{file_id}.pdf"
        (target_dir / pdf_name).write_bytes(data)
        content["catalogUrl"] = f"{rel_dir}/{pdf_name}"

    else:
        raise HTTPException(status_code=400, detail="不支援的上傳類型")

    draft["machines"][machine_id] = content
    draft["updatedAt"] = utc_now()
    save_draft(draft)
    return {"ok": True, "content": content}


@app.delete("/api/admin/machines/{machine_id}/photos/{index}")
def admin_delete_photo(
    machine_id: str,
    index: int,
    _: None = Depends(require_auth),
) -> dict:
    draft = load_draft()
    content = merge_machine_content(machine_id, draft)
    photos = list(content.get("photos") or [])
    if index < 0 or index >= len(photos):
        raise HTTPException(status_code=404, detail="找不到照片")
    photos.pop(index)
    content["photos"] = photos
    draft.setdefault("machines", {})
    draft["machines"][machine_id] = content
    draft["updatedAt"] = utc_now()
    save_draft(draft)
    return {"ok": True, "content": content}


@app.delete("/api/admin/machines/{machine_id}/presenter/{lang}")
def admin_delete_presenter(
    machine_id: str,
    lang: str,
    _: None = Depends(require_auth),
) -> dict:
    if lang not in PRESENTER_LANGS:
        raise HTTPException(status_code=400, detail="語言需為 zh / en / th")
    draft = load_draft()
    content = merge_machine_content(machine_id, draft)
    videos = dict(content.get("presenterVideos") or {})
    videos.pop(lang, None)
    content["presenterVideos"] = videos
    if lang == "zh":
        content["presenterVideo"] = ""
    draft.setdefault("machines", {})
    draft["machines"][machine_id] = content
    draft["updatedAt"] = utc_now()
    save_draft(draft)
    return {"ok": True, "content": content}


@app.post("/api/admin/publish")
def admin_publish(_: None = Depends(require_auth)) -> dict:
    draft = load_draft()
    published = copy.deepcopy(draft)
    published["version"] = int(published.get("version", 0)) + 1
    published["updatedAt"] = utc_now()
    save_published(published)
    save_draft(published)
    return {
        "ok": True,
        "version": published["version"],
        "updatedAt": published["updatedAt"],
    }


def seed_content_from_repo() -> None:
    """首次部署（持久碟為空）時，從 repo 內建內容初始化。"""
    PUBLISHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PUBLISHED_PATH.exists() or not SEED_PUBLISHED_PATH.exists():
        return
    shutil.copy2(SEED_PUBLISHED_PATH, PUBLISHED_PATH)


@app.on_event("startup")
def startup() -> None:
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    seed_content_from_repo()
    init_admin_password()
    if not PUBLISHED_PATH.exists():
        save_published(empty_manifest())
    draft = load_json(DRAFT_PATH, empty_manifest())
    if not draft.get("machines"):
        save_draft(copy.deepcopy(load_published()))


FILES_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "admin").mkdir(parents=True, exist_ok=True)


@app.get("/admin")
def admin_redirect() -> FileResponse:
    return FileResponse(ROOT / "admin" / "index.html")


@app.get("/")
def root_page() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/index.html")
def index_page() -> FileResponse:
    return FileResponse(ROOT / "index.html")


app.mount("/content/files", StaticFiles(directory=FILES_DIR), name="content-files")
app.mount("/content/published", StaticFiles(directory=CONTENT / "published"), name="content-published")
app.mount("/admin", StaticFiles(directory=ROOT / "admin", html=True), name="admin")
app.mount("/js", StaticFiles(directory=ROOT / "js"), name="js")
app.mount("/css", StaticFiles(directory=ROOT / "css"), name="css")
app.mount("/media", StaticFiles(directory=ROOT / "media"), name="media")
