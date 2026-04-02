// auth.js — login, register, session, topbar, logout
const auth = {
  user: null,

  async init() {
    api.loadToken();
    if (!api._token) return false;
    const res = await api.get('/api/auth/me');
    if (!res.ok) { api.setToken(null); return false; }
    this.user = {
      ...res.data,
      id: res.data?.id ?? res.data?.user_id,
    };
    return true;
  },

  async login(username, password) {
    const res = await api.post('/api/auth/login', { username, password });
    if (!res.ok) return res.data.error || 'Login failed.';
    api.setToken(res.data.token);
    this.user = res.data.user;
    return null;
  },

  async register(name, username, password, role) {
    const res = await api.post('/api/auth/register', { name, username, password, role });
    if (!res.ok) return res.data.error || 'Registration failed.';
    api.setToken(res.data.token);
    this.user = res.data.user;
    return null;
  },

  async logout() {
    await api.post('/api/auth/logout');
    api.setToken(null);
    this.user = null;
    localStorage.removeItem('ss_page');
    showAuthScreen();
  },

  can(minRole) {
    const rank = { admin: 4, manager: 3, finance: 2, staff: 1 };
    return (rank[this.user?.role] || 0) >= (rank[minRole] || 99);
  },

  isAdmin() { return this.user?.role === 'admin'; },

  openChangeUsername() {
    modal.open(`
      <div class="modal">
        <div class="modal-title">Change username</div>
        <div class="form-group" style="margin-bottom:13px">
          <label class="form-label">Current username</label>
          <input class="form-input" id="cu-current-username" value="${this.user?.username || ''}" disabled>
        </div>
        <div class="form-group" style="margin-bottom:13px">
          <label class="form-label">New username</label>
          <input class="form-input" id="cu-new-username" placeholder="Enter new username">
        </div>
        <div class="form-group" style="margin-bottom:16px">
          <label class="form-label">Current password</label>
          <input class="form-input" type="password" id="cu-current-password" placeholder="Enter current password">
          <label class="show-password-toggle">
            <input type="checkbox" onchange="togglePasswordField('cu-current-password', this.checked)">
            Show password
          </label>
        </div>
        <div class="error-bar" id="cu-err"></div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="auth.submitChangeUsername()">Update username</button>
        </div>
      </div>`);
  },

  async submitChangeUsername() {
    hideErr('cu-err');
    const newUsername = document.getElementById('cu-new-username').value.trim();
    const currentPw = document.getElementById('cu-current-password').value;
    if (!newUsername || !currentPw) { showErr('cu-err', 'All fields are required.'); return; }
    if (newUsername === this.user?.username) { showErr('cu-err', 'New username must be different.'); return; }
    const res = await api.post('/api/auth/change-username', { new_username: newUsername, current_password: currentPw });
    if (!res.ok) { showErr('cu-err', res.data.error || 'Failed to update username.'); return; }
    this.user = { ...this.user, username: res.data.username || newUsername };
    modal.close();
    toast('Username updated successfully.', 'success');
  },

  openChangePassword() {
    modal.open(`
      <div class="modal">
        <div class="modal-title">Change password</div>
        <div class="form-group" style="margin-bottom:13px">
          <label class="form-label">Current password</label>
          <input class="form-input" type="password" id="cp-current" placeholder="Enter current password">
          <label class="show-password-toggle">
            <input type="checkbox" onchange="togglePasswordField('cp-current', this.checked)">
            Show password
          </label>
        </div>
        <div class="form-group" style="margin-bottom:13px">
          <label class="form-label">New password</label>
          <input class="form-input" type="password" id="cp-new" placeholder="At least 6 characters">
          <label class="show-password-toggle">
            <input type="checkbox" onchange="togglePasswordField('cp-new', this.checked)">
            Show password
          </label>
        </div>
        <div class="form-group" style="margin-bottom:16px">
          <label class="form-label">Confirm new password</label>
          <input class="form-input" type="password" id="cp-confirm" placeholder="Repeat new password">
          <label class="show-password-toggle">
            <input type="checkbox" onchange="togglePasswordField('cp-confirm', this.checked)">
            Show password
          </label>
        </div>
        <div class="error-bar" id="cp-err"></div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="auth.submitChangePassword()">Update password</button>
        </div>
      </div>`);
  },

  async submitChangePassword() {
    hideErr('cp-err');
    const current = document.getElementById('cp-current').value;
    const newPw   = document.getElementById('cp-new').value;
    const confirm = document.getElementById('cp-confirm').value;
    if (!current || !newPw || !confirm) { showErr('cp-err', 'All fields are required.'); return; }
    if (newPw.length < 6) { showErr('cp-err', 'New password must be at least 6 characters.'); return; }
    if (newPw !== confirm) { showErr('cp-err', 'New passwords do not match.'); return; }
    const res = await api.post('/api/auth/change-password', { current_password: current, new_password: newPw });
    if (!res.ok) { showErr('cp-err', res.data.error || 'Failed to update password.'); return; }
    modal.close();
    toast('Password updated successfully.', 'success');
  },
};

