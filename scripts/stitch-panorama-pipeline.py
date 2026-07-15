"""360° 環景切片拼接流水線：SIFT + RANSAC Homography、GraphCut 尋縫、MultiBand 融合。

完整影像拼接管線（Image Stitching Pipeline）：
  1. SIFT 特徵匹配 + RANSAC 估計 Homography → 幾何校正與重投影
  2. GraphCutSeamFinder → 在重疊區尋找視覺影響最小的接縫路徑
  3. MultiBandBlender → 多頻段拉普拉斯金字塔融合（非線性透明度疊加）

用法：
  python scripts/stitch-panorama-pipeline.py slice_00.jpg slice_01.jpg slice_02.jpg -o output.jpg
  python scripts/stitch-panorama-pipeline.py --zone zone-1 --slices-dir path/to/slices/
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

# ── 路徑常數 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
ZONES_JSON = ROOT / "js" / "zones.json"
PANOS = ROOT / "media" / "panoramas"
THUMBS = ROOT / "media" / "thumbs"
DEFAULT_SOURCE = Path(r"C:\高將機械\machine-ai-upscale\output")

# ── 管線參數 ──────────────────────────────────────────────
WORK_MEGAPIX = 1.5       # 特徵匹配工作解析度（百萬像素）
SEAM_MEGAPIX = 0.3       # GraphCut 尋縫解析度
COMPOSE_MEGAPIX = 8.0    # 最終合成解析度上限
MATCH_CONF = 0.55        # SIFT 匹配置信度閾值
CONF_THRESH = 0.75       # 全景連通子圖閾值
BLEND_STRENGTH = 8       # 多頻段融合帶寬係數（愈大愈平滑光影過渡）
NUM_BANDS_CAP = 6        # MultiBand 最大頻段數（限制高頻模糊範圍）


# ══════════════════════════════════════════════════════════
#  工具函式
# ══════════════════════════════════════════════════════════

def imread_unicode(path: Path) -> np.ndarray:
    """讀取影像（支援 Windows 中文路徑）。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"無法讀取影像：{path}")
    return img


