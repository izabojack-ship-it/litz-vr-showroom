/**
 * 鋁台精機 VR 展間：環景導覽 + 機台介紹主程式
 */
import { Viewer, EquirectangularAdapter } from '@photo-sphere-viewer/core';
import { MarkersPlugin } from '@photo-sphere-viewer/markers-plugin';
import { ZONES } from './zones.js?v=hall250719a';
import { loadProductContent, getMachinesForScene } from './content-store.js?v=hall250716a';
import {
  initMachinePanel,
  setMachineBarVisible,
  setSceneMachines,
  openMachinePanel,
  closeMachinePanel,
  collapseMachineBar,
  buildMachineMarkers,
} from './machine-panel.js?v=hall250716a';

const MEDIA_VERSION = 'hall250720g';
// 媒體快取版本：更換背景圖或縮圖後調高此值即可強制瀏覽器重新載入

function mediaUrl(folder, file) {
  return `./media/${folder}/${encodeURIComponent(file)}?v=${MEDIA_VERSION}`;
}

function makePanoData(width, height) {
  return {
    fullWidth: width,
    fullHeight: height,
    croppedWidth: width,
    croppedHeight: height,
    croppedX: 0,
    croppedY: 0,
  };
}

// 各場景載入時的預設朝向（面向主機台）
const DEFAULT_YAW = {
  'zone-1': '29deg',
  'zone-2': '-115deg',
  'zone-5': '-80deg',
  'zone-3': '-122deg',
  'zone-4': '145deg',
};

const scenes = ZONES.map((zone) => ({
  id: zone.id,
  title: zone.title,
  panorama: mediaUrl('panoramas', zone.file),
  thumbnail: mediaUrl('thumbs', zone.file),
  panoData: makePanoData(zone.width, zone.height),
  defaultYaw: DEFAULT_YAW[zone.id] ?? '0deg',
  defaultPitch: '-4deg',
  defaultZoom: 18,
}));

const loaderEl = document.getElementById('lb-loader');
const loaderSubEl = loaderEl?.querySelector('.lb-loader__sub');
const fadeEl = document.getElementById('lb-fade');
const sceneNameEl = document.getElementById('lb-scene-name');
const radarBeamEl = document.getElementById('lb-radar-beam');
const zoneDockEl = document.getElementById('lb-zone-dock');
const zoneToggleEl = document.getElementById('lb-zone-toggle');
const guideDockEl = document.getElementById('lb-guide-dock');
const guideToggleEl = document.getElementById('lb-guide-toggle');
const thumbsEl = document.getElementById('lb-thumbs');
const resetBtn = document.getElementById('lb-reset');

let viewer = null;
let markersPlugin = null;
let currentSceneId = scenes[0]?.id;
let isTransitioning = false;
let zoneDockExpanded = false;
let guideDockExpanded = false;

function setZoneDockExpanded(expanded) {
  zoneDockExpanded = expanded;
  zoneDockEl?.classList.toggle('is-expanded', expanded);
  zoneToggleEl?.setAttribute('aria-expanded', String(expanded));
  if (expanded) collapseMachineBar();
}

function collapseZoneDock() {
  setZoneDockExpanded(false);
}

function setGuideDockExpanded(expanded) {
  guideDockExpanded = expanded;
  guideDockEl?.classList.toggle('is-expanded', expanded);
  guideToggleEl?.setAttribute('aria-expanded', String(expanded));
}

function collapseGuideDock() {
  setGuideDockExpanded(false);
}

function initGuideDock() {
  guideToggleEl?.addEventListener('click', () => {
    setGuideDockExpanded(!guideDockExpanded);
  });
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function getScene(id) {
  return scenes.find((s) => s.id === id);
}

function buildMarkersForScene(sceneId) {
  const machines = getMachinesForScene(sceneId);
  return buildMachineMarkers(machines);
}

function syncRadar(yawRad) {
  if (!radarBeamEl) return;
  radarBeamEl.style.transform = `rotate(${(yawRad * 180) / Math.PI}deg)`;
}

function updateSceneLabel() {
  const scene = getScene(currentSceneId);
  if (scene && sceneNameEl) sceneNameEl.textContent = scene.title;
}

function updateThumbnails() {
  thumbsEl?.querySelectorAll('.lb-thumb').forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.sceneId === currentSceneId);
  });
}

function updateSceneExtras() {
  const machines = getMachinesForScene(currentSceneId);
  setSceneMachines(machines);
  setMachineBarVisible(machines.length > 0);
  if (!machines.length) closeMachinePanel();
}

function buildThumbnailMenu() {
  if (!thumbsEl) return;
  thumbsEl.innerHTML = scenes.map((scene) => `
    <button type="button" class="lb-thumb" data-scene-id="${scene.id}" aria-label="前往 ${scene.title}">
      <img class="lb-thumb__img" src="${scene.thumbnail}" alt="" loading="lazy">
      <span class="lb-thumb__name">${scene.title}</span>
    </button>`).join('');

  thumbsEl.addEventListener('click', (event) => {
    const btn = event.target.closest('.lb-thumb');
    if (!btn) return;
    switchScene(btn.dataset.sceneId);
    collapseZoneDock();
  });
}