// ── AUTH SCREEN ───────────────────────────────────────────────────────
function resetAuthForms() {
  const ids = ['login-username', 'login-password', 'reg-name', 'reg-username', 'reg-password'];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });

  hideErr('login-err');
  hideErr('reg-err');

  document.querySelectorAll('#auth-screen input[type="checkbox"]').forEach(cb => {
    cb.checked = false;
  });

  ['login-password', 'reg-password'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.type = 'password';
  });

  const role = document.getElementById('reg-role');
  if (role) role.value = 'staff';

  switchAuthTab('login');
}

function showAuthScreen() {
  resetAuthForms();
  document.getElementById('auth-screen').style.display = 'flex';
  document.getElementById('app-screen').style.display = 'none';
}

function showAppScreen() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'flex';
  setupTopbar();
  setupSidebar();
  const savedPage = localStorage.getItem('ss_page') || 'dashboard';
  const page = (savedPage === 'users' && !auth.isAdmin()) ? 'dashboard' : savedPage;
  nav.go(page);
}

function setupTopbar() {
  const u = auth.user;
  document.getElementById('tb-avatar').textContent = initials(u.name);
  document.getElementById('tb-name').textContent = u.name;
  document.getElementById('tb-role').textContent = (u.role || '').replace(/^./, c => c.toUpperCase());
}

function setupSidebar() {
  const adminOnly = document.querySelectorAll('.nav-admin-only');
  adminOnly.forEach(el => el.classList.toggle('hidden', !auth.isAdmin()));
  document.querySelectorAll('.nav-item').forEach(item => {
    const label = item.textContent.replace(/\s+/g, ' ').trim();
    if (label) item.title = label;
  });
  toggleSidebar(localStorage.getItem('ss_sidebar_collapsed') === '1');
}

function toggleSidebar(forceCollapsed) {
  const appScreen = document.getElementById('app-screen');
  if (!appScreen) return;

  const shouldCollapse =
    typeof forceCollapsed === 'boolean'
      ? forceCollapsed
      : !appScreen.classList.contains('sidebar-collapsed');

  appScreen.classList.toggle('sidebar-collapsed', shouldCollapse);
  localStorage.setItem('ss_sidebar_collapsed', shouldCollapse ? '1' : '0');

  const btn = document.getElementById('sidebar-toggle-btn');
  if (btn) {
    const label = shouldCollapse ? 'Expand sidebar' : 'Collapse sidebar';
    btn.setAttribute('aria-pressed', shouldCollapse ? 'true' : 'false');
    btn.setAttribute('aria-label', label);
    btn.title = label;
  }
}

// ── TAB TOGGLE ────────────────────────────────────────────────────────
function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.getElementById('login-panel').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-panel').classList.toggle('hidden', tab !== 'register');
}

function fillDemo(u, p) {
  document.getElementById('login-username').value = u;
  document.getElementById('login-password').value = p;
  document.getElementById('login-username').dispatchEvent(new Event('input'));
}

function togglePasswordField(fieldId, show) {
  const input = document.getElementById(fieldId);
  if (!input) return;
  input.type = show ? 'text' : 'password';
}

// ── LOGIN HANDLER ─────────────────────────────────────────────────────
async function handleLogin() {
  hideErr('login-err');
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  if (!username || !password) { showErr('login-err', 'Enter username and password.'); return; }

  const btn = document.getElementById('login-btn');
  btn.disabled = true; btn.textContent = 'Signing in…';

  const err = await auth.login(username, password);
  btn.disabled = false; btn.textContent = 'Sign in';

  if (err) { showErr('login-err', err); return; }
  showAppScreen();
}

// ── REGISTER HANDLER ──────────────────────────────────────────────────
async function handleRegister() {
  hideErr('reg-err');
  const name     = document.getElementById('reg-name').value.trim();
  const username = document.getElementById('reg-username').value.trim();
  const password = document.getElementById('reg-password').value;
  const role     = document.getElementById('reg-role').value;

  if (!name || !username || !password) { showErr('reg-err', 'All fields are required.'); return; }
  if (password.length < 6)             { showErr('reg-err', 'Password must be at least 6 characters.'); return; }

  const btn = document.getElementById('reg-btn');
  btn.disabled = true; btn.textContent = 'Creating account…';

  const err = await auth.register(name, username, password, role);
  btn.disabled = false; btn.textContent = 'Create account';

  if (err) { showErr('reg-err', err); return; }
  showAppScreen();
}

// ── KEYBOARD HELPERS ──────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const loginPanel = document.getElementById('login-panel');
    const regPanel   = document.getElementById('register-panel');
    if (loginPanel && !loginPanel.classList.contains('hidden') &&
        document.activeElement?.closest('#login-panel')) {
      handleLogin();
    } else if (regPanel && !regPanel.classList.contains('hidden') &&
               document.activeElement?.closest('#register-panel')) {
      handleRegister();
    }
  }
});
