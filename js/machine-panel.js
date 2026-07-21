/** 機台介紹側欄與底部機型列（參考台中精機 VR 展間） */

const panelEl = document.getElementById('lb-product-panel');
const panelTitleEl = document.getElementById('lb-panel-title');
const panelSubEl = document.getElementById('lb-panel-sub');
const panelIntroEl = document.getElementById('lb-panel-intro');
const panelMenuEl = document.getElementById('lb-panel-menu');
const panelCloseEl = document.getElementById('lb-panel-close');
const machineDockEl = document.getElementById('lb-machine-dock');
const machineBarEl = document.getElementById('lb-machine-bar');
const machineToggleEl = document.getElementById('lb-machine-toggle');

const galleryEl = document.querySelector('.lb-gallery');
const galleryThumbsEl = document.getElementById('lb-panel-thumbs');
const galleryMainBtn = document.getElementById('lb-panel-main');
const galleryMainImg = document.getElementById('lb-panel-main-img');

const lightboxEl = document.getElementById('lb-lightbox');
const lightboxImg = document.getElementById('lb-lightbox-img');
const lightboxCloseEl = document.getElementById('lb-lightbox-close');

const presenterBtnEl = document.getElementById('lb-panel-presenter');
const presenterDockEl = document.getElementById('lb-presenter-dock');
const presenterCloseEl = document.getElementById('lb-presenter-close');
const presenterTitleEl = document.getElementById('lb-presenter-title');
const presenterVideoEl = document.getElementById('lb-presenter-video');
const presenterLangsEl = document.getElementById('lb-presenter-langs');
const presenterStageEl = presenterVideoEl?.closest('.lb-presenter-dock__stage');
const presenterInnerEl = presenterDockEl?.querySelector('.lb-presenter-dock__inner');
const presenterHeadEl = presenterDockEl?.querySelector('.lb-presenter-dock__head');
const presenterResizeEl = document.getElementById('lb-presenter-resize');
const presenterShrinkEl = document.getElementById('lb-presenter-shrink');
const presenterGrowEl = document.getElementById('lb-presenter-grow');
const presenterResetSizeEl = document.getElementById('lb-presenter-reset-size');

const PRESENTER_SIZE_STORAGE = 'litz-presenter-dock-size';
const PRESENTER_POS_STORAGE = 'litz-presenter-dock-pos';
const PRESENTER_MIN_SIZE = { w: 220, h: 240 };
const PRESENTER_NUDGE = { w: 28, h: 32 };

const PRESENTER_LANG_LABELS = { zh: '中文', en: 'EN', th: 'ไทย' };
const PRESENTER_LANG_ORDER = ['zh', 'en', 'th'];

let sceneMachines = [];
let activeMachineId = null;
let onFocusMachine = null;
let currentMainSrc = '';
let machineBarExpanded = false;
let activePresenterLang = 'zh';

let onMachineBarExpanded = null;

function setMachineBarExpanded(expanded) {
  machineBarExpanded = expanded;
  machineDockEl?.classList.toggle('is-expanded', expanded);
  machineToggleEl?.setAttribute('aria-expanded', String(expanded));
  onMachineBarExpanded?.(expanded);
}

export function collapseMachineBar() {
  setMachineBarExpanded(false);
}

export function expandMachineBar() {
  if (sceneMachines.length) setMachineBarExpanded(true);
}

