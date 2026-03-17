// reports.js — valuation, ledger, aging, audit trail, users
const reports = {

  // ── REPORTS ───────────────────────────────────────────────────────
  async render() {
    const [val, ledger, aging] = await Promise.all([
      api.get('/api/reports/valuation'),
      api.get('/api/reports/ledger'),
      api.get('/api/reports/aging'),
    ]);

    if (!val.ok || !ledger.ok) { handleApiError(val.ok ? ledger : val); return; }

    // Summary metrics
    const totalValue  = ledger.data.reduce((s, r) => s + (r.valuation || 0), 0);
    const lowCount    = ledger.data.filter(r => r.current_stock <= r.reorder_level).length;
    document.getElementById('r-products').textContent = ledger.data.length;
    document.getElementById('r-value').textContent    = fmtMoney(totalValue);
    document.getElementById('r-low').textContent      = lowCount;

    // Category valuation table
    document.getElementById('valuation-tbody').innerHTML = val.data.map(r => `<tr>
      <td>${r.category}</td>
      <td class="td-muted">${r.item_count}</td>
      <td class="td-muted">${fmtNum(r.total_qty)}</td>
      <td class="fw-600">${fmtMoney(r.total_value)}</td>
    </tr>`).join('');

    // Aging bars
    if (aging.ok) {
      document.getElementById('aging-list').innerHTML = aging.data.map(p => {
        const pct   = Math.min(100, Math.round((p.current_stock / p.reorder_level) * 100));
        const color = pct < 30 ? 'var(--danger)' : pct < 70 ? 'var(--warning)' : 'var(--brand)';
        return `<div>
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
            <span style="color:var(--text2)">${p.name}</span>
            <span style="font-weight:600;color:${color}">${pct}%</span>
          </div>
          <div class="prog-track"><div class="prog-fill" style="width:${pct}%;background:${color}"></div></div>
        </div>`;
      }).join('');
    }

    // Full ledger
    document.getElementById('ledger-tbody').innerHTML = ledger.data.map(r => `<tr>
      <td class="td-mono">${r.sku}</td>
      <td class="td-bold">${r.name}</td>
      <td><span class="badge badge-gray">${r.category}</span></td>
      <td class="td-muted">${r.opening_stock}</td>
      <td class="color-green fw-600">+${r.total_in}</td>
      <td class="color-red fw-600">-${r.total_out}</td>
      <td class="fw-600">${r.current_stock}</td>
      <td class="td-muted">₹${(r.unit_price||0).toLocaleString('en-IN')}</td>
      <td class="fw-600">${fmtMoney(r.valuation)}</td>
    </tr>`).join('');

    this._ledgerData = ledger.data;
  },

  _ledgerData: [],

  exportCSV() {
    const rows = [['SKU','Product','Category','Opening','Total In','Total Out','Closing','Unit Price','Valuation']];
    this._ledgerData.forEach(r => rows.push([
      r.sku, r.name, r.category, r.opening_stock, r.total_in, r.total_out,
      r.current_stock, r.unit_price, (r.valuation || 0).toFixed(2)
    ]));
    const csv  = rows.map(r => r.map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `stocksphere_ledger_${todayStr()}.csv`;
    a.click();
    toast('Ledger exported as CSV.', 'success');
  },

  // ── AUDIT ─────────────────────────────────────────────────────────
  async renderAudit() {
    const search = document.getElementById('audit-search')?.value || '';
    let url = '/api/audit';
    if (search) url += `?search=${encodeURIComponent(search)}`;
    const res = await api.get(url);
    if (!res.ok) { handleApiError(res); return; }
    const logs = res.data;
    const container = document.getElementById('audit-container');
    if (!logs.length) {
      container.innerHTML = '<div class="empty"><div class="empty-text">No audit logs yet</div></div>';
      return;
    }
    container.innerHTML = logs.map(l => `
      <div class="audit-item">
        <div class="audit-dot" style="background:${auditColor(l.action)}"></div>
        <div class="audit-body">
          <div class="audit-action">${l.action.replace(/_/g,' ')}: <span style="font-weight:400">${l.detail}</span></div>
          <div class="audit-meta">by ${l.username || 'system'} · ${fmtDateTime(l.created_at)}</div>
        </div>
        <span class="badge badge-gray" style="font-size:10px;flex-shrink:0">${l.action}</span>
      </div>`).join('');
  },

  // ── USERS ─────────────────────────────────────────────────────────
  async renderUsers() {
    const res = await api.get('/api/users');
    if (!res.ok) { handleApiError(res); return; }
    const users = res.data;
    const roleColors = {
      admin:   ['#EEEDFE','#26215C'],
      manager: ['#E6F1FB','#042C53'],
      staff:   ['#E1F5EE','#0F6E56'],
      finance: ['#FAEEDA','#412402'],
    };
    document.getElementById('users-grid').innerHTML = users.map(u => {
      const [bg, fg] = roleColors[u.role] || ['#F1EFE8','#2C2C2A'];
      const isMe = u.id === auth.user?.id;
      const canToggle = !isMe;
      const canDelete = !isMe && u.role !== 'admin';
      return `<div class="user-card" style="${!u.is_active?'opacity:0.5':''}">
        <div class="user-card-head">
          <div class="user-avatar" style="background:${bg};color:${fg}">${initials(u.name)}</div>
          <div style="flex:1">
            <div class="td-bold">${u.name}</div>
            ${roleBadge(u.role)}
          </div>
          ${(canToggle || canDelete) ? `<div class="td-actions">
            ${canToggle ? `<button class="action-btn ${u.is_active?'danger':''}" onclick="reports.toggleUser(${u.id},'${u.name}')">${u.is_active?'Disable':'Enable'}</button>` : ''}
            ${canDelete ? `<button class="action-btn danger" onclick="reports.deleteUser(${u.id},'${u.name}')">Delete</button>` : ''}
          </div>` : ''}
        </div>
        <div style="font-size:12px;color:var(--text3)">@${u.username}</div>
        <div style="font-size:11px;color:var(--text3);margin-top:3px">Joined: ${fmtDate(u.created_at)}</div>
        ${!u.is_active ? '<div style="margin-top:6px"><span class="badge badge-red">Inactive</span></div>' : ''}
      </div>`;
    }).join('');
  },

  async toggleUser(id, name) {
    const res = await api.put(`/api/users/${id}/toggle`);
    if (!res.ok) { toast(res.data.error || 'Action failed.', 'error'); return; }
    const state = res.data.is_active ? 'enabled' : 'disabled';
    toast(`${name} ${state}.`, 'info');
    this.renderUsers();
  },

  async deleteUser(id, name) {
    if (!confirm(`Delete user "${name}"? This cannot be undone.`)) return;
    const res = await api.delete(`/api/users/${id}`);
    if (!res.ok) { toast(res.data.error || 'Delete failed.', 'error'); return; }
    toast(`User "${name}" deleted.`, 'info');
    this.renderUsers();
  },

  openAddUser() {
    modal.open(`
      <div class="modal">
        <div class="modal-title">Add user</div>
        <div class="form-grid">
          <div class="form-group"><label class="form-label">Full name *</label><input class="form-input" id="au-name" placeholder="Full name"></div>
          <div class="form-group"><label class="form-label">Username *</label><input class="form-input" id="au-username" placeholder="Login username"></div>
          <div class="form-group"><label class="form-label">Password *</label><input class="form-input" type="password" id="au-password" placeholder="Min 6 characters"><label class="show-password-toggle"><input type="checkbox" onchange="togglePasswordField('au-password', this.checked)">Show password</label></div>
          <div class="form-group"><label class="form-label">Role *</label>
            <select class="form-select" id="au-role">
              <option value="staff">Inventory Staff</option>
              <option value="manager">Manager</option>
              <option value="finance">Finance</option>
              <option value="admin">Admin</option>
            </select></div>
        </div>
        <div class="error-bar" id="au-err"></div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="reports.submitAddUser()">Create user</button>
        </div>
      </div>`);
  },

  async submitAddUser() {
    hideErr('au-err');
    const name     = document.getElementById('au-name').value.trim();
    const username = document.getElementById('au-username').value.trim();
    const password = document.getElementById('au-password').value;
    const role     = document.getElementById('au-role').value;

    if (!name || !username || !password) { showErr('au-err', 'All fields are required.'); return; }

    const res = await api.post('/api/auth/register', { name, username, password, role });
    if (!res.ok) { showErr('au-err', res.data.error || 'Failed to create user.'); return; }
    modal.close();
    toast(`User "${name}" created.`, 'success');
    this.renderUsers();
  },
};