def imwrite_unicode(path: Path, image: np.ndarray, *, quality: int = 98) -> None:
    """寫入 JPEG（支援 Windows 中文路徑）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError(f"無法編碼影像：{path}")
    buf.tofile(str(path))


def _work_scale(h: int, w: int, megapix: float) -> float:
    """依目標百萬像素計算縮放比例。"""
    if megapix <= 0:
        return 1.0
    return min(1.0, math.sqrt(megapix * 1e6 / (h * w)))


def _create_sift() -> cv2.SIFT:
    """建立 SIFT 特徵偵測器（高精度特徵，適合結構線條匹配）。"""
    return cv2.SIFT_create(nfeatures=10000, contrastThreshold=0.03, edgeThreshold=12)


# ══════════════════════════════════════════════════════════
#  步驟 1：SIFT 特徵匹配 + RANSAC Homography
# ══════════════════════════════════════════════════════════

def extract_features(
    images: list[np.ndarray],
    finder: cv2.SIFT,
    work_scale: float,
) -> tuple[list, list[np.ndarray], list[tuple[int, int]]]:
    """在多尺度工作圖上計算 SIFT 特徵。

    回傳：(features, seam_images, full_sizes)
    """
    features = []
    seam_images = []
    full_sizes = []
    seam_scale = None

    for img in images:
        h, w = img.shape[:2]
        full_sizes.append((w, h))

        work_img = cv2.resize(
            img, None, fx=work_scale, fy=work_scale,
            interpolation=cv2.INTER_LINEAR_EXACT,
        )
        feat = cv2.detail.computeImageFeatures2(finder, work_img)
        features.append(feat)

        if seam_scale is None:
            seam_scale = _work_scale(h, w, SEAM_MEGAPIX)
        seam_img = cv2.resize(
            img, None, fx=seam_scale, fy=seam_scale,
            interpolation=cv2.INTER_LINEAR_EXACT,
        )
        seam_images.append(seam_img)

    return features, seam_images, full_sizes, seam_scale / work_scale


def match_features_ransac(
    features: list,
    match_conf: float = MATCH_CONF,
) -> object:
    """SIFT 特徵匹配 + RANSAC Homography 估計（透過 BestOf2NearestMatcher）。

    RANSAC 內建於 HomographyBasedEstimator，可剔除離群點，
    確保黃色構造線與天花板弧線的幾何對齊精度。
    """
    matcher = cv2.detail_BestOf2NearestMatcher(False, match_conf)
    pairwise = matcher.apply2(features)
    matcher.collectGarbage()
    return pairwise


def estimate_cameras(
    features: list,
    pairwise: object,
    conf_thresh: float = CONF_THRESH,
) -> tuple[list, list, list]:
    """Homography 相機姿態估計 + Bundle Adjustment 光束法平差。

    回傳：(cameras, indices, features_subset)
    """
    indices = cv2.detail.leaveBiggestComponent(features, pairwise, conf_thresh)
    if len(indices) < 2:
        raise RuntimeError("特徵匹配失敗：切片之間無法建立連通關係，請確認影像有足夠重疊區。")

    features_sub = [features[i] for i in indices]

    # Homography 幾何校正
    estimator = cv2.detail_HomographyBasedEstimator()
    ok, cameras = estimator.apply(features_sub, pairwise, None)
    if not ok:
        raise RuntimeError("Homography 幾何校正失敗：無法估計透視變換矩陣。")

    for cam in cameras:
        cam.R = cam.R.astype(np.float32)

    # Bundle Adjustment：全域優化相機姿態，消除累積誤差
    adjuster = cv2.detail_BundleAdjusterRay()
    adjuster.setConfThresh(conf_thresh)
    adjuster.setRefinementMask(np.eye(3, dtype=np.uint8))
    ok, cameras = adjuster.apply(features_sub, pairwise, cameras)
    if not ok:
        raise RuntimeError("Bundle Adjustment 失敗：相機姿態無法收斂。")

    # 水平波浪校正：消除柱狀投影扭曲
    rmats = [np.copy(cam.R) for cam in cameras]
    rmats = cv2.detail.waveCorrect(rmats, cv2.detail.WAVE_CORRECT_HORIZ)
    for idx, cam in enumerate(cameras):
        cam.R = rmats[idx]

    return cameras, indices, features_sub


# ══════════════════════════════════════════════════════════
#  步驟 2：GraphCut 尋縫
# ══════════════════════════════════════════════════════════

def find_seams_graphcut(
    seam_images: list[np.ndarray],
    cameras: list,
    seam_work_aspect: float,
    warp_type: str = "plane",
) -> tuple[list[np.ndarray], list, list, list, float]:
    """GraphCut 尋縫：在重疊區自動找視覺影響最小的拼接路徑。

    使用 COST_COLOR_GRAD 成本函數，偏好避開高梯度區域（如黃色燈帶、
    藍色弧線等複雜紋理），使接縫落在低對比度區域。
    """
    focals = sorted(cam.focal for cam in cameras)
    warped_scale = focals[len(focals) // 2]

    warper = cv2.PyRotationWarper(warp_type, warped_scale * seam_work_aspect)
    corners: list = []
    sizes: list = []
    images_warped: list[np.ndarray] = []
    masks_warped: list = []

    for idx, img in enumerate(seam_images):
        mask = 255 * np.ones(img.shape[:2], np.uint8)
        K = cameras[idx].K().astype(np.float32)
        swa = seam_work_aspect
        K[0, 0] *= swa
        K[0, 2] *= swa
        K[1, 1] *= swa
        K[1, 2] *= swa

        corner, warped = warper.warp(
            img, K, cameras[idx].R, cv2.INTER_LINEAR, cv2.BORDER_REFLECT,
        )
        _, mask_wp = warper.warp(
            mask, K, cameras[idx].R, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT,
        )
        corners.append(corner)
        sizes.append((warped.shape[1], warped.shape[0]))
        images_warped.append(warped)
        masks_warped.append(mask_wp)

    images_warped_f = [img.astype(np.float32) for img in images_warped]

    # 曝光補償：消除相機曝光差（區塊增益法）
    compensator = cv2.detail.BlocksGainCompensator()
    compensator.feed(corners, images_warped, masks_warped)

    # GraphCut 尋縫：最小割演算法找最佳接縫路徑
    seam_finder = cv2.detail.GraphCutSeamFinder("COST_COLOR_GRAD")
    masks_warped = seam_finder.find(images_warped_f, corners, masks_warped)
    masks_warped = [m.get() if hasattr(m, "get") else np.asarray(m) for m in masks_warped]

    return masks_warped, corners, sizes, images_warped, warped_scale, compensator


# ══════════════════════════════════════════════════════════
#  步驟 3：MultiBand 多頻段融合
# ══════════════════════════════════════════════════════════

def blend_multiband(
    images: list[np.ndarray],
    cameras: list,
    masks_warped: list[np.ndarray],
    indices: list[int],
    warped_scale: float,
    seam_work_aspect: float,
    compensator,
    full_sizes: list[tuple[int, int]],
    *,
    warp_type: str = "plane",
    compose_megapix: float = COMPOSE_MEGAPIX,
) -> np.ndarray:
    """MultiBand 多頻段拉普拉斯金字塔融合。

    低頻光影在寬範圍平滑過渡（消除曝光差）；
    高頻細節在極窄範圍銳利混合（保留牆面材質與構造邊緣）。
    嚴禁線性透明度疊加。
    """
    compose_scale = _work_scale(full_sizes[0][1], full_sizes[0][0], compose_megapix)
    compose_work_aspect = compose_scale / seam_work_aspect
    warped_scale_out = warped_scale * compose_work_aspect
    warper = cv2.PyRotationWarper(warp_type, warped_scale_out)

    corners: list = []
    sizes: list = []
    blender = None

    for local_idx, global_idx in enumerate(indices):
        img = images[global_idx]
        if compose_scale < 0.999:
            img = cv2.resize(
                img, None, fx=compose_scale, fy=compose_scale,
                interpolation=cv2.INTER_LINEAR_EXACT,
            )

        cam = cameras[local_idx]
        cam.focal *= compose_work_aspect
        cam.ppx *= compose_work_aspect
        cam.ppy *= compose_work_aspect

        sz = (
            int(round(full_sizes[global_idx][0] * compose_scale)),
            int(round(full_sizes[global_idx][1] * compose_scale)),
        )
        K = cam.K().astype(np.float32)
        roi = warper.warpRoi(sz, K, cam.R)
        corners.append(roi[0:2])
        sizes.append(roi[2:4])

        _, image_warped = warper.warp(
            img, K, cam.R, cv2.INTER_LINEAR, cv2.BORDER_REFLECT,
        )
        mask = 255 * np.ones(img.shape[:2], np.uint8)
        _, mask_warped = warper.warp(
            mask, K, cam.R, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT,
        )

        compensator.apply(local_idx, corners[-1], image_warped, mask_warped)
        image_warped_s = image_warped.astype(np.int16)

        # 套用 GraphCut 接縫遮罩（限制融合範圍，保留高頻銳利度）
        dilated = cv2.dilate(masks_warped[local_idx], None)
        seam_mask = cv2.resize(
            dilated,
            (mask_warped.shape[1], mask_warped.shape[0]),
            interpolation=cv2.INTER_LINEAR_EXACT,
        )
        mask_warped = cv2.bitwise_and(seam_mask, mask_warped)

        if blender is None:
            dst_sz = cv2.detail.resultRoi(corners=corners, sizes=sizes)
            blend_width = math.sqrt(dst_sz[2] * dst_sz[3]) * BLEND_STRENGTH / 100.0
            blender = cv2.detail.MultiBandBlender()
            # 限制頻段數：確保高頻細節在極窄範圍內混合
            num_bands = min(
                NUM_BANDS_CAP,
                max(1, int(math.log(max(blend_width, 2)) / math.log(2) - 1)),
            )
            blender.setNumBands(num_bands)
            blender.prepare(dst_sz)

        blender.feed(cv2.UMat(image_warped_s), mask_warped, corners[-1])

    result, _ = blender.blend(None, None)
    return cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


# ══════════════════════════════════════════════════════════
#  主流水線
# ══════════════════════════════════════════════════════════

def stitch_pipeline(
    img_paths: list[Path],
    output_path: Path,
    *,
    warp_type: str = "plane",
    compose_megapix: float = COMPOSE_MEGAPIX,
) -> np.ndarray:
    """完整影像拼接流水線：SIFT → RANSAC Homography → GraphCut → MultiBand。"""
    if len(img_paths) < 2:
        raise ValueError("至少需要兩張相鄰切片影像。")

    print(f"[1/4] 讀取 {len(img_paths)} 張切片…")
    images = [imread_unicode(p) for p in img_paths]
    h, w = images[0].shape[:2]
    work_scale = _work_scale(h, w, WORK_MEGAPIX)

    print(f"[2/4] SIFT 特徵匹配 + RANSAC Homography（工作解析度 {work_scale:.2f}x）…")
    finder = _create_sift()
    features, seam_images, full_sizes, seam_work_aspect = extract_features(
        images, finder, work_scale,
    )
    pairwise = match_features_ransac(features)
    cameras, indices, _ = estimate_cameras(features, pairwise)

    print(f"[3/4] GraphCut 尋縫（{len(indices)} 片連通）…")
    masks_warped, _, _, _, warped_scale, compensator = find_seams_graphcut(
        [seam_images[i] for i in indices],
        cameras,
        seam_work_aspect,
        warp_type=warp_type,
    )

    print(f"[4/4] MultiBand 多頻段融合（最多 {NUM_BANDS_CAP} 頻段）…")
    result = blend_multiband(
        images,
        cameras,
        masks_warped,
        indices,
        warped_scale,
        seam_work_aspect,
        compensator,
        full_sizes,
        warp_type=warp_type,
        compose_megapix=compose_megapix,
    )

    imwrite_unicode(output_path, result, quality=98)
    print(f"[ok] 輸出 → {output_path}（{result.shape[1]}×{result.shape[0]}）")
    return result


# ══════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="360° 環景切片拼接流水線（SIFT + GraphCut + MultiBand）",
    )
    parser.add_argument(
        "slices", nargs="*", type=Path,
        help="相鄰全景切片路徑（依序排列）",
    )
    parser.add_argument("-o", "--output", type=Path, default=None, help="輸出全景圖路徑")
    parser.add_argument("--zone", default=None, help="展區 id（自動填入輸出路徑）")
    parser.add_argument("--slices-dir", type=Path, default=None, help="切片目錄（*.jpg）")
    parser.add_argument(
        "--warp", default="plane",
        choices=("plane", "cylindrical", "spherical"),
        help="投影曲面（平面切片用 plane，環景實拍用 cylindrical）",
    )
    parser.add_argument(
        "--compose-megapix", type=float, default=COMPOSE_MEGAPIX,
        help=f"輸出解析度上限（百萬像素，預設 {COMPOSE_MEGAPIX}）",
    )
    args = parser.parse_args()

    # 收集切片路徑
    paths: list[Path] = list(args.slices)
    if args.slices_dir:
        paths = sorted(args.slices_dir.glob("*.jpg")) + sorted(args.slices_dir.glob("*.png"))
    if not paths:
        parser.error("請提供切片路徑或 --slices-dir。")

    # 決定輸出路徑
    output = args.output
    if output is None and args.zone:
        zone = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
        z = next((z for z in zone if z["id"] == args.zone), None)
        if z:
            output = PANOS / z["file"]
    if output is None:
        output = Path("stitched_output.jpg")

    result = stitch_pipeline(
        paths, output,
        warp_type=args.warp,
        compose_megapix=args.compose_megapix,
    )

    # 產生縮圖
    if args.zone:
        zone_data = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
        z = next((z for z in zone_data if z["id"] == args.zone), None)
        if z:
            thumb = cv2.resize(result, (320, 160), interpolation=cv2.INTER_AREA)
            THUMBS.mkdir(parents=True, exist_ok=True)
            imwrite_unicode(THUMBS / z["file"], thumb, quality=85)


if __name__ == "__main__":
    main()
