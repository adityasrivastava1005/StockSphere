#!/usr/bin/env python3
"""
StockSphere — Backend Server
Pure Python stdlib, no external dependencies.
REST API on port 8000, serves frontend from /frontend/
"""

import sys, os, json, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import mimetypes

# Add backend dir to path
sys.path.insert(0, os.path.dirname(__file__))

from db import init_db, get_conn
from middleware.auth import verify_token, has_role
from controllers.auth_controller import login, register, logout, change_password, change_username
from controllers.product_controller import get_all as products_get_all, get_categories, create as product_create, update as product_update, deactivate as product_deactivate
from controllers.transaction_controller import get_all as txns_get_all, record_inward, record_outward, clear_all as txns_clear_all
from controllers.report_controller import get_dashboard, get_alerts, get_valuation, get_ledger, get_aging, get_audit, get_users, toggle_user, delete_user

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')
PORT = 8000


class StockSphereHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  {self.address_string()} {format % args}")

    def _get_token(self):
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth[7:]
        return None

    def _require_auth(self):
        token = self._get_token()
        user = verify_token(token)
        if not user:
            self._json(401, {'error': 'Authentication required. Please sign in.'})
            return None
        return user

    def _require_role(self, role):
        user = self._require_auth()
        if not user:
            return None
        if not has_role(user['role'], role):
            self._json(403, {'error': f'Requires {role} role or higher.'})
            return None
        return user

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length:
            raw = self.rfile.read(length)
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    def _json(self, status, data):
        body = json.dumps(data, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path):
        if not os.path.exists(path) or not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')
            return
        mime, _ = mimetypes.guess_type(path)
        mime = mime or 'application/octet-stream'
        with open(path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)
        params = {k: v[0] for k, v in qs.items()}

        # API routes
        if path.startswith('/api'):
            self._handle_get_api(path, params)
        else:
            # Serve frontend files
            if path == '' or path == '/':
                self._serve_file(os.path.join(FRONTEND_DIR, 'index.html'))
            else:
                rel = path.lstrip('/')
                self._serve_file(os.path.join(FRONTEND_DIR, rel))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        body = self._read_body()
        self._handle_post_api(path, body)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        body = self._read_body()
        self._handle_put_api(path, body)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        self._handle_delete_api(path)

    def _handle_get_api(self, path, params):
        # Auth
        if path == '/api/auth/me':
            user = self._require_auth()
            if user:
                self._json(200, user)

        # Dashboard
        elif path == '/api/dashboard':
            user = self._require_auth()
            if user:
                status, data = get_dashboard()
                self._json(status, data)

        # Products
        elif path == '/api/products':
            user = self._require_auth()
            if user:
                status, data = products_get_all(params)
                self._json(status, data)

        elif path == '/api/products/categories':
            user = self._require_auth()
            if user:
                status, data = get_categories()
                self._json(status, data)

        # Transactions
        elif path == '/api/transactions':
            user = self._require_auth()
            if user:
                txn_type = params.get('type')
                search = params.get('search')
                status, data = txns_get_all(txn_type, search)
                self._json(status, data)

        # Reports
        elif path == '/api/reports/alerts':
            user = self._require_auth()
            if user:
                status, data = get_alerts()
                self._json(status, data)

        elif path == '/api/reports/valuation':
            user = self._require_auth()
            if user:
                status, data = get_valuation()
                self._json(status, data)

        elif path == '/api/reports/ledger':
            user = self._require_auth()
            if user:
                status, data = get_ledger()
                self._json(status, data)

        elif path == '/api/reports/aging':
            user = self._require_auth()
            if user:
                status, data = get_aging()
                self._json(status, data)

        elif path == '/api/audit':
            user = self._require_auth()
            if user:
                status, data = get_audit(params.get('search'))
                self._json(status, data)

        elif path == '/api/users':
            user = self._require_role('admin')
            if user:
                status, data = get_users()
                self._json(status, data)

        else:
            self._json(404, {'error': 'API endpoint not found.'})

    def _handle_post_api(self, path, body):
        if path == '/api/auth/login':
            status, data = login(body)
            self._json(status, data)

        elif path == '/api/auth/register':
            status, data = register(body)
            self._json(status, data)

        elif path == '/api/auth/logout':
            user = self._require_auth()
            if user:
                token = self._get_token()
                status, data = logout(token, user)
                self._json(status, data)

        elif path == '/api/auth/change-password':
            user = self._require_auth()
            if user:
                status, data = change_password(body, user)
                self._json(status, data)

        elif path == '/api/auth/change-username':
            user = self._require_auth()
            if user:
                status, data = change_username(body, user)
                self._json(status, data)

        elif path == '/api/products':
            user = self._require_role('staff')
            if user:
                status, data = product_create(body, user)
                self._json(status, data)

        elif path == '/api/transactions/inward':
            user = self._require_role('staff')
            if user:
                status, data = record_inward(body, user)
                self._json(status, data)

        elif path == '/api/transactions/outward':
            user = self._require_role('staff')
            if user:
                status, data = record_outward(body, user)
                self._json(status, data)

        else:
            self._json(404, {'error': 'API endpoint not found.'})

    def _handle_put_api(self, path, body):
        # PUT /api/products/:id
        m = re.match(r'^/api/products/(\d+)$', path)
        if m:
            user = self._require_role('staff')
            if user:
                status, data = product_update(int(m.group(1)), body, user)
                self._json(status, data)
            return

        # PUT /api/users/:id/toggle
        m = re.match(r'^/api/users/(\d+)/toggle$', path)
        if m:
            user = self._require_role('admin')
            if user:
                status, data = toggle_user(int(m.group(1)), user)
                self._json(status, data)
            return

        self._json(404, {'error': 'API endpoint not found.'})

    def _handle_delete_api(self, path):
        m = re.match(r'^/api/products/(\d+)$', path)
        if m:
            user = self._require_role('staff')
            if user:
                status, data = product_deactivate(int(m.group(1)), user)
                self._json(status, data)
            return

        # DELETE /api/users/:id
        m = re.match(r'^/api/users/(\d+)$', path)
        if m:
            user = self._require_role('admin')
            if user:
                status, data = delete_user(int(m.group(1)), user)
                self._json(status, data)
            return

        # DELETE /api/transactions
        if path == '/api/transactions':
            user = self._require_role('admin')
            if user:
                status, data = txns_clear_all(user)
                self._json(status, data)
            return

        self._json(404, {'error': 'API endpoint not found.'})


if __name__ == '__main__':
    print("Initializing StockSphere database...")
    init_db()
    print(f"Starting server on http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")
    server = HTTPServer(('0.0.0.0', PORT), StockSphereHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