function initZoneDock() {
  zoneToggleEl?.addEventListener('click', () => {
    setZoneDockExpanded(!zoneDockExpanded);
  });
}

function applySceneMarkers(sceneId) {
  if (!markersPlugin) return;
  markersPlugin.setMarkers(buildMarkersForScene(sceneId));
}

async function focusMachine(machine) {
  if (!viewer || !machine) return;
  const f = machine.focus ?? {};
  await viewer.animate({
    yaw: f.yaw ?? machine.position.yaw,
    pitch: f.pitch ?? '-2deg',
    zoom: f.zoom ?? 50,
    speed: '4rpm',
  });
}

async function switchScene(targetId) {
  if (isTransitioning || targetId === currentSceneId) return;

  const target = getScene(targetId);
  if (!target) return;

  isTransitioning = true;

  try {
    closeMachinePanel();
    collapseZoneDock();
    collapseGuideDock();

    fadeEl?.classList.add('is-out');
    await wait(460);

    if (loaderSubEl) loaderSubEl.textContent = `正在載入 ${target.title}…`;
    loaderEl?.classList.remove('is-hidden');

    await viewer.setPanorama(target.panorama, {
      caption: target.title,
      panoData: target.panoData,
      position: { yaw: target.defaultYaw, pitch: target.defaultPitch },
      zoom: target.defaultZoom ?? 18,
      transition: false,
    });

    currentSceneId = targetId;
    applySceneMarkers(targetId);
    updateThumbnails();
    updateSceneLabel();
    updateSceneExtras();

    fadeEl?.classList.remove('is-out');
    fadeEl?.classList.add('is-in');
    await wait(460);
    fadeEl?.classList.remove('is-in');
  } catch (err) {
    console.error('[lobby-tour] 切換場景失敗', err);
    fadeEl?.classList.remove('is-out', 'is-in');
  } finally {
    loaderEl?.classList.add('is-hidden');
    isTransitioning = false;
  }
}

async function resetView() {
  const scene = getScene(currentSceneId);
  if (!scene) return;
  closeMachinePanel();
  await viewer.animate({
    yaw: scene.defaultYaw,
    pitch: scene.defaultPitch,
    zoom: scene.defaultZoom ?? 18,
    speed: '4rpm',
  });
}

function initViewer() {
  const first = scenes[0];
  if (!first) return;

  if (loaderSubEl) loaderSubEl.textContent = `正在載入 ${first.title}…`;
  if (sceneNameEl) sceneNameEl.textContent = first.title;

  viewer = new Viewer({
    container: 'viewer',
    adapter: [EquirectangularAdapter, { blur: false }],
    panorama: first.panorama,
    panoData: first.panoData,
    caption: first.title,
    loadingTxt: '載入 VR 場景中…',
    navbar: false,
    defaultYaw: first.defaultYaw,
    defaultPitch: first.defaultPitch,
    defaultZoomLvl: first.defaultZoom,
    mousewheel: true,
    mousewheelCtrlKey: false,
    mousemove: true,
    moveInertia: true,
    moveSpeed: 0.85,
    zoomSpeed: 0.9,
    minFov: 12,
    maxFov: 90,
    canvasBackground: '#8fa8bc',
    plugins: [
      MarkersPlugin.withConfig({
        gotoMarkerSpeed: '4rpm',
        clickEventOnMarker: false,
        defaultHoverScale: { amount: 1.05, duration: 120, easing: 'ease-out' },
        markers: buildMarkersForScene(first.id),
      }),
    ],
  });

  markersPlugin = viewer.getPlugin(MarkersPlugin);

  viewer.addEventListener('position-updated', ({ position }) => {
    syncRadar(position.yaw);
  });

  viewer.container.addEventListener('pointerdown', (e) => {
    if (e.target.closest('.lb-machine-dock') || e.target.closest('.lb-zone-dock') || e.target.closest('.lb-guide-dock')) return;
    collapseMachineBar();
    collapseZoneDock();
    collapseGuideDock();
  });

  markersPlugin.addEventListener('select-marker', async ({ marker }) => {
    if (marker?.data?.type !== 'machine' || !marker.data.machineId) return;
    const machines = getMachinesForScene(currentSceneId);
    const machine = machines.find((m) => m.id === marker.data.machineId);
    if (machine) await focusMachine(machine);
    openMachinePanel(marker.data.machineId, { animate: false });
  });

  viewer.addEventListener('ready', () => {
    loaderEl?.classList.add('is-hidden');
    syncRadar(viewer.getPosition().yaw);
    updateSceneLabel();
    updateThumbnails();
    updateSceneExtras();
  }, { once: true });
}

initMachinePanel({
  focusMachine,
  onMachineBarExpanded: (expanded) => {
    if (expanded) collapseZoneDock();
  },
});
initGuideDock();
initZoneDock();
buildThumbnailMenu();
resetBtn?.addEventListener('click', () => resetView());

async function boot() {
  if (loaderSubEl) loaderSubEl.textContent = '正在載入產品內容…';
  loaderEl?.classList.remove('is-hidden');
  try {
    await loadProductContent();
  } catch (err) {
    console.error('[lobby] 產品內容載入失敗，仍開啟 VR 展間', err);
  }
  initViewer();
}

boot();