export function initMachinePanel({ focusMachine, onMachineBarExpanded: onExpanded }) {
  onFocusMachine = focusMachine;
  onMachineBarExpanded = onExpanded ?? null;
  panelCloseEl?.addEventListener('click', closeMachinePanel);
  panelEl?.addEventListener('click', (e) => {
    if (e.target === panelEl) closeMachinePanel();
  });

  galleryMainBtn?.addEventListener('click', () => {
    if (currentMainSrc) openLightbox(currentMainSrc);
  });
  lightboxCloseEl?.addEventListener('click', closeLightbox);
  lightboxEl?.addEventListener('click', (e) => {
    if (e.target === lightboxEl) closeLightbox();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (presenterDockEl?.classList.contains('is-open')) {
      closePresenterDock();
      return;
    }
    if (lightboxEl?.classList.contains('is-open')) closeLightbox();
  });

  machineToggleEl?.addEventListener('click', () => {
    setMachineBarExpanded(!machineBarExpanded);
  });

  presenterBtnEl?.addEventListener('click', () => {
    const machine = sceneMachines.find((m) => m.id === activeMachineId);
    if (machine) openPresenterDock(machine);
  });
  presenterCloseEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    closePresenterDock();
  });
  presenterCloseEl?.addEventListener('pointerdown', (e) => e.stopPropagation());
  // 只在「真正要播片卻失敗」時提示；關閉時清掉 src 觸發的 error 要忽略
  presenterVideoEl?.addEventListener('error', () => {
    if (presenterVideoEl?.dataset.ignoreError === '1') return;
    const src = presenterVideoEl?.currentSrc || presenterVideoEl?.getAttribute('src') || '';
    const code = presenterVideoEl?.error?.code;
    const detail = code ? `（錯誤碼 ${code}）` : '';
    if (!src) {
      window.alert('真人介紹影片載入失敗，路徑為空。請重新整理後再試，或至後台確認是否已「發布至展間」。');
    } else {
      window.alert(`真人介紹影片無法播放${detail}\n${src}\n請確認已按「發布至展間」，並強制重新整理頁面（Ctrl+F5）。`);
    }
    closePresenterDock();
  });
  // 影片載入後依實際比例調整播放框，避免橫式影片被壓成小小一條
  presenterVideoEl?.addEventListener('loadedmetadata', applyPresenterAspect);
  initPresenterResize();
  initPresenterDrag();
  loadPresenterSize();
  loadPresenterPosition();
}

function getPresenterMaxSize() {
  const top = 12;
  const bottom = 88;
  return {
    w: Math.min(Math.floor(window.innerWidth * 0.92), 560),
    h: Math.min(Math.floor(window.innerHeight - top - bottom), 920),
  };
}

function applyPresenterSize(w, h, { persist = false } = {}) {
  if (!presenterDockEl || !presenterInnerEl) return;
  const max = getPresenterMaxSize();
  const width = Math.round(Math.max(PRESENTER_MIN_SIZE.w, Math.min(max.w, w)));
  const height = Math.round(Math.max(PRESENTER_MIN_SIZE.h, Math.min(max.h, h)));
  presenterDockEl.style.setProperty('--presenter-dock-w', `${width}px`);
  presenterInnerEl.style.setProperty('--presenter-dock-h', `${height}px`);
  presenterDockEl.classList.add('is-sized');
  if (persist) {
    localStorage.setItem(PRESENTER_SIZE_STORAGE, JSON.stringify({ w: width, h: height }));
  }
}

function loadPresenterSize() {
  try {
    const raw = localStorage.getItem(PRESENTER_SIZE_STORAGE);
    if (!raw) return;
    const { w, h } = JSON.parse(raw);
    if (Number.isFinite(w) && Number.isFinite(h)) applyPresenterSize(w, h);
  } catch { /* ignore */ }
}

function resetPresenterSize() {
  presenterDockEl?.style.removeProperty('--presenter-dock-w');
  presenterInnerEl?.style.removeProperty('--presenter-dock-h');
  presenterDockEl?.classList.remove('is-sized');
  localStorage.removeItem(PRESENTER_SIZE_STORAGE);
}

function ensurePresenterSizedBaseline() {
  if (!presenterDockEl?.classList.contains('is-sized')) {
    applyPresenterSize(presenterDockEl.offsetWidth, presenterInnerEl.offsetHeight);
  }
}

function nudgePresenterSize(dw, dh) {
  ensurePresenterSizedBaseline();
  applyPresenterSize(
    presenterDockEl.offsetWidth + dw,
    presenterInnerEl.offsetHeight + dh,
    { persist: true },
  );
}

function getPresenterViewportPad() {
  return { top: 12, left: 12, right: 12, bottom: 96 };
}

function clampPresenterPos(x, y) {
  if (!presenterDockEl) return { x, y };
  const pad = getPresenterViewportPad();
  const w = presenterDockEl.offsetWidth;
  const h = presenterDockEl.offsetHeight;
  return {
    x: Math.round(Math.max(pad.left, Math.min(window.innerWidth - w - pad.right, x))),
    y: Math.round(Math.max(pad.top, Math.min(window.innerHeight - h - pad.bottom, y))),
  };
}

