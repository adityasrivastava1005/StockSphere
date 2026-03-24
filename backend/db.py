import os
import psycopg
from psycopg.rows import dict_row
import hashlib
from datetime import datetime, timedelta

# Fetch the database URL from Render's environment variables
DATABASE_URL = os.environ.get('DATABASE_URL')

class CursorPolyfill:
    """Wraps the Postgres cursor to act like SQLite so controllers don't need rewriting."""
    def __init__(self, cursor):
        self.cursor = cursor
        self._lastrowid = None

    def execute(self, query, params=None):
        # 1. Replace SQLite '?' with Postgres '%s'
        q = query.replace('?', '%s')
        
        # 2. Append RETURNING id for inserts (to polyfill SQLite's lastrowid)
        is_insert = q.strip().upper().startswith("INSERT")
        if is_insert and "RETURNING" not in q.upper():
            if "INTO sessions" not in q and "INTO SESSIONS" not in q:
                q += " RETURNING id"
        
        # 3. Execute query
        if params:
            self.cursor.execute(q, params)
        else:
            self.cursor.execute(q)
        
        # 4. Capture the returned ID
        if is_insert and "RETURNING id" in q:
            try:
                res = self.cursor.fetchone()
                if res and 'id' in res:
                    self._lastrowid = res['id']
            except Exception:
                pass
        
        return self

    def executemany(self, query, params_seq):
        q = query.replace('?', '%s')
        self.cursor.executemany(q, params_seq)
        return self

    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    
    @property
    def lastrowid(self): return self._lastrowid

class ConnPolyfill:
    def __init__(self, conn): self.conn = conn
    def execute(self, query, params=None): return self.cursor().execute(query, params)
    def commit(self): self.conn.commit()
    def close(self): self.conn.close()
    def cursor(self): return CursorPolyfill(self.conn.cursor())

def get_conn():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set!")
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return ConnPolyfill(conn)

def hash_password(password):
    salt = "stocksphere_salt_v1"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def init_db():
    if not DATABASE_URL:
        print("Skipping DB Init: DATABASE_URL not set.")
        return
    
    conn = get_conn()
    c = conn.cursor()
    # Postgres schema updates (SERIAL instead of AUTOINCREMENT, TIMESTAMP etc.)
    c.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','manager','staff','finance')),
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'pcs',
            current_stock INTEGER DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 10,
            unit_price REAL NOT NULL DEFAULT 0,
            opening_stock INTEGER DEFAULT 0,
            total_in INTEGER DEFAULT 0,
            total_out INTEGER DEFAULT 0,
            supplier TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            txn_type TEXT NOT NULL CHECK(txn_type IN ('INWARD','OUTWARD','RETURN','ADJUSTMENT')),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            party TEXT NOT NULL,
            unit_price REAL,
            reason TEXT,
            remarks TEXT,
            txn_date TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            detail TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    _seed(conn)
    conn.close()

