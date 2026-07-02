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

const PHOTO_BASE = './media/machines/';
const PRESENTER_BASE = './media/presenter/';

let sceneMachines = [];
let activeMachineId = null;
let onFocusMachine = null;
let currentMainSrc = '';
let machineBarExpanded = false;

function setMachineBarExpanded(expanded) {
  machineBarExpanded = expanded;
  machineDockEl?.classList.toggle('is-expanded', expanded);
  machineToggleEl?.setAttribute('aria-expanded', String(expanded));
}

export function collapseMachineBar() {
  setMachineBarExpanded(false);
}

export function expandMachineBar() {
  if (sceneMachines.length) setMachineBarExpanded(true);
}

export function initMachinePanel({ focusMachine }) {
  onFocusMachine = focusMachine;
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
  presenterCloseEl?.addEventListener('click', closePresenterDock);
  presenterVideoEl?.addEventListener('error', () => {
    window.alert('此機台的真人介紹影片尚未上傳，請將影片放入 media/presenter/ 資料夾。');
    closePresenterDock();
  });
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
    currentMainSrc = PHOTO_BASE + photo.full;
    if (galleryMainImg) {
      galleryMainImg.src = currentMainSrc;
      galleryMainImg.alt = `${machine.name} 產品照片`;
    }
    galleryThumbsEl?.querySelectorAll('.lb-gallery__thumb').forEach((t) => {
      t.classList.toggle('is-active', t.dataset.full === photo.full);
    });
  };

  if (galleryThumbsEl) {
    galleryThumbsEl.innerHTML = photos.map((p) => `
      <button type="button" class="lb-gallery__thumb" data-full="${p.full}" aria-label="${machine.name} 照片">
        <img src="${PHOTO_BASE + p.thumb}" alt="" loading="lazy" decoding="async">
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

function updatePresenterButton(machine) {
  if (!presenterBtnEl) return;
  const hasVideo = Boolean(machine?.presenterVideo);
  presenterBtnEl.hidden = !hasVideo;
}

function hideProductPanel() {
  panelEl?.classList.remove('is-open');
  panelEl?.setAttribute('aria-hidden', 'true');
}

function openPresenterDock(machine) {
  if (!presenterDockEl || !presenterVideoEl || !machine?.presenterVideo) return;

  hideProductPanel();
  activeMachineId = machine.id;

  presenterTitleEl.textContent = machine.name;
  presenterVideoEl.pause();
  presenterVideoEl.src = PRESENTER_BASE + machine.presenterVideo;
  presenterVideoEl.load();

  presenterDockEl.classList.add('is-open');
  presenterDockEl.setAttribute('aria-hidden', 'false');
  document.body.classList.add('lb-presenter-active');

  if (onFocusMachine) onFocusMachine(machine);

  presenterVideoEl.play().catch(() => {
    /* 瀏覽器可能阻擋自動播放，使用者可手動按播放 */
  });
}

function closePresenterDock() {
  if (!presenterDockEl || !presenterVideoEl) return;
  presenterVideoEl.pause();
  presenterVideoEl.removeAttribute('src');
  presenterVideoEl.load();
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
      ? `<img class="lb-machine-card__icon" src="${PHOTO_BASE + thumb}" alt="" loading="lazy" decoding="async">`
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
  const messages = {
    catalog: `${machine.name} 型錄下載連結可於 machines.js 設定。`,
    cases: `${machine.name} 應用案例內容可於 machines.js 設定。`,
  };
  if (messages[action]) {
    window.alert(messages[action]);
  }
}