function applyPresenterPosition(x, y, { persist = false } = {}) {
  if (!presenterDockEl) return;
  const { x: cx, y: cy } = clampPresenterPos(x, y);
  presenterDockEl.style.left = `${cx}px`;
  presenterDockEl.style.top = `${cy}px`;
  presenterDockEl.style.right = 'auto';
  presenterDockEl.style.bottom = 'auto';
  presenterDockEl.classList.add('is-positioned');
  if (persist) {
    localStorage.setItem(PRESENTER_POS_STORAGE, JSON.stringify({ x: cx, y: cy }));
  }
}

function loadPresenterPosition() {
  if (!presenterDockEl) return;
  try {
    const raw = localStorage.getItem(PRESENTER_POS_STORAGE);
    if (!raw) return;
    const { x, y } = JSON.parse(raw);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    presenterDockEl.style.left = `${x}px`;
    presenterDockEl.style.top = `${y}px`;
    presenterDockEl.style.right = 'auto';
    presenterDockEl.style.bottom = 'auto';
    presenterDockEl.classList.add('is-positioned');
  } catch { /* ignore */ }
}

function resetPresenterPosition() {
  if (!presenterDockEl) return;
  presenterDockEl.style.removeProperty('left');
  presenterDockEl.style.removeProperty('top');
  presenterDockEl.style.removeProperty('right');
  presenterDockEl.style.removeProperty('bottom');
  presenterDockEl.classList.remove('is-positioned');
  localStorage.removeItem(PRESENTER_POS_STORAGE);
}

function initPresenterDrag() {
  if (!presenterHeadEl || !presenterDockEl) return;

  presenterHeadEl.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || !presenterDockEl.classList.contains('is-open')) return;
    if (e.target.closest('button')) return;

    e.preventDefault();
    e.stopPropagation();

    const rect = presenterDockEl.getBoundingClientRect();
    const startX = e.clientX;
    const startY = e.clientY;
    const origLeft = rect.left;
    const origTop = rect.top;

    presenterDockEl.classList.add('is-dragging');

    const onMove = (ev) => {
      applyPresenterPosition(origLeft + (ev.clientX - startX), origTop + (ev.clientY - startY));
    };

    const onUp = (ev) => {
      presenterDockEl.classList.remove('is-dragging');
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onUp);
      applyPresenterPosition(
        origLeft + (ev.clientX - startX),
        origTop + (ev.clientY - startY),
        { persist: true },
      );
    };

    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onUp);
  });

  window.addEventListener('resize', () => {
    if (!presenterDockEl.classList.contains('is-positioned')) return;
    const rect = presenterDockEl.getBoundingClientRect();
    applyPresenterPosition(rect.left, rect.top, { persist: true });
  });
}

function initPresenterResize() {
  if (!presenterResizeEl || !presenterDockEl || !presenterInnerEl) return;

  presenterShrinkEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    nudgePresenterSize(-PRESENTER_NUDGE.w, -PRESENTER_NUDGE.h);
  });
  presenterGrowEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    nudgePresenterSize(PRESENTER_NUDGE.w, PRESENTER_NUDGE.h);
  });
  presenterResetSizeEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    resetPresenterSize();
    resetPresenterPosition();
    applyPresenterAspect();
  });

  presenterResizeEl.addEventListener('dblclick', (e) => {
    e.preventDefault();
    e.stopPropagation();
    resetPresenterSize();
    resetPresenterPosition();
    applyPresenterAspect();
  });

  presenterResizeEl.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();

    const startX = e.clientX;
    const startY = e.clientY;
    ensurePresenterSizedBaseline();
    const startW = presenterDockEl.offsetWidth;
    const startH = presenterInnerEl.offsetHeight;

    presenterDockEl.classList.add('is-resizing');

    const onMove = (ev) => {
      applyPresenterSize(startW + (ev.clientX - startX), startH + (ev.clientY - startY));
    };

    const onUp = () => {
      presenterDockEl.classList.remove('is-resizing');
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onUp);
      applyPresenterSize(presenterDockEl.offsetWidth, presenterInnerEl.offsetHeight, { persist: true });
    };

    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onUp);
  });
}

