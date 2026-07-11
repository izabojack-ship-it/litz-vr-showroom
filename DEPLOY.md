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

## 持久化（重要）

上傳的照片／影片必須寫入 **Disk**，否則每次重新部署都會消失。

1. Render Dashboard → 服務 `litz-vr-showroom`
2. **Disks**：確認有磁碟掛在 `/data`（Starter 方案才有持久碟；免費方案沒有）
3. **Environment** 務必設定：
   - `CONTENT_DIR` = `/data/content`
4. 儲存後 **Manual Deploy → Deploy latest commit**
5. 開啟 `/api/health`，確認：
   - `contentDir` 為 `/data/content`
   - `ephemeralStorage` 為 `false`
   - `dataMounted` 為 `true`

若 `contentDir` 仍是 `/app/content`，代表檔案寫在容器暫存區，**重新部署後上傳一定會不見**。

## 本機開發

```powershell
launch.bat
```

- VR：http://127.0.0.1:8990/
- 後台：http://127.0.0.1:8990/admin/

## 自訂網域

Render 後台 → 服務 → **Settings → Custom Domains** 可綁定例如 `vr.litz.com.tw`。
