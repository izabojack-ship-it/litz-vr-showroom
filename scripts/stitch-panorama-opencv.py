"""360° 環景切片無縫拼接：SIFT/ORB + RANSAC Homography、GraphCut 接縫、MultiBand 融合。

適用情境：
  1. 直接讀取相鄰切片目錄（*.jpg / *.png）
  2. 由等距柱狀全景圖自動切出重疊切片後再拼接

嚴禁線性透明度疊加；融合一律使用 cv2.detail.MultiBandBlender。
"""
from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(r"C:\高將機械\machine-ai-upscale\output")
PANOS = ROOT / "media" / "panoramas"
THUMBS = ROOT / "media" / "thumbs"
ZONES_JSON = ROOT / "js" / "zones.json"

# 接縫搜尋與融合參數
WORK_MEGAPIX = 1.2       # 特徵匹配工作解析度
SEAM_MEGAPIX = 0.25      # GraphCut 接縫估計解析度
COMPOSE_MEGAPIX = 4.0    # 最終輸出解析度上限（避免記憶體爆炸）
MATCH_CONF = 0.55        # SIFT 匹配置信度
CONF_THRESH = 0.8        # 全景連通閾值
BLEND_STRENGTH = 8       # 多頻段融合帶寬係數
OVERLAP_RATIO = 0.35     # 切片重疊比例


def imread_unicode(path: Path) -> np.ndarray:
    """讀取影像（支援 Windows 中文路徑）。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return img


def imwrite_unicode(path: Path, image: np.ndarray, *, quality: int = 95) -> None:
    """寫入影像（支援 Windows 中文路徑）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    if not ok:
        raise RuntimeError(f"無法編碼影像：{path}")
    buf.tofile(str(path))


def _zone_by_id(zone_id: str) -> dict:
    zones = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    for z in zones:
        if z["id"] == zone_id:
            return z
    raise SystemExit(f"找不到展區：{zone_id}")


def _resolve_source(zone: dict, source_dir: Path | None) -> Path:
    base = source_dir or DEFAULT_SOURCE
    for candidate in (base / zone["file"], PANOS / zone["file"], ROOT / zone["file"]):
        if candidate.exists():
            return candidate
    raise SystemExit(f"找不到來源圖：{zone['file']}")


def split_equirectangular_slices(
    image: np.ndarray,
    num_slices: int = 5,
    overlap_ratio: float = OVERLAP_RATIO,
) -> list[np.ndarray]:
    """將等距柱狀全景圖切成多張相鄰、具重疊的垂直切片。"""
    h, w = image.shape[:2]
    if num_slices < 2:
        return [image]

    # 單片寬度：在無重疊條件下均分，再依重疊比例加寬
    stride = w / num_slices
    slice_w = int(round(stride * (1.0 + overlap_ratio)))
    slices: list[np.ndarray] = []

    for i in range(num_slices):
        x0 = int(round(i * stride))
        x1 = min(x0 + slice_w, w)
        crop = image[:, x0:x1].copy()
        slices.append(crop)

    return slices