function applyPresenterAspect() {
  if (!presenterStageEl || !presenterVideoEl) return;
  const w = presenterVideoEl.videoWidth;
  const h = presenterVideoEl.videoHeight;
  if (w > 0 && h > 0) {
    presenterStageEl.style.setProperty('--presenter-aspect', `${w} / ${h}`);
  }
}

function renderGallery(machine) {
  const photos = machine.photos || [];
  if (!galleryEl) return;
  if (!photos.length) {
    galleryEl.style.display = 'none';
    currentMainSrc = '';
    return;
  }
  galleryEl.style.display = '';

  const setMain = (photo) => {
    currentMainSrc = photo.full;
    if (galleryMainImg) {
      galleryMainImg.src = photo.full;
      galleryMainImg.alt = `${machine.name} 產品照片`;
    }
    galleryThumbsEl?.querySelectorAll('.lb-gallery__thumb').forEach((t) => {
      t.classList.toggle('is-active', t.dataset.full === photo.full);
    });
  };

  if (galleryThumbsEl) {
    galleryThumbsEl.innerHTML = photos.map((p) => `
      <button type="button" class="lb-gallery__thumb" data-full="${p.full}" aria-label="${machine.name} 照片">
        <img src="${p.thumb}" alt="" loading="lazy" decoding="async">
      </button>`).join('');
    galleryThumbsEl.classList.toggle('is-single', photos.length <= 1);
    galleryThumbsEl.onclick = (e) => {
      const btn = e.target.closest('.lb-gallery__thumb');
      if (!btn) return;
      const p = photos.find((x) => x.full === btn.dataset.full);
      if (p) setMain(p);
    };
  }

  setMain(photos[0]);
}

function openLightbox(src) {
  if (!lightboxEl || !lightboxImg) return;
  lightboxImg.src = src;
  lightboxEl.classList.add('is-open');
  lightboxEl.setAttribute('aria-hidden', 'false');
}

function closeLightbox() {
  lightboxEl?.classList.remove('is-open');
  lightboxEl?.setAttribute('aria-hidden', 'true');
}

function getPresenterVideos(machine) {
  const videos = { ...(machine?.presenterVideos || {}) };
  // 舊資料相容：單一 presenterVideo 視為中文
  if (!videos.zh && machine?.presenterVideo) videos.zh = machine.presenterVideo;
  return videos;
}

function presenterLangList(machine) {
  const videos = getPresenterVideos(machine);
  return PRESENTER_LANG_ORDER.filter((lang) => videos[lang]);
}

function updatePresenterButton(machine) {
  if (!presenterBtnEl) return;
  presenterBtnEl.hidden = presenterLangList(machine).length === 0;
}

function renderPresenterLangControls(machine) {
  if (!presenterLangsEl) return;
  const langs = presenterLangList(machine);
  // 只有一種語言就不顯示切換列
  if (langs.length <= 1) {
    presenterLangsEl.innerHTML = '';
    presenterLangsEl.hidden = true;
    return;
  }
  presenterLangsEl.hidden = false;
  presenterLangsEl.innerHTML = langs.map((lang) => `
    <button type="button" class="lb-presenter-lang${lang === activePresenterLang ? ' is-active' : ''}" data-lang="${lang}" aria-pressed="${lang === activePresenterLang}">
      ${PRESENTER_LANG_LABELS[lang]}
    </button>`).join('');
  presenterLangsEl.onclick = (e) => {
    const btn = e.target.closest('.lb-presenter-lang');
    if (btn) switchPresenterLang(btn.dataset.lang);
  };
}

function hideProductPanel() {
  panelEl?.classList.remove('is-open');
  panelEl?.setAttribute('aria-hidden', 'true');
}

