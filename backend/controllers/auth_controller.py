from db import get_conn, hash_password
from middleware.auth import create_session_in_conn, destroy_session

VALID_ROLES = {'admin', 'manager', 'staff', 'finance'}


def _audit(conn, action, entity, detail, user=None):
    user_id = user.get('id') if user else None
    username = user.get('username') if user else None
    conn.execute(
        """INSERT INTO audit_logs(action, entity, detail, user_id, username)
           VALUES(?,?,?,?,?)""",
        (action, entity, detail, user_id, username),
    )


def login(body):
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    if not username or not password:
        return 400, {'error': 'Username and password are required.'}

    conn = get_conn()
    row = conn.execute(
        "SELECT id, name, username, password, role, is_active FROM users WHERE username=?",
        (username,),
    ).fetchone()

    if not row or row['password'] != hash_password(password):
        conn.close()
        return 401, {'error': 'Invalid username or password.'}

    if not row['is_active']:
        conn.close()
        return 403, {'error': 'Account is inactive. Contact admin.'}

    user = {
        'id': row['id'],
        'name': row['name'],
        'username': row['username'],
        'role': row['role'],
    }
    token = create_session_in_conn(conn, row['id'])
    _audit(conn, 'USER_LOGIN', row['username'], f"User {row['username']} signed in", user)
    conn.commit()
    conn.close()
    return 200, {'token': token, 'user': user}


def register(body):
    name = (body.get('name') or '').strip()
    username = (body.get('username') or '').strip().lower()
    password = body.get('password') or ''
    role = (body.get('role') or 'staff').strip().lower()

    if not name or not username or not password:
        return 400, {'error': 'Name, username and password are required.'}
    if len(password) < 6:
        return 400, {'error': 'Password must be at least 6 characters.'}
    if role not in VALID_ROLES:
        return 400, {'error': 'Invalid role.'}

    conn = get_conn()
    exists = conn.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
    if exists:
        conn.close()
        return 409, {'error': 'Username already exists.'}

    cur = conn.execute(
        "INSERT INTO users(name, username, password, role) VALUES(?,?,?,?)",
        (name, username, hash_password(password), role),
    )
    user_id = cur.lastrowid
    user = {'id': user_id, 'name': name, 'username': username, 'role': role}
    token = create_session_in_conn(conn, user_id)
    _audit(conn, 'USER_REGISTER', username, f"User {username} created with role {role}", user)
    conn.commit()
    conn.close()
    return 201, {'token': token, 'user': user}


def logout(token, user):
    if token:
        destroy_session(token)
    conn = get_conn()
    _audit(conn, 'USER_LOGOUT', user.get('username'), f"User {user.get('username')} signed out", user)
    conn.commit()
    conn.close()
    return 200, {'message': 'Logged out successfully.'}


def change_password(body, user):
    current_password = body.get('current_password') or ''
    new_password = body.get('new_password') or ''

    if not current_password or not new_password:
        return 400, {'error': 'Current and new passwords are required.'}
    if len(new_password) < 6:
        return 400, {'error': 'New password must be at least 6 characters.'}

    conn = get_conn()
    row = conn.execute('SELECT password FROM users WHERE id=?', (user['user_id'],)).fetchone()
    if not row or row['password'] != hash_password(current_password):
        conn.close()
        return 401, {'error': 'Current password is incorrect.'}

    conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(new_password), user['user_id']))
    _audit(conn, 'USER_UPDATE', user['username'], 'Password changed', user)
    conn.commit()
    conn.close()
    return 200, {'message': 'Password changed successfully.'}


def change_username(body, user):
    new_username = (body.get('new_username') or '').strip().lower()
    current_password = body.get('current_password') or ''

    if not new_username or not current_password:
        return 400, {'error': 'New username and current password are required.'}

    conn = get_conn()
    row = conn.execute('SELECT password FROM users WHERE id=?', (user['user_id'],)).fetchone()
    if not row or row['password'] != hash_password(current_password):
        conn.close()
        return 401, {'error': 'Current password is incorrect.'}

    taken = conn.execute('SELECT id FROM users WHERE username=? AND id<>?', (new_username, user['user_id'])).fetchone()
    if taken:
        conn.close()
        return 409, {'error': 'Username already exists.'}

    old_username = user['username']
    conn.execute('UPDATE users SET username=? WHERE id=?', (new_username, user['user_id']))
    conn.execute('UPDATE transactions SET username=? WHERE user_id=?', (new_username, user['user_id']))
    conn.execute('UPDATE audit_logs SET username=? WHERE user_id=?', (new_username, user['user_id']))
    _audit(conn, 'USER_UPDATE', new_username, f'Username changed from {old_username} to {new_username}', user)
    conn.commit()
    conn.close()
    return 200, {'message': 'Username changed successfully.', 'username': new_username}