def save_temp_slices(slices: list[np.ndarray], out_dir: Path) -> list[Path]:
    """將切片寫入暫存目錄，供 OpenCV 拼接管線讀取。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, sl in enumerate(slices):
        p = out_dir / f"slice_{i:02d}.jpg"
        imwrite_unicode(p, sl, quality=95)
        paths.append(p)
    return paths


def _work_scale(shape: tuple[int, int], megapix: float) -> float:
    h, w = shape
    if megapix <= 0:
        return 1.0
    return min(1.0, math.sqrt(megapix * 1e6 / (h * w)))


def _create_feature_finder(method: str = "sift"):
    """建立特徵偵測器（優先 SIFT，備援 ORB）。"""
    if method == "sift":
        try:
            return cv2.SIFT_create(nfeatures=8000)
        except AttributeError:
            pass
    return cv2.ORB_create(nfeatures=8000)


def _detect_and_match_homography(
    img_a: np.ndarray,
    img_b: np.ndarray,
    finder,
) -> np.ndarray | None:
    """以 SIFT/ORB 特徵 + RANSAC 估計 img_b → img_a 的 Homography。"""
    gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
    kp_a, des_a = finder.detectAndCompute(gray_a, None)
    kp_b, des_b = finder.detectAndCompute(gray_b, None)
    if des_a is None or des_b is None or len(kp_a) < 4 or len(kp_b) < 4:
        return None

    if isinstance(finder, cv2.ORB):
        norm = cv2.NORM_HAMMING
        cross_check = True
    else:
        norm = cv2.NORM_L2
        cross_check = False

    matcher = cv2.BFMatcher(norm, crossCheck=cross_check)
    if cross_check:
        matches = matcher.match(des_a, des_b)
        matches = sorted(matches, key=lambda m: m.distance)[:500]
    else:
        pairs = matcher.knnMatch(des_a, des_b, k=2)
        matches = [m for m, n in pairs if m.distance < 0.75 * n.distance]

    if len(matches) < 8:
        return None

    pts_a = np.float32([kp_a[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    pts_b = np.float32([kp_b[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, inliers = cv2.findHomography(pts_b, pts_a, cv2.RANSAC, 4.0)
    if H is None or inliers is None or int(inliers.sum()) < 6:
        return None
    return H


def _warp_with_homography(
    image: np.ndarray,
    H: np.ndarray,
    canvas_size: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    """將影像依 Homography 映射至畫布，回傳影像、遮罩與左上角座標。"""
    h, w = image.shape[:2]
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    warped_corners = cv2.perspectiveTransform(corners, H)
    xs = warped_corners[:, 0, 0]
    ys = warped_corners[:, 0, 1]
    min_x, min_y = int(np.floor(xs.min())), int(np.floor(ys.min()))
    max_x, max_y = int(np.ceil(xs.max())), int(np.ceil(ys.max()))

    # 平移使所有內容落在正座標
    T = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]], dtype=np.float64)
    H_shift = T @ H

    cw, ch = canvas_size
    warped = cv2.warpPerspective(
        image, H_shift, (cw, ch), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
    )
    mask = cv2.warpPerspective(
        255 * np.ones((h, w), np.uint8),
        H_shift,
        (cw, ch),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return warped, mask, (min_x, min_y)


def stitch_flat_strips(
    img_paths: list[Path],
    *,
    output_path: Path,
    feature_method: str = "sift",
    overlap_ratio: float = OVERLAP_RATIO,
    compose_megapix: float = COMPOSE_MEGAPIX,
) -> np.ndarray:
    """平面切片拼接（等距柱狀圖垂直切片）。

    適用同一全景圖切出的相鄰條帶：Homography 僅做微小透視校正，
    接縫以 GraphCut 尋找最佳路徑，MultiBand 保留高頻細節。
    """
    if len(img_paths) < 2:
        raise ValueError("至少需要兩張相鄰切片")

    images = [imread_unicode(p) for p in img_paths]
    h = images[0].shape[0]
    if any(im.shape[0] != h for im in images):
        raise ValueError("所有切片高度必須一致")

    widths = [im.shape[1] for im in images]
    finder = _create_feature_finder(feature_method)

    # 累積水平位移：以切片重疊區的 Homography 微調對齊
    x_offsets = [0.0]
    for i in range(1, len(images)):
        overlap = max(96, min(widths[i - 1], widths[i]) // 3)
        left_roi = images[i - 1][:, -overlap:]
        right_roi = images[i][:, :overlap]
        H_pair = _detect_and_match_homography(left_roi, right_roi, finder)

        base_dx = x_offsets[-1] + widths[i - 1] - overlap
        if H_pair is not None:
            # 右片原點經 Homography 後在左片座標中的位置
            origin = H_pair @ np.array([0.0, 0.0, 1.0])
            # 換算為畫布上的 x 偏移
            x_offsets.append(float(x_offsets[-1] + widths[i - 1] - overlap + origin[0]))
        else:
            x_offsets.append(float(base_dx))

    # 建立每片到畫布的 Homography（平移 + 匹配微調）
    global_H: list[np.ndarray] = []
    for i, x0 in enumerate(x_offsets):
        H = np.eye(3, dtype=np.float64)
        H[0, 2] = x0
        if i > 0:
            overlap = max(96, min(widths[i - 1], widths[i]) // 3)
            left_roi = images[i - 1][:, -overlap:]
            right_roi = images[i][:, :overlap]
            H_pair = _detect_and_match_homography(left_roi, right_roi, finder)
            if H_pair is not None and abs(H_pair[1, 0]) < 0.08:
                T = np.array(
                    [[1, 0, x_offsets[i - 1] + widths[i - 1] - overlap],
                     [0, 1, 0],
                     [0, 0, 1]],
                    dtype=np.float64,
                )
                H = T @ H_pair
        global_H.append(H)

    # 計算畫布大小
    all_corners = []
    for im, H in zip(images, global_H):
        w = im.shape[1]
        pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        warped = cv2.perspectiveTransform(pts, H)
        all_corners.append(warped)
    all_pts = np.vstack(all_corners)
    min_x = int(np.floor(all_pts[:, 0, 0].min()))
    min_y = int(np.floor(all_pts[:, 0, 1].min()))
    max_x = int(np.ceil(all_pts[:, 0, 0].max()))
    max_y = int(np.ceil(all_pts[:, 0, 1].max()))
    canvas_w = max_x - min_x
    canvas_h = max_y - min_y

    T_canvas = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]], dtype=np.float64)

    # 接縫估計尺度（縮小以加速 GraphCut）
    seam_scale = _work_scale((canvas_h, canvas_w), SEAM_MEGAPIX)
    seam_w = max(1, int(round(canvas_w * seam_scale)))
    seam_h = max(1, int(round(canvas_h * seam_scale)))

    images_warped: list[np.ndarray] = []
    masks_warped: list[np.ndarray] = []
    corners: list[tuple[int, int]] = []

    for im, H in zip(images, global_H):
        H_canvas = T_canvas @ H
        warped = cv2.warpPerspective(
            im, H_canvas, (canvas_w, canvas_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        mask = cv2.warpPerspective(
            255 * np.ones(im.shape[:2], np.uint8),
            H_canvas,
            (canvas_w, canvas_h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        # 縮小供 GraphCut 使用
        warped_s = cv2.resize(warped, (seam_w, seam_h), interpolation=cv2.INTER_AREA)
        mask_s = cv2.resize(mask, (seam_w, seam_h), interpolation=cv2.INTER_NEAREST)
        images_warped.append(warped_s)
        masks_warped.append(mask_s)
        corners.append((0, 0))

    images_warped_f = [img.astype(np.float32) for img in images_warped]
    seam_finder = cv2.detail.GraphCutSeamFinder("COST_COLOR_GRAD")
    masks_warped = seam_finder.find(images_warped_f, corners, masks_warped)

    # 全解析度 MultiBand 融合
    compose_scale = _work_scale((canvas_h, canvas_w), compose_megapix)
    out_w = max(1, int(round(canvas_w * compose_scale)))
    out_h = max(1, int(round(canvas_h * compose_scale)))
    dst_sz = (0, 0, out_w, out_h)

    blend_width = math.sqrt(out_w * out_h) * BLEND_STRENGTH / 100.0
    blender = cv2.detail.MultiBandBlender()
    num_bands = max(1, int(math.log(max(blend_width, 2)) / math.log(2) - 1))
    blender.setNumBands(num_bands)
    blender.prepare(dst_sz)

    for im, H, seam_mask in zip(images, global_H, masks_warped):
        H_canvas = T_canvas @ H
        if compose_scale < 0.999:
            H_canvas = H_canvas.copy()
            H_canvas[0, :] *= compose_scale
            H_canvas[1, :] *= compose_scale

        warped = cv2.warpPerspective(
            im, H_canvas, (out_w, out_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        mask = cv2.warpPerspective(
            255 * np.ones(im.shape[:2], np.uint8),
            H_canvas,
            (out_w, out_h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        dilated = cv2.dilate(seam_mask, None)
        seam_mask_full = cv2.resize(
            dilated, (out_w, out_h), interpolation=cv2.INTER_LINEAR_EXACT
        )
        mask = cv2.bitwise_and(seam_mask_full, mask)
        blender.feed(cv2.UMat(warped.astype(np.int16)), mask, (0, 0))

    result, _ = blender.blend(None, None)
    result_u8 = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    imwrite_unicode(output_path, result_u8, quality=98)
    return result_u8


def stitch_slice_images(
    img_paths: list[Path],
    *,
    output_path: Path,
    feature_method: str = "sift",
    warp_type: str = "cylindrical",
    mode: str = "auto",
    compose_megapix: float = COMPOSE_MEGAPIX,
) -> np.ndarray:
    """以 OpenCV detail 管線拼接相鄰切片。

    mode:
      - flat  : 等距柱狀垂直切片（SIFT + RANSAC Homography + GraphCut + MultiBand）
      - rotate: 旋轉環景照片（Homography + Bundle Adjustment + GraphCut + MultiBand）
      - auto  : 先嘗試 rotate，失敗則改用 flat
    """
    if mode == "flat":
        return stitch_flat_strips(
            img_paths,
            output_path=output_path,
            feature_method=feature_method,
            compose_megapix=compose_megapix,
        )

    if mode == "auto":
        try:
            return _stitch_rotating_panorama(
                img_paths,
                output_path=output_path,
                feature_method=feature_method,
                warp_type=warp_type,
                compose_megapix=compose_megapix,
            )
        except RuntimeError as exc:
            print(f"[warn] 旋轉拼接失敗（{exc}），改用平面切片模式…")
            return stitch_flat_strips(
                img_paths,
                output_path=output_path,
                feature_method=feature_method,
                compose_megapix=compose_megapix,
            )

    return _stitch_rotating_panorama(
        img_paths,
        output_path=output_path,
        feature_method=feature_method,
        warp_type=warp_type,
        compose_megapix=compose_megapix,
    )


def _stitch_rotating_panorama(
    img_paths: list[Path],
    *,
    output_path: Path,
    feature_method: str = "sift",
    warp_type: str = "cylindrical",
    compose_megapix: float = COMPOSE_MEGAPIX,
) -> np.ndarray:
    """旋轉環景拼接（適用多視角實拍切片）。"""
    if len(img_paths) < 2:
        raise ValueError("至少需要兩張相鄰切片")

    finder = _create_feature_finder(feature_method)
    full_sizes: list[tuple[int, int]] = []
    features = []
    seam_images = []
    work_scale = None
    seam_scale = None

    # --- 1. 讀取影像並計算多尺度特徵 ---
    for p in img_paths:
        full = imread_unicode(p)
        full_sizes.append((full.shape[1], full.shape[0]))

        if work_scale is None:
            work_scale = _work_scale(full.shape[:2], WORK_MEGAPIX)
            seam_scale = _work_scale(full.shape[:2], SEAM_MEGAPIX)

        work_img = cv2.resize(
            full, None, fx=work_scale, fy=work_scale, interpolation=cv2.INTER_LINEAR_EXACT
        )
        feat = cv2.detail.computeImageFeatures2(finder, work_img)
        features.append(feat)

        seam_img = cv2.resize(
            full, None, fx=seam_scale, fy=seam_scale, interpolation=cv2.INTER_LINEAR_EXACT
        )
        seam_images.append(seam_img)

    seam_work_aspect = seam_scale / work_scale

    # --- 2. 特徵匹配（RANSAC 估計 Homography）---
    matcher = cv2.detail_BestOf2NearestMatcher(False, MATCH_CONF)
    pairwise = matcher.apply2(features)
    matcher.collectGarbage()

    # 保留最大連通子圖，避免孤立切片
    indices = cv2.detail.leaveBiggestComponent(features, pairwise, CONF_THRESH)
    if len(indices) < 2:
        raise RuntimeError("特徵匹配失敗：無法建立切片連通關係")

    features = [features[i] for i in indices]
    seam_images = [seam_images[i] for i in indices]
    img_paths = [img_paths[i] for i in indices]
    full_sizes = [full_sizes[i] for i in indices]
    num_images = len(img_paths)

    # --- 3. Homography 相機姿態估計 + Bundle Adjustment ---
    estimator = cv2.detail_HomographyBasedEstimator()
    ok, cameras = estimator.apply(features, pairwise, None)
    if not ok:
        raise RuntimeError("Homography 幾何校正失敗")

    for cam in cameras:
        cam.R = cam.R.astype(np.float32)

    adjuster = cv2.detail_BundleAdjusterRay()
    adjuster.setConfThresh(CONF_THRESH)
    refine_mask = np.eye(3, dtype=np.uint8)  # 允許完整姿態微調
    adjuster.setRefinementMask(refine_mask)
    ok, cameras = adjuster.apply(features, pairwise, cameras)
    if not ok:
        raise RuntimeError("Bundle Adjustment 失敗")

    focals = sorted(cam.focal for cam in cameras)
    warped_scale = focals[len(focals) // 2]

    # 水平波浪校正，減少柱狀投影扭曲
    rmats = [np.copy(cam.R) for cam in cameras]
    rmats = cv2.detail.waveCorrect(rmats, cv2.detail.WAVE_CORRECT_HORIZ)
    for idx, cam in enumerate(cameras):
        cam.R = rmats[idx]

    # --- 4. 接縫尺度：旋轉展開 + GraphCut 最佳接縫 ---
    warper = cv2.PyRotationWarper(warp_type, warped_scale * seam_work_aspect)
    corners: list[tuple[int, int]] = []
    sizes: list[tuple[int, int]] = []
    images_warped: list[np.ndarray] = []
    masks_warped: list[np.ndarray] = []

    for idx in range(num_images):
        mask = 255 * np.ones(seam_images[idx].shape[:2], np.uint8)
        K = cameras[idx].K().astype(np.float32)
        swa = seam_work_aspect
        K[0, 0] *= swa
        K[0, 2] *= swa
        K[1, 1] *= swa
        K[1, 2] *= swa

        corner, warped = warper.warp(
            seam_images[idx], K, cameras[idx].R, cv2.INTER_LINEAR, cv2.BORDER_REFLECT
        )
        _, mask_wp = warper.warp(
            mask, K, cameras[idx].R, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT
        )
        corners.append(corner)
        sizes.append((warped.shape[1], warped.shape[0]))
        images_warped.append(warped)
        masks_warped.append(mask_wp)

    images_warped_f = [img.astype(np.float32) for img in images_warped]

    # 曝光補償（區塊增益，避免接縫亮度差）
    compensator = cv2.detail.BlocksGainCompensator()
    compensator.feed(corners, images_warped, masks_warped)

    # GraphCut：在重疊區自動找最佳接縫，避開牆面線條
    seam_finder = cv2.detail.GraphCutSeamFinder("COST_COLOR_GRAD")
    masks_warped = seam_finder.find(images_warped_f, corners, masks_warped)

    # --- 5. 全解析度合成：MultiBandBlender（非線性透明度）---
    compose_scale = _work_scale(
        (int(full_sizes[0][1]), int(full_sizes[0][0])), compose_megapix
    )
    compose_work_aspect = compose_scale / work_scale
    warped_scale *= compose_work_aspect
    warper = cv2.PyRotationWarper(warp_type, warped_scale)

    corners = []
    sizes = []
    blender = None

    for idx, p in enumerate(img_paths):
        full = imread_unicode(p)
        if compose_scale < 0.999:
            full = cv2.resize(
                full, None, fx=compose_scale, fy=compose_scale, interpolation=cv2.INTER_LINEAR_EXACT
            )

        cameras[idx].focal *= compose_work_aspect
        cameras[idx].ppx *= compose_work_aspect
        cameras[idx].ppy *= compose_work_aspect

        sz = (
            int(round(full_sizes[idx][0] * compose_scale)),
            int(round(full_sizes[idx][1] * compose_scale)),
        )
        K = cameras[idx].K().astype(np.float32)
        roi = warper.warpRoi(sz, K, cameras[idx].R)
        corners.append(roi[0:2])
        sizes.append(roi[2:4])

        corner, image_warped = warper.warp(
            full, K, cameras[idx].R, cv2.INTER_LINEAR, cv2.BORDER_REFLECT
        )
        mask = 255 * np.ones(full.shape[:2], np.uint8)
        _, mask_warped = warper.warp(
            mask, K, cameras[idx].R, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT
        )

        compensator.apply(idx, corners[idx], image_warped, mask_warped)
        image_warped_s = image_warped.astype(np.int16)

        # 套用 GraphCut 接縫遮罩
        dilated = cv2.dilate(masks_warped[idx], None)
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
            num_bands = max(1, int(math.log(max(blend_width, 2)) / math.log(2) - 1))
            blender.setNumBands(num_bands)
            blender.prepare(dst_sz)

        blender.feed(cv2.UMat(image_warped_s), mask_warped, corners[idx])

    result, _ = blender.blend(None, None)
    result_u8 = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    imwrite_unicode(output_path, result_u8, quality=98)
    return result_u8


def repair_wrap_seam_graphcut(
    image: np.ndarray,
    *,
    band_px: int | None = None,
    floor_ratio: float = 0.55,
    wall_bands: int = 1,
    floor_bands: int = 3,
) -> np.ndarray:
    """僅修復 360° 左右環繞接縫，其餘像素保持原圖銳利度。

    策略（對應參考圖效果）：
      - 牆面／色帶區：GraphCut 選邊 + 極窄 MultiBand（1 層），避免模糊
      - 地面區：略寬 MultiBand（3 層），消除 AI 水波紋差異
      - 先做色調匹配，不位移幾何（原圖已對齊）
    """
    h, w = image.shape[:2]
    overlap = band_px or max(256, min(768, w // 24))
    y_floor = int(h * floor_ratio)

    out = image.astype(np.float32).copy()

    # 色調匹配：消除左右亮度差，不模糊
    out = _tone_match_cv(out)

    right_strip = out[:, w - overlap :].copy()
    left_strip = out[:, :overlap].copy()

    # 雙層畫布：右緣與左緣在重疊區並排
    seam_overlap = overlap // 2
    cw = overlap + seam_overlap
    img_r = np.zeros((h, cw, 3), np.float32)
    img_l = np.zeros((h, cw, 3), np.float32)
    mask_r = np.zeros((h, cw), np.uint8)
    mask_l = np.zeros((h, cw), np.uint8)

    img_r[:, :overlap] = right_strip
    mask_r[:, :overlap] = 255
    img_l[:, seam_overlap : seam_overlap + overlap] = left_strip
    mask_l[:, seam_overlap : seam_overlap + overlap] = 255

    corners = [(0, 0), (0, 0)]
    imgs_f = [img_r, img_l]
    masks = [mask_r, mask_l]

    seam_finder = cv2.detail.GraphCutSeamFinder("COST_COLOR_GRAD")
    masks = seam_finder.find(imgs_f, corners, masks)
    masks = [m.get() if hasattr(m, "get") else np.asarray(m) for m in masks]

    def _blend_region(y0: int, y1: int, num_bands: int) -> np.ndarray:
        """對指定高度區間做多頻段融合。"""
        if y1 <= y0:
            return np.zeros((0, cw, 3), np.uint8)
        roi_r = img_r[y0:y1].astype(np.int16)
        roi_l = img_l[y0:y1].astype(np.int16)
        m_r = masks[0][y0:y1]
        m_l = masks[1][y0:y1]
        rh = y1 - y0
        blender = cv2.detail.MultiBandBlender()
        blender.setNumBands(max(1, num_bands))
        blender.prepare((0, 0, cw, rh))
        blender.feed(cv2.UMat(roi_r), m_r, (0, 0))
        blender.feed(cv2.UMat(roi_l), m_l, (0, 0))
        blended, _ = blender.blend(None, None)
        return cv2.normalize(blended, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    wall_patch = _blend_region(0, y_floor, wall_bands)
    floor_patch = _blend_region(y_floor, h, floor_bands) if y_floor < h else None

    # 從融合結果取接縫帶貼回原圖
    paste_half = seam_overlap // 2
    result = np.clip(out, 0, 255).astype(np.uint8)

    if wall_patch.size:
        pl = min(paste_half, overlap // 4, wall_patch.shape[1])
        pr = min(paste_half, overlap // 4, wall_patch.shape[1])
        rh = wall_patch.shape[0]
        if pl > 0:
            result[:rh, :pl] = wall_patch[:rh, :pl]
        if pr > 0:
            result[:rh, w - pr :] = wall_patch[:rh, cw - pr :]

    if floor_patch is not None and floor_patch.size:
        pl = min(paste_half, overlap // 4, floor_patch.shape[1])
        pr = min(paste_half, overlap // 4, floor_patch.shape[1])
        fh = floor_patch.shape[0]
        y0 = y_floor
        if pl > 0:
            result[y0 : y0 + fh, :pl] = floor_patch[:, :pl]
        if pr > 0:
            result[y0 : y0 + fh, w - pr :] = floor_patch[:, cw - pr :]

    return result


def _tone_match_cv(arr: np.ndarray) -> np.ndarray:
    """左右色調匹配（寬過渡、不糊化）。"""
    out = arr.copy()
    h, w = out.shape[:2]
    tone_trans = min(2500, w // 3)
    r0 = out[:, :30].mean(axis=(0, 1))
    l0 = out[:, w - 30 :].mean(axis=(0, 1))
    mid = (r0 + l0) * 0.5
    for x in range(w - tone_trans, w):
        r = 0.5 * (1.0 + np.cos(np.pi * (w - 1 - x) / tone_trans))
        out[:, x] += (mid - l0) * r
    for x in range(tone_trans):
        r = 0.5 * (1.0 + np.cos(np.pi * x / tone_trans))
        out[:, x] += (mid - r0) * r
    return out


def repair_wrap_seam_equirect(
    image: np.ndarray,
    *,
    band_ratio: float = 0.18,
    feature_method: str = "sift",
) -> np.ndarray:
    """修復等距柱狀圖左右環繞接縫（360° 首尾相連）。

    將左、右邊界帶視為兩張相鄰切片，以 Homography（RANSAC）對齊後
    以 GraphCut + MultiBand 融合，再貼回全景。
    """
    h, w = image.shape[:2]
    band_w = max(256, int(w * band_ratio))

    # 左帶：含左緣與其右側重疊區
    left_strip = image[:, :band_w].copy()
    # 右帶：含右緣與其左側重疊區（與左帶在環繞點相遇）
    right_strip = image[:, w - band_w :].copy()

    with tempfile.TemporaryDirectory(prefix="pano_wrap_") as tmp:
        left_p = Path(tmp) / "wrap_left.jpg"
        right_p = Path(tmp) / "wrap_right.jpg"
        imwrite_unicode(left_p, left_strip, quality=95)
        imwrite_unicode(right_p, right_strip, quality=95)

        # 在暫存畫布上拼接兩帶，取得修復後的接縫區域
        patch_path = Path(tmp) / "wrap_patch.jpg"
        patch = stitch_slice_images(
            [right_p, left_p],  # 右帶在左、左帶在右，模擬環繞相鄰
            output_path=patch_path,
            feature_method=feature_method,
            mode="flat",
        )

    # 將修復帶貼回（取 patch 中央對應寬度）
    ph, pw = patch.shape[:2]
    paste_w = min(band_w, pw)
    x0 = max(0, (pw - paste_w) // 2)
    seam_patch = patch[:, x0 : x0 + paste_w]

    out = image.copy()
    half = paste_w // 2
    rh = min(h, seam_patch.shape[0])
    lw = min(half, w, seam_patch.shape[1])
    rw = min(half, w)
    src_rx = max(0, seam_patch.shape[1] - rw)
    if lw > 0:
        out[:rh, :lw] = seam_patch[:rh, :lw]
    if rw > 0:
        out[:rh, w - rw :] = seam_patch[:rh, src_rx : src_rx + rw]
    return out


def process_zone(
    zone_id: str,
    *,
    source_dir: Path | None = None,
    slice_dir: Path | None = None,
    num_slices: int = 5,
    repair_wrap: bool = True,
    feature_method: str = "sift",
    compose_megapix: float = COMPOSE_MEGAPIX,
    mode: str = "seam-only",
) -> Path:
    """處理指定展區並輸出至 media/panoramas。

    mode:
      - seam-only : 保留原圖銳利度，僅修復 360° 環繞接縫（推薦）
      - restitch  : 切片重拼（適合多視角實拍素材）
    """
    zone = _zone_by_id(zone_id)
    out_pano = PANOS / zone["file"]

    if slice_dir and slice_dir.exists():
        img_paths = sorted(slice_dir.glob("*.jpg")) + sorted(slice_dir.glob("*.png"))
        if len(img_paths) < 2:
            raise SystemExit(f"切片目錄影像不足：{slice_dir}")
        print(f"[info] 讀取 {len(img_paths)} 張切片：{slice_dir}")
        result = stitch_slice_images(
            img_paths,
            output_path=out_pano,
            feature_method=feature_method,
            compose_megapix=compose_megapix,
        )
    else:
        src = _resolve_source(zone, source_dir)
        print(f"[info] 來源全景：{src}")
        pano = imread_unicode(src)

        if mode == "seam-only":
            print("[info] 接縫限定修復（保留原圖銳利度）…")
            result = repair_wrap_seam_graphcut(pano)
        else:
            with tempfile.TemporaryDirectory(prefix="pano_slices_") as tmp:
                slices = split_equirectangular_slices(pano, num_slices=num_slices)
                paths = save_temp_slices(slices, Path(tmp))
                print(f"[info] 自動切為 {len(paths)} 片（重疊 {OVERLAP_RATIO:.0%}）")
                result = stitch_slice_images(
                    paths,
                    output_path=ROOT / "media" / "panoramas" / f"tmp_{zone['file']}",
                    feature_method=feature_method,
                    mode="flat",
                    compose_megapix=compose_megapix,
                )

            if repair_wrap:
                print("[info] 修復 360° 環繞接縫…")
                result = repair_wrap_seam_graphcut(result)

            src_h, src_w = pano.shape[:2]
            if result.shape[1] != src_w or result.shape[0] != src_h:
                print(f"[info] 升採樣至來源解析度 {src_w}×{src_h}…")
                result = cv2.resize(
                    result, (src_w, src_h), interpolation=cv2.INTER_LANCZOS4
                )

        imwrite_unicode(out_pano, result, quality=98)

    # 產生縮圖
    THUMBS.mkdir(parents=True, exist_ok=True)
    thumb = cv2.resize(result, (320, 160), interpolation=cv2.INTER_AREA)
    imwrite_unicode(THUMBS / zone["file"], thumb, quality=85)

    print(f"[ok] {zone_id} → {out_pano} ({result.shape[1]}×{result.shape[0]})")
    return out_pano


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCV 環景切片無縫拼接")
    parser.add_argument("--zone", default="zone-1", help="展區 id，預設 zone-1")
    parser.add_argument("--source", type=Path, default=None, help="來源目錄或覆寫路徑")
    parser.add_argument("--slices", type=Path, default=None, help="相鄰切片目錄（可選）")
    parser.add_argument("--num-slices", type=int, default=5, help="自動切片數量")
    parser.add_argument("--features", choices=("sift", "orb"), default="sift")
    parser.add_argument(
        "--compose-megapix",
        type=float,
        default=COMPOSE_MEGAPIX,
        help=f"輸出解析度上限（百萬像素，預設 {COMPOSE_MEGAPIX}）",
    )
    parser.add_argument(
        "--mode",
        choices=("seam-only", "restitch"),
        default="seam-only",
        help="seam-only=僅修環繞接縫（推薦）；restitch=切片重拼",
    )
    parser.add_argument("--no-wrap-repair", action="store_true", help="略過 360° 環繞接縫修復")
    args = parser.parse_args()

    process_zone(
        args.zone,
        source_dir=args.source,
        slice_dir=args.slices,
        num_slices=args.num_slices,
        repair_wrap=not args.no_wrap_repair,
        feature_method=args.features,
        compose_megapix=args.compose_megapix,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
