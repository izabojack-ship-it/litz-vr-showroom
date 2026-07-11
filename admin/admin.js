const TOKEN_KEY = 'litz-vr-admin-token';

const loginView = document.getElementById('login-view');
const dashboardView = document.getElementById('dashboard-view');
const loginForm = document.getElementById('login-form');
const loginPassword = document.getElementById('login-password');
const loginError = document.getElementById('login-error');
const machineListEl = document.getElementById('machine-list');
const metaInfoEl = document.getElementById('meta-info');
const emptyStateEl = document.getElementById('empty-state');
const editForm = document.getElementById('edit-form');
const editTitleEl = document.getElementById('edit-title');
const editSubtitleEl = document.getElementById('edit-subtitle');
const fieldIntro = document.getElementById('field-intro');
const fieldCases = document.getElementById('field-cases');
const fieldContact = document.getElementById('field-contact');
const photoListEl = document.getElementById('photo-list');
const catalogInfoEl = document.getElementById('catalog-info');
const PRESENTER_LANGS = [
  { code: 'zh', name: '中文' },
  { code: 'en', name: 'English' },
  { code: 'th', name: 'ไทย' },
];
const saveStatusEl = document.getElementById('save-status');
const publishBtn = document.getElementById('publish-btn');
const logoutBtn = document.getElementById('logout-btn');
const uploadPhoto = document.getElementById('upload-photo');
const uploadCatalog = document.getElementById('upload-catalog');
const passwordForm = document.getElementById('password-form');
const pwdCurrent = document.getElementById('pwd-current');
const pwdNew = document.getElementById('pwd-new');
const pwdConfirm = document.getElementById('pwd-confirm');
const passwordStatusEl = document.getElementById('password-status');

let machines = [];
let activeMachineId = null;
let activeContent = null;

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    setToken(null);
    showLogin();
    throw new Error('登入已失效');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d) => d.msg || d.message).join('；')
      : (data.detail || `請求失敗 (${res.status})`);
    if (res.status === 501 || res.status === 405) {
      throw new Error('伺服器模式錯誤，請關閉舊視窗後重新執行 launch.bat');
    }
    throw new Error(detail);
  }
  return data;
}

function showLogin() {
  loginView.hidden = false;
  dashboardView.hidden = true;
}

function showDashboard() {
  loginView.hidden = true;
  dashboardView.hidden = false;
}

function assetUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith('media/')) return `/${path}`;
  return `/content/files/${path}`;
}

function groupMachines(items) {
  const groups = new Map();
  for (const item of items) {
    if (!groups.has(item.zoneId)) groups.set(item.zoneId, []);
    groups.get(item.zoneId).push(item);
  }
  return groups;
}

function renderMachineList() {
  machineListEl.innerHTML = '';
  for (const [zoneId, items] of groupMachines(machines)) {
    const group = document.createElement('div');
    group.className = 'admin-machine-group';
    group.innerHTML = `<p class="admin-machine-group__title">${items[0].zoneTitle || zoneId}</p>`;
    for (const item of items) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'admin-machine-item';
      btn.dataset.id = item.id;
      btn.innerHTML = `${item.name}<small>${item.subtitle || ''}</small>`;
      btn.classList.toggle('is-active', item.id === activeMachineId);
      btn.addEventListener('click', () => selectMachine(item.id));
      group.appendChild(btn);
    }
    machineListEl.appendChild(group);
  }
}

function fillForm(layout, content) {
  editTitleEl.textContent = layout.name;
  editSubtitleEl.textContent = `${layout.zoneTitle || layout.zoneId} · ${layout.subtitle || ''}`;
  fieldIntro.value = content.intro || '';
  fieldCases.value = content.casesUrl || '';
  fieldContact.value = content.contactUrl || 'https://www.litz.com.tw/';
  renderPresenterLangs(content);
  catalogInfoEl.textContent = content.catalogUrl
    ? `已上傳：${content.catalogUrl}`
    : '尚未上傳';
  renderPhotos(content.photos || []);
}

