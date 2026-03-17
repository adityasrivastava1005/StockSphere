// ui.js — shared utilities: API, toast, modal, navigation, helpers
const API_BASE = (window.location.origin === 'http://localhost:8000')
  ? ''
  : 'http://localhost:8000';

// ── API CLIENT ────────────────────────────────────────────────────────
const api = {
  _token: null,
  _cache: new Map(),
  _cacheTtlMs: 10000,

  setToken(t) {
    this._token = t;
    this._cache.clear();
    if (t) localStorage.setItem('ss_token', t); else localStorage.removeItem('ss_token');
  },
  loadToken()  { this._token = localStorage.getItem('ss_token') || null; },

  _cacheKey(method, path) {
    return `${method}:${path}`;
  },

  _getCached(method, path) {
    if (method !== 'GET') return null;
    const key = this._cacheKey(method, path);
    const cached = this._cache.get(key);
    if (!cached) return null;
    if ((Date.now() - cached.time) > this._cacheTtlMs) {
      this._cache.delete(key);
      return null;
    }
    return cached.value;
  },

  _setCached(method, path, value) {
    if (method !== 'GET' || !value?.ok) return;
    const key = this._cacheKey(method, path);
    this._cache.set(key, { time: Date.now(), value });
  },

  _invalidateCache() {
    this._cache.clear();
  },

  async _req(method, path, body) {
    const cached = this._getCached(method, path);
    if (cached) return cached;

    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (this._token) opts.headers['Authorization'] = `Bearer ${this._token}`;
    if (body) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(API_BASE + path, opts);
      const data = await res.json();
      const result = { ok: res.ok, status: res.status, data };
      this._setCached(method, path, result);
      if (method !== 'GET' && res.ok) this._invalidateCache();
      return result;
    } catch(e) {
      return { ok: false, status: 0, data: { error: 'Network error. Is the server running?' } };
    }
  },

  get(path)         { return this._req('GET', path); },
  post(path, body)  { return this._req('POST', path, body); },
  put(path, body)   { return this._req('PUT', path, body); },
  delete(path)      { return this._req('DELETE', path); },
};

// ── TOAST ─────────────────────────────────────────────────────────────
function toast(msg, type = 'success', duration = 3200) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-stack').appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── MODAL ─────────────────────────────────────────────────────────────
const modal = {
  _el: null,
  _inner: null,

  init() {
    this._el = document.getElementById('modal-overlay');
    this._inner = document.getElementById('modal-container');
    this._el.addEventListener('click', e => { if (e.target === this._el) this.close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') this.close(); });
  },

  open(html) {
    this._inner.innerHTML = html;
    this._el.classList.add('open');
  },

  close() {
    this._el.classList.remove('open');
    this._inner.innerHTML = '';
  },
};

// ── NAVIGATION ────────────────────────────────────────────────────────
const nav = {
  _current: null,

  go(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const pageEl = document.getElementById(`page-${page}`);
    if (!pageEl) return;
    pageEl.classList.add('active');
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
    this._current = page;
    localStorage.setItem('ss_page', page);
    const renderers = {
      dashboard: () => dashboard.render(),
      products:  () => inventory.renderProducts(),
      inward:    () => inventory.renderInward(),
      outward:   () => inventory.renderOutward(),
      alerts:    () => inventory.renderAlerts(),
      reports:   () => reports.render(),
      audit:     () => reports.renderAudit(),
      users:     () => reports.renderUsers(),
    };
    renderers[page]?.();
  },
};

// ── HELPERS ───────────────────────────────────────────────────────────
function fmtMoney(n) {
  n = parseFloat(n) || 0;
  return '₹' + n.toLocaleString('en-IN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function fmtNum(n) { return (n || 0).toLocaleString('en-IN'); }

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function fmtDateTime(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function txnId(id) { return 'TXN-' + String(id).padStart(4, '0'); }

function todayStr() { return new Date().toISOString().split('T')[0]; }

function stockBadge(stock, reorder) {
  if (stock < reorder / 2) return '<span class="badge badge-red">Critical</span>';
  if (stock <= reorder)    return '<span class="badge badge-amber">Low</span>';
  return '<span class="badge badge-green">In Stock</span>';
}

function roleBadge(role) {
  return `<span class="badge role-${role}">${role.charAt(0).toUpperCase() + role.slice(1)}</span>`;
}

function auditColor(action) {
  const map = {
    STOCK_INWARD: '#1D9E75', STOCK_OUTWARD: '#BA7517',
    PRODUCT_ADD: '#185FA5', PRODUCT_UPDATE: '#185FA5', PRODUCT_REMOVE: '#C94040',
    USER_LOGIN: '#7F77DD', USER_LOGOUT: '#888780', USER_REGISTER: '#7F77DD',
    LOW_STOCK_ALERT: '#C94040', USER_UPDATE: '#185FA5',
  };
  return map[action] || '#888780';
}

function initials(name) {
  return (name || '').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function setLoading(containerId, msg = 'Loading...') {
  document.getElementById(containerId).innerHTML =
    `<div class="page-loading"><div class="spinner"></div>${msg}</div>`;
}

function handleApiError(res, fallback = 'Something went wrong.') {
  const msg = res.data?.error || fallback;
  toast(msg, 'error');
  return msg;
}

// show / hide error bar inside a modal
function showErr(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}
function hideErr(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}