function openPresenterDock(machine) {
  if (!presenterDockEl || !presenterVideoEl) return;
  const videos = getPresenterVideos(machine);
  const langs = presenterLangList(machine);
  if (langs.length === 0) return;

  hideProductPanel();
  activeMachineId = machine.id;
  if (!langs.includes(activePresenterLang)) activePresenterLang = langs[0];

  presenterTitleEl.textContent = machine.name;
  renderPresenterLangControls(machine);

  presenterStageEl?.style.removeProperty('--presenter-aspect');
  presenterVideoEl.pause();
  presenterVideoEl.setAttribute('playsinline', '');
  presenterVideoEl.setAttribute('webkit-playsinline', '');
  presenterVideoEl.playsInline = true;
  // 先有聲；若瀏覽器擋自動播放再退回靜音（仍可手動開聲）
  presenterVideoEl.muted = false;
  presenterVideoEl.src = videos[activePresenterLang];
  presenterVideoEl.load();

  presenterDockEl.classList.add('is-open');
  presenterDockEl.setAttribute('aria-hidden', 'false');
  document.body.classList.add('lb-presenter-active');

  if (presenterDockEl.classList.contains('is-positioned')) {
    const rect = presenterDockEl.getBoundingClientRect();
    applyPresenterPosition(rect.left, rect.top);
  }

  if (onFocusMachine) onFocusMachine(machine);

  // 必須在「點擊真人介紹」的使用者手勢內盡早 play；延到 loadeddata 時 iOS 常會擋有聲播放
  tryPlayPresenter();
  if (presenterVideoEl.readyState < 2) {
    presenterVideoEl.addEventListener('loadeddata', tryPlayPresenter, { once: true });
  }
}

function tryPlayPresenter() {
  if (!presenterVideoEl) return;
  const attempt = (muted) => {
    presenterVideoEl.muted = muted;
    const p = presenterVideoEl.play();
    if (p && typeof p.catch === 'function') {
      p.catch(() => {
        if (!muted) attempt(true);
      });
    }
  };
  attempt(false);
}

function switchPresenterLang(lang) {
  const machine = sceneMachines.find((m) => m.id === activeMachineId);
  const videos = getPresenterVideos(machine);
  if (!machine || !videos[lang] || lang === activePresenterLang) return;
  activePresenterLang = lang;

  const wasPlaying = !presenterVideoEl.paused && !presenterVideoEl.ended;
  const resumeAt = presenterVideoEl.currentTime || 0;

  presenterVideoEl.pause();
  presenterVideoEl.src = videos[lang];
  presenterVideoEl.load();
  const onReady = () => {
    presenterVideoEl.removeEventListener('loadedmetadata', onReady);
    // 切換語言時盡量沿用原播放進度
    if (Number.isFinite(presenterVideoEl.duration)) {
      try {
        presenterVideoEl.currentTime = Math.min(resumeAt, Math.max(0, presenterVideoEl.duration - 0.1));
      } catch { /* 忽略 seek 失敗 */ }
    }
    if (wasPlaying) presenterVideoEl.play().catch(() => {});
  };
  presenterVideoEl.addEventListener('loadedmetadata', onReady);

  presenterLangsEl?.querySelectorAll('.lb-presenter-lang').forEach((b) => {
    const active = b.dataset.lang === lang;
    b.classList.toggle('is-active', active);
    b.setAttribute('aria-pressed', String(active));
  });
}

function closePresenterDock() {
  if (!presenterDockEl || !presenterVideoEl) return;
  presenterDockEl.classList.remove('is-dragging', 'is-resizing');
  presenterVideoEl.dataset.ignoreError = '1';
  presenterVideoEl.pause();
  presenterVideoEl.removeAttribute('src');
  try {
    presenterVideoEl.load();
  } catch { /* ignore */ }
  // 下一幀再恢復，避免清 src 的 error 被誤判成未上傳
  requestAnimationFrame(() => {
    if (presenterVideoEl) presenterVideoEl.dataset.ignoreError = '0';
  });
  presenterDockEl.classList.remove('is-open');
  presenterDockEl.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('lb-presenter-active');
}

export function setSceneMachines(machines) {
  sceneMachines = machines ?? [];
  buildMachineBar();
}

function buildMachineBar() {
  if (!machineBarEl) return;
  machineBarEl.innerHTML = sceneMachines.map((m) => {
    const thumb = m.photos?.[0]?.thumb;
    const icon = thumb
      ? `<img class="lb-machine-card__icon" src="${thumb}" alt="" loading="lazy" decoding="async">`
      : `<span class="lb-machine-card__icon" aria-hidden="true"></span>`;
    return `
    <button type="button" class="lb-machine-card" data-machine-id="${m.id}" aria-label="${m.name}">
      ${icon}
      <span class="lb-machine-card__name">${m.name}</span>
      <span class="lb-machine-card__check" aria-hidden="true">✓</span>
    </button>`;
  }).join('');

  machineBarEl.onclick = (e) => {
    const btn = e.target.closest('.lb-machine-card');
    if (!btn) return;
    openMachinePanel(btn.dataset.machineId, { animate: true });
    setMachineBarExpanded(false);
  };
}

