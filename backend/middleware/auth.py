import hashlib
import os
import secrets
from datetime import datetime, timedelta
from db import get_conn

SECRET = "stocksphere_jwt_secret_key_v1_2026"

def generate_token():
    return secrets.token_hex(32)

def create_session(user_id):
    token = generate_token()
    expires_at = (datetime.now() + timedelta(hours=8)).isoformat()
    conn = get_conn()
    try:
        create_session_in_conn(conn, user_id, token=token, expires_at=expires_at)
        conn.commit()
    finally:
        conn.close()
    return token


def create_session_in_conn(conn, user_id, token=None, expires_at=None):
    token = token or generate_token()
    expires_at = expires_at or (datetime.now() + timedelta(hours=8)).isoformat()
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
                 (token, user_id, expires_at))
    return token

def verify_token(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute("""
        SELECT s.user_id, s.expires_at, u.username, u.role, u.name, u.is_active
        FROM sessions s JOIN users u ON s.user_id=u.id
        WHERE s.token=?
    """, (token,)).fetchone()
    conn.close()
    if not row:
        return None
    if datetime.fromisoformat(row['expires_at']) < datetime.now():
        return None
    if not row['is_active']:
        return None
    return dict(row)

def destroy_session(token):
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()

ROLE_HIERARCHY = {'admin': 4, 'manager': 3, 'finance': 2, 'staff': 1}

def has_role(user_role, required_role):
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 99)
