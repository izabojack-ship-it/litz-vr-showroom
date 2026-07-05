# 線上部署（Render）

展間與後台需 **Python 伺服器**（不是 GitHub Pages 靜態站）。本 repo 已含 Docker 設定，可一鍵部署到 Render，取得 HTTPS 公開網址（全球可瀏覽）。

## 一鍵部署

1. 將本 repo 推送到 GitHub（已完成後略過）
2. 開啟 [Render Dashboard](https://dashboard.render.com/)
3. **New → Blueprint**，連線 GitHub repo：`izabojack-ship-it/litz-vr-showroom`
4. Render 會讀取 `render.yaml` 建立服務
5. 在 Render 環境變數設定 **`ADMIN_PASSWORD`**（後台登入密碼，至少 8 字）
6. 部署完成後取得網址，例如：`https://litz-vr-showroom.onrender.com`

| 用途 | 網址 |
|------|------|
| VR 展間 | `https://你的網域/` |
| 管理後台 | `https://你的網域/admin/` |

## 客戶更新流程

1. 登入 `/admin/`（你設定的 `ADMIN_PASSWORD`）
2. 左側選機台 → 改文案 / 上傳照片、影片、型錄
3. **儲存草稿** → **發布至展間**
4. 訪客重新整理展間即可看到更新（manifest 不快取）

左側 **帳號設定** 可修改後台密碼（存於持久碟 `content/config/admin.json`）。

## 持久化

- `render.yaml` 已掛載 **1GB 持久碟** 於 `/data`（客戶上傳的檔案、密碼設定會保留）
- 需 **Starter 方案**（Render 免費方案無持久碟，重啟後上傳會消失）

## 本機開發

```powershell
launch.bat
```

- VR：http://127.0.0.1:8990/
- 後台：http://127.0.0.1:8990/admin/

## 自訂網域

Render 後台 → 服務 → **Settings → Custom Domains** 可綁定例如 `vr.litz.com.tw`。
