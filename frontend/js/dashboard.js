// dashboard.js — metrics, chart, category breakdown, recent transactions
const dashboard = {
  async render() {
    setLoading('dash-recent', 'Loading dashboard…');
    const res = await api.get('/api/dashboard');
    if (!res.ok) { handleApiError(res); return; }
    const d = res.data;

    // Metrics
    document.getElementById('m-skus').textContent  = fmtNum(d.total_skus);
    document.getElementById('m-value').textContent  = fmtMoney(d.total_value);
    document.getElementById('m-txns').textContent   = fmtNum(d.total_transactions);
    document.getElementById('m-low').textContent    = d.low_stock_count;
    document.getElementById('m-low').className = 'metric-value ' + (d.low_stock_count > 0 ? 'danger' : 'success');

    // Alert bell + nav badge
    const alertCount = d.low_stock_count;
    const bellCount  = document.getElementById('bell-count');
    const navBadge   = document.getElementById('nav-alert-badge');
    if (alertCount > 0) {
      bellCount.textContent = alertCount;  bellCount.classList.remove('hidden');
      navBadge.textContent  = alertCount;  navBadge.classList.remove('hidden');
    } else {
      bellCount.classList.add('hidden');
      navBadge.classList.add('hidden');
    }

    // Top status bar
    const sb = document.getElementById('dash-status');
    if (alertCount > 0) {
      sb.innerHTML = `<div class="status-bar warning">⚠ ${alertCount} product${alertCount>1?'s':''} below reorder level — <strong style="cursor:pointer;text-decoration:underline" onclick="nav.go('alerts')">view alerts</strong></div>`;
    } else {
      sb.innerHTML = `<div class="status-bar success">✓ All products above reorder thresholds</div>`;
    }

    // Chart
    const max = Math.max(...d.chart_data.map(c => c.count), 1);
    const chartEl  = document.getElementById('dash-chart');
    const labelEl  = document.getElementById('dash-chart-labels');
    chartEl.innerHTML = d.chart_data.map(c => {
      const h = Math.max(4, Math.round((c.count / max) * 100));
      return `<div class="chart-bar" style="height:${h}%" title="${c.date}: ${c.count} txn${c.count!==1?'s':''}"></div>`;
    }).join('');
    labelEl.innerHTML = d.chart_data.map(c => {
      const label = new Date(c.date + 'T00:00:00').toLocaleDateString('en', { weekday: 'short' });
      return `<span class="chart-label">${label}</span>`;
    }).join('');

    // Category breakdown
    const catEl = document.getElementById('dash-categories');
    catEl.innerHTML = d.categories.map(cat => {
      const pct = cat.capacity ? Math.round((cat.total / cat.capacity) * 100) : 0;
      const color = pct < 30 ? 'var(--danger)' : pct < 60 ? 'var(--warning)' : 'var(--brand)';
      return `<div style="margin-bottom:11px">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
          <span style="color:var(--text2)">${cat.name}</span>
          <span style="font-weight:600;color:${color}">${pct}%</span>
        </div>
        <div class="prog-track"><div class="prog-fill" style="width:${pct}%;background:${color}"></div></div>
      </div>`;
    }).join('');

    // Recent transactions
    const tbEl = document.getElementById('dash-recent');
    if (!d.recent_transactions.length) {
      tbEl.innerHTML = '<div class="empty"><div class="empty-text">No transactions yet</div></div>';
      return;
    }
    tbEl.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Txn ID</th><th>Product</th><th>Type</th><th>Qty</th><th>Party</th><th>Date</th><th>By</th></tr></thead>
      <tbody>${d.recent_transactions.map(t => {
        const isIn = t.txn_type === 'INWARD';
        return `<tr>
          <td class="td-mono">${txnId(t.id)}</td>
          <td class="td-bold">${t.product_name}</td>
          <td><span class="badge ${isIn ? 'badge-green' : 'badge-amber'}">${t.txn_type}</span></td>
          <td class="${isIn ? 'color-green' : 'color-red'} fw-600">${isIn ? '+' : '-'}${t.quantity}</td>
          <td>${t.party}</td>
          <td>${t.txn_date}</td>
          <td class="td-muted">${t.username}</td>
        </tr>`;
      }).join('')}</tbody>
    </table></div>`;
  },
};