function getPresenterVideos(content) {
  const videos = { ...(content?.presenterVideos || {}) };
  // 舊資料相容：單一 presenterVideo 視為中文
  if (!videos.zh && content?.presenterVideo) videos.zh = content.presenterVideo;
  return videos;
}

function renderPresenterLangs(content) {
  const videos = getPresenterVideos(content);
  for (const { code } of PRESENTER_LANGS) {
    const info = document.getElementById(`presenter-info-${code}`);
    const del = document.getElementById(`delete-presenter-${code}`);
    const src = videos[code];
    if (info) info.textContent = src ? `已上傳：${src}` : '尚未上傳';
    if (del) del.hidden = !src;
  }
}

function renderPhotos(photos) {
  photoListEl.innerHTML = photos.map((photo, index) => {
    const src = assetUrl(typeof photo === 'string' ? photo : photo.thumb || photo.full);
    return `
      <div class="admin-photo">
        <img src="${src}" alt="">
        <button type="button" data-index="${index}" aria-label="刪除照片">×</button>
      </div>`;
  }).join('');
  photoListEl.querySelectorAll('button[data-index]').forEach((btn) => {
    btn.addEventListener('click', () => deletePhoto(Number(btn.dataset.index)));
  });
}

async function loadDashboard() {
  const data = await api('/api/admin/machines');
  machines = data.machines;
  metaInfoEl.textContent = `草稿版本 ${data.draftVersion} · 已發布版本 ${data.publishedVersion} · 更新 ${data.updatedAt || '-'}`;
  renderMachineList();
  if (activeMachineId) {
    const item = machines.find((m) => m.id === activeMachineId);
    if (item) {
      activeContent = item.draft;
      fillForm(item, item.draft);
    }
  }
}

async function selectMachine(id) {
  activeMachineId = id;
  const item = machines.find((m) => m.id === id);
  if (!item) return;
  activeContent = item.draft;
  emptyStateEl.hidden = true;
  editForm.hidden = false;
  fillForm(item, item.draft);
  renderMachineList();
}

function currentPayload() {
  return {
    intro: fieldIntro.value.trim(),
    photos: activeContent?.photos || [],
    presenterVideo: activeContent?.presenterVideo || '',
    presenterVideos: activeContent?.presenterVideos || {},
    catalogUrl: activeContent?.catalogUrl || '',
    casesUrl: fieldCases.value.trim(),
    contactUrl: fieldContact.value.trim() || 'https://www.litz.com.tw/',
  };
}

async function saveDraft() {
  if (!activeMachineId) return;
  const data = await api(`/api/admin/machines/${activeMachineId}`, {
    method: 'PUT',
    body: currentPayload(),
  });
  activeContent = data.content;
  saveStatusEl.hidden = false;
  saveStatusEl.textContent = '草稿已儲存';
  await loadDashboard();
}

async function uploadFile(kind, file, lang) {
  if (!activeMachineId || !file) return;
  const form = new FormData();
  form.append('file', file);
  let url = `/api/admin/machines/${activeMachineId}/upload?kind=${kind}`;
  if (lang) url += `&lang=${lang}`;
  const data = await api(url, { method: 'POST', body: form });
  activeContent = data.content;
  fillForm(machines.find((m) => m.id === activeMachineId), activeContent);
  saveStatusEl.hidden = false;
  saveStatusEl.style.color = '';
  saveStatusEl.textContent = '檔案已上傳並存入草稿';
  await loadDashboard();
}

async function deletePresenter(lang) {
  if (!activeMachineId) return;
  if (!window.confirm('確定刪除這段真人介紹影片？')) return;
  const data = await api(`/api/admin/machines/${activeMachineId}/presenter/${lang}`, {
    method: 'DELETE',
  });
  activeContent = data.content;
  fillForm(machines.find((m) => m.id === activeMachineId), activeContent);
  saveStatusEl.hidden = false;
  saveStatusEl.style.color = '';
  saveStatusEl.textContent = '影片已刪除並存入草稿';
  await loadDashboard();
}

