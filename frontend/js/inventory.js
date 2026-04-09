// inventory.js — products, inward, outward, alerts
const inventory = {
  _products: [],

  // ── PRODUCTS ──────────────────────────────────────────────────────
  async renderProducts() {
    const canEdit = auth.can('staff');
    const addBtn = document.getElementById('btn-add-product');
    if (addBtn) addBtn.classList.toggle('hidden', !canEdit);

    const search = document.getElementById('prod-search')?.value || '';
    const cat    = document.getElementById('prod-cat-filter')?.value || '';
    let url = '/api/products?';
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (cat)    url += `category=${encodeURIComponent(cat)}&`;

    const res = await api.get(url);
    if (!res.ok) { handleApiError(res); return; }
    const products = res.data;
    this._products = products;

    // Populate category filter (once)
    const catFilter = document.getElementById('prod-cat-filter');
    if (catFilter && catFilter.options.length === 1) {
      const cats = [...new Set(products.map(p => p.category))].sort();
      cats.forEach(c => {
        const o = document.createElement('option');
        o.value = c; o.textContent = c;
        catFilter.appendChild(o);
      });
    }

    const tbody = document.getElementById('products-tbody');
    if (!products.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty" style="padding:32px">
        <div class="empty-text" style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <span>No products found</span>
          ${canEdit ? '<button class="btn btn-sm btn-primary" onclick="inventory.openAddProduct()">+ Add product</button>' : ''}
        </div>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = products.map(p => {
      const isLow  = p.current_stock <= p.reorder_level;
      const isCrit = p.current_stock < p.reorder_level / 2;
      const actions = canEdit ? `
        <button class="action-btn" onclick="inventory.openEditProduct(${p.id})">Edit</button>
        <button class="action-btn danger" onclick="inventory.deleteProduct(${p.id})">Remove</button>
      ` : '—';
      return `<tr>
        <td class="td-mono">${p.sku}</td>
        <td class="td-bold">${p.name}</td>
        <td><span class="badge badge-gray">${p.category}</span></td>
        <td class="td-muted">${p.unit}</td>
        <td class="${isCrit ? 'color-red' : isLow ? '' : 'color-green'} fw-600">${p.current_stock}</td>
        <td class="td-muted">${p.reorder_level}</td>
        <td>₹${(p.unit_price||0).toLocaleString('en-IN')}</td>
        <td>${stockBadge(p.current_stock, p.reorder_level)}</td>
        <td><div class="td-actions">${actions}</div></td>
      </tr>`;
    }).join('');
  },

  openAddProduct() {
    if (!auth.can('staff')) {
      toast('You do not have permission to add products.', 'error');
      return;
    }

    modal.open(`
      <div class="modal">
        <div class="modal-title">Register product</div>
        <div class="form-grid">
          <div class="form-group"><label class="form-label">Product name *</label><input class="form-input" id="np-name" placeholder="e.g. Steel Rod 12mm"></div>
          <div class="form-group"><label class="form-label">SKU *</label><input class="form-input" id="np-sku" placeholder="e.g. SR-012" style="text-transform:uppercase"></div>
          <div class="form-group"><label class="form-label">Category *</label>
            <select class="form-select" id="np-cat">
              <option>Electronics</option><option>Raw Materials</option><option>Packaging</option>
              <option>Tools</option><option>Consumables</option><option>Spare Parts</option>
            </select></div>
          <div class="form-group"><label class="form-label">Unit</label>
            <select class="form-select" id="np-unit">
              <option>pcs</option><option>kg</option><option>meters</option><option>liters</option><option>rolls</option><option>pairs</option><option>boxes</option>
            </select></div>
          <div class="form-group"><label class="form-label">Initial stock *</label><input class="form-input" type="number" id="np-stock" placeholder="0" min="0"></div>
          <div class="form-group"><label class="form-label">Reorder level *</label><input class="form-input" type="number" id="np-reorder" placeholder="20" min="1"></div>
          <div class="form-group"><label class="form-label">Unit price (₹) *</label><input class="form-input" type="number" id="np-price" placeholder="0.00" min="0" step="0.01"></div>
          <div class="form-group"><label class="form-label">Supplier</label><input class="form-input" id="np-supplier" placeholder="Optional"></div>
        </div>
        <div class="error-bar" id="np-err"></div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="inventory.submitAddProduct()">Register product</button>
        </div>
      </div>`);
  },

  async submitAddProduct() {
    hideErr('np-err');
    const name    = document.getElementById('np-name').value.trim();
    const sku     = document.getElementById('np-sku').value.trim().toUpperCase();
    const stock   = parseInt(document.getElementById('np-stock').value) || 0;
    const reorder = parseInt(document.getElementById('np-reorder').value);
    const price   = parseFloat(document.getElementById('np-price').value);

    if (!name || !sku) { showErr('np-err', 'Name and SKU are required.'); return; }
    if (!reorder || reorder < 1) { showErr('np-err', 'Reorder level must be ≥ 1.'); return; }
    if (isNaN(price) || price < 0) { showErr('np-err', 'Enter a valid unit price.'); return; }

    const res = await api.post('/api/products', {
      name, sku,
      category: document.getElementById('np-cat').value,
      unit: document.getElementById('np-unit').value,
      current_stock: stock, reorder_level: reorder, unit_price: price,
      supplier: document.getElementById('np-supplier').value.trim(),
    });
    if (!res.ok) { showErr('np-err', res.data.error || 'Failed to add product.'); return; }
    modal.close();
    toast(`Product "${name}" registered.`, 'success');
    this.renderProducts();
  },

  openEditProduct(id) {
    const p = this._products.find(x => x.id === id);
    if (!p) return;
    modal.open(`
      <div class="modal">
        <div class="modal-title">Edit product</div>
        <input type="hidden" id="ep-id" value="${id}">
        <div class="form-grid">
          <div class="form-group"><label class="form-label">Product name</label><input class="form-input" id="ep-name" value="${p.name}"></div>
          <div class="form-group"><label class="form-label">SKU</label><input class="form-input" id="ep-sku" value="${p.sku}" readonly style="opacity:0.6"></div>
          <div class="form-group"><label class="form-label">Category</label>
            <select class="form-select" id="ep-cat">
              ${['Electronics','Raw Materials','Packaging','Tools','Consumables','Spare Parts'].map(c => `<option${c===p.category?' selected':''}>${c}</option>`).join('')}
            </select></div>
          <div class="form-group"><label class="form-label">Unit</label>
            <select class="form-select" id="ep-unit">
              ${['pcs','kg','meters','liters','rolls','pairs','boxes'].map(u => `<option${u===p.unit?' selected':''}>${u}</option>`).join('')}
            </select></div>
          <div class="form-group"><label class="form-label">Reorder level</label><input class="form-input" type="number" id="ep-reorder" value="${p.reorder_level}" min="1"></div>
          <div class="form-group"><label class="form-label">Unit price (₹)</label><input class="form-input" type="number" id="ep-price" value="${p.unit_price}" step="0.01"></div>
          <div class="form-group form-full"><label class="form-label">Supplier</label><input class="form-input" id="ep-supplier" value="${p.supplier||''}"></div>
        </div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="inventory.submitEditProduct()">Save changes</button>
        </div>
      </div>`);
  },

  async submitEditProduct() {
    const id = parseInt(document.getElementById('ep-id').value);
    const body = {
      name:          document.getElementById('ep-name').value.trim(),
      category:      document.getElementById('ep-cat').value,
      unit:          document.getElementById('ep-unit').value,
      reorder_level: parseInt(document.getElementById('ep-reorder').value),
      unit_price:    parseFloat(document.getElementById('ep-price').value),
      supplier:      document.getElementById('ep-supplier').value.trim(),
    };
    const res = await api.put(`/api/products/${id}`, body);
    if (!res.ok) { toast(res.data.error || 'Update failed.', 'error'); return; }
    modal.close();
    toast('Product updated.', 'success');
    this.renderProducts();
  },

  deleteProduct(id) {
    const product = this._products.find(x => x.id === id);
    const name = product?.name || 'this product';
    modal.open(`
      <div class="modal">
        <div class="modal-title">Remove product</div>
        <p style="margin-bottom:18px;color:var(--text2)">Remove <strong>${name}</strong> from the catalogue? This cannot be undone.</p>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-danger" onclick="inventory._confirmDeleteProduct(${id})">Remove</button>
        </div>
      </div>`);
  },

  async _confirmDeleteProduct(id) {
    const product = this._products.find(x => x.id === id);
    const name = product?.name || 'Product';
    modal.close();
    const res = await api.delete(`/api/products/${id}`);
    if (!res.ok) { toast(res.data.error || 'Remove failed.', 'error'); return; }
    toast(`"${name}" removed.`, 'info');
    this.renderProducts();
  },

  clearTransactions(txnType) {
    const isInward = txnType === 'INWARD';
    const title = isInward ? 'Clear inward history' : 'Clear outward history';
    const scopeText = isInward ? 'all inward transaction records' : 'all outward transaction records';
    modal.open(`
      <div class="modal">
        <div class="modal-title">${title}</div>
        <p style="margin-bottom:18px;color:var(--text2)">This will permanently delete <strong>${scopeText}</strong>. Product stock levels will be kept as-is. This cannot be undone.</p>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-danger" onclick="inventory._confirmClearTransactions('${txnType}')">Clear history</button>
        </div>
      </div>`);
  },

  async _confirmClearTransactions(txnType) {
    modal.close();
    const res = await api.delete(`/api/transactions?type=${encodeURIComponent(txnType)}`);
    if (!res.ok) { toast(res.data.error || 'Clear failed.', 'error'); return; }
    toast(res.data.message || 'Transaction history cleared.', 'info');
    api._invalidateCache();
    if (txnType === 'INWARD') this.renderInward();
    if (txnType === 'OUTWARD') this.renderOutward();
    this.renderTransactions();
  },

  // ── INWARD ────────────────────────────────────────────────────────
  async renderInward() {
    const search = document.getElementById('inward-search')?.value || '';
    let url = '/api/transactions?type=INWARD';
    if (search) url += `&search=${encodeURIComponent(search)}`;
    const res = await api.get(url);
    if (!res.ok) { handleApiError(res); return; }
    const txns = res.data;
    const tbody = document.getElementById('inward-tbody');
    if (!txns.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty" style="padding:32px">No inward records</td></tr>';
      return;
    }
    tbody.innerHTML = txns.map(t => `<tr>
      <td class="td-mono">${txnId(t.id)}</td>
      <td class="td-bold">${t.product_name}</td>
      <td>${t.party}</td>
      <td class="color-green fw-600">+${t.quantity} ${t.unit}</td>
      <td>${t.unit_price ? '₹' + t.unit_price.toLocaleString('en-IN') : '—'}</td>
      <td>${t.unit_price ? '₹' + (t.unit_price*t.quantity).toLocaleString('en-IN') : '—'}</td>
      <td>${t.txn_date}</td>
      <td class="td-muted">${t.username}</td>
    </tr>`).join('');
  },

  async openInward() {
    const res = await api.get('/api/products');
    if (!res.ok) { toast('Could not load products.', 'error'); return; }
    const products = res.data;
    const opts = products.map(p => `<option value="${p.id}">${p.name} (${p.sku}) — Stock: ${p.current_stock} ${p.unit}</option>`).join('');
    modal.open(`
      <div class="modal">
        <div class="modal-title">Record stock inward</div>
        <div class="form-grid">
          <div class="form-group form-full"><label class="form-label">Product *</label><select class="form-select" id="in-product">${opts}</select></div>
          <div class="form-group"><label class="form-label">Quantity *</label><input class="form-input" type="number" id="in-qty" placeholder="0" min="1"></div>
          <div class="form-group"><label class="form-label">Supplier *</label><input class="form-input" id="in-party" placeholder="Supplier name"></div>
          <div class="form-group"><label class="form-label">Unit price (₹)</label><input class="form-input" type="number" id="in-price" placeholder="From product" min="0" step="0.01"></div>
          <div class="form-group"><label class="form-label">Date *</label><input class="form-input" type="date" id="in-date" value="${todayStr()}"></div>
          <div class="form-group"><label class="form-label">Reason</label>
            <select class="form-select" id="in-reason"><option>Purchase Order</option><option>Replenishment</option><option>Return from Customer</option><option>Transfer</option></select></div>
          <div class="form-group form-full"><label class="form-label">Remarks</label><input class="form-input" id="in-remarks" placeholder="Optional notes"></div>
        </div>
        <div class="error-bar" id="in-err"></div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="inventory.submitInward()">Record inward</button>
        </div>
      </div>`);
  },

  async submitInward() {
    hideErr('in-err');
    const product_id = parseInt(document.getElementById('in-product').value);
    const quantity   = parseInt(document.getElementById('in-qty').value);
    const party      = document.getElementById('in-party').value.trim();
    const unit_price = document.getElementById('in-price').value || null;
    const txn_date   = document.getElementById('in-date').value;
    const reason     = document.getElementById('in-reason').value;
    const remarks    = document.getElementById('in-remarks').value.trim();

    if (!quantity || quantity < 1) { showErr('in-err', 'Quantity must be at least 1.'); return; }
    if (!party) { showErr('in-err', 'Supplier name is required.'); return; }
    if (!txn_date) { showErr('in-err', 'Date is required.'); return; }

    const res = await api.post('/api/transactions/inward', {
      product_id, quantity, party, unit_price: unit_price ? parseFloat(unit_price) : null,
      txn_date, reason, remarks,
    });
    if (!res.ok) { showErr('in-err', res.data.error || 'Failed to record.'); return; }
    modal.close();
    toast(`Inward recorded. New stock: ${res.data.new_stock}`, 'success');
    this.renderInward();
  },

  // ── OUTWARD ───────────────────────────────────────────────────────
  async renderOutward() {
    const search = document.getElementById('outward-search')?.value || '';
    let url = '/api/transactions?type=OUTWARD';
    if (search) url += `&search=${encodeURIComponent(search)}`;
    const res = await api.get(url);
    if (!res.ok) { handleApiError(res); return; }
    const txns = res.data;
    const tbody = document.getElementById('outward-tbody');
    if (!txns.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty" style="padding:32px">No outward records</td></tr>';
      return;
    }
    tbody.innerHTML = txns.map(t => `<tr>
      <td class="td-mono">${txnId(t.id)}</td>
      <td class="td-bold">${t.product_name}</td>
      <td>${t.party}</td>
      <td class="color-red fw-600">-${t.quantity} ${t.unit}</td>
      <td><span class="badge badge-gray">${t.reason}</span></td>
      <td>${t.txn_date}</td>
      <td class="td-muted">${t.username}</td>
    </tr>`).join('');
  },

  async renderTransactions() {
    const search = document.getElementById('tx-search')?.value || '';
    let url = '/api/transactions';
    if (search) url += `?search=${encodeURIComponent(search)}`;

    const res = await api.get(url);
    if (!res.ok) { handleApiError(res); return; }

    const txns = res.data;
    const tbody = document.getElementById('transactions-tbody');
    if (!tbody) return;

    if (!txns.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty" style="padding:32px">No transaction records found</td></tr>';
      return;
    }

    tbody.innerHTML = txns.map(t => {
      const isIn = t.txn_type === 'INWARD';
      return `<tr>
        <td class="td-mono">${txnId(t.id)}</td>
        <td class="td-bold">${t.product_name}</td>
        <td><span class="badge ${isIn ? 'badge-green' : 'badge-amber'}">${t.txn_type}</span></td>
        <td class="${isIn ? 'color-green' : 'color-red'} fw-600">${isIn ? '+' : '-'}${t.quantity} ${t.unit}</td>
        <td>${t.party}</td>
        <td>${t.reason || '—'}</td>
        <td>${t.txn_date}</td>
        <td class="td-muted">${t.username}</td>
      </tr>`;
    }).join('');
  },

  async openOutward() {
    const res = await api.get('/api/products');
    if (!res.ok) { toast('Could not load products.', 'error'); return; }
    const products = res.data;
    const opts = products.map(p => `<option value="${p.id}" data-stock="${p.current_stock}" data-unit="${p.unit}">${p.name} (${p.sku}) — Stock: ${p.current_stock} ${p.unit}</option>`).join('');
    modal.open(`
      <div class="modal">
        <div class="modal-title">Record stock outward</div>
        <div class="form-grid">
          <div class="form-group form-full">
            <label class="form-label">Product *</label>
            <select class="form-select" id="out-product" onchange="inventory._updateStockInfo()">${opts}</select>
          </div>
          <div class="form-group form-full" id="out-stock-info-wrap"></div>
          <div class="form-group"><label class="form-label">Quantity *</label><input class="form-input" type="number" id="out-qty" placeholder="0" min="1"></div>
          <div class="form-group"><label class="form-label">Issued to *</label>
            <select class="form-select" id="out-party">
              <option>Sales Dept</option><option>Production Floor</option><option>External Customer</option>
              <option>Finance Dept</option><option>Management</option><option>Return to Supplier</option>
            </select></div>
          <div class="form-group"><label class="form-label">Reason *</label>
            <select class="form-select" id="out-reason">
              <option>Sale Order</option><option>Internal Use</option><option>Return</option>
              <option>Adjustment</option><option>Damaged / Write-off</option>
            </select></div>
          <div class="form-group"><label class="form-label">Date *</label><input class="form-input" type="date" id="out-date" value="${todayStr()}"></div>
          <div class="form-group form-full"><label class="form-label">Remarks</label><input class="form-input" id="out-remarks" placeholder="Optional notes"></div>
        </div>
        <div class="error-bar" id="out-err"></div>
        <div class="modal-footer">
          <button class="btn" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" onclick="inventory.submitOutward()">Record outward</button>
        </div>
      </div>`);
    this._updateStockInfo();
  },

  _updateStockInfo() {
    const sel = document.getElementById('out-product');
    if (!sel) return;
    const opt = sel.options[sel.selectedIndex];
    const stock = parseInt(opt?.dataset.stock || 0);
    const unit  = opt?.dataset.unit || '';
    const wrap  = document.getElementById('out-stock-info-wrap');
    if (!wrap) return;
    const cls = stock <= 20 ? 'warning' : 'success';
    wrap.innerHTML = `<div class="status-bar ${cls}" style="padding:7px 11px;font-size:12px">Available stock: <strong>${stock} ${unit}</strong></div>`;
  },

  async submitOutward() {
    hideErr('out-err');
    const product_id = parseInt(document.getElementById('out-product').value);
    const quantity   = parseInt(document.getElementById('out-qty').value);
    const party      = document.getElementById('out-party').value;
    const reason     = document.getElementById('out-reason').value;
    const txn_date   = document.getElementById('out-date').value;
    const remarks    = document.getElementById('out-remarks').value.trim();

    if (!quantity || quantity < 1) { showErr('out-err', 'Quantity must be at least 1.'); return; }
    if (!txn_date) { showErr('out-err', 'Date is required.'); return; }

    const res = await api.post('/api/transactions/outward', {
      product_id, quantity, party, reason, txn_date, remarks,
    });
    if (!res.ok) { showErr('out-err', res.data.error || 'Failed to record.'); return; }
    modal.close();
    const d = res.data;
    toast(`Outward recorded. New stock: ${d.new_stock}`, 'success');
    if (d.alert) toast(`Low stock alert: stock is now at or below reorder level!`, 'warning', 5000);
    this.renderOutward();
  },

  // ── ALERTS ────────────────────────────────────────────────────────
  async renderAlerts() {
    const res = await api.get('/api/reports/alerts');
    if (!res.ok) { handleApiError(res); return; }
    const items = res.data;
    const container = document.getElementById('alerts-container');
    if (!items.length) {
      container.innerHTML = '<div class="status-bar success" style="margin-top:4px">✓ All products are above reorder thresholds. No alerts.</div>';
      return;
    }
    container.innerHTML = items.map(p => {
      const isCrit = p.current_stock < p.reorder_level / 2;
      const pct    = Math.min(100, Math.round((p.current_stock / p.reorder_level) * 100));
      const color  = isCrit ? 'var(--danger)' : 'var(--warning)';
      return `<div class="alert-card ${isCrit ? 'critical' : 'low'}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
          <div>
            <div style="font-weight:600;font-size:13.5px">${p.name}</div>
            <div style="font-size:11.5px;color:var(--text3);margin-top:2px">SKU: ${p.sku} · ${p.category} · ${p.supplier || '—'}</div>
          </div>
          <span class="badge ${isCrit ? 'badge-red' : 'badge-amber'}">${isCrit ? 'Critical' : 'Low Stock'}</span>
        </div>
        <div style="display:flex;gap:24px;font-size:12.5px;margin-bottom:9px">
          <span>Current: <strong>${p.current_stock} ${p.unit}</strong></span>
          <span>Reorder at: <strong>${p.reorder_level} ${p.unit}</strong></span>
          <span style="color:${color}">Shortfall: <strong>${p.reorder_level - p.current_stock} ${p.unit}</strong></span>
        </div>
        <div class="prog-track"><div class="prog-fill" style="width:${pct}%;background:${color}"></div></div>
        <div style="font-size:11px;color:var(--text3);margin-top:3px">${pct}% of reorder threshold</div>
      </div>`;
    }).join('');
  },
};
