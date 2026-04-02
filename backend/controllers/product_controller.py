from db import get_conn


def _audit(conn, action, entity, detail, user):
    conn.execute(
        """INSERT INTO audit_logs(action, entity, detail, user_id, username)
           VALUES(?,?,?,?,?)""",
        (action, entity, detail, user.get('user_id'), user.get('username')),
    )


def get_all(params):
    search = (params or {}).get('search', '').strip()
    category = (params or {}).get('category', '').strip()

    clauses = ['is_active=1']
    values = []

    if search:
        clauses.append('(name LIKE ? OR sku LIKE ? OR supplier LIKE ?)')
        q = f"%{search}%"
        values.extend([q, q, q])
    if category:
        clauses.append('category = ?')
        values.append(category)

    where_sql = ' AND '.join(clauses)
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT id, sku, name, category, unit, current_stock, reorder_level,
                   unit_price, opening_stock, total_in, total_out, supplier
            FROM products
            WHERE {where_sql}
            ORDER BY name""",
        values,
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def get_categories():
    conn = get_conn()
    rows = conn.execute(
        'SELECT DISTINCT category FROM products WHERE is_active=1 ORDER BY category'
    ).fetchall()
    conn.close()
    return 200, [row['category'] for row in rows]


def create(body, user):
    name = (body.get('name') or '').strip()
    sku = (body.get('sku') or '').strip().upper()
    category = (body.get('category') or '').strip()
    unit = (body.get('unit') or 'pcs').strip()
    current_stock = int(body.get('current_stock') or 0)
    reorder_level = int(body.get('reorder_level') or 0)
    unit_price = float(body.get('unit_price') or 0)
    supplier = (body.get('supplier') or '').strip()

    if not name or not sku or not category:
        return 400, {'error': 'Name, SKU and category are required.'}
    if reorder_level < 1:
        return 400, {'error': 'Reorder level must be at least 1.'}
    if current_stock < 0 or unit_price < 0:
        return 400, {'error': 'Stock and unit price cannot be negative.'}

    conn = get_conn()
    exists = conn.execute('SELECT id, is_active FROM products WHERE sku=?', (sku,)).fetchone()
    exists_is_active = bool(int(exists['is_active'])) if exists and exists['is_active'] is not None else False

    if exists and exists_is_active:
        conn.close()
        return 409, {'error': 'SKU already exists.'}

    if exists and not exists_is_active:
        conn.execute(
            """UPDATE products
               SET name=?, category=?, unit=?, current_stock=?, reorder_level=?, unit_price=?,
                   opening_stock=?, total_in=0, total_out=0, supplier=?, is_active=1
               WHERE id=?""",
            (name, category, unit, current_stock, reorder_level, unit_price, current_stock, supplier, exists['id']),
        )
        _audit(conn, 'PRODUCT_ADD', name, f'Product {sku} reactivated, stock: {current_stock}', user)
        conn.commit()
        conn.close()
        return 201, {'id': exists['id'], 'message': 'Product reactivated successfully.'}

    cur = conn.execute(
        """INSERT INTO products(
            sku, name, category, unit, current_stock, reorder_level, unit_price,
            opening_stock, total_in, total_out, supplier, is_active
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)""",
        (sku, name, category, unit, current_stock, reorder_level, unit_price, current_stock, 0, 0, supplier),
    )
    _audit(conn, 'PRODUCT_ADD', name, f'Product {sku} registered, stock: {current_stock}', user)
    conn.commit()
    conn.close()
    return 201, {'id': cur.lastrowid, 'message': 'Product created successfully.'}


def update(product_id, body, user):
    name = (body.get('name') or '').strip()
    category = (body.get('category') or '').strip()
    unit = (body.get('unit') or '').strip()
    reorder_level = int(body.get('reorder_level') or 0)
    unit_price = float(body.get('unit_price') or 0)
    supplier = (body.get('supplier') or '').strip()

    if not name or not category or not unit:
        return 400, {'error': 'Name, category and unit are required.'}
    if reorder_level < 1:
        return 400, {'error': 'Reorder level must be at least 1.'}
    if unit_price < 0:
        return 400, {'error': 'Unit price cannot be negative.'}

    conn = get_conn()
    old = conn.execute('SELECT name, sku FROM products WHERE id=? AND is_active=1', (product_id,)).fetchone()
    if not old:
        conn.close()
        return 404, {'error': 'Product not found.'}

    conn.execute(
        """UPDATE products
           SET name=?, category=?, unit=?, reorder_level=?, unit_price=?, supplier=?
           WHERE id=?""",
        (name, category, unit, reorder_level, unit_price, supplier, product_id),
    )
    _audit(conn, 'PRODUCT_UPDATE', name, f'Updated product {old["sku"]}', user)
    conn.commit()
    conn.close()
    return 200, {'message': 'Product updated successfully.'}


def deactivate(product_id, user):
    conn = get_conn()
    row = conn.execute('SELECT name, sku FROM products WHERE id=? AND is_active=1', (product_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {'error': 'Product not found.'}

    conn.execute('UPDATE products SET is_active=0 WHERE id=?', (product_id,))
    _audit(conn, 'PRODUCT_REMOVE', row['name'], f'Product {row["sku"]} deactivated', user)
    conn.commit()
    conn.close()
    return 200, {'message': 'Product removed successfully.'}
