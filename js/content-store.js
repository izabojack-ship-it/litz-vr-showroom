/** 載入後台發布的產品內容，與 layout 合併供 VR 展間使用。 */

const MANIFEST_URL = '/api/content/manifest';
const FALLBACK_MANIFEST_URL = './content/published/machines.json';
const CONTENT_FILES_BASE = '/content/files/';

let contentVersion = 0;
let mergedByZone = {};

export function getContentVersion() {
  return contentVersion;
}

export function resolveContentUrl(path, mediaVersion = contentVersion) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith('media/')) return `./${path}?v=${mediaVersion}`;
  return `${CONTENT_FILES_BASE}${path}?v=${mediaVersion}`;
}

function normalizePhotos(photos) {
  return (photos || []).map((p) => {
    if (typeof p === 'string') {
      const url = resolveContentUrl(p);
      return { full: url, thumb: url };
    }
    return {
      full: resolveContentUrl(p.full),
      thumb: resolveContentUrl(p.thumb || p.full),
    };
  });
}

function buildMenu(content) {
  const menu = [];
  if (content.photos?.length) {
    menu.push({ label: '產品圖示', action: 'images' });
  }
  if (content.catalogUrl) {
    menu.push({
      label: '產品型錄',
      action: 'catalog',
      href: resolveContentUrl(content.catalogUrl),
    });
  }
  if (content.casesUrl) {
    menu.push({
      label: '應用案例',
      action: 'cases',
      href: resolveContentUrl(content.casesUrl),
    });
  }
  if (content.contactUrl) {
    menu.push({
      label: '聯絡我們',
      action: 'contact',
      href: resolveContentUrl(content.contactUrl),
    });
  }
  return menu;
}

function mergeLayoutWithManifest(layout, manifest) {
  const result = {};
  for (const [zoneId, machines] of Object.entries(layout.zones || {})) {
    result[zoneId] = machines.map((machine) => {
      const content = manifest.machines?.[machine.id] || {};
      const photos = normalizePhotos(content.photos);
      return {
        ...machine,
        intro: content.intro || '',
        photos,
        presenterVideo: content.presenterVideo
          ? resolveContentUrl(content.presenterVideo)
          : '',
        catalogUrl: content.catalogUrl ? resolveContentUrl(content.catalogUrl) : '',
        casesUrl: content.casesUrl ? resolveContentUrl(content.casesUrl) : '',
        contactUrl: content.contactUrl ? resolveContentUrl(content.contactUrl) : '',
        menu: buildMenu(content),
      };
    });
  }
  return result;
}

async function fetchManifest() {
  try {
    const res = await fetch(MANIFEST_URL, { cache: 'no-cache' });
    if (res.ok) return res.json();
  } catch (err) {
    console.warn('[content] API 不可用，改讀本機 content/published/machines.json', err);
  }
  const fallback = await fetch(FALLBACK_MANIFEST_URL, { cache: 'no-cache' });
  if (!fallback.ok) {
    throw new Error(`無法載入產品內容 (${fallback.status})`);
  }
  return fallback.json();
}

export async function loadProductContent() {
  const [manifest, layoutRes] = await Promise.all([
    fetchManifest(),
    fetch('./js/machines.layout.json', { cache: 'no-cache' }),
  ]);
  if (!layoutRes.ok) {
    throw new Error(`無法載入機台 layout (${layoutRes.status})`);
  }
  const layout = await layoutRes.json();
  contentVersion = manifest.version || 0;
  mergedByZone = mergeLayoutWithManifest(layout, manifest);
}

export function getMachinesForScene(sceneId) {
  return mergedByZone[sceneId] ?? [];
}
