# 鋁台展間 · VR 多站點步行導覽

參考 [台中精機 VR 展覽館](https://www.victortaichung.com/showroom/tw.html) · Photo Sphere Viewer 5

## 站點動線

| 站點 ID | 名稱 | 全景檔 |
|---------|------|--------|
| `entrance` | 入口 | `media/panoramas/entrance.jpg` |
| `hall-center` | 中央展區 | `media/panoramas/hall-center.jpg` |
| `hall-left` | 左側展區 | `media/panoramas/hall-left.jpg` |
| `hall-right` | 右側展區 | `media/panoramas/hall-right.jpg` |

- 點擊**地面光點**或底部**縮圖**切換站點
- 設定檔：`js/lobby.js` → `scenes` 陣列

## 啟動

```powershell
cd C:\鋁台精機
python -m http.server 8989
```

開啟：**http://127.0.0.1:8989/lobby-showroom/**

## 新增 / 更換站點全景（Blender / 3ds Max）

### 輸出規格（必須）

| 項目 | 規格 |
|------|------|
| 投影 | Equirectangular（等距柱狀） |
| 比例 | **2:1**（例：4096×2048 或 8192×4096） |
| 格式 | JPG 品質 ≥ 90 |
| 水平 | 360° 完整閉合 |
| 垂直 | 180°（含天頂與地面） |
| 色彩 | sRGB |

### Blender 輸出步驟

1. 相機設為 **Panoramic → Equirectangular**
2. 解析度 X = 4096、Y = 2048
3. 在每個展間位置放置相機（高度約 1.6 m）
4. 渲染輸出 JPG
5. 檔名對應站點，例如 `hall-center.jpg`
6. 放入 `media/panoramas/`，執行：

```powershell
python lobby-showroom/scripts/prepare-panoramas.py
```

或手動產生縮圖：`media/thumbs/`（320×160）

### 更新導覽點

編輯 `js/lobby.js` 中對應站點的 `links`：

```javascript
{
  id: 'link-center-left',
  target: 'hall-left',
  position: { yaw: '-58deg', pitch: '-26deg' },  // 光點在全景中的位置
  label: '左側展區',
  arrivalYaw: '40deg',  // 到達下一站時面向的角度
}
```

## 中央展區 · 機台指標與介紹面板

參考 [台中精機 VR 展覽館](https://www.victortaichung.com/showroom/tw.html)：

- **橘色圓形指標**：浮在機台上，點擊開啟右側產品介紹
- **底部機型列**：DC-900 / DC-1000 / DC-1100 快速切換
- **右側列表**：產品 360°、型錄、應用案例、聯絡我們

設定檔：`js/machines.js`（機型名稱、介紹文、指標 yaw/pitch、選單連結）

```javascript
{
  id: 'dc-1000',
  name: 'DC-1000',
  position: { yaw: '0deg', pitch: '-12deg' },  // 指標位置
  focus: { yaw: '0deg', pitch: '-5deg', zoom: 28 },  // 點擊後視角
  menu: [{ label: '產品型錄', action: 'catalog', href: 'https://...' }],
}
```

## 素材腳本

- `scripts/prepare-panoramas.py` — 整理各站 4096×2048 全景與縮圖
- `scripts/fix-panorama-seam.py` — 修復 AI 全景接縫（3D 渲染通常不需要）
