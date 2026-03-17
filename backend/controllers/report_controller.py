from datetime import datetime, timedelta

from db import get_conn


def get_dashboard():
    conn = get_conn()

    totals = conn.execute(
        """SELECT
               COUNT(*) AS total_skus,
               COALESCE(SUM(current_stock * unit_price), 0) AS total_value,
               COALESCE(SUM(CASE WHEN current_stock <= reorder_level THEN 1 ELSE 0 END), 0) AS low_stock_count
           FROM products
           WHERE is_active=1"""
    ).fetchone()

    total_transactions = conn.execute('SELECT COUNT(*) AS c FROM transactions').fetchone()['c']

    recent = conn.execute(
        """SELECT t.id, t.txn_type, t.quantity, t.party, t.txn_date, t.username,
                  p.name AS product_name
           FROM transactions t
           JOIN products p ON p.id=t.product_id
           ORDER BY t.id DESC
           LIMIT 8"""
    ).fetchall()

    category_rows = conn.execute(
        """SELECT category,
                  SUM(current_stock) AS total,
                  SUM(reorder_level * 2) AS capacity
           FROM products
           WHERE is_active=1
           GROUP BY category
           ORDER BY category"""
    ).fetchall()

    chart_data = []
    for days_ago in reversed(range(7)):
        day = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        count = conn.execute(
            'SELECT COUNT(*) AS c FROM transactions WHERE txn_date=?', (day,)
        ).fetchone()['c']
        chart_data.append({'date': day, 'count': count})

    conn.close()
    return 200, {
        'total_skus': totals['total_skus'],
        'total_value': totals['total_value'],
        'total_transactions': total_transactions,
        'low_stock_count': totals['low_stock_count'],
        'recent_transactions': [dict(r) for r in recent],
        'categories': [
            {
                'name': r['category'],
                'total': r['total'] or 0,
                'capacity': r['capacity'] or 0,
            }
            for r in category_rows
        ],
        'chart_data': chart_data,
    }


def get_alerts():
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, sku, name, category, unit, current_stock, reorder_level, supplier
           FROM products
           WHERE is_active=1 AND current_stock <= reorder_level
           ORDER BY (CAST(current_stock AS REAL) / CASE WHEN reorder_level=0 THEN 1 ELSE reorder_level END) ASC,
                    name"""
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def get_valuation():
    conn = get_conn()
    rows = conn.execute(
        """SELECT category,
                  COUNT(*) AS item_count,
                  COALESCE(SUM(current_stock), 0) AS total_qty,
                  COALESCE(SUM(current_stock * unit_price), 0) AS total_value
           FROM products
           WHERE is_active=1
           GROUP BY category
           ORDER BY category"""
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def get_ledger():
    conn = get_conn()
    rows = conn.execute(
        """SELECT sku, name, category, opening_stock, total_in, total_out,
                  current_stock, unit_price,
                  (current_stock * unit_price) AS valuation
           FROM products
           WHERE is_active=1
           ORDER BY name"""
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def get_aging():
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, sku, name, category, unit, current_stock, reorder_level
           FROM products
           WHERE is_active=1
           ORDER BY (CAST(current_stock AS REAL) / CASE WHEN reorder_level=0 THEN 1 ELSE reorder_level END) ASC,
                    name"""
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def get_audit(search=None):
    conn = get_conn()
    if search:
        q = f"%{search.strip()}%"
        rows = conn.execute(
            """SELECT id, action, entity, detail, user_id, username, created_at
               FROM audit_logs
               WHERE action LIKE ? OR entity LIKE ? OR detail LIKE ? OR username LIKE ?
               ORDER BY id DESC
               LIMIT 200""",
            (q, q, q, q),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, action, entity, detail, user_id, username, created_at
               FROM audit_logs
               ORDER BY id DESC
               LIMIT 200"""
        ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def get_users():
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, name, username, role, is_active, created_at
           FROM users
           ORDER BY id"""
    ).fetchall()
    conn.close()
    return 200, [dict(row) for row in rows]


def toggle_user(user_id, actor):
    if actor.get('user_id') == user_id:
        return 400, {'error': 'You cannot disable your own account.'}

    conn = get_conn()
    row = conn.execute('SELECT id, name, username, is_active FROM users WHERE id=?', (user_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {'error': 'User not found.'}

    new_state = 0 if row['is_active'] else 1
    conn.execute('UPDATE users SET is_active=? WHERE id=?', (new_state, user_id))
    conn.execute(
        """INSERT INTO audit_logs(action, entity, detail, user_id, username)
           VALUES(?,?,?,?,?)""",
        (
            'USER_UPDATE',
            row['username'],
            f"User {row['username']} {'enabled' if new_state else 'disabled'}",
            actor.get('user_id'),
            actor.get('username'),
        ),
    )
    conn.commit()
    conn.close()
    return 200, {'is_active': bool(new_state)}


def delete_user(user_id, actor):
    if actor.get('user_id') == user_id:
        return 400, {'error': 'You cannot delete your own account.'}

    conn = get_conn()
    row = conn.execute('SELECT id, username, role FROM users WHERE id=?', (user_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {'error': 'User not found.'}
    if row['role'] == 'admin':
        conn.close()
        return 400, {'error': 'Admin users cannot be deleted.'}

    conn.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.execute(
        """INSERT INTO audit_logs(action, entity, detail, user_id, username)
           VALUES(?,?,?,?,?)""",
        (
            'USER_UPDATE',
            row['username'],
            f"User {row['username']} deleted",
            actor.get('user_id'),
            actor.get('username'),
        ),
    )
    conn.commit()
    conn.close()
    return 200, {'message': 'User deleted successfully.'}
