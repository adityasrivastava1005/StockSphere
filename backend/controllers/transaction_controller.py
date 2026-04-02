from datetime import datetime

from db import get_conn


def _audit(conn, action, entity, detail, user):
    conn.execute(
        """INSERT INTO audit_logs(action, entity, detail, user_id, username)
           VALUES(?,?,?,?,?)""",
        (action, entity, detail, user.get('user_id'), user.get('username')),
    )


def _find_product(conn, product_id):
    return conn.execute(
        """SELECT id, name, sku, unit, current_stock, reorder_level, unit_price, is_active
           FROM products WHERE id=?""",
        (product_id,),
    ).fetchone()


def get_all(txn_type=None, search=None):
    clauses = []
    values = []

    if txn_type:
        clauses.append('t.txn_type = ?')
        values.append(txn_type)
    if search:
        q = f"%{search.strip()}%"
        clauses.append('(p.name LIKE ? OR p.sku LIKE ? OR t.party LIKE ? OR t.username LIKE ?)')
        values.extend([q, q, q, q])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''

    conn = get_conn()
    rows = conn.execute(
        f"""SELECT t.id, t.txn_type, t.product_id, p.name AS product_name, p.unit,
                   t.quantity, t.party, t.unit_price, t.reason, t.remarks,
                   t.txn_date, t.username, t.created_at
            FROM transactions t
            JOIN products p ON p.id=t.product_id
            {where_sql}
            ORDER BY t.id DESC""",
        values,
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def record_inward(body, user):
    try:
        product_id = int(body.get('product_id'))
        quantity = int(body.get('quantity'))
    except Exception:
        return 400, {'error': 'Valid product and quantity are required.'}

    party = (body.get('party') or '').strip()
    reason = (body.get('reason') or 'Purchase Order').strip()
    remarks = (body.get('remarks') or '').strip()
    txn_date = (body.get('txn_date') or datetime.now().strftime('%Y-%m-%d')).strip()
    unit_price = body.get('unit_price')

    if quantity < 1:
        return 400, {'error': 'Quantity must be at least 1.'}
    if not party:
        return 400, {'error': 'Supplier name is required.'}

    if unit_price is not None:
        try:
            unit_price = float(unit_price)
        except Exception:
            return 400, {'error': 'Unit price must be a number.'}
        if unit_price < 0:
            return 400, {'error': 'Unit price cannot be negative.'}

    conn = get_conn()
    product = _find_product(conn, product_id)
    if not product or not product['is_active']:
        conn.close()
        return 404, {'error': 'Product not found.'}

    new_stock = int(product['current_stock']) + quantity
    conn.execute(
        """UPDATE products
           SET current_stock=?, total_in=total_in+?
           WHERE id=?""",
        (new_stock, quantity, product_id),
    )

    if unit_price is not None:
        conn.execute('UPDATE products SET unit_price=? WHERE id=?', (unit_price, product_id))

    cur = conn.execute(
        """INSERT INTO transactions(
            txn_type, product_id, quantity, party, unit_price,
            reason, remarks, txn_date, user_id, username
        ) VALUES('INWARD',?,?,?,?,?,?,?,?,?)""",
        (product_id, quantity, party, unit_price, reason, remarks, txn_date, user['user_id'], user['username']),
    )

    _audit(conn, 'STOCK_INWARD', product['name'], f'Received {quantity} {product["unit"]} from {party}', user)
    conn.commit()
    conn.close()
    return 201, {'id': cur.lastrowid, 'new_stock': new_stock}


def record_outward(body, user):
    try:
        product_id = int(body.get('product_id'))
        quantity = int(body.get('quantity'))
    except Exception:
        return 400, {'error': 'Valid product and quantity are required.'}

    party = (body.get('party') or '').strip()
    reason = (body.get('reason') or 'Sale Order').strip()
    remarks = (body.get('remarks') or '').strip()
    txn_date = (body.get('txn_date') or datetime.now().strftime('%Y-%m-%d')).strip()

    if quantity < 1:
        return 400, {'error': 'Quantity must be at least 1.'}
    if not party:
        return 400, {'error': 'Issued to is required.'}

    conn = get_conn()
    product = _find_product(conn, product_id)
    if not product or not product['is_active']:
        conn.close()
        return 404, {'error': 'Product not found.'}

    if quantity > int(product['current_stock']):
        conn.close()
        return 400, {'error': 'Insufficient stock for outward transaction.'}

    new_stock = int(product['current_stock']) - quantity
    conn.execute(
        """UPDATE products
           SET current_stock=?, total_out=total_out+?
           WHERE id=?""",
        (new_stock, quantity, product_id),
    )

    cur = conn.execute(
        """INSERT INTO transactions(
            txn_type, product_id, quantity, party, unit_price,
            reason, remarks, txn_date, user_id, username
        ) VALUES('OUTWARD',?,?,?,?,?,?,?,?,?)""",
        (product_id, quantity, party, None, reason, remarks, txn_date, user['user_id'], user['username']),
    )

    _audit(conn, 'STOCK_OUTWARD', product['name'], f'Dispatched {quantity} {product["unit"]} to {party}', user)

    alert = new_stock <= int(product['reorder_level'])
    if alert:
        _audit(
            conn,
            'LOW_STOCK_ALERT',
            product['name'],
            f'Stock ({new_stock}) at or below reorder level ({product["reorder_level"]})',
            user,
        )

    conn.commit()
    conn.close()
    return 201, {'id': cur.lastrowid, 'new_stock': new_stock, 'alert': alert}


def clear_all(user, txn_type=None):
    txn_type = (txn_type or '').strip().upper()
    if txn_type and txn_type not in {'INWARD', 'OUTWARD'}:
        return 400, {'error': 'Invalid transaction type.'}

    conn = get_conn()
    if txn_type:
        conn.execute('DELETE FROM transactions WHERE txn_type=?', (txn_type,))
        label = 'inward' if txn_type == 'INWARD' else 'outward'
        _audit(conn, 'TXN_CLEAR', 'transactions', f'All {label} transaction history cleared', user)
        message = f'All {label} transaction history cleared.'
    else:
        conn.execute('DELETE FROM transactions')
        _audit(conn, 'TXN_CLEAR', 'transactions', 'All transaction history cleared', user)
        message = 'All transaction history cleared.'

    conn.commit()
    conn.close()
    return 200, {'message': message}