export function setMachineBarVisible(visible) {
  machineDockEl?.classList.toggle('is-available', visible);
  if (!visible) {
    setMachineBarExpanded(false);
    closeMachinePanel();
  } else {
    setMachineBarExpanded(false);
  }
}

export function openMachinePanel(machineId, { animate = false } = {}) {
  const machine = sceneMachines.find((m) => m.id === machineId);
  if (!machine || !panelEl) return;

  activeMachineId = machineId;
  panelTitleEl.textContent = machine.name;
  panelSubEl.textContent = machine.subtitle;
  panelIntroEl.textContent = machine.intro;

  renderGallery(machine);
  updatePresenterButton(machine);

  panelMenuEl.innerHTML = machine.menu.map((item) => {
    const tag = item.href ? 'a' : 'button';
    const href = item.href ? ` href="${item.href}" target="_blank" rel="noopener"` : ` type="button" data-action="${item.action}"`;
    return `<${tag} class="lb-panel-menu__item"${href}>
      <span>${item.label}</span>
      <i aria-hidden="true"></i>
    </${tag}>`;
  }).join('');

  panelMenuEl.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => handleMenuAction(btn.dataset.action, machine));
  });

  machineBarEl?.querySelectorAll('.lb-machine-card').forEach((card) => {
    card.classList.toggle('is-active', card.dataset.machineId === machineId);
  });

  panelEl.classList.add('is-open');
  panelEl.setAttribute('aria-hidden', 'false');

  if (animate && onFocusMachine) {
    onFocusMachine(machine);
  }
}

export function closeMachinePanel() {
  activeMachineId = null;
  closePresenterDock();
  panelEl?.classList.remove('is-open');
  panelEl?.setAttribute('aria-hidden', 'true');
  machineBarEl?.querySelectorAll('.lb-machine-card').forEach((c) => c.classList.remove('is-active'));
}

export function getActiveMachineId() {
  return activeMachineId;
}

export function buildMachinePinHtml(name = '') {
  return `
    <div class="machine-pin" aria-hidden="true">
      <span class="machine-pin__label">${name}</span>
      <span class="machine-pin__stem"></span>
      <span class="machine-pin__dot">
        <span class="machine-pin__pulse"></span>
        <span class="machine-pin__pulse machine-pin__pulse--delay"></span>
        <svg class="machine-pin__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="3.2" fill="#fbbf24"/>
          <path d="M12 2.5v4M12 17.5v4M2.5 12h4M17.5 12h4" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </span>
    </div>`;
}

export function buildMachineMarkers(machines) {
  return machines.map((m) => ({
    id: `machine-${m.id}`,
    html: buildMachinePinHtml(m.name),
    position: m.position,
    size: { width: 132, height: 96 },
    anchor: 'bottom center',
    className: 'machine-pin-wrap',
    tooltip: {
      content: `${m.name} · 點擊查看`,
      className: 'lb-tooltip',
      position: 'top center',
      trigger: 'hover',
    },
    data: { machineId: m.id, type: 'machine' },
  }));
}

function handleMenuAction(action, machine) {
  if (action === 'images') {
    if (currentMainSrc) {
      openLightbox(currentMainSrc);
    } else {
      window.alert(`${machine.name} 尚無產品照片。`);
    }
    return;
  }
  if (action === 'catalog') {
    if (machine.catalogUrl) {
      window.open(machine.catalogUrl, '_blank', 'noopener');
    } else {
      window.alert(`${machine.name} 尚未上傳產品型錄。`);
    }
    return;
  }
  if (action === 'cases') {
    if (machine.casesUrl) {
      window.open(machine.casesUrl, '_blank', 'noopener');
    } else {
      window.alert(`${machine.name} 尚未設定應用案例連結。`);
    }
    return;
  }
}