def _seed(conn):
    c = conn.cursor()
    
    # Check if already seeded 
    c.execute("SELECT COUNT(*) as count FROM users")
    if c.fetchone()['count'] > 0:
        return

    users = [
        ('Admin User',   'admin',   hash_password('admin123'),   'admin'),
        ('Rahul Sharma', 'rahul',   hash_password('staff123'),   'staff'),
        ('Anjali Verma', 'anjali',  hash_password('manager123'), 'manager'),
        ('Finance User', 'finance', hash_password('finance123'), 'finance'),
        ('Priya Gupta',  'priya',   hash_password('staff123'),   'staff'),
    ]
    c.executemany("INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)", users)
    conn.commit()

    c.execute("SELECT username, id FROM users")
    uid = {row['username']: row['id'] for row in c.fetchall()}

    products = [
        ('ELEC-001','Circuit Board A3',   'Electronics',  'pcs',   340, 50,  480, 300,100, 60,'ABC Distributors'),
        ('ELEC-002','DC Motor 12V',        'Electronics',  'pcs',    82, 30, 1200, 100, 20, 38,'Tech World'),
        ('RAW-001', 'Steel Rod 10mm',      'Raw Materials','kg',   1200,200,   45,1000,400,200,'Sharma Enterprises'),
        ('RAW-002', 'Aluminium Sheet 2mm', 'Raw Materials','kg',     88,100,  320,  90, 50, 52,'Metro Metals'),
        ('PKG-001', 'Bubble Wrap Roll',    'Packaging',   'rolls',   18, 40,   90,  50, 10, 42,'Pack Masters'),
        ('PKG-002', 'Cardboard Box L',     'Packaging',   'pcs',      9, 60,   25,  70,  0, 61,'BoxCo'),
        ('TOOL-001','Hand Drill 500W',     'Tools',       'pcs',     15, 10, 2200,  12,  5,  2,'ToolKing'),
        ('TOOL-002','Measuring Tape 5m',   'Tools',       'pcs',      7, 15,  150,  20,  0, 13,'ToolKing'),
        ('CONS-001','Industrial Gloves L', 'Consumables', 'pairs',  220, 50,   35, 200,100, 80,'Safety First'),
        ('CONS-002','Cutting Disc 4"',     'Consumables', 'pcs',    145, 30,   22, 100, 80, 35,'Abrasives Ltd'),
    ]
    c.executemany("""INSERT INTO products(sku,name,category,unit,current_stock,reorder_level,
        unit_price,opening_stock,total_in,total_out,supplier) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", products)
    conn.commit()

    today = datetime.now()
    txns_raw = [
        ('INWARD',  1,100,'ABC Distributors',  480,'Purchase Order',15,'admin'),
        ('INWARD',  3,400,'Sharma Enterprises', 45,'Purchase Order',12,'rahul'),
        ('OUTWARD', 5, 32,'Production Floor',  None,'Internal Use', 10,'priya'),
        ('OUTWARD', 4, 52,'Sales Dept',         None,'Sale Order',   8,'rahul'),
        ('INWARD',  2, 20,'Tech World',        1200,'Replenishment', 7,'rahul'),
        ('OUTWARD', 6, 61,'External Customer',  None,'Sale Order',   5,'priya'),
        ('INWARD',  9,100,'Safety First',        35,'Monthly order', 4,'admin'),
        ('OUTWARD', 7,  2,'Production Floor',  None,'Internal Use',  3,'rahul'),
        ('OUTWARD', 8, 13,'Sales Dept',          None,'Sale Order',  2,'priya'),
        ('INWARD', 10, 80,'Abrasives Ltd',       22,'Reorder',       1,'rahul'),
        ('OUTWARD', 2, 38,'Sales Dept',          None,'Sale Order',  1,'admin'),
    ]
    for t in txns_raw:
        txn_type, product_id, qty, party, price, reason, days_ago, uname = t
        txn_date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        c.execute("""INSERT INTO transactions(txn_type,product_id,quantity,party,unit_price,
            reason,txn_date,username,user_id) VALUES(?,?,?,?,?,?,?,?,?)""",
            (txn_type, product_id, qty, party, price, reason, txn_date, uname, uid.get(uname)))

    audit_entries = [
        ('USER_LOGIN',      'admin',           'User admin signed in',                      'admin', 'admin'),
        ('PRODUCT_ADD',     'Circuit Board A3','Product ELEC-001 registered, stock: 300',   'admin', 'admin'),
        ('STOCK_INWARD',    'Circuit Board A3','Received 100 pcs from ABC Distributors',    'rahul', 'rahul'),
        ('STOCK_INWARD',    'Steel Rod 10mm',  'Received 400 kg from Sharma Enterprises',   'rahul', 'rahul'),
        ('STOCK_OUTWARD',   'Bubble Wrap Roll','Dispatched 32 rolls to Production Floor',   'priya', 'priya'),
        ('LOW_STOCK_ALERT', 'Cardboard Box L', 'Stock (9) at or below reorder level (60)',  None,     None),
    ]
    for action, entity, detail, uname, uid_key in audit_entries:
        user_id = uid.get(uid_key) if uid_key else None
        c.execute("INSERT INTO audit_logs(action,entity,detail,username,user_id) VALUES(?,?,?,?,?)",
                  (action, entity, detail, uname, user_id))

    conn.commit()
    print("Database seeded with demo data.")

if __name__ == '__main__':
    init_db()