async function deletePhoto(index) {
  if (!activeMachineId) return;
  if (!window.confirm('確定刪除這張照片？')) return;
  const data = await api(`/api/admin/machines/${activeMachineId}/photos/${index}`, {
    method: 'DELETE',
  });
  activeContent = data.content;
  fillForm(machines.find((m) => m.id === activeMachineId), activeContent);
  await loadDashboard();
}

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  loginError.hidden = true;
  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: { password: loginPassword.value },
    });
    setToken(data.token);
    showDashboard();
    await loadDashboard();
  } catch (err) {
    loginError.hidden = false;
    loginError.textContent = err.message || '登入失敗';
  }
});

editForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await saveDraft();
  } catch (err) {
    saveStatusEl.hidden = false;
    saveStatusEl.style.color = '#ef6b6b';
    saveStatusEl.textContent = err.message;
  }
});

uploadPhoto.addEventListener('change', () => uploadFile('photo', uploadPhoto.files[0]));
uploadCatalog.addEventListener('change', () => uploadFile('catalog', uploadCatalog.files[0]));

for (const { code } of PRESENTER_LANGS) {
  const input = document.getElementById(`upload-presenter-${code}`);
  input?.addEventListener('change', () => {
    uploadFile('presenter', input.files[0], code).catch((err) => {
      saveStatusEl.hidden = false;
      saveStatusEl.style.color = '#ef6b6b';
      saveStatusEl.textContent = err.message;
    });
    input.value = '';
  });
  const del = document.getElementById(`delete-presenter-${code}`);
  del?.addEventListener('click', () => {
    deletePresenter(code).catch((err) => window.alert(err.message));
  });
}

publishBtn.addEventListener('click', async () => {
  if (!window.confirm('確定發布？訪客將立即看到最新內容。')) return;
  try {
    const data = await api('/api/admin/publish', { method: 'POST' });
    saveStatusEl.hidden = false;
    saveStatusEl.style.color = '#5ecf8f';
    saveStatusEl.textContent = `已發布（版本 ${data.version}）`;
    await loadDashboard();
  } catch (err) {
    window.alert(err.message);
  }
});

logoutBtn.addEventListener('click', () => {
  setToken(null);
  activeMachineId = null;
  showLogin();
});

passwordForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  passwordStatusEl.hidden = true;
  passwordStatusEl.style.color = '#5ecf8f';
  try {
    const data = await api('/api/admin/change-password', {
      method: 'POST',
      body: {
        currentPassword: pwdCurrent.value,
        newPassword: pwdNew.value,
        confirmPassword: pwdConfirm.value,
      },
    });
    pwdCurrent.value = '';
    pwdNew.value = '';
    pwdConfirm.value = '';
    passwordStatusEl.hidden = false;
    passwordStatusEl.textContent = `密碼已更新（${data.passwordUpdatedAt || '剛剛'}）`;
  } catch (err) {
    passwordStatusEl.hidden = false;
    passwordStatusEl.style.color = '#ef6b6b';
    passwordStatusEl.textContent = err.message || '密碼更新失敗';
  }
});

(async function init() {
  const token = getToken();
  if (!token) {
    showLogin();
    return;
  }
  try {
    await api('/api/auth/check');
    showDashboard();
    await loadDashboard();
    try {
      const health = await fetch('/api/health').then((r) => r.json());
      const warn = document.getElementById('storage-warning');
      if (warn && health.ephemeralStorage) {
        warn.hidden = false;
        warn.textContent = health.warning || '警告：上傳檔案未寫入持久碟，重新部署後會消失。';
      }
    } catch { /* ignore */ }
  } catch {
    showLogin();
  }
})();
